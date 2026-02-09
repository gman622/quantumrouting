"""100K scale configuration for Intent IDE.

This module provides agent pool and intent generation for 100K intents × 250 agents,
matching the upper bound of D-Wave Leap's CQM hybrid solver (~5M variables).
"""

from . import css_renderer_config as cfg

# ══════════════════════════════════════════════════════════════════════════════
# SCALE PARAMETERS
# ══════════════════════════════════════════════════════════════════════════════

TOTAL_INTENTS = 100_000
TOTAL_AGENTS = 250

# ══════════════════════════════════════════════════════════════════════════════
# AGENT POOL (250 agents)
# ══════════════════════════════════════════════════════════════════════════════

# Cloud: 5 models × 40 sessions = 200 agents
CLOUD_MODELS_100K = [
    {'name': 'claude',   'quality': 0.95, 'token_rate': 0.000020},  # $20/Mtok
    {'name': 'gpt5.2',   'quality': 0.92, 'token_rate': 0.000030},  # $30/Mtok
    {'name': 'gemini',   'quality': 0.88, 'token_rate': 0.000005},  # $5/Mtok
    {'name': 'kimi2.5',  'quality': 0.85, 'token_rate': 0.000002},  # $2/Mtok
    {'name': 'deepseek', 'quality': 0.82, 'token_rate': 0.000001},  # $1/Mtok (new)
]
CLOUD_SESSIONS = 40
CLOUD_CAPACITY = 450  # Higher capacity for 100K scale
CLOUD_LATENCY = 2.0

# Local: 5 models × 10 instances = 50 agents
LOCAL_MODELS_100K = [
    {'name': 'llama3.3-70b',  'quality': 0.75, 'capacity': 200, 'latency': 1.5},
    {'name': 'llama3.2-8b',   'quality': 0.60, 'capacity': 300, 'latency': 0.8},
    {'name': 'qwen2.5-72b',   'quality': 0.72, 'capacity': 200, 'latency': 1.8},
    {'name': 'mistral-large', 'quality': 0.70, 'capacity': 250, 'latency': 1.2},
    {'name': 'codellama-70b', 'quality': 0.68, 'capacity': 250, 'latency': 1.4},
]
LOCAL_INSTANCES = 10

# Capabilities by quality tier
CAPABILITIES_BY_QUALITY = {
    0.95: {'trivial', 'simple', 'moderate', 'complex', 'very-complex', 'epic'},
    0.92: {'trivial', 'simple', 'moderate', 'complex', 'very-complex'},
    0.88: {'trivial', 'simple', 'moderate', 'complex'},
    0.85: {'trivial', 'simple', 'moderate', 'complex'},
    0.82: {'trivial', 'simple', 'moderate'},
    0.75: {'trivial', 'simple', 'moderate'},
    0.72: {'trivial', 'simple', 'moderate'},
    0.70: {'trivial', 'simple', 'moderate'},
    0.68: {'trivial', 'simple', 'moderate'},
    0.60: {'trivial', 'simple'},
}


def build_agent_pool_100k():
    """Build a 250-agent pool for 100K scale.

    Returns:
        (agents, agent_names): agents dict keyed by name, list of names
    """
    agents = {}

    # Cloud agents: 5 models × 40 sessions = 200 agents
    for model in CLOUD_MODELS_100K:
        quality = model['quality']
        caps = CAPABILITIES_BY_QUALITY.get(quality, {'trivial', 'simple'})
        for i in range(CLOUD_SESSIONS):
            agents[f"{model['name']}-{i}"] = {
                'token_rate': model['token_rate'],
                'quality': quality,
                'capabilities': caps,
                'is_local': False,
                'capacity': CLOUD_CAPACITY,
                'latency': CLOUD_LATENCY,
                'model_type': model['name'],
            }

    # Local agents: 5 models × 10 instances = 50 agents
    for model in LOCAL_MODELS_100K:
        quality = model['quality']
        caps = CAPABILITIES_BY_QUALITY.get(quality, {'trivial', 'simple'})
        for i in range(LOCAL_INSTANCES):
            agents[f"{model['name']}-{i}"] = {
                'token_rate': 0,  # Local = free
                'quality': quality,
                'capabilities': caps,
                'is_local': True,
                'capacity': model['capacity'],
                'latency': model['latency'],
                'model_type': model['name'],
            }

    agent_names = list(agents.keys())
    return agents, agent_names


# ══════════════════════════════════════════════════════════════════════════════
# INTENT DISTRIBUTION (100K intents)
# ══════════════════════════════════════════════════════════════════════════════

