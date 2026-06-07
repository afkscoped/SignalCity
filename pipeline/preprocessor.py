"""
pipeline/preprocessor.py — Converts OSMnx MultiDiGraph to game-ready JSON.
Handles coordinate normalization, edge dedup, and connected component extraction.
"""

import time
import math


def process_graph(G, city_id: str = "unknown", city_name: str = "Unknown") -> dict:
    """
    Takes a NetworkX MultiDiGraph from OSMnx (or a plain dict for synthetic graphs).
    Returns a dict ready for WeightedGraph.from_json() and JSON serialization.

    Processing steps:
    1. Extract nodes with lat/lon
    2. Normalize coordinates to [-100, 100] game space
    3. Extract and deduplicate edges
    4. Keep only largest connected component
    5. Assign sequential integer IDs (0..N-1)
    """
    import networkx as nx

    # Handle case where G is already a dict (synthetic graph)
    if isinstance(G, dict):
        return G

    # Step 1: Extract nodes
    raw_nodes = {}
    for node_id, data in G.nodes(data=True):
        raw_nodes[node_id] = {
            "osm_id": node_id,
            "lat": data.get("y", 0.0),
            "lon": data.get("x", 0.0),
            "x_m": data.get("x", 0.0),
            "y_m": data.get("y", 0.0),
        }

    # Try to project to meters for better spatial layout
    try:
        import osmnx as ox
        G_proj = ox.project_graph(G)
        for node_id, data in G_proj.nodes(data=True):
            if node_id in raw_nodes:
                raw_nodes[node_id]["x_m"] = data.get("x", raw_nodes[node_id]["x_m"])
                raw_nodes[node_id]["y_m"] = data.get("y", raw_nodes[node_id]["y_m"])
    except Exception:
        # If projection fails, use lat/lon directly (scaled)
        for node_id in raw_nodes:
            raw_nodes[node_id]["x_m"] = raw_nodes[node_id]["lon"] * 111320 * math.cos(
                math.radians(raw_nodes[node_id]["lat"])
            )
            raw_nodes[node_id]["y_m"] = raw_nodes[node_id]["lat"] * 110540

    # Step 2: Normalize coordinates to [-100, 100]
    if raw_nodes:
        xs = [n["x_m"] for n in raw_nodes.values()]
        ys = [n["y_m"] for n in raw_nodes.values()]
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        max_extent = max(
            max(abs(x - cx) for x in xs),
            max(abs(y - cy) for y in ys),
            1.0,
        )
        scale = 100.0 / max_extent
        for n in raw_nodes.values():
            n["x_norm"] = (n["x_m"] - cx) * scale
            n["y_norm"] = (n["y_m"] - cy) * scale

    # Step 3: Extract edges, deduplicate parallel edges
    raw_edges = {}
    for u, v, key, data in G.edges(keys=True, data=True):
        if u not in raw_nodes or v not in raw_nodes:
            continue
        edge_key = (min(u, v), max(u, v))
        weight = data.get("travel_time", data.get("length", 100.0) / 30.0 * 3.6)
        if isinstance(weight, (list, tuple)):
            weight = weight[0] if weight else 5.0
        try:
            weight = float(weight)
        except (ValueError, TypeError):
            weight = 5.0
        if weight <= 0:
            weight = 1.0

        lanes = data.get("lanes", 1)
        if isinstance(lanes, (list, tuple)):
            lanes = lanes[0] if lanes else 1
        try:
            lanes = int(lanes)
        except (ValueError, TypeError):
            lanes = 1
        capacity = lanes * 800

        length_m = data.get("length", 100.0)
        if isinstance(length_m, (list, tuple)):
            length_m = length_m[0] if length_m else 100.0
        try:
            length_m = float(length_m)
        except (ValueError, TypeError):
            length_m = 100.0

        speed_kph = data.get("speed_kph", 30.0)
        if isinstance(speed_kph, (list, tuple)):
            speed_kph = speed_kph[0] if speed_kph else 30.0
        try:
            speed_kph = float(speed_kph)
        except (ValueError, TypeError):
            speed_kph = 30.0

        if edge_key not in raw_edges or weight < raw_edges[edge_key]["weight"]:
            raw_edges[edge_key] = {
                "u_osm": u,
                "v_osm": v,
                "weight": round(weight, 3),
                "capacity": capacity,
                "length_m": round(length_m, 2),
                "speed_kph": round(speed_kph, 1),
            }

    # Step 4: Largest weakly connected component
    simple_G = nx.Graph()
    for (u, v), edata in raw_edges.items():
        simple_G.add_edge(u, v)
    if len(simple_G) > 0:
        largest_cc = max(nx.connected_components(simple_G), key=len)
    else:
        largest_cc = set(raw_nodes.keys())

    # Step 5: Assign sequential IDs
    osm_to_id = {}
    nodes_out = []
    node_idx = 0
    for osm_id in sorted(largest_cc):
        if osm_id not in raw_nodes:
            continue
        n = raw_nodes[osm_id]
        osm_to_id[osm_id] = node_idx
        pop_weight = 1.0 + abs(n["x_norm"]) * 0.01 + abs(n["y_norm"]) * 0.01
        nodes_out.append({
            "id": node_idx,
            "x": round(n["x_norm"], 3),
            "y": round(n["y_norm"], 3),
            "lat": round(n["lat"], 6),
            "lon": round(n["lon"], 6),
            "pop_weight": round(pop_weight, 2),
        })
        node_idx += 1

    edges_out = []
    for (u_osm, v_osm), edata in raw_edges.items():
        if u_osm in osm_to_id and v_osm in osm_to_id:
            edges_out.append({
                "u": osm_to_id[u_osm],
                "v": osm_to_id[v_osm],
                "weight": edata["weight"],
                "capacity": edata["capacity"],
                "length_m": edata["length_m"],
                "speed_kph": edata["speed_kph"],
            })

    # Compute bbox
    if nodes_out:
        min_x = min(n["x"] for n in nodes_out)
        max_x = max(n["x"] for n in nodes_out)
        min_y = min(n["y"] for n in nodes_out)
        max_y = max(n["y"] for n in nodes_out)
        clat = sum(n["lat"] for n in nodes_out) / len(nodes_out)
        clon = sum(n["lon"] for n in nodes_out) / len(nodes_out)
    else:
        min_x = max_x = min_y = max_y = 0
        clat = clon = 0

    return {
        "city_id": city_id,
        "city_name": city_name,
        "node_count": len(nodes_out),
        "edge_count": len(edges_out),
        "bbox": {"min_x": min_x, "max_x": max_x, "min_y": min_y, "max_y": max_y},
        "centroid": {"lat": round(clat, 6), "lon": round(clon, 6)},
        "nodes": nodes_out,
        "edges": edges_out,
        "metadata": {
            "source": "osmnx",
            "fetched_at": time.time(),
        },
    }
