"""Solvers for the QAAS routing problem: SA, D-Wave hybrid, and greedy."""

import time

from dimod import cqm_to_bqm
from dwave.system import LeapHybridCQMSampler
import neal

import config as cfg
from agents import can_assign


def solve_sa(cqm):
    """Solve via CQM-to-BQM conversion and simulated annealing.

    Returns:
        sampleset from neal.SimulatedAnnealingSampler.
    """
    print("Converting CQM to BQM...")
    bqm, _ = cqm_to_bqm(cqm, lagrange_multiplier=cfg.LAGRANGE_MULTIPLIER)

    print(f"BQM variables: {len(bqm.variables)} (includes slack)")
    print(f"BQM quadratic terms: {len(bqm.quadratic)}")

    num_intents = sum(1 for c in cqm.constraints if c.startswith('assign_'))
    print(f"\nRunning simulated annealing on {num_intents}-intent problem...")
    start_time = time.time()

    sampler = neal.SimulatedAnnealingSampler()
    sampleset = sampler.sample(bqm, num_reads=cfg.NUM_READS, num_sweeps=cfg.NUM_SWEEPS)

    solve_time = time.time() - start_time
    print(f"Solve time: {solve_time:.1f}s")
    print(f"Best energy: {sampleset.first.energy:.2f}")

    return sampleset


def solve_hybrid(cqm):
    """Solve via D-Wave Leap hybrid CQM sampler.

    Requires a valid D-Wave Leap API token.

    Returns:
        sampleset from LeapHybridCQMSampler.
    """
    sampler = LeapHybridCQMSampler()
    sampleset = sampler.sample_cqm(cqm, time_limit=cfg.HYBRID_TIME_LIMIT)

    feasible = sampleset.filter(lambda s: s.is_feasible)
    if feasible:
        best = feasible.first
        print(f"Best feasible energy: {best.energy}")
        print(f"QPU access time: {sampleset.info.get('qpu_access_time', 'N/A')} us")
    else:
        print("No feasible solution found")

    return sampleset


def parse_assignments(sampleset, agent_names):
    """Extract intent-to-agent assignments from the best sample.

    Returns:
        dict mapping intent index to agent name.
    """
    best = sampleset.first
    assignments = {}
    for var, val in best.sample.items():
        if val == 1 and var.startswith('x_'):
            parts = var.split('_')
            i, j = int(parts[1]), int(parts[2])
            assignments[i] = agent_names[j]
    return assignments


def greedy_solve(intents, agents):
    """Greedy baseline: cheapest valid agent, first come first served.

    Returns:
        (assignments, cost): assignments maps intent index to agent name.
    """
    names = list(agents.keys())
    result = {}
    load = {a: 0 for a in agents}
    cost = 0

    for idx, intent in enumerate(intents):
        best = None
        best_cost = float('inf')
        for name in names:
            a = agents[name]
            if intent['complexity'] not in a['capabilities']:
                continue
            if a['quality'] < intent['min_quality']:
                continue
            if load[name] >= a['capacity']:
                continue
            task_cost = intent['estimated_tokens'] * a['token_rate']
            if task_cost < best_cost:
                best_cost = task_cost
                best = name
        if best:
            result[idx] = best
            load[best] += 1
            cost += intent['estimated_tokens'] * agents[best]['token_rate']

    return result, cost
