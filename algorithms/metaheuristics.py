"""
algorithms/metaheuristics.py — Metaheuristic Optimization Algorithms for Signal City.
Contains 16 metaheuristic algorithms mapped to 4 municipal planning problems.
"""

import math
import random
import time
from .graph import WeightedGraph

# ==============================================================================
# Category 1: Facility Location Optimization (GWO, ALO, HHO, COA)
# Goal: Place k fire stations to minimize the maximum distance to any city node.
# ==============================================================================

def grey_wolf_optimizer(graph: WeightedGraph, k: int = 3, max_iter: int = 5, seed: int = 42):
    """
    Grey Wolf Optimizer (2014) for fire station placement.
    Search agents (wolves) represent lists of k node IDs.
    """
    rng = random.Random(seed)
    nodes = list(graph.nodes.keys())
    if not nodes: return
    
    # Population size
    pop_size = 6
    population = [rng.sample(nodes, k) for _ in range(pop_size)]
    
    def evaluate_fitness(position):
        # Fitness is max distance from any node to its nearest facility
        max_dist = 0
        for node in nodes:
            # Shortest distance from this node to any facility in position
            min_fac_dist = min(graph.get_edge_weight(node, fac) if node != fac else 0 for fac in position)
            if min_fac_dist == float("inf"):
                min_fac_dist = 50.0  # mock penalty for disconnected graph
            max_dist = max(max_dist, min_fac_dist)
        return max_dist

    # Run loop
    for iteration in range(max_iter):
        # Evaluate fitness
        scored = [(evaluate_fitness(pos), pos) for pos in population]
        scored.sort() # low fitness is better (minimize max distance)
        
        alpha_fit, alpha_pos = scored[0]
        beta_fit, beta_pos = scored[1]
        delta_fit, delta_pos = scored[2]
        
        yield {
            "kind": "iteration_complete",
            "iteration": iteration + 1,
            "best_fitness": round(alpha_fit, 3),
            "alpha_pos": alpha_pos,
            "op_count": (iteration + 1) * pop_size,
            "xai_text": f"GWO Iteration {iteration + 1}: Alpha (leader) wolf positioned at hubs {alpha_pos} "
                       f"with fitness {alpha_fit:.2f} (max response distance). Beta and Delta wolves following."
        }
        time.sleep(0.4)
        
        # Update positions towards Alpha, Beta, Delta
        new_population = []
        for wolf_idx in range(pop_size):
            if wolf_idx < 3:
                new_population.append(scored[wolf_idx][1]) # retain best 3 leaders
                continue
                
            # Rest of the wolves update coordinates
            curr_pos = population[wolf_idx]
            new_pos = []
            for d_idx in range(k):
                # Choose component from Alpha, Beta, or Delta with random probability
                choice = rng.choice([alpha_pos[d_idx], beta_pos[d_idx], delta_pos[d_idx]])
                # Random walk step
                if rng.random() < 0.2:
                    new_node = rng.choice(nodes)
                else:
                    new_node = choice
                new_pos.append(new_node)
            new_population.append(new_pos)
            
        population = new_population

    yield {
        "kind": "algorithm_done",
        "facilities": alpha_pos,
        "facility_type": "fire_station",
        "fitness": alpha_fit,
        "op_count": max_iter * pop_size,
        "theoretical_complexity": "O(Iterations * PopSize * V * k)",
        "xai_text": f"Grey Wolf Optimization complete! Placed {k} fire stations at nodes {alpha_pos} "
                   f"confirming response radius of {alpha_fit:.2f} travel units."
    }


def ant_lion_optimizer(graph: WeightedGraph, k: int = 3, max_iter: int = 5, seed: int = 43):
    """Ant Lion Optimizer (2015) for fire station placement. Simulates trap avoidance."""
    rng = random.Random(seed)
    nodes = list(graph.nodes.keys())
    pop_size = 5
    ants = [rng.sample(nodes, k) for _ in range(pop_size)]
    antlions = [rng.sample(nodes, k) for _ in range(pop_size)]
    
    def fitness(pos):
        return sum(min(graph.get_edge_weight(n, f) if n != f else 0 for f in pos) for n in nodes) / len(nodes)

    for it in range(max_iter):
        # Find elite antlion
        lion_scores = [(fitness(al), al) for al in antlions]
        lion_scores.sort()
        elite_fit, elite_pos = lion_scores[0]
        
        # Random walks for ants
        new_ants = []
        for a in ants:
            # Walk towards elite and a chosen antlion
            chosen_lion = rng.choice(antlions)
            new_pos = []
            for d in range(k):
                val = rng.choice([elite_pos[d], chosen_lion[d], a[d]])
                if rng.random() < 0.3:
                    val = rng.choice(nodes)
                new_pos.append(val)
            new_ants.append(new_pos)
        ants = new_ants
        
        # Update antlions
        for i in range(pop_size):
            if fitness(ants[i]) < fitness(antlions[i]):
                antlions[i] = ants[i]
                
        yield {
            "kind": "iteration_complete",
            "iteration": it + 1,
            "best_fitness": round(elite_fit, 3),
            "alpha_pos": elite_pos,
            "op_count": (it + 1) * pop_size * 2,
            "xai_text": f"ALO Iteration {it + 1}: Elite Antlion trap established at nodes {elite_pos}. "
                       f"Average coverage distance: {elite_fit:.2f}."
        }
        time.sleep(0.3)
        
    yield {
        "kind": "algorithm_done",
        "facilities": elite_pos,
        "facility_type": "fire_station",
        "fitness": elite_fit,
        "op_count": max_iter * pop_size,
        "theoretical_complexity": "O(Max_Iter * Pop * V * k)",
        "xai_text": f"Ant Lion Optimization complete! Placed stations at {elite_pos}."
    }


