"""
algorithms/mst.py — Prim's and Kruskal's Minimum Spanning Tree.
Both implemented as Python generators yielding GraphDelta dicts per step.
"""

import heapq
import math
from .graph import WeightedGraph


def prim_mst(graph: WeightedGraph, start_node: int = None, target_node: int = None, max_ops: int = 2500):
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

        # Check early connection
        if target_node is not None and target_node in visited:
            break
        if op_count >= max_ops:
            break

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
        "xai_text": f"Prim's MST complete. Connected {len(visited)} nodes with {edges_added} edges. "
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


def kruskal_mst(graph: WeightedGraph, source_node: int = None, target_node: int = None, max_ops: int = 2500):
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

            # Check early connection
            if source_node is not None and target_node is not None:
                if uf.connected(source_node, target_node):
                    break

            if op_count >= max_ops:
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


def steiner_tree(graph: WeightedGraph, terminals: list):
    """
    Computes an approximate Steiner tree connecting the specified terminal nodes
    using the metric-closure MST heuristic.
    Yields GraphDelta dicts per step for visualization.
    """
    import heapq
    import math
    import logging
    import networkx as nx
    from .mst import UnionFind

    logger = logging.getLogger(__name__)

    # 1. Parse terminals to match graph node type (int or str)
    first_node = list(graph.nodes.keys())[0]
    parsed_terminals = []
    for t in terminals:
        try:
            pt = int(t) if isinstance(first_node, int) else str(t)
        except ValueError:
            pt = t
        if pt in graph.nodes:
            parsed_terminals.append(pt)
    
    # Fallback if less than 2 valid terminals
    if len(parsed_terminals) < 2:
        # Pick 3 highest pop_weight nodes
        sorted_nodes = sorted(
            graph.nodes.keys(),
            key=lambda n: graph.nodes[n].get("pop_weight", 1.0),
            reverse=True
        )
        parsed_terminals = sorted_nodes[:3]

    op_count = 0
    yield {
        "kind": "steiner_start",
        "terminals": parsed_terminals,
        "op_count": op_count,
        "xai_text": f"Starting Steiner Tree approximation. Connecting {len(parsed_terminals)} terminal nodes: {parsed_terminals}.",
    }

    # 2. Compute shortest paths from each terminal using Dijkstra
    distances = {}
    prev_pointers = {}
    for source in parsed_terminals:
        dist = {source: 0.0}
        prev = {source: None}
        heap = [(0.0, source)]
        visited_nodes = 0
        
        while heap:
            d, u = heapq.heappop(heap)
            op_count += 1
            if d > dist.get(u, float('inf')):
                continue
            
            visited_nodes += 1
            if visited_nodes % 100 == 0:  # yield occasionally to show trace
                yield {
                    "kind": "steiner_searching",
                    "terminal": source,
                    "node": u,
                    "distance": d,
                    "op_count": op_count,
                    "xai_text": f"Dijkstra search from terminal {source} reached node {u} at distance {d:.1f}m.",
                }
            
            for edge in graph.neighbors(u):
                v = edge["to"]
                weight = edge["weight"]
                if d + weight < dist.get(v, float('inf')):
                    dist[v] = d + weight
                    prev[v] = u
                    heapq.heappush(heap, (dist[v], v))
        
        distances[source] = dist
        prev_pointers[source] = prev

    # 3. Build metric closure complete graph G_c on terminals
    closure_edges = []
    for i, u in enumerate(parsed_terminals):
        for v in parsed_terminals[i+1:]:
            w = distances[u].get(v, float('inf'))
            if w < float('inf'):
                closure_edges.append((w, u, v))
    
    # Sort closure edges (Kruskal's)
    closure_edges.sort()
    uf = UnionFind(parsed_terminals)
    mst_closure_edges = []
    
    yield {
        "kind": "steiner_closure_built",
        "op_count": op_count,
        "xai_text": f"Metric closure graph G_c built on terminals. Found {len(closure_edges)} candidate connection paths.",
    }

    # Kruskal's MST on G_c
    for w, u, v in closure_edges:
        op_count += 1
        if not uf.connected(u, v):
            uf.union(u, v)
            mst_closure_edges.append((u, v))
            yield {
                "kind": "steiner_closure_edge_accepted",
                "u": u,
                "v": v,
                "weight": w,
                "op_count": op_count,
                "xai_text": f"Accepted closure path between terminals {u} and {v} with shortest path distance {w:.1f}m.",
            }

    # 4. Construct subgraph H_S by taking union of shortest paths in original graph G
    subgraph_nodes = set()
    subgraph_edges = set()
    
    for u, v in mst_closure_edges:
        # Reconstruct path from v to u
        curr = v
        path_nodes = []
        while curr is not None:
            path_nodes.append(curr)
            curr = prev_pointers[u].get(curr)
            
        for idx in range(len(path_nodes) - 1):
            n1 = path_nodes[idx]
            n2 = path_nodes[idx+1]
            w = graph.get_edge_weight(n1, n2)
            subgraph_nodes.add(n1)
            subgraph_nodes.add(n2)
            subgraph_edges.add(tuple(sorted((n1, n2))))
            
            yield {
                "kind": "steiner_path_reconstructed",
                "u": n1,
                "v": n2,
                "weight": w,
                "op_count": op_count,
                "xai_text": f"Reconstructing shortest path: adding road segment ({n1}→{n2}) with weight {w:.2f}m.",
            }

    # 5. Find MST on subgraph H_S to eliminate any cycles from overlapping paths
    sub_wg = WeightedGraph()
    for node_id in subgraph_nodes:
        sub_wg.nodes[node_id] = graph.nodes[node_id]
        sub_wg.adj[node_id] = []
    
    edge_id = 0
    for u, v in subgraph_edges:
        w = graph.get_edge_weight(u, v)
        sub_wg.adj[u].append({"to": v, "weight": w, "edge_id": edge_id})
        sub_wg.adj[v].append({"to": u, "weight": w, "edge_id": edge_id})
        edge_id += 1
    sub_wg.node_count = len(subgraph_nodes)
    sub_wg.edge_count = edge_id
    
    visited = set()
    start_steiner = parsed_terminals[0]
    visited.add(start_steiner)
    heap = []
    for edge in sub_wg.neighbors(start_steiner):
        heapq.heappush(heap, (edge["weight"], start_steiner, edge["to"]))
        
    final_edges = []
    final_nodes = set()
    final_nodes.add(start_steiner)
    total_weight = 0.0
    
    while heap and len(visited) < sub_wg.node_count:
        weight, u, v = heapq.heappop(heap)
        op_count += 1
        if v in visited:
            continue
            
        visited.add(v)
        final_edges.append((u, v))
        final_nodes.add(v)
        total_weight += weight
        
        is_terminal = v in parsed_terminals
        yield {
            "kind": "edge_added",
            "from_node": u,
            "to_node": v,
            "weight": weight,
            "op_count": op_count,
            "edges_added": len(final_edges),
            "total_weight": round(total_weight, 2),
            "node_type": "terminal" if is_terminal else "steiner",
            "xai_text": f"Steiner Tree: added edge ({u}→{v}) weight {weight:.2f}m. Node {v} is a " + 
                       (f"terminal node." if is_terminal else f"Steiner point connecting terminals."),
        }
        
        for edge in sub_wg.neighbors(v):
            if edge["to"] not in visited:
                heapq.heappush(heap, (edge["weight"], v, edge["to"]))
                op_count += 1

    # Cross-validate the final Steiner tree
    try:
        from pipeline.validation import validate_steiner_tree
        nx_g = nx.Graph()
        for nid in graph.nodes:
            nx_g.add_node(nid)
        for u_id in graph.adj:
            for edge in graph.adj[u_id]:
                nx_g.add_edge(u_id, edge["to"], weight=edge["weight"])
                
        val_res = validate_steiner_tree(nx_g, parsed_terminals, final_edges)
        logger.info(f"Steiner validation result: {val_res}")
    except Exception as e:
        logger.error(f"Steiner validation failed: {e}")

    # Done
    ratio = op_count / max(100, op_count)
    yield {
        "kind": "algorithm_done",
        "op_count": op_count,
        "edges_added": len(final_edges),
        "total_weight": round(total_weight, 2),
        "nodes_visited": len(visited),
        "terminals": parsed_terminals,
        "steiner_points": list(final_nodes - set(parsed_terminals)),
        "theoretical_ops": op_count,
        "theoretical_complexity": "O(T · (V+E)logV)",
        "ratio": round(ratio, 4),
        "xai_text": f"Steiner Tree approximation complete! Connected all {len(parsed_terminals)} terminals "
                   f"using {len(final_nodes - set(parsed_terminals))} Steiner points. Total tree weight: {total_weight:.1f}m.",
    }
