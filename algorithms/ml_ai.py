"""
algorithms/ml_ai.py — Machine Learning and AI Algorithms for Signal City.
Implements Transformer Self-Attention, KAN, Swin zoning, and Diffusion building planning.
"""

import math
import random
import time
from .graph import WeightedGraph

def transformer_attention(graph: WeightedGraph, seed: int = 42):
    """
    Self-Attention over nodes based on population weight and degree.
    Identifies key traffic hubs by computing pairwise QK^T attention.
    """
    nodes = list(graph.nodes.keys())
    n = len(nodes)
    if n == 0: return
    
    # Feature matrix X: [pop_weight, degree, x, y]
    X = {}
    for node in nodes:
        pop = graph.nodes[node].get("pop_weight", 1.0)
        deg = graph.degree(node)
        x, y = graph.node_position(node)
        X[node] = [pop, float(deg), x/100.0, y/100.0]
        
    # Weight matrices W_Q, W_K (simplified 4x2 projections)
    rng = random.Random(seed)
    W_Q = [[rng.uniform(-1, 1), rng.uniform(-1, 1)] for _ in range(4)]
    W_K = [[rng.uniform(-1, 1), rng.uniform(-1, 1)] for _ in range(4)]
    
    # Compute Queries and Keys
    Q = {}
    K = {}
    for node in nodes:
        features = X[node]
        # Query projection
        q = [sum(features[i] * W_Q[i][j] for i in range(4)) for j in range(2)]
        # Key projection
        k = [sum(features[i] * W_K[i][j] for i in range(4)) for j in range(2)]
        Q[node] = q
        K[node] = k
        
    # Stream attention from first 10 nodes to all others
    sample_nodes = nodes[:10]
    op_count = 0
    
    for u in sample_nodes:
        # Calculate attention weights from u to all v
        scores = {}
        for v in nodes:
            # Dot product Q[u] * K[v]
            dot = sum(Q[u][j] * K[v][j] for j in range(2))
            scores[v] = dot / math.sqrt(2.0)  # scaled dot-product
            op_count += 2
            
        # Softmax
        exp_sum = sum(math.exp(scores[v]) for v in nodes)
        attention_weights = {v: math.exp(scores[v]) / exp_sum for v in nodes}
        
        # Find top attended nodes from u
        top_attended = sorted(attention_weights.items(), key=lambda item: item[1], reverse=True)[:5]
        
        yield {
            "kind": "node_frontier",
            "node": u,
            "top_attended": [{ "node": item[0], "weight": round(item[1], 4) } for item in top_attended],
            "op_count": op_count,
            "xai_text": f"Transformer Self-Attention: Node {u} is attending to the network. "
                       f"Highest attention weights directed to: {[item[0] for item in top_attended]}. "
                       f"Self-attention allows the model to learn global context without step-by-step traversal."
        }
        time.sleep(0.4)

    # Done - find top global attention nodes
    global_attention = {v: 0.0 for v in nodes}
    for u in nodes:
        scores = {v: sum(Q[u][j] * K[v][j] for j in range(2)) / math.sqrt(2.0) for v in nodes}
        exp_sum = sum(math.exp(scores[v]) for v in nodes)
        for v in nodes:
            global_attention[v] += math.exp(scores[v]) / exp_sum
            
    top_global = sorted(global_attention.items(), key=lambda item: item[1], reverse=True)[:5]
    
    yield {
        "kind": "algorithm_done",
        "top_nodes": [{"node": item[0], "score": round(item[1], 2)} for item in top_global],
        "op_count": n * n,
        "theoretical_complexity": "O(V^2 * d)",
        "xai_text": f"Self-Attention completed! Top global attention hubs identified: {[item[0] for item in top_global]}. "
                   f"These nodes act as major traffic brokers according to transformer features."
    }


