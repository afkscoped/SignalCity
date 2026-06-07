"""
database/connection.py — MongoDB connection with in-memory fallback.
If MONGODB_URI is empty, uses an in-memory dict-based store so the game
works immediately without external dependencies.
"""
import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "")
DB_NAME = "signalcity"

client = None
db = None
_using_memory = False


class _MemoryCollection:
    """Minimal in-memory MongoDB-like collection for development."""
    def __init__(self):
        self._docs = []
        self._counter = 0

    async def insert_one(self, doc):
        self._counter += 1
        if "_id" not in doc:
            doc["_id"] = f"mem_{self._counter}"
        self._docs.append(doc.copy())
        class R:
            inserted_id = doc["_id"]
        return R()

    async def insert_many(self, docs):
        for d in docs:
            await self.insert_one(d)

    async def find_one(self, query=None, sort=None):
        matches = self._match(query or {})
        if sort:
            for field, direction in reversed(sort):
                matches.sort(key=lambda d: d.get(field, 0), reverse=(direction == -1))
        return matches[0].copy() if matches else None

    def find(self, query=None, projection=None):
        return _MemoryCursor(self._match(query or {}), projection)

    async def update_one(self, query, update):
        matches = self._match(query)
        if matches:
            doc = matches[0]
            if "$set" in update:
                doc.update(update["$set"])

    async def replace_one(self, query, doc, upsert=False):
        matches = self._match(query)
        if matches:
            idx = self._docs.index(matches[0])
            doc["_id"] = matches[0].get("_id", doc.get("_id"))
            self._docs[idx] = doc
        elif upsert:
            await self.insert_one(doc)

    async def count_documents(self, query=None):
        return len(self._match(query or {}))

    async def create_index(self, *args, **kwargs):
        pass  # no-op in memory mode

    def _match(self, query):
        results = []
        for doc in self._docs:
            match = True
            for k, v in query.items():
                if isinstance(v, dict):
                    # Handle $gt, $gte, etc.
                    for op, val in v.items():
                        if op == "$gt" and not (doc.get(k, 0) > val): match = False
                else:
                    if doc.get(k) != v:
                        match = False
            if match:
                results.append(doc)
        return results


class _MemoryCursor:
    def __init__(self, docs, projection=None):
        self._docs = docs
        self._projection = projection
        self._sort_fields = []
        self._limit_n = None

    def sort(self, field_or_list, direction=None):
        if isinstance(field_or_list, str):
            self._sort_fields = [(field_or_list, direction or 1)]
        else:
            self._sort_fields = field_or_list
        return self

    def limit(self, n):
        self._limit_n = n
        return self

    def __aiter__(self):
        docs = self._docs[:]
        for field, direction in reversed(self._sort_fields):
            docs.sort(key=lambda d: d.get(field, 0), reverse=(direction == -1))
        if self._limit_n:
            docs = docs[:self._limit_n]
        if self._projection:
            filtered = []
            for d in docs:
                fd = {"_id": d.get("_id")}
                for k, v in self._projection.items():
                    if v and k in d:
                        fd[k] = d[k]
                filtered.append(fd)
            docs = filtered
        self._iter_docs = iter(docs)
        return self

    async def __anext__(self):
        try:
            return next(self._iter_docs).copy()
        except StopIteration:
            raise StopAsyncIteration


class _MemoryDB:
    """Dict-backed pseudo-database with auto-creating collections."""
    def __init__(self):
        self._collections = {}

    def __getattr__(self, name):
        if name.startswith('_'):
            return super().__getattribute__(name)
        if name not in self._collections:
            self._collections[name] = _MemoryCollection()
        return self._collections[name]

    def __getitem__(self, name):
        return getattr(self, name)


