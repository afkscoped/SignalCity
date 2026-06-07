# 🏙️ SIGNAL CITY — Algorithm City Simulator

> Build cities with real algorithms. An educational 3D strategy game powered by Prim, Dijkstra, Max-Flow, and cutting-edge graph algorithms on real OpenStreetMap data.

## 🎮 Features

- **10 Algorithms** visualized step-by-step in 3D:
  - Prim's MST, Kruskal's MST, Dijkstra's Shortest Path
  - Edmonds-Karp Max Flow, EDF/SJF/FCFS/Round Robin Scheduling
  - Leiden Community Detection, Contraction Hierarchies, k-Median Facility Location, PageRank Centrality
- **Real city data** from OpenStreetMap (Bengaluru, London, Tokyo, NYC, Sydney)
- **RPG progression** — levels, XP, gold coins, quest system
- **Character classes** — Algorithm Mage, Chrono Strategist, Flow Architect, Data Ranger
- **Weather events** — storms, rain, fog, blizzards dynamically alter the graph
- **XAI explanations** — plain-English explanation for every algorithm step
- **Complexity dashboard** — live operation counts, Big-O progress bars

## 🚀 Quick Start

```bash
cd signal_city
pip install -r requirements.txt
python server.py
```

The browser will automatically open to `http://localhost:8000`.

## 🏗️ Tech Stack

- **Backend**: Python 3.11, FastAPI, OSMnx, NetworkX, SQLite
- **Frontend**: Three.js (3D), D3.js (charts), Tailwind CSS, vanilla JavaScript
- **All libraries via CDN** — no build step, no npm

## 📁 Project Structure

```
signal_city/
├── server.py              # FastAPI entry point
├── requirements.txt       # Python dependencies
├── algorithms/            # All algorithm implementations (generators)
│   ├── graph.py           # WeightedGraph data structure
│   ├── mst.py             # Prim + Kruskal
│   ├── dijkstra.py        # Dijkstra shortest path
│   ├── flow.py            # Edmonds-Karp max flow
│   ├── scheduling.py      # EDF, SJF, FCFS, Round Robin
│   ├── leiden.py           # Leiden community detection
│   ├── contraction.py      # Contraction hierarchies
│   ├── facility.py         # k-Median facility location
│   └── pagerank.py         # PageRank centrality
├── pipeline/              # Data fetching and preprocessing
│   ├── osm_fetcher.py     # OSM data with fallback
│   ├── preprocessor.py    # Graph normalization
│   └── weather.py         # Weather simulation
└── static/                # Frontend
    ├── index.html          # Game UI
    └── js/                 # ES modules
        ├── main.js         # Scene + game orchestration
        ├── city.js         # Three.js 3D city builder
        ├── algorithms.js   # WebSocket + animation
        ├── hud.js          # HUD panels + Gantt + flow
        ├── tutorial.js     # 7-step tutorial
        ├── xai.js          # Explainable AI panel
        └── analytics.js    # Run tracking + export
```

## 📚 Research-Based Algorithms

| Algorithm | Paper | Game Application |
|-----------|-------|-----------------|
| Leiden | Traag et al., 2019 | City district zoning |
| Contraction Hierarchies | Geisberger et al., 2012; SPoCH 2023 | Emergency vehicle routing |
| k-Median Facility Location | Jain & Vazirani, 2001; Fair Outliers 2023 | Hospital/fire station placement |
| PageRank | Brin & Page, 1998; modern graph analytics | Commercial hub identification |

## 🎲 Game Mechanics

- **Level 1–50**: XP curve = `100 × level^1.5`
- **Algorithm unlock tiers**: higher tiers need more levels
- **Quests**: complete algorithmic challenges for XP + gold
- **Weather events**: dynamically modify edge weights/capacities
- **Happiness**: computed from infrastructure coverage

## License

MIT
