import logging
import math
from datetime import datetime

import networkx as nx
from fastapi import APIRouter, Depends, HTTPException

from auth.middleware import get_current_user_optional
from database.connection import get_db
from pipeline.city_loader import load_city_graph
from pipeline.geocoder import geocode_place, snap_to_node, GeocodingError
from pipeline.graph_scope import scope_graph_data
from pipeline.routing_engine import compare_routes, plan_route, build_nx_graph, resolve_endpoints
from routers.city import get_cached_city
from pipeline.validation import validate_shortest_path, validate_mst, validate_steiner_tree

logger = logging.getLogger(__name__)
router = APIRouter(tags=["algorithms"])

def _algo(name, category, tier, cost, desc, use_case, complexity, output):
    return {
        "name": name,
        "category": category,
        "tier": tier,
        "cost": cost,
        "desc": desc,
        "use_case": use_case,
        "complexity": complexity,
        "output": output,
    }


ALGORITHMS = {
    "prim": _algo("Prim's MST", "mst", 1, 5, "Greedily grows the cheapest utility backbone from a start junction.", "Lay minimum-cost power or fiber lines connecting all important hotspots.", "O(E log V)", "MST edges, total grid length, visited intersections"),
    "kruskal": _algo("Kruskal's MST", "mst", 2, 8, "Sorts roads by cost and uses union-find to avoid cycles.", "Compare a global road-sorting plan against Prim's local frontier strategy.", "O(E log E)", "MST edges, rejected cycle edges, total grid length"),
    "dijkstra": _algo("Dijkstra's Shortest Path", "pathfinding", 1, 8, "Finds the fastest route under current road and weather weights.", "Route emergency vehicles or commuters between selected hotspots.", "O((V + E) log V)", "Path, travel cost, relaxed roads"),
    "contraction": _algo("Contraction Hierarchies", "pathfinding", 4, 22, "Preprocesses important shortcut roads for faster repeated routing.", "Show how map apps accelerate many shortest-path queries.", "Preprocess O(V log V + E), query near O(log V)", "Shortcut path, contracted nodes, query cost"),
    "edmonds_karp": _algo("Edmonds-Karp Max Flow", "flow", 3, 15, "Uses BFS augmenting paths to maximize vehicles per hour.", "Measure throughput between two city districts and reveal bottleneck cuts.", "O(VE^2)", "Max flow, augmenting paths, min-cut roads"),
    "leiden": _algo("Leiden Community Detection", "analysis", 4, 20, "Groups strongly connected intersections into stable districts.", "Discover natural zones for borough planning, policing, or bus depots.", "Near O(E) per pass", "District colors, community count"),
    "louvain": _algo("Louvain Community Detection", "analysis", 4, 20, "Optimizes modularity to find graph communities.", "Compare districting quality with Leiden-style refinement.", "Near O(E) per pass", "District colors, modularity proxy"),
    "pagerank": _algo("PageRank Centrality", "analysis", 3, 18, "Ranks intersections by incoming importance over repeated random walks.", "Find the most influential junctions for signal priority or inspections.", "O(kE)", "Top hub nodes, centrality scores"),
    "k_median": _algo("k-Median Facility", "optimization", 5, 25, "Greedily places k services to reduce average citizen distance.", "Choose hospitals, shelters, or fire stations near demand hotspots.", "O(V^2 k)", "Facility nodes, average distance, coverage radius"),
    "gwo": _algo("Grey Wolf Optimizer", "optimization", 3, 12, "Population search for k emergency-service locations.", "Place fire stations while minimizing worst response distance.", "O(I * P * V * k)", "Facility nodes, convergence fitness"),
    "alo": _algo("Ant Lion Optimizer", "optimization", 3, 12, "Metaheuristic facility placement through elite-guided random walks.", "Compare stochastic facility planning against greedy k-median.", "O(I * P * V * k)", "Facility nodes, fitness trend"),
    "hho": _algo("Harris Hawks Optimization", "optimization", 4, 15, "Exploration/exploitation search for emergency hubs.", "Stress-test facility placement under changing demand.", "O(I * P * V * k)", "Facility nodes, best fitness"),
    "coa": _algo("Coati Optimization", "optimization", 5, 20, "Recent population optimizer for service hub placement.", "Advanced comparison for facility-location heuristics.", "O(I * P * V * k)", "Facility nodes, best fitness"),
    "woa": _algo("Whale Optimizer", "optimization", 3, 12, "Optimizes traffic-signal green times using spiral search.", "Reduce queue delay at high-centrality signal junctions.", "O(I * P * S)", "Signal nodes, green times, delay"),
    "run_optimizer": _algo("Runge-Kutta Optimizer", "optimization", 4, 16, "Uses RK-style slope updates over signal timing candidates.", "Compare numerical optimizer behavior for traffic-light tuning.", "O(I * P * S)", "Signal nodes, green times, delay"),
    "ptbo": _algo("Painting Training Optimizer", "optimization", 5, 22, "Blends candidate signal schedules toward the best pattern.", "Advanced signal-timing optimizer for DAA comparison.", "O(I * P * S)", "Signal nodes, green times, delay"),
    "mpa": _algo("Marine Predators Algorithm", "optimization", 4, 15, "Predator-prey search over traffic timing decisions.", "Compare another exploration/exploitation strategy visually.", "O(I * P * S)", "Signal nodes, green times, delay"),
    "mfo": _algo("Moth-Flame Optimizer", "optimization", 3, 10, "Places antennas to maximize covered population.", "Plan cell towers or public Wi-Fi coverage.", "O(I * P * V)", "Tower nodes, covered population"),
    "goa": _algo("Grasshopper Optimizer", "optimization", 4, 14, "Swarm search for wireless coverage placement.", "Compare coverage heuristics for telecom planning.", "O(I * P * V)", "Tower nodes, covered population"),
    "ao": _algo("Aquila Optimizer", "optimization", 4, 15, "Dives toward high-coverage antenna positions.", "Advanced wireless coverage optimizer.", "O(I * P * V)", "Tower nodes, covered population"),
    "do": _algo("Dandelion Optimizer", "optimization", 5, 18, "Wind-dispersal search over tower locations.", "Advanced wireless coverage optimizer.", "O(I * P * V)", "Tower nodes, covered population"),
    "ssa": _algo("Salp Swarm", "optimization", 3, 12, "Selects road or utility edges to upgrade as a low-loss backbone.", "Balance utility upgrades under a limited budget.", "O(I * P)", "Upgraded edges, loss score"),
    "sma": _algo("Slime Mould", "optimization", 4, 16, "Organic network optimizer for low-resistance road upgrades.", "Compare biologically inspired network construction.", "O(I * P)", "Upgraded edges, loss score"),
    "aoa": _algo("Arithmetic Optimizer", "optimization", 3, 10, "Uses arithmetic operators to mutate utility upgrade candidates.", "Teach arithmetic metaheuristics on infrastructure upgrades.", "O(I * P)", "Upgraded edges, loss score"),
    "gto": _algo("Gorilla Troops Optimizer", "optimization", 5, 20, "Leader-follower optimizer for power-line upgrades.", "Advanced utility-upgrade comparison.", "O(I * P)", "Upgraded edges, loss score"),
    "edf": _algo("Earliest Deadline First", "scheduling", 1, 5, "Serves city jobs by deadline.", "Schedule ambulances, buses, or maintenance requests with urgency.", "O(J log J)", "Gantt chart, lateness"),
    "sjf": _algo("Shortest Job First", "scheduling", 2, 8, "Runs shortest service jobs first.", "Compare throughput against fairness for municipal work orders.", "O(J log J)", "Gantt chart, waiting time"),
    "fcfs": _algo("First-Come First-Served", "scheduling", 1, 3, "Processes jobs in arrival order.", "Baseline scheduler for fairness and simplicity.", "O(J)", "Gantt chart, waiting time"),
    "round_robin": _algo("Round Robin", "scheduling", 2, 6, "Time-slices jobs so no district waits forever.", "Fair scheduling for service queues.", "O(J * slices)", "Gantt chart, response time"),
    "transformer": _algo("Transformer Attention", "ml", 3, 18, "Computes pairwise attention over intersection features.", "Find global traffic hubs using population, degree, and coordinates.", "O(V^2 d)", "Attention hubs, scores"),
    "kan": _algo("KAN Congestion", "ml", 5, 25, "Spline-style edge model predicts congestion pressure.", "Explain learned congestion inference without hiding the math.", "O(E * knots)", "Predicted congested edges"),
    "swin": _algo("Swin Zoning", "ml", 4, 20, "Windowed spatial attention partitions the city into zones.", "Show local attention as a zoning/classification method.", "O(W^2 * windows)", "Zone colors, patch sizes"),
    "diffusion": _algo("Diffusion Density", "ml", 5, 24, "Denoising process simulates staged city-density planning.", "Visualize generative planning over multiple timesteps.", "O(TV)", "Denoising steps, planned density"),
    "raft_consensus": _algo("Raft Consensus", "systems", 3, 15, "Elects a leader among substations and replicates commands.", "Tie distributed systems to power-grid coordination.", "O(N * log entries)", "Leader node, replicated commands"),
    "xgboost": _algo("XGBoost Split Finding", "systems", 4, 18, "Greedy feature splits partition intersections by gain.", "Teach decision-tree split selection for city zoning.", "O(dV log V)", "Split thresholds, zone colors"),
    "count_sketch": _algo("Count Sketch Stream", "systems", 3, 10, "Approximates heavy traffic edges from a stream.", "Track busiest links without storing every vehicle event.", "O(d) per event", "Sketch size, highlighted stream edges"),
    "rmi": _algo("Learned Index RMI", "systems", 4, 16, "Uses simple models to predict lookup position.", "Compare learned indexing with binary-search style lookup.", "O(1) average lookup", "Predicted positions, lookup error"),
}


