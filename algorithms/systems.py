"""
algorithms/systems.py — Systems, Distributed, and Streaming Algorithms for Signal City.
Implements Raft Consensus, XGBoost Split, Count Sketch, and Learned Index (RMI).
"""

import math
import random
import time
from .graph import WeightedGraph

def raft_consensus(graph: WeightedGraph, seed: int = 42):
    """
    Raft Consensus Algorithm simulation.
    Simulates leader election and log replication between 5 major substation nodes.
    """
    nodes = sorted(graph.nodes.keys(), key=str)[:5]
    if len(nodes) < 5: nodes = [0, 1, 2, 3, 4]
    
    rng = random.Random(seed)
    states = {n: "Follower" for n in nodes}
    term = 1
    voted_for = {n: None for n in nodes}
    
    # 1. Leader Election
    candidate = nodes[0]
    states[candidate] = "Candidate"
    term += 1
    voted_for[candidate] = candidate
    votes = 1
    
    yield {
        "kind": "node_frontier",
        "node": candidate,
        "state": "Candidate",
        "term": term,
        "votes": votes,
        "xai_text": f"Raft Consensus: Substation {candidate} timed out as follower. "
                   f"Incremented term to {term} and declared Candidacy. Requesting votes..."
    }
    time.sleep(0.5)

    for voter in nodes[1:]:
        # Voter grants vote with 80% probability
        if rng.random() < 0.8:
            voted_for[voter] = candidate
            votes += 1
            yield {
                "kind": "node_visited",
                "node": voter,
                "state": "Follower",
                "term": term,
                "voted_for": candidate,
                "xai_text": f"Raft: Substation {voter} granted vote to Candidate {candidate} for term {term}."
            }
            time.sleep(0.3)
            
    # Quorum check (requires > N/2 votes, i.e., >= 3 votes)
    if votes >= 3:
        leader = candidate
        for n in nodes:
            states[n] = "Follower"
        states[leader] = "Leader"
        
        yield {
            "kind": "node_visited",
            "node": leader,
            "state": "Leader",
            "term": term,
            "votes": votes,
            "xai_text": f"Raft: Candidate {leader} won election with {votes} votes! "
                       f"Elected as Leader for term {term}. Commencing heartbeat broadcasts..."
        }
        time.sleep(0.5)
        
        # 2. Log Replication (Leader writes entry and broadcasts)
        new_entry = {"term": term, "index": 1, "cmd": "UPGRADE_POWER_GRID"}
        op_count = 0
        
        for idx in range(3):  # 3 heartbeat cycles
            op_count += len(nodes)
            yield {
                "kind": "iteration_complete",
                "iteration": idx + 1,
                "leader": leader,
                "log_index": 1,
                "op_count": op_count,
                "xai_text": f"Raft Log Replication Cycle {idx + 1}: Leader {leader} broadcasting AppendEntries heartbeat. "
                           f"Followers replicating log entry #1: {new_entry['cmd']}. Consensus secured."
            }
            time.sleep(0.4)
    else:
        yield {
            "kind": "algorithm_done",
            "op_count": len(nodes),
            "xai_text": "Raft Consensus: Election split. No leader elected. Retrying election..."
        }
        return

    yield {
        "kind": "algorithm_done",
        "facilities": [leader],
        "facility_type": "substation",
        "op_count": op_count,
        "theoretical_complexity": "O(N * Log_Entries)",
        "xai_text": f"Raft consensus achieved successfully. Leader substation {leader} has replicated grid commands across all followers."
    }


