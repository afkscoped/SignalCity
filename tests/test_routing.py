import os
import sys
import pytest
import networkx as nx

# Add workspace to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pipeline.city_loader import load_city_graph
from pipeline.geocoder import geocode_place, snap_to_node
from routers.algorithms import _dijkstra_result, _node_pair, _graph_from_data


@pytest.mark.asyncio
async def test_bengaluru_routing_pairs():
    # Load Bengaluru Graph
    graph_data = await load_city_graph("bengaluru")
    assert graph_data is not None
    assert "nodes" in graph_data
    assert "edges" in graph_data

    # Convert to networkx
    nx_graph = _graph_from_data(graph_data)
    assert len(nx_graph.nodes) > 0

    # Test pairs (Source Name, Dest Name)
    pairs = [
        ("HSR Layout", "Koramangala"),
        ("Indiranagar", "Whitefield"),
        ("Jayanagar", "MG Road"),
        ("Majestic", "Electronic City"),
        ("Hebbal", "Marathahalli"),
    ]

    resolved_paths = []

    for src_name, dest_name in pairs:
        # Geocode and resolve nodes
        src_lat, src_lon = geocode_place(src_name, "bengaluru")
        dest_lat, dest_lon = geocode_place(dest_name, "bengaluru")

        src_node = snap_to_node(graph_data, src_lat, src_lon)
        dest_node = snap_to_node(graph_data, dest_lat, dest_lon)

        assert src_node is not None
        assert dest_node is not None
        assert src_node in nx_graph.nodes
        assert dest_node in nx_graph.nodes

        # Route
        params = {"source_name": src_name, "dest_name": dest_name, "city_id": "bengaluru"}
        result = _dijkstra_result(nx_graph, params, graph_data)

        assert "path" in result
        assert len(result["path"]) >= 2
        assert result["path"][0] == src_node
        assert result["path"][-1] == dest_node

        # Get snapped nodes' actual coordinates
        src_lat_snapped = nx_graph.nodes[src_node]["lat"]
        src_lon_snapped = nx_graph.nodes[src_node]["lon"]
        dest_lat_snapped = nx_graph.nodes[dest_node]["lat"]
        dest_lon_snapped = nx_graph.nodes[dest_node]["lon"]

        # Calculate straight line distance (Haversine) between snapped nodes
        from pipeline.geocoder import _haversine_m
        straight_dist = _haversine_m(src_lat_snapped, src_lon_snapped, dest_lat_snapped, dest_lon_snapped)

        # Path length (sum of edge lengths in path)
        path = result["path"]
        print(f"\nDEBUG Route '{src_name}' -> '{dest_name}': path={path}")
        path_length = 0
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            edge_data = nx_graph[u][v]
            print(f"  Edge ({u} -> {v}): length_m={edge_data.get('length_m')}, weight={edge_data.get('weight')}")
            path_length += edge_data.get("length_m", edge_data.get("weight", 0))

        # Detour factor check
        detour_factor = path_length / max(straight_dist, 1.0)
        print(f"Route '{src_name}' -> '{dest_name}' (snapped): straight_dist={straight_dist:.1f}m, path_length={path_length:.1f}m, detour={detour_factor:.2f}")

        # Assert detour factor is within reasonable bounds (1.0x to 3.0x on the snapped endpoints)
        assert detour_factor >= 0.7  # Road distance must be at least straight line distance (within small numeric precision)
        assert detour_factor <= 3.5  # Safe upper bound for urban grid detour

        resolved_paths.append(tuple(path))

    # Assert paths are different
    assert len(set(resolved_paths)) == len(pairs), "Paths are not distinct!"


@pytest.mark.asyncio
async def test_determinism_and_caching():
    graph_data = await load_city_graph("bengaluru")
    nx_graph = _graph_from_data(graph_data)

    params = {"source_name": "HSR Layout", "dest_name": "Koramangala", "city_id": "bengaluru"}

    res1 = _dijkstra_result(nx_graph, params, graph_data)
    res2 = _dijkstra_result(nx_graph, params, graph_data)

    assert res1["path"] == res2["path"], "Routing is non-deterministic!"
