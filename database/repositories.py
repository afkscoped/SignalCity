"""
database/repositories.py — CRUD operations for MongoDB collections.
"""
from datetime import datetime, timedelta
from typing import Optional, List
try:
    from bson import ObjectId
except ModuleNotFoundError:
    def ObjectId(value):
        return value
from .connection import get_db


def _oid(doc: dict) -> dict:
    """Convert MongoDB _id ObjectId to string."""
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


# ─── Users ───────────────────────────────────────────────────────────────

async def create_user(user_data: dict) -> dict:
    db = get_db()
    result = await db.users.insert_one(user_data)
    user_data["_id"] = str(result.inserted_id)
    return user_data


async def get_user_by_username(username: str) -> Optional[dict]:
    db = get_db()
    doc = await db.users.find_one({"username": username})
    return _oid(doc) if doc else None


async def get_user_by_email(email: str) -> Optional[dict]:
    db = get_db()
    doc = await db.users.find_one({"email": email})
    return _oid(doc) if doc else None


async def get_user_by_id(user_id: str) -> Optional[dict]:
    db = get_db()
    try:
        doc = await db.users.find_one({"_id": ObjectId(user_id)})
    except Exception:
        doc = await db.users.find_one({"_id": user_id})
    return _oid(doc) if doc else None


async def update_user(user_id: str, updates: dict) -> Optional[dict]:
    db = get_db()
    updates["last_active"] = datetime.utcnow()
    try:
        await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": updates})
        return await get_user_by_id(user_id)
    except Exception:
        await db.users.update_one({"_id": user_id}, {"$set": updates})
        return await get_user_by_id(user_id)


# ─── Algorithm Runs ─────────────────────────────────────────────────────

async def save_algorithm_run(run_data: dict) -> str:
    db = get_db()
    result = await db.runs.insert_one(run_data)
    return str(result.inserted_id)


async def get_user_runs(user_id: str, limit: int = 50) -> List[dict]:
    db = get_db()
    cursor = db.runs.find({"user_id": user_id}).sort("ran_at", -1).limit(limit)
    runs = []
    async for doc in cursor:
        runs.append(_oid(doc))
    return runs


# ─── City Cache ──────────────────────────────────────────────────────────

async def cache_city(city_data: dict):
    db = get_db()
    await db.cities.replace_one(
        {"city_id": city_data["city_id"]},
        city_data,
        upsert=True
    )


async def get_cached_city(city_id: str) -> Optional[dict]:
    db = get_db()
    doc = await db.cities.find_one(
        {"city_id": city_id},
        sort=[("fetched_at", -1)]
    )
    if doc:
        fetched = doc.get("fetched_at", datetime.min)
        if isinstance(fetched, datetime) and (datetime.utcnow() - fetched) < timedelta(hours=24):
            return _oid(doc)
    return None


# ─── Leaderboard ────────────────────────────────────────────────────────

async def get_leaderboard(limit: int = 20) -> List[dict]:
    db = get_db()
    cursor = db.users.find(
        {"total_runs": {"$gt": 0}},
        {"username": 1, "guild": 1, "level": 1, "avg_efficiency": 1,
         "total_runs": 1, "avatar": 1}
    ).sort("avg_efficiency", -1).limit(limit)
    results = []
    async for doc in cursor:
        results.append(_oid(doc))
    return results


# ─── Quests ──────────────────────────────────────────────────────────────

async def get_all_quests() -> List[dict]:
    db = get_db()
    cursor = db.quests.find({})
    quests = []
    async for doc in cursor:
        quests.append(_oid(doc))
    return quests


async def get_quest_by_id(quest_id: str) -> Optional[dict]:
    db = get_db()
    doc = await db.quests.find_one({"id": quest_id})
    return _oid(doc) if doc else None


# ─── Game State (City Builder) ──────────────────────────────────────────

async def save_game_state(user_id: str, state: dict):
    db = get_db()
    state["user_id"] = user_id
    state["updated_at"] = datetime.utcnow()
    await db.game_states.replace_one({"user_id": user_id}, state, upsert=True)


async def get_game_state(user_id: str) -> Optional[dict]:
    db = get_db()
    doc = await db.game_states.find_one({"user_id": user_id})
    return _oid(doc) if doc else None


# ─── Sessions ───────────────────────────────────────────────────────────

async def save_session(session_data: dict) -> str:
    db = get_db()
    result = await db.sessions.insert_one(session_data)
    return str(result.inserted_id)