def harris_hawks_optimization(graph: WeightedGraph, k: int = 3, max_iter: int = 5, seed: int = 44):
    """Harris Hawks Optimization (2019) for fire station placement. Cooperative hunting."""
    rng = random.Random(seed)
    nodes = list(graph.nodes.keys())
    pop_size = 5
    hawks = [rng.sample(nodes, k) for _ in range(pop_size)]
    
    def fitness(pos):
        return max(min(graph.get_edge_weight(n, f) if n != f else 0 for f in pos) for n in nodes)

    for it in range(max_iter):
        scores = [(fitness(hw), hw) for hw in hawks]
        scores.sort()
        rabbit_fit, rabbit_pos = scores[0]
        
        new_hawks = []
        for hw in hawks:
            # Energy of rabbit decays
            E = 2.0 * (1.0 - it/max_iter) * rng.uniform(-1, 1)
            if abs(E) >= 1.0: # Exploration
                new_hawks.append(rng.sample(nodes, k))
            else: # Exploitation (soft/hard besiege)
                new_pos = []
                for d in range(k):
                    if rng.random() < 0.5:
                        new_pos.append(rabbit_pos[d])
                    else:
                        new_pos.append(hw[d])
                new_hawks.append(new_pos)
        hawks = new_hawks
        
        yield {
            "kind": "iteration_complete",
            "iteration": it + 1,
            "best_fitness": round(rabbit_fit, 3),
            "alpha_pos": rabbit_pos,
            "op_count": (it + 1) * pop_size,
            "xai_text": f"HHO Iteration {it + 1}: Hawks converging on prey (rabbit position) at nodes {rabbit_pos}. Max distance: {rabbit_fit:.2f}."
        }
        time.sleep(0.3)
        
    yield {
        "kind": "algorithm_done",
        "facilities": rabbit_pos,
        "facility_type": "fire_station",
        "fitness": rabbit_fit,
        "op_count": max_iter * pop_size,
        "theoretical_complexity": "O(Max_Iter * Pop * V * k)",
        "xai_text": f"Harris Hawks Optimization complete! Stations placed at {rabbit_pos}."
    }


def coati_optimization_algorithm(graph: WeightedGraph, k: int = 3, max_iter: int = 5, seed: int = 45):
    """Coati Optimization Algorithm (2023) for fire station placement."""
    rng = random.Random(seed)
    nodes = list(graph.nodes.keys())
    pop_size = 5
    coatis = [rng.sample(nodes, k) for _ in range(pop_size)]
    
    def fitness(pos):
        return sum(min(graph.get_edge_weight(n, f) if n != f else 0 for f in pos) for n in nodes)

    for it in range(max_iter):
        scores = [(fitness(c), c) for c in coatis]
        scores.sort()
        best_fit, best_pos = scores[0]
        
        new_coatis = []
        for c in coatis:
            # Phase 1: Attack iguanas
            # Phase 2: Escape predators
            new_pos = []
            for d in range(k):
                if rng.random() < 0.6:
                    new_pos.append(best_pos[d])
                else:
                    new_pos.append(rng.choice(nodes))
            new_coatis.append(new_pos)
        coatis = new_coatis
        
        yield {
            "kind": "iteration_complete",
            "iteration": it + 1,
            "best_fitness": round(best_fit, 3),
            "alpha_pos": best_pos,
            "op_count": (it + 1) * pop_size,
            "xai_text": f"COA Iteration {it + 1}: Coatis climbing trees towards food source {best_pos}. Total distance: {best_fit:.2f}."
        }
        time.sleep(0.3)
        
    yield {
        "kind": "algorithm_done",
        "facilities": best_pos,
        "facility_type": "fire_station",
        "fitness": best_fit,
        "op_count": max_iter * pop_size,
        "theoretical_complexity": "O(Max_Iter * Pop * V * k)",
        "xai_text": f"Coati Optimization complete! Stations placed at {best_pos}."
    }


