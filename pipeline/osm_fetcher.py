"""
pipeline/osm_fetcher.py — Fetches city road networks via Overpass API and Nominatim.
Projects and normalizes road coordinates to game space in pure Python.
Falls back to synthetic graph generation when OSM is unavailable.
"""

import json
import math
import random
import time
import sqlite3
from pathlib import Path
import httpx

FALLBACK_DIR = Path("data/fallback")
DB_PATH = Path("data/cache.db")

CITY_CONFIGS = {
    "bangalore": {"place": "Bengaluru, India", "name": "Bengaluru, India"},
    "london": {"place": "City of London, UK", "name": "London, UK"},
    "tokyo": {"place": "Shinjuku, Tokyo, Japan", "name": "Tokyo, Japan"},
    "nyc": {"place": "Manhattan, New York", "name": "New York City, USA"},
    "sydney": {"place": "Sydney CBD, Australia", "name": "Sydney, Australia"},
    "mumbai": {"place": "Mumbai, India", "name": "Mumbai, India"},
    "delhi": {"place": "New Delhi, India", "name": "Delhi, India"},
    "chennai": {"place": "Chennai, India", "name": "Chennai, India"},
    "kolkata": {"place": "Kolkata, India", "name": "Kolkata, India"},
}


def fetch_city_graph(city_id: str, timeout: int = 30) -> dict:
    """
    Fetch city road network. Order of attempts:
    1. SQLite cache (< 24h old)
    2. Overpass live fetch
    3. Fallback JSON file
    4. Synthetic graph generation
    """
    # Step 1: Check cache
    cached = _check_cache(city_id)
    if cached:
        return cached

    config = CITY_CONFIGS.get(city_id, {"place": city_id, "name": city_id.title()})
    place = config.get("place", city_id)
    city_name = config.get("name", city_id)

    # Step 2: Try Overpass API
    try:
        print(f"[OSM] Attempting live Overpass fetch for: {place}")
        graph_data = _fetch_overpass_graph(place, city_id, timeout)
        if graph_data:
            _save_cache(city_id, graph_data)
            return graph_data
    except Exception as e:
        print(f"[OSM] Failed to fetch live data for {city_id}: {e}")

    # Step 3: Try fallback file
    fallback_path = FALLBACK_DIR / f"{city_id}.json"
    if fallback_path.exists():
        try:
            with open(fallback_path, "r") as f:
                data = json.load(f)
            data["metadata"]["source"] = "fallback"
            _save_cache(city_id, data)
            return data
        except Exception as e:
            print(f"[Fallback] Failed to load {city_id}: {e}")

    # Step 4: Generate synthetic
    graph_data = generate_synthetic_graph(city_id, n_nodes=250)
    _save_cache(city_id, graph_data)
    return graph_data


