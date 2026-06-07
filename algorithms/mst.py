"""
algorithms/mst.py — Prim's and Kruskal's Minimum Spanning Tree.
Both implemented as Python generators yielding GraphDelta dicts per step.
"""

import heapq
import math
from .graph import WeightedGraph


def prim_mst(graph: WeightedGraph, start_node: int = None):
    """
    Prim's MST generator. Yields one GraphDelta per operation.
    Uses min-heap priority queue. Tracks op_count for visualization.
    """
    if graph.node_count == 0:
        return

    # Pick start node: highest pop_weight if not specified
    if start_node is None or start_node not in graph.nodes:
        start_node = max(graph.nodes.keys(),
                        key=lambda n: graph.nodes[n].get("pop_weight", 1.0))

    visited = set()
    visited.add(start_node)
    heap = []  # (weight, from_node, to_node)
    op_count = 0
    edges_added = 0
    total_weight = 0.0

    # Push all edges from start node
    for edge in graph.neighbors(start_node):
        heapq.heappush(heap, (edge["weight"], start_node, edge["to"]))
        op_count += 1
        yield {
            "kind": "node_frontier",
            "node": edge["to"],
            "from_node": start_node,
            "weight": edge["weight"],
            "op_count": op_count,
            "frontier_size": len(heap),
            "xai_text": f"Added node {edge['to']} to frontier with edge weight {edge['weight']:.2f}. "
                       f"Frontier now has {len(heap)} candidates.",
        }

    yield {
        "kind": "node_visited",
        "node": start_node,
        "distance": 0,
        "op_count": op_count,
        "frontier_size": len(heap),
        "xai_text": f"Starting Prim's MST from node {start_node} "
                   f"(population weight: {graph.nodes[start_node].get('pop_weight', 1.0):.1f}). "
                   f"This node is now in the growing tree.",
    }

    V = graph.node_count
    E = graph.edge_count
    theoretical = int((V + E) * math.log2(max(V, 2)))

    while heap and len(visited) < graph.node_count:
        weight, u, v = heapq.heappop(heap)
        op_count += 1

        if v in visited:
            continue

        visited.add(v)
        edges_added += 1
        total_weight += weight

        yield {
            "kind": "edge_added",
            "from_node": u,
            "to_node": v,
            "weight": weight,
            "op_count": op_count,
            "frontier_size": len(heap),
            "edges_added": edges_added,
            "total_weight": round(total_weight, 2),
            "xai_text": f"Prim chose edge ({u}→{v}) with weight {weight:.2f} — the minimum-weight edge "
                       f"connecting the {len(visited)} already-connected nodes to any of the {len(heap)} "
                       f"frontier candidates. Adding this edge grows the tree without creating a cycle.",
        }

        # Push edges from newly visited node
        for edge in graph.neighbors(v):
            if edge["to"] not in visited:
                heapq.heappush(heap, (edge["weight"], v, edge["to"]))
                op_count += 1

    # Final summary
    ratio = op_count / max(theoretical, 1)
    yield {
        "kind": "algorithm_done",
        "op_count": op_count,
        "edges_added": edges_added,
        "total_weight": round(total_weight, 2),
        "nodes_visited": len(visited),
        "theoretical_ops": theoretical,
        "theoretical_complexity": "O((V+E)logV)",
        "ratio": round(ratio, 4),
        "xai_text": f"Prim's MST complete. Connected all {len(visited)} nodes with {edges_added} edges. "
                   f"Total tree weight: {total_weight:.1f}. Used {op_count} priority queue operations. "
                   f"Theoretical bound: O((V+E)logV) = O({theoretical}). "
                   f"Actual/theoretical ratio: {ratio:.1%}.",
    }


class UnionFind:
    """Union-Find supporting string or integer keys."""

    def __init__(self, elements):
        self.parent = {x: x for x in elements}
        self.rank = {x: 0 for x in elements}
        self.component_count = len(elements)

    def find(self, x):
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x, y) -> bool:
        px, py = self.find(x), self.find(y)
        if px == py:
            return False
        if self.rank[px] < self.rank[py]:
            px, py = py, px
        self.parent[py] = px
        if self.rank[px] == self.rank[py]:
            self.rank[px] += 1
        self.component_count -= 1
        return True

    def connected(self, x, y):
        return self.find(x) == self.find(y)


def kruskal_mst(graph: WeightedGraph):
    """
    Kruskal's MST generator. Yields one GraphDelta per edge consideration.
    Uses Union-Find for cycle detection.
    """
    if graph.node_count == 0:
        return

    # Get all edges and sort by weight
    all_edges = graph.get_all_edges()
    sorted_edges = sorted(all_edges, key=lambda e: e["weight"])

    uf = UnionFind(list(graph.nodes.keys()))
    op_count = len(sorted_edges)  # sorting cost
    edges_added = 0
    total_weight = 0.0
    rank = 0

    E = len(sorted_edges)
    theoretical = int(E * math.log2(max(E, 2)))

    for edge in sorted_edges:
        u, v = edge["u"], edge["v"]
        w = edge["weight"]
        rank += 1
        op_count += 2  # find operations

        if uf.connected(u, v):
            comp = uf.find(u)
            yield {
                "kind": "edge_rejected",
                "from_node": u,
                "to_node": v,
                "weight": w,
                "op_count": op_count,
                "xai_text": f"Kruskal skipped edge ({u}→{v}) weight {w:.2f} — both endpoints are already "
                           f"in the same connected component (component #{comp}). Adding it would create "
                           f"a cycle, violating the MST property.",
            }
        else:
            uf.union(u, v)
            op_count += 1  # union operation
            edges_added += 1
            total_weight += w

            yield {
                "kind": "edge_added",
                "from_node": u,
                "to_node": v,
                "weight": w,
                "op_count": op_count,
                "edges_added": edges_added,
                "total_weight": round(total_weight, 2),
                "xai_text": f"Kruskal accepted edge ({u}→{v}) weight {w:.2f} — the #{rank} lightest edge "
                           f"overall. Nodes {u} and {v} are in different components, so adding this "
                           f"edge connects two parts of the forest without forming a cycle.",
            }

            if edges_added == graph.node_count - 1:
                break

    ratio = op_count / max(theoretical, 1)
    yield {
        "kind": "algorithm_done",
        "op_count": op_count,
        "edges_added": edges_added,
        "total_weight": round(total_weight, 2),
        "nodes_visited": graph.node_count,
        "theoretical_ops": theoretical,
        "theoretical_complexity": "O(E·log E)",
        "ratio": round(ratio, 4),
        "xai_text": f"Kruskal's MST complete. Used {edges_added} of {len(sorted_edges)} edges. "
                   f"Total weight: {total_weight:.1f}. {op_count} operations (sorting + union-find). "
                   f"Theoretical: O(E·logE) = O({theoretical}). Ratio: {ratio:.1%}.",
    }
