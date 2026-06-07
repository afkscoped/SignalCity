import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pipeline.city_loader import CITY_REGISTRY, get_city_list, load_city_graph, slugify_city
from pipeline.dataset_loader import enrich_graph_with_pois
from pipeline.weather import WeatherEngine

router = APIRouter(prefix="/api", tags=["city"])
logger = logging.getLogger(__name__)
weather_engine = WeatherEngine()
CITY_CACHE: dict[str, dict] = {}


class CityLoadRequest(BaseModel):
    city: str | None = None
    city_id: str | None = None
    apply_weather: bool = True
    include_pois: bool = True


def get_cached_city(city_id: str) -> dict | None:
    return CITY_CACHE.get(slugify_city(city_id))


@router.get("/cities")
async def cities():
    cities_list = get_city_list()
    return {"cities": cities_list}


@router.get("/cities/legacy")
async def cities_legacy():
    return {
        c["key"]: {"name": c["name"], "lat": c["lat"], "lon": c["lon"], "icon": ""}
        for c in get_city_list()
    }


@router.post("/load-city")
async def load_city(payload: CityLoadRequest):
    city_key = slugify_city(payload.city or payload.city_id or "bengaluru")
    try:
        graph_data = await load_city_graph(city_key)
        if payload.include_pois:
            graph_data = await enrich_graph_with_pois(graph_data, city_key)

        city_info = CITY_REGISTRY.get(city_key, {"place": city_key.title(), "lat": 0.0, "lon": 0.0})
        if payload.apply_weather:
            weather = await weather_engine.get_weather(city_info["lat"], city_info["lon"])
            graph_data = weather_engine.apply_to_graph(graph_data, weather)

        CITY_CACHE[city_key] = graph_data
        return {
            "status": "ok",
            "city_id": city_key,
            "city_name": city_info["place"].split(",")[0],
            "lat": city_info["lat"],
            "lon": city_info["lon"],
            "node_count": graph_data["node_count"],
            "edge_count": graph_data["edge_count"],
            "source": graph_data.get("source", "unknown"),
            "data": graph_data,
            "graph": graph_data,
        }
    except Exception as exc:
        logger.exception("City load failed for %s", city_key)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/city/custom")
async def save_custom_city(payload: dict):
    city_id = slugify_city(payload.get("city_id", "custom_forge"))
    payload["city_name"] = payload.get("city_name", "Custom City")
    payload["node_count"] = len(payload.get("nodes", []))
    payload["edge_count"] = len(payload.get("edges", []))
    payload["source"] = "custom_forge"
    CITY_CACHE[city_id] = payload
    return {"status": "ok", "city_id": city_id}


@router.get("/weather/{lat}/{lon}")
async def get_weather(lat: float, lon: float):
    weather = await weather_engine.get_weather(lat, lon)
    return weather

