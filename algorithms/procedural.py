"""
algorithms/procedural.py — Procedural City Generation Sandbox.
Generates terrain, city hubs, and road grids step-by-step.
"""

import math
import random
import time

def generate_procedural_city(terrain_type: str = "plains", size: str = "medium", hubs_count: int = 4, seed: int = 42):
    """
    Procedural city generator. Yields GraphDelta steps for 3D visualization.
    
    Phases:
    1. Terrain heightmap generation (Fractal-like noise)
    2. Hub selection (k-Means clustering on buildable cells)
    3. Road backbone generation (Delaunay-style triangulation + Prim's MST)
    4. Secondary loop/street laying (Grid filling + cycles)
    5. final complete graph data
    """
    rng = random.Random(seed)
    
    # Grid dimensions based on size
    grid_sizes = {"small": 10, "medium": 15, "large": 20}
    N = grid_sizes.get(size, 15)
    spacing = 200.0 / N
    
    # 1. Heightmap Generation
    heightmap = {}
    nodes_all = []
    node_idx = 0
    
    # Generate peaks based on terrain type
    peaks = []
    if terrain_type == "coast":
        # Water on the left (x < 0)
        peaks = [(-100, 0, -1.0), (100, 0, 1.5)]
    elif terrain_type == "valley":
        # Low in center, high on left/right
        peaks = [(-100, 0, 2.0), (0, 0, -0.5), (100, 0, 2.0)]
    elif terrain_type == "archipelago":
        # Multiple islands
        peaks = [(-50, -50, 1.8), (50, 50, 1.8), (-50, 50, 1.5), (50, -50, 1.5)]
    else: # plains
        peaks = [(0, 0, 0.5), (-60, -60, 0.8), (60, 60, 0.8)]
        
    for r in range(N):
        for c in range(N):
            x = -100 + c * spacing + rng.uniform(-spacing * 0.15, spacing * 0.15)
            y = -100 + r * spacing + rng.uniform(-spacing * 0.15, spacing * 0.15)
            
            # Compute height based on peaks and distance
            height = 0.5 # base elevation
            for px, py, amp in peaks:
                dist = math.sqrt((x - px)**2 + (y - py)**2)
                height += amp * math.exp(-dist / 80.0)
            
            # Add micro-roughness
            height += rng.uniform(-0.15, 0.15)
            heightmap[node_idx] = height
            
            nodes_all.append({
                "id": node_idx, "x": round(x, 3), "y": round(y, 3),
                "height": round(height, 2)
            })
            node_idx += 1

    yield {
        "kind": "terrain_generated",
        "nodes": nodes_all,
        "xai_text": f"Procedural Phase 1: Generated {len(nodes_all)} terrain grid cells. "
                   f"Elevation model simulates {terrain_type} terrain using distance-weighted fractal peaks."
    }
    time.sleep(0.5)

    # 2. Filter buildable nodes (height >= 0.2 is land)
    buildable_nodes = [n for n in nodes_all if n["height"] >= 0.2]
    if not buildable_nodes:
        buildable_nodes = nodes_all  # fallback

    # Remap sequential IDs
    remap = {n["id"]: i for i, n in enumerate(buildable_nodes)}
    nodes_build = []
    for n in buildable_nodes:
        # Compute real coordinates from game coordinates
        lat = 12.9716 + (n["y"] / 100.0) * 0.02
        lon = 77.5946 + (n["x"] / 100.0) * 0.03
        
        nodes_build.append({
            "id": remap[n["id"]],
            "x": n["x"],
            "y": n["y"],
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "height": n["height"],
            "pop_weight": 1.0
        })

    # Run k-Means clustering to choose hubs
    # Initialize centroids randomly on buildable nodes
    centroids = rng.sample(nodes_build, min(hubs_count, len(nodes_build)))
    centroids_coords = [[c["x"], c["y"]] for c in centroids]
    
    # 3 iterations of k-Means
    for iteration in range(3):
        clusters = {i: [] for i in range(len(centroids_coords))}
        for n in nodes_build:
            # Find closest centroid
            best_dist = float("inf")
            best_idx = 0
            for idx, cc in enumerate(centroids_coords):
                d = (n["x"] - cc[0])**2 + (n["y"] - cc[1])**2
                if d < best_dist:
                    best_dist = d
                    best_idx = idx
            clusters[best_idx].append(n)
            
        # Update centroids
        for idx in range(len(centroids_coords)):
            if clusters[idx]:
                xs = [n["x"] for n in clusters[idx]]
                ys = [n["y"] for n in clusters[idx]]
                centroids_coords[idx] = [sum(xs)/len(xs), sum(ys)/len(ys)]
                
    # Mark the closest node to each centroid as a hub
    hubs = []
    hub_types = ["Residential Hub 🏘️", "Commercial District 🏢", "Industrial Center 🏭", "Green Park 🌲", "University Square 🎓"]
    for idx, cc in enumerate(centroids_coords):
        closest_node = min(nodes_build, key=lambda n: (n["x"] - cc[0])**2 + (n["y"] - cc[1])**2)
        closest_node["pop_weight"] = 3.0  # high population weight for hubs
        closest_node["is_hub"] = True
        closest_node["hub_type"] = hub_types[idx % len(hub_types)]
        hubs.append(closest_node)

    yield {
        "kind": "hubs_placed",
        "hubs": hubs,
        "nodes": nodes_build,
        "xai_text": f"Procedural Phase 2: Placed {len(hubs)} city centers using k-Means clustering on buildable land. "
                   f"Hub types assigned: {', '.join(h['hub_type'] for h in hubs)}."
    }
    time.sleep(0.5)

    # 3. Create Candidate Connections (Delaunay-style)
    # Connect each node to its 3 nearest neighbors
    candidates = []
    edge_set = set()
    for n1 in nodes_build:
        # Get distances to other nodes
        dists = []
        for n2 in nodes_build:
            if n1["id"] == n2["id"]:
                continue
            d = math.sqrt((n1["x"] - n2["x"])**2 + (n1["y"] - n2["y"])**2)
            dists.append((d, n2["id"]))
        dists.sort()
        
        # Connect to 3 nearest
        for d, nid2 in dists[:3]:
            key = (min(n1["id"], nid2), max(n1["id"], nid2))
            if key not in edge_set:
                edge_set.add(key)
                # Edge weight depends on distance and elevation change (avoid steep roads)
                h_diff = abs(n1["height"] - nodes_build[nid2]["height"])
                weight = d * (1.0 + h_diff * 3.0)
                candidates.append({
                    "u": key[0], "v": key[1], "weight": weight,
                    "length": d, "capacity": 800, "speed": 30.0
                })

    # 4. Lay Road Backbone (Prim's MST)
    # Connect everything into a spanning tree to guarantee connectivity
    visited = {0}
    mst_edges = []
    available_edges = [e for e in candidates if (e["u"] == 0 or e["v"] == 0)]
    
    while available_edges and len(visited) < len(nodes_build):
        # Pick cheapest edge connecting visited to unvisited
        cheapest_edge = min(available_edges, key=lambda e: e["weight"])
        mst_edges.append(cheapest_edge)
        
        new_node = cheapest_edge["v"] if cheapest_edge["u"] in visited else cheapest_edge["u"]
        visited.add(new_node)
        
        # Refresh available edges
        available_edges = [
            e for e in candidates
            if (e["u"] in visited) != (e["v"] in visited)
        ]

    yield {
        "kind": "mst_generated",
        "edges": mst_edges,
        "xai_text": "Procedural Phase 3: Constructed main road grid spine using Prim's Minimum Spanning Tree. "
                   "By prioritizing low elevation changes, the roads naturally wind around hills."
    }
    time.sleep(0.5)

    # 5. Add Secondary Loops & Streets
    # Re-insert 15% of discarded candidate edges to create street cycles / highway loops
    discarded = [e for e in candidates if e not in mst_edges]
    random.Random(seed + 1).shuffle(discarded)
    secondary_edges = discarded[:int(len(discarded) * 0.15)]
    
    final_edges = mst_edges + secondary_edges
    
    # Adjust road size based on population flow potential
    for e in final_edges:
        u_node = nodes_build[e["u"]]
        v_node = nodes_build[e["v"]]
        # Highways between hubs or near hubs get more lanes (capacity)
        if u_node.get("pop_weight", 1.0) > 2.0 or v_node.get("pop_weight", 1.0) > 2.0:
            e["capacity"] = 2400  # 3 lanes
            e["speed"] = 60.0
        else:
            e["capacity"] = 800   # 1 lane
            e["speed"] = 30.0

    edges_out = []
    for e in final_edges:
        edges_out.append({
            "u": e["u"], "v": e["v"],
            "weight": round(e["length"] / 20.0, 3),
            "capacity": e["capacity"],
            "length_m": round(e["length"] * 10, 2),
            "speed_kph": e["speed"]
        })

    # Prepare complete graph
    graph_data = {
        "city_id": f"procedural_{seed}",
        "city_name": f"New {terrain_type.title()} City",
        "node_count": len(nodes_build),
        "edge_count": len(edges_out),
        "bbox": {"min_x": -100, "max_x": 100, "min_y": -100, "max_y": 100},
        "centroid": {"lat": 12.9716, "lon": 77.5946},
        "nodes": nodes_build,
        "edges": edges_out,
        "metadata": {
            "source": "procedural",
            "terrain": terrain_type,
            "size": size,
            "fetched_at": time.time()
        }
    }

    yield {
        "kind": "algorithm_done",
        "graph": graph_data,
        "nodes": nodes_build,
        "edges": edges_out,
        "xai_text": f"Procedural city generation complete! Built {len(nodes_build)} intersections and "
                   f"{len(edges_out)} streets. The city is ready to receive simulations, Architect!"
    }
