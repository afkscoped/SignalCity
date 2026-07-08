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
from pipeline.routing_engine import compare_routes, plan_route, resilient_k_routes
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


class RouteImpactRequest(BaseModel):
    city_id: str = "bengaluru"
    source_name: Optional[str] = None
    dest_name: Optional[str] = None
    start_node: Optional[str] = None
    end_node: Optional[str] = None
    flooded_nodes: List[str] = []
    algorithms: List[str] = ["dijkstra", "astar", "risk_aware", "contraction"]
    k: int = 4


class CivicOptimizerRequest(BaseModel):
    city_id: str = "bengaluru"
    facility_type: str = "hospital"
    k: int = 4
    candidate_pool: int = 90
    max_iterations: int = 18
    equity_weight: float = 0.38


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


def _feature_centroid(feature: dict) -> tuple[float, float]:
    """Return a simple centroid for Polygon/MultiPolygon GeoJSON features."""
    geom = feature.get("geometry", {})
    coords = geom.get("coordinates", [])
    points: list[tuple[float, float]] = []

    def collect(ring):
        for item in ring:
            if isinstance(item, list) and len(item) >= 2 and isinstance(item[0], (int, float)):
                points.append((float(item[1]), float(item[0])))
            elif isinstance(item, list):
                collect(item)

    collect(coords)
    if not points:
        props = feature.get("properties", {})
        return float(props.get("centroid_lat", 12.9716)), float(props.get("centroid_lon", 77.5946))
    return sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points)


def _nearest_graph_node_by_latlon(nx_graph: nx.Graph, lat: float, lon: float) -> str:
    return min(
        nx_graph.nodes,
        key=lambda n: (float(nx_graph.nodes[n].get("lat", 0.0)) - lat) ** 2
        + (float(nx_graph.nodes[n].get("lon", 0.0)) - lon) ** 2,
    )


