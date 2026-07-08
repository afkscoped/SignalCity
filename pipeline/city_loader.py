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

CITY_ALIASES = {
    "bangalore": "bengaluru",
    "bengaluru-urban": "bengaluru",
}

CITY_HOTSPOTS = {
    "bengaluru": [
        ("Majestic", 12.9767, 77.5713, "transit"),
        ("MG Road", 12.9756, 77.6068, "commercial"),
        ("Indiranagar", 12.9784, 77.6408, "commercial"),
        ("Koramangala", 12.9352, 77.6245, "startup hub"),
        ("HSR Layout", 12.9116, 77.6474, "residential tech hub"),
        ("Electronic City", 12.8452, 77.6602, "technology district"),
        ("Whitefield", 12.9698, 77.7500, "technology district"),
        ("Yeshwanthpur", 13.0250, 77.5340, "industrial transit"),
        ("Hebbal", 13.0358, 77.5970, "airport corridor"),
        ("Jayanagar", 12.9250, 77.5938, "residential market"),
        ("Banashankari", 12.9255, 77.5468, "residential"),
        ("Marathahalli", 12.9569, 77.7011, "ring road junction"),
    ],
    "mumbai": [
        ("Churchgate", 18.9322, 72.8264, "transit"),
        ("Bandra Kurla Complex", 19.0663, 72.8674, "finance district"),
        ("Dadar", 19.0180, 72.8448, "rail interchange"),
        ("Andheri", 19.1197, 72.8464, "commercial"),
        ("Powai", 19.1176, 72.9060, "technology district"),
        ("Worli", 19.0176, 72.8177, "business district"),
        ("Lower Parel", 18.9936, 72.8256, "office district"),
        ("Navi Mumbai Vashi", 19.0762, 72.9987, "satellite city"),
        ("Borivali", 19.2307, 72.8567, "suburban hub"),
        ("Chembur", 19.0522, 72.9005, "eastern corridor"),
    ],
    "delhi": [
        ("Connaught Place", 28.6315, 77.2167, "commercial core"),
        ("India Gate", 28.6129, 77.2295, "civic landmark"),
        ("Karol Bagh", 28.6514, 77.1907, "market"),
        ("Saket", 28.5245, 77.2066, "south district"),
        ("Dwarka", 28.5921, 77.0460, "residential hub"),
        ("Rohini", 28.7383, 77.0822, "north district"),
        ("Nehru Place", 28.5494, 77.2513, "technology market"),
        ("Hauz Khas", 28.5494, 77.2001, "institutional"),
        ("Anand Vihar", 28.6473, 77.3150, "transport hub"),
        ("Noida Sector 18", 28.5708, 77.3261, "NCR commercial"),
    ],
    "chennai": [
        ("T Nagar", 13.0418, 80.2341, "retail district"),
        ("Anna Nagar", 13.0850, 80.2101, "residential hub"),
        ("Guindy", 13.0067, 80.2206, "industrial transit"),
        ("Adyar", 13.0012, 80.2565, "institutional"),
        ("Velachery", 12.9791, 80.2209, "residential"),
        ("OMR Thoraipakkam", 12.9416, 80.2362, "IT corridor"),
        ("Tambaram", 12.9249, 80.1000, "suburban rail"),
        ("Mylapore", 13.0339, 80.2699, "cultural core"),
    ],
    "hyderabad": [
        ("HITEC City", 17.4435, 78.3772, "technology district"),
        ("Gachibowli", 17.4401, 78.3489, "finance technology"),
        ("Secunderabad", 17.4399, 78.4983, "rail hub"),
        ("Charminar", 17.3616, 78.4747, "heritage market"),
        ("Banjara Hills", 17.4126, 78.4483, "commercial"),
        ("Jubilee Hills", 17.4326, 78.4071, "residential"),
        ("Kukatpally", 17.4948, 78.3996, "residential transit"),
        ("LB Nagar", 17.3457, 78.5522, "eastern corridor"),
    ],
    "pune": [
        ("Shivajinagar", 18.5308, 73.8475, "civic transit"),
        ("Hinjawadi", 18.5913, 73.7389, "IT park"),
        ("Kothrud", 18.5074, 73.8077, "residential"),
        ("Hadapsar", 18.5089, 73.9259, "industrial IT"),
        ("Koregaon Park", 18.5362, 73.8938, "commercial"),
        ("Swargate", 18.5018, 73.8636, "bus hub"),
        ("Wakad", 18.5978, 73.7649, "suburban growth"),
        ("Viman Nagar", 18.5679, 73.9143, "airport corridor"),
    ],
    "kolkata": [
        ("Esplanade", 22.5646, 88.3517, "central transit"),
        ("Howrah", 22.5958, 88.2636, "rail hub"),
        ("Salt Lake Sector V", 22.5760, 88.4333, "IT district"),
        ("Park Street", 22.5535, 88.3525, "commercial"),
        ("Ballygunge", 22.5279, 88.3633, "residential"),
        ("Dum Dum", 22.6420, 88.4310, "airport rail"),
        ("New Town", 22.5797, 88.4746, "planned city"),
        ("Garia", 22.4667, 88.4000, "south transit"),
    ],
    "jaipur": [
        ("MI Road", 26.9165, 75.8120, "commercial"),
        ("C-Scheme", 26.9124, 75.8013, "business district"),
        ("Malviya Nagar", 26.8543, 75.8124, "residential commercial"),
        ("Mansarovar", 26.8503, 75.7614, "residential"),
        ("Vaishali Nagar", 26.9120, 75.7434, "west district"),
        ("Jagatpura", 26.8360, 75.8412, "growth corridor"),
        ("Amer Fort", 26.9855, 75.8513, "heritage tourism"),
        ("Sitapura", 26.7811, 75.8274, "industrial"),
    ],
    "ahmedabad": [
        ("CG Road", 23.0300, 72.5577, "commercial"),
        ("SG Highway", 23.0714, 72.5178, "business corridor"),
        ("Maninagar", 22.9961, 72.6086, "residential"),
        ("Vastrapur", 23.0396, 72.5293, "commercial residential"),
        ("Satellite", 23.0290, 72.5117, "residential"),
        ("Naroda", 23.0700, 72.6570, "industrial"),
        ("Sabarmati", 23.0716, 72.5860, "transit"),
        ("GIFT City", 23.1582, 72.6835, "finance district"),
    ],
    "surat": [
        ("Adajan", 21.1959, 72.7933, "residential"),
        ("Varachha", 21.2183, 72.8665, "diamond district"),
        ("Ring Road", 21.1950, 72.8311, "textile market"),
        ("Vesu", 21.1417, 72.7709, "residential commercial"),
        ("Udhna", 21.1700, 72.8397, "industrial"),
        ("Katargam", 21.2321, 72.8311, "residential"),
        ("Dumas", 21.0886, 72.7083, "coastal"),
        ("Sachin GIDC", 21.0871, 72.8782, "industrial"),
    ],
}