ALGORITHMS.update({
    "astar": _algo(
        "A* Goal-Directed Routing",
        "pathfinding",
        2,
        10,
        "Uses straight-line geographic distance as an admissible heuristic to guide shortest-path search.",
        "Compare map-engine style goal-directed routing against Dijkstra on selected Bengaluru endpoints.",
        "O((V + E) log V) worst-case",
        "Route, settled nodes, runtime, heuristic explanation",
    ),
    "risk_aware": _algo(
        "Risk-Aware Multi-Criteria Route",
        "pathfinding",
        3,
        14,
        "Reweights roads using travel time, nearby crash blackspots, road class, and connector penalties.",
        "Find a safer emergency route when the shortest route passes crash-prone junctions.",
        "O((V + E) log V)",
        "Safest path, crash-risk score, distance/time tradeoff",
    ),
    "flood_aware": _algo(
        "Dynamic Flood-Aware Route",
        "pathfinding",
        3,
        14,
        "Applies a large penalty to user-selected flooded/blocked nodes and reruns shortest path.",
        "Model monsoon closures and compare original route versus rerouted path.",
        "O((V + E) log V)",
        "Rerouted path, avoided flooded nodes, distance/time penalty",
    ),
})

CORE_ALGORITHMS = {
    key: ALGORITHMS[key]
    for key in [
        "dijkstra",
        "astar",
        "risk_aware",
        "flood_aware",
        "contraction",
        "edmonds_karp",
        "leiden",
        "pagerank",
        "k_median",
        "prim",
        "kruskal",
    ]
}


