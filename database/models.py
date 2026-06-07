"""
database/models.py — Pydantic models for all MongoDB collections.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class Guild(str, Enum):
    ALGORITHM_MAGE = "Algorithm Mage"
    FLOW_ARCHITECT = "Flow Architect"
    CHRONO_STRATEGIST = "Chrono Strategist"
    DATA_RANGER = "Data Ranger"


class EfficiencyGrade(str, Enum):
    S = "S"
    A = "A"
    B = "B"
    C = "C"
    D = "D"


# ─── User / Profile ──────────────────────────────────────────────────────
class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    guild: str = "Algorithm Mage"


class UserLogin(BaseModel):
    username: str
    password: str


class UserProfile(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    username: str
    email: str
    password_hash: str = ""
    guild: str = "Algorithm Mage"
    avatar: str = "🧙"
    level: int = 1
    xp: int = 0
    xp_to_next: int = 150
    coins: int = 500
    research_points: int = 100
    happiness: float = 75.0
    population: int = 100
    current_turn: int = 1
    unlocked_algos: List[str] = Field(default_factory=lambda: ["prim", "dijkstra", "fcfs"])
    completed_quests: List[str] = Field(default_factory=list)
    achievements: List[str] = Field(default_factory=list)
    game_mode: str = "none"
    city_id: Optional[str] = None
    total_runs: int = 0
    total_efficiency_score: float = 0.0
    avg_efficiency: float = 0.0
    cities_loaded: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_active: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


# ─── Algorithm Run Log ───────────────────────────────────────────────────
class AlgorithmRun(BaseModel):
    user_id: str
    session_id: str = ""
    algo_name: str
    city_id: str
    node_count: int = 0
    edge_count: int = 0
    actual_ops: int = 0
    theoretical_ops: int = 0
    efficiency_ratio: float = 1.0
    efficiency_score: float = 50.0
    grade: str = "C"
    wall_ms: float = 0.0
    xp_earned: int = 0
    coins_earned: int = 0
    rp_earned: int = 0
    xai_summary: str = ""
    tips: List[str] = Field(default_factory=list)
    comparison_text: str = ""
    ran_at: datetime = Field(default_factory=datetime.utcnow)


# ─── City Cache ──────────────────────────────────────────────────────────
class CityCache(BaseModel):
    city_id: str
    city_name: str
    graph_json: Dict[str, Any]
    centroid_lat: float = 0.0
    centroid_lon: float = 0.0
    node_count: int = 0
    edge_count: int = 0
    source: str = "synthetic"
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Game Session ────────────────────────────────────────────────────────
class GameSession(BaseModel):
    user_id: str
    mode: str = "map_explorer"
    city_id: Optional[str] = None
    turns_played: int = 0
    algorithms_run: List[str] = Field(default_factory=list)
    total_ops: int = 0
    final_score: float = 0.0
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None


# ─── Leaderboard Entry ──────────────────────────────────────────────────
class LeaderboardEntry(BaseModel):
    username: str
    guild: str
    level: int
    avg_efficiency_score: float
    total_runs: int
    best_grade: str = "D"
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ─── City Builder State ──────────────────────────────────────────────────
class CityBuilderState(BaseModel):
    user_id: str
    turn: int = 1
    coins: int = 500
    power: int = 0
    power_capacity: int = 0
    population: int = 0
    happiness: float = 75.0
    research_points: int = 0
    placed_buildings: List[Dict[str, Any]] = Field(default_factory=list)
    roads: List[Dict[str, Any]] = Field(default_factory=list)
    power_lines: List[Dict[str, Any]] = Field(default_factory=list)
    districts: List[Dict[str, Any]] = Field(default_factory=list)
    weather: str = "CLEAR"
    updated_at: datetime = Field(default_factory=datetime.utcnow)
