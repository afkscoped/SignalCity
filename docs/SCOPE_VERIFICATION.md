# Scope Verification

This file tracks the overhaul requests against the implemented code.

## Completed

- Larger Bengaluru graph loading:
  - `pipeline/city_loader.py` now uses a larger Bengaluru OSM radius and higher visual node cap.
  - Graph schema versioning prevents silently reusing stale old JSON caches.

- Data honesty:
  - Graphs now expose `data_quality`.
  - Synthetic/fallback graphs are clearly marked as demo-only.
  - Synthetic hotspot connector edges are marked with `virtual_connector` and warned about in route XAI.

- Universal route input layer:
  - `pipeline/routing_engine.py` resolves place names, clicked node IDs, selected landmarks, and validates connected paths.
  - It returns path coordinates, metrics, operation counts, runtime, and XAI.

- Signal Map two-point workflow:
  - Route algorithms require Start and End.
  - Max-flow (`edmonds_karp`) is also treated as a two-point algorithm.
  - Algorithm comparison refuses route/flow comparisons without two points.

- Reduced core algorithm surface:
  - `/api/algorithms` exposes a focused DAA set instead of the old 30+ public list.
  - Level unlocks were aligned to this smaller set.

- Impact Console rewrite:
  - `Route Lab`: Dijkstra, A*, risk-aware, CH-style comparison.
  - `Flood Reroute`: baseline versus flood-aware route.
  - `Facility Siting`: before/after response-time siting.
  - `Transit Equity`: ward access ranking.
  - `Resilient K-Routes`: research showcase based on 2023 dynamic K-shortest-path work.

- XAI and metrics:
  - Route outputs include problem statement, algorithm, graph size, operations, runtime, distance, estimated travel time, and data warnings.
  - Impact Console displays XAI, metrics, and route overlays.

- Tests and demos:
  - Automated route and impact tests are in `tests/test_routing.py` and `tests/test_impact.py`.
  - Manual classroom examples are in `docs/DEMO_TEST_SCENARIOS.md`.

## Honest Limitations

- Live graph quality depends on OSMnx/Overpass availability. When unavailable, Signal City marks fallback data clearly instead of claiming it is live.
- BMTC GTFS files in `data/civic` are still not a full official stop-times/trips feed. Transit Equity is therefore presented as an access-analysis demo unless full GTFS trip sequences are provided.
- The Resilient K-Route feature implements a local teaching adaptation of the 2023 KSP-DG idea. It does not claim to reproduce the full distributed DTLP index from the paper.

## Research Showcase

Feature: Resilient K-Routes in Impact Console.

Research basis:

- Ziqiang Yu, Xiaohui Yu, Nick Koudas, Yueting Chen, Yang Liu.
- "A Distributed Solution for Efficient K Shortest Paths Computation over Dynamic Road Networks."
- arXiv, 2023.
- https://arxiv.org/abs/2312.12687

Why it fits the project:

- Bengaluru route planning is dynamic: crashes, floods, and congestion can invalidate a single shortest path.
- The feature returns multiple backup routes and ranks them by travel time, crash-risk, flood exposure, and overlap diversity.
- It demonstrates DAA beyond a black-box shortest path by showing tradeoffs, robustness, and algorithmic evaluation.