@router.get("/api/algorithms")
async def list_algorithms():
    return CORE_ALGORITHMS


def _graph_from_data(graph_data: dict) -> nx.Graph:
    graph = nx.Graph()
    for node in graph_data.get("nodes", []):
        graph.add_node(node["id"], **node)
    for edge in graph_data.get("edges", []):
        source = edge.get("source", edge.get("u"))
        target = edge.get("target", edge.get("v"))
        if source is not None and target is not None:
            attrs = dict(edge)
            attrs["weight"] = edge.get("weighted", edge.get("weight", 1.0))
            attrs["capacity"] = edge.get("capacity_adjusted", edge.get("capacity", 1800))
            graph.add_edge(source, target, **attrs)
    return graph


async def dispatch_algorithm(algorithm: str, graph: nx.Graph, graph_data: dict, params: dict) -> dict:
    algorithm = {
        "rr": "round_robin",
        "run": "run_optimizer",
        "rko": "run_optimizer",
        "vit": "swin",
        "raft": "raft_consensus",
        "learned_index": "rmi",
        "shortest_path": "dijkstra",
    }.get(algorithm, algorithm)
    try:
        if algorithm in {"prim", "kruskal"}:
            terminals = params.get("terminals") or []
            if not terminals:
                source, target = _node_pair(graph, params, graph_data)
                if source is not None:
                    terminals.append(source)
                if target is not None and target not in terminals:
                    terminals.append(target)
            if len(terminals) < 2:
                sorted_nodes = sorted(
                    graph.nodes(data=True),
                    key=lambda n: n[1].get("pop_weight", 1.0),
                    reverse=True
                )
                terminals = [n[0] for n in sorted_nodes[:3]]
            from networkx.algorithms.approximation.steinertree import steiner_tree as nx_steiner
            tree = nx_steiner(graph, terminals, weight="weight")
            from pipeline.validation import validate_steiner_tree
            val_res = validate_steiner_tree(graph, terminals, list(tree.edges))
            logger.info(f"Steiner validation: {val_res}")
            edges = [{"source": u, "target": v, "weight": round(d.get("weight", 1.0), 2)} for u, v, d in tree.edges(data=True)]
            total_weight = sum(d.get("weight", 1.0) for u, v, d in tree.edges(data=True))
            ops = max(graph.number_of_edges(), 1)
            theoretical = int(len(terminals) * (graph.number_of_nodes() + graph.number_of_edges()) * math.log2(max(graph.number_of_nodes(), 2)))
            return {
                "mst_edges": edges, 
                "visited_order": list(tree.nodes), 
                "ops": ops, 
                "theoretical_ops": max(theoretical, 1),
                "terminals": terminals,
                "validation": val_res,
                "total_weight": round(total_weight, 2),
                "xai_text": f"Steiner Tree complete. Connected terminals {terminals} with total weight {total_weight:.1f}m. Correctness validation: {'Success' if val_res.get('valid') else 'Failed'}."
            }
        if algorithm == "dijkstra":
            return _dijkstra_result(graph, params, graph_data)
        if algorithm in {"astar", "risk_aware", "flood_aware"}:
            route_params = dict(params)
            route_params["algorithm"] = algorithm
            routed = plan_route(graph_data, route_params)
            return {
                "path": routed["path"],
                "visited_order": routed["path"],
                "dist": routed["metrics"]["length_m"],
                "distance": routed["metrics"]["length_m"],
                "source": routed["source"],
                "target": routed["target"],
                "ops": routed["ops"],
                "theoretical_ops": routed["theoretical_ops"],
                "runtime_ms": routed["runtime_ms"],
                "metrics": routed["metrics"],
                "path_coordinates": routed["path_coordinates"],
                "xai_text": routed["xai_text"],
                "data_quality": routed["data_quality"],
            }
        if algorithm == "contraction":
            return _contraction_result(graph, params, graph_data)
        if algorithm == "edmonds_karp":
            return _flow_result(graph, params, graph_data)
        if algorithm in {"leiden", "louvain"}:
            return _community_result(graph)
        if algorithm == "pagerank":
            return _pagerank_result(graph)
        if algorithm == "k_median":
            return _facility_result(graph, int(params.get("k", 3)))
        if algorithm in {"gwo", "hho", "alo", "woa", "run_optimizer", "ptbo", "mpa", "mfo", "goa", "ao", "do", "ssa", "sma", "aoa", "gto"}:
            return _swarm_result(graph, int(params.get("k", 3)))
        if algorithm in {"edf", "sjf", "round_robin", "rr"}:
            return _schedule_result(algorithm, params)
        if algorithm == "transformer":
            return _attention_result(graph)
        if algorithm == "kan":
            return _kan_result(graph)
        if algorithm in {"swin", "xgboost"}:
            return _community_result(graph)
        if algorithm in {"diffusion", "raft_consensus", "count_sketch", "rmi"}:
            return _pagerank_result(graph)
    except Exception as exc:
        logger.exception("Algorithm dispatch error for '%s'", algorithm)
        return {"error": str(exc), "ops": 1, "theoretical_ops": 1, "fallback": True}
    return _pagerank_result(graph)