async def connect_db():
    """Connect to MongoDB, or fall back to in-memory store."""
    global client, db, _using_memory

    if MONGODB_URI:
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
            client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            await client.admin.command("ismaster")
            db = client[DB_NAME]

            await db.users.create_index("username", unique=True)
            await db.users.create_index("email", unique=True)
            await db.leaderboard.create_index([("avg_efficiency_score", -1)])
            await db.cities.create_index([("city_id", 1), ("fetched_at", -1)])
            await db.runs.create_index([("user_id", 1), ("ran_at", -1)])
            await db.sessions.create_index("user_id")

            count = await db.quests.count_documents({})
            if count == 0:
                await _seed_quests()

            print(f"[SIGNAL CITY] ✓ Connected to MongoDB: {DB_NAME}")
            return
        except Exception as e:
            print(f"[SIGNAL CITY] ⚠ MongoDB connection failed: {e}")
            print("[SIGNAL CITY] Falling back to in-memory storage...")

    # In-memory fallback
    _using_memory = True
    db = _MemoryDB()
    await _seed_quests()
    print("[SIGNAL CITY] ✓ Using in-memory storage (data lost on restart)")
    print("[SIGNAL CITY]   Set MONGODB_URI in .env for persistent storage")


async def init_db():
    await connect_db()


async def close_db():
    global client
    if client:
        client.close()


def get_db():
    return db


def is_memory_mode():
    return _using_memory


async def _seed_quests():
    quests = [
        {"id": "q_001", "title": "Build the Power Grid", "description": "Connect all nodes using Prim's MST",
         "quest_type": "main", "algorithm": "prim", "reward_xp": 100, "reward_coins": 50, "reward_rp": 15,
         "difficulty": "easy", "requirements": {"algorithm": "prim"}},
        {"id": "q_002", "title": "The Shortest Route", "description": "Find optimal path between two points",
         "quest_type": "main", "algorithm": "dijkstra", "reward_xp": 150, "reward_coins": 75, "reward_rp": 20,
         "difficulty": "easy", "requirements": {"algorithm": "dijkstra"}},
        {"id": "q_003", "title": "Forest of Connections", "description": "Build MST using Kruskal's method",
         "quest_type": "main", "algorithm": "kruskal", "reward_xp": 120, "reward_coins": 60, "reward_rp": 15,
         "difficulty": "easy", "requirements": {"algorithm": "kruskal"}},
        {"id": "q_004", "title": "Maximum Traffic Flow", "description": "Maximize vehicle flow through the network",
         "quest_type": "main", "algorithm": "edmonds_karp", "reward_xp": 200, "reward_coins": 100, "reward_rp": 25,
         "difficulty": "medium", "requirements": {"algorithm": "edmonds_karp"}},
        {"id": "q_005", "title": "Emergency Services", "description": "Place hospitals optimally using k-Median",
         "quest_type": "main", "algorithm": "k_median", "reward_xp": 300, "reward_coins": 150, "reward_rp": 30,
         "difficulty": "medium", "requirements": {"algorithm": "k_median"}},
        {"id": "q_006", "title": "District Planner", "description": "Zone the city using Leiden community detection",
         "quest_type": "main", "algorithm": "leiden", "reward_xp": 350, "reward_coins": 175, "reward_rp": 35,
         "difficulty": "hard", "requirements": {"algorithm": "leiden"}},
        {"id": "q_007", "title": "The Fast Lane", "description": "Build contraction hierarchies for instant routing",
         "quest_type": "side", "algorithm": "contraction", "reward_xp": 400, "reward_coins": 200, "reward_rp": 40,
         "difficulty": "hard", "requirements": {"algorithm": "contraction"}},
        {"id": "q_008", "title": "Influence Network", "description": "Find key intersections via PageRank",
         "quest_type": "side", "algorithm": "pagerank", "reward_xp": 250, "reward_coins": 125, "reward_rp": 25,
         "difficulty": "medium", "requirements": {"algorithm": "pagerank"}},
        {"id": "q_009", "title": "Wolf Pack Strategy", "description": "Optimize fire station placement with GWO",
         "quest_type": "side", "algorithm": "gwo", "reward_xp": 280, "reward_coins": 140, "reward_rp": 28,
         "difficulty": "medium", "requirements": {"algorithm": "gwo"}},
        {"id": "q_010", "title": "Storm Response", "description": "Re-optimize network after a weather event",
         "quest_type": "event", "algorithm": "prim", "reward_xp": 500, "reward_coins": 250, "reward_rp": 50,
         "difficulty": "hard", "requirements": {"weather": "STORM"}},
    ]
    await db.quests.insert_many(quests)
    print("[SIGNAL CITY] ✓ Seeded 10 default quests")
