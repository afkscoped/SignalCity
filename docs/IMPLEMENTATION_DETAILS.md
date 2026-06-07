# 🏙️ Signal City — Implementation Details & System Architecture

Welcome to the comprehensive implementation documentation of **Signal City (v2.0)**, a gamified algorithm strategy simulator and laboratory manual designed for the university **Design and Analysis of Algorithms (CS-401)** course.

This document details the backend architecture, frontend clients, database layers, grading formulas, and the full catalog of **33+ algorithms** that are implemented and running.

---

## 1. System Architecture Overview

Signal City is built with a **decoupled, full-stack architecture** optimized for lightweight local deployment and immediate offline execution without heavy external dependencies or node package compilation.

```
+---------------------------------------------------------------------------------+
|                                 FRONTEND CLIENT                                 |
|   +---------------------------------------+   +-----------------------------+   |
|   |         MODE 1: LEAFLET.JS            |   |     MODE 2: PHASER.JS       |   |
|   |   Geographical OpenStreetMap View     |   |   Isometric Hex Builder     |   |
|   +---------------------------------------+   +-----------------------------+   |
|                       |                                      |                  |
+-----------------------|--------------------------------------|------------------+
                        | HTTP REST / WebSocket                | HTTP REST / WebSocket
                        v                                      v
+---------------------------------------------------------------------------------+
|                            FASTAPI BACKEND ENGINE                               |
|                                                                                 |
|   +------------------+  +-------------------+  +------------------+             |
|   |  routers/city.py |  |routers/game.py    |  |routers/nlp.py    |             |
|   |  OSM Data/Cache  |  |Hex Placements     |  |Groq & Regex Parse|             |
|   +------------------+  +-------------------+  +------------------+             |
|             |                     |                      |                      |
|             +---------------------+----------------------+                      |
|                                   |                                             |
|                                   v                                             |
|                        +----------------------+                                 |
|                        | routers/algorithms.py|                                 |
|                        |  Execution Engine    |                                 |
|                        +----------------------+                                 |
|                                   |                                             |
|                                   v                                             |
|                        +----------------------+                                 |
|                        |    algorithms/       |                                 |
|                        |  33+ Gen Loops       |                                 |
|                        +----------------------+                                 |
+-----------------------------------|---------------------------------------------+
                                    v
+---------------------------------------------------------------------------------+
|                                DATABASE LAYER                                   |
|       +-----------------------------------------------------------------+       |
|       |                     database/connection.py                      |       |
|       |                                                                 |       |
|       |   If MONGODB_URI is set:             If MONGODB_URI is empty:   |       |
|       |      Motor client -> MongoDB            In-Memory Mock DB       |       |
|       +-----------------------------------------------------------------+       |
+---------------------------------------------------------------------------------+
```

