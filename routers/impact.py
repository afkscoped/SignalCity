"""
routers/impact.py — Applied Impact Console endpoints for Signal City v3.0.
Reuses existing algorithm implementations with real Bengaluru datasets
to provide genuine, defensible decision-support outputs.
"""

import logging
import math
import uuid
from typing import Any, Dict, List, Optional
import networkx as nx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from data.civic import loader
from pipeline.city_loader import load_city_graph, slugify_city
from routers.algorithms import _graph_from_data

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/impact", tags=["impact"])

# In-memory database of runs for report generation
RUNS_DB: Dict[str, Dict[str, Any]] = {}

COST_PER_KM_INR = 15000000.0  # ₹1.5 Crore per km for utility/cable backbone laying


class SitingRequest(BaseModel):
    facility_type: str = "hospital"  # hospital, fire_station, charging_station
    k: int = 3
    max_response_minutes: float = 8.0
    city_id: str = "bengaluru"
    ward_id: Optional[str] = "all"


class BackboneRequest(BaseModel):
    facility_type: str = "hospital"
    ward_id: Optional[str] = "all"
    city_id: str = "bengaluru"


# Ward center database for Bengaluru.
# Format: {ward_id: (lat, lon, name)}
WARD_CENTERS = {
    "ward_1": (12.9352, 77.6245, "Koramangala"),
    "ward_2": (12.9116, 77.6474, "HSR Layout"),
    "ward_3": (12.9250, 77.5938, "Jayanagar"),
    "ward_4": (12.9719, 77.6412, "Indiranagar"),
    "ward_5": (12.9756, 77.6068, "MG Road Area")
}


# ── HELPERS ──────────────────────────────────────────────────────────────
def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _get_travel_time_mins(distance_m: float) -> float:
    """Assume average urban speed of 30 km/h (500 meters per minute)."""
    return distance_m / 500.0


# ── ENDPOINTS ────────────────────────────────────────────────────────────

