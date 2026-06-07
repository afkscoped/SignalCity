import networkx as nx
from ._nx_helpers import ensure_graph, theoretical_nlogn


def prim(G, source=None):
    try:
        G = ensure_graph(G)
        tree = nx.minimum_spanning_tree(G, algorithm="prim", weight="weight")
        return {"mst_edges": list(tree.edges()), "visited_order": list(tree.nodes()), "ops": max(G.number_of_edges(), 1), "theoretical_ops": max(theoretical_nlogn(G), 1)}
    except Exception as exc:
        return {"mst_edges": [], "visited_order": [], "ops": 1, "theoretical_ops": 1, "error": str(exc)}


def kruskal(G):
    try:
        G = ensure_graph(G)
        tree = nx.minimum_spanning_tree(G, algorithm="kruskal", weight="weight")
        return {"mst_edges": list(tree.edges()), "ops": max(G.number_of_edges(), 1), "theoretical_ops": max(theoretical_nlogn(G), 1)}
    except Exception as exc:
        return {"mst_edges": [], "ops": 1, "theoretical_ops": 1, "error": str(exc)}
