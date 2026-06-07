"""
algorithms/graph.py — WeightedGraph data structure for Signal City.
Central graph representation used by all algorithm implementations.
"""

import math


class WeightedGraph:
    """Weighted undirected graph optimized for algorithm visualization."""

    def __init__(self):
        self.nodes: dict[int, dict] = {}      # node_id → {x, y, lat, lon, pop_weight}
        self.adj: dict[int, list] = {}         # node_id → [{to, weight, capacity, edge_id, length_m}]
        self.edge_index: dict = {}             # (u, v) → index in adj list
        self.node_count: int = 0
        self.edge_count: int = 0
        self._edge_list: list = []

    @classmethod
    def from_json(cls, data: dict) -> 'WeightedGraph':
        """Build graph from JSON dict (pipeline output format)."""
        g = cls()
        for n in data.get("nodes", []):
            nid = n["id"]
            g.nodes[nid] = {
                "x": n["x"],
                "y": n["y"],
                "lat": n.get("lat", 0),
                "lon": n.get("lon", 0),
                "pop_weight": n.get("pop_weight", 1.0),
            }
            g.adj[nid] = []

        edge_id = 0
        for e in data.get("edges", []):
            u, v = e["u"], e["v"]
            weight = e.get("weight", 1.0)
            capacity = e.get("capacity", 800)
            length_m = e.get("length_m", 100.0)
            speed_kph = e.get("speed_kph", 30.0)

            if u not in g.adj:
                g.adj[u] = []
            if v not in g.adj:
                g.adj[v] = []

            edge_data_uv = {
                "to": v, "weight": weight, "capacity": capacity,
                "edge_id": edge_id, "length_m": length_m, "speed_kph": speed_kph,
            }
            edge_data_vu = {
                "to": u, "weight": weight, "capacity": capacity,
                "edge_id": edge_id, "length_m": length_m, "speed_kph": speed_kph,
            }

            g.adj[u].append(edge_data_uv)
            g.adj[v].append(edge_data_vu)
            g.edge_index[(u, v)] = len(g.adj[u]) - 1
            g.edge_index[(v, u)] = len(g.adj[v]) - 1
            g._edge_list.append({"u": u, "v": v, "weight": weight, "capacity": capacity,
                                 "length_m": length_m, "edge_id": edge_id})
            edge_id += 1

        g.node_count = len(g.nodes)
        g.edge_count = edge_id
        return g

    def neighbors(self, node_id: int) -> list:
        """Returns list of {to, weight, capacity, edge_id}."""
        return self.adj.get(node_id, [])

    def get_edge_weight(self, u: int, v: int) -> float:
        """Get weight of edge (u, v). Returns inf if not found."""
        for e in self.adj.get(u, []):
            if e["to"] == v:
                return e["weight"]
        return float("inf")

    def get_edge_capacity(self, u: int, v: int) -> int:
        """Get capacity of edge (u, v)."""
        for e in self.adj.get(u, []):
            if e["to"] == v:
                return e.get("capacity", 800)
        return 0

    def get_all_edges(self) -> list:
        """Return list of all unique edges as (u, v, weight, capacity)."""
        return self._edge_list

    def apply_weather_event(self, event: dict) -> list:
        """
        Apply weather effects to edges.
        STORM: halves capacity, doubles weight
        RAIN: multiplies weight by 1.5
        FOG: marks edges with fog=True
        BLIZZARD: triples weight, 30% capacity
        Returns list of modified edge tuples for frontend.
        """
        wtype = event.get("type", "CLEAR")
        affected_edges = event.get("affected_edges", [])
        modified = []

        weight_mult = event.get("effect_weight_multiplier", 1.0)
        cap_mult = event.get("effect_capacity_multiplier", 1.0)

        for edge_info in affected_edges:
            u = edge_info.get("u", 0)
            v = edge_info.get("v", 0)

            for e in self.adj.get(u, []):
                if e["to"] == v:
                    old_weight = e["weight"]
                    e["weight"] = round(e["weight"] * weight_mult, 3)
                    e["capacity"] = int(e["capacity"] * cap_mult)
                    if wtype == "FOG":
                        e["fog"] = True
                    modified.append({
                        "u": u, "v": v,
                        "old_weight": old_weight,
                        "new_weight": e["weight"],
                        "weather": wtype,
                    })
                    break

            for e in self.adj.get(v, []):
                if e["to"] == u:
                    e["weight"] = round(e["weight"] * weight_mult, 3)
                    e["capacity"] = int(e["capacity"] * cap_mult)
                    if wtype == "FOG":
                        e["fog"] = True
                    break

        return modified

    def to_json(self) -> dict:
        """Serialize back to JSON-safe dict."""
        nodes = []
        for nid, ndata in sorted(self.nodes.items()):
            nodes.append({"id": nid, **ndata})

        edges = []
        seen = set()
        for nid in sorted(self.adj.keys()):
            for e in self.adj[nid]:
                key = (min(nid, e["to"]), max(nid, e["to"]))
                if key not in seen:
                    seen.add(key)
                    edges.append({
                        "u": key[0], "v": key[1],
                        "weight": e["weight"],
                        "capacity": e.get("capacity", 800),
                        "length_m": e.get("length_m", 100),
                    })

        return {
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "nodes": nodes,
            "edges": edges,
        }

    def subgraph_bbox(self, min_x, min_y, max_x, max_y) -> 'WeightedGraph':
        """Returns subgraph within bounding box."""
        sub = WeightedGraph()
        valid_nodes = set()
        for nid, ndata in self.nodes.items():
            if min_x <= ndata["x"] <= max_x and min_y <= ndata["y"] <= max_y:
                valid_nodes.add(nid)
                sub.nodes[nid] = ndata.copy()
                sub.adj[nid] = []

        edge_id = 0
        for nid in valid_nodes:
            for e in self.adj.get(nid, []):
                if e["to"] in valid_nodes:
                    sub.adj[nid].append({**e, "edge_id": edge_id})
                    edge_id += 1

        sub.node_count = len(sub.nodes)
        sub.edge_count = edge_id // 2
        return sub

    def degree(self, node_id: int) -> int:
        """Return degree of a node."""
        return len(self.adj.get(node_id, []))

    def avg_degree(self) -> float:
        """Return average degree."""
        if self.node_count == 0:
            return 0
        return sum(len(self.adj.get(n, [])) for n in self.nodes) / self.node_count

    def node_position(self, node_id: int) -> tuple:
        """Return (x, y) position of a node."""
        n = self.nodes.get(node_id, {})
        return (n.get("x", 0), n.get("y", 0))
