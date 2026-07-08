import os
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from auth.jwt_handler import create_token
from auth.middleware import get_current_user
from auth.password import hash_password, verify_password
from database import repositories as repo
from database.connection import close_db, connect_db, is_memory_mode
from routers.algorithms import ALGORITHMS, dispatch_algorithm, _graph_from_data
from routers.city import get_cached_city
from routers import algorithms, city, game, nlp, impact
from pipeline.graph_scope import scope_graph_data

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    for path in ["data/graphs", "data/pois", "data/osmnx_cache", "data/cities"]:
        os.makedirs(path, exist_ok=True)
    print("[SIGNAL CITY] Server Started")
    yield
    await close_db()


app = FastAPI(title="Signal City", version="3.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

Path("static").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/data", StaticFiles(directory="data"), name="data")
app.include_router(city.router)
app.include_router(algorithms.router)
app.include_router(nlp.router)
app.include_router(game.router)
app.include_router(impact.router)


def _page(path: str):
    return FileResponse(path)


@app.get("/")
async def serve_index():
    return _page("static/mode-select.html")


@app.get("/auth")
async def serve_auth():
    return _page("static/auth.html")


@app.get("/select")
async def serve_select():
    return _page("static/mode-select.html")


@app.get("/mode1")
async def serve_mode1():
    return _page("static/mode1.html")


@app.get("/mode2")
async def serve_mode2():
    return _page("static/mode2.html")


@app.get("/impact")
async def serve_impact():
    return _page("static/impact.html")


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "services": {
            "groq_nlp": "enabled" if os.getenv("GROQ_API_KEY") else "regex_fallback",
            "database": "in_memory" if is_memory_mode() else "mongodb",
            "weather": "live" if os.getenv("OWM_API_KEY") else "simulated",
        },
    }


LEVEL_UNLOCKS = {
    1: ["dijkstra", "prim", "kruskal"],
    2: ["astar", "edmonds_karp"],
    3: ["risk_aware", "flood_aware", "pagerank"],
    4: ["leiden", "k_median"],
    5: ["contraction"],
}

def _unlock_algos_for_level(user: dict, new_level: int, current_unlocked: list) -> list:
    unlocked = list(current_unlocked)
    for lvl in range(1, new_level + 1):
        for algo in LEVEL_UNLOCKS.get(lvl, []):
            if algo not in unlocked:
                unlocked.append(algo)
    return unlocked


@app.post("/api/auth/register")
async def register(body: dict):
    username = body.get("username", "").strip()
    email = body.get("email", "").strip() or f"{username}@local"
    password = body.get("password", "")
    if not username or not password:
        raise HTTPException(400, "Username and password are required")
    if await repo.get_user_by_username(username):
        raise HTTPException(409, "Username already exists")

    user_data = {
        "username": username,
        "email": email,
        "password_hash": hash_password(password),
        "level": 1,
        "xp": 0,
        "coins": 2000,
        "research_points": 100,
        "happiness": 75,
        "population": 100,
        "current_turn": 1,
        "unlocked_algos": LEVEL_UNLOCKS[1],
        "completed_quests": [],
        "created_at": datetime.utcnow(),
    }
    user = await repo.create_user(user_data)
    token = create_token(user["_id"], username)
    return {"token": token, "profile": _serialize_user(user)}


@app.post("/api/auth/login")
async def login(body: dict):
    username = body.get("username", "").strip()
    password = body.get("password", "")
    user = await repo.get_user_by_username(username)
    if not user or not verify_password(password, user.get("password_hash", "")):
        raise HTTPException(401, "Invalid credentials")
    token = create_token(user["_id"], username)
    return {"token": token, "profile": _serialize_user(user)}