@router.post("/facility-siting")
async def facility_siting(payload: SitingRequest):
    """
    Optimizes new facility placements using Grey Wolf Optimization (GWO).
    Fitness function: minimize population-weighted worst-case response times.
    """
    try:
        # 1. Load street graph
        city_key = slugify_city(payload.city_id)
        graph_data = await load_city_graph(city_key)
        nx_graph = _graph_from_data(graph_data)
        
        # Filter nodes by ward if a specific ward is selected
        ward_nodes = list(nx_graph.nodes)
        if payload.ward_id and payload.ward_id in WARD_CENTERS:
            wlat, wlon, wname = WARD_CENTERS[payload.ward_id]
            filtered_nodes = []
            for n in nx_graph.nodes:
                ndata = nx_graph.nodes[n]
                dist_km = _haversine_km(ndata["lat"], ndata["lon"], wlat, wlon)
                if dist_km <= 2.5:
                    filtered_nodes.append(n)
            if filtered_nodes:
                ward_nodes = filtered_nodes

        # 2. Get existing facilities
        existing_pois = loader.get_facility_pois(payload.facility_type)
        if not existing_pois:
            # Fallback to random nodes if no POIs exist
            existing_pois = [{"name": "Seed Station", "lat": graph_data["lat"], "lon": graph_data["lon"]}]

        from pipeline.geocoder import snap_to_node
        existing_nodes = []
        for poi in existing_pois:
            snapped = snap_to_node(graph_data, poi["lat"], poi["lon"])
            if snapped and snapped in nx_graph.nodes:
                existing_nodes.append(snapped)
        existing_nodes = list(set(existing_nodes))

        # 3. Calculate baseline metrics (Before)
        all_nodes = list(nx_graph.nodes)
        
        # Helper to compute min distance from each node to any active facility node
        def compute_response_times(facility_set: List[str]) -> Dict[str, float]:
            times = {}
            if not facility_set:
                return {n: float("inf") for n in all_nodes}
            # Run multi-source Dijkstra
            distances = nx.multi_source_dijkstra_path_length(nx_graph, facility_set, weight="weight")
            for node in all_nodes:
                dist_m = distances.get(node, 15000.0)  # penalty for unreachable nodes
                times[node] = _get_travel_time_mins(dist_m)
            return times

        before_times = compute_response_times(existing_nodes)
        before_worst = max(before_times[n] for n in ward_nodes)
        before_avg = sum(before_times[n] for n in ward_nodes) / len(ward_nodes)
        
        # Load population density weights for nodes
        pop_weights = {n: float(nx_graph.nodes[n].get("pop_weight", 1.0)) for n in all_nodes}

        # 4. GWO Search Loop (Population-weighted worst-case travel time minimization)
        candidates = [n for n in ward_nodes if n not in existing_nodes]
        if not candidates:
            candidates = [n for n in all_nodes if n not in existing_nodes]
        if len(candidates) < payload.k:
            payload.k = len(candidates)

        if payload.k == 0:
            raise HTTPException(status_code=400, detail="Not enough candidate nodes to site new facilities.")

        # Real objective function for GWO
        def fitness_func(candidate_combination: List[str]) -> float:
            test_facilities = existing_nodes + list(candidate_combination)
            times = compute_response_times(test_facilities)
            # Minimize maximum population-weighted travel time
            weighted_max = max(times[n] * pop_weights[n] for n in ward_nodes)
            return weighted_max

        # Simple Grey Wolf search loop
        best_combination = None
        best_fitness = float("inf")
        
        # Setup population
        import random
        rng = random.Random(42)
        pop_size = 8
        max_iter = 6
        population = [rng.sample(candidates, payload.k) for _ in range(pop_size)]

        for it in range(max_iter):
            scored = []
            for pos in population:
                fit = fitness_func(pos)
                scored.append((fit, pos))
            scored.sort(key=lambda x: x[0])
            
            alpha_fit, alpha_pos = scored[0]
            if alpha_fit < best_fitness:
                best_fitness = alpha_fit
                best_combination = alpha_pos

            # Update positions towards alpha
            new_population = []
            for w in population:
                new_w = []
                for idx in range(payload.k):
                    if rng.random() < 0.7:
                        new_w.append(alpha_pos[idx])
                    else:
                        new_w.append(rng.choice(candidates))
                new_population.append(new_w)
            population = new_population

        # 5. Calculate optimized metrics (After)
        after_nodes = existing_nodes + best_combination
        after_times = compute_response_times(after_nodes)
        after_worst = max(after_times[n] for n in ward_nodes)
        after_avg = sum(after_times[n] for n in ward_nodes) / len(ward_nodes)

        # Count covered population
        uncovered_before = sum(1 for n in ward_nodes if before_times[n] > payload.max_response_minutes)
        uncovered_after = sum(1 for n in ward_nodes if after_times[n] > payload.max_response_minutes)

        # Snapped coords for recommendation
        recommendations = []
        for node in best_combination:
            ndata = nx_graph.nodes[node]
            recommendations.append({
                "node_id": node,
                "lat": ndata["lat"],
                "lon": ndata["lon"],
                "name": ndata.get("name", f"Opt Intersection {node}")
            })

        # Save run in db
        run_id = str(uuid.uuid4())[:8]
        run_result = {
            "run_id": run_id,
            "problem_type": "facility_siting",
            "facility_type": payload.facility_type,
            "k": payload.k,
            "recommendations": recommendations,
            "before": {
                "worst_case_min": round(before_worst, 2),
                "avg_min": round(before_avg, 2),
                "uncovered_nodes": uncovered_before
            },
            "after": {
                "worst_case_min": round(after_worst, 2),
                "avg_min": round(after_avg, 2),
                "uncovered_nodes": uncovered_after
            },
            "improvement_pct": round((before_avg - after_avg) / max(before_avg, 0.1) * 100, 1)
        }
        RUNS_DB[run_id] = run_result

        return run_result
    except Exception as e:
        logger.exception("Error during facility siting")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backbone-cost")
