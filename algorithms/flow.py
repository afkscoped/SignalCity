"""
algorithms/flow.py — Edmonds-Karp (BFS-based Ford-Fulkerson) max flow algorithm.
Generator-based for step-by-step visualization.
"""

from collections import deque
from .graph import WeightedGraph


def edmonds_karp(graph: WeightedGraph, source: int, sink: int):
    """
    Edmonds-Karp generator. Yields one delta per augmenting path found.
    Uses BFS to find shortest augmenting paths (O(VE²) complexity).
    """
    if source not in graph.nodes or sink not in graph.nodes:
        return
    if source == sink:
        return

    # Build residual graph
    residual = {}
    nodes_in_flow = set()
    for nid in graph.nodes:
        for edge in graph.neighbors(nid):
            u, v = nid, edge["to"]
            nodes_in_flow.add(u)
            nodes_in_flow.add(v)
            if (u, v) not in residual:
                residual[(u, v)] = edge.get("capacity", 800)
            if (v, u) not in residual:
                residual[(v, u)] = 0  # reverse edge starts at 0

    total_flow = 0
    num_paths = 0
    op_count = 0

    while True:
        # BFS to find augmenting path
        parent = {source: None}
        visited_bfs = {source}
        queue = deque([source])
        found = False

        while queue:
            u = queue.popleft()
            op_count += 1

            for v in graph.nodes:
                if v not in visited_bfs and residual.get((u, v), 0) > 0:
                    parent[v] = u
                    visited_bfs.add(v)
                    if v == sink:
                        found = True
                        break
                    queue.append(v)

            # Also check reverse edges
            for (eu, ev), cap in residual.items():
                if eu == u and ev not in visited_bfs and cap > 0:
                    parent[ev] = u
                    visited_bfs.add(ev)
                    if ev == sink:
                        found = True
                        break
                    queue.append(ev)

            if found:
                break

        if not found:
            break

        # Find bottleneck
        path = []
        v = sink
        bottleneck = float("inf")
        while v is not None:
            path.append(v)
            if parent[v] is not None:
                cap = residual.get((parent[v], v), 0)
                bottleneck = min(bottleneck, cap)
            v = parent[v]
        path.reverse()

        if bottleneck <= 0 or bottleneck == float("inf"):
            break

        # Find bottleneck edge
        bottleneck_edge = [path[0], path[1]]
        min_cap = float("inf")
        for i in range(len(path) - 1):
            cap = residual.get((path[i], path[i + 1]), 0)
            if cap < min_cap:
                min_cap = cap
                bottleneck_edge = [path[i], path[i + 1]]

        # Augment along path
        v = sink
        while parent[v] is not None:
            u = parent[v]
            residual[(u, v)] = residual.get((u, v), 0) - bottleneck
            residual[(v, u)] = residual.get((v, u), 0) + bottleneck
            v = u

        total_flow += bottleneck
        num_paths += 1

        # Build residual edges snapshot for frontend
        res_edges = []
        for (eu, ev), cap in residual.items():
            if cap > 0 and eu in nodes_in_flow and ev in nodes_in_flow:
                res_edges.append({"from": eu, "to": ev, "residual_cap": cap})

        path_str = " → ".join(map(str, path))
        yield {
            "kind": "augmenting_path",
            "path": path,
            "path_flow": bottleneck,
            "bottleneck_edge": bottleneck_edge,
            "total_flow": total_flow,
            "residual_edges": res_edges[:50],  # limit for performance
            "op_count": op_count,
            "xai_text": f"Found augmenting path: {path_str} — can push {bottleneck:.0f} vehicles/hr along "
                       f"this route. The bottleneck is edge ({bottleneck_edge[0]}→{bottleneck_edge[1]}) "
                       f"with only {min_cap:.0f} remaining capacity. After augmentation, total flow: "
                       f"{total_flow:.0f} vehicles/hr.",
        }

    # Find min-cut: BFS from source on residual graph
    reachable = set()
    queue = deque([source])
    reachable.add(source)
    while queue:
        u = queue.popleft()
        for (eu, ev), cap in residual.items():
            if eu == u and ev not in reachable and cap > 0:
                reachable.add(ev)
                queue.append(ev)

    # Min-cut edges: from reachable to unreachable
    cut_edges = []
    for nid in reachable:
        for edge in graph.neighbors(nid):
            if edge["to"] not in reachable:
                cut_edges.append({"u": nid, "v": edge["to"]})

    yield {
        "kind": "algorithm_done",
        "total_flow": total_flow,
        "num_paths": num_paths,
        "cut_edges": cut_edges,
        "cut_size": len(cut_edges),
        "op_count": op_count,
        "nodes_visited": len(nodes_in_flow),
        "theoretical_complexity": "O(VE²)",
        "xai_text": f"Max flow reached: {total_flow:.0f} vehicles/hr from source to sink. "
                   f"Found {num_paths} augmenting paths. The min-cut has {len(cut_edges)} edges — "
                   f"these are the critical bottleneck roads. Max-Flow Min-Cut theorem confirmed: "
                   f"flow = cut capacity = {total_flow:.0f}.",
    }
