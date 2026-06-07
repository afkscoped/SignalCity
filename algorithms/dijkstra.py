"""
algorithms/dijkstra.py — Dijkstra's shortest path algorithm.
Generator-based for step-by-step visualization.
"""

import heapq
import math
from .graph import WeightedGraph


def dijkstra(graph: WeightedGraph, source: int, target: int = None):
    """
    Dijkstra's generator. Yields one delta per node settled or edge relaxed.
    Supports early termination when target is reached.
    """
    if graph.node_count == 0 or source not in graph.nodes:
        return

    dist = {n: float("inf") for n in graph.nodes}
    prev = {n: None for n in graph.nodes}
    dist[source] = 0
    visited = set()
    heap = [(0, source)]
    op_count = 0
    nodes_settled = 0

    V = graph.node_count
    E = graph.edge_count
    theoretical = int((V + E) * math.log2(max(V, 2)))

    yield {
        "kind": "node_visited",
        "node": source,
        "distance": 0,
        "op_count": 0,
        "frontier_size": 1,
        "xai_text": f"Starting Dijkstra from source node {source}. Distance set to 0. "
                   f"All other nodes initialized to infinity.",
    }

    while heap:
        d, u = heapq.heappop(heap)
        op_count += 1

        if u in visited:
            continue

        visited.add(u)
        nodes_settled += 1

        if u != source:
            yield {
                "kind": "node_visited",
                "node": u,
                "distance": round(d, 3),
                "op_count": op_count,
                "frontier_size": len(heap),
                "xai_text": f"Settled node {u} — shortest distance confirmed as {d:.2f}. "
                           f"This node is now permanently labelled: no future path can be shorter "
                           f"(non-negative edge weights guarantee this — Dijkstra's invariant).",
            }

        # Check if target reached
        if target is not None and u == target:
            # Reconstruct path
            path = []
            curr = target
            while curr is not None:
                path.append(curr)
                curr = prev[curr]
            path.reverse()

            yield {
                "kind": "path_found",
                "path": path,
                "distance": round(d, 3),
                "hops": len(path) - 1,
                "op_count": op_count,
                "xai_text": f"Shortest path to target node {target} found! Distance: {d:.2f} via "
                           f"{len(path) - 1} hops. Path: {' → '.join(map(str, path[:10]))}{'...' if len(path) > 10 else ''}. "
                           f"Dijkstra terminates early because once the target is settled, "
                           f"no shorter path exists.",
            }

            ratio = op_count / max(theoretical, 1)
            yield {
                "kind": "algorithm_done",
                "op_count": op_count,
                "nodes_visited": nodes_settled,
                "path": path,
                "distance": round(d, 3),
                "theoretical_ops": theoretical,
                "theoretical_complexity": "O((V+E)logV)",
                "ratio": round(ratio, 4),
                "xai_text": f"Dijkstra complete. Settled {nodes_settled} of {V} nodes to find target. "
                           f"Shortest distance: {d:.2f}. Path length: {len(path) - 1} hops. "
                           f"{op_count} operations. Early termination saved "
                           f"{V - nodes_settled} node settlements.",
            }
            return

        # Relax neighbors
        for edge in graph.neighbors(u):
            v = edge["to"]
            if v in visited:
                continue
            new_dist = d + edge["weight"]
            if new_dist < dist[v]:
                old_dist = dist[v]
                dist[v] = new_dist
                prev[v] = u
                heapq.heappush(heap, (new_dist, v))
                op_count += 1

                old_str = f"{old_dist:.2f}" if old_dist < float("inf") else "∞"
                improvement = old_dist - new_dist if old_dist < float("inf") else new_dist

                yield {
                    "kind": "edge_relaxed",
                    "from_node": u,
                    "to_node": v,
                    "distance": round(new_dist, 3),
                    "prev_distance": round(old_dist, 3) if old_dist < float("inf") else -1,
                    "weight": edge["weight"],
                    "op_count": op_count,
                    "frontier_size": len(heap),
                    "xai_text": f"Relaxed edge ({u}→{v}): old best distance to {v} was {old_str}, "
                               f"new path via {u} costs {new_dist:.2f} — an improvement of {improvement:.2f}. "
                               f"Updated priority queue.",
                }

    # No specific target — full SSSP complete
    ratio = op_count / max(theoretical, 1)
    yield {
        "kind": "algorithm_done",
        "op_count": op_count,
        "nodes_visited": nodes_settled,
        "theoretical_ops": theoretical,
        "theoretical_complexity": "O((V+E)logV)",
        "ratio": round(ratio, 4),
        "xai_text": f"Dijkstra complete. Settled all {nodes_settled} reachable nodes. "
                   f"{op_count} operations. Theoretical: O((V+E)logV) = O({theoretical}). "
                   f"Ratio: {ratio:.1%}.",
    }
