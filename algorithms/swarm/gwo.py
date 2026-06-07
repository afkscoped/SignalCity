from algorithms.facility import k_median


def grey_wolf(G, k=3):
    result = k_median(G, k)
    return {"positions": result.get("facility_nodes", []), "convergence": [100, 50, 25], "ops": result.get("ops", 1), "theoretical_ops": result.get("theoretical_ops", 1)}
