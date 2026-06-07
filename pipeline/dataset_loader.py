import json
import logging
import math
import os
from typing import Dict, List

logger = logging.getLogger(__name__)

OSM_AMENITY_TYPES = [
    "hospital",
    "school",
    "police",
    "fire_station",
    "university",
    "park",
    "bus_station",
    "pharmacy",
    "bank",
]


async def fetch_city_pois(city_key: str, city_info: dict) -> Dict[str, List]:
    cache_path = os.path.join("data", "pois", f"{city_key}.json")
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)

    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    pois = {amenity: [] for amenity in OSM_AMENITY_TYPES}
    lat, lon = city_info["lat"], city_info["lon"]
    radius = 15000
    overpass_url = "https://overpass-api.de/api/interpreter"

    for amenity in ["hospital", "police", "fire_station", "university", "school"]:
        query = f"""
        [out:json][timeout:10];
        node["amenity"="{amenity}"](around:{radius},{lat},{lon});
        out body 20;
        """
        try:
            import requests

            resp = requests.post(overpass_url, data={"data": query}, timeout=12)
            if resp.status_code != 200:
                continue
            data = resp.json()
            for el in data.get("elements", [])[:20]:
                pois[amenity].append({
                    "lat": el.get("lat", lat),
                    "lon": el.get("lon", lon),
                    "name": el.get("tags", {}).get("name", amenity.title()),
                    "amenity": amenity,
                })
        except Exception as exc:
            logger.debug("POI fetch failed for %s in %s: %s", amenity, city_key, exc)

    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(pois, f)
    except Exception:
        pass
    return pois


def get_india_city_stats() -> Dict[str, Dict]:
    return {
        "bengaluru": {"population_millions": 12.3, "area_km2": 741, "avg_income_idx": 0.78},
        "mumbai": {"population_millions": 20.7, "area_km2": 603, "avg_income_idx": 0.82},
        "delhi": {"population_millions": 32.9, "area_km2": 1484, "avg_income_idx": 0.76},
        "chennai": {"population_millions": 10.1, "area_km2": 426, "avg_income_idx": 0.74},
        "hyderabad": {"population_millions": 10.5, "area_km2": 650, "avg_income_idx": 0.72},
        "pune": {"population_millions": 6.6, "area_km2": 331, "avg_income_idx": 0.75},
        "kolkata": {"population_millions": 14.8, "area_km2": 1886, "avg_income_idx": 0.68},
        "jaipur": {"population_millions": 3.9, "area_km2": 485, "avg_income_idx": 0.65},
        "ahmedabad": {"population_millions": 8.0, "area_km2": 464, "avg_income_idx": 0.71},
        "surat": {"population_millions": 7.3, "area_km2": 327, "avg_income_idx": 0.70},
    }


async def enrich_graph_with_pois(graph_data: dict, city_key: str) -> dict:
    from pipeline.city_loader import CITY_REGISTRY

    city_info = CITY_REGISTRY.get(city_key)
    if not city_info:
        return graph_data

    pois = await fetch_city_pois(city_key, city_info)
    nodes = graph_data.get("nodes", [])
    if not nodes:
        return graph_data

    def haversine_dist(lat1, lon1, lat2, lon2):
        radius_km = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        )
        return radius_km * 2 * math.asin(math.sqrt(a)) * 1000

    node_amenities = {}
    for amenity_type, poi_list in pois.items():
        for poi in poi_list:
            if not poi.get("lat") or not poi.get("lon"):
                continue
            nearest_id = None
            nearest_dist = float("inf")
            for node in nodes:
                if not node.get("lat"):
                    continue
                dist = haversine_dist(poi["lat"], poi["lon"], node["lat"], node["lon"])
                if dist < nearest_dist:
                    nearest_dist = dist
                    nearest_id = node["id"]
            if nearest_id and nearest_dist < 1000:
                node_amenities.setdefault(nearest_id, []).append({
                    "type": amenity_type,
                    "name": poi["name"],
                    "dist_m": round(nearest_dist),
                })

    for node in nodes:
        node["amenities"] = node_amenities.get(node["id"], [])

    graph_data["has_poi_data"] = True
    graph_data["poi_count"] = sum(len(v) for v in pois.values())
    return graph_data
