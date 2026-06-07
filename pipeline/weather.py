"""
pipeline/weather.py — Weather event simulation for Signal City.
Supports live OpenWeatherMap API or deterministic mock scenarios.
"""

import random
import time
import math
import os

WEATHER_MOCK_SCENARIOS = {
    "STORM": {
        "description": "Severe thunderstorm",
        "effect_weight_multiplier": 2.0,
        "effect_capacity_multiplier": 0.5,
        "color": "#E24B4A",
        "particle_type": "lightning",
        "n_edges_affected": 15,
        "icon": "⛈️",
        "damage": 15,
        "lore": "The Algorithm Gods are displeased. Lightning strikes fracture your network.",
    },
    "RAIN": {
        "description": "Heavy rainfall",
        "effect_weight_multiplier": 1.5,
        "effect_capacity_multiplier": 0.75,
        "color": "#378ADD",
        "particle_type": "rain",
        "n_edges_affected": 25,
        "icon": "🌧️",
        "damage": 8,
        "lore": "Rain floods the lower districts. Travel times increase across arterial roads.",
    },
    "FOG": {
        "description": "Dense fog",
        "effect_weight_multiplier": 1.2,
        "effect_capacity_multiplier": 0.9,
        "color": "#888780",
        "particle_type": "fog",
        "n_edges_affected": 40,
        "icon": "🌫️",
        "damage": 4,
        "lore": "Fog blankets the city. Heuristic-based algorithms lose their advantage.",
    },
    "CLEAR": {
        "description": "Clear skies",
        "effect_weight_multiplier": 1.0,
        "effect_capacity_multiplier": 1.0,
        "color": "#1D9E75",
        "particle_type": "none",
        "n_edges_affected": 0,
        "icon": "☀️",
        "damage": 0,
        "lore": "Perfect conditions. Your algorithms perform at peak efficiency.",
    },
    "BLIZZARD": {
        "description": "Arctic blizzard",
        "effect_weight_multiplier": 3.0,
        "effect_capacity_multiplier": 0.3,
        "color": "#A5B4C8",
        "particle_type": "snow",
        "n_edges_affected": 30,
        "icon": "🌨️",
        "damage": 20,
        "lore": "A blizzard from the Northern Wastes. Only the most robust paths survive.",
    },
}


def get_weather_event(lat: float, lon: float, use_live: bool = False) -> dict:
    """
    Get weather event for given coordinates.
    If use_live=True AND OWM_API_KEY env var is set: call OpenWeatherMap API.
    Otherwise: deterministically pick based on hash(lat+lon+floor(time/3600))
    so weather changes hourly but is reproducible within an hour.
    """
    if use_live and os.environ.get("OWM_API_KEY"):
        try:
            return _fetch_live_weather(lat, lon)
        except Exception:
            pass

    # Deterministic mock: hash lat+lon+hour to pick scenario
    hour_seed = int(math.floor(time.time() / 3600))
    combined = hash((round(lat, 4), round(lon, 4), hour_seed))
    scenarios = list(WEATHER_MOCK_SCENARIOS.keys())
    # Weight CLEAR higher so storms aren't constant
    weights = [0.15, 0.25, 0.20, 0.30, 0.10]
    rng = random.Random(combined)
    chosen = rng.choices(scenarios, weights=weights, k=1)[0]
    scenario = WEATHER_MOCK_SCENARIOS[chosen].copy()
    scenario["type"] = chosen
    scenario["source"] = "simulated"
    scenario["timestamp"] = time.time()
    return scenario


