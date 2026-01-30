"""CQM construction and cost functions for 10K CSS Renderer."""

import time

from dimod import ConstrainedQuadraticModel, Binary

import css_renderer_config as cfg
from css_renderer_agents import can_assign


def get_cost(intent, agent_name, agents):
    """Compute assignment cost: token cost + overkill penalty + latency.

    Args:
        intent: Intent dict with estimated_tokens
        agent_name: Name of the agent
        agents: Dict of all agent definitions

    Returns:
        float: Total cost for this assignment
    """
    agent = agents[agent_name]
    token_cost = intent['estimated_tokens'] * agent['token_rate']
    quality_surplus = agent['quality'] - intent['min_quality']
    overkill_cost = quality_surplus * token_cost * cfg.OVERKILL_WEIGHT
    latency_cost = agent['latency'] * cfg.LATENCY_WEIGHT
    return token_cost + overkill_cost + latency_cost


def build_cqm(intents, agents, agent_names):
    """Build a Constrained Quadratic Model for the 10K assignment problem.

    For 10K scale, this creates a large CQM that may need decomposition
    for classical solvers. The function reports statistics to help decide
    whether to use wave-based decomposition.

    Args:
        intents: List of intent dicts
        agents: Dict of agent definitions
        agent_names: List of agent names

    Returns:
        (cqm, x): the CQM and the dict of Binary decision variables
            keyed by (intent_index, agent_index).
    """
    num_intents = len(intents)
    num_agents = len(agent_names)

    print(f"Building CQM: {num_intents} tasks x {num_agents} agents")
    start_time = time.time()

    cqm = ConstrainedQuadraticModel()

    # Decision variables — only valid (intent, agent) pairs
    x = {}
    valid_count = 0
    filtered_count = 0

    for i, intent in enumerate(intents):
        for j, name in enumerate(agent_names):
            if can_assign(intent, name, agents):
                x[i, j] = Binary(f'x_{i}_{j}')
                valid_count += 1
            else:
                filtered_count += 1

    print(f"Valid assignments: {valid_count}")
    print(f"Filtered out: {filtered_count}")

    # Objective: minimize cost + dependency quality penalties
    objective = 0
    for (i, j), var in x.items():
        objective += get_cost(intents[i], agent_names[j], agents) * var

    # Dependency penalty terms
    dep_terms = 0
    for i, intent in enumerate(intents):
        for dep_idx in intent.get('depends', []):
            for j in range(num_agents):
                for k in range(num_agents):
                    if (i, j) in x and (dep_idx, k) in x:
                        if agents[agent_names[j]]['quality'] < agents[agent_names[k]]['quality']:
                            objective += cfg.DEP_PENALTY * x[i, j] * x[dep_idx, k]
                            dep_terms += 1

    cqm.set_objective(objective)
    print(f"Dependency penalty terms: {dep_terms}")

    # Hard constraints: each intent assigned to exactly one agent
    for i in range(num_intents):
        valid = [x[i, j] for j in range(num_agents) if (i, j) in x]
        if valid:
            cqm.add_constraint(sum(valid) == 1, label=f'assign_{i}')

    # Hard constraints: agent capacity limits
    for j, name in enumerate(agent_names):
        cap = agents[name]['capacity']
        assigned = [x[i, j] for i in range(num_intents) if (i, j) in x]
        if assigned:
            cqm.add_constraint(sum(assigned) <= cap, label=f'cap_{name}')

    build_time = time.time() - start_time
    print(f"Constraints: {len(cqm.constraints)}")
    print(f"Build time: {build_time:.2f}s")

    return cqm, x