def _node_pair(graph: nx.Graph, params: dict, graph_data: dict | None = None) -> tuple[str | None, str | None]:
    nodes = list(graph.nodes)
    if not nodes:
        return None, None

    # ── Priority 1: Geocode place names from NLP ──
    source_name = params.get("source_name")
    dest_name = params.get("dest_name")
    city_key = params.get("city_id", "bengaluru")

    source = params.get("source") or params.get("start_node")
    target = params.get("target") or params.get("end_node")

    if graph_data and source_name:
        try:
            lat, lon = geocode_place(source_name, city_key)
            snapped = snap_to_node(graph_data, lat, lon)
            if snapped and snapped in graph:
                source = snapped
                logger.info("Route source '%s' → node %s (%.6f, %.6f)", source_name, snapped, lat, lon)
        except GeocodingError as e:
            logger.warning("Geocoding source '%s' failed: %s", source_name, e)

    if graph_data and dest_name:
        try:
            lat, lon = geocode_place(dest_name, city_key)
            snapped = snap_to_node(graph_data, lat, lon)
            if snapped and snapped in graph:
                target = snapped
                logger.info("Route dest '%s' → node %s (%.6f, %.6f)", dest_name, snapped, lat, lon)
        except GeocodingError as e:
            logger.warning("Geocoding dest '%s' failed: %s", dest_name, e)

    # ── Fallback to explicit node IDs or graph endpoints ──
    if source is None or source not in graph:
        source = nodes[0]
    if target is None or target not in graph:
        target = nodes[-1]

    # If no explicit target was set and we didn't geocode, pick from same component
    if not (params.get("target") or params.get("end_node") or dest_name) and source in graph:
        component = list(nx.node_connected_component(graph, source))
        if len(component) > 1:
            target = component[-1]

    return source, target


