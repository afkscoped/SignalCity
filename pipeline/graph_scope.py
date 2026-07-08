"""
Graph scoping helpers for Signal City.

Large city graphs are useful for realism, but most DAA demonstrations should
run on a selected corridor, ward, radius, or viewport. These helpers keep the
scope semantics consistent across REST, WebSocket, Signal Map, and Impact
Console calls.
"""

from __future__ import annotations

import math
from typing import Any


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _node_lookup(graph_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(node.get("id")): node for node in graph_data.get("nodes", [])}


def _bounds_from_nodes(nodes: list[dict[str, Any]], pad_ratio: float = 0.2) -> tuple[float, float, float, float] | None:
    pts = [(float(n["lat"]), float(n["lon"])) for n in nodes if n.get("lat") is not None and n.get("lon") is not None]
    if not pts:
        return None
    min_lat = min(lat for lat, _ in pts)
    max_lat = max(lat for lat, _ in pts)
    min_lon = min(lon for _, lon in pts)
    max_lon = max(lon for _, lon in pts)
    lat_pad = max((max_lat - min_lat) * pad_ratio, 0.01)
    lon_pad = max((max_lon - min_lon) * pad_ratio, 0.01)
    return min_lat - lat_pad, min_lon - lon_pad, max_lat + lat_pad, max_lon + lon_pad


def _cap_nodes(nodes: list[dict[str, Any]], anchors: list[dict[str, Any]], max_nodes: int) -> list[dict[str, Any]]:
    if max_nodes <= 0 or len(nodes) <= max_nodes:
        return nodes
    if not anchors:
        anchors = nodes[:1]

    def distance_to_anchors(node: dict[str, Any]) -> float:
        lat = float(node.get("lat", 0.0))
        lon = float(node.get("lon", 0.0))
        return min(
            (lat - float(anchor.get("lat", lat))) ** 2 + (lon - float(anchor.get("lon", lon))) ** 2
            for anchor in anchors
        )

    anchor_ids = {str(anchor.get("id")) for anchor in anchors}
    ordered = sorted(nodes, key=distance_to_anchors)
    selected = []
    seen = set()
    for node in ordered:
        if len(selected) >= max_nodes:
            break
        nid = str(node.get("id"))
        selected.append(node)
        seen.add(nid)
    for node in nodes:
        nid = str(node.get("id"))
        if nid in anchor_ids and nid not in seen:
            selected.append(node)
            seen.add(nid)
    return selected[:max_nodes]


def scope_graph_data(graph_data: dict[str, Any], params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or {}
    scope = params.get("scope") or {}
    mode = str(scope.get("mode") or params.get("scope_mode") or "all").lower()
    if mode in {"", "all", "whole_city", "full"}:
        graph_data.setdefault("scope", {"mode": "all", "node_count": graph_data.get("node_count")})
        return graph_data

    nodes = list(graph_data.get("nodes", []))
    edges = list(graph_data.get("edges", []))
    lookup = _node_lookup(graph_data)
    anchors = []
    for key in ("start_node", "source_node", "source", "end_node", "sink_node", "target"):
        val = params.get(key)
        if val is not None and str(val) in lookup:
            anchors.append(lookup[str(val)])

    min_lat = min_lon = max_lat = max_lon = None
    if mode == "bbox" and scope.get("bbox"):
        bbox = scope["bbox"]
        min_lat = float(bbox["min_lat"])
        min_lon = float(bbox["min_lon"])
        max_lat = float(bbox["max_lat"])
        max_lon = float(bbox["max_lon"])
    elif mode in {"selection", "corridor", "radius"} and anchors:
        radius_km = float(scope.get("radius_km", params.get("scope_radius_km", 4.0 if len(anchors) >= 2 else 2.5)))
        bounds = _bounds_from_nodes(anchors, pad_ratio=0.35)
        if bounds:
            min_lat, min_lon, max_lat, max_lon = bounds
            # Ensure single-point scopes still behave like a true radius.
            if len(anchors) == 1:
                center = anchors[0]
                lat = float(center["lat"])
                lon = float(center["lon"])
                lat_delta = radius_km / 111.0
                lon_delta = radius_km / max(111.0 * math.cos(math.radians(lat)), 1.0)
                min_lat, max_lat = lat - lat_delta, lat + lat_delta
                min_lon, max_lon = lon - lon_delta, lon + lon_delta

    if min_lat is None:
        graph_data.setdefault("scope", {"mode": "all", "warning": f"Scope mode {mode} had no usable bounds."})
        return graph_data

    if mode == "radius" and anchors:
        radius_m = float(scope.get("radius_km", params.get("scope_radius_km", 3.0))) * 1000.0
        scoped_nodes = [
            node for node in nodes
            if node.get("lat") is not None and any(
                _haversine_m(float(node["lat"]), float(node["lon"]), float(anchor["lat"]), float(anchor["lon"])) <= radius_m
                for anchor in anchors
            )
        ]
    else:
        scoped_nodes = [
            node for node in nodes
            if node.get("lat") is not None
            and min_lat <= float(node["lat"]) <= max_lat
            and min_lon <= float(node["lon"]) <= max_lon
        ]

    max_nodes = int(scope.get("max_nodes", params.get("scope_max_nodes", 1500)))
    scoped_nodes = _cap_nodes(scoped_nodes, anchors, max_nodes)
    scoped_ids = {str(node.get("id")) for node in scoped_nodes}
    if len(scoped_ids) < 2:
        graph_data.setdefault("scope", {"mode": "all", "warning": "Scope was too small; full graph kept."})
        return graph_data

    scoped_edges = [
        edge for edge in edges
        if str(edge.get("source", edge.get("u"))) in scoped_ids and str(edge.get("target", edge.get("v"))) in scoped_ids
    ]
    if not scoped_edges:
        graph_data.setdefault("scope", {"mode": "all", "warning": "Scope had no internal roads; full graph kept."})
        return graph_data

    scoped = dict(graph_data)
    scoped["nodes"] = scoped_nodes
    scoped["edges"] = scoped_edges
    scoped["node_count"] = len(scoped_nodes)
    scoped["edge_count"] = len(scoped_edges)
    scoped["scope"] = {
        "mode": mode,
        "node_count": len(scoped_nodes),
        "edge_count": len(scoped_edges),
        "full_node_count": graph_data.get("node_count", len(nodes)),
        "full_edge_count": graph_data.get("edge_count", len(edges)),
        "max_nodes": max_nodes,
    }
    return scoped