def build_wave_cqms(intents, agents, agent_names):
    """Build separate CQMs for each pipeline stage (wave-based decomposition).

    This is a fallback for when the monolithic CQM is too large.
    Each wave (stage) is solved independently, then cross-wave
    dependencies are resolved in post-processing.

    Args:
        intents: List of intent dicts
        agents: Dict of agent definitions
        agent_names: List of agent names

    Returns:
        List of (stage_name, cqm, x_vars, intent_indices) tuples
    """
    print("Building wave-based CQMs (one per pipeline stage)...")
    start_time = time.time()

    # Group intents by stage
    stage_intents = {stage: [] for stage in cfg.PIPELINE_STAGES}
    for idx, intent in enumerate(intents):
        stage_intents[intent['stage']].append(idx)

    waves = []

    for stage in cfg.PIPELINE_STAGES:
        intent_indices = stage_intents[stage]
        num_stage_intents = len(intent_indices)

        print(f"\n  Building {stage}: {num_stage_intents} intents")

        cqm = ConstrainedQuadraticModel()
        x = {}

        # Create variables for this stage only
        for local_i, global_i in enumerate(intent_indices):
            intent = intents[global_i]
            for j, name in enumerate(agent_names):
                if can_assign(intent, name, agents):
                    x[local_i, j] = Binary(f'x_{stage}_{local_i}_{j}')

        # Objective
        objective = 0
        for (local_i, j), var in x.items():
            global_i = intent_indices[local_i]
            objective += get_cost(intents[global_i], agent_names[j], agents) * var

        # Intra-stage dependencies only
        dep_terms = 0
        for local_i, global_i in enumerate(intent_indices):
            intent = intents[global_i]
            for dep_global_idx in intent.get('depends', []):
                # Only include if dependency is in same stage
                if dep_global_idx in intent_indices:
                    dep_local_idx = intent_indices.index(dep_global_idx)
                    for j in range(len(agent_names)):
                        for k in range(len(agent_names)):
                            if (local_i, j) in x and (dep_local_idx, k) in x:
                                if agents[agent_names[j]]['quality'] < agents[agent_names[k]]['quality']:
                                    objective += cfg.DEP_PENALTY * x[local_i, j] * x[dep_local_idx, k]
                                    dep_terms += 1

        cqm.set_objective(objective)

        # Assignment constraints
        for local_i in range(num_stage_intents):
            valid = [x[local_i, j] for j in range(len(agent_names)) if (local_i, j) in x]
            if valid:
                cqm.add_constraint(sum(valid) == 1, label=f'{stage}_assign_{local_i}')

        # Capacity constraints (shared across all waves - will need coordination)
        for j, name in enumerate(agent_names):
            cap = agents[name]['capacity']
            assigned = [x[local_i, j] for local_i in range(num_stage_intents) if (local_i, j) in x]
            if assigned:
                # Use a fraction of capacity per wave (simplified)
                wave_cap = max(1, cap // len(cfg.PIPELINE_STAGES))
                cqm.add_constraint(sum(assigned) <= wave_cap, label=f'{stage}_cap_{name}')

        print(f"    Variables: {len(x)}, Constraints: {len(cqm.constraints)}, Dep terms: {dep_terms}")
        waves.append((stage, cqm, x, intent_indices))

    total_time = time.time() - start_time
    print(f"\nTotal wave build time: {total_time:.2f}s")

    return waves


def estimate_problem_size(intents, agents, agent_names):
    """Estimate the size of the CQM problem without building it.

    Args:
        intents: List of intent dicts
        agents: Dict of agent definitions
        agent_names: List of agent names

    Returns:
        Dict with size estimates
    """
    num_intents = len(intents)
    num_agents = len(agent_names)

    # Estimate valid assignments
    valid_assignments = 0
    for intent in intents:
        valid_for_intent = sum(1 for name in agent_names if can_assign(intent, name, agents))
        valid_assignments += valid_for_intent

    # Estimate dependency terms
    dep_edges = sum(len(intent.get('depends', [])) for intent in intents)
    # Each edge creates up to (num_agents^2) quadratic terms
    avg_valid_agents = valid_assignments / max(num_intents, 1)
    estimated_dep_terms = dep_edges * (avg_valid_agents ** 2)

    return {
        'num_intents': num_intents,
        'num_agents': num_agents,
        'valid_assignments': valid_assignments,
        'total_possible': num_intents * num_agents,
        'filter_rate': 1 - (valid_assignments / max(num_intents * num_agents, 1)),
        'dependency_edges': dep_edges,
        'estimated_quadratic_terms': estimated_dep_terms,
        'estimated_constraints': num_intents + num_agents,
    }


if __name__ == '__main__':
    # Test model building
    from css_renderer_intents import generate_intents, build_workflow_chains
    from css_renderer_agents import build_agent_pool

    print("Testing CQM Model Builder")
    print("=" * 50)

    agents, agent_names = build_agent_pool()
    intents = generate_intents()
    workflow_chains = build_workflow_chains(intents)

    # Estimate size
    estimates = estimate_problem_size(intents, agents, agent_names)
    print("\nProblem Size Estimates:")
    for key, value in estimates.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2f}")
        else:
            print(f"  {key}: {value}")

    # Build full CQM (may be large!)
    print("\n" + "=" * 50)
    cqm, x = build_cqm(intents, agents, agent_names)