# 10× the original distribution
STAGE_DISTRIBUTION_100K = {
    'parsing': 25_000,
    'style_computation': 25_000,
    'layout': 25_000,
    'painting': 15_000,
    'compositing': 10_000,
}

# Workflow chains scaled 10×
WORKFLOW_CHAINS_100K = {
    'parsing': 1500,
    'style_computation': 1500,
    'layout': 1500,
    'painting': 1000,
    'compositing': 800,
}

CROSS_STAGE_EDGES_100K = 5000


def generate_intents_100k():
    """Generate 100K CSS renderer intents.

    Returns:
        list of intent dicts
    """
    from .css_renderer_intents import CSS_TASK_TEMPLATES

    intents = []
    intent_id = 0

    for stage in cfg.PIPELINE_STAGES:
        stage_count = STAGE_DISTRIBUTION_100K[stage]
        complexity_dist = cfg.STAGE_COMPLEXITY[stage]
        templates = CSS_TASK_TEMPLATES[stage]

        # Calculate counts per complexity
        complexity_counts = {}
        remaining = stage_count
        for complexity, fraction, min_quality in complexity_dist[:-1]:
            count = int(stage_count * fraction)
            complexity_counts[complexity] = {'count': count, 'min_quality': min_quality}
            remaining -= count

        last_complexity, _, last_quality = complexity_dist[-1]
        complexity_counts[last_complexity] = {'count': remaining, 'min_quality': last_quality}

        # Generate intents
        for complexity, data in complexity_counts.items():
            count = data['count']
            min_quality = data['min_quality']
            task_list = templates.get(complexity, ['generic-task'])

            for i in range(count):
                template = task_list[i % len(task_list)]
                intents.append({
                    'id': f'{stage}-{template}-{intent_id}',
                    'stage': stage,
                    'complexity': complexity,
                    'min_quality': min_quality,
                    'depends': [],
                    'deadline': -1,
                    'estimated_tokens': cfg.TOKEN_ESTIMATES[complexity],
                    'story_points': cfg.STORY_POINTS[complexity],
                })
                intent_id += 1

    return intents


def get_scale_stats():
    """Get statistics for the 100K scale configuration."""
    agents, _ = build_agent_pool_100k()

    cloud = [a for a in agents.values() if not a['is_local']]
    local = [a for a in agents.values() if a['is_local']]

    cloud_capacity = sum(a['capacity'] for a in cloud)
    local_capacity = sum(a['capacity'] for a in local)

    total_intents = sum(STAGE_DISTRIBUTION_100K.values())

    # Estimate variable count (N × M with quality filtering)
    # Rough estimate: ~30% of pairs valid due to quality floors
    estimated_vars = int(total_intents * len(agents) * 0.30)

    return {
        'intents': total_intents,
        'agents': len(agents),
        'cloud_agents': len(cloud),
        'local_agents': len(local),
        'cloud_capacity': cloud_capacity,
        'local_capacity': local_capacity,
        'total_capacity': cloud_capacity + local_capacity,
        'estimated_variables': estimated_vars,
        'dwave_variable_limit': 5_000_000,
        'fits_dwave': estimated_vars <= 5_000_000,
    }


if __name__ == '__main__':
    stats = get_scale_stats()

    print("100K Scale Configuration")
    print("=" * 60)
    print(f"Intents:           {stats['intents']:,}")
    print(f"Agents:            {stats['agents']}")
    print(f"  Cloud:           {stats['cloud_agents']} (capacity {stats['cloud_capacity']:,})")
    print(f"  Local:           {stats['local_agents']} (capacity {stats['local_capacity']:,})")
    print(f"Total capacity:    {stats['total_capacity']:,}")
    print()
    print(f"Estimated CQM variables: {stats['estimated_variables']:,}")
    print(f"D-Wave limit:            {stats['dwave_variable_limit']:,}")
    print(f"Fits D-Wave Leap:        {'✓' if stats['fits_dwave'] else '✗'}")
    print()

    # Test generation
    print("Testing intent generation...")
    intents = generate_intents_100k()
    print(f"Generated {len(intents):,} intents")

    print("\nBy stage:")
    from collections import Counter
    stages = Counter(i['stage'] for i in intents)
    for stage, count in stages.items():
        print(f"  {stage}: {count:,}")

    print("\nBy complexity:")
    complexity = Counter(i['complexity'] for i in intents)
    for c in ['trivial', 'simple', 'moderate', 'complex', 'very-complex', 'epic']:
        print(f"  {c}: {complexity.get(c, 0):,}")
