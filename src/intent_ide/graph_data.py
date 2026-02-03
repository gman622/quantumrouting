"""Graph aggregation and JSON generation for Intent IDE canvas.

Generates node/edge JSON at four zoom levels:
  0: 5 nodes (one per pipeline stage)
  1: ~30 nodes (stage x complexity tier)
  2: ~250 nodes (workflow chains, ~50 chains x 5 steps)
  3: ~1000 nodes (all chains + unclustered intents, capped for React Flow)
"""

from collections import defaultdict

from quantum_routing import css_renderer_config as cfg


# Fixed X positions per stage (left-to-right pipeline flow)
STAGE_X = {stage: i * 280 + 100 for i, stage in enumerate(cfg.PIPELINE_STAGES)}

# Color palette per stage
STAGE_COLORS = {
    'parsing': '#6366f1',
    'style_computation': '#8b5cf6',
    'layout': '#ec4899',
    'painting': '#f59e0b',
    'compositing': '#10b981',
}


def _status(intent_idx, assignments, intents, agents):
    """Determine node status: satisfied / overkill / violated."""
    if intent_idx not in assignments:
        return 'violated'
    agent_name = assignments[intent_idx]
    agent = agents[agent_name]
    intent = intents[intent_idx]
    if agent['quality'] < intent['min_quality']:
        return 'violated'
    surplus = agent['quality'] - intent['min_quality']
    if surplus > 0.20 and agent['token_rate'] > 0.00001:
        return 'overkill'
    return 'satisfied'


def _agg_status(statuses):
    """Pick dominant status for an aggregate node."""
    if 'violated' in statuses:
        return 'violated'
    if 'overkill' in statuses:
        return 'overkill'
    return 'satisfied'


def _status_counts(statuses):
    counts = {'satisfied': 0, 'overkill': 0, 'violated': 0}
    for s in statuses:
        counts[s] += 1
    return counts


# ── Zoom 0: pipeline stages ────────────────────────────────────────────

def zoom0(intents, agents, assignments, workflow_chains):
    """5 nodes (one per stage), edges = cross-stage dependency counts."""
    stage_indices = defaultdict(list)
    for i, intent in enumerate(intents):
        stage_indices[intent['stage']].append(i)

    nodes = []
    for stage in cfg.PIPELINE_STAGES:
        indices = stage_indices[stage]
        statuses = [_status(i, assignments, intents, agents) for i in indices]
        counts = _status_counts(statuses)
        cost = sum(
            intents[i]['estimated_tokens'] * agents[assignments[i]]['token_rate']
            for i in indices if i in assignments
        )
        nodes.append({
            'id': f'stage-{stage}',
            'type': 'stageNode',
            'position': {'x': STAGE_X[stage], 'y': 250},
            'data': {
                'label': stage.replace('_', ' ').title(),
                'stage': stage,
                'taskCount': len(indices),
                'status': _agg_status(statuses),
                'counts': counts,
                'cost': round(cost, 2),
                'color': STAGE_COLORS[stage],
            },
        })

    edges = []
    for i in range(len(cfg.PIPELINE_STAGES) - 1):
        src = cfg.PIPELINE_STAGES[i]
        tgt = cfg.PIPELINE_STAGES[i + 1]
        edges.append({
            'id': f'e-{src}-{tgt}',
            'source': f'stage-{src}',
            'target': f'stage-{tgt}',
            'animated': True,
            'style': {'stroke': STAGE_COLORS[tgt]},
        })

    return {'nodes': nodes, 'edges': edges}


# ── Zoom 1: stage x complexity ──────────────────────────────────────────

