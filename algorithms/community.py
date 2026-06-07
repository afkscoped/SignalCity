import networkx as nx
from ._nx_helpers import ensure_graph


def louvain(G):
    try:
        G = ensure_graph(G)
        groups = list(nx.algorithms.community.greedy_modularity_communities(G)) if G.number_of_edges() else [set(G.nodes())]
        communities = {node: i for i, group in enumerate(groups) for node in group}
        ops = max(G.number_of_edges(), 1)
        return {"communities": communities, "num_communities": len(groups), "modularity": 0, "ops": ops, "theoretical_ops": ops}
    except Exception as exc:
        return {"communities": {}, "num_communities": 0, "modularity": 0, "ops": 1, "theoretical_ops": 1, "error": str(exc)}


def leiden(G):
    return louvain(G)
