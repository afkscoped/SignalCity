"""
scoring/efficiency_engine.py — Algorithm Efficiency Scoring Engine.
Grades every algorithm run on a S/A/B/C/D scale based on actual vs. theoretical operations.
"""
import math

# Theoretical complexity lookup: algo_name → lambda(V, E) → estimated ops
COMPLEXITY_MAP = {
    # Classic graph algorithms
    "prim": lambda V, E: E * math.log2(max(V, 2)),            # O(E log V)
    "kruskal": lambda V, E: E * math.log2(max(E, 2)) + V,     # O(E log E + V)
    "dijkstra": lambda V, E: (V + E) * math.log2(max(V, 2)),  # O((V+E) log V)
    "bellman_ford": lambda V, E: V * E,                         # O(VE)
    "edmonds_karp": lambda V, E: V * E * E,                    # O(VE²)
    "push_relabel": lambda V, E: V * V * E,                    # O(V²E)
    "contraction": lambda V, E: (V + E) * math.log2(max(V, 2)),

    # Community detection
    "louvain": lambda V, E: V * math.log2(max(V, 2)),          # O(V log V)
    "leiden": lambda V, E: V * math.log2(max(V, 2)),
    "label_propagation": lambda V, E: V + E,                   # O(V + E)
    "girvan_newman": lambda V, E: V * E * E,                   # O(VE²)

    # Centrality
    "pagerank": lambda V, E: 20 * (V + E),                     # O(k(V+E))
    "betweenness": lambda V, E: V * E,                         # O(VE)
    "k_median": lambda V, E: V * V,                            # O(V²)

    # Scheduling
    "fcfs": lambda V, E: V,
    "sjf": lambda V, E: V * math.log2(max(V, 2)),
    "round_robin": lambda V, E: V * 5,
    "priority": lambda V, E: V * math.log2(max(V, 2)),
    "edf": lambda V, E: V * math.log2(max(V, 2)),

    # Metaheuristics (population-based, fixed iterations)
    "gwo": lambda V, E: 5 * 6 * V * 3,
    "alo": lambda V, E: 5 * 5 * V * 3,
    "hho": lambda V, E: 5 * 5 * V * 3,
    "coa": lambda V, E: 5 * 5 * V,
    "woa": lambda V, E: 5 * 5 * 4,
    "run_optimizer": lambda V, E: 5 * 5 * 4,
    "ptbo": lambda V, E: 5 * 5 * 4,
    "mpa": lambda V, E: 5 * 5 * 4,
    "mfo": lambda V, E: 5 * 5 * V,
    "goa": lambda V, E: 5 * 5 * V,
    "ao": lambda V, E: 5 * 5 * V,
    "do": lambda V, E: 5 * 5 * V,
    "ssa": lambda V, E: 5 * 5 * 3,
    "sma": lambda V, E: 5 * 5 * 3,
    "aoa": lambda V, E: 5 * 5 * 3,
    "gto": lambda V, E: 5 * 5 * 3,

    # Advanced
    "raft_consensus": lambda V, E: V * 5,
    "kan_network": lambda V, E: V * V,
}

GRADE_THRESHOLDS = [
    (95, "S"), (80, "A"), (65, "B"), (50, "C")
]

GRADE_REWARDS = {
    "S": {"xp": 500, "coins": 300, "rp": 50},
    "A": {"xp": 300, "coins": 200, "rp": 35},
    "B": {"xp": 200, "coins": 120, "rp": 20},
    "C": {"xp": 100, "coins": 60, "rp": 10},
    "D": {"xp": 50, "coins": 20, "rp": 5},
}

ALGO_TIPS = {
    "prim": [
        "Start from the node with highest population weight for better early coverage.",
        "Prim's works best on dense graphs — sparse cities may benefit from Kruskal's instead.",
    ],
    "dijkstra": [
        "Using a Fibonacci heap can reduce complexity to O(V log V + E).",
        "Pre-compute contraction hierarchies for repeated shortest-path queries.",
    ],
    "edmonds_karp": [
        "BFS guarantees shortest augmenting paths — this bounds iterations to O(VE).",
        "Consider Push-Relabel for denser networks — it has better practical performance.",
    ],
    "kruskal": [
        "Union-Find with path compression keeps amortized cost nearly O(1) per operation.",
        "Pre-sorting edges dominates runtime — consider radix sort for integer weights.",
    ],
    "leiden": [
        "Leiden improves on Louvain by guaranteeing well-connected communities.",
        "Lower resolution parameter → fewer, larger communities.",
    ],
    "pagerank": [
        "Convergence typically happens in 15-25 iterations for road networks.",
        "Damping factor 0.85 is standard — lower values spread rank more evenly.",
    ],
}

DEFAULT_TIPS = [
    "Analyze the complexity class to understand scaling behavior.",
    "Compare your actual operations vs. the theoretical bound for insights.",
]


def grade_algorithm_run(
    algo_name: str,
    node_count: int,
    edge_count: int,
    actual_ops: int,
    wall_ms: float = 0.0,
) -> dict:
    """
    Grade an algorithm run based on actual vs. theoretical operations.

    Returns:
        {
            "grade": "S" | "A" | "B" | "C" | "D",
            "efficiency_score": float (0-100),
            "theoretical_ops": int,
            "efficiency_ratio": float,
            "xp_earned": int,
            "coins_earned": int,
            "rp_earned": int,
            "tips": list[str],
            "comparison_text": str,
        }
    """
    V = max(node_count, 1)
    E = max(edge_count, 1)

    # Get theoretical bound
    complexity_fn = COMPLEXITY_MAP.get(algo_name)
    if complexity_fn:
        theoretical_ops = max(int(complexity_fn(V, E)), 1)
    else:
        # Unknown algorithm — use V*E as a generous fallback
        theoretical_ops = max(V * E, 1)

    # Compute ratio and score
    ratio = actual_ops / theoretical_ops if theoretical_ops > 0 else 1.0
    efficiency_score = max(0, min(100, 100 * (1 - (ratio - 1) / 2)))

    # Assign grade
    grade = "D"
    for threshold, g in GRADE_THRESHOLDS:
        if efficiency_score >= threshold:
            grade = g
            break

    # Get rewards
    rewards = GRADE_REWARDS[grade]

    # Get tips
    tips = ALGO_TIPS.get(algo_name, DEFAULT_TIPS)[:2]

    # Comparison text
    if ratio <= 1.0:
        comparison_text = f"Outstanding! Your run used {actual_ops} ops, {(1-ratio)*100:.0f}% fewer than the theoretical bound of {theoretical_ops}."
    elif ratio <= 1.5:
        comparison_text = f"Good work! {actual_ops} ops vs. theoretical {theoretical_ops} — only {(ratio-1)*100:.0f}% overhead."
    else:
        comparison_text = f"Room to improve: {actual_ops} ops vs. theoretical {theoretical_ops}. Ratio: {ratio:.2f}x."

    return {
        "grade": grade,
        "efficiency_score": round(efficiency_score, 1),
        "theoretical_ops": theoretical_ops,
        "actual_ops": actual_ops,
        "efficiency_ratio": round(ratio, 3),
        "xp_earned": rewards["xp"],
        "coins_earned": rewards["coins"],
        "rp_earned": rewards["rp"],
        "tips": tips,
        "comparison_text": comparison_text,
        "wall_ms": round(wall_ms, 1),
    }
