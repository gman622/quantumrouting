"""Agent pool definition and capability filtering for 10K CSS Renderer."""

from . import css_renderer_config as cfg

# Cloud model definitions - 240 agents total
CLOUD_MODELS = [
    {
        'name': 'claude',
        'quality': 0.95,
        'capabilities': {'trivial', 'simple', 'moderate', 'complex', 'very-complex', 'epic', 'long-context'},
    },
    {
        'name': 'gpt5.2',
        'quality': 0.92,
        'capabilities': {'trivial', 'simple', 'moderate', 'complex', 'very-complex', 'long-context'},
    },
    {
        'name': 'gemini',
        'quality': 0.88,
        'capabilities': {'trivial', 'simple', 'moderate', 'complex', 'long-context'},
    },
    {
        'name': 'kimi2.5',
        'quality': 0.85,
        'capabilities': {'trivial', 'simple', 'moderate', 'complex', 'long-context'},
    },
]

# Local model definitions - 60 agents total
LOCAL_MODELS = [
    {'name': 'llama3.2-1b',    'token_rate': 0, 'quality': 0.40, 'capabilities': {'trivial', 'simple'}, 'capacity': 10, 'latency': 0.5},
    {'name': 'llama3.2-3b',    'token_rate': 0, 'quality': 0.55, 'capabilities': {'trivial', 'simple', 'moderate'}, 'capacity': 8, 'latency': 0.8},
    {'name': 'llama3.1-8b',    'token_rate': 0, 'quality': 0.65, 'capabilities': {'trivial', 'simple', 'moderate'}, 'capacity': 6, 'latency': 1.2},
    {'name': 'codellama-7b',   'token_rate': 0, 'quality': 0.70, 'capabilities': {'trivial', 'simple', 'moderate'}, 'capacity': 6, 'latency': 1.0},
    {'name': 'mistral-7b',     'token_rate': 0, 'quality': 0.60, 'capabilities': {'trivial', 'simple', 'moderate'}, 'capacity': 6, 'latency': 1.0},
    {'name': 'qwen2-7b',       'token_rate': 0, 'quality': 0.65, 'capabilities': {'trivial', 'simple', 'moderate'}, 'capacity': 6, 'latency': 1.1},
]

# Cloud agent configuration - 60 sessions per model = 240 agents
CLOUD_SESSIONS = 60
CLOUD_CAPACITY = 50  # Higher capacity per session for 10K scale
CLOUD_LATENCY = 2.0

# Number of local agents per model type
LOCAL_COUNT = 10  # 10 instances of each local model = 60 agents


def build_agent_pool():
    """Build the full 300-agent pool from cloud and local model definitions.

    Returns:
        (agents, agent_names): agents is a dict keyed by agent name,
            agent_names is a list of all agent names.
    """
    agents = {}

    # Build cloud agents: 4 models × 60 sessions = 240 agents
    for model in CLOUD_MODELS:
        for i in range(CLOUD_SESSIONS):
            agents[f"{model['name']}-{i}"] = {
                'token_rate': cfg.TOKEN_RATES.get(model['name'], 0.0),
                'quality': model['quality'],
                'capabilities': model['capabilities'],
                'is_local': False,
                'capacity': CLOUD_CAPACITY,
                'latency': CLOUD_LATENCY,
                'model_type': model['name'],
            }

    # Build local agents: 6 models × 10 instances = 60 agents
    for model in LOCAL_MODELS:
        for i in range(LOCAL_COUNT):
            agents[f"{model['name']}-{i}"] = {
                'token_rate': model['token_rate'],
                'quality': model['quality'],
                'capabilities': model['capabilities'],
                'is_local': True,
                'capacity': model['capacity'],
                'latency': model['latency'],
                'model_type': model['name'],
            }

    agent_names = list(agents.keys())
    return agents, agent_names


def can_assign(intent, agent_name, agents):
    """Check if an agent can handle a task at acceptable quality.

    Args:
        intent: Dict with 'complexity' and 'min_quality' keys
        agent_name: Name of the agent to check
        agents: Dict of all agent definitions

    Returns:
        bool: True if agent can handle the task
    """
    agent = agents[agent_name]
    if intent['complexity'] not in agent['capabilities']:
        return False
    if agent['quality'] < intent['min_quality']:
        return False
    return True


def get_agent_stats(agents):
    """Get statistics about the agent pool.

    Args:
        agents: Dict of agent definitions

    Returns:
        Dict with pool statistics
    """
    cloud_agents = [a for a in agents.values() if not a['is_local']]
    local_agents = [a for a in agents.values() if a['is_local']]

    cloud_capacity = sum(a['capacity'] for a in cloud_agents)
    local_capacity = sum(a['capacity'] for a in local_agents)

    return {
        'total_agents': len(agents),
        'cloud_agents': len(cloud_agents),
        'local_agents': len(local_agents),
        'cloud_capacity': cloud_capacity,
        'local_capacity': local_capacity,
        'total_capacity': cloud_capacity + local_capacity,
    }


if __name__ == '__main__':
    # Test the agent pool
    agents, agent_names = build_agent_pool()
    stats = get_agent_stats(agents)

    print("CSS Renderer Agent Pool (10K Scale)")
    print("=" * 50)
    print(f"Total agents: {stats['total_agents']}")
    print(f"  Cloud: {stats['cloud_agents']} agents, capacity {stats['cloud_capacity']}")
    print(f"  Local: {stats['local_agents']} agents, capacity {stats['local_capacity']}")
    print(f"Total capacity: {stats['total_capacity']}")
    print()

    # Show cloud model breakdown
    print("Cloud Models:")
    for model in CLOUD_MODELS:
        count = sum(1 for a in agents.values() if a.get('model_type') == model['name'])
        total_cap = sum(a['capacity'] for a in agents.values() if a.get('model_type') == model['name'])
        print(f"  {model['name']}: {count} agents, {total_cap} capacity, "
              f"${model['token_rate']*1_000_000:.0f}/M tokens, quality {model['quality']}")

    print()
    print("Local Models:")
    for model in LOCAL_MODELS:
        count = sum(1 for a in agents.values() if a.get('model_type') == model['name'])
        total_cap = sum(a['capacity'] for a in agents.values() if a.get('model_type') == model['name'])
        print(f"  {model['name']}: {count} agents, {total_cap} capacity, "
              f"free, quality {model['quality']}")