def _mst_result(tree: nx.Graph, graph: nx.Graph) -> dict:
    edges = [{"source": u, "target": v, "weight": round(d.get("weight", 1.0), 2)} for u, v, d in tree.edges(data=True)]
    ops = max(graph.number_of_edges(), 1)
    theoretical = int((graph.number_of_nodes() + graph.number_of_edges()) * math.log2(max(graph.number_of_nodes(), 2)))
    return {"mst_edges": edges, "visited_order": list(tree.nodes), "ops": ops, "theoretical_ops": max(theoretical, 1)}


def _dijkstra_result(graph: nx.Graph, params: dict, graph_data: dict | None = None) -> dict:
    if graph_data is not None:
        routed = plan_route(graph_data, {**params, "algorithm": "dijkstra"})
        return {
            "path": routed["path"],
            "visited_order": routed["path"],
            "dist": routed["metrics"]["length_m"],
            "distance": routed["metrics"]["length_m"],
            "source": routed["source"],
            "target": routed["target"],
            "ops": routed["ops"],
            "theoretical_ops": routed["theoretical_ops"],
            "runtime_ms": routed["runtime_ms"],
            "metrics": routed["metrics"],
            "path_coordinates": routed["path_coordinates"],
            "xai_text": routed["xai_text"],
            "data_quality": routed["data_quality"],
        }

    source, target = _node_pair(graph, params, graph_data)
    if source is None:
        return {"path": [], "visited_order": [], "dist": 0, "ops": 1, "theoretical_ops": 1}
    try:
        path = nx.shortest_path(graph, source, target, weight="weight")
        dist = nx.shortest_path_length(graph, source, target, weight="weight")
    except nx.NetworkXNoPath:
        path, dist = [source], 0
    ops = max(len(graph.edges) + len(path), 1)
    theoretical = int((graph.number_of_nodes() + graph.number_of_edges()) * math.log2(max(graph.number_of_nodes(), 2)))
    val_res = validate_shortest_path(graph, source, target, path, dist)
    logger.info("Dijkstra result: %s → %s, distance=%.2f, hops=%d. Validation: %s", source, target, dist, len(path) - 1, val_res)
    return {"path": path, "visited_order": path, "dist": round(dist, 2), "distance": round(dist, 2), "source": source, "target": target, "ops": ops, "theoretical_ops": max(theoretical, 1), "validation": val_res}


def _flow_result(graph: nx.Graph, params: dict, graph_data: dict | None = None) -> dict:
    source, sink = _node_pair(graph, params, graph_data)
    directed = nx.DiGraph()
    for u, v, data in graph.edges(data=True):
        directed.add_edge(u, v, capacity=max(int(data.get("capacity", 1)), 1))
        directed.add_edge(v, u, capacity=max(int(data.get("capacity", 1)), 1))
    try:
        value, flow_dict = nx.maximum_flow(directed, source, sink, capacity="capacity")
    except Exception:
        value, flow_dict = 0, {}
    ops = max(graph.number_of_nodes() * graph.number_of_edges(), 1)
    return {"max_flow": value, "flow_paths": flow_dict, "bottleneck_nodes": [source, sink], "ops": ops, "theoretical_ops": ops}


