import json
import os
import re

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/nlp", tags=["nlp"])


class ParseRequest(BaseModel):
    command: str | None = None
    text: str | None = None


def _regex_parse(text: str) -> dict:
    lowered = text.lower()
    patterns = [
        (r"power|grid|connect|mst|minimum|prim", "prim", "Build a minimum spanning tree for the grid."),
        (r"kruskal|spanning forest", "kruskal", "Build Kruskal's minimum spanning forest."),
        (r"shortest|route|path|dijkstra|travel|distance", "dijkstra", "Find the shortest route."),
        (r"flow|traffic|max|throughput|edmonds|karp", "edmonds_karp", "Maximize flow through the network."),
        (r"zone|district|community|cluster|leiden|louvain", "leiden", "Detect city communities."),
        (r"hospital|facility|median|placement|k-median|kmedian", "k_median", "Place facilities efficiently."),
        (r"rank|central|important|hub|influence|pagerank", "pagerank", "Find central intersections."),
        (r"contraction|shortcut|hierarchy", "contraction", "Compute contraction hierarchies for routing."),
    ]
    for pattern, algorithm, explanation in patterns:
        if re.search(pattern, lowered):
            return {
                "intent": "run_algorithm",
                "algorithm": algorithm,
                "params": {},
                "source": "regex",
                "confidence": 0.7,
                "explanation": explanation,
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
            "Map this game command to one algorithm id from: prim, kruskal, dijkstra, "
            "edmonds_karp, leiden, pagerank, k_median. Return compact JSON with "
            "intent, algorithm, confidence, explanation. Command: "
            + text
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
