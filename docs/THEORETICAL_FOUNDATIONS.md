# DAA Signal City: Theoretical Foundations of Algorithms

This document provides a concise theoretical summary (maximum 5 lines per algorithm) for every algorithm used in the Signal City simulator and the Impact Console experiments, detailing their steps, complexity, integration, and role.

---

## Part 1: Core Simulator Algorithms (Mode 1 & Mode 2)

### 1. Prim's Algorithm (Minimum Spanning Tree)
- **Steps & Mechanism**: Starts from a source vertex, maintains a min-priority queue of frontier edges, greedily extracts the cheapest edge connecting to an unvisited node, and relaxes its neighbors.
- **Integration & Role**: Integrated as a step-by-step WebSocket generator. Used to construct the city's power/fiber utility backbone grid with minimum total line construction cost.
- **Complexity**: $O((V + E) \log V)$ using a binary min-heap priority queue.

### 2. Kruskal's Algorithm (Minimum Spanning Tree)
- **Steps & Mechanism**: Collects all graph edges, sorts them by weight, iterates through the sorted list, and accepts edges that connect disjoint components using a Union-Find (Disjoint Set Union) structure to prevent cycles.
- **Integration & Role**: Runs as an active WebSocket generator. Serves as a global comparison benchmark against Prim's local frontier strategy for building the optimal utility backbone.
- **Complexity**: $O(E \log E)$ for sorting, with Union-Find operations running in near-constant $O(E \cdot \alpha(V))$ time.

### 3. Dijkstra's Algorithm (Shortest Path)
- **Steps & Mechanism**: Initializes all node distances to $\infty$ (source to 0), relaxes adjacent edges greedily using a min-heap, and marks nodes as settled once popped.
- **Integration & Role**: Runs with early termination to calculate shortest routes between selected terminals. Used for vehicle routing, latency estimation, and baseline travel-time calculations.
- **Complexity**: $O((V + E) \log V)$ using a min-heap.

### 4. Contraction Hierarchies (Preprocessed Routing)
- **Steps & Mechanism**: Preprocesses the graph by contracting nodes in order of importance, adding shortcut edges to preserve shortest paths, and runs a bidirectional Dijkstra search.
- **Integration & Role**: Implemented as the high-tier routing algorithm. Simulates commercial mapping services by accelerating path queries by up to 100x compared to standard Dijkstra.
- **Complexity**: Preprocessing: $O(V(V + E) \log V)$; Query time: $O(\sqrt{V} \log \sqrt{V})$ (typically microseconds).

### 5. Edmonds-Karp Algorithm (Maximum Flow)
- **Steps & Mechanism**: Iteratively finds augmenting paths from source to sink using Breadth-First Search (BFS) and updates residual capacities until no more augmenting paths exist.
- **Integration & Role**: Exposed as the traffic throughput solver. Calculates maximum vehicles per hour between districts and identifies bottleneck edges (min-cut roads) for lane expansions.
- **Complexity**: $O(V E^2)$ since BFS guarantees shortest augmenting paths.

### 6. Leiden Algorithm (Community Detection)
- **Steps & Mechanism**: Optimizes partition modularity by moving nodes locally, refining partitions, and aggregating communities iteratively to guarantee well-connected groups.
- **Integration & Role**: Groups the road network into administrative districts. Used to determine spatial zones for local public services, police stations, and neighborhood boundaries.
- **Complexity**: Near-linear $O(E)$ per refinement pass.

### 7. Louvain Algorithm (Community Detection)
- **Steps & Mechanism**: Performs local modularity optimization greedily, collapses communities into meta-nodes, and repeats hierarchically until modularity stops increasing.
- **Integration & Role**: Benchmarked against Leiden for community districting quality to show modularity-based graph partitioning trade-offs.
- **Complexity**: $O(E \log V)$ on average.

### 8. PageRank Centrality (Node Importance)
- **Steps & Mechanism**: Simulates random walks across road segments with a damping factor ($d=0.85$), iteratively updating node probability vectors until convergence.
- **Integration & Role**: Measures junction influence. Ranks intersections to recommend which traffic lights require priority signaling or police inspection.
- **Complexity**: $O(k \cdot E)$ where $k$ is the number of power iterations.

---

## Part 2: Impact Console Algorithms (8 Experiments)

