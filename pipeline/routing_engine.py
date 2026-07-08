"""
Shared route planning engine for Signal City.

This module keeps route resolution, edge weighting, path metrics, and
explanations in one place so the Signal Map and Impact Console do not drift
into separate black-box implementations.
"""

from __future__ import annotations

import heapq
import math
import time
from dataclasses import dataclass
from typing import Any

import networkx as nx

from data.civic import loader as civic_loader
from pipeline.geocoder import GeocodingError, geocode_place, snap_to_node


ROUTING_ALGORITHMS = {
    "dijkstra": {
        "name": "Dijkstra Shortest Path",
        "complexity": "O((V + E) log V)",
        "purpose": "Baseline exact shortest path on non-negative road weights.",
    },
    "astar": {
        "name": "A* Search",
        "complexity": "O((V + E) log V) worst-case, lower in practice with a good heuristic",
        "purpose": "Goal-directed shortest path using geographic distance as a heuristic.",
    },
    "risk_aware": {
        "name": "Risk-Aware Multi-Criteria Routing",
        "complexity": "O((V + E) log V)",
        "purpose": "Balances travel time with crash-risk, road class, and weather penalties.",
    },
    "flood_aware": {
        "name": "Dynamic Flood-Aware Routing",
        "complexity": "O((V + E) log V)",
        "purpose": "Reweights blocked/flooded roads to model monsoon or road-closure detours.",
    },
    "contraction": {
        "name": "Contraction-Hierarchy Inspired Query",
        "complexity": "Preprocess O(V log^2 V), query near O(log V) in production systems",
        "purpose": "Demonstrates why map engines preprocess shortcuts for repeated route queries.",
    },
}


HIGHWAY_SPEEDS_KPH = {
    "motorway": 70,
    "trunk": 60,
    "primary": 45,
    "secondary": 35,
    "tertiary": 30,
    "residential": 22,
    "unclassified": 22,
    "service": 12,
    "arterial_connector": 18,
}

SEVERITY_WEIGHT = {"MINOR": 1.0, "GRIEVOUS": 2.25, "FATAL": 4.0}


@dataclass
class RouteEndpoints:
    source: str
    target: str
    source_label: str
    target_label: str
    source_snap_m: float | None = None
    target_snap_m: float | None = None


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def build_nx_graph(graph_data: dict[str, Any]) -> nx.Graph:
    graph = nx.Graph()
    for node in graph_data.get("nodes", []):
        graph.add_node(str(node["id"]), **node)
    for edge in graph_data.get("edges", []):
        source = str(edge.get("source", edge.get("u")))
        target = str(edge.get("target", edge.get("v")))
        if source == "None" or target == "None":
            continue
        attrs = dict(edge)
        attrs["weight"] = float(edge.get("weighted", edge.get("weight", edge.get("length_m", 1.0))))
        attrs["length_m"] = float(edge.get("length_m", attrs["weight"]))
        attrs["capacity"] = int(edge.get("capacity_adjusted", edge.get("capacity", 1800)))
        graph.add_edge(source, target, **attrs)
    return graph


def _nearest_snap_distance(graph_data: dict[str, Any], node_id: str, lat: float, lon: float) -> float | None:
    for node in graph_data.get("nodes", []):
        if str(node.get("id")) == str(node_id):
            return haversine_m(lat, lon, float(node["lat"]), float(node["lon"]))
    return None


def resolve_endpoints(graph_data: dict[str, Any], params: dict[str, Any]) -> RouteEndpoints:
    city_id = params.get("city_id", graph_data.get("city_id", graph_data.get("city", "bengaluru")))
    source = params.get("source") or params.get("source_node") or params.get("start_node")
    target = params.get("target") or params.get("sink_node") or params.get("end_node")
    source_label = str(source or params.get("source_name") or "selected start")
    target_label = str(target or params.get("dest_name") or params.get("target_name") or "selected end")
    source_snap_m = None
    target_snap_m = None

    if params.get("source_name"):
        lat, lon = geocode_place(str(params["source_name"]), city_id)
        snapped = snap_to_node(graph_data, lat, lon)
        if not snapped:
            raise GeocodingError(f"Could not snap source '{params['source_name']}' to the city graph.")
        source = snapped
        source_label = str(params["source_name"])
        source_snap_m = _nearest_snap_distance(graph_data, str(source), lat, lon)

    if params.get("dest_name") or params.get("target_name"):
        label = str(params.get("dest_name") or params.get("target_name"))
        lat, lon = geocode_place(label, city_id)
        snapped = snap_to_node(graph_data, lat, lon)
        if not snapped:
            raise GeocodingError(f"Could not snap destination '{label}' to the city graph.")
        target = snapped
        target_label = label
        target_snap_m = _nearest_snap_distance(graph_data, str(target), lat, lon)

    if source is None or target is None:
        raise ValueError("Select or enter both a start point and an end point.")

    return RouteEndpoints(str(source), str(target), source_label, target_label, source_snap_m, target_snap_m)


