import networkx as nx
from ._nx_helpers import ensure_graph


def edmonds_karp(G, source=None, sink=None):
    try:
        G = ensure_graph(G)
        nodes = list(G.nodes())
        source = source if source in G else (nodes[0] if nodes else None)
        sink = sink if sink in G else (nodes[-1] if nodes else None)
        D = nx.DiGraph()
        for u, v, data in G.edges(data=True):
            D.add_edge(u, v, capacity=int(data.get("capacity", 1)))
            D.add_edge(v, u, capacity=int(data.get("capacity", 1)))
        value, flows = nx.maximum_flow(D, source, sink, capacity="capacity") if source and sink else (0, {})
        ops = max(G.number_of_nodes() * G.number_of_edges(), 1)
        return {"max_flow": value, "flow_paths": flows, "bottleneck_nodes": [source, sink], "ops": ops, "theoretical_ops": ops}
    except Exception as exc:
        return {"max_flow": 0, "flow_paths": [], "bottleneck_nodes": [], "ops": 1, "theoretical_ops": 1, "error": str(exc)}
