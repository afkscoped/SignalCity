import json
import os
import re

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/nlp", tags=["nlp"])


class ParseRequest(BaseModel):
    command: str | None = None
    text: str | None = None


# ── Place-name extraction patterns ──────────────────────────────────────
# Extracts source and destination from natural language routing commands.

_ROUTE_PATTERNS = [
    # "shortest path from HSR Layout to Koramangala"
    re.compile(
        r"(?:shortest|fastest|route|path|distance|navigate|direction|travel|go|drive|walk|ride)\s+"
        r"(?:from\s+)?(.+?)\s+(?:to|towards?|->|→)\s+(.+?)(?:\s+(?:using|with|via|by)\s+.+)?$",
        re.IGNORECASE,
    ),
    # "from HSR Layout to Koramangala"
    re.compile(
        r"from\s+(.+?)\s+(?:to|towards?|->|→)\s+(.+?)(?:\s+(?:using|with|via|by)\s+.+)?$",
        re.IGNORECASE,
    ),
    # "route between HSR Layout and Koramangala"
    re.compile(
        r"(?:route|path|distance|travel)\s+between\s+(.+?)\s+(?:and|&)\s+(.+?)(?:\s+.+)?$",
        re.IGNORECASE,
    ),
    # "HSR Layout to Koramangala shortest route"
    re.compile(
        r"^(.+?)\s+(?:to|towards?|->|→)\s+(.+?)(?:\s+(?:shortest|fastest|route|path|distance).*)?$",
        re.IGNORECASE,
    ),
]


def _extract_places(text: str) -> tuple[str | None, str | None]:
    """
    Extract source and destination place names from a routing command.
    Returns (source_name, dest_name) or (None, None) if not a routing query.
    """
    cleaned = text.strip()
    for pattern in _ROUTE_PATTERNS:
        m = pattern.search(cleaned)
        if m:
            source = m.group(1).strip().strip("'\"")
            dest = m.group(2).strip().strip("'\"").rstrip("?.!")
            # Sanity: skip if either is just an algorithm name
            algo_names = {"dijkstra", "prim", "kruskal", "bfs", "dfs", "contraction"}
            if source.lower() in algo_names or dest.lower() in algo_names:
                continue
            if len(source) > 2 and len(dest) > 2:
                return source, dest
    return None, None