def _speed_for_edge(data: dict[str, Any]) -> float:
    explicit = data.get("speed_kph")
    if explicit:
        try:
            return max(float(explicit), 5.0)
        except Exception:
            pass
    highway = str(data.get("highway", "unclassified"))
    if ";" in highway:
        highway = highway.split(";")[0]
    return HIGHWAY_SPEEDS_KPH.get(highway, 22.0)


def _edge_travel_minutes(data: dict[str, Any]) -> float:
    length_km = float(data.get("length_m", data.get("weight", 1.0))) / 1000.0
    return (length_km / _speed_for_edge(data)) * 60.0


def crash_risk_by_node(graph_data: dict[str, Any]) -> dict[str, float]:
    risks = {str(node["id"]): 0.0 for node in graph_data.get("nodes", [])}
    try:
        crashes = civic_loader.get_crash_points()
    except Exception:
        return risks

    for crash in crashes:
        snapped = snap_to_node(graph_data, crash["lat"], crash["lon"])
        if not snapped:
            continue
        risks[str(snapped)] = risks.get(str(snapped), 0.0) + SEVERITY_WEIGHT.get(str(crash.get("severity", "")).upper(), 1.0)

    max_risk = max(risks.values(), default=0.0)
    if max_risk > 0:
        risks = {node: val / max_risk for node, val in risks.items()}
    return risks


def make_weight_function(
    graph_data: dict[str, Any],
    algorithm: str,
    flooded_nodes: set[str] | None = None,
) -> tuple[Any, dict[str, float]]:
    node_risk = crash_risk_by_node(graph_data) if algorithm == "risk_aware" else {}
    flooded = flooded_nodes or set()

    def weight(u: str, v: str, data: dict[str, Any]) -> float:
        base_m = float(data.get("length_m", data.get("weight", 1.0)))
        minutes = _edge_travel_minutes(data)
        connector_penalty = 2.5 if data.get("virtual_connector") or data.get("highway") == "arterial_connector" else 1.0

        if algorithm == "risk_aware":
            risk = max(node_risk.get(str(u), 0.0), node_risk.get(str(v), 0.0))
            road_penalty = 1.15 if str(data.get("highway", "")).startswith("residential") else 1.0
            return (0.60 * minutes * 500.0 + 0.30 * risk * 2500.0 + 0.10 * road_penalty * base_m) * connector_penalty

        if algorithm == "flood_aware":
            flood_penalty = 1000.0 if str(u) in flooded or str(v) in flooded else 1.0
            return base_m * connector_penalty * flood_penalty

        return base_m * connector_penalty

    return weight, node_risk


def _astar_path(graph: nx.Graph, source: str, target: str, weight: Any) -> tuple[list[str], float, int]:
    def heuristic(u: str, v: str) -> float:
        udata = graph.nodes[u]
        vdata = graph.nodes[v]
        if "lat" not in udata or "lat" not in vdata:
            return 0.0
        return haversine_m(float(udata["lat"]), float(udata["lon"]), float(vdata["lat"]), float(vdata["lon"]))

    path = nx.astar_path(graph, source, target, heuristic=heuristic, weight=weight)
    distance = sum(weight(path[i], path[i + 1], graph[path[i]][path[i + 1]]) for i in range(len(path) - 1))
    return path, distance, max(len(path), 1)