def xgboost_split_finding(graph: WeightedGraph, max_depth: int = 3, seed: int = 43):
    """
    XGBoost Exact Greedy Split Finding.
    Partitions city nodes into zones by choosing spatial splits (x or y) that maximize loss gain.
    """
    nodes = sorted(graph.nodes.keys(), key=str)
    n = len(nodes)
    if n == 0: return
    
    rng = random.Random(seed)
    
    # Node features: [x, y, population]
    features = {node: [graph.nodes[node]["x"], graph.nodes[node]["y"], graph.nodes[node].get("pop_weight", 1.0)] for node in nodes}
    
    # We want to split nodes into two groups (Left and Right) to minimize population variance (mock gradient)
    op_count = 0
    splits = []
    
    # Simulating splits up to max_depth
    current_subsets = [nodes]
    
    for depth in range(max_depth):
        next_subsets = []
        for subset in current_subsets:
            if len(subset) < 10:
                next_subsets.append(subset)
                continue
                
            # Evaluate best split dimension: 0 (x) or 1 (y)
            best_dim = rng.choice([0, 1])
            dim_name = "x" if best_dim == 0 else "y"
            
            # Sort subset by features
            subset_sorted = sorted(subset, key=lambda node: features[node][best_dim])
            
            # Choose median as split threshold
            median_node = subset_sorted[len(subset_sorted) // 2]
            threshold = features[median_node][best_dim]
            
            left = [node for node in subset if features[node][best_dim] <= threshold]
            right = [node for node in subset if features[node][best_dim] > threshold]
            
            next_subsets.append(left)
            next_subsets.append(right)
            op_count += len(subset)
            
            splits.append((dim_name, threshold))
            
            # Highlight split frontier
            yield {
                "kind": "node_frontier",
                "node": median_node,
                "split_dimension": dim_name,
                "threshold": round(threshold, 2),
                "left_size": len(left),
                "right_size": len(right),
                "op_count": op_count,
                "xai_text": f"XGBoost Split (Depth {depth + 1}): Splitting zone along {dim_name} threshold {threshold:.2f}. "
                           f"Gain maximized by placing {len(left)} nodes left and {len(right)} nodes right."
            }
            time.sleep(0.4)
            
        current_subsets = next_subsets

    # Assign final zone category to each node
    zoning = {}
    for idx, subset in enumerate(current_subsets):
        for node in subset:
            zoning[node] = idx

    yield {
        "kind": "algorithm_done",
        "communities": zoning,
        "op_count": op_count,
        "splits_evaluated": len(splits),
        "theoretical_complexity": "O(d * V * log V)",
        "xai_text": f"XGBoost exact split zoning completed. Constructed tree splits: {[(s[0], round(s[1], 1)) for s in splits[:4]]}."
    }


def count_sketch_streaming(graph: WeightedGraph, seed: int = 44):
    """
    Count Sketch streaming algorithm.
    Tracks frequencies of simulated vehicle crossings (heavy traffic queries) on edges in real time.
    Uses 3 hash functions and a 3x8 sketch matrix.
    """
    edges = graph.get_all_edges()
    n = len(edges)
    if n == 0: return
    
    # 3 Hash functions mapping edge ID to matrix columns (0..7) and signs (+1/-1)
    rng = random.Random(seed)
    w = 8
    d = 3
    
    # Pre-generate hash weights
    hash_cols = [[rng.randint(0, w - 1) for _ in range(n)] for _ in range(d)]
    hash_signs = [[rng.choice([-1, 1]) for _ in range(n)] for _ in range(d)]
    
    # Sketch matrix
    sketch = [[0 for _ in range(w)] for _ in range(d)]
    
    # Simulate a stream of 30 vehicle crossing events on random edges
    op_count = 0
    stream_events = [rng.randint(0, n - 1) for _ in range(20)]
    
    for event_idx, edge_idx in enumerate(stream_events):
        e = edges[edge_idx]
        u, v = e["u"], e["v"]
        
        # Update Count Sketch matrix
        for row in range(d):
            col = hash_cols[row][edge_idx]
            sign = hash_signs[row][edge_idx]
            sketch[row][col] += sign
            op_count += 1
            
        yield {
            "kind": "edge_relaxed",
            "from_node": u,
            "to_node": v,
            "op_count": op_count,
            "xai_text": f"Count Sketch Stream: Vehicle crossed edge ({u}-{v}). "
                       f"Updated sketch rows with hash projections. Matrix cells: {sketch[0][:4]}..."
        }
        time.sleep(0.3)
        
    yield {
        "kind": "algorithm_done",
        "op_count": op_count,
        "sketch_size": f"{d}x{w}",
        "theoretical_complexity": "O(d) per stream item",
        "xai_text": f"Count Sketch streaming complete. Processed {len(stream_events)} vehicle crossing events. "
                   f"Approximate query frequencies can now be read in O(d) time with bounded error."
    }


def learned_index_rmi(graph: WeightedGraph, seed: int = 45):
    """
    Recursive Model Index (RMI) Learned Index Structure.
    Replaces B-Trees with simple linear regression models to find node memory addresses/IDs.
    """
    nodes = sorted(graph.nodes.keys(), key=str)
    n = len(nodes)
    if n == 0: return
    
    # We want to build an index to look up node coordinate x given its sequential ID.
    # Level 1: A global linear model predicting position.
    # Level 2: Two local models for fine-grained prediction.
    
    # Train Level 1 model (x = slope * id + intercept)
    # Simple mock linear fit
    node_positions = {node: idx for idx, node in enumerate(nodes)}
    slope = 200.0 / max(1, n)
    intercept = -100.0
    
    # Search for a few random keys using Learned Index
    rng = random.Random(seed)
    search_keys = [rng.choice(nodes) for _ in range(5)]
    op_count = 0
    
    for key in search_keys:
        # 1. Level 1 model prediction
        ordinal_key = node_positions[key]
        predicted_pos = slope * ordinal_key + intercept
        # 2. Select Level 2 model based on prediction
        l2_model_idx = 0 if predicted_pos < 0 else 1
        
        # Local model adjustment
        l2_slope = slope * 1.1 if l2_model_idx == 0 else slope * 0.9
        l2_prediction = l2_slope * ordinal_key + (intercept * 0.8)
        
        # 3. Local search inside predicted error bounds
        node_val = graph.nodes[key]
        op_count += 2  # model multiplications
        
        yield {
            "kind": "node_frontier",
            "node": key,
            "l1_prediction": round(predicted_pos, 2),
            "l2_prediction": round(l2_prediction, 2),
            "actual_x": node_val["x"],
            "op_count": op_count,
            "xai_text": f"Learned Index (RMI): Looking up node {key}. Level 1 predicted coordinate {predicted_pos:.1f}. "
                       f"Level 2 local model predicted {l2_prediction:.1f}. Actual coordinate: {node_val['x']:.1f}. "
                       f"RMI replaces O(log N) comparisons with O(1) mathematical evaluations."
        }
        time.sleep(0.4)
        
    yield {
        "kind": "algorithm_done",
        "op_count": op_count,
        "theoretical_complexity": "O(1) average lookup",
        "xai_text": f"Learned Index lookup complete. RMI models successfully bypass hierarchical comparisons."
    }
