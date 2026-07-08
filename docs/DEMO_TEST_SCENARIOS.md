# Signal City Demo Test Scenarios

Use these as quick classroom/demo checks after starting the server with:

```bash
python server.py
```

Open the app at `http://127.0.0.1:8000`.

## 1. Signal Map: Two-Point Shortest Path

UI:

1. Open `http://127.0.0.1:8000/mode1`.
2. Load `Bengaluru`.
3. Select Start: `HSR Layout`.
4. Select End: `Koramangala`.
5. Run `Dijkstra`, `A*`, or `Contraction Hierarchies`.

Expected:

- The app refuses to run route/flow algorithms until both points are selected.
- Final route is highlighted.
- XAI explains algorithm, endpoints, distance, operations, and runtime.

API:

```bash
curl -X POST http://127.0.0.1:8000/api/route/plan ^
  -H "Content-Type: application/json" ^
  -d "{\"city_id\":\"bengaluru\",\"algorithm\":\"dijkstra\",\"params\":{\"source_name\":\"HSR Layout\",\"dest_name\":\"Koramangala\"}}"
```

## 2. Signal Map: Algorithm Comparison

UI:

1. Select Start: `Jayanagar`.
2. Select End: `MG Road`.
3. Check `Dijkstra`, `A*`, `Risk-Aware Route`.
4. Click `Compare Checked Algorithms`.

Expected:

- The comparison requires two points.
- Results show distance, operations, theoretical complexity, and route-specific summary.

API:

```bash
curl -X POST http://127.0.0.1:8000/api/route/compare ^
  -H "Content-Type: application/json" ^
  -d "{\"city_id\":\"bengaluru\",\"params\":{\"source_name\":\"Jayanagar\",\"dest_name\":\"MG Road\"},\"algorithms\":[\"dijkstra\",\"astar\",\"risk_aware\"]}"
```

## 3. Impact Console: Route Lab

UI:

1. Open `http://127.0.0.1:8000/impact`.
2. Choose `Route Lab`.
3. Start: `HSR Layout`.
4. End: `Koramangala`.
5. Run analysis.

Expected:

- Shows Dijkstra, A*, risk-aware, and CH-style results on the same endpoints.
- Shows path overlays, runtime, distance, risk, settled nodes, and XAI.

API:

```bash
curl -X POST http://127.0.0.1:8000/api/impact/route-lab ^
  -H "Content-Type: application/json" ^
  -d "{\"source_name\":\"HSR Layout\",\"dest_name\":\"Koramangala\",\"algorithms\":[\"dijkstra\",\"astar\",\"risk_aware\",\"contraction\"]}"
```

## 4. Impact Console: Flood Reroute

UI:

1. Choose `Flood Reroute`.
2. Pick Start and End.
3. Click road nodes after start/end to mark flooded nodes.
4. Run analysis.

Expected:

- Baseline route and flood-aware route are both drawn.
- XAI explains the flood penalty and the distance/time change.

API:

```bash
curl -X POST http://127.0.0.1:8000/api/impact/flood-reroute ^
  -H "Content-Type: application/json" ^
  -d "{\"source_name\":\"HSR Layout\",\"dest_name\":\"Koramangala\",\"flooded_nodes\":[]}"
```

## 5. Impact Console: Research Showcase - Resilient K-Routes

UI:

1. Choose `Resilient K-Routes`.
2. Start: `Jayanagar`.
3. End: `MG Road`.
4. Select `4 alternatives`.
5. Optionally mark flooded nodes.
6. Run analysis.

Expected:

- Returns a ranked route portfolio instead of one shortest path.
- Each route has distance, travel time, crash-risk, overlap with the best route, and resilience score.
- XAI mentions the 2023 dynamic K-shortest-path research basis.

API:

```bash
curl -X POST http://127.0.0.1:8000/api/impact/resilience-ksp ^
  -H "Content-Type: application/json" ^
  -d "{\"source_name\":\"Jayanagar\",\"dest_name\":\"MG Road\",\"k\":4,\"flooded_nodes\":[]}"
```

## 6. Impact Console: Facility Siting

UI:

1. Choose `Facility Siting`.
2. Facility type: `Hospitals`.
3. Set `k = 2`.
4. Run analysis.

Expected:

- Recommended facility nodes appear on the map.
- Before/after average and worst-case response times are shown.

API:

```bash
curl -X POST http://127.0.0.1:8000/api/impact/facility-siting ^
  -H "Content-Type: application/json" ^
  -d "{\"facility_type\":\"hospital\",\"k\":2,\"city_id\":\"bengaluru\",\"max_response_minutes\":8}"
```

## 7. Impact Console: Transit Equity

UI:

1. Choose `Transit Equity`.
2. Run analysis.

Expected:

- Wards are ranked by transit-desert score.
- XAI explains PageRank/ward-access logic and data limitations.

API:

```bash
curl -X POST "http://127.0.0.1:8000/api/impact/transit-equity?city_id=bengaluru"
```

## 8. Automated Test Command

```bash
python -m pytest tests\test_routing.py tests\test_impact.py -q
```

Expected:

- All route and impact endpoint tests pass.
- If `.pytest_cache` cannot be written on Windows, that warning is harmless.