### 1.1 Backend Router Decoupling
To keep the codebase modular, routes are isolated under the `routers/` directory:
- [city.py](file:///c:/Users/raddo/Documents/daa%20el%204th%20sem%202nd/signal_city/routers/city.py): Geocodes cities, handles local JSON/GraphML caching, and coordinates openstreetmap loadings.
- [algorithms.py](file:///c:/Users/raddo/Documents/daa%20el%204th%20sem%202nd/signal_city/routers/algorithms.py): Dispatches algorithms and handles the WebSocket generator streaming loop.
- [nlp.py](file:///c:/Users/raddo/Documents/daa%20el%204th%20sem%202nd/signal_city/routers/nlp.py): Integrates with the Groq LLaMA-3 model to parse commands with a regex keyword matcher fallback.
- [game.py](file:///c:/Users/raddo/Documents/daa%20el%204th%20sem%202nd/signal_city/routers/game.py): Tracks hex tile building coordinates, municipal stats, and power grid wiring in Mode 2.

### 1.2 In-Memory Database Fallback
The database connection in [connection.py](file:///c:/Users/raddo/Documents/daa%20el%204th%20sem%202nd/signal_city/database/connection.py) detects the presence of `MONGODB_URI` in `.env`.
* **Standard Mode**: Connects asynchronously to MongoDB using the `motor` driver, creating unique indexes for fast lookups.
* **Offline Fallback Mode**: Instantiates an asynchronous mock database (`_MemoryDB`, `_MemoryCollection`, and `_MemoryCursor`) which implements the standard Motor driver API. Quests, users, and caches are seeded and run entirely in memory.

### 1.3 Secure Cryptographic Hashing
To bypass compatibility issues of standard hashing libraries like `passlib` on newer Python runtimes (e.g. Python 3.14):
* [auth/password.py](file:///c:/Users/raddo/Documents/daa%20el%204th%20sem%202nd/signal_city/auth/password.py) implements custom hashing using `hashlib.sha256` combined with a cryptographically secure 16-byte random salt.
* Password validation utilizes constant-time comparison via `hmac.compare_digest` to prevent timing-attack exploits.

---

## 2. Theoretical Codex of the 33+ Algorithms

Each algorithm yields state representations step-by-step (`yield`) using a custom `GraphDelta` protocol streamed over WebSockets to client visualizations.

### 2.1 Graph Optimization & Routing
1. **Prim's MST** ($O(E \log V)$)
   - **Formula**: $e = \text{argmin} \{ w(u,v) \mid u \in S, v \notin S \}$
   - **Municipal Use**: Connects electricity grid structures with minimal layout cables.
2. **Kruskal's MST** ($O(E \log E)$)
   - **Formula**: Union-Find disjoint sets sorting edges to prevent cyclic closures.
   - **Municipal Use**: Regional transit pipeline network connecting distant hubs.
3. **Dijkstra's Shortest Path** ($O((V + E) \log V)$)
   - **Formula**: Relaxation step: $dist[u] + w(u,v) < dist[v] \implies dist[v] = dist[u] + w(u,v)$
   - **Municipal Use**: Standard emergency ambulance routing between nodes.
4. **Contraction Hierarchies** (Fast Query, $O((V+E)\log V)$ Preprocessing)
   - **Formula**: Contract nodes based on 'importance' and inject shortcut edges.
   - **Municipal Use**: Accelerated logistics dispatch calculations.
5. **Edmonds-Karp Max Flow** ($O(V E^2)$)
   - **Formula**: BFS searching augmenting paths in residual graph $r(u,v) = c(u,v) - f(u,v)$.
   - **Municipal Use**: Water main and heavy traffic capacity routing.
6. **Leiden Community Detection** ($O(V \log V)$)
   - **Formula**: Maximizes modularity $Q$ ensuring sub-communities remain connected.
   - **Municipal Use**: Automates municipal administrative district zoning.
7. **PageRank Centrality** ($O(V + E)$ per iteration)
   - **Formula**: $PR(u) = \frac{1-d}{N} + d \sum_{v \in B_u} \frac{PR(v)}{L(v)}$
   - **Municipal Use**: Ranks commercial hubs based on node connectivity profiles.
8. **k-Median Facility Location** ($O(k \cdot V \cdot E)$ approximation)
   - **Formula**: Minimizes $\sum_{v \in V} \min_{f \in F} dist(v, f)$
   - **Municipal Use**: Optimal placement of hospital centers.

### 2.2 Swarm Intelligence & Metaheuristics
These algorithms simulate biological swarming mechanisms to search coordinate spaces for municipal placements.
9. **Grey Wolf Optimizer (GWO)**: Models hierarchy (Alpha, Beta, Delta wolves) hunting prey nodes.
10. **Whale Optimization (WOA)**: Simulates bubble-net hunting spirals.
11. **Ant Lion Optimizer (ALO)**: Simulates random walks inside sand traps.
12. **Harris Hawks Optimization (HHO)**: Simulates surprise pouncing and soft/hard besieges.
13. **Coati Optimization (COA)**: Simulates climbing trees and predator escapes.
14. **Runge-Kutta Optimizer (RKO)**: Integrates search paths numerically using Runge-Kutta math.
15. **Painting Training Optimizer (PTBO)**: Simulates learner artists refining styles based on teacher templates.
16. **Marine Predators (MPA)**: Brownian and Levy movement steps.
17. **Moth-Flame Optimization (MFO)**: Moths spiraling around flames.
18. **Grasshopper Optimization (GOA)**: Swarm vector calculations based on attraction-repulsion formulas.
19. **Aquila Optimizer (AO)**: High soar, low glide, and vertical pouncing mechanics.
20. **Dandelion Optimizer (DO)**: Simulates seeds floating on atmospheric wind currents.
21. **Salp Swarm Algorithm (SSA)**: Simulates a chain of salps seeking food sources.
22. **Slime Mould Algorithm (SMA)**: Physarum feedback loops thickening channels and contracting paths.
23. **Arithmetic Optimization (AOA)**: Restricts bounds via Multiplication, Division, Addition, and Subtraction.
24. **Gorilla Troops Optimizer (GTO)**: Troop migration routes.

### 2.3 Machine Learning & Neural Network Inference
These algorithms model neural features directly on city graph layouts.
25. **Transformer Attention**: Pairwise scaled dot-product attention mapping $Attention(Q, K, V) = \text{softmax}\left(\frac{QK^T}{\sqrt{d_k}}\right)V$ over node populations.
26. **KAN Splines**: Learns univariate B-splines directly on edge transitions to predict road traffic delays.
27. **Swin Zoning**: Local window-shifted self-attention to cluster municipal coordinates.
28. **Diffusion Density**: Iterative Gaussian denoising to generate building grid layouts.

### 2.4 Distributed Systems, Consensus & Scheduling
29. **Raft Consensus**: Follower, Candidate, and Leader heartbeats replicating configurations across substation hubs.
30. **XGBoost Split Finding**: Greedy exact splits optimizing local population boundaries.
31. **Count Sketch Streaming**: Frequency estimations of vehicle crossings using pairwise independent hash matrices.
32. **Learned Index (RMI)**: Recursive Model Index using linear models to predict physical array addresses of nodes.
33. **Earliest Deadline First (EDF)**: Schedules municipal tasks sorting by closest deadline.
34. **Shortest Job First (SJF)**: Minimizes waiting times by scheduling tasks by length.
35. **First-Come First-Served (FCFS)**: Sequential task scheduler queue.
36. **Round Robin (RR)**: Time-quantum sliced CPU scheduling.

### 2.5 Computational Geometry & Helpers
37. **Graham Scan**: Convex hull computations ($O(N \log N)$) identifying boundary vertices of a city zone.
38. **First-Fit Decreasing**: Approximates 1D bin packing to fit pipelines into fixed capacity holds.

---

## 3. Game Mechanics & Gamification Metrics

Signal City ties academic performance metrics to RPG progression mechanisms to motivate students to write optimized algorithms.

### 3.1 Big-O Operations Grading
Every run logs physical operational steps ($actual\_ops$) and computes a ratio against the theoretical Big-O boundary ($theoretical\_ops$) for the graph's size ($V$ nodes, $E$ edges):

$$\text{ratio} = \frac{\text{actual\_ops}}{\text{theoretical\_ops}}$$

The backend calculates a normalized efficiency score:

$$\text{efficiency\_score} = 100 \times \left(1 - \frac{\text{ratio} - 1}{2}\right) \quad (\text{clamped between } 0 \text{ and } 100)$$

Grades and resource rewards scale accordingly:

| Grade | Score Boundary | Ratio Requirement | Reward |
| :---: | :---: | :---: | :--- |
| **S** | $\ge 95$ | $\text{ratio} \le 1.10$ | +500 XP, +300 Gold, +50 RP |
| **A** | $\ge 80$ | $\text{ratio} \le 1.40$ | +300 XP, +200 Gold, +35 RP |
| **B** | $\ge 65$ | $\text{ratio} \le 1.70$ | +200 XP, +120 Gold, +20 RP |
| **C** | $\ge 50$ | $\text{ratio} \le 2.00$ | +100 XP, +60 Gold, +10 RP |
| **D** | $< 50$ | $\text{ratio} > 2.00$ | +50 XP, +20 Gold, +5 RP |

### 3.2 RPG Level Progression
XP limits to reach a level scale according to:

$$\text{XP\_needed} = 100 \times \text{level}^{1.5}$$

### 3.3 Guild Class Modifiers
Upon registration, players choose a class to gain unique benefits:
* **Algorithm Mage**: Starts with +50 Research Points.
* **Flow Architect**: Starts with +500 Gold Coins.
* **Chrono Strategist**: Doubles WebSocket simulation rates.
* **Data Ranger**: Basic search algorithms unlocked by default.

---

## 4. API Endpoint Index

| Method | Route | Description |
| :--- | :--- | :--- |
| **POST** | `/api/auth/register` | Registers user; hashes via SHA-256 PBKDF2. |
| **POST** | `/api/auth/login` | Returns secure JWT token credentials. |
| **GET** | `/api/auth/me` | Retrieves profile statistics. |
| **GET** | `/api/cities` | Lists Indian cities with coordinates. |
| **POST** | `/api/load-city` | Geocodes coordinates via OSMnx or loads fallback cache. |
| **POST** | `/api/nlp/parse` | Sends query to Groq LLaMA-3 or regex search. |
| **GET** | `/api/quests` | Lists quest contracts. |
| **POST** | `/api/game/place-building`| Registers hex coordinates and deducts construction coins. |

---

## 5. Quick Verification & Execution

To boot the server:
1. Initialize environment setup (creates `.env` file):
   ```bash
   python setup.py
   ```
2. Start the FastAPI Uvicorn server:
   ```bash
   python server.py
   ```
3. Open the client in a browser:
   ```
   http://localhost:8000
   ```