def zoom1(intents, agents, assignments, workflow_chains):
    """~30 nodes: one per (stage, complexity) combination."""
    buckets = defaultdict(list)
    for i, intent in enumerate(intents):
        buckets[(intent['stage'], intent['complexity'])].append(i)

    complexity_order = ['trivial', 'simple', 'moderate', 'complex', 'very-complex', 'epic']
    complexity_y = {c: idx * 100 + 50 for idx, c in enumerate(complexity_order)}

    nodes = []
    for (stage, complexity), indices in sorted(buckets.items()):
        statuses = [_status(i, assignments, intents, agents) for i in indices]
        counts = _status_counts(statuses)
        cost = sum(
            intents[i]['estimated_tokens'] * agents[assignments[i]]['token_rate']
            for i in indices if i in assignments
        )
        nid = f'sc-{stage}-{complexity}'
        nodes.append({
            'id': nid,
            'type': 'clusterNode',
            'position': {'x': STAGE_X[stage], 'y': complexity_y.get(complexity, 300)},
            'data': {
                'label': f'{stage.replace("_", " ").title()}\n{complexity}',
                'stage': stage,
                'complexity': complexity,
                'taskCount': len(indices),
                'status': _agg_status(statuses),
                'counts': counts,
                'cost': round(cost, 2),
                'color': STAGE_COLORS[stage],
            },
        })

    # Edges: within-stage (complexity tiers top-to-bottom)
    edges = []
    for stage in cfg.PIPELINE_STAGES:
        tiers = [c for c in complexity_order if (stage, c) in buckets]
        for k in range(len(tiers) - 1):
            src = f'sc-{stage}-{tiers[k]}'
            tgt = f'sc-{stage}-{tiers[k + 1]}'
            edges.append({
                'id': f'e-{src}-{tgt}',
                'source': src,
                'target': tgt,
                'style': {'stroke': STAGE_COLORS[stage], 'opacity': 0.4},
            })

    # Cross-stage edges (stage-level)
    for i in range(len(cfg.PIPELINE_STAGES) - 1):
        src_stage = cfg.PIPELINE_STAGES[i]
        tgt_stage = cfg.PIPELINE_STAGES[i + 1]
        # Connect the moderate tier of adjacent stages
        src = f'sc-{src_stage}-moderate'
        tgt = f'sc-{tgt_stage}-moderate'
        if src in [n['id'] for n in nodes] and tgt in [n['id'] for n in nodes]:
            edges.append({
                'id': f'e-cross-{src_stage}-{tgt_stage}',
                'source': src,
                'target': tgt,
                'animated': True,
                'style': {'stroke': STAGE_COLORS[tgt_stage], 'opacity': 0.6},
            })

    return {'nodes': nodes, 'edges': edges}


# ── Zoom 2: workflow chains ──────────────────────────────────────────────

def zoom2(intents, agents, assignments, workflow_chains):
    """~250 nodes: sample workflow chains (~50 chains x ~5 steps each)."""
    max_chains = 50
    chains_to_show = workflow_chains[:max_chains]

    nodes = []
    edges = []
    node_ids = set()

    for chain_idx, (chain_type, steps) in enumerate(chains_to_show):
        y_base = chain_idx * 80 + 50
        for step_idx, intent_idx in enumerate(steps):
            intent = intents[intent_idx]
            nid = f'i-{intent_idx}'
            if nid in node_ids:
                continue
            node_ids.add(nid)

            status = _status(intent_idx, assignments, intents, agents)
            agent_name = assignments.get(intent_idx, 'unassigned')
            cost = 0
            if intent_idx in assignments:
                cost = intent['estimated_tokens'] * agents[agent_name]['token_rate']

            nodes.append({
                'id': nid,
                'type': 'intentNode',
                'position': {
                    'x': STAGE_X.get(intent['stage'], 100) + step_idx * 50,
                    'y': y_base,
                },
                'data': {
                    'label': intent['id'][:30],
                    'intentIdx': intent_idx,
                    'stage': intent['stage'],
                    'complexity': intent['complexity'],
                    'status': status,
                    'agent': agent_name,
                    'cost': round(cost, 4),
                    'color': STAGE_COLORS.get(intent['stage'], '#888'),
                },
            })

        # Chain edges
        for k in range(1, len(steps)):
            src_id = f'i-{steps[k - 1]}'
            tgt_id = f'i-{steps[k]}'
            if src_id in node_ids and tgt_id in node_ids:
                edges.append({
                    'id': f'e-chain-{chain_idx}-{k}',
                    'source': src_id,
                    'target': tgt_id,
                    'style': {'stroke': STAGE_COLORS.get(intents[steps[k]]['stage'], '#888')},
                })

    return {'nodes': nodes, 'edges': edges}


# ── Zoom 3: all chains + clusters ───────────────────────────────────────