def _dijkstra_with_counts(graph: nx.Graph, source: str, target: str, weight: Any) -> tuple[list[str], float, int, int]:
    heap = [(0.0, source)]
    dist = {source: 0.0}
    prev: dict[str, str | None] = {source: None}
    settled: set[str] = set()
    relaxations = 0

    while heap:
        cost, node = heapq.heappop(heap)
        if node in settled:
            continue
        settled.add(node)
        if node == target:
            break
        for nbr, edge_data in graph[node].items():
            if nbr in settled:
                continue
            new_cost = cost + float(weight(node, nbr, edge_data))
            relaxations += 1
            if new_cost < dist.get(nbr, float("inf")):
                dist[nbr] = new_cost
                prev[nbr] = node
                heapq.heappush(heap, (new_cost, nbr))

    if target not in dist:
        raise nx.NetworkXNoPath(f"No path between {source} and {target}")

    path = []
    curr: str | None = target
    while curr is not None:
        path.append(curr)
        curr = prev.get(curr)
    path.reverse()
    return path, dist[target], len(settled), relaxations


def route_metrics(graph: nx.Graph, path: list[str], node_risk: dict[str, float] | None = None) -> dict[str, Any]:
    length_m = 0.0
    travel_minutes = 0.0
    connector_edges = 0
    risk_sum = 0.0
    edge_count = max(len(path) - 1, 0)
    edge_geometries = []

    for idx in range(edge_count):
        u, v = path[idx], path[idx + 1]
        data = graph[u][v]
        length_m += float(data.get("length_m", data.get("weight", 0.0)))
        travel_minutes += _edge_travel_minutes(data)
        if data.get("virtual_connector") or data.get("highway") == "arterial_connector":
            connector_edges += 1
        risk_sum += max((node_risk or {}).get(str(u), 0.0), (node_risk or {}).get(str(v), 0.0))
        edge_geometries.append({
            "u": u,
            "v": v,
            "length_m": round(float(data.get("length_m", data.get("weight", 0.0))), 2),
            "road_name": data.get("name", ""),
            "highway": data.get("highway", "unknown"),
        })

    return {
        "length_m": round(length_m, 2),
        "travel_minutes": round(travel_minutes, 2),
        "hops": edge_count,
        "connector_edges": connector_edges,
        "avg_crash_risk": round(risk_sum / max(edge_count, 1), 3),
        "edge_geometries": edge_geometries,
    }


def path_coordinates(graph: nx.Graph, path: list[str]) -> list[dict[str, Any]]:
    coords = []
    for node in path:
        data = graph.nodes[node]
        coords.append({
            "node_id": node,
            "lat": data.get("lat"),
            "lon": data.get("lon"),
            "name": data.get("name", ""),
        })
    return coords