# ==============================================================================
# Category 2: Traffic Light Timing Optimization (WOA, RUN, PTBO, MPA)
# Goal: Find green phase intervals (seconds) at major hubs to minimize queue delays.
# ==============================================================================

def whale_optimization_algorithm(graph: WeightedGraph, max_iter: int = 5, seed: int = 46):
    """
    Whale Optimization Algorithm (2016) for traffic signal delays.
    Whales represent array of green times (seconds) for 4 main hubs.
    """
    rng = random.Random(seed)
    hubs = sorted(graph.nodes.keys(), key=str)[:4]  # optimize traffic signals at first 4 nodes
    if len(hubs) < 4: hubs = [0, 1, 2, 3]
    
    pop_size = 5
    # Position: green time in seconds [10, 60]
    whales = [[rng.uniform(10, 60) for _ in range(4)] for _ in range(pop_size)]
    
    def evaluate_delay(green_times):
        # Simulate traffic delay. Delay is high if green time is too short or too long
        total_delay = 0.0
        for i, node in enumerate(hubs):
            g = green_times[i]
            # Delays minimized around g = 35 seconds
            delay = (g - 35.0) ** 2 + 10.0
            total_delay += delay
        return total_delay

    for iteration in range(max_iter):
        scored = [(evaluate_delay(pos), pos) for pos in whales]
        scored.sort()
        best_delay, best_times = scored[0]
        
        yield {
            "kind": "iteration_complete",
            "iteration": iteration + 1,
            "best_fitness": round(best_delay, 2),
            "xai_text": f"WOA Iteration {iteration + 1}: Bubble-net encircling active. "
                       f"Best green times found: {[round(t,1) for t in best_times]}s. "
                       f"Simulated network delay: {best_delay:.1f} vehicle-minutes."
        }
        time.sleep(0.4)
        
        # Update positions
        new_whales = []
        for w in whales:
            a = 2.0 - iteration * (2.0 / max_iter)
            r = rng.random()
            p = rng.random()
            
            new_pos = []
            for d in range(4):
                if p < 0.5:
                    if abs(a) < 1.0: # shrink encircling
                        D = abs(best_times[d] - w[d])
                        val = best_times[d] - a * D
                    else: # search randomly
                        random_whale = rng.choice(whales)
                        D = abs(random_whale[d] - w[d])
                        val = random_whale[d] - a * D
                else: # spiral bubble net
                    D_prime = abs(best_times[d] - w[d])
                    l = rng.uniform(-1, 1)
                    val = D_prime * math.exp(0.5 * l) * math.cos(2 * math.pi * l) + best_times[d]
                
                val = max(10.0, min(60.0, val))
                new_pos.append(val)
            new_whales.append(new_pos)
        whales = new_whales

    yield {
        "kind": "algorithm_done",
        "facilities": hubs,
        "facility_type": "traffic_light",
        "fitness": best_delay,
        "optimal_green_times": [round(t,1) for t in best_times],
        "op_count": max_iter * pop_size,
        "theoretical_complexity": "O(Max_Iter * Pop * Signals)",
        "xai_text": f"Whale Optimization complete! Signal timings established for hubs {hubs}: "
                   f"{[round(t,1) for t in best_times]} seconds. Delay minimized to {best_delay:.2f}."
    }


def runge_kutta_optimizer(graph: WeightedGraph, max_iter: int = 5, seed: int = 47):
    """Runge-Kutta Optimization Algorithm (2021) for signal delays. Uses RK slope equations."""
    rng = random.Random(seed)
    hubs = sorted(graph.nodes.keys(), key=str)[:4]
    if len(hubs) < 4: hubs = [0, 1, 2, 3]
    pop_size = 5
    agents = [[rng.uniform(10, 60) for _ in range(4)] for _ in range(pop_size)]
    
    def fitness(pos):
        return sum((t - 32.0)**2 + 5.0 for t in pos)

    for it in range(max_iter):
        scored = [(fitness(a), a) for a in agents]
        scored.sort()
        best_fit, best_pos = scored[0]
        
        # Runge-Kutta slopes updating
        new_agents = []
        for a in agents:
            new_pos = []
            for d in range(4):
                # Calculate slopes k1, k2
                k1 = rng.uniform(-2, 2) * (best_pos[d] - a[d])
                k2 = rng.uniform(-2, 2) * (best_pos[d] - (a[d] + k1/2.0))
                val = a[d] + k2 + rng.uniform(-1, 1)
                val = max(10.0, min(60.0, val))
                new_pos.append(val)
            new_agents.append(new_pos)
        agents = new_agents
        
        yield {
            "kind": "iteration_complete",
            "iteration": it + 1,
            "best_fitness": round(best_fit, 2),
            "xai_text": f"RUN Iteration {it + 1}: Integrating Runge-Kutta slopes for traffic flows. "
                       f"Best signal times: {[round(x,1) for x in best_pos]}s. Queue length penalty: {best_fit:.1f}."
        }
        time.sleep(0.3)
        
    yield {
        "kind": "algorithm_done",
        "facilities": hubs,
        "facility_type": "traffic_light",
        "fitness": best_fit,
        "optimal_green_times": [round(x,1) for x in best_pos],
        "op_count": max_iter * pop_size,
        "theoretical_complexity": "O(Max_Iter * Pop * Signals)",
        "xai_text": f"Runge-Kutta Optimization complete! Signal times: {[round(x,1) for x in best_pos]}s."
    }