def _regex_parse(text: str) -> dict:
    lowered = text.lower()

    # First, try to extract places for routing queries
    source_name, dest_name = _extract_places(text)
    params = {}
    if source_name and dest_name:
        params["source_name"] = source_name
        params["dest_name"] = dest_name

    k_match = re.search(r"\b(?:k|choose|place|select|site)\s*=?\s*(\d{1,2})\b", lowered)
    if k_match:
        params["k"] = max(1, min(20, int(k_match.group(1))))

    radius_match = re.search(r"\b(\d+(?:\.\d+)?)\s*km\b", lowered)
    if radius_match:
        params["scope"] = {
            "mode": "radius" if not (source_name and dest_name) else "selection",
            "radius_km": float(radius_match.group(1)),
            "max_nodes": 1800,
        }
    elif re.search(r"\b(near|around|within|corridor|local|selected|ward|area)\b", lowered):
        params["scope"] = {"mode": "selection", "radius_km": 5.0, "max_nodes": 1800}
    elif re.search(r"\b(whole city|entire city|full city|all bengaluru|city-wide|citywide)\b", lowered):
        params["scope"] = {"mode": "all", "max_nodes": 9000}

    patterns = [
        (r"kruskal|spanning forest", "kruskal", "Build Kruskal's minimum spanning forest."),
        (r"power|grid|connect|mst|minimum|prim", "prim", "Build a minimum spanning tree for the selected infrastructure scope."),
        (r"kruskal|spanning forest", "kruskal", "Build Kruskal's minimum spanning forest."),
        (r"shortest|route|path|dijkstra|travel|distance|navigate|direction", "dijkstra", "Find the shortest route."),
        (r"\ba\*|astar|a-star", "astar", "Run A* goal-directed routing."),
        (r"risk|safer|crash|blackspot|accident", "risk_aware", "Run crash-risk-aware routing."),
        (r"flood|monsoon|blocked|closure|reroute", "flood_aware", "Run flood-aware rerouting."),
        (r"flow|traffic|max|throughput|edmonds|karp", "edmonds_karp", "Maximize flow through the network."),
        (r"zone|district|community|cluster|leiden|louvain", "leiden", "Detect city communities."),
        (r"hospital|facility|median|placement|k-median|kmedian", "k_median", "Place facilities efficiently."),
        (r"rank|central|important|hub|influence|pagerank", "pagerank", "Find central intersections."),
        (r"contraction|shortcut|hierarchy", "contraction", "Compute contraction hierarchies for routing."),
        (r"wolf|gwo", "gwo", "Run Grey Wolf Optimizer for facility placement."),
        (r"hawk|hho", "hho", "Run Harris Hawks for facility placement."),
        (r"ant.?lion|alo", "alo", "Run Ant Lion Optimizer."),
        (r"whale|woa", "woa", "Run Whale Optimization for signal timing."),
        (r"schedule|edf|deadline", "edf", "Schedule jobs by earliest deadline."),
        (r"sjf|shortest job", "sjf", "Schedule by shortest job first."),
        (r"fcfs|first come|first.serve", "fcfs", "First-come first-served scheduling."),
        (r"round.robin|rr|time.slice", "round_robin", "Round robin scheduling."),
    ]
    for pattern, algorithm, explanation in patterns:
        if re.search(pattern, lowered):
            result = {
                "intent": "run_algorithm",
                "algorithm": algorithm,
                "params": dict(params),
                "source": "regex",
                "confidence": 0.7,
                "explanation": explanation,
            }
            # Attach extracted place names if found
            if source_name and dest_name:
                result["confidence"] = 0.85
                result["explanation"] = (
                    f"{explanation} Source: {source_name}; destination: {dest_name}."
                )
            if "scope" in params:
                result["confidence"] = max(result["confidence"], 0.82)
                result["explanation"] += f" Scope: {params['scope']['mode']}."
            if "k" in params:
                result["explanation"] += f" k={params['k']}."
            return result

    # If we found places but no algorithm keyword, default to dijkstra
    if source_name and dest_name:
        return {
            "intent": "run_algorithm",
            "algorithm": "dijkstra",
            "params": params,
            "source": "regex",
            "confidence": 0.8,
            "explanation": f"Find the shortest route from {source_name} to {dest_name}.",
        }

    return {
        "intent": "unknown",
        "algorithm": "prim",
        "params": {},
        "source": "regex",
        "confidence": 0.35,
        "explanation": "I defaulted to Prim because no strong keyword matched.",
    }


async def _groq_parse(text: str) -> dict:
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return _regex_parse(text)
    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        prompt = (
            "You are a command parser for a city simulation game. "
            "Parse this command and return JSON with these fields:\n"
            "- intent: 'run_algorithm' or 'route'\n"
            "- algorithm: one of (prim, kruskal, dijkstra, contraction, edmonds_karp, "
            "leiden, pagerank, k_median, gwo, hho, alo, woa, edf, sjf, fcfs, round_robin)\n"
            "- params: object with optional source_name and dest_name if the user "
            "mentions specific locations\n"
            "- confidence: 0-1 float\n"
            "- explanation: brief description\n\n"
            "If the user says something like 'shortest path from HSR Layout to Koramangala', "
            "extract source_name='HSR Layout' and dest_name='Koramangala' and set algorithm='dijkstra'.\n\n"
            "Command: " + text
        )
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        parsed = json.loads(response.choices[0].message.content)
        parsed["source"] = "groq"
        return parsed
    except Exception:
        return _regex_parse(text)


@router.post("/parse")
async def parse(payload: ParseRequest):
    text = (payload.command or payload.text or "").strip()
    return await _groq_parse(text)
