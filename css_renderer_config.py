"""Hyperparameters for the 10K CSS Renderer quantum routing model."""

# Dependency quality degradation penalty weight
DEP_PENALTY = 100.0

# CQM-to-BQM conversion Lagrange multiplier
LAGRANGE_MULTIPLIER = 10.0

# Cost function weights
OVERKILL_WEIGHT = 2
LATENCY_WEIGHT = 0.001

# Token estimates per complexity tier (scaled for CSS renderer complexity)
TOKEN_ESTIMATES = {
    'trivial': 500,        # Simple token matching, property lookups
    'simple': 1500,        # Basic selector parsing, box calculations
    'moderate': 5000,      # Layout algorithms, cascade resolution
    'complex': 12000,      # Flexbox/grid implementations
    'very-complex': 25000, # Compositing, GPU integration
    'epic': 60000,         # Architecture, optimization passes
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

# Rule of thumb: ~2000 tokens per story point (baseline)
TOKENS_PER_STORY_POINT = 2000

# Simulated annealing parameters (tuned for 10K scale)
NUM_READS = 5            # Reduced for speed
NUM_SWEEPS = 300         # Reduced for 10-minute target

# D-Wave hybrid solver time limit (seconds)
HYBRID_TIME_LIMIT = 600  # 10 minutes

# CSS Renderer Pipeline Stages
PIPELINE_STAGES = [
    'parsing',           # Stage 1: CSS Parsing (2,500 tasks)
    'style_computation', # Stage 2: Style Computation (2,500 tasks)
    'layout',            # Stage 3: Layout Engine (2,500 tasks)
    'painting',          # Stage 4: Painting (1,500 tasks)
    'compositing',       # Stage 5: Compositing (1,000 tasks)
]

# Task distribution across stages
STAGE_DISTRIBUTION = {
    'parsing': 2500,
    'style_computation': 2500,
    'layout': 2500,
    'painting': 1500,
    'compositing': 1000,
}

# Complexity distribution within each stage
# Format: (complexity, fraction_of_stage, min_quality)
STAGE_COMPLEXITY = {
    'parsing': [
        ('trivial', 0.30, 0.40),      # Tokenizer work
        ('simple', 0.35, 0.50),       # Basic parsing
        ('moderate', 0.25, 0.70),     # At-rule handling
        ('complex', 0.08, 0.85),      # Complex selectors
        ('very-complex', 0.02, 0.90), # Parser optimization
    ],
    'style_computation': [
        ('trivial', 0.20, 0.40),      # Property lookups
        ('simple', 0.30, 0.50),       # Selector matching
        ('moderate', 0.30, 0.70),     # Cascade resolution
        ('complex', 0.15, 0.85),      # Specificity wars
        ('very-complex', 0.05, 0.90), # Style optimization
    ],
    'layout': [
        ('trivial', 0.15, 0.40),      # Box model basics
        ('simple', 0.25, 0.50),       # Standard layout
        ('moderate', 0.30, 0.70),     # Float/position
        ('complex', 0.20, 0.85),      # Flexbox/Grid
        ('very-complex', 0.08, 0.90), # Layout optimization
        ('epic', 0.02, 0.95),         # Layout engine arch
    ],
    'painting': [
        ('trivial', 0.20, 0.40),      # Basic backgrounds
        ('simple', 0.25, 0.50),       # Borders, simple text
        ('moderate', 0.30, 0.70),     # Complex painting
        ('complex', 0.20, 0.85),      # Effects, gradients
        ('very-complex', 0.05, 0.90), # Paint optimization
    ],
    'compositing': [
        ('simple', 0.20, 0.50),       # Layer basics
        ('moderate', 0.30, 0.70),     # Layer tree
        ('complex', 0.30, 0.85),      # GPU commands
        ('very-complex', 0.15, 0.90), # Compositing optimization
        ('epic', 0.05, 0.95),         # GPU architecture
    ],
}

# Workflow chain counts per stage
WORKFLOW_CHAINS_PER_STAGE = {
    'parsing': 150,
    'style_computation': 150,
    'layout': 150,
    'painting': 100,
    'compositing': 80,
}

# Cross-stage dependency edges (API contracts between stages)
CROSS_STAGE_EDGES = 500

# Time budget for classical solver (seconds)
CLASSICAL_TIME_BUDGET = 600  # 10 minutes