def painting_training_optimizer(graph: WeightedGraph, max_iter: int = 5, seed: int = 48):
    """Painting Training-Based Optimization (2025) for traffic signals. Simulates painting strokes."""
    rng = random.Random(seed)
    hubs = sorted(graph.nodes.keys(), key=str)[:4]
    if len(hubs) < 4: hubs = [0, 1, 2, 3]
    pop_size = 5
    canvases = [[rng.uniform(10, 60) for _ in range(4)] for _ in range(pop_size)]
    
    def fitness(pos):
        return sum((t - 28.0)**2 + 8.0 for t in pos)

    for it in range(max_iter):
        scored = [(fitness(c), c) for c in canvases]
        scored.sort()
        best_fit, best_stroke = scored[0]
        
        # Color mixing and brush strokes updating
        new_canvases = []
        for c in canvases:
            new_pos = []
            for d in range(4):
                # Blend with best stroke
                stroke = rng.uniform(0.1, 0.9)
                val = c[d] * (1 - stroke) + best_stroke[d] * stroke + rng.uniform(-1, 1)
                val = max(10.0, min(60.0, val))
                new_pos.append(val)
            new_canvases.append(new_pos)
        canvases = new_canvases
        
        yield {
            "kind": "iteration_complete",
            "iteration": it + 1,
            "best_fitness": round(best_fit, 2),
            "xai_text": f"PTBO Iteration {it + 1}: Blending canvas layers for intersection signals. "
                       f"Best times: {[round(x,1) for x in best_stroke]}s. Cost: {best_fit:.1f}."
        }
        time.sleep(0.3)
        
    yield {
        "kind": "algorithm_done",
        "facilities": hubs,
        "facility_type": "traffic_light",
        "fitness": best_fit,
        "optimal_green_times": [round(x,1) for x in best_stroke],
        "op_count": max_iter * pop_size,
        "theoretical_complexity": "O(Max_Iter * Pop * Signals)",
        "xai_text": f"PTBO signal layout complete! Optimized green phases: {[round(x,1) for x in best_stroke]}s."
    }


def marine_predators_algorithm(graph: WeightedGraph, max_iter: int = 5, seed: int = 49):
    """Marine Predators Algorithm (2020) for public transit schedules. Prey-predator loops."""
    rng = random.Random(seed)
    hubs = sorted(graph.nodes.keys(), key=str)[:4]
    if len(hubs) < 4: hubs = [0, 1, 2, 3]
    pop_size = 5
    prey = [[rng.uniform(10, 60) for _ in range(4)] for _ in range(pop_size)]
    
    def fitness(pos):
        return sum((t - 30.0)**2 for t in pos)

    for it in range(max_iter):
        scored = [(fitness(p), p) for p in prey]
        scored.sort()
        best_fit, elite_predator = scored[0]
        
        # Predator-prey interactions (Levy flights)
        new_prey = []
        for p in prey:
            new_pos = []
            for d in range(4):
                if it < max_iter / 2: # phase 1: high velocity ratio
                    val = p[d] + rng.uniform(-1, 1) * (elite_predator[d] - p[d])
                else: # phase 2: predator hunting
                    val = elite_predator[d] + rng.uniform(-1, 1) * p[d]
                val = max(10.0, min(60.0, val))
                new_pos.append(val)
            new_prey.append(new_pos)
        prey = new_prey
        
        yield {
            "kind": "iteration_complete",
            "iteration": it + 1,
            "best_fitness": round(best_fit, 2),
            "xai_text": f"MPA Iteration {it + 1}: Predators patrolling schedule space. "
                       f"Optimal Green times: {[round(x,1) for x in elite_predator]}s. Fitness: {best_fit:.2f}."
        }
        time.sleep(0.3)
        
    yield {
        "kind": "algorithm_done",
        "facilities": hubs,
        "facility_type": "traffic_light",
        "fitness": best_fit,
        "optimal_green_times": [round(x,1) for x in elite_predator],
        "op_count": max_iter * pop_size,
        "theoretical_complexity": "O(Max_Iter * Pop * Signals)",
        "xai_text": f"MPA schedule optimization complete! Signal times: {[round(x,1) for x in elite_predator]}s."
    }