### 9. Dijkstra vs. Flood/Risk-Aware Rerouting (Route Lab)
- **Steps & Mechanism**: Compares standard Dijkstra against a modified version that scales edge weights by safety weights ($w_{new} = w_{old} \times (1 + \alpha \cdot \text{risk})$) to avoid high-accident and flooded nodes.
- **Integration & Role**: Runs as the Route Lab comparison tool. Helps planners evaluate trade-offs between travel times, CPU query load, and safety metrics.
- **Complexity**: $O((V + E) \log V)$ per algorithm run.

### 10. Iterative Penalty-based K-Shortest Paths (Resilient K-Routes)
- **Steps & Mechanism**: Finds the shortest path, applies a multiplicative penalty factor to its edges, runs Dijkstra again to find distinct alternatives, and scores them by overlap.
- **Integration & Role**: Serves as the Resilience KSP planner. Generates emergency evacuation portfolios so that if primary arterial streets flood, distinct detour options are available.
- **Complexity**: $O(k(V + E) \log V)$ where $k$ is the number of detours.

### 11. Grey Wolf Optimizer Siting (Classic Siting)
- **Steps & Mechanism**: Runs a population-based search tracking Alpha, Beta, and Delta wolves to minimize average Dijkstra distance from demand centers to $k$ facility points.
- **Integration & Role**: Powers the Classic Siting tab. Places fire stations or clinics to minimize global response times while treating start/end nodes as pre-existing facilities.
- **Complexity**: $O(I \times P \times k(V + E) \log V)$ where $I$ = iterations and $P$ = population size.

### 12. NSGA-II Multi-Objective Evolutionary Optimizer (NSGA-II Siting)
- **Steps & Mechanism**: Uses non-dominated sorting and crowding distance crowding selection to evolve candidate facility layouts across three conflicting objectives (budget, time, equity).
- **Integration & Role**: Drives the NSGA-II Siting tab. Outputs a Pareto frontier of layouts, showing planners the trade-off between installation cost and access equity (Gini coefficient).
- **Complexity**: $O(G \times P \times k(V + E) \log V + G \times P^2 \times M)$ where $G$ = generations, $P$ = population, and $M$ = objectives.

### 13. Brandes' Betweenness Centrality (Street Centrality)
- **Steps & Mechanism**: Accumulates dependency scores via SSSP DAGs in a backward pass from a set of pivot sources ($k=40$) to estimate node path frequencies.
- **Integration & Role**: Powers the Centrality tab. Highlights the city's key structural spines (top 10% integration corridors) requiring zoning changes or transit lanes.
- **Complexity**: $O(k(V + E) \log V)$ using the pivot approximation.

### 14. Bounded Dijkstra Accessibility Zones (Isochrone Bands)
- **Steps & Mechanism**: Runs Dijkstra SSSP radiating outwards from selected coordinate nodes and terminates immediately once path distances exceed a 15-minute walking cutoff.
- **Integration & Role**: Drives the Isochrones tab. Groups reachable nodes into 5, 10, and 15-minute bands to identify walking accessibility deficits.
- **Complexity**: $O((V' + E') \log V')$ where $V'$ and $E'$ are local nodes/edges inside the cutoff boundary.

### 15. BFS/DFS Connected Components decay (Percolation Test)
- **Steps & Mechanism**: Shuffles all edges, removes them in incremental batches (representing uniform damage), and runs BFS/DFS to track the decay of the Giant Connected Component (GCC).
- **Integration & Role**: Powers the Percolation tab. Simulates systemic road failure under monsoons and shows the critical threshold where the city fractures into isolated subgrids.
- **Complexity**: $O(S \times (V + E))$ where $S$ is the number of decay steps.

### 16. Spatial Nearest-Neighbor vulnerability mapping (Digital Twin)
- **Steps & Mechanism**: Maps continuous crash risks using an inverse-distance decay function ($1/(d_{crash} + 0.1)$), intersects it with flood zones, and evaluates composite route risk.
- **Integration & Role**: Operates the Digital Twin. Visualizes city-wide hazard density in 3D extrusion heights and rates selected start-to-end corridors for planners.
- **Complexity**: $O(V \times C)$ where $C$ is the number of crash blackspots, plus path evaluations.
