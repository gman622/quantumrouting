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
from css_renderer_intents import PROJECT_DURATION_DAYS


# Scale factor: CP-SAT requires integer coefficients. Multiply dollar costs
# by this factor, round to int, then divide back for reporting.
COST_SCALE = 1_000_000

# Quality is stored as float 0.0–1.0. Scale to integers for CP-SAT.
QUALITY_SCALE = 100


def _build_model_types(agents, agent_names):
    """Collapse identical agents into model types."""
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
    """Solve the 10K assignment problem using OR-Tools CP-SAT."""
    num_intents = len(intents)
    model_types, _ = _build_model_types(agents, agent_names)
    num_types = len(model_types)

    print(f"Building CP-SAT model: {num_intents} tasks x {num_types} model types")
    build_start = time.time()

    model = cp_model.CpModel()

    # --- Decision variables: x[i, t] = 1 iff intent i assigned to model type t ---
    x = {}
    valid_types_for_intent = defaultdict(list)
    for i, intent in enumerate(intents):
        for t, mt in enumerate(model_types):
            if _can_assign_type(intent, mt):
                x[i, t] = model.new_bool_var(f'x_{i}_{t}')
                valid_types_for_intent[i].append(t)

    print(f"  Boolean variables: {len(x):,}")

    # --- Constraints ---
    for i in range(num_intents):
        if valid_types_for_intent[i]:
            model.add_exactly_one(x[i, t] for t in valid_types_for_intent[i])
    for t, mt in enumerate(model_types):
        model.add(sum(x[i, t] for i in range(num_intents) if (i, t) in x) <= mt['total_capacity'])

    # --- Objective Function ---
    objective_terms = []

    # 1. Base assignment cost
    for (i, t), var in x.items():
        cost = _get_cost_for_type(intents[i], model_types[t])
        objective_terms.append(int(cost * COST_SCALE) * var)

    # 2. Deadline penalty
    for i, intent in enumerate(intents):
        if intent.get('deadline', -1) >= 0:
            urgency = (PROJECT_DURATION_DAYS - intent['deadline']) / PROJECT_DURATION_DAYS
            deadline_penalty = int(urgency * cfg.DEADLINE_WEIGHT * COST_SCALE)
            if deadline_penalty > 0:
                for t in valid_types_for_intent[i]:
                    objective_terms.append(deadline_penalty * x[i, t])

    # 3. Dependency quality penalty
    dep_penalty_scaled = int(cfg.DEP_PENALTY * COST_SCALE)
    for i, intent in enumerate(intents):
        for dep_idx in intent.get('depends', []):
            if not valid_types_for_intent[i] or not valid_types_for_intent[dep_idx]:
                continue
            
            q_i = sum(int(model_types[t]['quality'] * QUALITY_SCALE) * x[i, t] for t in valid_types_for_intent[i])
            q_dep = sum(int(model_types[t]['quality'] * QUALITY_SCALE) * x[dep_idx, t] for t in valid_types_for_intent[dep_idx])
            
            deficit = model.new_int_var(0, QUALITY_SCALE, f'def_{i}_{dep_idx}')
            model.add(deficit >= q_dep - q_i)
            objective_terms.append(dep_penalty_scaled * deficit)

    # 4. Context affinity bonus
    affinity_bonus_scaled = int(cfg.CONTEXT_BONUS * COST_SCALE)
    for i, intent in enumerate(intents):
        for dep_idx in intent.get('depends', []):
            for t in valid_types_for_intent[i]:
                if t in valid_types_for_intent[dep_idx]:
                    # Create an intermediate boolean var for the product x[i,t] * x[dep_idx,t]
                    affinity_var = model.new_bool_var(f'aff_{i}_{dep_idx}_{t}')
                    model.add_bool_and([x[i, t], x[dep_idx, t]]).only_enforce_if(affinity_var)
                    model.add_implication(affinity_var.not_(), x[i, t].not_()).only_enforce_if(affinity_var.not_())
                    model.add_implication(affinity_var.not_(), x[dep_idx, t].not_()).only_enforce_if(affinity_var.not_())
                    objective_terms.append(-affinity_bonus_scaled * affinity_var)

    model.minimize(sum(objective_terms))
    build_time = time.time() - build_start
    print(f"  Model build time: {build_time:.1f}s")

    # --- Solve ---
    print(f"\nSolving with CP-SAT (time limit: {time_limit}s)...")
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.log_search_progress = True
    solver.parameters.num_workers = 0

    solve_start = time.time()
    status = solver.solve(model)
    solve_time = time.time() - solve_start

    print(f"\nSolver status: {solver.status_name(status)} in {solve_time:.1f}s")

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        # ... (rest of the function is for extracting results and remains the same)
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
    """Map model-type assignments to individual agent instances."""
    instance_load = defaultdict(int)
    next_instance = defaultdict(int)
    assignments = {}

    for i, t in sorted(type_assignments.items()):
        mt = model_types[t]
        instances = mt['instances']
        num_instances = len(instances)
        per_instance_cap = mt['capacity']

        assigned = False
        for _ in range(num_instances):
            idx = next_instance[t] % num_instances
            instance_name = instances[idx]
            next_instance[t] += 1

            if instance_load[instance_name] < per_instance_cap:
                assignments[i] = instance_name
                instance_load[instance_name] += 1
                assigned = True
                break
        
        if not assigned:
            assignments[i] = instances[0]
            instance_load[instances[0]] += 1

    return assignments


def greedy_solve(intents, agents):
    """Greedy baseline: cheapest valid agent, first come first served."""
    names = list(agents.keys())
    result = {}
    load = {a: 0 for a in agents}
    cost = 0

    for idx, intent in enumerate(intents):
        best = None
        best_cost = float('inf')

        for name in names:
            a = agents[name]
            if not can_assign(intent, name, agents):
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
    cost