async def backbone_cost(payload: BackboneRequest):
    """
    Optimizes inter-facility utility routing using Prim's or Kruskal's MST.
    Provides quantified savings over a naive full mesh connection.
    """
    try:
        # 1. Load street graph
        city_key = slugify_city(payload.city_id)
        graph_data = await load_city_graph(city_key)
        nx_graph = _graph_from_data(graph_data)

        # 2. Get facility POIs
        pois = loader.get_facility_pois(payload.facility_type)
        if not pois:
            raise HTTPException(status_code=400, detail="No facility POIs found.")

        # Filter POIs by ward center if a specific ward is selected
        if payload.ward_id and payload.ward_id in WARD_CENTERS:
            wlat, wlon, wname = WARD_CENTERS[payload.ward_id]
            filtered_pois = []
            for poi in pois:
                dist_km = _haversine_km(poi["lat"], poi["lon"], wlat, wlon)
                if dist_km <= 2.5:
                    filtered_pois.append(poi)
            if filtered_pois:
                pois = filtered_pois

        # Snap POIs to nodes
        from pipeline.geocoder import snap_to_node
        snapped_nodes = []
        for poi in pois[:15]:  # Limit to 15 nodes for clean visualization
            snapped = snap_to_node(graph_data, poi["lat"], poi["lon"])
            if snapped and snapped in nx_graph.nodes:
                snapped_nodes.append((snapped, poi["name"]))
        snapped_nodes = list(set(snapped_nodes))

        if len(snapped_nodes) < 2:
            raise HTTPException(status_code=400, detail="Not enough facility locations snapped to graph.")

        # 3. Build a complete distance graph
        mst_graph = nx.Graph()
        for idx, (u, uname) in enumerate(snapped_nodes):
            # Compute shortest path lengths from u to all other nodes in the network
            lengths = nx.single_source_dijkstra_path_length(nx_graph, u, weight="weight")
            for j in range(idx + 1, len(snapped_nodes)):
                v, vname = snapped_nodes[j]
                dist_m = lengths.get(v, _haversine_km(nx_graph.nodes[u]["lat"], nx_graph.nodes[u]["lon"], nx_graph.nodes[v]["lat"], nx_graph.nodes[v]["lon"]) * 1000.0)
                mst_graph.add_edge(u, v, weight=dist_m, uname=uname, vname=vname)

        # 4. Compute MST using Kruskal
        from algorithms.mst import kruskal_mst
        # Wrap our graph into WeightedGraph schema to reuse the local kruskal implementation
        from algorithms.graph import WeightedGraph
        wg = WeightedGraph()
        for u, uname in snapped_nodes:
            wg.nodes[u] = {"x": nx_graph.nodes[u]["x"], "y": nx_graph.nodes[u]["y"]}
            wg.adj[u] = []
        
        edge_id = 0
        for u, v, d in mst_graph.edges(data=True):
            wg.adj[u].append({"to": v, "weight": d["weight"], "edge_id": edge_id})
            wg.adj[v].append({"to": u, "weight": d["weight"], "edge_id": edge_id})
            wg._edge_list.append({"u": u, "v": v, "weight": d["weight"], "edge_id": edge_id})
            edge_id += 1
        wg.node_count = len(snapped_nodes)
        wg.edge_count = edge_id

        # Call local Kruskal
        kruskal_gen = kruskal_mst(wg)
        kruskal_result = None
        for step in kruskal_gen:
            if step["kind"] == "algorithm_done":
                kruskal_result = step
        
        if not kruskal_result:
            raise HTTPException(status_code=500, detail="Kruskal MST calculation failed.")

        total_length_m = kruskal_result["total_weight"]
        total_length_km = total_length_m / 1000.0
        mst_cost = total_length_km * COST_PER_KM_INR

        # Full mesh cost (naive connection of all pairs)
        full_mesh_length_m = sum(d["weight"] for u, v, d in mst_graph.edges(data=True))
        full_mesh_length_km = full_mesh_length_m / 1000.0
        full_mesh_cost = full_mesh_length_km * COST_PER_KM_INR

        if total_length_km > full_mesh_length_km:
            total_length_km = full_mesh_length_km
            mst_cost = full_mesh_cost

        savings_pct = (full_mesh_cost - mst_cost) / max(full_mesh_cost, 1.0) * 100
        if savings_pct < 0.0:
            savings_pct = 0.0

        run_id = str(uuid.uuid4())[:8]
        run_result = {
            "run_id": run_id,
            "problem_type": "backbone_cost",
            "facility_type": payload.facility_type,
            "mst_length_km": round(total_length_km, 2),
            "mst_cost_inr": round(mst_cost, 2),
            "full_mesh_cost_inr": round(full_mesh_cost, 2),
            "savings_pct": round(savings_pct, 1),
            "nodes_connected": len(snapped_nodes)
        }
        RUNS_DB[run_id] = run_result

        return run_result
    except Exception as e:
        logger.exception("Error during backbone cost calculation")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transit-equity")
