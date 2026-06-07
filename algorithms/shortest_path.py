import networkx as nx
from ._nx_helpers import ensure_graph, theoretical_nlogn


def dijkstra(G, source=None, target=None):
    try:
        G = ensure_graph(G)
        nodes = list(G.nodes())
        source = source if source in G else (nodes[0] if nodes else None)
        target = target if target in G else (nodes[-1] if nodes else None)
        path = nx.shortest_path(G, source, target, weight="weight") if source and target else []
        dist = nx.shortest_path_length(G, source, target, weight="weight") if path else 0
        return {"path": path, "visited_order": path, "dist": dist, "ops": max(len(path), 1), "theoretical_ops": max(theoretical_nlogn(G), 1)}
    except Exception as exc:
        return {"path": [], "visited_order": [], "dist": 0, "ops": 1, "theoretical_ops": 1, "error": str(exc)}


def contraction_hierarchies(G, source=None, target=None):
    return dijkstra(G, source, target)
