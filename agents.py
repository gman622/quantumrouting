"""Agent pool definition and capability filtering for QAAS."""

CLOUD_MODELS = [
    {
        'name': 'claude',
        'token_rate': 0.000020,   # $20/M tokens — enterprise negotiated
        'quality': 0.95,
        'capabilities': {'trivial', 'simple', 'moderate', 'complex', 'very-complex', 'epic', 'long-context'},
    },
    {
        'name': 'gpt5.2',
        'token_rate': 0.000030,   # $30/M tokens
        'quality': 0.92,
        'capabilities': {'trivial', 'simple', 'moderate', 'complex', 'very-complex', 'long-context'},
    },
    {
        'name': 'gemini',
        'token_rate': 0.000005,   # $5/M tokens
        'quality': 0.88,
        'capabilities': {'trivial', 'simple', 'moderate', 'complex', 'long-context'},
    },
    {
        'name': 'kimi2.5',
        'token_rate': 0.000002,   # $2/M tokens
        'quality': 0.85,
        'capabilities': {'trivial', 'simple', 'moderate', 'complex', 'long-context'},
    },
]

LOCAL_MODELS = [
    {'name': 'llama3.2-1b',    'token_rate': 0, 'quality': 0.40, 'capabilities': {'trivial', 'simple'}, 'capacity': 3, 'latency': 0.5},
    {'name': 'llama3.2-3b',    'token_rate': 0, 'quality': 0.55, 'capabilities': {'trivial', 'simple', 'moderate'}, 'capacity': 2, 'latency': 0.8},
    {'name': 'llama3.1-8b',    'token_rate': 0, 'quality': 0.65, 'capabilities': {'trivial', 'simple', 'moderate'}, 'capacity': 2, 'latency': 1.2},
    {'name': 'codellama-7b',   'token_rate': 0, 'quality': 0.70, 'capabilities': {'trivial', 'simple', 'moderate'}, 'capacity': 2, 'latency': 1.0},
    {'name': 'mistral-7b',     'token_rate': 0, 'quality': 0.60, 'capabilities': {'trivial', 'simple', 'moderate'}, 'capacity': 2, 'latency': 1.0},
    {'name': 'phi3-mini',      'token_rate': 0, 'quality': 0.45, 'capabilities': {'trivial', 'simple'}, 'capacity': 4, 'latency': 0.3},
    {'name': 'qwen2-7b',       'token_rate': 0, 'quality': 0.65, 'capabilities': {'trivial', 'simple', 'moderate'}, 'capacity': 2, 'latency': 1.1},
    {'name': 'deepseek-coder', 'token_rate': 0, 'quality': 0.72, 'capabilities': {'trivial', 'simple', 'moderate'}, 'capacity': 2, 'latency': 1.0},
]

CLOUD_SESSIONS = 10
CLOUD_CAPACITY = 25
CLOUD_LATENCY = 2.0


def build_agent_pool():
    """Build the full agent pool from cloud and local model definitions.

    Returns:
        (agents, agent_names): agents is a dict keyed by agent name,
            agent_names is a list of all agent names.
    """
    agents = {}

    for model in CLOUD_MODELS:
        for i in range(CLOUD_SESSIONS):
            agents[f"{model['name']}-{i}"] = {
                'token_rate': model['token_rate'],
                'quality': model['quality'],
                'capabilities': model['capabilities'],
                'is_local': False,
                'capacity': CLOUD_CAPACITY,
                'latency': CLOUD_LATENCY,
            }

    for model in LOCAL_MODELS:
        agents[model['name']] = {
            'token_rate': model['token_rate'],
            'quality': model['quality'],
            'capabilities': model['capabilities'],
            'is_local': True,
            'capacity': model['capacity'],
            'latency': model['latency'],
        }

    agent_names = list(agents.keys())
    return agents, agent_names


def can_assign(intent, agent_name, agents):
    """Check if an agent can handle a task at acceptable quality."""
    agent = agents[agent_name]
    if intent['complexity'] not in agent['capabilities']:
        return False
    if agent['quality'] < intent['min_quality']:
        return False
    return True
