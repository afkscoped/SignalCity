import networkx as nx
from ._nx_helpers import ensure_graph


def pagerank(G):
    try:
        G = ensure_graph(G)
        scores = nx.pagerank(G, weight="weight") if G.number_of_nodes() else {}
        top_nodes = [node for node, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)[:10]]
        ops = max(20 * G.number_of_edges(), 1)
        return {"scores": scores, "top_nodes": top_nodes, "ops": ops, "theoretical_ops": ops}
    except Exception as exc:
        return {"scores": {}, "top_nodes": [], "ops": 1, "theoretical_ops": 1, "error": str(exc)}