def kolmogorov_arnold_networks(graph: WeightedGraph, seed: int = 43):
    """
    Kolmogorov-Arnold Network (KAN) (2024) for congestion prediction.
    Unlike standard MLPs, KANs learn univariate B-splines on the connections (edges).
    """
    edges = graph.get_all_edges()
    n = len(edges)
    if n == 0: return
    
    rng = random.Random(seed)
    # Define splines on each edge: sum of 3 sine/cosine waves with random phases
    splines = {}
    for idx, e in enumerate(edges):
        u, v = e["u"], e["v"]
        splines[(u, v)] = [rng.uniform(0.1, 1.0), rng.uniform(0, 2*math.pi)]
        
    op_count = 0
    # Evaluate congestion prediction for each edge
    for idx, e in enumerate(edges):
        u, v = e["u"], e["v"]
        # Feature: node population weights and length
        feat1 = graph.nodes[u].get("pop_weight", 1.0)
        feat2 = graph.nodes[v].get("pop_weight", 1.0)
        length = e.get("length_m", 100.0) / 200.0
        
        # Spline evaluation: phi(x) = a * sin(x + b)
        coeff, phase = splines[(u, v)]
        val = coeff * math.sin((feat1 + feat2 + length) + phase)
        congestion = max(0.0, min(1.0, 0.5 + val * 0.4))
        op_count += 3
        
        if idx % max(1, n // 10) == 0:
            yield {
                "kind": "edge_relaxed",
                "from_node": u,
                "to_node": v,
                "congestion": round(congestion, 2),
                "op_count": op_count,
                "xai_text": f"KAN spline activation evaluated for edge ({u}-{v}): predicted congestion: {congestion*100:.1f}%. "
                           f"KAN places learnable activation functions directly on the links, rather than on the nodes."
            }
            time.sleep(0.3)
            
    yield {
        "kind": "algorithm_done",
        "op_count": op_count,
        "theoretical_complexity": "O(E * Spline_Knots)",
        "xai_text": f"KAN congestion inference complete. Simulated activations on all {n} edges."
    }


def swin_transformer_zoning(graph: WeightedGraph, seed: int = 44):
    """
    Swin Transformer (Hierarchical Vision Transformer) for zoning categorization.
    Divides the city space into 4 window regions (patches) and computes local attention.
    """
    nodes = list(graph.nodes.keys())
    if not nodes: return
    
    # Partition nodes into 4 quadrant patches based on coordinate signs
    patches = {
        "Quadrant I (NE)": [],
        "Quadrant II (NW)": [],
        "Quadrant III (SW)": [],
        "Quadrant IV (SE)": []
    }
    
    for node in nodes:
        x, y = graph.node_position(node)
        if x >= 0 and y >= 0:
            patches["Quadrant I (NE)"].append(node)
        elif x < 0 and y >= 0:
            patches["Quadrant II (NW)"].append(node)
        elif x < 0 and y < 0:
            patches["Quadrant III (SW)"].append(node)
        else:
            patches["Quadrant IV (SE)"].append(node)

    op_count = 0
    # Process local window attention inside each patch
    for name, members in patches.items():
        if not members: continue
        # Highlight window
        for node in members:
            # Simulates local self-attention inside the window
            op_count += len(members)
            
        yield {
            "kind": "node_frontier",
            "node": members[0],
            "patch_name": name,
            "size": len(members),
            "op_count": op_count,
            "xai_text": f"Swin Transformer: Shifting local window active on {name} ({len(members)} nodes). "
                       f"Local attention is calculated inside this patch first (O(W^2) complexity instead of O(V^2))."
        }
        time.sleep(0.5)

    # Classify patches to zoning types based on population weights
    zoning = {}
    zone_types = ["Residential 🏘️", "Commercial 🏢", "Industrial 🏭", "Park 🌲"]
    for idx, (name, members) in enumerate(patches.items()):
        if not members: continue
        avg_pop = sum(graph.nodes[n].get("pop_weight", 1.0) for n in members) / len(members)
        # Choose zoning based on average population weight
        zone = zone_types[int(avg_pop * 1.5) % len(zone_types)]
        for n in members:
            zoning[n] = int(avg_pop * 1.5) % len(zone_types)
            
    yield {
        "kind": "algorithm_done",
        "communities": zoning,
        "op_count": op_count,
        "xai_text": f"Swin zoning classification complete! Grouped city intersections into 4 spatial patches and categorized districts."
    }


def diffusion_models(graph: WeightedGraph, seed: int = 45):
    """
    Generative Diffusion Model.
    Simulates reverse denoising process: starts with random building offsets,
    and gradually diffuses them to clean central hub alignments over 5 timesteps.
    """
    nodes = list(graph.nodes.keys())
    n = len(nodes)
    if n == 0: return
    
    rng = random.Random(seed)
    # Generate initial high gaussian noise offsets for building locations
    noise = {node: [rng.uniform(-25, 25), rng.uniform(-25, 25)] for node in nodes}
    
    # 5 Denoising timesteps
    timesteps = 5
    for t in range(timesteps, 0, -1):
        # Scale noise down (denoise step)
        fraction = (t - 1) / timesteps
        for node in nodes:
            noise[node][0] *= fraction
            noise[node][1] *= fraction
            
        yield {
            "kind": "iteration_complete",
            "iteration": timesteps - t + 1,
            "timestep": t,
            "noise_level": round(fraction * 100, 1),
            "op_count": (timesteps - t + 1) * n,
            "xai_text": f"Diffusion Denoising Step {timesteps - t + 1}: Timestep t={t}. Noise level reduced to {fraction*100:.1f}%. "
                       f"Nodes and simulated buildings are diffusing towards their clean spatial coordinates."
        }
        time.sleep(0.5)
        
    yield {
        "kind": "algorithm_done",
        "op_count": timesteps * n,
        "theoretical_complexity": "O(T * V)",
        "xai_text": f"Diffusion generation complete! All building locations fully denoised and aligned."
    }
