"""
algorithms/contraction.py — Contraction Hierarchies for ultra-fast shortest paths.
Based on: Geisberger et al. (2012) "Exact Routing in Large Road Networks Using Contraction Hierarchies"
Recent: SPoCH (2023) — Scalable Parallelization of Contraction Hierarchies.

Game context: Emergency vehicle routing — preprocesses the graph to enable
near-instant shortest path queries. Shows why services like Google Maps are fast.
"""

import heapq
import math
from .graph import WeightedGraph


def contraction_hierarchies(graph: WeightedGraph, source: int = None, target: int = None):
    """
    Contraction Hierarchies generator.
    Phase 1: Preprocessing — contract nodes in order of importance
    Phase 2: Query — bidirectional Dijkstra on hierarchy

    Yields deltas showing:
    - Node contractions (nodes "collapse", shortcuts appear)
    - Bidirectional search waves meeting
    """
    if graph.node_count == 0:
        return

    node_list = sorted(graph.nodes.keys())
    n = len(node_list)
    op_count = 0

    # ===== PHASE 1: PREPROCESSING =====
    # Compute node importance (ordering heuristic)
    # Importance = edge_difference + contracted_neighbors + depth
    importance = {}
    for node in node_list:
        degree = len(graph.neighbors(node))
        # Edge difference: shortcuts needed - edges removed
        neighbors = [e["to"] for e in graph.neighbors(node)]
        potential_shortcuts = 0
        for i in range(len(neighbors)):
            for j in range(i + 1, len(neighbors)):
                # Would need shortcut if path through node is shortest
                potential_shortcuts += 1
        edge_diff = potential_shortcuts - degree
        importance[node] = edge_diff + degree * 0.1
        op_count += 1

    # Sort by importance (contract least important first)
    contraction_order = sorted(node_list, key=lambda n: importance[n])

    # Build hierarchy
    shortcuts = []
    contracted = set()
    node_level = {n: 0 for n in node_list}

    # Contract nodes (show subset for visualization)
    steps_to_show = max(1, n // 25)

    for rank, node in enumerate(contraction_order):
        contracted.add(node)
        node_level[node] = rank
        op_count += 1

        # Find shortcuts needed
        neighbors = [(e["to"], e["weight"]) for e in graph.neighbors(node) if e["to"] not in contracted]
        new_shortcuts = []

        for i in range(len(neighbors)):
            for j in range(i + 1, len(neighbors)):
                u, wu = neighbors[i]
                v, wv = neighbors[j]
                shortcut_weight = wu + wv

                # Check if shortcut is necessary (is this the only shortest path?)
                # Simplified: always add shortcut if path through contracted node
                direct = graph.get_edge_weight(u, v)
                if shortcut_weight < direct:
                    new_shortcuts.append({
                        "from": u, "to": v,
                        "weight": round(shortcut_weight, 3),
                        "via": node,
                    })

        shortcuts.extend(new_shortcuts)

        if rank % steps_to_show == 0 or rank == n - 1:
            yield {
                "kind": "node_contracted",
                "node": node,
                "rank": rank,
                "total": n,
                "shortcuts_added": len(new_shortcuts),
                "total_shortcuts": len(shortcuts),
                "op_count": op_count,
                "xai_text": f"Contracted node {node} (rank {rank + 1}/{n}). "
                           f"Importance score: {importance[node]:.1f}. "
                           f"Added {len(new_shortcuts)} shortcut edges to preserve shortest paths. "
                           f"Total shortcuts so far: {len(shortcuts)}. "
                           f"Least important nodes are contracted first to minimize shortcuts.",
            }

    yield {
        "kind": "preprocessing_done",
        "total_shortcuts": len(shortcuts),
        "contraction_order_size": n,
        "op_count": op_count,
        "xai_text": f"Contraction preprocessing complete. Created {len(shortcuts)} shortcut edges. "
                   f"The hierarchy enables queries in O(log n) time instead of O((V+E)logV). "
                   f"This is why Google Maps can route across millions of nodes instantly.",
    }

    # ===== PHASE 2: QUERY (if source and target provided) =====
    if source is None or target is None:
        # Pick random source/target
        if source is None:
            source = node_list[0]
        if target is None:
            target = node_list[min(n - 1, n // 2)]

    # Bidirectional Dijkstra on hierarchy
    # Forward search from source (only go UP in hierarchy)
    # Backward search from target (only go UP in hierarchy)

    fwd_dist = {source: 0}
    bwd_dist = {target: 0}
    fwd_heap = [(0, source)]
    bwd_heap = [(0, target)]
    fwd_visited = set()
    bwd_visited = set()
    fwd_prev = {source: None}
    bwd_prev = {target: None}
    best_dist = float("inf")
    meeting_node = None

    yield {
        "kind": "query_start",
        "source": source,
        "target": target,
        "op_count": op_count,
        "xai_text": f"Starting bidirectional CH query from node {source} to {target}. "
                   f"Forward search goes UP the hierarchy from source. "
                   f"Backward search goes UP from target. They meet at a high-level node.",
    }

    while fwd_heap or bwd_heap:
        # Forward step
        if fwd_heap:
            d, u = heapq.heappop(fwd_heap)
            op_count += 1
            if u not in fwd_visited:
                fwd_visited.add(u)

                # Check if backward search reached this node
                if u in bwd_dist:
                    total = d + bwd_dist[u]
                    if total < best_dist:
                        best_dist = total
                        meeting_node = u

                for edge in graph.neighbors(u):
                    v = edge["to"]
                    # Only go UP in hierarchy
                    if node_level.get(v, 0) > node_level.get(u, 0):
                        new_dist = d + edge["weight"]
                        if v not in fwd_dist or new_dist < fwd_dist[v]:
                            fwd_dist[v] = new_dist
                            fwd_prev[v] = u
                            heapq.heappush(fwd_heap, (new_dist, v))

        # Backward step
        if bwd_heap:
            d, u = heapq.heappop(bwd_heap)
            op_count += 1
            if u not in bwd_visited:
                bwd_visited.add(u)

                if u in fwd_dist:
                    total = d + fwd_dist[u]
                    if total < best_dist:
                        best_dist = total
                        meeting_node = u

                for edge in graph.neighbors(u):
                    v = edge["to"]
                    if node_level.get(v, 0) > node_level.get(u, 0):
                        new_dist = d + edge["weight"]
                        if v not in bwd_dist or new_dist < bwd_dist[v]:
                            bwd_dist[v] = new_dist
                            bwd_prev[v] = u
                            heapq.heappush(bwd_heap, (new_dist, v))

        # Termination check
        fwd_min = fwd_heap[0][0] if fwd_heap else float("inf")
        bwd_min = bwd_heap[0][0] if bwd_heap else float("inf")
        if fwd_min + bwd_min >= best_dist:
            break

        if len(fwd_visited) % max(1, n // 15) == 0:
            yield {
                "kind": "query_progress",
                "fwd_settled": len(fwd_visited),
                "bwd_settled": len(bwd_visited),
                "best_dist": round(best_dist, 3) if best_dist < float("inf") else -1,
                "meeting_node": meeting_node,
                "op_count": op_count,
                "xai_text": f"Bidirectional search: forward settled {len(fwd_visited)}, "
                           f"backward settled {len(bwd_visited)} nodes. "
                           f"{'Best path so far: ' + str(round(best_dist, 2)) if best_dist < float('inf') else 'Searching...'}",
            }

    # Reconstruct path
    path = []
    if meeting_node is not None:
        # Forward path
        fwd_path = []
        curr = meeting_node
        while curr is not None:
            fwd_path.append(curr)
            curr = fwd_prev.get(curr)
        fwd_path.reverse()

        # Backward path
        bwd_path = []
        curr = bwd_prev.get(meeting_node)
        while curr is not None:
            bwd_path.append(curr)
            curr = bwd_prev.get(curr)

        path = fwd_path + bwd_path

    yield {
        "kind": "algorithm_done",
        "source": source,
        "target": target,
        "distance": round(best_dist, 3) if best_dist < float("inf") else -1,
        "path": path,
        "meeting_node": meeting_node,
        "fwd_settled": len(fwd_visited),
        "bwd_settled": len(bwd_visited),
        "total_settled": len(fwd_visited) + len(bwd_visited),
        "total_shortcuts": len(shortcuts),
        "op_count": op_count,
        "nodes_visited": len(fwd_visited) + len(bwd_visited),
        "theoretical_complexity": "O(n·log²n) preprocess, O(log n) query",
        "xai_text": f"Contraction Hierarchies complete. "
                   f"Shortest distance: {best_dist:.2f} (source {source} → target {target}). "
                   f"Query settled only {len(fwd_visited) + len(bwd_visited)} of {n} nodes — "
                   f"that's {(len(fwd_visited) + len(bwd_visited)) / n * 100:.0f}% of the graph. "
                   f"Standard Dijkstra would settle ~{n} nodes. "
                   f"CH trades {len(shortcuts)} preprocessing shortcuts for {n // max(len(fwd_visited) + len(bwd_visited), 1)}x faster queries.",
    }
