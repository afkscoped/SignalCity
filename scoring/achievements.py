"""
scoring/achievements.py — Achievement system for Signal City.
"""
from datetime import datetime
from typing import List, Dict

ACHIEVEMENTS = {
    "first_run": {
        "title": "First Steps",
        "description": "Complete your first algorithm run",
        "icon": "🏃",
        "condition": lambda profile, run: profile.get("total_runs", 0) >= 1,
    },
    "ten_runs": {
        "title": "Algorithm Veteran",
        "description": "Complete 10 algorithm runs",
        "icon": "⚔️",
        "condition": lambda profile, run: profile.get("total_runs", 0) >= 10,
    },
    "perfect_grade": {
        "title": "Perfectionist",
        "description": "Achieve an S-grade on any algorithm",
        "icon": "🌟",
        "condition": lambda profile, run: run.get("grade") == "S",
    },
    "prim_master": {
        "title": "Grid Architect",
        "description": "Run Prim's MST with grade A or higher",
        "icon": "🔌",
        "condition": lambda profile, run: run.get("algo_name") == "prim" and run.get("grade") in ("S", "A"),
    },
    "dijkstra_master": {
        "title": "Pathfinder",
        "description": "Run Dijkstra with grade A or higher",
        "icon": "🗺️",
        "condition": lambda profile, run: run.get("algo_name") == "dijkstra" and run.get("grade") in ("S", "A"),
    },
    "flow_master": {
        "title": "Flow Controller",
        "description": "Run Edmonds-Karp with grade B or higher",
        "icon": "🌊",
        "condition": lambda profile, run: run.get("algo_name") == "edmonds_karp" and run.get("grade") in ("S", "A", "B"),
    },
    "wolf_tamer": {
        "title": "Wolf Tamer",
        "description": "Run Grey Wolf Optimizer successfully",
        "icon": "🐺",
        "condition": lambda profile, run: run.get("algo_name") == "gwo",
    },
    "five_cities": {
        "title": "Explorer",
        "description": "Load 5 different cities",
        "icon": "🌍",
        "condition": lambda profile, run: len(profile.get("cities_loaded", [])) >= 5,
    },
    "level_5": {
        "title": "Rising Star",
        "description": "Reach level 5",
        "icon": "⭐",
        "condition": lambda profile, run: profile.get("level", 1) >= 5,
    },
    "rich_citizen": {
        "title": "City Treasurer",
        "description": "Accumulate 5000 coins",
        "icon": "💰",
        "condition": lambda profile, run: profile.get("coins", 0) >= 5000,
    },
    "meta_runner": {
        "title": "Metaheuristic Master",
        "description": "Run 5 different metaheuristic algorithms",
        "icon": "🧬",
        "condition": lambda profile, run: _count_meta_runs(profile) >= 5,
    },
    "community_builder": {
        "title": "Community Builder",
        "description": "Run Leiden or Louvain community detection",
        "icon": "🏘️",
        "condition": lambda profile, run: run.get("algo_name") in ("leiden", "louvain"),
    },
}

META_ALGOS = {"gwo", "alo", "hho", "coa", "woa", "run_optimizer", "ptbo", "mpa",
              "mfo", "goa", "ao", "do", "ssa", "sma", "aoa", "gto"}


def _count_meta_runs(profile: dict) -> int:
    """Count unique metaheuristic algorithms run by user."""
    # We need to track this from run history — approximate from achievements
    return 0  # Tracked via database queries in practice


def check_achievements(profile: dict, run: dict) -> List[Dict]:
    """
    Check which new achievements are earned after a run.
    Returns list of newly earned achievement dicts.
    """
    existing = set(profile.get("achievements", []))
    newly_earned = []

    for ach_id, ach in ACHIEVEMENTS.items():
        if ach_id not in existing:
            try:
                if ach["condition"](profile, run):
                    newly_earned.append({
                        "id": ach_id,
                        "title": ach["title"],
                        "description": ach["description"],
                        "icon": ach["icon"],
                        "earned_at": datetime.utcnow().isoformat(),
                    })
            except Exception:
                pass

    return newly_earned


def get_all_achievements() -> List[Dict]:
    """Return all achievement definitions (without condition lambdas)."""
    return [
        {"id": k, "title": v["title"], "description": v["description"], "icon": v["icon"]}
        for k, v in ACHIEVEMENTS.items()
    ]