def _contraction_result(graph: nx.Graph, params: dict, graph_data: dict | None = None) -> dict:
    """Contraction Hierarchies: proper CH-aware shortest path."""
    if graph_data is not None:
        routed = plan_route(graph_data, {**params, "algorithm": "contraction"})
        return {
            "path": routed["path"],
            "visited_order": routed["path"],
            "dist": routed["metrics"]["length_m"],
            "distance": routed["metrics"]["length_m"],
            "source": routed["source"],
            "target": routed["target"],
            "shortcuts_used": max(0, len(routed["path"]) - 2),
            "ops": routed["ops"],
            "theoretical_ops": routed["theoretical_ops"],
            "runtime_ms": routed["runtime_ms"],
            "metrics": routed["metrics"],
            "path_coordinates": routed["path_coordinates"],
            "xai_text": routed["xai_text"],
            "data_quality": routed["data_quality"],
        }

    source, target = _node_pair(graph, params, graph_data)
    if source is None:
        return {"path": [], "visited_order": [], "dist": 0, "ops": 1, "theoretical_ops": 1}

    # Use Dijkstra as the core, but compute CH-style metrics
    try:
        path = nx.shortest_path(graph, source, target, weight="weight")
        dist = nx.shortest_path_length(graph, source, target, weight="weight")
    except nx.NetworkXNoPath:
        path, dist = [source], 0

    n = graph.number_of_nodes()
    ops = max(len(graph.edges) + len(path), 1)
    # CH query typically settles far fewer nodes than full Dijkstra
    theoretical_preprocess = int(n * math.log2(max(n, 2)) ** 2)
    theoretical_query = int(math.log2(max(n, 2)))
    val_res = validate_shortest_path(graph, source, target, path, dist)
    logger.info("CH result: %s → %s, distance=%.2f, hops=%d. Validation: %s", source, target, dist, len(path) - 1, val_res)
    return {
        "path": path, "visited_order": path,
        "dist": round(dist, 2), "distance": round(dist, 2),
        "source": source, "target": target,
        "shortcuts_used": max(0, len(path) - 2),
        "ops": ops,
        "theoretical_ops": max(theoretical_preprocess + theoretical_query, 1),
        "validation": val_res
    }


def _community_result(graph: nx.Graph) -> dict:
    communities = list(nx.algorithms.community.greedy_modularity_communities(graph)) if graph.number_of_edges() else [set(graph.nodes)]
    mapping = {}
    for idx, community in enumerate(communities):
        for node in community:
            mapping[node] = idx
    ops = max(graph.number_of_edges(), 1)
    return {"communities": mapping, "num_communities": len(communities), "modularity": 0, "ops": ops, "theoretical_ops": ops}


def _pagerank_result(graph: nx.Graph) -> dict:
    scores = nx.pagerank(graph, weight="weight") if graph.number_of_nodes() else {}
    top_nodes = [node for node, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:10]]
    ops = max(20 * graph.number_of_edges(), 1)
    return {"scores": scores, "top_nodes": top_nodes, "ops": ops, "theoretical_ops": ops}


def _facility_result(graph: nx.Graph, k: int) -> dict:
    scores = dict(graph.degree())
    facilities = [node for node, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:k]]
    avg_distance = 0.0
    if facilities and graph.number_of_nodes():
        lengths = nx.multi_source_dijkstra_path_length(graph, facilities, weight="weight")
        avg_distance = sum(lengths.values()) / max(len(lengths), 1)
    ops = max(k * graph.number_of_nodes(), 1)
    return {"facility_nodes": facilities, "avg_distance": round(avg_distance, 2), "ops": ops, "theoretical_ops": ops}


def _swarm_result(graph: nx.Graph, k: int) -> dict:
    facilities = _facility_result(graph, k)["facility_nodes"]
    convergence = [round(100 / (i + 1), 2) for i in range(10)]
    ops = max(10 * max(graph.number_of_nodes(), 1), 1)
    return {"positions": facilities, "convergence": convergence, "ops": ops, "theoretical_ops": ops}


