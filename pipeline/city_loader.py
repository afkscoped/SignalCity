import asyncio
import hashlib
import json
import logging
import math
import os
import random
import re
from typing import Any

import networkx as nx

logger = logging.getLogger(__name__)

CITY_REGISTRY = {
    "bengaluru": {"place": "Bengaluru, Karnataka, India", "lat": 12.9716, "lon": 77.5946},
    "mumbai": {"place": "Mumbai, Maharashtra, India", "lat": 19.0760, "lon": 72.8777},
    "delhi": {"place": "Delhi, India", "lat": 28.6139, "lon": 77.2090},
    "chennai": {"place": "Chennai, Tamil Nadu, India", "lat": 13.0827, "lon": 80.2707},
    "hyderabad": {"place": "Hyderabad, Telangana, India", "lat": 17.3850, "lon": 78.4867},
    "pune": {"place": "Pune, Maharashtra, India", "lat": 18.5204, "lon": 73.8567},
    "kolkata": {"place": "Kolkata, West Bengal, India", "lat": 22.5726, "lon": 88.3639},
    "jaipur": {"place": "Jaipur, Rajasthan, India", "lat": 26.9124, "lon": 75.7873},
    "ahmedabad": {"place": "Ahmedabad, Gujarat, India", "lat": 23.0225, "lon": 72.5714},
    "surat": {"place": "Surat, Gujarat, India", "lat": 21.1702, "lon": 72.8311},
}

GRAPH_CACHE_DIR = os.path.join("data", "graphs")
os.makedirs(GRAPH_CACHE_DIR, exist_ok=True)


def slugify_city(city_key: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", city_key.lower().strip()).strip("-")
    return slug or "bengaluru"


def _coerce_int(value: Any, default: int = 1) -> int:
    if isinstance(value, list):
        value = value[0] if value else default
    try:
        return int(str(value).split(";")[0])
    except Exception:
        return default


def _coerce_str(value: Any, default: str = "") -> str:
    if isinstance(value, list):
        value = value[0] if value else default
    return str(value) if value is not None else default


def _project_coords(graph: nx.MultiDiGraph) -> dict[str, Any]:
    u_graph = nx.Graph(graph)
    components = sorted(nx.connected_components(u_graph), key=len, reverse=True)
    if not components:
        raise ValueError("Graph has no connected components")
    
    largest_cc = components[0]
    
    cc_nodes = []
    lats_dict = {}
    lons_dict = {}
    for nid in largest_cc:
        data = graph.nodes[nid]
        if "y" in data and "x" in data:
            cc_nodes.append(nid)
            lats_dict[nid] = float(data["y"])
            lons_dict[nid] = float(data["x"])

    if not cc_nodes:
        raise ValueError("Connected component has no coordinate data")

    if len(cc_nodes) > 150:
        avg_lat = sum(lats_dict[nid] for nid in cc_nodes) / len(cc_nodes)
        avg_lon = sum(lons_dict[nid] for nid in cc_nodes) / len(cc_nodes)
        
        center_node = min(cc_nodes, key=lambda nid: (lats_dict[nid] - avg_lat)**2 + (lons_dict[nid] - avg_lon)**2)
        
        sampled_ids = set([center_node])
        queue = [center_node]
        head = 0
        while head < len(queue) and len(sampled_ids) < 150:
            curr = queue[head]
            head += 1
            for neighbor in u_graph.neighbors(curr):
                if neighbor in cc_nodes and neighbor not in sampled_ids:
                    sampled_ids.add(neighbor)
                    queue.append(neighbor)
                    if len(sampled_ids) >= 150:
                        break
    else:
        sampled_ids = set(cc_nodes)

    nodes_raw = [(nid, graph.nodes[nid]) for nid in sampled_ids]
    lats = [float(data["y"]) for _, data in nodes_raw]
    lons = [float(data["x"]) for _, data in nodes_raw]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    lat_range = max(max_lat - min_lat, 1e-6)
    lon_range = max(max_lon - min_lon, 1e-6)

    def project(lat: float, lon: float) -> tuple[float, float]:
        x = ((lon - min_lon) / lon_range) * 200 - 100
        y = ((lat - min_lat) / lat_range) * 200 - 100
        return round(x, 4), round(y, 4)

    nodes = []
    node_id_map = {}
    for i, (nid, data) in enumerate(nodes_raw):
        short_id = f"n{i}"
        node_id_map[nid] = short_id
        lat = float(data["y"])
        lon = float(data["x"])
        x, y = project(lat, lon)
        nodes.append({
            "id": short_id,
            "osmid": str(nid),
            "x": x,
            "y": y,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "street_count": _coerce_int(data.get("street_count", 0), 0),
        })

    edges = []
    seen_pairs = set()
    for u, v, data in graph.edges(data=True):
        if u not in sampled_ids or v not in sampled_ids:
            continue
        pair = tuple(sorted((u, v)))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        length = float(data.get("length", 100) or 100)
        lanes = _coerce_int(data.get("lanes", 1), 1)
        source = node_id_map[u]
        target = node_id_map[v]
        edges.append({
            "source": source,
            "target": target,
            "u": source,
            "v": target,
            "weight": round(length, 2),
            "length_m": round(length, 2),
            "lanes": lanes,
            "highway": _coerce_str(data.get("highway", "unclassified"), "unclassified"),
            "name": _coerce_str(data.get("name", ""), ""),
            "capacity": lanes * 1800,
        })

    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "bbox": {"min_lat": min_lat, "max_lat": max_lat, "min_lon": min_lon, "max_lon": max_lon},
    }


