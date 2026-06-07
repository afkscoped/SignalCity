"""
algorithms/pagerank.py — PageRank Centrality for Signal City.
Based on: Brin & Page (1998) "The Anatomy of a Large-Scale Hypertextual Web Search Engine"
Modern applications in graph analytics for urban planning (2023-2024).

Game context: Identify the most important/connected intersections for
commercial district placement. High-PageRank nodes are natural hubs.
"""

import math
from .graph import WeightedGraph


def pagerank_centrality(graph: WeightedGraph, damping: float = 0.85, max_iter: int = 30, tol: float = 1e-6):
    """
    PageRank centrality generator using power iteration.
    Yields deltas showing rank values converging across iterations.

    Parameters:
        damping: probability of following a link (vs random teleport)
        max_iter: maximum iterations
        tol: convergence tolerance
    """
    if graph.node_count == 0:
        return

    node_list = sorted(graph.nodes.keys())
    n = len(node_list)
    op_count = 0

    # Initialize uniform rank
    rank = {node: 1.0 / n for node in node_list}
    out_degree = {node: len(graph.neighbors(node)) for node in node_list}

    yield {
        "kind": "iteration_start",
        "iteration": 0,
        "max_rank_node": node_list[0],
        "max_rank": round(1.0 / n, 6),
        "op_count": op_count,
        "xai_text": f"Starting PageRank with {n} nodes. Initial rank: {1.0/n:.6f} per node. "
                   f"Damping factor: {damping}. This simulates a random surfer who follows links "
                   f"with probability {damping} and teleports randomly with probability {1-damping}.",
    }

    for iteration in range(max_iter):
        new_rank = {}
        dangling_sum = 0

        # Compute dangling node contribution (nodes with no outgoing edges)
        for node in node_list:
            if out_degree[node] == 0:
                dangling_sum += rank[node]

        max_diff = 0
        for node in node_list:
            # Sum of rank contributions from incoming edges
            incoming_sum = 0
            for neighbor_edge in graph.neighbors(node):
                neighbor = neighbor_edge["to"]
                if out_degree[neighbor] > 0:
                    incoming_sum += rank[neighbor] / out_degree[neighbor]
                op_count += 1

            new_rank[node] = (1 - damping) / n + damping * (incoming_sum + dangling_sum / n)
            max_diff = max(max_diff, abs(new_rank[node] - rank[node]))

        rank = new_rank

        # Find top nodes
        sorted_nodes = sorted(node_list, key=lambda nd: rank[nd], reverse=True)
        top_5 = sorted_nodes[:5]

        # Yield progress every iteration
        yield {
            "kind": "iteration_complete",
            "iteration": iteration + 1,
            "max_diff": round(max_diff, 8),
            "top_nodes": [{"node": nd, "rank": round(rank[nd], 6), "x": graph.nodes[nd]["x"], "y": graph.nodes[nd]["y"]} for nd in top_5],
            "converged": max_diff < tol,
            "op_count": op_count,
            "xai_text": f"PageRank iteration {iteration + 1}: max change = {max_diff:.8f}. "
                       f"Top node: {top_5[0]} (rank {rank[top_5[0]]:.6f}). "
                       f"{'Converged!' if max_diff < tol else f'Converging... (need < {tol})'} "
                       f"Rank flows from low-importance to high-importance nodes, "
                       f"amplified by the damping factor.",
        }

        if max_diff < tol:
            break

    # Final ranking
    sorted_final = sorted(node_list, key=lambda nd: rank[nd], reverse=True)

    # Classify nodes by importance
    top_10_pct = set(sorted_final[:max(1, n // 10)])
    top_25_pct = set(sorted_final[:max(1, n // 4)])

    # Assign roles
    commercial_hubs = sorted_final[:max(1, n // 15)]  # top ~7%
    transit_hubs = sorted_final[max(1, n // 15):max(1, n // 8)]
    residential = sorted_final[max(1, n // 4):]

    yield {
        "kind": "algorithm_done",
        "ranks": {str(node): round(rank[node], 6) for node in sorted_final[:50]},
        "top_nodes": [{"node": nd, "rank": round(rank[nd], 6)} for nd in sorted_final[:10]],
        "commercial_hubs": commercial_hubs,
        "transit_hubs": transit_hubs[:10],
        "total_iterations": min(iteration + 1, max_iter),
        "op_count": op_count,
        "nodes_visited": n,
        "theoretical_complexity": "O(V + E) per iteration",
        "xai_text": f"PageRank complete after {min(iteration + 1, max_iter)} iterations. "
                   f"Top hub: node {sorted_final[0]} (rank {rank[sorted_final[0]]:.6f}, "
                   f"degree {out_degree[sorted_final[0]]}). "
                   f"Identified {len(commercial_hubs)} commercial hub candidates and "
                   f"{len(transit_hubs[:10])} transit hubs. "
                   f"PageRank captures 'importance' better than degree centrality because "
                   f"it considers the quality of connections, not just quantity "
                   f"(a link from an important node is worth more).",
    }