GRAPH_CACHE_DIR = os.path.join("data", "graphs")
os.makedirs(GRAPH_CACHE_DIR, exist_ok=True)


def slugify_city(city_key: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", city_key.lower().strip()).strip("-")
    return CITY_ALIASES.get(slug, slug or "bengaluru")


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

    if len(cc_nodes) > 450:
        avg_lat = sum(lats_dict[nid] for nid in cc_nodes) / len(cc_nodes)
        avg_lon = sum(lons_dict[nid] for nid in cc_nodes) / len(cc_nodes)
        
        center_node = min(cc_nodes, key=lambda nid: (lats_dict[nid] - avg_lat)**2 + (lons_dict[nid] - avg_lon)**2)
        
        sampled_ids = set([center_node])
        queue = [center_node]
        head = 0
        while head < len(queue) and len(sampled_ids) < 450:
            curr = queue[head]
            head += 1
            for neighbor in u_graph.neighbors(curr):
                if neighbor in cc_nodes and neighbor not in sampled_ids:
                    sampled_ids.add(neighbor)
                    queue.append(neighbor)
                    if len(sampled_ids) >= 450:
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

    return _attach_hotspots({
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "bbox": {"min_lat": min_lat, "max_lat": max_lat, "min_lon": min_lon, "max_lon": max_lon},
    })


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _attach_hotspots(graph_data: dict[str, Any]) -> dict[str, Any]:
    city_key = slugify_city(graph_data.get("city", graph_data.get("city_id", "bengaluru")))
    hotspots = CITY_HOTSPOTS.get(city_key, [])
    nodes = graph_data.get("nodes", [])
    if not hotspots or not nodes:
        return graph_data

    assigned = []
    used_nodes = set()
    existing_ids = {str(node.get("id")) for node in nodes}
    for idx, (name, lat, lon, role) in enumerate(hotspots):
        nearest = None
        nearest_dist = float("inf")
        for node in nodes:
            if "lat" not in node or "lon" not in node:
                continue
            dist = _haversine_m(lat, lon, float(node["lat"]), float(node["lon"]))
            if dist < nearest_dist:
                nearest = node
                nearest_dist = dist
        if nearest is None:
            continue
        if nearest_dist > 1500:
            hotspot_id = f"hotspot_{idx}"
            while hotspot_id in existing_ids:
                hotspot_id = f"{hotspot_id}_x"
            existing_ids.add(hotspot_id)
            center_lat = graph_data.get("centroid", {}).get("lat") or CITY_REGISTRY.get(city_key, {}).get("lat", lat)
            center_lon = graph_data.get("centroid", {}).get("lon") or CITY_REGISTRY.get(city_key, {}).get("lon", lon)
            hotspot_node = {
                "id": hotspot_id,
                "x": max(-120, min(120, round((lon - center_lon) * 900, 3))),
                "y": max(-120, min(120, round((lat - center_lat) * 900, 3))),
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "street_count": 4,
                "name": name,
                "hotspot": True,
                "district_role": role,
                "pop_weight": 3.0,
                "amenities": [{"type": "hotspot", "name": name, "dist_m": 0}],
            }
            nodes.append(hotspot_node)
            graph_data.setdefault("edges", []).append({
                "source": nearest["id"],
                "target": hotspot_id,
                "u": nearest["id"],
                "v": hotspot_id,
                "weight": round(nearest_dist, 2),
                "length_m": round(nearest_dist, 2),
                "lanes": 2,
                "highway": "arterial_connector",
                "name": f"{name} connector",
                "capacity": 3600,
            })
            nearest = hotspot_node
            nearest_dist = 0
        nearest["name"] = name
        nearest["hotspot"] = True
        nearest["district_role"] = role
        nearest["pop_weight"] = max(float(nearest.get("pop_weight", 1.0)), 2.5)
        nearest.setdefault("amenities", []).append({"type": "hotspot", "name": name, "dist_m": round(nearest_dist)})
        if nearest["id"] not in used_nodes:
            assigned.append({"node_id": nearest["id"], "name": name, "role": role, "lat": lat, "lon": lon, "nearest_dist_m": round(nearest_dist)})
            used_nodes.add(nearest["id"])

    graph_data["hotspots"] = assigned
    graph_data["hotspot_count"] = len(assigned)
    graph_data["node_count"] = len(graph_data.get("nodes", []))
    graph_data["edge_count"] = len(graph_data.get("edges", []))
    return graph_data


def _load_bundled_fallback(city_key: str) -> dict[str, Any] | None:
    fallback_names = [city_key]
    if city_key == "bengaluru":
        fallback_names.append("bangalore")
    for name in fallback_names:
        path = os.path.join("data", "fallback", f"{name}.json")
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["city"] = city_key
            data["city_id"] = city_key
            data["source"] = data.get("source") or data.get("metadata", {}).get("source", "bundled_fallback")
            data["source"] = "bundled_fallback"
            data["node_count"] = len(data.get("nodes", []))
            data["edge_count"] = len(data.get("edges", []))
            return _attach_hotspots(data)
        except Exception as exc:
            logger.warning("Bundled fallback failed for %s: %s", city_key, exc)
    return None


async def load_city_graph(city_key: str) -> dict[str, Any]:
    city_key = slugify_city(city_key)
    json_cache_path = os.path.join(GRAPH_CACHE_DIR, f"{city_key}.json")
    graphml_cache_path = os.path.join(GRAPH_CACHE_DIR, f"{city_key}.graphml")

    if os.path.exists(json_cache_path):
        try:
            with open(json_cache_path, "r", encoding="utf-8") as f:
                cached = _attach_hotspots(json.load(f))
            return cached
        except Exception as exc:
            logger.warning("JSON cache corrupt for %s: %s", city_key, exc)

    if os.path.exists(graphml_cache_path):
        try:
            graph = nx.read_graphml(graphml_cache_path)
            data = _project_coords(graph)
            data.update({"city": city_key, "source": "osmnx_cache"})
            with open(json_cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            return _attach_hotspots(data)
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
        return _attach_hotspots(data)
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
        return _attach_hotspots(data)
    except Exception as overpass_exc:
        logger.error("Overpass download failed for %s: %s", city_key, overpass_exc)

    bundled = _load_bundled_fallback(city_key)
    if bundled:
        return bundled
    return _generate_synthetic_graph(city_key)



def _generate_synthetic_graph(city_key: str, n: int = 240) -> dict[str, Any]:
    seed = int(hashlib.md5(city_key.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed)
    center = CITY_REGISTRY.get(city_key, {"lat": 0.0, "lon": 0.0})

    nodes = []
    hotspots = CITY_HOTSPOTS.get(city_key, [])
    for i, (name, lat, lon, role) in enumerate(hotspots):
        x = round((lon - center["lon"]) * 900, 3)
        y = round((lat - center["lat"]) * 900, 3)
        nodes.append({
            "id": f"h{i}",
            "x": max(-100, min(100, x)),
            "y": max(-100, min(100, y)),
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "street_count": 4,
            "osmid": f"hotspot-{i}",
            "name": name,
            "hotspot": True,
            "district_role": role,
            "pop_weight": 3.0,
            "amenities": [{"type": "hotspot", "name": name, "dist_m": 0}],
        })
    for i in range(len(nodes), n):
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

    return _attach_hotspots({
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "city": city_key,
        "source": "synthetic_fallback",
        "bbox": {"min_lat": min(n["lat"] for n in nodes), "max_lat": max(n["lat"] for n in nodes),
                 "min_lon": min(n["lon"] for n in nodes), "max_lon": max(n["lon"] for n in nodes)},
    })


def get_city_list() -> list[dict[str, Any]]:
    return [{"key": key, "name": value["place"].split(",")[0], "lat": value["lat"], "lon": value["lon"]}
            for key, value in CITY_REGISTRY.items()]
