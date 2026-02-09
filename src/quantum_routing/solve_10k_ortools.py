"""CP-SAT solver for the 10K CSS Renderer routing problem.

Replaces D-Wave SA with OR-Tools CP-SAT to avoid the O(dep_edges * agents^2)
quadratic term explosion. Dependencies are modeled as O(dep_edges) linear
constraints using auxiliary integer variables for assigned quality.

Key optimization: 300 agents collapse to 10 model types (all instances of the
same model are interchangeable). This reduces boolean variables from ~2.6M to
~87K — a 30x reduction that fits comfortably in memory.

Profile filtering (optional): when a staffing plan is provided, each intent is
restricted to model types that match its assigned profile via PROFILE_AGENT_MODELS.
This narrows the search space dramatically (typically 70-90% variable reduction).
"""

import logging
import time
from collections import defaultdict

from ortools.sat.python import cp_model

from . import css_renderer_config as cfg
from .css_renderer_agents import can_assign
from .css_renderer_intents import PROJECT_DURATION_DAYS
from .staffing_engine import assign_profile, PROFILE_AGENT_MODELS

logger = logging.getLogger(__name__)


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


def _build_profile_index(staffing_plan):
    """Build a flat mapping from intent ID to profile name.

    The staffing plan nests intents inside waves.  This flattens it into
    a dict ``{intent_id: profile_name}`` for O(1) lookup during model
    construction.
    """
    index = {}
    for wave in staffing_plan.get("waves", []):
        for intent_entry in wave.get("intents", []):
            index[intent_entry["id"]] = intent_entry["profile"]
    return index


def get_allowed_agents_for_intent(intent_idx, intents, agents, agent_names,
                                  staffing_plan):
    """Return the set of allowed agent indices for an intent.

    When *staffing_plan* is ``None``, every agent that passes the
    capability / quality check (``can_assign``) is allowed.  When a plan
    is provided, agents are further restricted to model types listed in
    ``PROFILE_AGENT_MODELS`` for the intent's assigned profile.

    Args:
        intent_idx: Index into the *intents* list.
        intents: Full list of intent dicts.
        agents: Agent pool dict keyed by agent name.
        agent_names: Ordered list of agent names.
        staffing_plan: Output of ``generate_staffing_plan()`` or ``None``.

    Returns:
        set[int]: Indices into *agent_names* that are allowed.
    """
    intent = intents[intent_idx]
    allowed = set()

    # Determine allowed model type names from the profile (if filtering)
    allowed_model_names = None
    if staffing_plan is not None:
        profile_index = _build_profile_index(staffing_plan)
        intent_id = intent.get("id", "")
        profile = profile_index.get(intent_id)
        if profile is None:
            # Intent not found in plan -- fall back to assign_profile()
            profile = assign_profile(intent)
        allowed_model_names = set(
            PROFILE_AGENT_MODELS.get(profile, [])
        )

    for j, name in enumerate(agent_names):
        if not can_assign(intent, name, agents):
            continue
        if allowed_model_names is not None:
            if agents[name]["model_type"] not in allowed_model_names:
                continue
        allowed.add(j)

    return allowed


def _get_allowed_model_types_for_intent(intent, model_types,
                                        profile_index):
    """Return the set of model-type indices allowed for *intent*.

    Applies both the capability check (``_can_assign_type``) and the
    profile filter.  *profile_index* is a dict ``{intent_id: profile}``
    built by ``_build_profile_index`` or ``None`` when no staffing plan
    is active.

    Returns:
        (allowed_indices, was_filtered):
            allowed_indices -- list of model-type indices
            was_filtered   -- True if the profile filter removed any
                              type that would have been capability-valid
    """
    # First pass: capability-valid types
    capability_valid = []
    for t, mt in enumerate(model_types):
        if _can_assign_type(intent, mt):
            capability_valid.append(t)

    if profile_index is None:
        return capability_valid, False

    # Determine the profile for this intent
    intent_id = intent.get("id", "")
    profile = profile_index.get(intent_id)
    if profile is None:
        profile = assign_profile(intent)

    allowed_model_names = set(PROFILE_AGENT_MODELS.get(profile, []))

    # Second pass: intersect with profile-allowed model types
    profile_valid = [
        t for t in capability_valid
        if model_types[t]["name"] in allowed_model_names
    ]

    was_filtered = len(profile_valid) < len(capability_valid)
    return profile_valid, was_filtered


def solve_cpsat(intents, agents, agent_names, time_limit=cfg.CLASSICAL_TIME_BUDGET,
                staffing_plan=None):
    """Solve the 10K assignment problem using OR-Tools CP-SAT.

    Args:
        intents: List of intent dicts.
        agents: Agent pool dict keyed by agent name.
        agent_names: Ordered list of agent names.
        time_limit: CP-SAT solver time limit in seconds.
        staffing_plan: Optional staffing plan from ``generate_staffing_plan()``.
            When provided, each intent is restricted to model types matching
            its assigned profile via ``PROFILE_AGENT_MODELS``.  When ``None``,
            no profile filtering is applied (original behavior).

    Returns:
        dict mapping intent index to assigned agent name, or empty dict
        if no feasible solution is found.
    """
    num_intents = len(intents)
    model_types, _ = _build_model_types(agents, agent_names)
    num_types = len(model_types)

    # Build profile index for fast lookup (None when no plan provided)
    profile_index = (
        _build_profile_index(staffing_plan) if staffing_plan is not None
        else None
    )

    filtering_label = " (with profile filtering)" if staffing_plan else ""
    print(f"Building CP-SAT model{filtering_label}: "
          f"{num_intents} tasks x {num_types} model types")
    build_start = time.time()

    model = cp_model.CpModel()

    # --- Decision variables: x[i, t] = 1 iff intent i assigned to model type t ---
    x = {}
    valid_types_for_intent = defaultdict(list)
    vars_without_filtering = 0
    vars_eliminated_by_profile = 0

    for i, intent in enumerate(intents):
        allowed, was_filtered = _get_allowed_model_types_for_intent(
            intent, model_types, profile_index
        )

        # Count capability-valid types (what we would have without filtering)
        capability_valid_count = sum(
            1 for t, mt in enumerate(model_types)
            if _can_assign_type(intent, mt)
        )
        vars_without_filtering += capability_valid_count

        for t in allowed:
            x[i, t] = model.new_bool_var(f'x_{i}_{t}')
            valid_types_for_intent[i].append(t)

        # Track how many variables were eliminated by profile filtering
        vars_eliminated_by_profile += capability_valid_count - len(allowed)

    print(f"  Boolean variables: {len(x):,}")

    # Log profile filtering statistics
    if staffing_plan is not None:
        if vars_without_filtering > 0:
            pct = vars_eliminated_by_profile / vars_without_filtering * 100
        else:
            pct = 0.0
        msg = (f"  Profile filtering: {vars_eliminated_by_profile:,} of "
               f"{vars_without_filtering:,} variables eliminated "
               f"({pct:.0f}% reduction)")
        print(msg)
        logger.info(msg)

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
                    # affinity_var == 1 only when both i and dep_idx use type t
                    affinity_var = model.new_bool_var(f'aff_{i}_{dep_idx}_{t}')
                    model.add_implication(affinity_var, x[i, t])
                    model.add_implication(affinity_var, x[dep_idx, t])
                    model.add_bool_or([affinity_var, x[i, t].Not(), x[dep_idx, t].Not()])
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