def _fetch_live_weather(lat: float, lon: float) -> dict:
    """Fetch live weather from OpenWeatherMap (optional)."""
    import httpx

    api_key = os.environ["OWM_API_KEY"]
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}"
    resp = httpx.get(url, timeout=10)
    data = resp.json()
    weather_id = data.get("weather", [{}])[0].get("id", 800)

    if weather_id < 300:
        wtype = "STORM"
    elif weather_id < 600:
        wtype = "RAIN"
    elif weather_id < 700:
        wtype = "BLIZZARD"
    elif weather_id < 800:
        wtype = "FOG"
    else:
        wtype = "CLEAR"

    scenario = WEATHER_MOCK_SCENARIOS[wtype].copy()
    scenario["type"] = wtype
    scenario["source"] = "live"
    scenario["timestamp"] = time.time()
    scenario["raw"] = data
    return scenario


def select_affected_edges(graph_edges: list, n: int, seed: int = None) -> list:
    """
    Select n edges to be affected by weather.
    Prefers edges near city center (lower x,y magnitude).
    Returns list of edge dicts {u, v, original_weight, original_capacity}.
    """
    if n == 0 or not graph_edges:
        return []

    rng = random.Random(seed if seed is not None else int(time.time()))

    # Calculate distance from centroid for each edge
    scored = []
    for e in graph_edges:
        # Edges closer to center (0,0) are more likely affected
        mid_x = 0
        mid_y = 0
        if "from_x" in e and "from_y" in e and "to_x" in e and "to_y" in e:
            mid_x = (e["from_x"] + e["to_x"]) / 2
            mid_y = (e["from_y"] + e["to_y"]) / 2
        dist = math.sqrt(mid_x ** 2 + mid_y ** 2) + 1.0
        weight = 1.0 / dist  # inverse distance = higher weight for center
        scored.append((e, weight))

    total_weight = sum(w for _, w in scored)
    if total_weight == 0:
        selected = rng.sample(graph_edges, min(n, len(graph_edges)))
    else:
        probabilities = [w / total_weight for _, w in scored]
        n = min(n, len(graph_edges))
        selected_indices = set()
        attempts = 0
        while len(selected_indices) < n and attempts < n * 10:
            r = rng.random()
            cumulative = 0
            for i, p in enumerate(probabilities):
                cumulative += p
                if r <= cumulative:
                    selected_indices.add(i)
                    break
            attempts += 1
        selected = [graph_edges[i] for i in selected_indices]

    result = []
    for e in selected:
        result.append({
            "u": e.get("u", e.get("from", 0)),
            "v": e.get("v", e.get("to", 0)),
            "original_weight": e.get("weight", 1.0),
            "original_capacity": e.get("capacity", 800),
        })
    return result


class WeatherEngine:
    """Offline-safe weather wrapper used by the city endpoints."""

    def __init__(self, use_live: bool | None = None):
        self.use_live = bool(os.environ.get("OWM_API_KEY")) if use_live is None else use_live

    async def get_weather(self, lat: float, lon: float) -> dict:
        return get_weather_event(lat, lon, use_live=self.use_live)

    def apply_to_graph(self, graph_data: dict, weather: dict) -> dict:
        edges = graph_data.get("edges", [])
        affected = select_affected_edges(
            edges,
            int(weather.get("n_edges_affected", 0)),
            seed=int(weather.get("timestamp", time.time())),
        )
        affected_pairs = {(edge["u"], edge["v"]) for edge in affected}
        weight_mult = weather.get("effect_weight_multiplier", 1.0)
        cap_mult = weather.get("effect_capacity_multiplier", 1.0)

        for edge in edges:
            pair = (edge.get("u", edge.get("source")), edge.get("v", edge.get("target")))
            reverse_pair = (pair[1], pair[0])
            edge["weighted"] = edge.get("weight", 1.0)
            edge["capacity_adjusted"] = edge.get("capacity", 1800)
            if pair in affected_pairs or reverse_pair in affected_pairs:
                edge["weather_affected"] = True
                edge["weighted"] = round(edge.get("weight", 1.0) * weight_mult, 2)
                edge["capacity_adjusted"] = int(edge.get("capacity", 1800) * cap_mult)

        graph_data["weather"] = weather
        graph_data["affected_edges"] = affected
        return graph_data
