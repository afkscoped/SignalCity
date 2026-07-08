"""
pipeline/geocoder.py — Geocoding and node snapping for Signal City.

Resolves place names to (lat, lon) coordinates and snaps them to the
nearest node in a loaded city graph. Used by the NLP routing pipeline
to enable queries like "shortest path from HSR Layout to Koramangala".

Priority order:
1. Known hotspot lookup (instant, offline)
2. Fuzzy hotspot match (offline, handles partial names)
3. Nominatim geocoding via httpx (online fallback)
"""

import logging
import math
import re
from typing import Optional

logger = logging.getLogger(__name__)


class GeocodingError(Exception):
    """Raised when a place name cannot be resolved to coordinates."""
    pass


# ── Bengaluru Locality Database (offline-first) ──────────────────────────
# Covers all major localities so routing works without network access.
# Coordinates sourced from Google Maps / OSM.

BENGALURU_LOCALITIES: dict[str, tuple[float, float]] = {
    # Core / Central
    "majestic": (12.9767, 77.5713),
    "mg road": (12.9756, 77.6068),
    "brigade road": (12.9716, 77.6070),
    "commercial street": (12.9833, 77.6073),
    "cubbon park": (12.9763, 77.5929),
    "vidhana soudha": (12.9791, 77.5907),
    "kr market": (12.9653, 77.5779),
    "city market": (12.9653, 77.5779),
    "shivajinagar": (12.9857, 77.6046),
    "cantonment": (12.9910, 77.5990),
    "ulsoor": (12.9831, 77.6190),

    # South Bengaluru
    "koramangala": (12.9352, 77.6245),
    "hsr layout": (12.9116, 77.6474),
    "btm layout": (12.9166, 77.6101),
    "jayanagar": (12.9250, 77.5938),
    "jp nagar": (12.9063, 77.5857),
    "banashankari": (12.9255, 77.5468),
    "basavanagudi": (12.9437, 77.5738),
    "wilson garden": (12.9510, 77.5960),
    "lalbagh": (12.9507, 77.5848),
    "madiwala": (12.9220, 77.6160),
    "bommanahalli": (12.9010, 77.6180),
    "begur": (12.8761, 77.6297),
    "arekere": (12.8968, 77.6080),
    "bilekahalli": (12.9063, 77.6016),

    # East Bengaluru
    "indiranagar": (12.9784, 77.6408),
    "domlur": (12.9609, 77.6387),
    "old airport road": (12.9642, 77.6417),
    "cv raman nagar": (12.9860, 77.6600),
    "whitefield": (12.9698, 77.7500),
    "marathahalli": (12.9569, 77.7011),
    "varthur": (12.9437, 77.7400),
    "bellandur": (12.9260, 77.6780),
    "sarjapur road": (12.9100, 77.6800),
    "harlur": (12.9120, 77.6570),
    "kr puram": (13.0050, 77.6940),
    "mahadevapura": (12.9910, 77.6850),
    "kundalahalli": (12.9620, 77.7150),
    "brookefield": (12.9690, 77.7200),
    "itpl": (12.9850, 77.7320),

    # North Bengaluru
    "hebbal": (13.0358, 77.5970),
    "yelahanka": (13.1005, 77.5940),
    "rt nagar": (13.0217, 77.5960),
    "sadashivanagar": (13.0060, 77.5790),
    "sankey road": (12.9970, 77.5760),
    "rajajinagar": (12.9900, 77.5540),
    "malleshwaram": (13.0035, 77.5680),
    "yeshwanthpur": (13.0250, 77.5340),
    "peenya": (13.0320, 77.5180),
    "jalahalli": (13.0440, 77.5430),
    "nagawara": (13.0450, 77.6100),
    "thanisandra": (13.0590, 77.6280),
    "hennur": (13.0440, 77.6350),
    "kalyan nagar": (13.0280, 77.6390),
    "banaswadi": (13.0130, 77.6410),

    # West Bengaluru
    "vijayanagar": (12.9710, 77.5350),
    "basaveshwaranagar": (12.9870, 77.5380),
    "nagarbhavi": (12.9600, 77.5100),
    "kengeri": (12.9110, 77.4890),
    "rajarajeshwari nagar": (12.9200, 77.5120),
    "mysore road": (12.9500, 77.5300),
    "magadi road": (12.9660, 77.5350),
    "nayandahalli": (12.9530, 77.5200),

    # South-East / Tech Corridor
    "electronic city": (12.8452, 77.6602),
    "silk board": (12.9173, 77.6230),
    "bommasandra": (12.8160, 77.6850),
    "chandapura": (12.7990, 77.7050),
    "anekal": (12.7110, 77.6960),
    "sarjapur": (12.8600, 77.7870),

    # Airport corridor
    "kempegowda international airport": (13.1989, 77.7068),
    "kia": (13.1989, 77.7068),
    "devanahalli": (13.2460, 77.7130),
    "yelahanka air force station": (13.1350, 77.6030),

    # Outer Ring Road / ORR
    "outer ring road": (12.9560, 77.6950),
    "orr": (12.9560, 77.6950),
    "silk board junction": (12.9173, 77.6230),
    "tin factory": (13.0030, 77.6570),
    "kr pura": (13.0050, 77.6940),
    "hebbal flyover": (13.0358, 77.5970),

    # Malls / Landmarks (common in user queries)
    "forum mall": (12.9347, 77.6108),
    "phoenix mall": (12.9972, 77.6964),
    "orion mall": (12.9912, 77.5571),
    "ub city": (12.9716, 77.5967),
    "mantri mall": (12.9913, 77.5700),
    "garuda mall": (12.9709, 77.6096),
    "lulu mall": (12.9580, 77.7060),
}


