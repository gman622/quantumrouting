# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QAAS (Quantum Agent Annealed Swarm) is a research proof-of-concept that uses quantum annealing to optimally assign tasks ("intents") to a heterogeneous swarm of AI agents. The core problem: given N intents and M agents with different costs, quality levels, capabilities, and capacities, find the assignment that minimizes total cost while satisfying all constraints.

This maps to D-Wave's Multi-Vehicle Routing Problem (MVRP) but simplified — QAAS only needs clustering (assignment), not route ordering.

## Running the Project

The notebook `quantum-routing.ipynb` is the primary artifact. Read it directly — all cells include their output. It runs end-to-end: defines 48 agents and 1000 intents, builds a Constrained Quadratic Model (CQM), solves via simulated annealing, and compares against a greedy baseline.

To re-execute or modify cells:
```bash
source .venv/bin/activate
```

To run on real quantum hardware (requires D-Wave Leap API token):
```bash
dwave config create   # one-time setup
```
Then uncomment the `LeapHybridCQMSampler` cell in the notebook.

## Architecture

The notebook `quantum-routing.ipynb` is a thin orchestrator that imports from six Python modules:

- **`config.py`** — All hyperparameters: `DEP_PENALTY`, `LAGRANGE_MULTIPLIER`, `OVERKILL_WEIGHT`, `LATENCY_WEIGHT`, `NUM_READS`, `NUM_SWEEPS`, `HYBRID_TIME_LIMIT`, `TOKEN_ESTIMATES` (per-complexity token counts)
- **`agents.py`** — Agent pool data as lists of dicts with named keys (`CLOUD_MODELS`, `LOCAL_MODELS`). Each agent has a `token_rate` ($/token). `build_agent_pool()` returns `(agents_dict, agent_names)`. `can_assign(intent, agent_name, agents)` filters valid pairs.
- **`intents.py`** — `INTENT_TEMPLATES`, `DISTRIBUTION`. `generate_intents()` returns list of intent dicts, each with `estimated_tokens` from `config.TOKEN_ESTIMATES`. `build_workflow_chains(intents)` creates dependency chains.
- **`model.py`** — `get_cost(intent, agent_name, agents)` computes per-assignment cost (token_cost + overkill + latency), where token_cost = estimated_tokens × token_rate. `build_cqm(intents, agents, agent_names)` returns `(cqm, x_vars)`.
- **`solve.py`** — `solve_sa(cqm)` runs simulated annealing. `solve_hybrid(cqm)` runs D-Wave Leap. `greedy_solve(intents, agents)` runs the greedy baseline. `parse_assignments(sampleset, agent_names)` extracts results.
- **`report.py`** — `print_shift_report(assignments, intents, agents, workflow_chains)` prints the factory floor report. `print_comparison(anneal_assignments, greedy_assignments, greedy_cost, intents, agents)` prints the head-to-head table.

The pipeline:

1. **Agent pool** — `build_agent_pool()` creates 48 agents: 40 cloud (claude, gpt5.2, gemini, kimi2.5 × 10 sessions each, capacity 25) + 8 local (llama, mistral, etc., capacity 2-4, free but lower quality)
2. **Intent generation** — `generate_intents()` creates 1000 tasks across 5 complexity tiers, each with a minimum quality bar
3. **Dependency chains** — `build_workflow_chains()` creates 50 workflow chains (feature-dev, bug-fix, infra)
4. **CQM construction** — `build_cqm()` creates binary variables `x_ij` (intent i → agent j), with token-based cost + overkill + latency + dependency penalty objective and one-assignment + capacity hard constraints
5. **Solve** — `solve_sa()` does CQM→BQM conversion then `neal.SimulatedAnnealingSampler` (or `solve_hybrid()` on D-Wave hardware)
6. **Greedy comparison** — `greedy_solve()` picks cheapest valid agent per task, first-come-first-served

## Dependencies

D-Wave Ocean SDK (`dwave-ocean-sdk`) is the primary dependency, providing `dimod`, `dwave-system`, `dwave-neal`, and related packages. Also uses `numpy`. Python 3.13.

## Key Documentation

- `quantum-agent-annealed-swarm.md` — QUBO formulation, cost matrix, scale estimates, implementation phases
- `dependency-aware-routing.md` — Wave-based routing algorithm for handling intent dependencies (Kahn's algorithm for topological sort into waves, then quantum optimize each wave)
- `mvrp-to-qaas-mapping.md` — How D-Wave's vehicle routing maps to agent task routing
- `nextsteps.md` — Roadmap: token-based costs → deadlines + context affinity → D-Wave Leap → integrate into Intenterator VS Code extension

## Intent Format

`.intent` files use YAML frontmatter with fields: `@id`, `@complexity`, `@agent` (local/cloud/auto), `@depends` (list of prerequisite intent IDs). Body is markdown describing the task.

## Current Results

- All 1000 tasks assigned, zero constraint violations
- Token-based cost model: cost = estimated_tokens × token_rate, creating significant cost variance across complexity tiers (500–8000 tokens) and agents ($0–$0.005/token)
- The value of quantum optimization is expected to emerge with deadlines, context affinity, and at larger scale via D-Wave hybrid solvers