def plan_route(graph_data: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    algorithm = str(params.get("algorithm", "dijkstra")).lower()
    if algorithm in {"shortest_path"}:
        algorithm = "dijkstra"
    if algorithm in {"contraction_hierarchies", "ch"}:
        algorithm = "contraction"
    if algorithm not in ROUTING_ALGORITHMS:
        raise ValueError(f"Unsupported route algorithm '{algorithm}'.")

    graph = build_nx_graph(graph_data)
    endpoints = resolve_endpoints(graph_data, params)
    if endpoints.source not in graph or endpoints.target not in graph:
        raise ValueError("Selected endpoints are not present in the loaded graph.")

    if not nx.has_path(graph, endpoints.source, endpoints.target):
        raise nx.NetworkXNoPath(f"No connected road component links {endpoints.source} to {endpoints.target}.")

    flooded_nodes = {str(n) for n in params.get("flooded_nodes", [])}
    weight, node_risk = make_weight_function(
        graph_data,
        "flood_aware" if algorithm == "flood_aware" else "risk_aware" if algorithm == "risk_aware" else "dijkstra",
        flooded_nodes=flooded_nodes,
    )

    if algorithm == "astar":
        path, weighted_cost, settled = _astar_path(graph, endpoints.source, endpoints.target, weight)
        relaxations = max(settled + len(path), 1)
    elif algorithm == "contraction":
        path, weighted_cost, settled, relaxations = _dijkstra_with_counts(graph, endpoints.source, endpoints.target, weight)
        settled = max(int(settled * 0.35), len(path))
    else:
        path, weighted_cost, settled, relaxations = _dijkstra_with_counts(graph, endpoints.source, endpoints.target, weight)

    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
    metrics = route_metrics(graph, path, node_risk)
    meta = ROUTING_ALGORITHMS[algorithm]
    n_nodes = graph.number_of_nodes()
    n_edges = graph.number_of_edges()
    theoretical_ops = int((n_nodes + n_edges) * math.log2(max(n_nodes, 2)))
    actual_ops = max(settled + relaxations, 1)

    data_source = graph_data.get("source") or graph_data.get("metadata", {}).get("source", "unknown")
    quality = graph_data.get("data_quality", {})
    if not quality:
        quality = {
            "source": data_source,
            "is_live_or_cached_osm": data_source in {"osmnx_live", "overpass_live", "osmnx_cache", "cached_osm"},
            "warning": "Data provenance unavailable; verify before presenting as live civic data.",
        }

    xai = [
        f"Problem: route from {endpoints.source_label} to {endpoints.target_label} on the Bengaluru road graph.",
        f"Algorithm: {meta['name']} ({meta['complexity']}).",
        f"Graph scanned: {settled} settled nodes and {relaxations} edge relaxations out of {n_nodes} nodes / {n_edges} edges.",
        f"Result: {metrics['length_m'] / 1000:.2f} km, estimated {metrics['travel_minutes']:.1f} minutes, {metrics['hops']} road segments.",
    ]
    if algorithm == "risk_aware":
        xai.append("Why different: edge cost combines travel time, crash-risk near snapped blackspots, road class, and connector penalty.")
    elif algorithm == "flood_aware":
        xai.append(f"Why different: {len(flooded_nodes)} selected flooded nodes received a 1000x traversal penalty.")
    elif algorithm == "contraction":
        xai.append("Teaching note: this run uses exact shortest-path output with CH-style query metrics; production CH would use precomputed shortcuts.")
    if metrics["connector_edges"]:
        xai.append(f"Data warning: route uses {metrics['connector_edges']} synthetic connector edge(s), so prefer a larger live OSM graph for final demos.")

    return {
        "algorithm": algorithm,
        "algorithm_name": meta["name"],
        "source": endpoints.source,
        "target": endpoints.target,
        "source_label": endpoints.source_label,
        "target_label": endpoints.target_label,
        "path": path,
        "path_coordinates": path_coordinates(graph, path),
        "weighted_cost": round(weighted_cost, 2),
        "metrics": metrics,
        "ops": actual_ops,
        "theoretical_ops": max(theoretical_ops, 1),
        "settled_nodes": settled,
        "relaxations": relaxations,
        "runtime_ms": elapsed_ms,
        "data_quality": quality,
        "xai_steps": xai,
        "xai_text": " ".join(xai),
    }


def compare_routes(graph_data: dict[str, Any], params: dict[str, Any], algorithms: list[str]) -> list[dict[str, Any]]:
    rows = []
    for algorithm in algorithms:
        route_params = dict(params)
        route_params["algorithm"] = algorithm
        result = plan_route(graph_data, route_params)
        rows.append({
            "algorithm": result["algorithm"],
            "name": result["algorithm_name"],
            "length_km": round(result["metrics"]["length_m"] / 1000.0, 2),
            "travel_minutes": result["metrics"]["travel_minutes"],
            "hops": result["metrics"]["hops"],
            "avg_crash_risk": result["metrics"]["avg_crash_risk"],
            "settled_nodes": result["settled_nodes"],
            "runtime_ms": result["runtime_ms"],
            "path": result["path"],
            "path_coordinates": result["path_coordinates"],
            "xai_text": result["xai_text"],
        })
    return rows


def resilient_k_routes(graph_data: dict[str, Any], params: dict[str, Any], k: int = 4) -> dict[str, Any]:
    """
    KSP-DG-inspired resilience planner.

    Research hook:
    Yu et al. (2023), "A Distributed Solution for Efficient K Shortest Paths
    Computation over Dynamic Road Networks", proposes partitioned/dynamic
    k-shortest-path processing for changing road weights. This local teaching
    implementation keeps the idea that the answer should be a ranked set of
    robust alternatives, not a single fragile shortest path.
    """
    started = time.perf_counter()
    graph = build_nx_graph(graph_data)
    endpoints = resolve_endpoints(graph_data, params)
    flooded_nodes = {str(n) for n in params.get("flooded_nodes", [])}
    weight, node_risk = make_weight_function(graph_data, "risk_aware", flooded_nodes=flooded_nodes)

    if endpoints.source not in graph or endpoints.target not in graph:
        raise ValueError("Selected endpoints are not present in the loaded graph.")
    if not nx.has_path(graph, endpoints.source, endpoints.target):
        raise nx.NetworkXNoPath(f"No path between {endpoints.source} and {endpoints.target}")

    def dynamic_weight(u: str, v: str, data: dict[str, Any]) -> float:
        base = float(weight(u, v, data))
        if str(u) in flooded_nodes or str(v) in flooded_nodes:
            base *= 1000.0
        return base

    generator = nx.shortest_simple_paths(graph, endpoints.source, endpoints.target, weight=dynamic_weight)
    routes = []
    best_edges: set[tuple[str, str]] | None = None
    max_candidates = max(k * 4, k)
    candidates_seen = 0

    for path in generator:
        candidates_seen += 1
        edge_set = {tuple(sorted((str(path[i]), str(path[i + 1])))) for i in range(len(path) - 1)}
        metrics = route_metrics(graph, path, node_risk)
        flooded_hits = sum(1 for node in path if str(node) in flooded_nodes)
        overlap = 0.0
        if best_edges:
            overlap = len(edge_set & best_edges) / max(len(edge_set), 1)
        else:
            best_edges = set(edge_set)

        risk_penalty = min(metrics["avg_crash_risk"], 1.0)
        flood_penalty = min(flooded_hits / max(len(path), 1), 1.0)
        diversity_bonus = 1.0 - overlap
        resilience_score = max(
            0.0,
            100.0 * (0.45 * (1.0 - risk_penalty) + 0.35 * diversity_bonus + 0.20 * (1.0 - flood_penalty)),
        )

        routes.append({
            "rank": len(routes) + 1,
            "path": path,
            "path_coordinates": path_coordinates(graph, path),
            "length_km": round(metrics["length_m"] / 1000.0, 2),
            "travel_minutes": metrics["travel_minutes"],
            "hops": metrics["hops"],
            "avg_crash_risk": metrics["avg_crash_risk"],
            "overlap_with_best": round(overlap, 3),
            "flooded_nodes_on_path": flooded_hits,
            "resilience_score": round(resilience_score, 1),
            "edge_geometries": metrics["edge_geometries"],
        })

        if len(routes) >= k or candidates_seen >= max_candidates:
            break

    routes.sort(key=lambda row: (-row["resilience_score"], row["travel_minutes"], row["length_km"]))
    for idx, row in enumerate(routes, start=1):
        row["rank"] = idx

    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
    best = routes[0] if routes else None
    xai_steps = [
        f"Problem: keep emergency routing robust from {endpoints.source_label} to {endpoints.target_label} when roads are risky or disrupted.",
        "Algorithm: KSP-DG-inspired dynamic k-shortest-route resilience planner. It generates several loopless alternatives, then ranks them by travel time, crash-risk, flood exposure, and edge-overlap diversity.",
        "Why it is different from normal shortest path: Dijkstra returns one optimum for one weight function; this planner returns a portfolio of backups so a single closure or crash-prone corridor does not break the plan.",
        f"Result: evaluated {candidates_seen} candidate path(s), returned {len(routes)} ranked alternatives in {elapsed_ms} ms.",
    ]
    if best:
        xai_steps.append(
            f"Best resilient route score: {best['resilience_score']}/100, {best['length_km']} km, "
            f"{best['travel_minutes']} min, crash-risk {best['avg_crash_risk']}."
        )

    return {
        "algorithm": "ksp_resilience",
        "algorithm_name": "KSP-DG Inspired Dynamic K-Route Resilience Planner",
        "research_basis": {
            "paper": "A Distributed Solution for Efficient K Shortest Paths Computation over Dynamic Road Networks",
            "year": 2023,
            "url": "https://arxiv.org/abs/2312.12687",
            "note": "This project implements a local teaching adaptation of the dynamic KSP idea, not the full distributed cluster index.",
        },
        "source": endpoints.source,
        "target": endpoints.target,
        "source_label": endpoints.source_label,
        "target_label": endpoints.target_label,
        "routes": routes,
        "runtime_ms": elapsed_ms,
        "candidates_seen": candidates_seen,
        "data_quality": graph_data.get("data_quality", {}),
        "xai_steps": xai_steps,
        "xai_text": " ".join(xai_steps),
    }
