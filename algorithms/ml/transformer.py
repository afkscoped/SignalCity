from algorithms.centrality import pagerank


def attention_map(G, node_id=None):
    return {"scores": pagerank(G).get("scores", {})}
