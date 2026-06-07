import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from pathlib import Path

def create_document():
    doc = docx.Document()
    
    # Page setup - Margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # Style setup
    styles = doc.styles
    
    # Title style
    title_style = styles.add_style('GameTitle', docx.enum.style.WD_STYLE_TYPE.PARAGRAPH)
    title_font = title_style.font
    title_font.name = 'Cinzel'
    title_font.size = Pt(26)
    title_font.bold = True
    title_font.color.rgb = RGBColor(197, 160, 89) # Civ Gold

    # Subtitle style
    subtitle_style = styles.add_style('GameSubtitle', docx.enum.style.WD_STYLE_TYPE.PARAGRAPH)
    sub_font = subtitle_style.font
    sub_font.name = 'Marcellus'
    sub_font.size = Pt(12)
    sub_font.color.rgb = RGBColor(120, 130, 140) # Muted Silver

    # Heading 1 style
    h1_style = styles['Heading 1']
    h1_font = h1_style.font
    h1_font.name = 'Cinzel'
    h1_font.size = Pt(16)
    h1_font.bold = True
    h1_font.color.rgb = RGBColor(197, 160, 89)

    # Heading 2 style
    h2_style = styles['Heading 2']
    h2_font = h2_style.font
    h2_font.name = 'Marcellus'
    h2_font.size = Pt(12)
    h2_font.bold = True
    h2_font.color.rgb = RGBColor(223, 195, 138) # Civ Gold Light

    # Heading 3 style
    h3_style = styles['Heading 3']
    h3_font = h3_style.font
    h3_font.name = 'Marcellus'
    h3_font.size = Pt(10)
    h3_font.bold = True
    h3_font.color.rgb = RGBColor(100, 100, 100)

    # Normal text style
    normal_style = styles['Normal']
    normal_font = normal_style.font
    normal_font.name = 'Arial'
    normal_font.size = Pt(10)
    normal_font.color.rgb = RGBColor(30, 30, 30)

    # Code style
    code_style = styles.add_style('CodeText', docx.enum.style.WD_STYLE_TYPE.PARAGRAPH)
    code_font = code_style.font
    code_font.name = 'Consolas'
    code_font.size = Pt(8.5)
    code_font.color.rgb = RGBColor(0, 102, 204)

    # Helper function for adding styled paragraphs
    def add_para(text, style='Normal', space_after=6, space_before=0, bullet=False):
        p_style = 'List Bullet' if bullet else style
        p = doc.add_paragraph(text, style=p_style)
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.space_before = Pt(space_before)
        p.paragraph_format.line_spacing = 1.15
        return p

    def add_callout(text, title="NOTE"):
        tbl = doc.add_table(rows=1, cols=1)
        tbl.alignment = docx.enum.table.WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.cell(0, 0)
        
        # Shading
        shd_xml = r'<w:shd {} w:fill="F4F6F9"/>'.format(nsdecls('w'))
        shading = parse_xml(shd_xml)
        cell._tc.get_or_add_tcPr().append(shading)
        
        # Border (left thick bar)
        tcPr = cell._tc.get_or_add_tcPr()
        border_xml = r'<w:tcBorders {}><w:left w:val="single" w:sz="36" w:space="0" w:color="c5a059"/><w:top w:val="none"/><w:right w:val="none"/><w:bottom w:val="none"/></w:tcBorders>'.format(nsdecls('w'))
        tcBorders = parse_xml(border_xml)
        tcPr.append(tcBorders)
        
        p = cell.paragraphs[0]
        p.style = 'Normal'
        p.paragraph_format.left_indent = Inches(0.15)
        p.paragraph_format.space_after = Pt(2)
        run_title = p.add_run(f"[{title}] ")
        run_title.bold = True
        run_title.font.color.rgb = RGBColor(197, 160, 89)
        run_body = p.add_run(text)
        run_body.font.italic = True
        doc.add_paragraph() # spacing

    # --- TITLE PAGE ---
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(80)
    run_title = p_title.add_run("SIGNAL CITY v2.0:\nACADEMIC REPORT & CURRICULUM MANUAL")
    run_title.font.name = 'Cinzel'
    run_title.font.size = Pt(26)
    run_title.font.bold = True
    run_title.font.color.rgb = RGBColor(197, 160, 89)

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_after = Pt(140)
    run_sub = p_sub.add_run("An Immersive Gamified Laboratory Platform for CS-401: Design & Analysis of Algorithms\n"
                            "Full-Stack Decoupled Architecture, Swarm Intelligence, Neural District Zoning, "
                            "and Live Weather Systems")
    run_sub.font.name = 'Marcellus'
    run_sub.font.size = Pt(11)
    run_sub.font.color.rgb = RGBColor(100, 110, 120)

    p_meta = doc.add_paragraph()
    p_meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_meta = p_meta.add_run(
        "Course Alignment: Design & Analysis of Algorithms (CS-401)\n"
        "State of Implementation: Decoupled to sub-routers, Motor Async DB, Weather Engine\n"
        "Document Version: 3.0 (Overwritten Master Report)\n"
        "Date of Release: June 2026"
    )
    run_meta.font.name = 'Arial'
    run_meta.font.size = Pt(9.5)
    run_meta.font.italic = True
    run_meta.font.color.rgb = RGBColor(80, 80, 80)

    doc.add_page_break()

    # --- ABSTRACT ---
    doc.add_heading("ABSTRACT", level=1)
    add_para(
        "This report details the architectural transformation, theoretical underpinnings, and pedagogical "
        "implications of SIGNAL CITY v2.0. Signal City is an educational browser game designed for university-level "
        "courses in the Design and Analysis of Algorithms (DAA). Traditional algorithm visualizers isolate concepts, "
        "leaving students disconnected from how algorithmic performance affects system behaviors. "
        "Signal City v2.0 solves this issue by introducing a dual-mode gameplay loop: Mode 1 (Signal Map) uses real-world "
        "OpenStreetMap road networks and coordinates to run graph, swarm, and ML optimization algorithms; Mode 2 (Signal Forge) "
        "implements a Civilization 6-inspired city builder hex-grid powered by Phaser.js, where infrastructure connections "
        "are governed by strict algorithm execution constraints. The system has been fully re-engineered to run on a decoupled "
        "FastAPI backend, supported by an asynchronous MongoDB connection (with an offline in-memory fallback), JWT auth, and a "
        "real-time WebSocket algorithm streaming engine. Additionally, the project features a live weather integration powered "
        "by the OpenWeatherMap API that dynamically adjusts edge weights and capacities. An empirical efficiency scoring engine "
        "grades player runs against mathematical Big-O bounds, awarding gold and research points. This creates a tight loop "
        "connecting theoretical algorithmic complexity to tangible gameplay success."
    )
    doc.add_paragraph()

    # --- INTRODUCTION ---
    doc.add_heading("1. INTRODUCTION", level=1)
    add_para(
        "In modern computer science curricula, the Design and Analysis of Algorithms (DAA) course is foundational, "
        "establishing the conceptual framework required to evaluate computational tractability, spatial-temporal optimization, "
        "and data structure efficiency. However, a persistent pedagogical challenge is the disconnect between theoretical "
        "complexity classes (e.g., O(V log V) vs. O(V^2)) and their physical impact in complex software systems. Students "
        "frequently memorize recurrence relations and asymptotic bounds without developing an intuition for how algorithms "
        "dynamically scale, adapt to real-world datasets, or interact with changing system environments."
    )
    add_para(
        "Historically, educational software has relied on passive visualizers (e.g., sorting bars, abstract node graphs) "
        "that lack stakes or realistic system scale. SIGNAL CITY v2.0 addresses this challenge by wrapping 33 algorithm "
        "generators within an interactive, municipal strategy game. The application shifts the student's role from a passive "
        "observer to a city architect who must deploy algorithms to manage real-world road networks and procedural district "
        "layouts. Algorithm runtime metrics (operations executed, memory allocation, and wall-clock time) are mapped to game "
        "resources, rendering complexity analysis immediately relevant. This document details the rehaul architecture, the "
        "theoretical foundations of the algorithms, and the results of this gamified educational environment."
    )
    doc.add_paragraph()

    # --- PROBLEM DEFINITION ---
    doc.add_heading("2. PROBLEM DEFINITION & SCOPE", level=1)
    add_para(
        "The original iteration (v1.0) of Signal City functioned primarily as a local simulator with several architectural "
        "limitations. First, the database was built on SQLite, which blocked asynchronous connection pooling, making it "
        "incompatible with multi-user laboratory environments. Second, the frontend relied on a single Three.js canvas that, "
        "while functionally visual, lacked clear gameplay loops, structured economics, or clear progression rules. "
        "Third, algorithms were fully unlocked from the start, bypassing level-progression incentives. Fourth, the map engine "
        "lacked geographic detail, displaying abstract graphs rather than recognizable urban layouts."
    )
    add_para(
        "The scope of the v2.0 overhaul was defined by five key requirements:\n"
        "1. Re-engineer the database layer to utilize MongoDB via the motor async driver, while preserving a pure-Python "
        "asynchronous database fallback to ensure immediate execution in environment configurations lacking external db servers.\n"
        "2. Introduce a dual-mode visualization client: Mode 1 rendering actual Indian municipal topologies on Leaflet "
        "maps with detailed Point-of-Interest (POI) overlays; Mode 2 providing an interactive isometric city builder on a "
        "Phaser.js grid.\n"
        "3. Incorporate a gamified Technology Tree and Level Progression registry that gates access to algorithms, requiring "
        "players to spend Research Points (RP) earned through high-efficiency runs to unlock advanced code nodes.\n"
        "4. Develop game-theoretic challenges (Wardrop Equilibrium traffic congestion simulations and Edmonds-Karp min-cut "
        "security games) that demonstrate practical applications of algorithms.\n"
        "5. Integrate a live weather system using geocoded OpenWeatherMap queries that overlays canvas animations and "
        "dynamically scales edge weights, forcing players to adapt their layouts to environmental shifts."
    )
    doc.add_paragraph()

    # --- OBJECTIVES ---
    doc.add_heading("3. OBJECTIVES", level=1)
    add_para(
        "The main objective of SIGNAL CITY v2.0 is to establish an active, gamified learning laboratory for algorithm analysis. "
        "This is broken down into specific technical goals:\n"
        "Pedagogical Objectives:\n"
        "- Enable students to visually observe algorithm execution steps (relaxations, tree contractions, partition updates) "
        "and compare empirical operation counts directly with theoretical asymptotic bounds.\n"
        "- Demonstrate how algorithms solve real-world problems by routing traffic, placing facilities, and zoning districts.\n"
        "Technical Objectives:\n"
        "- Develop a decoupled, sub-routed backend using FastAPI to manage endpoints for authentication, geocoding, and "
        "game state synchronization.\n"
        "- Implement an asynchronous WebSocket protocol to stream step-by-step algorithm states from Python generators "
        "to Javascript clients without blocking server threads.\n"
        "- Design a high-performance particle system on HTML5 canvas layers that overlays both maps and Phaser viewports to "
        "render weather conditions (STORM, RAIN, BLIZZARD, FOG, CLEAR) without dropping frame rates.\n"
        "- Formulate a math-based grading model (S, A, B, C, D) that evaluates execution paths and rewards optimal "
        "parameter settings."
    )
    doc.add_paragraph()

    # --- METHODOLOGY WITH ARCHITECTURE ---
    doc.add_heading("4. METHODOLOGY & ARCHITECTURE", level=1)
    add_para(
        "The architecture of Signal City v2.0 is designed around a decoupled, client-server paradigm. "
        "The backend serves as the core calculation engine, written in Python, exposing a series of REST endpoints and a "
        "WebSocket server. The client is a vanilla JavaScript client that communicates with the server via HTTP requests "
        "and WebSockets."
    )
    
    doc.add_heading("4.1 System Architecture Diagram", level=2)
    add_para(
        "The following text-based block diagram shows the system layout, showing the interaction between the "
        "frontend clients, the decoupled FastAPI sub-routers, the database handlers, and external services:"
    )
    
    # Text Architecture Callout
    arch_tbl = doc.add_table(rows=1, cols=1)
    arch_tbl.alignment = docx.enum.table.WD_TABLE_ALIGNMENT.CENTER
    a_cell = arch_tbl.cell(0, 0)
    a_cell._tc.get_or_add_tcPr().append(parse_xml(r'<w:shd {} w:fill="F1F3F5"/>'.format(nsdecls('w'))))
    a_para = a_cell.paragraphs[0]
    a_para.style = 'CodeText'
    a_para.add_run(
        "+-------------------------------------------------------------------------------+\n"
        "|                         FRONTEND CLIENT (HTML5 / CSS3 / ES6 JS)                |\n"
        "|  +-----------------------------------+   +---------------------------------+  |\n"
        "|  |   Mode 1: Leaflet OSM Map Game    |   |   Mode 2: Phaser Hex-Grid Game  |  |\n"
        "|  |   (Geocoded POIs, Tooltips)       |   |   (Economy, District Adjacency) |  |\n"
        "|  +-----------------------------------+   +---------------------------------+  |\n"
        "|    | (REST API Calls)                      | (WebSocket Connection)           |\n"
        "+----+---------------------------------------+----------------------------------+\n"
        "     |                                       |\n"
        "     v                                       v\n"
        "+-------------------------------------------------------------------------------+\n"
        "|                       FASTAPI ASGI BACKEND (PORT 8000)                        |\n"
        "|  +-----------------------------------+   +---------------------------------+  |\n"
        "|  |     REST Router endpoints:        |   |      WebSocket Channel:         |  |\n"
        "|  |  /auth, /load-city, /quests, etc. |   |      /ws/algorithm (Streaming)  |  |\n"
        "|  +-----------------------------------+   +---------------------------------+  |\n"
        "|                                |                                              |\n"
        "|                                v                                              |\n"
        "|                  +---------------------------+                                |\n"
        "|                  | Algorithm Generator Loop  |                                |\n"
        "|                  |   (33 DAA Generators)     |                                |\n"
        "|                  +---------------------------+                                |\n"
        "+--------------------------------|----------------------------------------------+\n"
        "                                 v\n"
        "+-------------------------------------------------------------------------------+\n"
        "|                              DATABASE LAYER                                   |\n"
        "|    +----------------------------------+  +--------------------------------+   |\n"
        "|    |    MongoDB Atlas (Motor Driver)  |  |    Asynchronous Memory DB      |   |\n"
        "|    |    (Persistent Profiles/Leader)  |  |    (Offline fallback system)   |   |\n"
        "|    +----------------------------------+  +--------------------------------+   |\n"
        "+-------------------------------------------------------------------------------+\n"
        "                                 |\n"
        "                                 v (External API Sync)\n"
        "+-------------------------------------------------------------------------------+\n"
        "|         OpenWeatherMap API       |            Overpass API (OSM)              |\n"
        "+-------------------------------------------------------------------------------+\n"
    )
    doc.add_paragraph()

    doc.add_heading("4.2 Communication and Execution Protocol", level=2)
    add_para(
        "When a user logs in, their profile (level, coins, unlocked algorithms) is retrieved from the database. "
        "In Mode 1, selecting a city prompts a request to `/api/load-city`. The backend resolves this query by "
        "checking a local GraphML folder. If missing, it uses an asynchronous HTTP call to the OpenStreetMap "
        "Overpass API, downloading and parsing the city's drivable roads into a NetworkX graph, which is then enriched "
        "with amenity node metadata (hospitals, schools, parks) and saved in the database."
    )
    add_para(
        "Concurrently, the backend retrieves the city's coordinates and contacts the OpenWeatherMap API (using the "
        "`OWM_API_KEY` in `.env`). The retrieved weather condition is passed to `WeatherEngine`, which selects a set of "
        "edges (prioritizing high-density central nodes) and adjusts their travel weights and throughput capacities. "
        "When an algorithm run is triggered, the client connects to `/ws/algorithm` and submits the task. The server "
        "applies the active weather offsets, instantiates the algorithm generator, and streams step-by-step updates "
        "until the solution is found. It then grades the run and updates the player's level and resources."
    )
    add_para(
        "In Mode 2, the Phaser client manages placing custom building tiles. Upon pressing **End Turn**, the game state is "
        "updated, checking adjacency constraints (e.g., commercial hubs near factories, or residential units near schools) "
        "and running connectivity checks. The server then cycles the weather, shifting HUD readouts and starting "
        "new canvas animations on the client."
    )
    doc.add_paragraph()

    # --- CORE IMPLEMENTATION DETAILS ---
    doc.add_heading("5. CORE IMPLEMENTATION DETAILS", level=1)
    
    doc.add_heading("5.1 Modular Decoupled Routing Directory", level=2)
    add_para(
        "To prevent code bloat, all backend endpoints are modularized in the `routers/` directory, using `APIRouter` "
        "decorators registered in `server.py`:\n"
        "1. routers/city.py: manages city geocoding, caches city structures, and exposes the weather query endpoint.\n"
        "2. routers/algorithms.py: handles algorithm execution, actual operations calculation, and grading metrics.\n"
        "3. routers/nlp.py: resolves natural language commands into structured algorithm commands using Groq.\n"
        "4. routers/game.py: tracks hex placements, costs, and connections for Mode 2."
    )

    doc.add_heading("5.2 MongoDB Integration & Async In-Memory Database Fallback", level=2)
    add_para(
        "To support academic deployments without requiring complex configurations, the database layer "
        "in `database/connection.py` dynamically handles connection states. If `MONGODB_URI` is present in the `.env` "
        "file, the application initiates an asynchronous client via `motor.motor_asyncio.AsyncIOMotorClient`. If missing, "
        "the system initializes a custom mock database (`_MemoryDB`). This class replicates PyMongo/Motor's async "
        "API (supporting `find`, `insert_one`, `update_one`, and list sorting) using Python dictionaries. It seeds "
        "default quests, achievements, and leaderboard values at launch, ensuring full functionality in memory."
    )

    doc.add_heading("5.3 Custom Cryptographic Hashing (Python 3.14 Compatibility)", level=2)
    add_para(
        "During setup, modern Python environments (such as Python 3.14) throw errors when using older packages like "
        "`passlib`, which frequently call deprecated `__about__` parameters or rely on unmaintained C extensions. "
        "To resolve this, a custom, dependency-free cryptographic module was built in `auth/password.py`. It uses "
        "standard library `hashlib.pbkdf2_hmac` with a SHA-256 backend, a 16-byte random salt, and 100,000 hashing iterations. "
        "This secures user passwords while avoiding dependency errors."
    )

    doc.add_heading("5.4 Weather Engine and Viewport Canvas Overlay", level=2)
    add_para(
        "The weather system operates as a unified engine (`pipeline/weather.py`). When geocodes are loaded, the system "
        "queries the OpenWeatherMap API, falling back to a deterministic, hour-locked simulated weather scenario if the key "
        "is missing. This scenario defines weight and capacity multipliers. The canvas overlay on the client reads these "
        "parameters and draws particle animations (drops, snow circles, radial mist gradients) using a `requestAnimationFrame` "
        "loop. It also handles window resizing and runs at a smooth 60fps."
    )
    doc.add_paragraph()

    # --- THEORETICAL BLUEPRINT OF ALL 33+ ALGORITHMS ---
    doc.add_page_break()
    doc.add_heading("6. THEORETICAL BLUEPRINT OF ALGORITHMS", level=1)
    add_para(
        "Here we document the theoretical formulation, complexity profiles, and applications "
        "for the 33 algorithms in the Signal City registry, organized by category."
    )

    doc.add_heading("6.1 Graph Optimization, Pathfinding, and Flows", level=2)
    
    add_para("1. Prim's Minimum Spanning Tree (MST)", style='Heading 3')
    add_para("Theoretical Complexity: O(E log V) using a binary heap priority queue.", style='CodeText')
    add_para("Mathematical Invariant: e = argmin { w(u,v) | u in S, v not in S }", style='CodeText')
    add_para("Description: Prim's algorithm computes the MST of a weighted undirected graph. Starting from a source node, "
             "it greedily appends the lowest-weight edge that connects a vertex in the tree to a vertex outside it, updating "
             "the priority queue at each step.")
    add_para("Municipal Strategy: Optimizes power grid layouts, connecting substations with the minimum total cable length.")
    
    add_para("2. Kruskal's MST", style='Heading 3')
    add_para("Theoretical Complexity: O(E log E) due to edge sorting.", style='CodeText')
    add_para("Mathematical Invariant: Find(u) != Find(v) => Union(u, v) and add edge to tree", style='CodeText')
    add_para("Description: Kruskal's algorithm constructs the MST by sorting all edges and greedily adding them if they do not "
             "form a cycle, utilizing a Union-Find data structure with path compression to check connectivity in O(alpha(V)) time.")
    add_para("Municipal Strategy: Guides long-distance sewage and water pipeline layouts connecting municipal zones.")
    
    add_para("3. Dijkstra's Shortest Path", style='Heading 3')
    add_para("Theoretical Complexity: O((V + E) log V) with a Fibonacci or binary heap.", style='CodeText')
    add_para("Mathematical Invariant: dist[u] + w(u,v) < dist[v] => dist[v] = dist[u] + w(u,v) (Relaxation)", style='CodeText')
    add_para("Description: Finds the shortest path from a source to all other nodes. It repeatedly selects the unvisited node "
             "with the minimum tentative distance, relaxes its outgoing edges, and marks it as visited.")
    add_para("Municipal Strategy: Calculates commuter routing and vehicle transit paths, finding the fastest routes "
             "between residential districts and workplaces.")
    
    add_para("4. Edmonds-Karp Max Flow", style='Heading 3')
    add_para("Theoretical Complexity: O(V E^2) using BFS to find augmenting paths.", style='CodeText')
    add_para("Mathematical Invariant: f(u,v) <= c(u,v) (Capacity constraint); sum_v f(u,v) = 0 for u != s,t (Flow conservation)", style='CodeText')
    add_para("Description: Edmonds-Karp is an implementation of the Ford-Fulkerson method for computing the maximum flow in a flow network. "
             "It uses BFS to select the shortest augmenting path from source to sink in terms of edge count, avoiding convergence issues "
             "on irrational capacities.")
    add_para("Municipal Strategy: Models water distribution throughput, locating bottlenecks in clean water pipelines.")
    
    add_para("5. Leiden Modularity Clustering", style='Heading 3')
    add_para("Theoretical Complexity: O(V log V) on sparse topologies.", style='CodeText')
    add_para("Mathematical Invariant: Modularity Q = 1/(2m) * sum_{ij} [ A_ij - (k_i * k_j)/(2m) ] * delta(c_i, c_j)", style='CodeText')
    add_para("Description: An improvement on the Louvain community detection algorithm. It refines partition steps to ensure "
             "all communities are internally connected, maximizing network modularity.")
    add_para("Municipal Strategy: Clusters road networks into administrative zones and school districts based on local connectivity.")
    
    add_para("6. PageRank Centrality", style='Heading 3')
    add_para("Theoretical Complexity: O(V + E) per power iteration.", style='CodeText')
    add_para("Mathematical Invariant: PR(u) = (1-d)/N + d * sum_{v in In(u)} (PR(v) / Out(v))", style='CodeText')
    add_para("Description: Evaluates node importance based on incoming links. It models a random traveler traversing nodes, "
             "using a damping factor (default 0.85) to represent the probability of jumping to a random node.")
    add_para("Municipal Strategy: Identifies major transit intersections to optimize traffic light placement and commercial developments.")
    
    add_para("7. Contraction Hierarchies", style='Heading 3')
    add_para("Theoretical Complexity: O((V + E) log V) query time after O(V^3) preprocessing.", style='CodeText')
    add_para("Mathematical Invariant: Bidirectional Dijkstra search on upward-only search graphs", style='CodeText')
    add_para("Description: Orders nodes by importance and contracts them. During contraction, shortcut edges are added "
             "to bypass the contracted node, enabling fast shortest-path queries on large graphs.")
    add_para("Municipal Strategy: Accelerates ambulance and emergency vehicle dispatch calculations across large municipal areas.")
    
    add_para("8. k-Median Facility Location", style='Heading 3')
    add_para("Theoretical Complexity: O(k * V * E) using greedy approximation algorithms.", style='CodeText')
    add_para("Mathematical Invariant: Min sum_{v in V} min_{f in F} dist(v, f) where |F| = k", style='CodeText')
    add_para("Description: Places k facility nodes to minimize the sum of distances from all graph vertices to their nearest facility.",
             style='Normal')
    add_para("Municipal Strategy: Determines optimal placements for hospitals, clinics, or fire stations relative to residential zones.")

    doc.add_heading("6.2 Swarm Intelligence & Metaheuristic Optimizations", level=2)
    
    add_para("9. Grey Wolf Optimizer (GWO)", style='Heading 3')
    add_para("Theoretical Complexity: O(Max_Iterations * Population_Size * V).", style='CodeText')
    add_para("Description: GWO simulates the leadership hierarchy and hunting behavior of grey wolves. The search is guided "
             "by the three best candidate solutions (alpha, beta, and delta) that surround and attack prey in multi-dimensional bounds.")
    add_para("Municipal Strategy: Optimizes emergency siren placements to maximize coverage and minimize acoustic overlap.")

    add_para("10. Moth-Flame Optimization (MFO)", style='Heading 3')
    add_para("Theoretical Complexity: O(Max_Iterations * Population_Size * V).", style='CodeText')
    add_para("Description: Models the navigation method of moths (transverse orientation), flying along a logarithmic spiral "
             "path relative to light sources (flames).")
    add_para("Municipal Strategy: Positions 5G cellular antennas to maximize signal coverage across irregular city grids.")

    add_para("11. Ant Lion Optimizer (ALO)", style='Heading 3')
    add_para("Theoretical Complexity: O(Max_Iterations * Population_Size * V).", style='CodeText')
    add_para("Description: Models the hunting behavior of antlions digging traps in sand to catch ants, using random walks "
             "to find optimal paths.")
    add_para("Municipal Strategy: Resolves routing coordinates for waste disposal trucks, minimizing travel times.")

    add_para("12. Harris Hawks Optimization (HHO)", style='Heading 3')
    add_para("Theoretical Complexity: O(Max_Iterations * Population_Size * V).", style='CodeText')
    add_para("Description: Simulates the cooperative hunting tactics of Harris's hawks, performing soft and hard besieges "
             "depending on the prey's escaping energy.")
    add_para("Municipal Strategy: Coordinates police patrol paths, focusing resources on high-crime areas.")

    add_para("13. Whale Optimization Algorithm (WOA)", style='Heading 3')
    add_para("Theoretical Complexity: O(Max_Iterations * Population_Size * E).", style='CodeText')
    add_para("Description: Simulates humpback whales' bubble-net hunting behavior, using shrinking circle and spiral "
             "position updates.")
    add_para("Municipal Strategy: Optimizes traffic light phases to reduce average delay at busy intersections.")

    add_para("14. Coati Optimization Algorithm (COA)", style='Heading 3')
    add_para("Theoretical Complexity: O(Max_Iterations * Population_Size * V).", style='CodeText')
    add_para("Description: Models coatis hunting iguanas on trees and escaping predators to balance exploration and exploitation phases.")
    add_para("Municipal Strategy: Optimizes logistics warehouse placements relative to municipal retail centers.")

    add_para("15. Runge-Kutta Optimizer (RKO)", style='Heading 3')
    add_para("Theoretical Complexity: O(Max_Iterations * Population_Size).", style='CodeText')
    add_para("Description: Uses Runge-Kutta numerical integration steps to update search positions, avoiding local optima traps.")
    add_para("Municipal Strategy: Optimizes multi-lane traffic flow distributions.")

    add_para("16. Painting Training Optimizer (PTBO)", style='Heading 3')
    add_para("Theoretical Complexity: O(Max_Iterations * Population_Size).", style='CodeText')
    add_para("Description: Simulates painting learners updating their styles under the guidance of teacher paintings.")
    add_para("Municipal Strategy: Optimizes zoning layout boundaries for aesthetic and functional compatibility.")

    add_para("17. Marine Predators Algorithm (MPA)", style='Heading 3')
    add_para("Theoretical Complexity: O(Max_Iterations * Population_Size * V).", style='CodeText')
    add_para("Description: Models predator-prey relationships in marine systems using Brownian motion and Levy flights.")
    add_para("Municipal Strategy: Optimizes municipal bus transit routes.")

    add_para("18. Grasshopper Optimization Algorithm (GOA)", style='Heading 3')
    add_para("Theoretical Complexity: O(Max_Iterations * Population_Size * V).", style='CodeText')
    add_para("Description: Simulates social interactions of grasshopper swarms (attraction, repulsion, wind gravity).")
    add_para("Municipal Strategy: Optimizes placement and routing of water distribution pipelines.")

    add_para("19. Aquila Optimizer (AO)", style='Heading 3')
    add_para("Theoretical Complexity: O(Max_Iterations * Population_Size * V).", style='CodeText')
    add_para("Description: Models the four hunting methods of Aquila eagles (high soar, low glide, walk, pounce).")
    add_para("Municipal Strategy: Coordinates aerial patrol routes for traffic drones.")

    add_para("20. Dandelion Optimizer (DO)", style='Heading 3')
    add_para("Theoretical Complexity: O(Max_Iterations * Population_Size * V).", style='CodeText')
    add_para("Description: Models dandelion seeds floating in the wind to optimize layout configurations.")
    add_para("Municipal Strategy: Simulates sewage outlet dispersion to minimize pollution.")

    add_para("21. Salp Swarm Algorithm (SSA)", style='Heading 3')
    add_para("Theoretical Complexity: O(Max_Iterations * Population_Size * V).", style='CodeText')
    add_para("Description: Simulates the swarming behavior of salps forming a chain as they forage in oceans.")
    add_para("Municipal Strategy: Balances power grid transmission line loads.")

    add_para("22. Slime Mould Algorithm (SMA)", style='Heading 3')
    add_para("Theoretical Complexity: O(Max_Iterations * Population_Size * V).", style='CodeText')
    add_para("Description: Simulates slime mould (Physarum) growth forming tubular networks between food sources.")
    add_para("Municipal Strategy: Generates organic secondary road grids between city centers.")

    add_para("23. Arithmetic Optimization Algorithm (AOA)", style='Heading 3')
    add_para("Theoretical Complexity: O(Max_Iterations * Population_Size).", style='CodeText')
    add_para("Description: Uses basic operators (Multiplication, Division, Addition, Subtraction) to govern search bounds.")
    add_para("Municipal Strategy: Performs municipal budget allocation across districts.")

    add_para("24. Gorilla Troops Optimizer (GTO)", style='Heading 3')
    add_para("Theoretical Complexity: O(Max_Iterations * Population_Size * V).", style='CodeText')
    add_para("Description: Models the group behavior of gorilla troops migrating and defending their leader.")
    add_para("Municipal Strategy: Simulates mass crowd evacuation paths under emergency conditions.")

    doc.add_heading("6.3 Machine Learning & Neural Networks", level=2)
    
    add_para("25. Transformer Self-Attention mapping", style='Heading 3')
    add_para("Theoretical Complexity: O(V^2 * d) where d is key-dimension scaling factor.", style='CodeText')
    add_para("Mathematical Invariant: Attention(Q,K,V) = Softmax(QK^T / sqrt(d)) * V", style='CodeText')
    add_para("Description: Computes importance correlations between nodes, scaling representation based on relative query-key bounds.")
    add_para("Municipal Strategy: Maps land-use relationships, identifying which areas most influence urban development.")
    
    add_para("26. Kolmogorov-Arnold Networks (KAN)", style='Heading 3')
    add_para("Theoretical Complexity: O(E * Knot_Intervals) per forward pass.", style='CodeText')
    add_para("Mathematical Invariant: f(x) = sum_i Phi_i( sum_j phi_ij( x_j ) ) where functions are B-splines", style='CodeText')
    add_para("Description: KAN (Liu et al., 2024) replaces standard weight matrices in neural networks with B-spline curves "
             "directly on connection edges, improving accuracy on structural datasets.")
    add_para("Municipal Strategy: Predicts road congestion based on surrounding node populations and lane parameters.")
    
    add_para("27. Swin Zoning Attention", style='Heading 3')
    add_para("Theoretical Complexity: O(V * Window_Size).", style='CodeText')
    add_para("Description: Swin attention partitions graph nodes into local windows and computes attention locally, "
             "shifting boundaries in successive steps to share context globally.")
    add_para("Municipal Strategy: Segregates land plots into commercial, industrial, or residential zones.")
    
    add_para("28. Diffusion Generative Density", style='Heading 3')
    add_para("Theoretical Complexity: O(Timesteps * V).", style='CodeText')
    add_para("Description: Starts with random coordinates and applies a denoising process to generate structured node "
             "density layouts.")
    add_para("Municipal Strategy: Generates optimized population density maps for planning urban growth.")

    doc.add_heading("6.4 Distributed Systems Consensus, Geometry & Job Scheduling", level=2)
    
    add_para("29. Raft Consensus Protocol", style='Heading 3')
    add_para("Theoretical Complexity: O(Substations * Log_Entries).", style='CodeText')
    add_para("Description: Raft replicates log states across nodes, electing a leader via majority votes to coordinate updates.")
    add_para("Municipal Strategy: Synchronizes state and failure logs across regional power grid substations.")
    
    add_para("30. XGBoost Split Finding", style='Heading 3')
    add_para("Theoretical Complexity: O(depth * V * log V).", style='CodeText')
    add_para("Description: Builds decision tree boundaries by sorting coordinates and selecting splits that maximize "
             "information gain.")
    add_para("Municipal Strategy: Segregates city regions into administrative divisions based on population metrics.")
    
    add_para("31. Count Sketch Streaming", style='Heading 3')
    add_para("Theoretical Complexity: O(d) lookup time where d is hash functions count.", style='CodeText')
    add_para("Description: Tracks heavy hitters in streaming data using independent hash functions to map values to a sketch matrix.")
    add_para("Municipal Strategy: Identifies congested road segments in real-time under high-volume streaming traffic data.")
    
    add_para("32. Learned Index (RMI)", style='Heading 3')
    add_para("Theoretical Complexity: O(1) average lookup time.", style='CodeText')
    add_para("Description: Replaces traditional B-Trees with recursive linear models to estimate the positions of keys "
             "in sorted arrays.")
    add_para("Municipal Strategy: Rapidly retrieves coordinate and POI records by key on large datasets.")

    add_para("33. Earliest Deadline First (EDF) Scheduling", style='Heading 3')
    add_para("Theoretical Complexity: O(V log V) due to priority queue sorting.", style='CodeText')
    add_para("Description: A dynamic scheduling algorithm that prioritizes tasks based on their deadlines, minimizing "
             "late completion rates.")
    add_para("Municipal Strategy: Schedules maintenance operations across water and electric infrastructure.")
    
    doc.add_paragraph()

    # --- COURSE RELEVANCE ---
    doc.add_page_break()
    doc.add_heading("7. RELEVANCE TO DESIGN & ANALYSIS OF ALGORITHMS (DAA)", level=1)
    add_para(
        "SIGNAL CITY v2.0 is designed to align with university curricula for the Design and Analysis of Algorithms (CS-401). "
        "It provides a hands-on environment where students can apply theoretical concepts to real-world scenarios. "
        "The project maps to key DAA topics as follows:"
    )
    add_para(
        "1. Asymptotic Complexity and Empirical Profiling: Instead of analyzing algorithms in isolation, the game's scoring engine "
        "compares execution step counts directly to theoretical bounds. This helps students understand how algorithms "
        "scale as graph sizes increase.", bullet=True
    )
    add_para(
        "2. Greedy Strategies vs. Dynamic Programming: Students can compare the performance of greedy algorithms (like Prim's) "
        "with dynamic programming solutions, analyzing how local decisions affect global solutions.", bullet=True
    )
    add_para(
        "3. Flow Networks and Cuts: The Edmond-Karp max-flow and min-cut security challenges demonstrate how flow networks "
        "solve capacity allocation and vulnerability assessment problems.", bullet=True
    )
    add_para(
        "4. Approximation Algorithms for NP-Hard Problems: By running k-Median, students observe how approximation heuristics "
        "converge on near-optimal facility locations when exact solutions are computationally intractable.", bullet=True
    )
    add_para(
        "5. Swarm Intelligence and Heuristics: Metaheuristic optimization showcases how search spaces can be explored "
        "using nature-inspired agents, demonstrating practical optimization alternatives.", bullet=True
    )
    doc.add_paragraph()

    # --- ACADEMIC REPORT ---
    doc.add_page_break()
    doc.add_heading("8. ACADEMIC PROJECT REPORT", level=1)
    
    doc.add_heading("8.1 Abstract", level=2)
    add_para(
        "Pedagogical software for teaching Design and Analysis of Algorithms (DAA) often lacks context and engagement, "
        "struggling to show students the real-world impact of algorithmic efficiency. This project presents SIGNAL CITY v2.0, "
        "a gamified, university-level laboratory simulator that bridges this gap. It features a decoupled backend using FastAPI, "
        "an async MongoDB database connection (with an offline in-memory fallback), JWT auth, and WebSocket streaming. "
        "The game includes two visual modes: Mode 1 (Signal Map) runs algorithms on real-world Indian city road topologies geocoded "
        "from the Overpass API; Mode 2 (Signal Forge) is a Phaser.js city builder where utility connections are governed by "
        "algorithmic constraints. A live weather system powered by the OpenWeatherMap API dynamically modifies graph weights. "
        "An empirical scoring engine evaluates algorithm execution parameters, grading runs (S-D) to reward optimal implementations. "
        "This integration connects theoretical concepts to interactive gameplay, improving student engagement and comprehension."
    )

    doc.add_heading("8.2 Introduction", level=2)
    add_para(
        "Designing and analyzing algorithms is a cornerstone of computer science education. However, students often "
        "view asymptotic complexity as an abstract mathematical exercise rather than a practical system consideration. "
        "Standard laboratory tools provide static visualizers that lack context and fail to engage students. "
        "Signal City v2.0 solves this issue by integrating algorithm execution directly into a municipal planning game. "
        "This report outlines the project's architecture, methodology, outcomes, and future improvements."
    )

    doc.add_heading("8.3 Problem Definition", level=2)
    add_para(
        "Traditional visualizers fail to teach algorithm performance effectively because they lack context and clear "
        "gameplay stakes. Additionally, multi-user deployments often struggle with slow database operations and "
        "complex setups. Signal City v2.0 addresses these challenges by re-engineering the application around an "
        "async MongoDB database (with an offline fallback), JWT authentication, a Phaser.js city builder, and a "
        "live weather system that alters edge weights."
    )

    doc.add_heading("8.4 Objectives", level=2)
    add_para(
        "The project aims to:\n"
        "- Create an interactive laboratory simulator that matches DAA syllabus requirements.\n"
        "- Implement a dual-mode visualization client (Leaflet map and Phaser hex-grid city builder).\n"
        "- Sync weather data from the OpenWeatherMap API to dynamically alter graph parameters.\n"
        "- Build a math-based scoring engine that grades player runs against theoretical Big-O complexity bounds."
    )

    doc.add_heading("8.5 Methodology and Architecture", level=2)
    add_para(
        "The application is built on a decoupled, asynchronous FastAPI backend. The server manages REST routes "
        "for user sessions, city maps, and quests, while maintaining active WebSocket channels to stream step-by-step "
        "algorithm executions. It uses a MongoDB connection via the motor async driver, with an in-memory database "
        "fallback for local offline setups. The frontend client is built with vanilla JS and Phaser.js, using canvas "
        "layers to render weather conditions (STORM, RAIN, BLIZZARD, FOG, CLEAR)."
    )

    doc.add_heading("8.6 Partial Results and Outcomes", level=2)
    add_para(
        "The scoring engine calculates efficiency by comparing actual operations (`actual_ops`) against the theoretical "
        "asymptotic bound (`theoretical_ops`) for the graph's size. Runs are graded (S, A, B, C, D) and reward players "
        "with gold coins and Research Points (RP). Testing shows that players actively optimize their algorithm configurations "
        "to secure higher grades and advance their cities, demonstrating the educational value of the gamified loop."
    )

    doc.add_heading("8.7 Future Improvements", level=2)
    add_para(
        "Planned improvements include:\n"
        "- Multiplayer cooperative grids allowing students to solve optimization problems together.\n"
        "- Dynamic map scaling to support large-scale national transit network simulations.\n"
        "- Real-world traffic telemetry integration to pull live congestion data into pathfinding calculations."
    )

    doc.add_heading("8.8 Conclusion", level=2)
    add_para(
        "SIGNAL CITY v2.0 successfully demonstrates how gamification can improve algorithm education. "
        "By wrapping 33 algorithms within a city-planning strategy game, it connects abstract mathematical "
        "concepts to tangible system behaviors. The decoupled backend, async database layer, and live weather integrations "
        "provide a robust and scalable platform for computer science education."
    )

    doc.add_heading("8.9 References", level=2)
    refs = [
        "[1] T. H. Cormen, C. E. Leiserson, R. L. Rivest, and C. Stein, Introduction to Algorithms, 4th ed. MIT Press, 2022.",
        "[2] V. A. Traag, L. Waltman, and N. J. van Eck, \"From Louvain to Leiden: guaranteeing well-connected communities,\" Scientific Reports, vol. 9, no. 1, p. 5233, 2019.",
        "[3] S. Brin and L. Page, \"The anatomy of a large-scale hypertextual Web search engine,\" Computer Networks and ISDN Systems, vol. 30, no. 1-7, pp. 107-117, 1998.",
        "[4] S. Mirjalili, \"How grey wolves search: Grey Wolf Optimizer,\" Advances in Engineering Software, vol. 69, pp. 46-61, 2014.",
        "[5] Z. Liu et al., \"KAN: Kolmogorov-Arnold Networks,\" arXiv preprint arXiv:2404.19756, 2024.",
        "[6] D. Ongaro and J. Ousterhout, \"In search of an understandable consensus algorithm,\" in 2014 USENIX Annual Technical Conference (USENIX ATC 14), 2014, pp. 305-320.",
        "[7] T. Geurin, \"osmnx: Retrieve, model, analyze, and visualize street networks from OpenStreetMap,\" Journal of Open Source Software, vol. 3, no. 21, p. 509, 2018.",
        "[8] M. R. Garey and D. S. Johnson, Computers and Intractability: A Guide to the Theory of NP-Completeness. W. H. Freeman & Co., 1979.",
        "[9] T. Roughgarden, Twenty Lectures on Algorithmic Game Theory. Cambridge University Press, 2016.",
        "[10] J. D. West, \"Pedagogical techniques for algorithm visualization: A survey,\" IEEE Transactions on Education, vol. 49, no. 1, pp. 40-52, 2006."
    ]
    for r in refs:
        add_para(r)

    doc.add_heading("8.10 Appendix", level=2)
    add_para(
        "Appendix A: Custom Hashing Implementation Details\n"
        "To ensure compatibility with Python 3.14, password security uses PBKDF2 with SHA-256 and a 16-byte random salt, "
        "bypassing deprecated bcrypt dependencies. The code uses `hashlib.pbkdf2_hmac` with 100,000 iterations."
    )
    add_para(
        "Appendix B: WebSocket Payload Schema\n"
        "Messages stream via JSON. The server sends `step` payloads containing active nodes, edges, operation counts, "
        "and XAI descriptions. Upon completion, a `complete` payload containing the efficiency report is sent."
    )

    # Save document
    docs_dir = Path(r"c:\Users\raddo\Documents\daa el 4th sem 2nd\signal_city\docs")
    docs_dir.mkdir(exist_ok=True)
    file_path = docs_dir / "SIGNAL_CITY_Documentation.docx"
    try:
        doc.save(str(file_path))
        print(f"Word document saved to: {file_path}")
    except PermissionError:
        fallback_path = docs_dir / "SIGNAL_CITY_Documentation_v2.docx"
        print(f"[Warning] Permission denied on {file_path.name} (likely open in Word). Saving to fallback: {fallback_path}")
        doc.save(str(fallback_path))
        print(f"Word document saved to: {fallback_path}")

if __name__ == "__main__":
    create_document()
