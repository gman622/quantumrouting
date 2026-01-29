"""Hyperparameters for the QAAS quantum routing model."""

# Dependency quality degradation penalty weight
DEP_PENALTY = 100.0

# CQM-to-BQM conversion Lagrange multiplier
LAGRANGE_MULTIPLIER = 10.0

# Cost function weights
OVERKILL_WEIGHT = 2
LATENCY_WEIGHT = 0.001

# Token estimates per complexity tier
TOKEN_ESTIMATES = {
    'trivial': 350,
    'simple': 1000,
    'moderate': 3500,
    'complex': 8500,
    'very-complex': 15000,
    'epic': 35000,
}

# Fibonacci story points per tier (reporting only — CQM stays token-based)
STORY_POINTS = {
    'trivial': 1,
    'simple': 2,
    'moderate': 3,
    'complex': 5,
    'very-complex': 8,
    'epic': 13,
}

# Rule of thumb: ~2000 tokens per story point
TOKENS_PER_STORY_POINT = 2000

# Simulated annealing parameters
NUM_READS = 10
NUM_SWEEPS = 500

# D-Wave hybrid solver time limit (seconds)
HYBRID_TIME_LIMIT = 60
