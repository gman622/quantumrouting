# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

**Intent IDE** is an experimental development environment where intents (tasks) replace files as the primary unit of work. Instead of navigating a file tree, you navigate a directed graph of 10,000 tasks, adjust constraint sliders, and watch a CP-SAT solver route work across 300 heterogeneous AI agents in real time.

The core optimization problem: given N intents and M agents with different costs, quality levels, and capacities, minimize total cost while satisfying all constraints.

## Running the Project

**Intent IDE (web app)**:
```bash
source .venv/bin/activate
pip install -e .
python -m intent_ide        # Flask backend on :5001
cd frontend && npm run dev  # React frontend on :5173 (or npm run build for production)
```

**Notebooks** (for exploration/research):
```bash
source .venv/bin/activate
jupyter notebook notebooks/quantum-routing-10k.ipynb
```

## Architecture

### Intent IDE (`src/intent_ide/`)

The web app is a Flask backend + React frontend:

- **`app.py`** — Flask server with REST + WebSocket APIs. Initializes 10K intents and 300 agents on startup, runs initial CP-SAT solve, serves React build.
- **`graph_data.py`** — Transforms intents/assignments into React Flow nodes and edges. Computes status (satisfied/overkill/violated) per intent.
- **`solver_worker.py`** — Background thread that re-runs CP-SAT when constraints change. Emits progress via WebSocket.

### Solver Backend (`src/quantum_routing/`)

Shared between Intent IDE and notebooks:

- **`css_renderer_config.py`** — Hyperparameters: `OVERKILL_WEIGHT`, `LATENCY_WEIGHT`, `DEADLINE_PENALTY`, token estimates per complexity tier
- **`css_renderer_agents.py`** — Agent pool: 240 cloud (claude, gpt5.2, gemini, kimi2.5 × 60 sessions, capacity 50) + 60 local (llama, mistral, etc., capacity 6-10). Each agent has `token_rate`, `quality`, `latency`.
- **`css_renderer_intents.py`** — Generates 10K intents across 5 pipeline stages and 6 complexity tiers. Each intent has `estimated_tokens`, `quality_floor`, `deadline`. `build_workflow_chains()` creates dependency edges.
- **`solve_10k_ortools.py`** — CP-SAT solver. Creates binary variables `x[i,j]` (intent i → agent j), minimizes cost subject to one-assignment and capacity constraints.
- **`report_10k.py`** — Generates shift reports: total cost, $/story-point, agent utilization, overkill instances.

### Frontend (`frontend/`)

React + TypeScript + Tailwind + React Flow:

- **`components/IntentCanvas.tsx`** — Zoomable DAG visualization with stage nodes, cluster nodes, and intent nodes
- **`components/ConstraintPanel.tsx`** — Sliders for quality_floor, budget_cap, overkill_weight, etc.
- **`components/AgentRoster.tsx`** — Agent list with utilization bars
- **`components/ViolationsDashboard.tsx`** — Status counts and constraint health
- **`store.ts`** — Zustand store managing constraints, assignments, and WebSocket connection
- **`types.ts`** — TypeScript types: `Intent`, `Agent`, `Status`, `Constraints`

## Cost Model

```
cost = token_cost + overkill_cost + latency_cost + deadline_penalty

where:
  token_cost   = estimated_tokens × token_rate
  overkill_cost = (agent_quality - intent_quality_floor) × token_cost × OVERKILL_WEIGHT
  latency_cost  = agent_latency × LATENCY_WEIGHT
  deadline_penalty = max(0, completion_time - deadline) × DEADLINE_PENALTY
```

**Overkill** penalizes assigning expensive high-quality agents to tasks that don't need them. This pushes trivial tasks toward cheap/free local models.

## Key Documentation

- `docs/intent-ide-2030.md` — Vision doc: what software development looks like when code is exhaust
- `docs/nextsteps.md` — Roadmap: scaling, D-Wave integration, Intenterator VS Code extension
- `docs/quantum-agent-annealed-swarm.md` — Original QUBO formulation for D-Wave
- `docs/dependency-aware-routing.md` — Wave-based algorithm for dependency handling

## Constraints

**Hard constraints** (must satisfy):
- Each intent assigned to exactly one agent
- No agent exceeds capacity
- Agent quality ≥ intent quality floor

**Soft constraints** (sliders in UI):
- `quality_floor` — Minimum acceptable quality (0.5–0.95)
- `budget_cap` — Maximum total spend
- `overkill_weight` — How much to penalize quality surplus (default 2.0)
- `latency_weight` — How much to penalize slow agents
- `deadline_penalty` — Cost per unit time past deadline

## Intent Format

`.intent` files use YAML frontmatter:
```yaml
@id: parse-css-selectors
@complexity: moderate
@agent: auto
@depends:
  - tokenize-input
---
Parse CSS selectors into AST nodes...
```

## Dependencies

- `ortools` — Google CP-SAT solver (primary)
- `dwave-ocean-sdk` — D-Wave quantum annealing (optional, for notebooks)
- `flask`, `flask-socketio`, `flask-cors` — Backend
- `numpy`, `matplotlib` — Data/visualization

Python 3.13, Node 18+.