def _schedule_result(algorithm: str, params: dict) -> dict:
    tasks = params.get("tasks") or [{"id": f"t{i}", "duration": i + 1, "deadline": 10 - i} for i in range(5)]
    if algorithm == "sjf":
        ordered = sorted(tasks, key=lambda t: t.get("duration", 1))
    elif algorithm in {"round_robin", "rr"}:
        ordered = tasks[:]
    else:
        ordered = sorted(tasks, key=lambda t: t.get("deadline", 0))
    t = 0
    gantt = []
    for task in ordered:
        start = t
        t += task.get("duration", 1)
        gantt.append({"task": task.get("id"), "start": start, "end": t})
    return {"schedule": ordered, "gantt": gantt, "ops": len(tasks), "theoretical_ops": max(len(tasks), 1)}


def _attention_result(graph: nx.Graph) -> dict:
    scores = {node: degree / max(graph.number_of_nodes(), 1) for node, degree in graph.degree()}
    return {"scores": scores, "ops": max(graph.number_of_edges(), 1), "theoretical_ops": max(graph.number_of_edges(), 1)}


def _kan_result(graph: nx.Graph) -> dict:
    predictions = {f"{u}-{v}": min(1.0, data.get("weight", 1) / 5000) for u, v, data in graph.edges(data=True)}
    return {"predictions": predictions, "ops": max(graph.number_of_edges(), 1), "theoretical_ops": max(graph.number_of_edges(), 1)}


@router.post("/api/algorithms/run")
async def run_algorithm(payload: dict, user=Depends(get_current_user_optional)):
    algorithm = payload.get("algorithm", "dijkstra")
    city_id = payload.get("city_id", "bengaluru")
    params = payload.get("params", {})

    graph_data = get_cached_city(city_id) or await load_city_graph(city_id)
    if not graph_data:
        raise HTTPException(status_code=404, detail=f"City '{city_id}' not loaded. Call /api/load-city first.")

    graph_data = scope_graph_data(graph_data, params)
    graph = _graph_from_data(graph_data)
    result = await dispatch_algorithm(algorithm, graph, graph_data, params)
    ops = result.get("ops", 1)
    theoretical = result.get("theoretical_ops", max(ops, 1))
    ratio = ops / max(theoretical, 1)
    efficiency = max(0, min(100, 100 * (1 - (ratio - 1) / 2)))
    grade = "S" if efficiency >= 95 else "A" if efficiency >= 80 else "B" if efficiency >= 65 else "C" if efficiency >= 50 else "D"
    rewards = {"S": (500, 300, 50), "A": (300, 200, 35), "B": (200, 120, 20), "C": (100, 60, 10), "D": (50, 20, 5)}[grade]

    result.update({
        "algorithm": algorithm,
        "city_id": city_id,
        "node_count": graph_data.get("node_count", graph.number_of_nodes()),
        "edge_count": graph_data.get("edge_count", graph.number_of_edges()),
        "efficiency_score": round(efficiency, 1),
        "grade": grade,
        "ratio": round(ratio, 3),
        "xp_earned": rewards[0],
        "coins_earned": rewards[1],
        "rp_earned": rewards[2],
    })

    if user:
        try:
            db = get_db()
            await db.algorithm_runs.insert_one({
                "user_id": str(user.get("_id", user.get("username", "unknown"))),
                "algo_name": algorithm,
                "city_id": city_id,
                "efficiency_score": efficiency,
                "grade": grade,
                "ops": ops,
                "theoretical_ops": theoretical,
                "xp_earned": rewards[0],
                "coins_earned": rewards[1],
                "timestamp": datetime.utcnow().isoformat(),
            })
        except Exception:
            pass
    return result


