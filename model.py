"""CQM construction and cost functions for QAAS."""

import time

from dimod import ConstrainedQuadraticModel, Binary

import config as cfg
from agents import can_assign


def get_cost(intent, agent_name, agents):
    """Compute assignment cost: token cost + overkill penalty + latency."""
    agent = agents[agent_name]
    token_cost = intent['estimated_tokens'] * agent['token_rate']
    quality_surplus = agent['quality'] - intent['min_quality']
    overkill_cost = quality_surplus * token_cost * cfg.OVERKILL_WEIGHT
    latency_cost = agent['latency'] * cfg.LATENCY_WEIGHT
    return token_cost + overkill_cost + latency_cost


def build_cqm(intents, agents, agent_names):
    """Build a Constrained Quadratic Model for the assignment problem.

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
    for i, intent in enumerate(intents):
        for j, name in enumerate(agent_names):
            if can_assign(intent, name, agents):
                x[i, j] = Binary(f'x_{i}_{j}')

    print(f"Valid assignments: {len(x)}")
    print(f"Filtered out: {num_intents * num_agents - len(x)}")

    # Objective: minimize cost + dependency quality penalties
    objective = 0
    for (i, j), var in x.items():
        objective += get_cost(intents[i], agent_names[j], agents) * var

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

    # Hard constraints
    for i in range(num_intents):
        valid = [x[i, j] for j in range(num_agents) if (i, j) in x]
        if valid:
            cqm.add_constraint(sum(valid) == 1, label=f'assign_{i}')

    for j, name in enumerate(agent_names):
        cap = agents[name]['capacity']
        assigned = [x[i, j] for i in range(num_intents) if (i, j) in x]
        if assigned:
            cqm.add_constraint(sum(assigned) <= cap, label=f'cap_{name}')

    build_time = time.time() - start_time
    print(f"Constraints: {len(cqm.constraints)}")
    print(f"Build time: {build_time:.2f}s")

    return cqm, x
