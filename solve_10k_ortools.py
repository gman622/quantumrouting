"""CP-SAT solver for the 10K CSS Renderer routing problem.

Replaces D-Wave SA with OR-Tools CP-SAT to avoid the O(dep_edges * agents^2)
quadratic term explosion. Dependencies are modeled as O(dep_edges) linear
constraints using auxiliary integer variables for assigned quality.

Key optimization: 300 agents collapse to 10 model types (all instances of the
same model are interchangeable). This reduces boolean variables from ~2.6M to
~87K — a 30x reduction that fits comfortably in memory.
"""

import time
from collections import defaultdict

from ortools.sat.python import cp_model

import css_renderer_config as cfg
from css_renderer_agents import can_assign
from css_renderer_model import get_cost


# Scale factor: CP-SAT requires integer coefficients. Multiply dollar costs
# by this factor, round to int, then divide back for reporting.
COST_SCALE = 1_000_000

# Quality is stored as float 0.0–1.0. Scale to integers for CP-SAT.
QUALITY_SCALE = 100


def _build_model_types(agents, agent_names):
    """Collapse identical agents into model types.

    Returns:
        model_types: list of dicts with keys: name, token_rate, quality,
            capabilities, is_local, capacity (total), latency, instances (list of agent names)
        type_index: dict mapping agent_name -> model type index
    """
    type_map = {}  # model_type_name -> index in model_types
    model_types = []

    for name in agent_names:
        a = agents[name]
        mt = a['model_type']
        if mt not in type_map:
            type_map[mt] = len(model_types)
            model_types.append({
                'name': mt,
                'token_rate': a['token_rate'],
                'quality': a['quality'],
                'capabilities': a['capabilities'],
                'is_local': a['is_local'],
                'capacity': a['capacity'],  # per-instance; will accumulate
                'latency': a['latency'],
                'instances': [],
                'total_capacity': 0,
            })
        idx = type_map[mt]
        model_types[idx]['instances'].append(name)
        model_types[idx]['total_capacity'] += a['capacity']

    type_index = {}
    for name in agent_names:
        mt = agents[name]['model_type']
        type_index[name] = type_map[mt]

    return model_types, type_index


def _can_assign_type(intent, model_type):
    """Check if a model type can handle an intent."""
    if intent['complexity'] not in model_type['capabilities']:
        return False
    if model_type['quality'] < intent['min_quality']:
        return False
    return True


def _get_cost_for_type(intent, model_type):
    """Compute assignment cost for a model type (same formula as get_cost)."""
    token_cost = intent['estimated_tokens'] * model_type['token_rate']
    quality_surplus = model_type['quality'] - intent['min_quality']
    overkill_cost = quality_surplus * token_cost * cfg.OVERKILL_WEIGHT
    latency_cost = model_type['latency'] * cfg.LATENCY_WEIGHT
    return token_cost + overkill_cost + latency_cost