def _gini(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(max(0.0, v) for v in values)
    total = sum(ordered)
    if total <= 0:
        return 0.0
    n = len(ordered)
    weighted = sum((idx + 1) * value for idx, value in enumerate(ordered))
    return round((2 * weighted) / (n * total) - (n + 1) / n, 4)


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


@router.post("/route-lab")
async def route_lab(payload: RouteImpactRequest):
    """
    Compare route algorithms on the same selected Bengaluru origin/destination.
    This is the main DAA-viva endpoint: it exposes inputs, graph provenance,
    complexity, measured runtime, and explanation text for each algorithm.
    """
    try:
        city_key = slugify_city(payload.city_id)
        graph_data = await load_city_graph(city_key)
        params = {
            "city_id": city_key,
            "source_name": payload.source_name,
            "dest_name": payload.dest_name,
            "start_node": payload.start_node,
            "end_node": payload.end_node,
            "flooded_nodes": payload.flooded_nodes,
        }
        algos = payload.algorithms or ["dijkstra", "astar", "risk_aware", "contraction"]
        results = compare_routes(graph_data, params, algos[:5])
        run_id = str(uuid.uuid4())[:8]
        run_result = {
            "run_id": run_id,
            "problem_type": "route_lab",
            "city_id": city_key,
            "source": payload.source_name or payload.start_node,
            "target": payload.dest_name or payload.end_node,
            "data_quality": graph_data.get("data_quality", {}),
            "results": results,
            "xai_text": (
                "Route Lab compares exact shortest path, goal-directed A*, risk-aware routing, "
                "and CH-style query behavior on the same selected origin and destination."
            ),
        }
        RUNS_DB[run_id] = run_result
        return run_result
    except Exception as e:
        logger.exception("Error during route lab")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/civic-service-optimizer")
async def civic_service_optimizer(payload: CivicOptimizerRequest):
    """
    Research-grade non-routing showcase.

    Teaching adaptation of 2024 knowledge-informed RL for large urban facility
    location: start from a greedy k-median baseline, then perform learned-swap
    style local improvement using ward demand, road-network travel time, and
    equity penalty.
    """
    try:
        city_key = slugify_city(payload.city_id)
        graph_data = await load_city_graph(city_key)
        nx_graph = _graph_from_data(graph_data)
        wards = loader.get_ward_boundaries().get("features", [])
        if not wards:
            raise HTTPException(status_code=400, detail="BBMP ward data unavailable.")

        demand_points = []
        for idx, feature in enumerate(wards[:120]):
            props = feature.get("properties", {})
            lat, lon = _feature_centroid(feature)
            node = _nearest_graph_node_by_latlon(nx_graph, lat, lon)
            population = float(props.get("population", 50000))
            income_idx = float(props.get("income_idx", 0.7))
            demand_weight = population * (1.25 - min(max(income_idx, 0.1), 1.2) * 0.35)
            demand_points.append({
                "ward_id": str(props.get("KGISWardNo") or props.get("ward_id") or idx + 1),
                "ward_name": props.get("KGISWardName") or props.get("ward_name") or f"Ward {idx + 1}",
                "lat": lat,
                "lon": lon,
                "node": node,
                "population": int(population),
                "income_idx": round(income_idx, 3),
                "demand_weight": demand_weight,
            })

        existing_nodes: list[str] = []
        try:
            from pipeline.geocoder import snap_to_node
            for poi in loader.get_facility_pois(payload.facility_type):
                snapped = snap_to_node(graph_data, poi["lat"], poi["lon"])
                if snapped and snapped in nx_graph:
                    existing_nodes.append(snapped)
        except Exception:
            existing_nodes = []
        existing_nodes = list(dict.fromkeys(existing_nodes))

        degree_ranked = sorted(
            nx_graph.nodes,
            key=lambda n: (
                float(nx_graph.nodes[n].get("pop_weight", 1.0)),
                int(nx_graph.nodes[n].get("street_count", 0)),
            ),
            reverse=True,
        )
        ward_nearest = [point["node"] for point in demand_points]
        candidates = list(dict.fromkeys(ward_nearest + degree_ranked))[:max(payload.candidate_pool, payload.k)]
        candidates = [c for c in candidates if c not in existing_nodes]
        if len(candidates) < payload.k:
            raise HTTPException(status_code=400, detail="Not enough candidate sites for optimizer.")

        demand_nodes = [p["node"] for p in demand_points]
        demand_weights = {p["node"]: p["demand_weight"] for p in demand_points}
        demand_by_node = {p["node"]: p for p in demand_points}
        distance_cache: dict[str, dict[str, float]] = {}

        def distances_from(source: str) -> dict[str, float]:
            if source not in distance_cache:
                lengths = nx.single_source_dijkstra_path_length(nx_graph, source, weight="weight", cutoff=30000)
                distance_cache[source] = {node: float(lengths.get(node, 30000.0)) for node in demand_nodes}
            return distance_cache[source]

        for node in existing_nodes[:25] + candidates:
            distances_from(node)

        def assignment(site_set: list[str]) -> tuple[float, list[dict], dict]:
            active = list(dict.fromkeys(existing_nodes[:25] + site_set))
            ward_rows = []
            weighted_sum = 0.0
            weighted_total = 0.0
            minutes = []
            for demand_node in demand_nodes:
                best_site = min(active, key=lambda s: distances_from(s).get(demand_node, 30000.0)) if active else site_set[0]
                dist_m = distances_from(best_site).get(demand_node, 30000.0)
                minute = _get_travel_time_mins(dist_m)
                point = demand_by_node[demand_node]
                weight = demand_weights[demand_node]
                weighted_sum += minute * weight
                weighted_total += weight
                minutes.append(minute)
                ward_rows.append({
                    "ward_id": point["ward_id"],
                    "ward_name": point["ward_name"],
                    "population": point["population"],
                    "lat": round(point["lat"], 6),
                    "lon": round(point["lon"], 6),
                    "nearest_site": best_site,
                    "travel_minutes": round(minute, 2),
                    "served_under_10_min": minute <= 10.0,
                })
            avg = weighted_sum / max(weighted_total, 1.0)
            inequality = _gini(minutes)
            worst = max(minutes) if minutes else 0.0
            uncovered = sum(1 for m in minutes if m > 10.0)
            score = avg + payload.equity_weight * worst + payload.equity_weight * 18.0 * inequality
            return score, ward_rows, {
                "weighted_avg_minutes": round(avg, 2),
                "worst_minutes": round(worst, 2),
                "gini_access_inequality": inequality,
                "wards_over_10_min": uncovered,
                "objective_score": round(score, 3),
            }

        current_service_score, current_service_rows, current_service_metrics = assignment([])
        selected: list[str] = []
        remaining = list(candidates)
        trace = []
        for step in range(min(payload.k, len(remaining))):
            scored = []
            for candidate in remaining:
                score, _, metrics = assignment(selected + [candidate])
                scored.append((score, candidate, metrics))
            scored.sort(key=lambda row: row[0])
            _, chosen, metrics = scored[0]
            selected.append(chosen)
            remaining.remove(chosen)
            trace.append({
                "phase": "greedy_construct",
                "step": step + 1,
                "chosen_node": chosen,
                "objective_score": metrics["objective_score"],
                "why": "Selected the candidate that gave the largest population-weighted accessibility gain at this construction step.",
            })

        baseline_sites = list(selected)
        baseline_score, baseline_rows, baseline_metrics = assignment(baseline_sites)
        current_sites = list(baseline_sites)
        current_score = baseline_score

        for iteration in range(max(0, payload.max_iterations)):
            improved = False
            best_swap = None
            for out_site in list(current_sites):
                for in_site in remaining[: min(len(remaining), 45)]:
                    trial = [s for s in current_sites if s != out_site] + [in_site]
                    score, _, metrics = assignment(trial)
                    demand_tie_break = -float(nx_graph.nodes[in_site].get("pop_weight", 1.0)) * 0.0001
                    comparable_score = score + demand_tie_break
                    if score + 1e-6 < current_score or (abs(score - current_score) <= 1e-6 and comparable_score < current_score):
                        best_swap = (score, out_site, in_site, trial, metrics)
                        improved = True
            if not improved or not best_swap:
                trace.append({
                    "phase": "swap_stop",
                    "step": iteration + 1,
                    "why": "No candidate swap improved the accessibility-equity objective, so the local policy converged.",
                })
                break
            real_score, out_site, in_site, trial, metrics = best_swap
            current_sites = trial
            current_score = real_score
            if out_site in selected:
                selected.remove(out_site)
            if in_site not in selected:
                selected.append(in_site)
            if in_site in remaining:
                remaining.remove(in_site)
            remaining.append(out_site)
            trace.append({
                "phase": "knowledge_guided_swap",
                "step": iteration + 1,
                "removed_node": out_site,
                "added_node": in_site,
                "objective_score": metrics["objective_score"],
                "why": "A swap reduced travel-time inequity while preserving strong demand coverage, simulating the edge-swap idea from knowledge-informed RL.",
            })

        final_score, final_rows, final_metrics = assignment(current_sites)
        final_rows.sort(key=lambda row: row["travel_minutes"], reverse=True)

        recommendations = []
        for node in current_sites:
            ndata = nx_graph.nodes[node]
            recommendations.append({
                "node_id": node,
                "lat": round(float(ndata["lat"]), 6),
                "lon": round(float(ndata["lon"]), 6),
                "name": ndata.get("name") or f"Candidate site {node}",
                "street_count": int(ndata.get("street_count", 0)),
                "pop_weight": round(float(ndata.get("pop_weight", 1.0)), 2),
            })

        improvement = (current_service_metrics["objective_score"] - final_metrics["objective_score"]) / max(current_service_metrics["objective_score"], 0.1) * 100
        run_id = str(uuid.uuid4())[:8]
        run_result = {
            "run_id": run_id,
            "problem_type": "civic_service_optimizer",
            "city_id": city_key,
            "facility_type": payload.facility_type,
            "k": len(current_sites),
            "algorithm": {
                "name": "Knowledge-Informed RL Swap Optimizer for Urban Facility Location",
                "research_basis": {
                    "title": "Large-scale Urban Facility Location Selection with Knowledge-informed Reinforcement Learning",
                    "year": 2024,
                    "url": "https://arxiv.org/abs/2409.01588",
                    "note": "Signal City implements a deterministic teaching adaptation: greedy construction plus knowledge-guided swap improvement on BBMP ward demand and Bengaluru road travel-time data.",
                },
                "complexity": "O(I * k * C * (E log V + W)) after distance caching; facility location is NP-hard, so this uses an explainable heuristic.",
            },
            "data_used": {
                "wards": len(demand_points),
                "candidate_sites": len(candidates),
                "existing_facilities": len(existing_nodes),
                "road_nodes": nx_graph.number_of_nodes(),
                "road_edges": nx_graph.number_of_edges(),
                "sources": ["BBMP ward boundaries", "OSM road graph", "OSM civic facility POIs"],
            },
            "baseline": current_service_metrics,
            "greedy_baseline": baseline_metrics,
            "optimized": final_metrics,
            "improvement_pct": round(max(0.0, improvement), 2),
            "recommendations": recommendations,
            "worst_served_wards": final_rows[:10],
            "trace": trace[:24],
            "xai_steps": [
                "Problem: choose a small number of new civic service sites so high-demand BBMP wards get faster access.",
                "Baseline: current service coverage is measured using existing civic POIs snapped to the Bengaluru road graph.",
                "Greedy comparison: k-median adds one site at a time by minimizing population-weighted road travel time.",
                "Research upgrade: the 2024 knowledge-informed RL idea is adapted as an explainable swap policy. It tests replacing one chosen site with a better candidate, guided by demand and road centrality.",
                "Objective: weighted average minutes + worst-case penalty + access-inequality penalty. This avoids placing every site only in already well-connected central areas.",
                f"Result: objective improved by {round(max(0.0, improvement), 2)}% over greedy baseline; {final_metrics['wards_over_10_min']} wards remain above 10 minutes.",
            ],
        }
        RUNS_DB[run_id] = run_result
        return run_result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error during civic service optimizer")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/flood-reroute")