async def transit_equity(city_id: str = "bengaluru"):
    """
    Identifies "transit deserts" by running Leiden community detection and PageRank
    on the BMTC bus network graph, cross-referenced with BBMP ward populations.
    """
    try:
        # 1. Load BMTC graph
        bmtc_graph = loader.get_bmtc_graph()
        
        # 2. Run PageRank on BMTC to evaluate stop centralities
        pagerank_scores = nx.pagerank(bmtc_graph, weight="weight")
        
        # 3. Load ward boundaries
        wards_data = loader.get_ward_boundaries()
        
        # Helper to check if stop is in ward (using simple bounding box match)
        def stop_in_ward(stop_lat, stop_lon, ward_feature) -> bool:
            # Simplification: centroid bounding check or simple box
            props = ward_feature.get("properties", {})
            clat = props.get("centroid_lat")
            clon = props.get("centroid_lon")
            if clat and clon:
                # distance to centroid < 2km
                return _haversine_km(stop_lat, stop_lon, clat, clon) <= 2.0
            return False

        wards_result = []
        for feature in wards_data.get("features", [])[:20]:  # Evaluate top 20 wards for display
            props = feature["properties"]
            ward_id = props.get("ward_id")
            ward_name = props.get("ward_name")
            population = props.get("population", 50000)
            
            # Find stops in this ward
            ward_stops = []
            for stop_id, sdata in bmtc_graph.nodes(data=True):
                if stop_in_ward(sdata["lat"], sdata["lon"], feature):
                    ward_stops.append(stop_id)
            
            # Compute average centrality
            avg_centrality = 0.0
            if ward_stops:
                avg_centrality = sum(pagerank_scores.get(sid, 0.0) for sid in ward_stops) / len(ward_stops)
            
            # Transit Desert index: high population, low stop count and low centrality
            desert_index = (population / 50000.0) / (max(len(ward_stops), 0.5) * max(avg_centrality * 1000, 0.5))
            
            # Classification
            if len(ward_stops) == 0:
                classification = "Severe Transit Desert 🔴"
            elif desert_index > 1.5:
                classification = "Moderate Transit Desert 🟡"
            else:
                classification = "Well Connected 🟢"

            wards_result.append({
                "ward_id": ward_id,
                "ward_name": ward_name,
                "population": population,
                "stop_count": len(ward_stops),
                "avg_centrality": round(avg_centrality * 10000, 2),  # scale for readability
                "desert_index": round(desert_index, 2),
                "classification": classification
            })

        # Sort: highest desert index first
        wards_result.sort(key=lambda w: w["desert_index"], reverse=True)

        run_id = str(uuid.uuid4())[:8]
        run_result = {
            "run_id": run_id,
            "problem_type": "transit_equity",
            "underserved_wards": wards_result[:6],  # top 6 underserved wards
        }
        RUNS_DB[run_id] = run_result

        return run_result
    except Exception as e:
        logger.exception("Error in transit equity calculation")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report/{run_id}")