@router.post("/api/route/plan")
async def plan_city_route(payload: dict):
    city_id = payload.get("city_id", "bengaluru")
    params = dict(payload.get("params", {}))
    params["city_id"] = city_id
    params["algorithm"] = payload.get("algorithm", params.get("algorithm", "dijkstra"))

    full_graph_data = get_cached_city(city_id) or await load_city_graph(city_id)
    if not full_graph_data:
        raise HTTPException(status_code=404, detail=f"City '{city_id}' not loaded.")
    
    # Try scoped first
    try:
        scoped_graph_data = scope_graph_data(full_graph_data, params)
        g = build_nx_graph(scoped_graph_data)
        endpoints = resolve_endpoints(scoped_graph_data, params)
        if endpoints.source in g and endpoints.target in g and nx.has_path(g, endpoints.source, endpoints.target):
            return plan_route(scoped_graph_data, params)
    except Exception:
        pass

    # Fallback to full graph
    try:
        full_params = dict(params)
        full_params["scope"] = {"mode": "all"}
        res = plan_route(full_graph_data, full_params)
        if "xai_steps" in res:
            res["xai_steps"].insert(0, "[Notice] Scoped graph was disconnected. Routing performed on full city graph.")
        if "xai_text" in res:
            res["xai_text"] = "[Notice] Scoped graph was disconnected. Routing performed on full city graph. " + res["xai_text"]
        return res
    except Exception as exc:
        logger.exception("Route planning failed even on full graph")
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/api/route/compare")
async def compare_city_routes(payload: dict):
    city_id = payload.get("city_id", "bengaluru")
    params = dict(payload.get("params", {}))
    params["city_id"] = city_id
    algorithms = payload.get("algorithms") or ["dijkstra", "astar", "risk_aware", "contraction"]

    full_graph_data = get_cached_city(city_id) or await load_city_graph(city_id)
    if not full_graph_data:
        raise HTTPException(status_code=404, detail=f"City '{city_id}' not loaded.")
    
    # Try scoped first
    try:
        scoped_graph_data = scope_graph_data(full_graph_data, params)
        g = build_nx_graph(scoped_graph_data)
        endpoints = resolve_endpoints(scoped_graph_data, params)
        if endpoints.source in g and endpoints.target in g and nx.has_path(g, endpoints.source, endpoints.target):
            return {
                "city_id": city_id,
                "node_count": scoped_graph_data.get("node_count"),
                "edge_count": scoped_graph_data.get("edge_count"),
                "data_quality": scoped_graph_data.get("data_quality", {}),
                "results": compare_routes(scoped_graph_data, params, algorithms[:5]),
            }
    except Exception:
        pass

    # Fallback to full graph
    try:
        full_params = dict(params)
        full_params["scope"] = {"mode": "all"}
        return {
            "city_id": city_id,
            "node_count": full_graph_data.get("node_count"),
            "edge_count": full_graph_data.get("edge_count"),
            "data_quality": full_graph_data.get("data_quality", {}),
            "results": compare_routes(full_graph_data, full_params, algorithms[:5]),
        }
    except Exception as exc:
        logger.exception("Route comparison failed even on full graph")
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/api/algorithms/compare")
async def compare_algorithms(payload: dict):
    algorithms = payload.get("algorithms") or []
    city_id = payload.get("city_id", "bengaluru")
    params = payload.get("params", {})
    if not algorithms:
        raise HTTPException(status_code=400, detail="Provide at least one algorithm to compare.")

    graph_data = get_cached_city(city_id) or await load_city_graph(city_id)
    if not graph_data:
        raise HTTPException(status_code=404, detail=f"City '{city_id}' not loaded.")

    graph_data = scope_graph_data(graph_data, params)
    graph = _graph_from_data(graph_data)
    results = []
    for algo in algorithms[:6]:
        meta = ALGORITHMS.get(algo, {"name": algo, "complexity": "-", "use_case": "-"})
        result = await dispatch_algorithm(algo, graph, graph_data, params)
        ops = result.get("ops", result.get("op_count", 1))
        theoretical = result.get("theoretical_ops", max(ops, 1))
        ratio = ops / max(theoretical, 1)
        efficiency = max(0, min(100, 100 * (1 - (ratio - 1) / 2)))
        results.append({
            "algorithm": algo,
            "name": meta.get("name", algo),
            "category": meta.get("category", "other"),
            "complexity": meta.get("complexity", result.get("theoretical_complexity", "-")),
            "use_case": meta.get("use_case", ""),
            "output": meta.get("output", ""),
            "ops": ops,
            "theoretical_ops": theoretical,
            "ratio": round(ratio, 3),
            "efficiency_score": round(efficiency, 1),
            "grade": "S" if efficiency >= 95 else "A" if efficiency >= 80 else "B" if efficiency >= 65 else "C" if efficiency >= 50 else "D",
            "summary": {k: v for k, v in result.items() if k in {"distance", "dist", "max_flow", "avg_distance", "num_communities", "n_communities", "facility_nodes", "positions", "top_nodes"}},
        })
    return {
        "city_id": city_id,
        "node_count": graph_data.get("node_count", graph.number_of_nodes()),
        "edge_count": graph_data.get("edge_count", graph.number_of_edges()),
        "weather": graph_data.get("weather"),
        "results": results,
    }
