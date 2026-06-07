import math
import networkx as nx


def ensure_graph(graph):
    if isinstance(graph, nx.Graph):
        return graph
    g = nx.Graph()
    for node in graph.get("nodes", []):
        g.add_node(node["id"], **node)
    for edge in graph.get("edges", []):
        u = edge.get("source", edge.get("u"))
        v = edge.get("target", edge.get("v"))
        if u and v:
            g.add_edge(u, v, **edge, weight=edge.get("weight", 1))
    return g


def theoretical_nlogn(g):
    return int((g.number_of_nodes() + g.number_of_edges()) * math.log2(max(g.number_of_nodes(), 2)))