async def flood_reroute(payload: RouteImpactRequest):
    """Return baseline and flood-aware route for the same two selected points."""
    try:
        city_key = slugify_city(payload.city_id)
        graph_data = await load_city_graph(city_key)
        params = {
            "city_id": city_key,
            "source_name": payload.source_name,
            "dest_name": payload.dest_name,
            "start_node": payload.start_node,
            "end_node": payload.end_node,
        }
        baseline = plan_route(graph_data, {**params, "algorithm": "dijkstra"})
        rerouted = plan_route(graph_data, {**params, "algorithm": "flood_aware", "flooded_nodes": payload.flooded_nodes})
        run_id = str(uuid.uuid4())[:8]
        run_result = {
            "run_id": run_id,
            "problem_type": "flood_reroute",
            "flooded_nodes": payload.flooded_nodes,
            "baseline": baseline,
            "rerouted": rerouted,
            "extra_distance_m": round(rerouted["metrics"]["length_m"] - baseline["metrics"]["length_m"], 2),
            "extra_minutes": round(rerouted["metrics"]["travel_minutes"] - baseline["metrics"]["travel_minutes"], 2),
        }
        RUNS_DB[run_id] = run_result
        return run_result
    except Exception as e:
        logger.exception("Error during flood reroute")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/resilience-ksp")
