"""Solvers for the 10K CSS Renderer routing problem: SA, wave-based, and greedy."""

import time

from dimod import cqm_to_bqm
import neal

import css_renderer_config as cfg
from css_renderer_agents import can_assign


def solve_sa(cqm, time_limit=cfg.CLASSICAL_TIME_BUDGET):
    """Solve via CQM-to-BQM conversion and simulated annealing.

    Args:
        cqm: ConstrainedQuadraticModel to solve
        time_limit: Maximum time in seconds (default 600 = 10 minutes)

    Returns:
        sampleset from neal.SimulatedAnnealingSampler.
    """
    print("Converting CQM to BQM...")
    start_time = time.time()
    bqm, _ = cqm_to_bqm(cqm, lagrange_multiplier=cfg.LAGRANGE_MULTIPLIER)
    convert_time = time.time() - start_time

    print(f"BQM variables: {len(bqm.variables)} (includes slack)")
    print(f"BQM quadratic terms: {len(bqm.quadratic)}")
    print(f"Conversion time: {convert_time:.1f}s")

    num_intents = sum(1 for c in cqm.constraints if 'assign_' in str(c))
    remaining_time = max(10, time_limit - convert_time - 10)  # Leave buffer

    print(f"\nRunning simulated annealing on {num_intents}-intent problem...")
    print(f"Time budget: {remaining_time:.0f}s")
    print(f"Reads: {cfg.NUM_READS}, Sweeps: {cfg.NUM_SWEEPS}")

    start_time = time.time()
    sampler = neal.SimulatedAnnealingSampler()

    sampleset = sampler.sample(
        bqm,
        num_reads=cfg.NUM_READS,
        num_sweeps=cfg.NUM_SWEEPS
    )

    solve_time = time.time() - start_time
    print(f"Solve time: {solve_time:.1f}s")
    print(f"Best energy: {sampleset.first.energy:.2f}")

    return sampleset


def solve_wave_based(waves, agents, agent_names, time_per_wave=120):
    """Solve using wave-based decomposition.

    Each wave (pipeline stage) is solved independently.
    Cross-wave dependencies are handled by solving stages in order.

    Args:
        waves: List of (stage_name, cqm, x_vars, intent_indices) from build_wave_cqms
        agents: Dict of agent definitions
        agent_names: List of agent names
        time_per_wave: Time limit per wave in seconds

    Returns:
        dict: Combined assignments from all waves
    """
    print("\nSolving with wave-based decomposition...")
    all_assignments = {}
    agent_loads = {name: 0 for name in agent_names}

    for stage, cqm, x, intent_indices in waves:
        print(f"\n  Solving {stage} ({len(intent_indices)} intents)...")

        # Adjust capacity constraints based on remaining capacity
        # (This is a simplified approach - full implementation would rebuild CQM)

        start_time = time.time()

        # Convert and solve this wave
        bqm, _ = cqm_to_bqm(cqm, lagrange_multiplier=cfg.LAGRANGE_MULTIPLIER)
        sampler = neal.SimulatedAnnealingSampler()
        sampleset = sampler.sample(bqm, num_reads=cfg.NUM_READS, num_sweeps=cfg.NUM_SWEEPS)

        # Extract assignments
        best = sampleset.first
        wave_assignments = {}

        for var, val in best.sample.items():
            if val == 1 and var.startswith(f'x_{stage}_'):
                parts = var.split('_')
                local_i = int(parts[2])
                j = int(parts[3])
                global_i = intent_indices[local_i]
                wave_assignments[global_i] = agent_names[j]

        # Update global assignments and track loads
        for global_i, agent_name in wave_assignments.items():
            all_assignments[global_i] = agent_name
            agent_loads[agent_name] += 1

        solve_time = time.time() - start_time
        print(f"    Solved in {solve_time:.1f}s, {len(wave_assignments)} assignments")

    print(f"\nTotal wave assignments: {len(all_assignments)}")
    return all_assignments


def parse_assignments(sampleset, agent_names):
    """Extract intent-to-agent assignments from the best sample.

    Args:
        sampleset: SampleSet from a solver
        agent_names: List of agent names

    Returns:
        dict mapping intent index to agent name.
    """
    best = sampleset.first
    assignments = {}

    for var, val in best.sample.items():
        if val == 1 and var.startswith('x_'):
            parts = var.split('_')
            if len(parts) == 3:
                i, j = int(parts[1]), int(parts[2])
                assignments[i] = agent_names[j]

    return assignments


def greedy_solve(intents, agents):
    """Greedy baseline: cheapest valid agent, first come first served.

    Args:
        intents: List of intent dicts
        agents: Dict of agent definitions

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


def solve_with_fallback(intents, agents, agent_names, time_limit=cfg.CLASSICAL_TIME_BUDGET):
    """Attempt monolithic solve, fall back to wave-based if too large.

    Args:
        intents: List of intent dicts
        agents: Dict of agent definitions
        agent_names: List of agent names
        time_limit: Maximum time in seconds

    Returns:
        (assignments, method_used): assignments dict and method string
    """
    from css_renderer_model import build_cqm, build_wave_cqms, estimate_problem_size

    # First, estimate problem size
    estimates = estimate_problem_size(intents, agents, agent_names)
    print("Problem Size Analysis:")
    print(f"  Valid assignments: {estimates['valid_assignments']:,}")
    print(f"  Est. quadratic terms: {estimates['estimated_quadratic_terms']:,.0f}")

    # Decide strategy based on size
    # If > 500K variables or > 10M quadratic terms, use wave-based
    use_wave = (estimates['valid_assignments'] > 500000 or
                estimates['estimated_quadratic_terms'] > 10_000_000)

    if use_wave:
        print("\nProblem too large for monolithic solve, using wave-based decomposition...")
        waves = build_wave_cqms(intents, agents, agent_names)
        assignments = solve_wave_based(waves, agents, agent_names)
        return assignments, 'wave-based'
    else:
        print("\nBuilding monolithic CQM...")
        cqm, x = build_cqm(intents, agents, agent_names)
        sampleset = solve_sa(cqm, time_limit)
        assignments = parse_assignments(sampleset, agent_names)
        return assignments, 'monolithic-sa'


if __name__ == '__main__':
    # Test solvers
    from css_renderer_intents import generate_intents, build_workflow_chains
    from css_renderer_agents import build_agent_pool

    print("Testing 10K Solvers")
    print("=" * 50)

    agents, agent_names = build_agent_pool()
    intents = generate_intents()
    workflow_chains = build_workflow_chains(intents)

    print(f"\nGenerated {len(intents)} intents")
    print(f"Agent pool: {len(agent_names)} agents")

    # Test greedy
    print("\n" + "=" * 50)
    print("Testing Greedy Solver...")
    greedy_assignments, greedy_cost = greedy_solve(intents, agents)
    print(f"Greedy assigned {len(greedy_assignments)}/{len(intents)} tasks")
    print(f"Greedy cost: ${greedy_cost:.2f}")

    # Test main solver with fallback
    print("\n" + "=" * 50)
    print("Testing Main Solver (with fallback)...")
    assignments, method = solve_with_fallback(intents, agents, agent_names)
    print(f"Method used: {method}")
    print(f"Assigned {len(assignments)}/{len(intents)} tasks")
