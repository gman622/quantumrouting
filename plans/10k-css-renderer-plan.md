# 10K Task CSS Renderer - Quantum Agent Routing Plan

## Overview

Scale the QAAS (Quantum Agent Annealed Swarm) system from 1K to 10K tasks for building a CSS Renderer from scratch. This is a stepping stone toward the 1M-task browser architecture.

## Current vs Target Scale

| Metric | Current (1K) | Target (10K) | Growth |
|--------|--------------|--------------|--------|
| Tasks | 1,000 | 10,000 | 10× |
| Agents | 48 | 300 | 6.25× |
| Binary variables | ~42K | ~500K | 12× |
| Quadratic terms | ~65K | ~800K | 12× |
| Problem class | NP-hard | NP-hard | — |

## CSS Renderer Architecture (10K Tasks)

The CSS rendering pipeline consists of 5 major stages with dependencies flowing downward:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CSS RENDERER PIPELINE                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Stage 1: CSS Parsing (2,500 tasks)                                 │
│    ├── Tokenizer/Lexer (800)                                        │
│    ├── Parser - At-rules (600)                                      │
│    ├── Parser - Selectors (700)                                     │
│    └── Parser - Declarations (400)                                  │
│                                                                     │
│  Stage 2: Style Computation (2,500 tasks)                           │
│    ├── Selector matching (800)                                      │
│    ├── Specificity calculation (600)                                │
│    ├── Cascade resolution (500)                                     │
│    └── Inheritance propagation (600)                                │
│                                                                     │
│  Stage 3: Layout Engine (2,500 tasks)                               │
│    ├── Box model calculation (700)                                  │
│    ├── Flexbox layout (600)                                         │
│    ├── Grid layout (600)                                            │
│    └── Positioning (float, absolute) (600)                          │
│                                                                     │
│  Stage 4: Painting (1,500 tasks)                                    │
│    ├── Background rendering (400)                                   │
│    ├── Border rendering (300)                                       │
│    ├── Text rendering (400)                                         │
│    └── Effects (shadows, filters) (400)                             │
│                                                                     │
│  Stage 5: Compositing (1,000 tasks)                                 │
│    ├── Layer creation (300)                                         │
│    ├── Layer tree building (300)                                    │
│    └── GPU command generation (400)                                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Task Complexity Distribution

| Tier | Count | Story Points | Min Quality | Description |
|------|-------|--------------|-------------|-------------|
| trivial | 2,000 | 1 | 0.40 | Simple token matching, property lookups |
| simple | 3,000 | 2 | 0.50 | Basic selector parsing, box calculations |
| moderate | 2,500 | 3 | 0.70 | Layout algorithms, cascade resolution |
| complex | 1,500 | 5 | 0.85 | Flexbox/grid implementations |
| very-complex | 700 | 8 | 0.90 | Compositing, GPU integration |
| epic | 300 | 13 | 0.95 | Architecture, optimization passes |

**Total: 10,000 tasks, 32,400 story points**

## Agent Pool (300 Agents)

### Cloud Agents (240 agents)
| Model | Sessions | Capacity/Session | Total Capacity | Token Rate | Quality |
|-------|----------|------------------|----------------|------------|---------|
| claude | 60 | 50 | 3,000 | $0.000020 | 0.95 |
| gpt5.2 | 60 | 50 | 3,000 | $0.000030 | 0.92 |
| gemini | 60 | 50 | 3,000 | $0.000005 | 0.88 |
| kimi2.5 | 60 | 50 | 3,000 | $0.000002 | 0.85 |

### Local Agents (60 agents)
| Model | Count | Capacity | Total Capacity | Token Rate | Quality |
|-------|-------|----------|----------------|------------|---------|
| llama3.2-1b | 10 | 10 | 100 | $0 | 0.40 |
| llama3.2-3b | 10 | 8 | 80 | $0 | 0.55 |
| llama3.1-8b | 10 | 6 | 60 | $0 | 0.65 |
| codellama-7b | 10 | 6 | 60 | $0 | 0.70 |
| mistral-7b | 10 | 6 | 60 | $0 | 0.60 |
| qwen2-7b | 10 | 6 | 60 | $0 | 0.65 |

**Total Capacity: 9,420 tasks** (with headroom for 10K)

## Dependency Patterns

### Stage Dependencies (Hard Constraints)
Each stage depends on the previous:
- Parsing → Style Computation → Layout → Painting → Compositing

### Cross-Stage API Contracts
- CSS property definitions flow: Parser → Style → Layout
- Box metrics flow: Layout → Painting → Compositing
- ~500 cross-stage dependency edges

### Intra-Stage Parallelism
- Tasks within a stage can run in parallel
- ~200 workflow chains per stage modeling feature development

## Solver Strategy

### Classical Approach (Simulated Annealing)
- CQM-to-BQM conversion with Lagrange multipliers
- Time budget: 10 minutes (600 seconds)
- Expected variables: ~500K binary
- Expected solve time: 5-10 minutes

### Fallback: Wave-Based Decomposition
If monolithic CQM is too large:
1. Decompose by pipeline stage (5 waves)
2. Solve each wave independently
3. Resolve cross-wave dependencies in post-processing

## Success Criteria

1. **All 10K tasks assigned** (no drops)
2. **Zero stage-order violations** (Parsing before Layout)
3. **Zero capacity violations** (no overloaded agents)
4. **Cost within 10% of theoretical minimum**
5. **Solve time under 10 minutes**

## File Structure

```
quantumrouting/
├── config.py                    # Original 1K config
├── agents.py                    # Original 1K agents
├── intents.py                   # Original 1K intents
├── model.py                     # Original CQM builder
├── solve.py                     # Original solvers
├── report.py                    # Original reporting
├── css_renderer_config.py       # NEW: 10K hyperparameters
├── css_renderer_agents.py       # NEW: 300 agent definitions
├── css_renderer_intents.py      # NEW: 10K CSS task taxonomy
├── css_renderer_model.py        # NEW: Extended CQM builder
├── solve_10k.py                 # NEW: Time-bounded SA solver
├── report_10k.py                # NEW: CSS-specific reporting
└── quantum-routing-10k.ipynb    # NEW: 10K orchestration notebook
```

## Implementation Phases

### Phase 1: Configuration & Agents
- Create `css_renderer_config.py` with 10K-specific parameters
- Create `css_renderer_agents.py` with 300-agent pool

### Phase 2: Task Taxonomy
- Create `css_renderer_intents.py` with CSS pipeline tasks
- Define 10K tasks across 5 pipeline stages
- Build stage-based dependency chains

### Phase 3: Model Extension
- Extend `css_renderer_model.py` for larger scale
- Implement wave-based decomposition option

### Phase 4: Solvers & Reporting
- Create `solve_10k.py` with time-bounded SA
- Create `report_10k.py` with CSS-specific metrics

### Phase 5: Integration
- Create `quantum-routing-10k.ipynb` notebook
- Test end-to-end pipeline
- Validate against success criteria