# ==============================================================================
# Category 3: Wireless Signal Coverage Placement (MFO, GOA, AO, DO)
# Goal: Place 3 antennas on nodes to maximize coverage weight (sum of pop weights).
# ==============================================================================

def moth_flame_optimization(graph: WeightedGraph, k: int = 3, max_iter: int = 5, seed: int = 50):
    """
    Moth-Flame Optimization (2015) for cellular antenna placement.
    Moths represent positions of antennas (lists of node IDs).
    Flames are the best positions saved.
    """
    rng = random.Random(seed)
    nodes = list(graph.nodes.keys())
    if not nodes: return
    
    pop_size = 5
    moths = [rng.sample(nodes, k) for _ in range(pop_size)]
    
    def evaluate_coverage(position):
        # We want to maximize population coverage.
        # Covered nodes are those within 3 edges of any antenna.
        # Fitness is 1000.0 - total covered population weight (so we can minimize it).
        covered = set()
        for ant in position:
            covered.add(ant)
            # Add neighbors
            for neighbor_edge in graph.neighbors(ant):
                n = neighbor_edge["to"]
                covered.add(n)
                # 2nd hop
                for n2_edge in graph.neighbors(n):
                    covered.add(n2_edge["to"])
                    
        total_weight = sum(graph.nodes[n].get("pop_weight", 1.0) for n in covered if n in graph.nodes)
        return 1000.0 - total_weight

    for iteration in range(max_iter):
        scored = [(evaluate_coverage(pos), pos) for pos in moths]
        scored.sort()
        
        # Best position
        best_fit, best_flame = scored[0]
        covered_pop = 1000.0 - best_fit
        
        yield {
            "kind": "iteration_complete",
            "iteration": iteration + 1,
            "best_fitness": round(covered_pop, 2),
            "xai_text": f"MFO Iteration {iteration + 1}: Moths flying around flames (best nodes {best_flame}). "
                       f"Population covered: {covered_pop:.1f} citizens."
        }
        time.sleep(0.4)
        
        # Update moths
        new_moths = []
        for idx, moth in enumerate(moths):
            # Number of flames decreases logarithmically
            flame_idx = min(idx, len(scored) - 1)
            target_flame = scored[flame_idx][1]
            
            # Spiral flight towards flame
            t = -1.0 + iteration * (1.0 / max_iter)  # t in [-1, 0]
            new_pos = []
            for d in range(k):
                # We either fly towards flame or sample randomly
                if rng.random() < abs(t):
                    new_pos.append(target_flame[d])
                else:
                    new_pos.append(rng.choice(nodes))
            new_moths.append(new_pos)
        moths = new_moths

    yield {
        "kind": "algorithm_done",
        "facilities": best_flame,
        "facility_type": "antenna",
        "fitness": 1000.0 - best_fit,
        "op_count": max_iter * pop_size,
        "xai_text": f"Moth-Flame Optimization complete! Placed antenna towers at {best_flame} "
                   f"providing 5G cell signals to {1000.0 - best_fit:.1f} weight-units of the population."
    }


def grasshopper_optimization_algorithm(graph: WeightedGraph, k: int = 3, max_iter: int = 5, seed: int = 51):
    """Grasshopper Optimization Algorithm (2017) for wireless antenna placement. Simulates grasshopper swarming."""
    rng = random.Random(seed)
    nodes = list(graph.nodes.keys())
    pop_size = 5
    hoppers = [rng.sample(nodes, k) for _ in range(pop_size)]
    
    def fitness(pos):
        covered = set()
        for p in pos:
            covered.add(p)
            for n in graph.neighbors(p):
                covered.add(n["to"])
        return sum(graph.nodes[n].get("pop_weight", 1.0) for n in covered if n in graph.nodes)

    for it in range(max_iter):
        scored = [(fitness(h), h) for h in hoppers]
        scored.sort(reverse=True)
        best_fit, best_pos = scored[0]
        
        # Grasshopper attraction/repulsion coefficient c decays
        c = 1.0 - it * (1.0 / max_iter)
        
        new_hoppers = []
        for h in hoppers:
            new_pos = []
            for d in range(k):
                if rng.random() < c:
                    new_pos.append(best_pos[d])
                else:
                    new_pos.append(rng.choice(nodes))
            new_hoppers.append(new_pos)
        hoppers = new_hoppers
        
        yield {
            "kind": "iteration_complete",
            "iteration": it + 1,
            "best_fitness": round(best_fit, 2),
            "xai_text": f"GOA Iteration {it + 1}: Grasshoppers repelled/attracted in space. Best antennas: {best_pos}. Coverage: {best_fit:.1f} pop."
        }
        time.sleep(0.3)
        
    yield {
        "kind": "algorithm_done",
        "facilities": best_pos,
        "facility_type": "antenna",
        "fitness": best_fit,
        "op_count": max_iter * pop_size,
        "theoretical_complexity": "O(Max_Iter * Pop * V)",
        "xai_text": f"Grasshopper antenna grid laid at {best_pos} with coverage {best_fit:.2f}."
    }