def zoom3(intents, agents, assignments, workflow_chains):
    """~1000 nodes: all workflow chains plus sampled unclustered intents."""
    nodes = []
    edges = []
    node_ids = set()

    # All workflow chains
    for chain_idx, (chain_type, steps) in enumerate(workflow_chains):
        y_base = chain_idx * 40 + 50
        for step_idx, intent_idx in enumerate(steps):
            intent = intents[intent_idx]
            nid = f'i-{intent_idx}'
            if nid in node_ids:
                continue
            node_ids.add(nid)

            status = _status(intent_idx, assignments, intents, agents)
            agent_name = assignments.get(intent_idx, 'unassigned')
            cost = 0
            if intent_idx in assignments:
                cost = intent['estimated_tokens'] * agents[agent_name]['token_rate']

            nodes.append({
                'id': nid,
                'type': 'intentNode',
                'position': {
                    'x': STAGE_X.get(intent['stage'], 100) + step_idx * 40,
                    'y': y_base,
                },
                'data': {
                    'label': intent['id'][:25],
                    'intentIdx': intent_idx,
                    'stage': intent['stage'],
                    'complexity': intent['complexity'],
                    'status': status,
                    'agent': agent_name,
                    'cost': round(cost, 4),
                    'color': STAGE_COLORS.get(intent['stage'], '#888'),
                },
            })

        for k in range(1, len(steps)):
            src_id = f'i-{steps[k - 1]}'
            tgt_id = f'i-{steps[k]}'
            if src_id in node_ids and tgt_id in node_ids:
                edges.append({
                    'id': f'e-chain-{chain_idx}-{k}',
                    'source': src_id,
                    'target': tgt_id,
                    'style': {'stroke': STAGE_COLORS.get(intents[steps[k]]['stage'], '#888')},
                })

    # Cap at ~1000 nodes: add unclustered intents if under limit
    max_nodes = 1000
    if len(nodes) < max_nodes:
        remaining = max_nodes - len(nodes)
        step = max(1, len(intents) // remaining)
        for i in range(0, len(intents), step):
            if len(nodes) >= max_nodes:
                break
            nid = f'i-{i}'
            if nid in node_ids:
                continue
            node_ids.add(nid)

            intent = intents[i]
            status = _status(i, assignments, intents, agents)
            agent_name = assignments.get(i, 'unassigned')
            cost = 0
            if i in assignments:
                cost = intent['estimated_tokens'] * agents[agent_name]['token_rate']

            stage_idx = cfg.PIPELINE_STAGES.index(intent['stage']) if intent['stage'] in cfg.PIPELINE_STAGES else 0
            nodes.append({
                'id': nid,
                'type': 'intentNode',
                'position': {
                    'x': STAGE_X.get(intent['stage'], 100) + (i % 10) * 30,
                    'y': len(nodes) * 3 + 50,
                },
                'data': {
                    'label': intent['id'][:25],
                    'intentIdx': i,
                    'stage': intent['stage'],
                    'complexity': intent['complexity'],
                    'status': status,
                    'agent': agent_name,
                    'cost': round(cost, 4),
                    'color': STAGE_COLORS.get(intent['stage'], '#888'),
                },
            })

    return {'nodes': nodes, 'edges': edges}


# ── Public API ────────────────────────────────────────────────────────────

ZOOM_FUNCTIONS = [zoom0, zoom1, zoom2, zoom3]


def get_graph(zoom_level, intents, agents, assignments, workflow_chains):
    """Return graph JSON for the given zoom level (0-3)."""
    zoom_level = max(0, min(3, zoom_level))
    return ZOOM_FUNCTIONS[zoom_level](intents, agents, assignments, workflow_chains)


def get_assignments_metadata(assignments, intents, agents):
    """Return assignment metadata: cost, violations, status counts."""
    total_cost = 0
    status_counts = {'satisfied': 0, 'overkill': 0, 'violated': 0}
    dep_violations = 0

    for i, intent in enumerate(intents):
        status = _status(i, assignments, intents, agents)
        status_counts[status] += 1
        if i in assignments:
            total_cost += intent['estimated_tokens'] * agents[assignments[i]]['token_rate']

        for dep_idx in intent.get('depends', []):
            if i in assignments and dep_idx in assignments:
                if agents[assignments[i]]['quality'] < agents[assignments[dep_idx]]['quality']:
                    dep_violations += 1

    unassigned = sum(1 for i in range(len(intents)) if i not in assignments)

    return {
        'totalCost': round(total_cost, 2),
        'totalTasks': len(intents),
        'assignedTasks': len(assignments),
        'unassignedTasks': unassigned,
        'depViolations': dep_violations,
        'statusCounts': status_counts,
    }


def get_agent_summary(assignments, intents, agents):
    """Return per-model-type dispatch summary."""
    from collections import defaultdict
    type_stats = defaultdict(lambda: {'tasks': 0, 'cost': 0.0, 'capacity': 0})

    # Tally capacity per model type
    for name, agent in agents.items():
        mt = agent['model_type']
        type_stats[mt]['capacity'] += agent['capacity']
        type_stats[mt]['quality'] = agent['quality']
        type_stats[mt]['tokenRate'] = agent['token_rate']
        type_stats[mt]['isLocal'] = agent['is_local']

    # Tally tasks/cost per model type
    for i, agent_name in assignments.items():
        mt = agents[agent_name]['model_type']
        type_stats[mt]['tasks'] += 1
        type_stats[mt]['cost'] += intents[i]['estimated_tokens'] * agents[agent_name]['token_rate']

    result = []
    for mt, stats in sorted(type_stats.items()):
        result.append({
            'modelType': mt,
            'tasks': stats['tasks'],
            'capacity': stats['capacity'],
            'cost': round(stats['cost'], 2),
            'quality': stats.get('quality', 0),
            'tokenRate': stats.get('tokenRate', 0),
            'isLocal': stats.get('isLocal', False),
        })

    return result