def solve_cpsat(intents, agents, agent_names, time_limit=cfg.CLASSICAL_TIME_BUDGET):
    """Solve the 10K assignment problem using OR-Tools CP-SAT.

    Uses model-type aggregation: 300 agents -> 10 model types, reducing
    variables from ~2.6M to ~87K.

    Args:
        intents: List of intent dicts
        agents: Dict of agent definitions
        agent_names: List of agent names
        time_limit: Maximum solve time in seconds

    Returns:
        dict mapping intent index to agent name, or empty dict on failure.
    """
    num_intents = len(intents)

    # Collapse agents to model types
    model_types, type_index = _build_model_types(agents, agent_names)
    num_types = len(model_types)

    print(f"Building CP-SAT model: {num_intents} tasks x {num_types} model types "
          f"(collapsed from {len(agent_names)} agents)")
    build_start = time.time()

    model = cp_model.CpModel()

    # --- Decision variables: x[i, t] = 1 iff intent i assigned to model type t ---
    x = {}
    valid_types_for_intent = {}  # intent_idx -> list of type indices

    for i, intent in enumerate(intents):
        valid_types_for_intent[i] = []
        for t, mt in enumerate(model_types):
            if _can_assign_type(intent, mt):
                x[i, t] = model.new_bool_var(f'x_{i}_{t}')
                valid_types_for_intent[i].append(t)

    total_vars = len(x)
    print(f"  Boolean variables: {total_vars:,}")

    # --- Constraints: each intent gets exactly one model type ---
    for i in range(num_intents):
        if valid_types_for_intent[i]:
            model.add_exactly_one(x[i, t] for t in valid_types_for_intent[i])
        else:
            print(f"  WARNING: intent {i} has no valid model types")

    # --- Constraints: model type total capacity ---
    for t, mt in enumerate(model_types):
        total_cap = mt['total_capacity']
        assigned = [x[i, t] for i in range(num_intents) if (i, t) in x]
        if assigned:
            model.add(sum(assigned) <= total_cap)

    # --- Auxiliary variables for dependency handling ---
    assigned_quality = {}
    dep_intents = set()
    for i, intent in enumerate(intents):
        for dep_idx in intent.get('depends', []):
            dep_intents.add(i)
            dep_intents.add(dep_idx)

    for i in dep_intents:
        if not valid_types_for_intent[i]:
            continue
        qualities = [int(model_types[t]['quality'] * QUALITY_SCALE)
                     for t in valid_types_for_intent[i]]
        min_q = min(qualities)
        max_q = max(qualities)
        assigned_quality[i] = model.new_int_var(min_q, max_q, f'q_{i}')

        model.add(
            assigned_quality[i] == sum(
                int(model_types[t]['quality'] * QUALITY_SCALE) * x[i, t]
                for t in valid_types_for_intent[i]
            )
        )

    print(f"  Quality aux vars: {len(assigned_quality)}")

    # --- Objective: minimize total cost + dependency penalty ---
    objective_terms = []

    # Linear cost terms
    for (i, t), var in x.items():
        cost = _get_cost_for_type(intents[i], model_types[t])
        scaled_cost = int(cost * COST_SCALE)
        if scaled_cost > 0:
            objective_terms.append(scaled_cost * var)

    # Dependency penalty
    dep_penalty_scaled = int(cfg.DEP_PENALTY * COST_SCALE)
    num_dep_constraints = 0

    for i, intent in enumerate(intents):
        for dep_idx in intent.get('depends', []):
            if i not in assigned_quality or dep_idx not in assigned_quality:
                continue

            q_i = assigned_quality[i]
            q_dep = assigned_quality[dep_idx]

            max_possible_deficit = QUALITY_SCALE
            deficit = model.new_int_var(0, max_possible_deficit, f'def_{i}_{dep_idx}')
            model.add(deficit >= q_dep - q_i)

            objective_terms.append(dep_penalty_scaled * deficit)
            num_dep_constraints += 1

    model.minimize(sum(objective_terms))

    build_time = time.time() - build_start
    print(f"  Dependency constraints: {num_dep_constraints}")
    print(f"  Model build time: {build_time:.1f}s")

    # --- Solve ---
    print(f"\nSolving with CP-SAT (time limit: {time_limit}s)...")
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.log_search_progress = True
    solver.parameters.num_workers = 0  # auto-detect CPU cores

    solve_start = time.time()
    status = solver.solve(model)
    solve_time = time.time() - solve_start

    status_name = solver.status_name(status)
    print(f"\nSolver status: {status_name}")
    print(f"Solve time: {solve_time:.1f}s")

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f"Objective value: {solver.objective_value / COST_SCALE:.2f}")
        if status == cp_model.OPTIMAL:
            print("Solution is OPTIMAL")
        else:
            gap = solver.best_objective_bound / max(solver.objective_value, 1e-9)
            print(f"Best bound: {solver.best_objective_bound / COST_SCALE:.2f} "
                  f"(gap: {abs(1 - gap):.2%})")

        # Extract type-level assignments, then distribute to individual agents
        type_assignments = {}  # intent_idx -> model_type_index
        for i in range(num_intents):
            for t in valid_types_for_intent[i]:
                if solver.value(x[i, t]):
                    type_assignments[i] = t
                    break

        assignments = _distribute_to_instances(type_assignments, model_types,
                                               intents, agents)

        print(f"Assigned {len(assignments)}/{num_intents} tasks")
        return assignments
    else:
        print("No feasible solution found.")
        return {}


def _distribute_to_instances(type_assignments, model_types, intents, agents):
    """Map model-type assignments to individual agent instances.

    Round-robins across instances within each model type to respect
    per-instance capacity.

    Args:
        type_assignments: dict mapping intent_idx -> model_type_index
        model_types: list of model type dicts
        intents: list of intent dicts
        agents: dict of agent definitions

    Returns:
        dict mapping intent_idx -> agent_name
    """
    # Track load per instance
    instance_load = defaultdict(int)
    # Track next instance index per type (round-robin)
    next_instance = defaultdict(int)

    assignments = {}

    for i, t in sorted(type_assignments.items()):
        mt = model_types[t]
        instances = mt['instances']
        num_instances = len(instances)
        per_instance_cap = mt['capacity']  # per-instance capacity

        # Find an instance with remaining capacity (round-robin)
        assigned = False
        for _ in range(num_instances):
            idx = next_instance[t] % num_instances
            instance_name = instances[idx]
            next_instance[t] = idx + 1

            if instance_load[instance_name] < per_instance_cap:
                assignments[i] = instance_name
                instance_load[instance_name] += 1
                assigned = True
                break

        if not assigned:
            # All instances full — shouldn't happen if capacity constraint holds
            # Fall back to first instance (over-capacity)
            assignments[i] = instances[0]
            instance_load[instances[0]] += 1

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


if __name__ == '__main__':
    from css_renderer_intents import generate_intents, build_workflow_chains
    from css_renderer_agents import build_agent_pool

    print("Testing CP-SAT Solver for 10K CSS Renderer")
    print("=" * 60)

    agents, agent_names = build_agent_pool()
    intents = generate_intents()
    workflow_chains = build_workflow_chains(intents)

    print(f"Generated {len(intents)} intents")
    print(f"Agent pool: {len(agent_names)} agents")

    # Test greedy
    print("\n" + "=" * 60)
    print("Greedy Solver...")
    greedy_assignments, greedy_cost = greedy_solve(intents, agents)
    print(f"Greedy assigned {len(greedy_assignments)}/{len(intents)} tasks")
    print(f"Greedy cost: ${greedy_cost:.2f}")

    # Test CP-SAT
    print("\n" + "=" * 60)
    print("CP-SAT Solver...")
    assignments = solve_cpsat(intents, agents, agent_names)
    print(f"CP-SAT assigned {len(assignments)}/{len(intents)} tasks")