def aquila_optimizer(graph: WeightedGraph, k: int = 3, max_iter: int = 5, seed: int = 52):
    """Aquila Optimizer (2021) for wireless coverage. Swooping flight hunting behavior."""
    rng = random.Random(seed)
    nodes = list(graph.nodes.keys())
    pop_size = 5
    aquilas = [rng.sample(nodes, k) for _ in range(pop_size)]
    
    def fitness(pos):
        covered = set()
        for p in pos:
            covered.add(p)
            for n in graph.neighbors(p):
                covered.add(n["to"])
        return sum(graph.nodes[n].get("pop_weight", 1.0) for n in covered if n in graph.nodes)

    for it in range(max_iter):
        scored = [(fitness(a), a) for a in aquilas]
        scored.sort(reverse=True)
        best_fit, best_pos = scored[0]
        
        new_aquilas = []
        for a in aquilas:
            new_pos = []
            for d in range(k):
                # Swoop attack towards best prey
                if rng.random() < 0.5:
                    new_pos.append(best_pos[d])
                else:
                    new_pos.append(rng.choice(nodes))
            new_aquilas.append(new_pos)
        aquilas = new_aquilas
        
        yield {
            "kind": "iteration_complete",
            "iteration": it + 1,
            "best_fitness": round(best_fit, 2),
            "xai_text": f"AO Iteration {it + 1}: Aquila soaring high, looking for optimal coverage targets. Best: {best_pos}. Population: {best_fit:.1f}."
        }
        time.sleep(0.3)
        
    yield {
        "kind": "algorithm_done",
        "facilities": best_pos,
        "facility_type": "antenna",
        "fitness": best_fit,
        "op_count": max_iter * pop_size,
        "theoretical_complexity": "O(Max_Iter * Pop * V)",
        "xai_text": f"Aquila tower optimization complete! Antennas at {best_pos}."
    }


def dandelion_optimizer(graph: WeightedGraph, k: int = 3, max_iter: int = 5, seed: int = 53):
    """Dandelion Optimizer (2022) for cellular signal coverage. Simulates seed wind sowing."""
    rng = random.Random(seed)
    nodes = list(graph.nodes.keys())
    pop_size = 5
    seeds = [rng.sample(nodes, k) for _ in range(pop_size)]
    
    def fitness(pos):
        covered = set()
        for p in pos:
            covered.add(p)
            for n in graph.neighbors(p):
                covered.add(n["to"])
        return sum(graph.nodes[n].get("pop_weight", 1.0) for n in covered if n in graph.nodes)

    for it in range(max_iter):
        scored = [(fitness(s), s) for s in seeds]
        scored.sort(reverse=True)
        best_fit, best_pos = scored[0]
        
        # Wind blowing seeds randomly with decrease
        new_seeds = []
        for s in seeds:
            new_pos = []
            for d in range(k):
                if rng.random() < 0.7:
                    new_pos.append(best_pos[d])
                else:
                    # Blow to a neighbor node
                    neighbors = [e["to"] for e in graph.neighbors(s[d])]
                    new_pos.append(rng.choice(neighbors) if neighbors else rng.choice(nodes))
            new_seeds.append(new_pos)
        seeds = new_seeds
        
        yield {
            "kind": "iteration_complete",
            "iteration": it + 1,
            "best_fitness": round(best_fit, 2),
            "xai_text": f"DO Iteration {it + 1}: Dandelion seeds floating in wind currents. Best tower: {best_pos}. Pop: {best_fit:.1f}."
        }
        time.sleep(0.3)
        
    yield {
        "kind": "algorithm_done",
        "facilities": best_pos,
        "facility_type": "antenna",
        "fitness": best_fit,
        "op_count": max_iter * pop_size,
        "theoretical_complexity": "O(Max_Iter * Pop * V)",
        "xai_text": f"Dandelion optimization complete! Antennas set at {best_pos}."
    }