@app.get("/api/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    user = await repo.get_user_by_id(current_user["sub"])
    if not user:
        raise HTTPException(404, "User not found")
    return _serialize_user(user)


def _serialize_user(user: dict) -> dict:
    out = {k: v for k, v in user.items() if k != "password_hash"}
    for key, value in list(out.items()):
        if isinstance(value, datetime):
            out[key] = value.isoformat()
    out.setdefault("avatar", "SC")
    out.setdefault("xp_to_next", 150)
    return out


@app.get("/api/quests")
async def quests():
    return await repo.get_all_quests()


@app.get("/api/leaderboard")
async def leaderboard():
    return await repo.get_leaderboard()


@app.get("/api/profile/{user_id}")
async def get_profile(user_id: str):
    user = await repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return _serialize_user(user)


@app.post("/api/profile/{user_id}/update")
async def update_profile(user_id: str, body: dict):
    user = await repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    
    updates = {}
    
    # Calculate updates
    for field in ["xp", "coins", "research_points"]:
        if field in body:
            val = body[field]
            updates[field] = max(0, user.get(field, 0) + val)
            
    if "unlock_algo" in body:
        unlocked = list(user.get("unlocked_algos", []))
        algo = body["unlock_algo"]
        if algo not in unlocked:
            unlocked.append(algo)
            updates["unlocked_algos"] = unlocked
            
    for field in ["level", "happiness", "population"]:
        if field in body:
            updates[field] = body[field]

    # XP level up logic
    if "xp" in updates and updates["xp"] != user.get("xp", 0):
        level = user.get("level", 1)
        xp = updates["xp"]
        while xp >= _xp_for_level(level):
            level += 1
        if level > user.get("level", 1):
            updates["level"] = level
            updates["xp_to_next"] = _xp_for_level(level)
            updates["unlocked_algos"] = _unlock_algos_for_level(user, level, updates.get("unlocked_algos", user.get("unlocked_algos", [])))

    updated = await repo.update_user(user_id, updates)
    return _serialize_user(updated)


@app.post("/api/profile/{user_id}/research")
async def research_algorithm(user_id: str, body: dict):
    user = await repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")

    algo = body.get("algorithm", "").strip().lower()
    if not algo:
        raise HTTPException(400, "Algorithm name is required")

    unlocked = list(user.get("unlocked_algos", LEVEL_UNLOCKS[1]))
    if algo in unlocked:
        return {"status": "ok", "message": "Already unlocked", "profile": _serialize_user(user)}

    if algo not in ALGORITHMS:
        raise HTTPException(400, f"Unknown algorithm: {algo}")

    algo_meta = ALGORITHMS[algo]
    cost = algo_meta.get("cost", 8) * 5

    current_rp = user.get("research_points", 0)
    if current_rp < cost:
        raise HTTPException(400, f"Insufficient Research Points. Need {cost} RP, you have {current_rp} RP.")

    unlocked.append(algo)
    updates = {
        "research_points": current_rp - cost,
        "unlocked_algos": unlocked
    }

    updated = await repo.update_user(user_id, updates)
    return {"status": "ok", "message": f"Successfully unlocked {algo_meta.get('name', algo)}!", "profile": _serialize_user(updated)}


@app.post("/api/quests/{quest_id}/complete")
async def complete_quest(quest_id: str):
    quest = await repo.get_quest_by_id(quest_id)
    if not quest:
        return {"status": "ok", "quest_id": quest_id, "reward_xp": 100, "reward_coins": 50, "reward_rp": 15}
    return {
        "status": "ok",
        "quest_id": quest_id,
        "reward_xp": quest.get("reward_xp", 100),
        "reward_coins": quest.get("reward_coins", 50),
        "reward_rp": quest.get("reward_rp", 15)
    }


@app.post("/api/profile/{user_id}/end-turn")
async def end_turn(user_id: str):
    user = await repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    updates = {
        "current_turn": user.get("current_turn", 1) + 1,
        "coins": user.get("coins", 0) + 50,
        "research_points": user.get("research_points", 0) + 10,
        "population": user.get("population", 100) + 5,
        "xp": user.get("xp", 0) + 25,
    }
    updated = await repo.update_user(user_id, updates)
    return {"turn": updates["current_turn"], "profile": _serialize_user(updated), "leveled_up": False, "new_unlocks": []}


def _xp_for_level(level: int) -> int:
    return int(100 * (level ** 1.5))


ALGO_REGISTRY = {
    "prim": {"name": "Prim's MST", "category": "mst"},
    "kruskal": {"name": "Kruskal's MST", "category": "mst"},
    "dijkstra": {"name": "Dijkstra's Shortest Path", "category": "pathfinding"},
    "contraction": {"name": "Contraction Hierarchies", "category": "pathfinding"},
    "edmonds_karp": {"name": "Edmonds-Karp Max Flow", "category": "flow"},
    "leiden": {"name": "Leiden Community Detection", "category": "analysis"},
    "louvain": {"name": "Louvain Community Detection", "category": "analysis"},
    "pagerank": {"name": "PageRank Centrality", "category": "analysis"},
    "gwo": {"name": "Grey Wolf Optimizer", "category": "optimization"},
    "alo": {"name": "Ant Lion Optimizer", "category": "optimization"},
    "hho": {"name": "Harris Hawks", "category": "optimization"},
    "coa": {"name": "Coati Optimization Algorithm", "category": "optimization"},
    "woa": {"name": "Whale Optimization Algorithm", "category": "optimization"},
    "run_optimizer": {"name": "Runge-Kutta Optimizer", "category": "optimization"},
    "ptbo": {"name": "Painting Training Optimizer", "category": "optimization"},
    "mpa": {"name": "Marine Predators Algorithm", "category": "optimization"},
    "mfo": {"name": "Moth-Flame Optimization", "category": "optimization"},
    "goa": {"name": "Grasshopper Optimization Algorithm", "category": "optimization"},
    "ao": {"name": "Aquila Optimizer", "category": "optimization"},
    "do": {"name": "Dandelion Optimizer", "category": "optimization"},
    "ssa": {"name": "Salp Swarm Algorithm", "category": "optimization"},
    "sma": {"name": "Slime Mould Algorithm", "category": "optimization"},
    "aoa": {"name": "Arithmetic Optimization Algorithm", "category": "optimization"},
    "gto": {"name": "Gorilla Troops Optimizer", "category": "optimization"},
    "transformer": {"name": "Transformer Attention", "category": "ml"},
    "kan": {"name": "Kolmogorov-Arnold Network", "category": "ml"},
    "swin": {"name": "Swin Transformer Zoning", "category": "ml"},
    "diffusion": {"name": "Diffusion Models", "category": "ml"},
    "raft_consensus": {"name": "Raft Consensus", "category": "systems"},
    "xgboost": {"name": "XGBoost Split Finding", "category": "systems"},
    "count_sketch": {"name": "Count Sketch Streaming", "category": "systems"},
    "rmi": {"name": "Learned Index RMI", "category": "systems"},
    "edf": {"name": "Earliest Deadline First", "category": "scheduling"},
    "sjf": {"name": "Shortest Job First", "category": "scheduling"},
    "fcfs": {"name": "First-Come First-Served", "category": "scheduling"},
    "round_robin": {"name": "Round Robin", "category": "scheduling"},
    "rr": {"name": "Round Robin", "category": "scheduling"},
    "graham_scan": {"name": "Graham Scan CCW Convex Hull", "category": "geometry"},
    "first_fit": {"name": "First-Fit Decreasing Bin Packing", "category": "geometry"},
}


def _get_algorithm_generator(algo_key: str, graph, params: dict, graph_data: dict | None = None):
    from algorithms.graph import WeightedGraph
    import networkx as nx
    from pipeline.geocoder import geocode_place, snap_to_node, GeocodingError

    # Convert networkx Graph to WeightedGraph if needed
    if not isinstance(graph, WeightedGraph):
        wg = WeightedGraph()
        for node_id, data in graph.nodes(data=True):
            try:
                nid = int(node_id)
            except ValueError:
                nid = node_id
            wg.nodes[nid] = {
                "x": data.get("x", 0.0),
                "y": data.get("y", 0.0),
                "lat": data.get("lat", 0.0),
                "lon": data.get("lon", 0.0),
                "pop_weight": data.get("pop_weight", 1.0)
            }
        for u, v, data in graph.edges(data=True):
            try:
                u_id = int(u)
            except ValueError:
                u_id = u
            try:
                v_id = int(v)
            except ValueError:
                v_id = v
            weight = float(data.get("weight", 1.0))
            capacity = int(data.get("capacity", 800))
            length_m = float(data.get("length_m", 100.0))
            edge_id = int(data.get("edge_id", 0))

            if u_id not in wg.adj:
                wg.adj[u_id] = []
            if v_id not in wg.adj:
                wg.adj[v_id] = []

            wg.adj[u_id].append({"to": v_id, "weight": weight, "capacity": capacity, "edge_id": edge_id, "length_m": length_m})
            wg.adj[v_id].append({"to": u_id, "weight": weight, "capacity": capacity, "edge_id": edge_id, "length_m": length_m})
            wg.edge_index[(u_id, v_id)] = len(wg.adj[u_id]) - 1
            wg.edge_index[(v_id, u_id)] = len(wg.adj[v_id]) - 1
            wg._edge_list.append({"u": u_id, "v": v_id, "weight": weight, "capacity": capacity,
                                  "length_m": length_m, "edge_id": edge_id})
            edge_id += 1
        wg.node_count = len(wg.nodes)
        wg.edge_count = edge_id
        graph = wg

    import algorithms.mst as mst
    import algorithms.dijkstra as dijkstra_mod
    import algorithms.flow as flow
    import algorithms.leiden as leiden_mod
    import algorithms.pagerank as pagerank_mod
    import algorithms.metaheuristics as metaheuristics
    import algorithms.ml_ai as ml_ai
    import algorithms.systems as systems
    import algorithms.scheduling as scheduling
    import algorithms.geometry as geometry
    import algorithms.contraction as contraction
    import algorithms.facility as facility

    key = algo_key.lower().strip()
    aliases = {
        "rr": "round_robin",
        "run": "run_optimizer",
        "rko": "run_optimizer",
        "vit": "swin",
        "raft": "raft_consensus",
        "learned_index": "rmi",
        "kan_network": "kan",
        "shortest_path": "dijkstra",
    }
    key = aliases.get(key, key)

    source = params.get("source_node", params.get("start_node", params.get("source")))
    target = params.get("sink_node", params.get("end_node", params.get("target")))

    # Resolve place names via geocoder if provided
    source_name = params.get("source_name")
    dest_name = params.get("dest_name")
    city_key = params.get("city_id", "bengaluru")

    if graph_data and source_name:
        try:
            lat, lon = geocode_place(source_name, city_key)
            snapped = snap_to_node(graph_data, lat, lon)
            if snapped:
                try:
                    snapped_parsed = int(snapped)
                except ValueError:
                    snapped_parsed = snapped
                if snapped_parsed in graph.nodes:
                    source = snapped_parsed
        except Exception as e:
            print(f"[WS] Error geocoding source '{source_name}': {e}")

    if graph_data and dest_name:
        try:
            lat, lon = geocode_place(dest_name, city_key)
            snapped = snap_to_node(graph_data, lat, lon)
            if snapped:
                try:
                    snapped_parsed = int(snapped)
                except ValueError:
                    snapped_parsed = snapped
                if snapped_parsed in graph.nodes:
                    target = snapped_parsed
        except Exception as e:
            print(f"[WS] Error geocoding dest '{dest_name}': {e}")

    if graph.nodes:
        first_node = list(graph.nodes.keys())[0]
        if isinstance(first_node, int):
            if source is not None:
                try:
                    source = int(source)
                except ValueError:
                    pass
            if target is not None:
                try:
                    target = int(target)
                except ValueError:
                    pass
        else:
            if source is not None:
                source = str(source)
            if target is not None:
                target = str(target)

        if source is None or source not in graph.nodes:
            source = first_node
        if target is None or target not in graph.nodes:
            target = list(graph.nodes.keys())[-1]

    if key == "prim":
        return mst.prim_mst(graph, start_node=source, target_node=target)
    elif key == "kruskal":
        return mst.kruskal_mst(graph, source_node=source, target_node=target)
    elif key == "steiner":
        terminals = params.get("terminals") or []
        if not terminals:
            terminals = [source] if source is not None else []
            if target is not None and target not in terminals:
                terminals.append(target)
        return mst.steiner_tree(graph, terminals=terminals)
    elif key in {"dijkstra", "shortest_path"}:
        return dijkstra_mod.dijkstra(graph, source=source, target=target)
    elif key == "flooding_astar":
        import copy
        g_copy = copy.deepcopy(graph)
        flooded = params.get("flooded_nodes", [])
        for u in g_copy.adj:
            for edge in g_copy.adj[u]:
                v = edge["to"]
                if u in flooded or v in flooded:
                    edge["weight"] = edge["weight"] * 1000.0
        return dijkstra_mod.dijkstra(g_copy, source=source, target=target)
    elif key in {"contraction", "contraction_hierarchies"}:
        return contraction.contraction_hierarchies(graph, source=source, target=target)
    elif key in {"edmonds_karp", "flow"}:
        return flow.edmonds_karp(graph, source=source, sink=target)
    elif key in {"leiden", "louvain"}:
        res = float(params.get("resolution", 1.0))
        return leiden_mod.leiden_communities(graph, resolution=res)
    elif key == "pagerank":
        damping = float(params.get("damping", 0.85))
        max_iter = int(params.get("max_iter", 30))
        return pagerank_mod.pagerank_centrality(graph, damping=damping, max_iter=max_iter)
    elif key == "gwo":
        k_val = int(params.get("k", 3))
        max_iter = int(params.get("max_iter", 12))
        return metaheuristics.grey_wolf_optimizer(graph, k=k_val, max_iter=max_iter)
    elif key == "alo":
        k_val = int(params.get("k", 3))
        max_iter = int(params.get("max_iter", 12))
        return metaheuristics.ant_lion_optimizer(graph, k=k_val, max_iter=max_iter)
    elif key == "hho":
        k_val = int(params.get("k", 3))
        max_iter = int(params.get("max_iter", 12))
        return metaheuristics.harris_hawks_optimization(graph, k=k_val, max_iter=max_iter)
    elif key in {"k_median", "facility"}:
        k_val = int(params.get("k", 3))
        return facility.k_median_facility(graph, k=k_val, facility_type=params.get("facility_type", "hospital"))
    elif key in {"coa", "coati"}:
        k_val = int(params.get("k", 3))
        max_iter = int(params.get("max_iter", 12))
        return metaheuristics.coati_optimization_algorithm(graph, k=k_val, max_iter=max_iter)
    elif key == "woa":
        max_iter = int(params.get("max_iter", 12))
        return metaheuristics.whale_optimization_algorithm(graph, max_iter=max_iter)
    elif key == "run_optimizer":
        max_iter = int(params.get("max_iter", 12))
        return metaheuristics.runge_kutta_optimizer(graph, max_iter=max_iter)
    elif key in {"ptbo", "painting"}:
        max_iter = int(params.get("max_iter", 12))
        return metaheuristics.painting_training_optimizer(graph, max_iter=max_iter)
    elif key == "mpa":
        max_iter = int(params.get("max_iter", 12))
        return metaheuristics.marine_predators_algorithm(graph, max_iter=max_iter)
    elif key == "mfo":
        k_val = int(params.get("k", 3))
        max_iter = int(params.get("max_iter", 12))
        return metaheuristics.moth_flame_optimization(graph, k=k_val, max_iter=max_iter)
    elif key == "goa":
        k_val = int(params.get("k", 3))
        max_iter = int(params.get("max_iter", 12))
        return metaheuristics.grasshopper_optimization_algorithm(graph, k=k_val, max_iter=max_iter)
    elif key == "ao":
        k_val = int(params.get("k", 3))
        max_iter = int(params.get("max_iter", 12))
        return metaheuristics.aquila_optimizer(graph, k=k_val, max_iter=max_iter)
    elif key == "do":
        k_val = int(params.get("k", 3))
        max_iter = int(params.get("max_iter", 12))
        return metaheuristics.dandelion_optimizer(graph, k=k_val, max_iter=max_iter)
    elif key == "ssa":
        max_iter = int(params.get("max_iter", 12))
        return metaheuristics.salp_swarm_algorithm(graph, max_iter=max_iter)
    elif key == "sma":
        max_iter = int(params.get("max_iter", 12))
        return metaheuristics.slime_mould_algorithm(graph, max_iter=max_iter)
    elif key == "aoa":
        max_iter = int(params.get("max_iter", 12))
        return metaheuristics.arithmetic_optimization_algorithm(graph, max_iter=max_iter)
    elif key == "gto":
        max_iter = int(params.get("max_iter", 12))
        return metaheuristics.gorilla_troops_optimizer(graph, max_iter=max_iter)
    elif key == "transformer":
        return ml_ai.transformer_attention(graph)
    elif key in {"kan", "kan_network"}:
        return ml_ai.kolmogorov_arnold_networks(graph)
    elif key == "swin":
        return ml_ai.swin_transformer_zoning(graph)
    elif key == "diffusion":
        return ml_ai.diffusion_models(graph)
    elif key == "raft_consensus":
        return systems.raft_consensus(graph)
    elif key == "xgboost":
        max_d = int(params.get("max_depth", 3))
        return systems.xgboost_split_finding(graph, max_depth=max_d)
    elif key == "count_sketch":
        return systems.count_sketch_streaming(graph)
    elif key == "rmi":
        return systems.learned_index_rmi(graph)
    elif key in {"edf", "sjf", "fcfs", "round_robin"}:
        n_jobs = int(params.get("n_jobs", params.get("k", 5)))
        jobs = scheduling.generate_citizen_jobs(n_jobs)
        if key == "edf":
            return scheduling.schedule_edf(jobs)
        elif key == "sjf":
            return scheduling.schedule_sjf(jobs)
        elif key == "fcfs":
            return scheduling.schedule_fcfs(jobs)
        else:
            q = float(params.get("quantum", 2.0))
            return scheduling.schedule_rr(jobs, quantum=q)
    elif key == "graham_scan":
        pts = [(data.get("x", 0), data.get("y", 0)) for data in graph.nodes.values()]
        def scan_gen():
            hull = geometry.graham_scan(pts)
            yield {"kind": "node_visited", "nodes": hull, "op_count": len(pts), "xai_text": "Graham scan convex hull computed."}
            yield {"kind": "algorithm_done", "hull": hull, "op_count": len(pts), "theoretical_complexity": "O(N log N)", "xai_text": f"Graham scan Convex Hull: identified {len(hull)} boundary vertices."}
        return scan_gen()
    elif key == "first_fit":
        items = [float(e.get("length_m", 100.0)) for e in graph.get_all_edges()[:30]]
        cap = float(params.get("bin_capacity", 500.0))
        return geometry.first_fit_decreasing(items, bin_capacity=cap)
    
    return dijkstra_mod.dijkstra(graph, source=source or 0, target=target or 1)


@app.websocket("/ws/algorithm")
async def ws_algorithm(websocket: WebSocket):
    import asyncio
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("action") != "run":
                continue
            city_id = data.get("city_id", "bengaluru")
            graph_data = get_cached_city(city_id)
            if not graph_data:
                try:
                    from pipeline.city_loader import load_city_graph
                    from pipeline.dataset_loader import enrich_graph_with_pois
                    from routers.city import CITY_CACHE, slugify_city
                    city_key = slugify_city(city_id)
                    graph_data = await load_city_graph(city_key)
                    graph_data = await enrich_graph_with_pois(graph_data, city_key)
                    CITY_CACHE[city_key] = graph_data
                except Exception as load_err:
                    await websocket.send_json({"type": "error", "message": f"Auto-loading city '{city_id}' failed: {str(load_err)}"})
                    continue

            algo_name = data.get("algorithm", "dijkstra")
            user_id = data.get("user_id")

            params = data.get("params", {})
            speed_ms = float(params.get("speed_ms", 120))
            delay = speed_ms / 1000.0

            # Re-apply current weather to graph so edge weight/capacity multipliers match live conditions
            try:
                from pipeline.weather import WeatherEngine
                weather_eng = WeatherEngine()
                lat = graph_data.get("lat", 12.9716)
                lon = graph_data.get("lon", 77.5946)
                weather = await weather_eng.get_weather(lat, lon)
                graph_data = weather_eng.apply_to_graph(graph_data, weather)
            except Exception as w_err:
                print(f"Error applying weather to graph in WebSocket: {w_err}")

            graph_data = scope_graph_data(graph_data, params)
            graph = _graph_from_data(graph_data)

            # Start background reader task to check for skip commands
            is_skipped = False
            async def listen_for_skip():
                nonlocal is_skipped
                try:
                    while True:
                        incoming = await websocket.receive_json()
                        if incoming.get("action") == "skip":
                            is_skipped = True
                            break
                except Exception:
                    pass

            listener_task = asyncio.create_task(listen_for_skip())

            try:
                try:
                    gen = _get_algorithm_generator(algo_name, graph, params, graph_data)
                    if gen is None:
                        await websocket.send_json({"type": "error", "message": f"Algorithm '{algo_name}' generator not found."})
                        listener_task.cancel()
                        continue

                    start_time = time.time()
                    last_step = None

                    MAX_STEPS = 2500 if algo_name in {"prim", "kruskal"} else 1500
                    step_count = 0
                    for step in gen:
                        step_count += 1
                        await websocket.send_json({
                            "type": "step",
                            "delta": step,
                            "stats": {
                                "algo_name": algo_name,
                                "ops_so_far": step.get("op_count", 0),
                                "theoretical_n": graph.node_count if hasattr(graph, 'node_count') else len(graph.nodes),
                                "theoretical_complexity": step.get("theoretical_complexity", "O(V + E)"),
                                "wall_ms": int((time.time() - start_time) * 1000)
                            }
                        })
                        if not is_skipped:
                            await asyncio.sleep(delay)
                        last_step = step
                        
                        if step.get("kind") == "algorithm_done":
                            break
                        if step_count >= MAX_STEPS:
                            # Silently drain generator to get the final done step stats
                            for remaining in gen:
                                last_step = remaining
                                if remaining.get("kind") == "algorithm_done":
                                    break
                            break
                finally:
                    if not listener_task.done():
                        listener_task.cancel()

                # Post-run metrics grading
                wall_ms = int((time.time() - start_time) * 1000)
                ops = last_step.get("op_count", 1) if last_step else 1
                theoretical = last_step.get("theoretical_ops", max(ops, 1)) if last_step else max(ops, 1)

                ratio = ops / max(theoretical, 1)
                efficiency = max(0, min(100, 100 * (1 - (ratio - 1) / 2)))
                grade = "S" if efficiency >= 95 else "A" if efficiency >= 80 else "B" if efficiency >= 65 else "C" if efficiency >= 50 else "D"
                rewards = {"S": (500, 300, 50), "A": (300, 200, 35), "B": (200, 120, 20), "C": (100, 60, 10), "D": (50, 20, 5)}[grade]

                summary = {
                    "algorithm": algo_name,
                    "city_id": city_id,
                    "node_count": graph_data.get("node_count", graph.node_count if hasattr(graph, 'node_count') else len(graph.nodes)),
                    "edge_count": graph_data.get("edge_count", graph.edge_count if hasattr(graph, 'edge_count') else len(graph.edges)),
                    "scope": graph_data.get("scope", {"mode": "all"}),
                    "efficiency_score": round(efficiency, 1),
                    "grade": grade,
                    "ratio": round(ratio, 3),
                    "xp_earned": rewards[0],
                    "coins_earned": rewards[1],
                    "rp_earned": rewards[2],
                    "total_wall_ms": wall_ms,
                    "ops": ops,
                    "theoretical_ops": theoretical,
                    "xai_text": last_step.get("xai_text", "") if last_step else ""
                }

                if last_step:
                    for field in ["mst_edges", "path", "distance", "dist", "max_flow", "flow_paths", "communities", "n_communities", "scores", "top_nodes", "facilities", "positions", "schedule", "gantt", "predictions", "hull", "total_bins", "bin_fills"]:
                        if field in last_step:
                            summary[field] = last_step[field]

                grade_card = {
                    "grade": grade,
                    "efficiency_score": round(efficiency, 1),
                    "theoretical_ops": theoretical,
                    "actual_ops": ops,
                    "efficiency_ratio": round(ratio, 3),
                    "xp_earned": rewards[0],
                    "coins_earned": rewards[1],
                    "rp_earned": rewards[2],
                    "comparison_text": f"Run used {ops} ops vs. theoretical {theoretical} (ratio: {ratio:.2f}x).",
                    "tips": ["Optimize network parameters for better complexity.", "Avoid duplicate node searches."],
                    "wall_ms": wall_ms
                }
                summary["grade"] = grade_card

                # DB updates
                user_id = data.get("user_id")
                if user_id and user_id != "guest":
                    try:
                        user = await repo.get_user_by_id(user_id)
                        if user:
                            await repo.save_algorithm_run({
                                "user_id": user_id,
                                "algo_name": algo_name,
                                "city_id": city_id,
                                "efficiency_score": efficiency,
                                "grade": grade,
                                "ops": ops,
                                "theoretical_ops": theoretical,
                                "xp_earned": rewards[0],
                                "coins_earned": rewards[1],
                                "timestamp": datetime.utcnow().isoformat(),
                            })

                            updates = {
                                "xp": user.get("xp", 0) + rewards[0],
                                "coins": user.get("coins", 0) + rewards[1],
                                "research_points": user.get("research_points", 0) + rewards[2],
                            }

                            lvl = user.get("level", 1)
                            xp = updates["xp"]
                            while xp >= _xp_for_level(lvl):
                                lvl += 1
                            if lvl > user.get("level", 1):
                                updates["level"] = lvl
                                updates["xp_to_next"] = _xp_for_level(lvl)
                                updates["unlocked_algos"] = _unlock_algos_for_level(user, lvl, updates.get("unlocked_algos", user.get("unlocked_algos", [])))

                            await repo.update_user(user_id, updates)
                    except Exception as db_err:
                        print(f"Error updating user profile via WebSocket: {db_err}")

                await websocket.send_json({
                    "type": "complete",
                    "summary": summary
                })

            except WebSocketDisconnect:
                break
            except Exception as exc:
                import traceback
                traceback.print_exc()
                try:
                    await websocket.send_json({"type": "error", "message": f"Execution error: {str(exc)}"})
                except Exception:
                    pass

    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    print("SIGNAL CITY v2.0 starting on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