def _fetch_overpass_graph(place_name: str, city_id: str, timeout: int = 30) -> dict | None:
    """Fetch city street network using Nominatim Geocoding and Overpass API."""
    headers = {"User-Agent": "SignalCity/1.0 (raddo@example.com)"}
    
    # 1. Geocode via Nominatim
    geocode_url = f"https://nominatim.openstreetmap.org/search?q={place_name}&format=json&limit=1"
    try:
        r = httpx.get(geocode_url, headers=headers, timeout=timeout)
        geo_data = r.json()
        if not geo_data:
            print(f"[OSM] Nominatim found no results for: {place_name}")
            return None
        lat = float(geo_data[0]["lat"])
        lon = float(geo_data[0]["lon"])
        display_name = geo_data[0].get("display_name", place_name).split(",")[0]
    except Exception as e:
        print(f"[OSM] Geocoding failed: {e}")
        return None

    # 2. Query Overpass API (highways within 1200 meters of centroid)
    overpass_url = "https://overpass-api.de/api/interpreter"
    overpass_query = f"""
    [out:json][timeout:{timeout}];
    (
      way["highway"~"primary|secondary|tertiary|residential"](around:1200, {lat}, {lon});
    );
    out body;
    >;
    out skel qt;
    """
    try:
        r = httpx.post(overpass_url, data={"data": overpass_query}, timeout=timeout)
        if r.status_code != 200:
            print(f"[OSM] Overpass returned status code {r.status_code}")
            return None
            
        data = r.json()
    except Exception as e:
        print(f"[OSM] Overpass request failed: {e}")
        return None

    elements = data.get("elements", [])
    raw_nodes = {}
    raw_ways = []
    
    for el in elements:
        etype = el.get("type")
        if etype == "node":
            raw_nodes[el["id"]] = {"lat": el["lat"], "lon": el["lon"]}
        elif etype == "way":
            raw_ways.append(el)

    if not raw_nodes or not raw_ways:
        print("[OSM] No nodes or ways found in Overpass response")
        return None

    # 3. Filter orphan nodes
    used_node_ids = set()
    for way in raw_ways:
        for nid in way.get("nodes", []):
            if nid in raw_nodes:
                used_node_ids.add(nid)

    if not used_node_ids:
        return None

    # 4. Map OSM IDs to sequential integer IDs
    osm_to_seq = {osm_id: i for i, osm_id in enumerate(sorted(used_node_ids))}
    
    # 5. Centroid
    clat = sum(raw_nodes[nid]["lat"] for nid in used_node_ids) / len(used_node_ids)
    clon = sum(raw_nodes[nid]["lon"] for nid in used_node_ids) / len(used_node_ids)

    # 6. Project relative to centroid (simple transverse mercator)
    projected = {}
    for nid in used_node_ids:
        node_lat = raw_nodes[nid]["lat"]
        node_lon = raw_nodes[nid]["lon"]
        R = 6371000.0
        x = R * math.radians(node_lon - clon) * math.cos(math.radians(clat))
        y = R * math.radians(node_lat - clat)
        projected[nid] = (x, y)

    # Normalize projected coordinates to [-100, 100]
    xs = [p[0] for p in projected.values()]
    ys = [p[1] for p in projected.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    
    cx = (min_x + max_x) / 2
    cy = (min_y + max_y) / 2
    max_extent = max(max_x - min_x, max_y - min_y, 1.0)
    scale = 200.0 / max_extent  # fits in [-100, 100]
    
    nodes_list = []
    for nid in sorted(used_node_ids):
        x_norm = (projected[nid][0] - cx) * scale
        y_norm = (projected[nid][1] - cy) * scale
        
        # Population weight based on density or distance from center
        dist_from_center = math.sqrt(x_norm ** 2 + y_norm ** 2)
        pop_weight = max(0.5, 3.0 - dist_from_center / 50.0) + random.uniform(0, 0.5)

        nodes_list.append({
            "id": osm_to_seq[nid],
            "x": round(x_norm, 3),
            "y": round(y_norm, 3),
            "lat": round(raw_nodes[nid]["lat"], 6),
            "lon": round(raw_nodes[nid]["lon"], 6),
            "pop_weight": round(pop_weight, 2),
        })

    # 7. Extract edges and deduplicate
    edge_set = set()
    edges_list = []
    
    for way in raw_ways:
        way_nodes = way.get("nodes", [])
        tags = way.get("tags", {})
        speed = 40.0
        lanes = 1
        
        # Parse speed limit
        maxspeed = tags.get("maxspeed", "")
        if "mph" in maxspeed:
            try: speed = float(maxspeed.split()[0]) * 1.609
            except: pass
        else:
            try: speed = float(maxspeed)
            except: pass
            
        # Parse lanes
        try: lanes = int(tags.get("lanes", 1))
        except: pass
        
        for i in range(len(way_nodes) - 1):
            u_osm = way_nodes[i]
            v_osm = way_nodes[i + 1]
            if u_osm not in osm_to_seq or v_osm not in osm_to_seq:
                continue
                
            u = osm_to_seq[u_osm]
            v = osm_to_seq[v_osm]
            key = (min(u, v), max(u, v))
            
            if key in edge_set:
                continue
            edge_set.add(key)
            
            # Calculate distance in meters
            ux, uy = projected[u_osm]
            vx, vy = projected[v_osm]
            dist_m = math.sqrt((ux - vx) ** 2 + (uy - vy) ** 2)
            
            # Weight is travel time in minutes: dist_m / speed_mps
            speed_mps = (speed * 1000) / 3600.0
            weight = (dist_m / speed_mps) / 60.0 if speed_mps > 0 else dist_m / 100.0
            
            edges_list.append({
                "u": u,
                "v": v,
                "weight": round(weight, 3),
                "capacity": lanes * 800,
                "length_m": round(dist_m, 2),
                "speed_kph": speed,
            })

    # Limit graph size to 400 nodes for high visual performance
    if len(nodes_list) > 400:
        nodes_list.sort(key=lambda n: n["x"]**2 + n["y"]**2)
        kept_nodes = set(n["id"] for n in nodes_list[:400])
        nodes_list = [n for n in nodes_list if n["id"] in kept_nodes]
        # Remap sequential IDs
        remap = {old: new for new, old in enumerate(sorted(kept_nodes))}
        for n in nodes_list:
            n["id"] = remap[n["id"]]
        edges_list = [
            {**e, "u": remap[e["u"]], "v": remap[e["v"]]}
            for e in edges_list
            if e["u"] in kept_nodes and e["v"] in kept_nodes
        ]
        nodes_list.sort(key=lambda n: n["id"])

    return {
        "city_id": city_id,
        "city_name": display_name,
        "node_count": len(nodes_list),
        "edge_count": len(edges_list),
        "bbox": {"min_x": -100, "max_x": 100, "min_y": -100, "max_y": 100},
        "centroid": {"lat": round(clat, 6), "lon": round(clon, 6)},
        "nodes": nodes_list,
        "edges": edges_list,
        "metadata": {
            "source": "overpass",
            "fetched_at": time.time(),
        },
    }


def generate_synthetic_graph(city_id: str, n_nodes: int = 250) -> dict:
    """
    Generate a realistic synthetic city graph when OSM is unavailable.
    Creates a grid with diagonal shortcuts and randomized weights.
    """
    rng = random.Random(hash(city_id))
    grid_size = int(math.sqrt(n_nodes))
    if grid_size < 5:
        grid_size = 5

    # Coordinates
    city_coords = {
        "bangalore": (12.9716, 77.5946),
        "london": (51.5074, -0.1278),
        "tokyo": (35.6762, 139.6503),
        "nyc": (40.7128, -74.0060),
        "sydney": (-33.8688, 151.2093),
        "mumbai": (18.9750, 72.8258),
        "delhi": (28.6139, 77.2090),
        "chennai": (13.0827, 80.2707),
        "kolkata": (22.5726, 88.3639),
    }
    base_lat, base_lon = city_coords.get(city_id, (12.97, 77.59))
    city_name = CITY_CONFIGS.get(city_id, {}).get("name", city_id.title())

    nodes = []
    node_idx = 0
    grid_spacing = 200.0 / grid_size

    for row in range(grid_size):
        for col in range(grid_size):
            x = -100 + col * grid_spacing + rng.uniform(-grid_spacing * 0.15, grid_spacing * 0.15)
            y = -100 + row * grid_spacing + rng.uniform(-grid_spacing * 0.15, grid_spacing * 0.15)
            x = max(-100, min(100, x))
            y = max(-100, min(100, y))

            dist_from_center = math.sqrt(x ** 2 + y ** 2)
            pop_weight = max(0.5, 3.0 - dist_from_center / 50.0) + rng.uniform(0, 0.5)

            lat = base_lat + (y / 100.0) * 0.02
            lon = base_lon + (x / 100.0) * 0.03

            nodes.append({
                "id": node_idx,
                "x": round(x, 3),
                "y": round(y, 3),
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "pop_weight": round(pop_weight, 2),
            })
            node_idx += 1

    actual_nodes = grid_size * grid_size
    edges = []
    edge_set = set()

    def add_edge(u, v):
        key = (min(u, v), max(u, v))
        if key in edge_set or u == v:
            return
        edge_set.add(key)
        nu, nv = nodes[u], nodes[v]
        dist = math.sqrt((nu["x"] - nv["x"]) ** 2 + (nu["y"] - nv["y"]) ** 2)
        weight = dist * rng.uniform(0.8, 1.4)
        weight = max(0.5, weight)
        capacity = rng.randint(500, 2000)
        speed = rng.choice([20, 30, 40, 50, 60])
        edges.append({
            "u": u, "v": v,
            "weight": round(weight / 10.0, 3),
            "capacity": capacity,
            "length_m": round(dist * 10, 2),
            "speed_kph": speed,
        })

    # Grid connections (horizontal + vertical)
    for row in range(grid_size):
        for col in range(grid_size):
            idx = row * grid_size + col
            if col < grid_size - 1:
                add_edge(idx, idx + 1)
            if row < grid_size - 1:
                add_edge(idx, idx + grid_size)

    # Diagonal shortcuts
    for row in range(grid_size - 1):
        for col in range(grid_size - 1):
            if rng.random() < 0.2:
                idx = row * grid_size + col
                add_edge(idx, idx + grid_size + 1)
            if rng.random() < 0.15 and col > 0:
                idx = row * grid_size + col
                add_edge(idx, idx + grid_size - 1)

    # Random long-distance shortcuts
    for _ in range(actual_nodes // 8):
        u = rng.randint(0, actual_nodes - 1)
        v = rng.randint(0, actual_nodes - 1)
        if abs(u - v) > grid_size * 2:
            add_edge(u, v)

    return {
        "city_id": city_id,
        "city_name": city_name,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "bbox": {"min_x": -100, "max_x": 100, "min_y": -100, "max_y": 100},
        "centroid": {"lat": base_lat, "lon": base_lon},
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "source": "synthetic",
            "fetched_at": time.time(),
            "grid_size": grid_size,
        },
    }


def create_fallback_files():
    """Create fallback JSON files for default cities if they don't exist."""
    FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
    for city_id in ["bangalore", "london", "tokyo", "mumbai"]:
        path = FALLBACK_DIR / f"{city_id}.json"
        if not path.exists():
            print(f"[Fallback] Generating synthetic graph for {city_id}...")
            graph = generate_synthetic_graph(city_id, n_nodes=289)
            graph["metadata"]["source"] = "fallback"
            with open(path, "w") as f:
                json.dump(graph, f)


def _check_cache(city_id: str) -> dict | None:
    """Check SQLite cache for recent graph data."""
    if not DB_PATH.exists():
        return None
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute("SELECT graph_json, fetched_at FROM cities WHERE id = ?", (city_id,))
        row = cur.fetchone()
        conn.close()
        if row:
            fetched_at = row[1]
            if time.time() - fetched_at < 86400:  # 24 hours validity
                return json.loads(row[0])
    except Exception:
        pass
    return None


def _save_cache(city_id: str, graph_data: dict):
    """Save graph to cache."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        cur.execute(
            """INSERT OR REPLACE INTO cities (id, name, lat, lon, graph_json, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                city_id,
                graph_data.get("city_name", city_id),
                graph_data.get("centroid", {}).get("lat", 0),
                graph_data.get("centroid", {}).get("lon", 0),
                json.dumps(graph_data),
                time.time(),
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Cache] Failed to save {city_id}: {e}")