# ==============================================================================
# Category 4: Utility backbone grid upgrades (SSA, SMA, AOA, GTO)
# Goal: Select 4 major edges to upgrade to grid pipelines to balance utility flow.
# ==============================================================================

def salp_swarm_algorithm(graph: WeightedGraph, max_iter: int = 5, seed: int = 54):
    """
    Salp Swarm Algorithm (2017) for utility power line grid balancing.
    Salp chain represents selected edges to upgrade.
    """
    rng = random.Random(seed)
    edges = graph.get_all_edges()
    if not edges: return
    
    pop_size = 5
    # Position: select 3 indices of edges to upgrade
    swarm = [rng.sample(range(len(edges)), 3) for _ in range(pop_size)]
    
    def evaluate_loss(edge_indices):
        # We want to minimize the flow resistance.
        # Loss is sum of weights of upgraded edges (we want cheap, strong backbone lines)
        # combined with connection coverage.
        return sum(edges[idx]["weight"] for idx in edge_indices)

    for iteration in range(max_iter):
        scored = [(evaluate_loss(pos), pos) for pos in swarm]
        scored.sort() # lower loss is better
        
        best_loss, best_indices = scored[0]
        best_edges = [edges[i] for i in best_indices]
        
        yield {
            "kind": "iteration_complete",
            "iteration": iteration + 1,
            "best_fitness": round(best_loss, 2),
            "xai_text": f"SSA Iteration {iteration + 1}: Salp leader directing the swarm towards food source. "
                       f"Upgraded lines loss score: {best_loss:.2f}. Swarm chain maintaining cohesion."
        }
        time.sleep(0.4)
        
        # Update followers
        new_swarm = []
        for idx in range(pop_size):
            if idx == 0: # leader salp updates towards food
                c1 = 2 * math.exp(-(4 * iteration / max_iter)**2)
                new_pos = []
                for d in range(3):
                    c2 = rng.random()
                    c3 = rng.random()
                    if c3 < 0.5:
                        val = best_indices[d] + c1 * ((len(edges) - 1) * c2)
                    else:
                        val = best_indices[d] - c1 * ((len(edges) - 1) * c2)
                    val = max(0, min(len(edges) - 1, int(val)))
                    new_pos.append(val)
                new_swarm.append(new_pos)
            else: # followers follow the salp in front
                prev_salp = swarm[idx - 1]
                new_pos = [(prev_salp[d] + swarm[idx][d]) // 2 for d in range(3)]
                new_swarm.append(new_pos)
        swarm = new_swarm

    # Set edge states to relaxed (backbone)
    for e in best_edges:
        graph.apply_weather_event({"type": "UPGRADE", "affected_edges": [{"u": e["u"], "v": e["v"]}], "effect_weight_multiplier": 0.5, "effect_capacity_multiplier": 2.0})

    yield {
        "kind": "algorithm_done",
        "facilities": [e["u"] for e in best_edges],
        "upgraded_edges": [(e["u"], e["v"]) for e in best_edges],
        "fitness": best_loss,
        "op_count": max_iter * pop_size,
        "xai_text": f"Salp Swarm Algorithm complete! Upgraded utility power lines between {[ (e['u'], e['v']) for e in best_edges ]}. "
                   f"Grid flow loss minimized to {best_loss:.2f}."
    }


def slime_mould_algorithm(graph: WeightedGraph, max_iter: int = 5, seed: int = 55):
    """Slime Mould Algorithm (2020) for organic road grid laying. Simulates Physarum foraging networks."""
    rng = random.Random(seed)
    edges = graph.get_all_edges()
    pop_size = 5
    moulds = [rng.sample(range(len(edges)), 3) for _ in range(pop_size)]
    
    def fitness(pos):
        return sum(edges[i]["weight"] for i in pos)

    for it in range(max_iter):
        scored = [(fitness(m), m) for m in moulds]
        scored.sort()
        best_fit, best_tubes = scored[0]
        
        # Tube contraction based on flow weights
        new_moulds = []
        for m in moulds:
            new_pos = []
            for d in range(3):
                # Thicken popular paths, thin out weak paths
                if rng.random() < 0.7:
                    new_pos.append(best_tubes[d])
                else:
                    new_pos.append(rng.randint(0, len(edges)-1))
            new_moulds.append(new_pos)
        moulds = new_moulds
        
        yield {
            "kind": "iteration_complete",
            "iteration": it + 1,
            "best_fitness": round(best_fit, 2),
            "xai_text": f"SMA Iteration {it + 1}: Slime mould tubes pulsating. Organic highway connection: {[(edges[i]['u'], edges[i]['v']) for i in best_tubes]}. Loss: {best_fit:.2f}."
        }
        time.sleep(0.3)
        
    yield {
        "kind": "algorithm_done",
        "upgraded_edges": [(edges[i]["u"], edges[i]["v"]) for i in best_tubes],
        "fitness": best_fit,
        "op_count": max_iter * pop_size,
        "theoretical_complexity": "O(Max_Iter * Pop)",
        "xai_text": f"Slime Mould optimization complete! Organic highways: {[(edges[i]['u'], edges[i]['v']) for i in best_tubes]}."
    }


def arithmetic_optimization_algorithm(graph: WeightedGraph, max_iter: int = 5, seed: int = 56):
    """Arithmetic Optimization Algorithm (2021) for utility network balancing. Uses math operators (+, -, *, /)."""
    rng = random.Random(seed)
    edges = graph.get_all_edges()
    pop_size = 5
    agents = [rng.sample(range(len(edges)), 3) for _ in range(pop_size)]
    
    def fitness(pos):
        return sum(edges[i]["weight"] for i in pos)

    for it in range(max_iter):
        scored = [(fitness(a), a) for a in agents]
        scored.sort()
        best_fit, best_pos = scored[0]
        
        # Math Optimizer Accelerated (MOA) function
        MOA = 0.2 + it * (0.8 / max_iter)
        
        new_agents = []
        for a in agents:
            new_pos = []
            for d in range(3):
                r1 = rng.random()
                if r1 > MOA: # Division / Multiplication
                    if rng.random() < 0.5:
                        val = best_pos[d] / (rng.uniform(0.8, 1.2))
                    else:
                        val = best_pos[d] * (rng.uniform(0.8, 1.2))
                else: # Addition / Subtraction
                    if rng.random() < 0.5:
                        val = best_pos[d] + rng.uniform(-5, 5)
                    else:
                        val = best_pos[d] - rng.uniform(-5, 5)
                val = max(0, min(len(edges) - 1, int(val)))
                new_pos.append(val)
            new_agents.append(new_pos)
        agents = new_agents
        
        yield {
            "kind": "iteration_complete",
            "iteration": it + 1,
            "best_fitness": round(best_fit, 2),
            "xai_text": f"AOA Iteration {it + 1}: Executing arithmetic operators. Best utility links: {[(edges[i]['u'], edges[i]['v']) for i in best_pos]}. Fitness: {best_fit:.2f}."
        }
        time.sleep(0.3)
        
    yield {
        "kind": "algorithm_done",
        "upgraded_edges": [(edges[i]["u"], edges[i]["v"]) for i in best_pos],
        "fitness": best_fit,
        "op_count": max_iter * pop_size,
        "theoretical_complexity": "O(Max_Iter * Pop)",
        "xai_text": f"AOA optimization complete! Utility links upgraded: {[(edges[i]['u'], edges[i]['v']) for i in best_pos]}."
    }


def gorilla_troops_optimizer(graph: WeightedGraph, max_iter: int = 5, seed: int = 57):
    """Gorilla Troops Optimizer (2021) for power line updates. Troop movements and leadership dynamics."""
    rng = random.Random(seed)
    edges = graph.get_all_edges()
    pop_size = 5
    troops = [rng.sample(range(len(edges)), 3) for _ in range(pop_size)]
    
    def fitness(pos):
        return sum(edges[i]["weight"] for i in pos)

    for it in range(max_iter):
        scored = [(fitness(t), t) for t in troops]
        scored.sort()
        silverback_fit, silverback_pos = scored[0]
        
        new_troops = []
        for t in troops:
            new_pos = []
            for d in range(3):
                # Follow Silverback leader
                if rng.random() < 0.6:
                    new_pos.append(silverback_pos[d])
                else:
                    new_pos.append(rng.randint(0, len(edges)-1))
            new_troops.append(new_pos)
        troops = new_troops
        
        yield {
            "kind": "iteration_complete",
            "iteration": it + 1,
            "best_fitness": round(silverback_fit, 2),
            "xai_text": f"GTO Iteration {it + 1}: Gorilla Silverback leading troop to resource {[(edges[i]['u'], edges[i]['v']) for i in silverback_pos]}. Cost: {silverback_fit:.2f}."
        }
        time.sleep(0.3)
        
    yield {
        "kind": "algorithm_done",
        "upgraded_edges": [(edges[i]["u"], edges[i]["v"]) for i in silverback_pos],
        "fitness": silverback_fit,
        "op_count": max_iter * pop_size,
        "theoretical_complexity": "O(Max_Iter * Pop)",
        "xai_text": f"GTO complete! Utility lines upgraded at: {[(edges[i]['u'], edges[i]['v']) for i in silverback_pos]}."
    }
