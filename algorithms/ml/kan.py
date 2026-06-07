from algorithms._nx_helpers import ensure_graph


def predict_congestion(G):
    G = ensure_graph(G)
    return {"predictions": {f"{u}-{v}": min(1.0, data.get("weight", 1) / 5000) for u, v, data in G.edges(data=True)}}