async def load_city_graph(city_key: str) -> dict[str, Any]:
    city_key = slugify_city(city_key)
    json_cache_path = os.path.join(GRAPH_CACHE_DIR, f"{city_key}.json")
    graphml_cache_path = os.path.join(GRAPH_CACHE_DIR, f"{city_key}.graphml")

    if os.path.exists(json_cache_path):
        try:
            with open(json_cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("JSON cache corrupt for %s: %s", city_key, exc)

    if os.path.exists(graphml_cache_path):
        try:
            graph = nx.read_graphml(graphml_cache_path)
            data = _project_coords(graph)
            data.update({"city": city_key, "source": "osmnx_cache"})
            with open(json_cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            return data
        except Exception as exc:
            logger.warning("GraphML cache failed for %s: %s", city_key, exc)

    try:
        import osmnx as ox
        os.makedirs(os.path.join("data", "osmnx_cache"), exist_ok=True)
        ox.settings.log_console = False
        ox.settings.use_cache = True
        ox.settings.cache_folder = os.path.join("data", "osmnx_cache")

        city_info = CITY_REGISTRY.get(city_key)
        loop = asyncio.get_running_loop()
        if city_info:
            lat, lon = city_info["lat"], city_info["lon"]
            graph = await loop.run_in_executor(
                None,
                lambda: ox.graph_from_point((lat, lon), dist=1200, network_type="drive"),
            )
        else:
            place_query = f"{city_key.replace('-', ' ').title()}, India"
            graph = await loop.run_in_executor(
                None,
                lambda: ox.graph_from_place(place_query, network_type="drive", simplify=True, retain_all=False),
            )
        ox.save_graphml(graph, filepath=graphml_cache_path)
        data = _project_coords(graph)
        data.update({"city": city_key, "source": "osmnx_live"})
        with open(json_cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return data
    except Exception as exc:
        logger.warning("osmnx download/import failed for %s: %s. Trying Overpass API direct download...", city_key, exc)

    try:
        import httpx
        city_info = CITY_REGISTRY.get(city_key)
        if city_info:
            lat, lon = city_info["lat"], city_info["lon"]
        else:
            place_query = f"{city_key.replace('-', ' ').title()}, India"
            headers = {"User-Agent": "SignalCity/2.0"}
            async with httpx.AsyncClient() as client:
                geo_resp = await client.get(
                    f"https://nominatim.openstreetmap.org/search?q={place_query}&format=json&limit=1",
                    headers=headers,
                    timeout=10.0
                )
                geo_data = geo_resp.json()
                if geo_data:
                    lat = float(geo_data[0]["lat"])
                    lon = float(geo_data[0]["lon"])
                else:
                    raise ValueError(f"Could not geocode {place_query}")

        query = f"""
        [out:json][timeout:30];
        (
          way["highway"](around:1200, {lat}, {lon});
        );
        out body;
        >;
        out skel qt;
        """
        async with httpx.AsyncClient() as client:
            response = await client.post("https://overpass-api.de/api/interpreter", data={"data": query}, timeout=30.0)
            response.raise_for_status()
            osm_data = response.json()

        elements = osm_data.get("elements", [])
        nodes_dict = {}
        for el in elements:
            if el.get("type") == "node":
                nodes_dict[el["id"]] = {
                    "y": el["lat"],
                    "x": el["lon"],
                    "street_count": 0
                }

        node_ways_count = {}
        ways_to_add = []
        for el in elements:
            if el.get("type") == "way":
                w_nodes = el.get("nodes", [])
                tags = el.get("tags", {})
                highway = tags.get("highway", "unclassified")
                name = tags.get("name", "")
                lanes = tags.get("lanes", "1")
                oneway = tags.get("oneway", "no")

                if highway in {"footway", "pedestrian", "cycleway", "path", "steps", "corridor", "proposed", "construction", "bridleway", "abandoned", "platform", "raceway", "service"}:
                    continue

                ways_to_add.append({
                    "nodes": w_nodes,
                    "highway": highway,
                    "name": name,
                    "lanes": lanes,
                    "oneway": oneway,
                    "id": el["id"]
                })
                for nid in w_nodes:
                    node_ways_count[nid] = node_ways_count.get(nid, 0) + 1

        for nid, count in node_ways_count.items():
            if nid in nodes_dict:
                nodes_dict[nid]["street_count"] = count

        graph = nx.MultiDiGraph()
        for nid, attrs in nodes_dict.items():
            graph.add_node(nid, **attrs)

        for w in ways_to_add:
            w_nodes = w["nodes"]
            for i in range(len(w_nodes) - 1):
                u = w_nodes[i]
                v = w_nodes[i+1]
                if u in nodes_dict and v in nodes_dict:
                    lat1, lon1 = nodes_dict[u]["y"], nodes_dict[u]["x"]
                    lat2, lon2 = nodes_dict[v]["y"], nodes_dict[v]["x"]
                    R = 6371000.0
                    phi1 = math.radians(lat1)
                    phi2 = math.radians(lat2)
                    dphi = math.radians(lat2 - lat1)
                    dlambda = math.radians(lon2 - lon1)
                    a = math.sin(dphi/2.0)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2.0)**2
                    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
                    dist = R * c

                    try:
                        lanes_val = int(str(w["lanes"]).split(";")[0])
                    except Exception:
                        lanes_val = 1

                    attrs = {
                        "length": dist,
                        "highway": w["highway"],
                        "name": w["name"],
                        "lanes": lanes_val,
                        "osmid": w["id"]
                    }
                    graph.add_edge(u, v, **attrs)
                    is_oneway = w["oneway"] in {"yes", "true", "1"}
                    if not is_oneway:
                        graph.add_edge(v, u, **attrs)

        data = _project_coords(graph)
        data.update({"city": city_key, "source": "overpass_live"})
        with open(json_cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return data
    except Exception as overpass_exc:
        logger.error("Overpass download failed for %s: %s", city_key, overpass_exc)

    return _generate_synthetic_graph(city_key)



def _generate_synthetic_graph(city_key: str, n: int = 120) -> dict[str, Any]:
    seed = int(hashlib.md5(city_key.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed)
    center = CITY_REGISTRY.get(city_key, {"lat": 0.0, "lon": 0.0})

    nodes = []
    for i in range(n):
        x = round(rng.uniform(-90, 90), 3)
        y = round(rng.uniform(-90, 90), 3)
        lat = center["lat"] + y / 900
        lon = center["lon"] + x / 900
        nodes.append({
            "id": f"n{i}",
            "x": x,
            "y": y,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "street_count": 0,
            "osmid": str(i),
        })

    edges = []
    seen = set()
    for i, ni in enumerate(nodes):
        candidates = []
        for j, nj in enumerate(nodes):
            if i == j:
                continue
            dist = math.hypot(ni["x"] - nj["x"], ni["y"] - nj["y"])
            candidates.append((dist, j, nj))
        for dist, j, nj in sorted(candidates)[:3]:
            pair = tuple(sorted((ni["id"], nj["id"])))
            if pair in seen:
                continue
            seen.add(pair)
            lanes = rng.choice([1, 2, 2, 4])
            edges.append({
                "source": pair[0],
                "target": pair[1],
                "u": pair[0],
                "v": pair[1],
                "weight": round(dist * 50, 2),
                "length_m": round(dist * 50, 2),
                "lanes": lanes,
                "highway": rng.choice(["residential", "secondary", "primary"]),
                "name": f"Street {pair[0]}-{pair[1]}",
                "capacity": lanes * 1800,
            })

    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "city": city_key,
        "source": "synthetic_fallback",
        "bbox": {"min_lat": min(n["lat"] for n in nodes), "max_lat": max(n["lat"] for n in nodes),
                 "min_lon": min(n["lon"] for n in nodes), "max_lon": max(n["lon"] for n in nodes)},
    }


def get_city_list() -> list[dict[str, Any]]:
    return [{"key": key, "name": value["place"].split(",")[0], "lat": value["lat"], "lon": value["lon"]}
            for key, value in CITY_REGISTRY.items()]
