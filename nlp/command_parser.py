"""
nlp/command_parser.py — Natural Language → Algorithm command parser.
Uses Anthropic Claude API if available, otherwise falls back to keyword matching.
"""
import os
import re
from typing import Dict, Optional

try:
    import anthropic
except ImportError:
    anthropic = None

NLP_KEYWORD_MAP = {
    # Prim
    "power grid": "prim", "connect everything": "prim", "minimum spanning": "prim",
    "build grid": "prim", "prim": "prim", "mst": "prim", "spanning tree": "prim",
    "electrical grid": "prim", "connect all": "prim",
    # Kruskal
    "kruskal": "kruskal", "cheapest roads": "kruskal", "sort edges": "kruskal",
    # Dijkstra
    "shortest path": "dijkstra", "fastest route": "dijkstra", "navigate": "dijkstra",
    "route from": "dijkstra", "dijkstra": "dijkstra", "find path": "dijkstra",
    "get me to": "dijkstra", "directions": "dijkstra",
    # Bellman-Ford
    "negative weight": "bellman_ford", "bellman": "bellman_ford",
    # Max Flow
    "max flow": "edmonds_karp", "traffic flow": "edmonds_karp", "maximize flow": "edmonds_karp",
    "edmonds": "edmonds_karp", "ford fulkerson": "edmonds_karp", "flow network": "edmonds_karp",
    "vehicle throughput": "edmonds_karp",
    # Push-Relabel
    "push relabel": "push_relabel",
    # Community
    "community": "leiden", "zone the city": "leiden", "districts": "leiden",
    "neighborhoods": "leiden", "leiden": "leiden", "louvain": "louvain",
    "cluster": "leiden",
    # PageRank
    "important intersections": "pagerank", "key nodes": "pagerank", "pagerank": "pagerank",
    "influence": "pagerank", "ranking": "pagerank",
    # Scheduling
    "schedule": "fcfs", "jobs": "fcfs", "task order": "sjf",
    "round robin": "round_robin", "priority queue": "priority",
    "deadline": "edf",
    # Metaheuristics
    "fire station": "gwo", "grey wolf": "gwo", "wolf": "gwo",
    "antenna": "mfo", "signal coverage": "mfo", "wireless": "mfo",
    "traffic light": "woa", "signal timing": "woa", "whale": "woa",
    "power line": "ssa", "utility": "ssa", "backbone": "ssa",
    # Contraction
    "fast routing": "contraction", "contraction": "contraction", "hierarchy": "contraction",
    # Hospital
    "hospital": "k_median", "emergency": "k_median", "medical": "k_median",
}

ALGO_DESCRIPTIONS = {
    "prim": "Prim's Minimum Spanning Tree — builds optimal power grid connections",
    "kruskal": "Kruskal's MST — sorts all roads by cost, adds cheapest non-cyclic ones",
    "dijkstra": "Dijkstra's Shortest Path — finds the fastest route between two points",
    "bellman_ford": "Bellman-Ford — handles negative weights for cost analysis",
    "edmonds_karp": "Edmonds-Karp Max Flow — maximizes traffic throughput in the network",
    "push_relabel": "Push-Relabel — alternative max flow using preflow techniques",
    "leiden": "Leiden Community Detection — zones the city into balanced districts",
    "louvain": "Louvain Modularity — greedy community detection for district planning",
    "pagerank": "PageRank Centrality — identifies the most influential intersections",
    "contraction": "Contraction Hierarchies — preprocesses for instant shortest-path queries",
    "k_median": "k-Median Clustering — optimally places hospitals/emergency services",
    "gwo": "Grey Wolf Optimizer — fire station placement using wolf pack hunting",
    "woa": "Whale Optimization — traffic signal timing via bubble-net strategy",
    "mfo": "Moth-Flame Optimization — cellular antenna placement",
    "ssa": "Salp Swarm Algorithm — utility power line grid balancing",
    "fcfs": "First Come First Served — basic job scheduling",
    "sjf": "Shortest Job First — prioritizes quick tasks",
    "round_robin": "Round Robin — fair time-sliced scheduling",
    "priority": "Priority Scheduling — urgency-based task ordering",
    "edf": "Earliest Deadline First — deadline-aware scheduling",
}


def _keyword_parse(text: str) -> Optional[Dict]:
    """Rule-based keyword matching fallback."""
    text_lower = text.lower().strip()

    for keyword, algo in NLP_KEYWORD_MAP.items():
        if keyword in text_lower:
            return {
                "intent": "run_algorithm",
                "algorithm": algo,
                "params": {},
                "explanation": ALGO_DESCRIPTIONS.get(algo, f"Running {algo}"),
                "confidence": 0.7,
                "source": "keyword",
            }
    return None


async def parse_nlp_command(text: str, context: dict = None) -> Dict:
    """
    Parse a natural language command into an algorithm action.

    Args:
        text: User's natural language input (e.g., "connect the power grid")
        context: Optional game context (current city, loaded graph, etc.)

    Returns:
        {
            "intent": "run_algorithm" | "help" | "unknown",
            "algorithm": str or None,
            "params": dict,
            "explanation": str,
            "confidence": float 0-1,
            "source": "claude" | "keyword",
        }
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")

    # Try Claude API first
    if api_key and anthropic:
        try:
            client = anthropic.Anthropic(api_key=api_key)
            prompt = f"""You are Signal City's command parser. The player typed: "{text}"

Available algorithms: {', '.join(ALGO_DESCRIPTIONS.keys())}

Respond ONLY with a JSON object:
{{"intent": "run_algorithm", "algorithm": "<algo_name>", "params": {{}}, "explanation": "<one-line description of what this does>"}}

If you can't match to an algorithm, use:
{{"intent": "unknown", "algorithm": null, "params": {{}}, "explanation": "I didn't understand that command."}}"""

            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            import json
            text_response = response.content[0].text.strip()
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', text_response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                result["confidence"] = 0.95
                result["source"] = "claude"
                return result
        except Exception as e:
            print(f"[NLP] Claude API error: {e}, falling back to keywords")

    # Keyword fallback
    result = _keyword_parse(text)
    if result:
        return result

    return {
        "intent": "unknown",
        "algorithm": None,
        "params": {},
        "explanation": "I couldn't understand that command. Try something like 'build the power grid' or 'find shortest path'.",
        "confidence": 0.0,
        "source": "keyword",
    }