def _normalize_place(name: str) -> str:
    """Normalize a place name for fuzzy matching."""
    name = name.lower().strip()
    # Remove common suffixes/prefixes
    name = re.sub(r"\b(area|layout|suburb|locality|junction|jn|cross|main|road|rd|stage|phase|block|sector|circle)\b", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _fuzzy_match(name: str, localities: dict[str, tuple[float, float]]) -> Optional[tuple[str, float, float]]:
    """Fuzzy match a place name against known localities."""
    normalized = _normalize_place(name)
    if not normalized:
        return None

    # Exact match on normalized
    for key, (lat, lon) in localities.items():
        if _normalize_place(key) == normalized:
            return key, lat, lon

    # Substring match (input contains key or key contains input)
    best_match = None
    best_len = 0
    for key, (lat, lon) in localities.items():
        norm_key = _normalize_place(key)
        if norm_key in normalized or normalized in norm_key:
            if len(norm_key) > best_len:
                best_len = len(norm_key)
                best_match = (key, lat, lon)

    return best_match


def geocode_place(name: str, city_key: str = "bengaluru") -> tuple[float, float]:
    """
    Resolve a place name to (lat, lon) coordinates.

    Priority:
    1. Exact match in BENGALURU_LOCALITIES (instant, offline)
    2. Fuzzy match (handles partial names, abbreviations)
    3. Nominatim geocoding (online fallback)

    Raises GeocodingError with a descriptive message on failure.
    """
    if not name or not name.strip():
        raise GeocodingError("Empty place name provided")

    name_lower = name.lower().strip()

    # ── 1. Exact hotspot lookup ──
    if name_lower in BENGALURU_LOCALITIES:
        lat, lon = BENGALURU_LOCALITIES[name_lower]
        logger.info("Geocoded '%s' via exact hotspot match → (%.6f, %.6f)", name, lat, lon)
        return lat, lon

    # ── 2. Fuzzy match ──
    match = _fuzzy_match(name_lower, BENGALURU_LOCALITIES)
    if match:
        matched_name, lat, lon = match
        logger.info("Geocoded '%s' via fuzzy match '%s' → (%.6f, %.6f)", name, matched_name, lat, lon)
        return lat, lon

    # ── 3. Also check the CITY_HOTSPOTS from city_loader ──
    try:
        from pipeline.city_loader import CITY_HOTSPOTS
        hotspots = CITY_HOTSPOTS.get(city_key, [])
        for hotspot_name, lat, lon, _role in hotspots:
            if _normalize_place(hotspot_name) == _normalize_place(name_lower):
                logger.info("Geocoded '%s' via CITY_HOTSPOTS → (%.6f, %.6f)", name, lat, lon)
                return lat, lon
            if _normalize_place(name_lower) in _normalize_place(hotspot_name) or \
               _normalize_place(hotspot_name) in _normalize_place(name_lower):
                logger.info("Geocoded '%s' via fuzzy CITY_HOTSPOTS '%s' → (%.6f, %.6f)",
                            name, hotspot_name, lat, lon)
                return lat, lon
    except ImportError:
        pass

    # ── 4. Nominatim geocoding (online fallback) ──
    try:
        import httpx

        query = f"{name}, {city_key.replace('-', ' ').title()}, India"
        logger.info("Geocoding '%s' via Nominatim: query='%s'", name, query)

        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "format": "json", "limit": 1},
                headers={"User-Agent": "SignalCity/3.0"},
            )
            data = resp.json()
            if data:
                lat = float(data[0]["lat"])
                lon = float(data[0]["lon"])
                logger.info("Geocoded '%s' via Nominatim → (%.6f, %.6f)", name, lat, lon)
                return lat, lon

        logger.warning("Nominatim returned no results for '%s'", query)
    except Exception as exc:
        logger.warning("Nominatim geocoding failed for '%s': %s", name, exc)

    raise GeocodingError(
        f"Could not resolve '{name}' to coordinates. "
        f"Try a well-known Bengaluru locality name like 'Koramangala', 'HSR Layout', "
        f"'Indiranagar', 'Whitefield', etc."
    )


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in meters between two (lat, lon) points."""
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def snap_to_node(graph_data: dict, lat: float, lon: float) -> Optional[str]:
    """
    Find the nearest graph node to the given (lat, lon) coordinates.
    Returns the node ID, or None if no nodes have lat/lon data.

    Logs the snapping result for debugging.
    """
    nodes = graph_data.get("nodes", [])
    if not nodes:
        return None

    best_id = None
    best_dist = float("inf")

    for node in nodes:
        node_lat = node.get("lat")
        node_lon = node.get("lon")
        if node_lat is None or node_lon is None:
            continue

        dist = _haversine_m(lat, lon, float(node_lat), float(node_lon))
        if dist < best_dist:
            best_dist = dist
            best_id = node["id"]

    if best_id is not None:
        logger.info(
            "Snapped (%.6f, %.6f) → node '%s' (distance: %.0f m)",
            lat, lon, best_id, best_dist,
        )

    return best_id


def resolve_route_endpoints(
    graph_data: dict,
    source_name: Optional[str],
    dest_name: Optional[str],
    city_key: str = "bengaluru",
) -> tuple[Optional[str], Optional[str], dict]:
    """
    High-level resolver: takes place names, returns (source_node_id, dest_node_id, metadata).

    The metadata dict contains geocoding details for logging/debugging:
    {
        "source_name": str, "source_lat": float, "source_lon": float, "source_node": str,
        "dest_name": str, "dest_lat": float, "dest_lon": float, "dest_node": str,
    }

    Raises GeocodingError if either name cannot be resolved.
    """
    meta = {}

    if source_name:
        src_lat, src_lon = geocode_place(source_name, city_key)
        src_node = snap_to_node(graph_data, src_lat, src_lon)
        meta.update({
            "source_name": source_name,
            "source_lat": src_lat,
            "source_lon": src_lon,
            "source_node": src_node,
        })
    else:
        src_node = None

    if dest_name:
        dst_lat, dst_lon = geocode_place(dest_name, city_key)
        dst_node = snap_to_node(graph_data, dst_lat, dst_lon)
        meta.update({
            "dest_name": dest_name,
            "dest_lat": dst_lat,
            "dest_lon": dst_lon,
            "dest_node": dst_node,
        })
    else:
        dst_node = None

    return src_node, dst_node, meta