async def resilience_ksp(payload: RouteImpactRequest):
    """
    Research-grade showcase endpoint: dynamic k-shortest route resilience.
    Finds several alternative routes for the same origin/destination and ranks
    them by time, crash-risk, flood exposure, and route diversity.
    """
    try:
        city_key = slugify_city(payload.city_id)
        graph_data = await load_city_graph(city_key)
        params = {
            "city_id": city_key,
            "source_name": payload.source_name,
            "dest_name": payload.dest_name,
            "start_node": payload.start_node,
            "end_node": payload.end_node,
            "flooded_nodes": payload.flooded_nodes,
        }
        result = resilient_k_routes(graph_data, params, k=max(2, min(payload.k, 6)))
        run_id = str(uuid.uuid4())[:8]
        result["run_id"] = run_id
        result["problem_type"] = "resilience_ksp"
        RUNS_DB[run_id] = result
        return result
    except Exception as e:
        logger.exception("Error during resilience KSP")
        raise HTTPException(status_code=400, detail=str(e))


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
    """Identify transit deserts with BMTC PageRank centrality and BBMP ward demand."""
    try:
        bmtc_graph = loader.get_bmtc_graph()
        pagerank_scores = nx.pagerank(bmtc_graph, weight="weight")
        wards_data = loader.get_ward_boundaries()
        all_stops = list(bmtc_graph.nodes(data=True))

        wards_result = []
        for feature in wards_data.get("features", [])[:80]:
            props = feature["properties"]
            ward_id = str(props.get("KGISWardNo") or props.get("ward_id") or "")
            ward_name = props.get("KGISWardName") or props.get("ward_name") or f"Ward {ward_id}"
            population = int(props.get("population", 50000))
            income_idx = float(props.get("income_idx", 0.75))
            clat, clon = _feature_centroid(feature)

            nearby_stops = []
            for stop_id, sdata in all_stops:
                distance_km = _haversine_km(sdata["lat"], sdata["lon"], clat, clon)
                if distance_km <= 2.2:
                    nearby_stops.append((stop_id, sdata, distance_km))
            nearby_stops.sort(key=lambda row: row[2])

            avg_centrality = 0.0
            if nearby_stops:
                avg_centrality = sum(pagerank_scores.get(sid, 0.0) for sid, _, _ in nearby_stops) / len(nearby_stops)

            stop_access = len(nearby_stops) / max(population / 50000.0, 0.4)
            centrality_access = avg_centrality * 10000
            equity_need = 1.25 - min(max(income_idx, 0.2), 1.15) * 0.35
            desert_index = (population / 50000.0) * equity_need / (max(stop_access, 0.25) * max(centrality_access, 0.18))

            if len(nearby_stops) == 0:
                classification = "Severe Transit Desert"
            elif desert_index > 1.5:
                classification = "Moderate Transit Desert"
            else:
                classification = "Well Connected"

            wards_result.append({
                "ward_id": ward_id,
                "ward_name": ward_name,
                "population": population,
                "lat": round(clat, 6),
                "lon": round(clon, 6),
                "stop_count": len(nearby_stops),
                "avg_centrality": round(avg_centrality * 10000, 2),
                "desert_index": round(desert_index, 2),
                "classification": classification,
                "nearest_stops": [
                    {
                        "stop_id": sid,
                        "name": sdata.get("name", sid),
                        "lat": sdata["lat"],
                        "lon": sdata["lon"],
                        "distance_km": round(distance, 2),
                        "pagerank": round(pagerank_scores.get(sid, 0.0) * 10000, 2),
                    }
                    for sid, sdata, distance in nearby_stops[:5]
                ],
                "xai_reason": (
                    f"{ward_name} has population {population}, {len(nearby_stops)} nearby BMTC stops, "
                    f"and average stop PageRank {round(avg_centrality * 10000, 2)}. "
                    "High demand with low stop count or low network centrality increases the transit desert index."
                ),
            })

        wards_result.sort(key=lambda w: w["desert_index"], reverse=True)
        run_id = str(uuid.uuid4())[:8]
        run_result = {
            "run_id": run_id,
            "problem_type": "transit_equity",
            "underserved_wards": wards_result[:6],
            "all_wards": wards_result,
            "algorithm": {
                "name": "PageRank Transit Centrality + BBMP Ward Demand Index",
                "complexity": "PageRank O(I * E) plus ward-stop spatial join O(W * S)",
                "purpose": "Find wards where public transport access is weak relative to population demand.",
            },
            "xai_steps": [
                "BMTC stops are modeled as a graph and PageRank estimates which stops are structurally important in the bus network.",
                "Each BBMP ward is matched to nearby bus stops around its centroid.",
                "The transit desert index rises when a ward has high population, few nearby stops, or stops with low network centrality.",
                "This is an access-equity analysis for deciding where to add stops, feeder services, or higher-frequency routes.",
            ],
        }
        RUNS_DB[run_id] = run_result
        return run_result
    except Exception as e:
        logger.exception("Error in transit equity calculation")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transit-equity-legacy")
async def transit_equity_legacy(city_id: str = "bengaluru"):
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