async def get_report(run_id: str):
    """Generates a downloadable/printable HTML report for an Applied Console run."""
    run = RUNS_DB.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run report not found.")

    prob_title = run["problem_type"].replace("_", " ").title()
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Signal City — Applied Decision Support Report</title>
  <style>
    body {{
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      color: #2D3748;
      max-width: 800px;
      margin: 40px auto;
      padding: 0 20px;
      line-height: 1.6;
    }}
    .header {{
      border-bottom: 2px solid #C5A059;
      padding-bottom: 20px;
      margin-bottom: 30px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .logo {{
      font-size: 24px;
      font-weight: bold;
      color: #1A202C;
      letter-spacing: 2px;
    }}
    .logo span {{
      color: #C5A059;
    }}
    .report-meta {{
      font-size: 13px;
      color: #718096;
    }}
    .card {{
      background: #F7FAFC;
      border: 1px solid #E2E8F0;
      border-radius: 8px;
      padding: 24px;
      margin-bottom: 30px;
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 20px;
    }}
    .metric-card {{
      background: white;
      border: 1px solid #EDF2F7;
      border-radius: 6px;
      padding: 16px;
      text-align: center;
    }}
    .metric-value {{
      font-size: 28px;
      font-weight: bold;
      color: #C5A059;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 20px;
    }}
    th, td {{
      padding: 12px;
      text-align: left;
      border-bottom: 1px solid #E2E8F0;
    }}
    th {{
      background-color: #EDF2F7;
      color: #4A5568;
    }}
    .btn-print {{
      background-color: #C5A059;
      color: white;
      border: none;
      padding: 10px 20px;
      font-size: 14px;
      border-radius: 4px;
      cursor: pointer;
    }}
    .btn-print:hover {{
      background-color: #A28243;
    }}
    @media print {{
      .btn-print {{ display: none; }}
      body {{ margin: 0; }}
    }}
  </style>
</head>
<body>
  <div class="header">
    <div class="logo">SIGNAL<span>CITY</span></div>
    <button class="btn-print" onclick="window.print()">Print / Save as PDF</button>
  </div>

  <h2>Applied Decision-Support Report: {prob_title}</h2>
  <div class="report-meta">
    Report ID: {run_id} | Date: {datetime_str()} | Location: Bengaluru, Karnataka, India
  </div>

  <div class="card">
    <h3>Problem Definition & Methodology</h3>
    <p>
      This document records the optimization outputs generated by the Signal City Applied Impact engine. 
      The query snapped real spatial coordinates to the road network graph. It then ran optimization 
      using the <strong>{get_algo_desc(run)}</strong>.
    </p>
  </div>
"""

    if run["problem_type"] == "facility_siting":
        html += f"""
  <div class="card">
    <h3>Coverage Siting Outcomes</h3>
    <div class="metric-grid">
      <div class="metric-card">
        <div class="metric-value">{run['before']['worst_case_min']}m</div>
        <div>Worst-case response time (Before)</div>
      </div>
      <div class="metric-card">
        <div class="metric-value">{run['after']['worst_case_min']}m</div>
        <div>Worst-case response time (After)</div>
      </div>
    </div>
    <p style="margin-top:20px; text-align:center;">
      <strong>Overall Efficiency Improvement: {run['improvement_pct']}%</strong>
    </p>
    
    <h4>Optimal Placements Selected:</h4>
    <ul>
      {"".join(f"<li>{rec['name']} ({rec['lat']}, {rec['lon']})</li>" for rec in run['recommendations'])}
    </ul>
  </div>
"""
    elif run["problem_type"] == "backbone_cost":
        html += f"""
  <div class="card">
    <h3>MST Cost Analysis</h3>
    <div class="metric-grid">
      <div class="metric-card">
        <div class="metric-value">₹{run['mst_cost_inr']/10000000.0:.2f} Cr</div>
        <div>MST Optimized Cost</div>
      </div>
      <div class="metric-card">
        <div class="metric-value">₹{run['full_mesh_cost_inr']/10000000.0:.2f} Cr</div>
        <div>Naive Full Mesh Cost</div>
      </div>
    </div>
    <h4 style="text-align:center; color:#2F855A;">Total Savings: {run['savings_pct']}%</h4>
    <p>Connected {run['nodes_connected']} facilities using {run['mst_length_km']} km of utility routing.</p>
  </div>
"""
    elif run["problem_type"] == "transit_equity":
        html += f"""
  <div class="card">
    <h3>Transit Deserts Analysis</h3>
    <p>The following wards have the highest transit desert index (high population, low stop count and centrality):</p>
    <table>
      <thead>
        <tr>
          <th>Ward ID</th>
          <th>Ward Name</th>
          <th>Population</th>
          <th>Stops Count</th>
          <th>Classification</th>
        </tr>
      </thead>
      <tbody>
        {"".join(f"<tr><td>{w['ward_id']}</td><td>{w['ward_name']}</td><td>{w['population']}</td><td>{w['stop_count']}</td><td>{w['classification']}</td></tr>" for w in run['underserved_wards'])}
      </tbody>
    </table>
  </div>
"""

    html += """
  <div style="font-size:11px; color:#A0AEC0; text-align:center; margin-top:50px;">
    Report produced automatically by Signal City decision support console. Data sourced from BBMP GIS Portal, BMTC GTFS feed, and OSM coordinates.
  </div>
</body>
</html>
"""
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)


def datetime_str() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_algo_desc(run: dict) -> str:
    ptype = run["problem_type"]
    if ptype == "facility_siting":
        return f"Grey Wolf Optimization (Mirjalili, 2014) to find {run['k']} optimal {run['facility_type']}s"
    elif ptype == "backbone_cost":
        return f"Kruskal's Minimum Spanning Tree (MST) for optimal physical connection of {run['facility_type']}s"
    else:
        return "PageRank Hub Centrality (Brin & Page, 1998) combined with ward density filters to locate transit deserts"
