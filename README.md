# QAAS — Quantum Agent Annealed Swarm

Quantum annealing to optimally assign coding tasks ("intents") to a heterogeneous swarm of AI agents. Given N intents and M agents with different costs, quality levels, capabilities, and capacities, find the assignment that minimizes total cost while satisfying all constraints.

Maps to D-Wave's Multi-Vehicle Routing Problem (MVRP), simplified to clustering (assignment) without route ordering.

## Agent Pool

| Type | Models | Sessions | Capacity/session | Total slots |
|------|--------|----------|------------------|-------------|
| Cloud | claude, gpt5.2, gemini, kimi2.5 | 10 each | 25 | 1,000 |
| Local | llama, mistral, codellama, phi3, qwen2, deepseek-coder, etc. | 1 each | 2–4 | 19 |
| **Total** | **12 models** | **48 agents** | | **1,019** |

## Intent Backlog (1,000 intents)

| Tier | Count | Tokens/intent | SP/intent | Total tokens | Total SP |
|------|-------|---------------|-----------|-------------|----------|
| trivial | 200 | 350 | 1 | 70,000 | 200 |
| simple | 300 | 1,000 | 2 | 300,000 | 600 |
| moderate | 250 | 3,500 | 3 | 875,000 | 750 |
| complex | 150 | 8,500 | 5 | 1,275,000 | 750 |
| very-complex | 70 | 15,000 | 8 | 1,050,000 | 560 |
| epic | 30 | 35,000 | 13 | 1,050,000 | 390 |
| **Total** | **1,000** | | | **4,620,000** | **3,250** |

50 workflow chains create dependency constraints (feature-dev, bug-fix, infra), forcing sequential execution within chains.

## Factory Throughput

One batch of 1,000 intents = **3,250 story points** in ~12–40 minutes:

- ~12 min if all independent (bottleneck = longest epic at 35K tokens)
- ~40 min with dependency chains on the critical path

### 8-hour factory day

| Scenario | Batch time | Batches/day | Intents/day | SP/day |
|----------|-----------|-------------|-------------|--------|
| All independent | ~12 min | ~40 | 40,000 | 130,000 |
| With chains | ~40 min | ~12 | 12,000 | 39,000 |

### Human baseline: 10-person team, 6 hours/day coding

QAAS story points are calibrated small (1 SP = a trivial 15-minute fix), not the common industry scale where 1 SP = half a day. Realistic human throughput at this calibration:

| Tier | SP | Example | Human time | Tasks/person/6hr day |
|------|----|---------|-----------:|---------------------:|
| trivial | 1 | fix-typo | 15–30 min | 12–24 |
| simple | 2 | fix-off-by-one | 45 min – 1.5 hr | 4–8 |
| moderate | 3 | write-unit-test | 2–4 hr | 1.5–3 |
| complex | 5 | implement-auth-flow | 1–3 days | 0.3–1 |
| very-complex | 8 | design-distributed-system | 3–5 days | ~0.2 |
| epic | 13 | redesign-platform-architecture | 1–2 weeks | ~0.1 |

Following the intent distribution mix: **~5 SP/person/day** (conservative, includes context-switching overhead).

| | 10-person team | Swarm (chained) | Swarm (independent) |
|---|---|---|---|
| SP/day | 50 | 39,000 | 130,000 |
| SP/sprint (10 days) | 500 | 390,000 | 1,300,000 |
| **Swarm multiplier** | **1x** | **780x** | **2,600x** |

### The real bottleneck: humans are the backlog

The swarm consumes 12,000–40,000 intents/day. But someone has to *write* them — scoping work, setting complexity, defining dependencies, writing clear task descriptions. Humans are the backlog.

| Intent complexity | Time to author | Intents/person/6hr day |
|---|---:|---:|
| trivial | 2–5 min | 70–180 |
| simple | 5–15 min | 24–72 |
| moderate | 15–30 min | 12–24 |
| complex | 30–60 min | 6–12 |
| very-complex | 1–2 hr | 3–6 |
| epic | 2–4 hr | 1.5–3 |

Following the distribution mix: **~30 intents/person/day**.

| | 10-person team | Swarm capacity |
|---|---|---|
| Intents/day | ~300 | 12,000–40,000 |
| Intents/sprint | ~3,000 | 120,000–400,000 |
| **Swarm utilization** | | **0.75–2.5%** |

The swarm runs at **~1% utilization** waiting on humans. The factory floor is idle 99% of the time. The quantum optimizer is solving the wrong bottleneck — the constraint isn't *which agent gets which task*, it's *generating enough well-specified tasks to keep the agents busy*.

This inverts the traditional engineering model: developers stop being the labor and become the supply chain. Their job is to decompose, specify, and sequence work fast enough to feed the swarm.

### Agents as the supply chain: recursive decomposition

The supply chain bottleneck solves itself when agents generate intents for other agents. A human writes one epic intent ("redesign the auth system") and a decomposition agent cascades it into executable leaf intents:

```
Human: 1 epic intent
  → Decomposer agent: 5–15 sub-intents (complex, moderate)
    → Further decomposition: 30–100 leaf intents (simple, trivial)
      → Swarm executes leaves in parallel
```

| | Humans only | Humans + agent decomposition |
|---|---|---|
| Intents/person/day | ~30 | ~300–1,000 |
| 10-person team/day | ~300 | ~3,000–10,000 |
| Swarm utilization | ~1% | ~8–80% |

The human's job shrinks from "write 30 detailed intents" to "write 10–30 epics and review the decomposition tree."

### Where agents become the bottleneck

Once humans are out of the critical path, the bottleneck shifts to the **decomposition agents themselves**. They're doing the hard cognitive work — scoping, sequencing, defining acceptance criteria — and they consume tokens to do it.

This is where the economics flip: **more throughput costs more**. Every layer of decomposition is a paid inference call.

| Layer | Work | Tokens consumed | Who pays |
|---|---|---|---|
| Human | Write epic intent | 0 | Salary |
| Decomposer (L1) | Epic → 5–15 complex/moderate sub-intents | ~8,000–20,000 | Token cost |
| Decomposer (L2) | Complex → 5–10 simple/trivial leaves | ~3,000–8,000 per sub-intent | Token cost |
| Executor swarm | Run the leaf intents | ~350–3,500 per leaf | Token cost |

For one epic decomposed into ~50 leaf intents:

| Stage | Tokens | Cost (claude) | Cost (optimized mix) |
|---|---|---|---|
| Decomposition (L1+L2) | ~60,000–140,000 | $1.20–$2.80 | $0.30–$0.70 |
| Execution (50 leaves) | ~50,000–100,000 | $1.00–$2.00 | $0.10–$0.50 |
| **Total per epic** | **~110,000–240,000** | **$2.20–$4.80** | **$0.40–$1.20** |

Scale that to the 10-person team writing 20 epics/day:

| | Per day | Per sprint |
|---|---|---|
| Epics authored | 200 | 2,000 |
| Leaf intents generated | ~10,000 | ~100,000 |
| Decomposition cost (optimized) | $60–$140 | $600–$1,400 |
| Execution cost (optimized) | $20–$100 | $200–$1,000 |
| **Total factory cost** | **$80–$240** | **$800–$2,400** |

The quantum optimizer now matters at both levels: assigning decomposition work to the cheapest agent that can handle it, *and* assigning leaf execution. The cost function is the same — token_cost + overkill + quality floor — but applied recursively.

**The insight:** throughput and cost are now the same knob. Want 10x more leaf intents? Spend 10x more on decomposition. The factory's output is directly proportional to its token budget. Humans set the direction, agents are both the supply chain and the labor, and the quantum router optimizes the cost of the whole pipeline.

### Cost to run the factory

4,620,000 tokens per batch. The quantum optimizer pushes cheap work to kimi2.5/gemini and reserves claude for complex+.

| | Per batch | Per day (chained) | Per sprint |
|---|---|---|---|
| All-claude ceiling | ~$92 | ~$1,100 | ~$11,000 |
| Optimized mix | ~$30–50 | ~$360–600 | ~$3,600–6,000 |
| Local-only floor | $0 | $0 | $0 |

The annealer finds the cheapest valid assignment across all 1,000 x 48 possibilities simultaneously, rather than greedily overspending by assigning claude to trivial work.

## Running

```bash
source .venv/bin/activate
```

The notebook `quantum-routing.ipynb` runs end-to-end: defines 48 agents, generates 1,000 intents, builds a Constrained Quadratic Model (CQM), solves via simulated annealing, and compares against a greedy baseline.

For real quantum hardware (requires D-Wave Leap API token):

```bash
dwave config create   # one-time setup
```

Then uncomment the `LeapHybridCQMSampler` cell in the notebook.

## Architecture

Six Python modules orchestrated by the notebook:

- **`config.py`** — Hyperparameters, token estimates, story points, solver settings
- **`agents.py`** — Agent pool: cloud models x sessions + local models, capability filtering
- **`intents.py`** — Intent generation across 5 complexity tiers, workflow dependency chains
- **`model.py`** — Cost function (token_cost + overkill + latency) and CQM construction
- **`solve.py`** — Simulated annealing, D-Wave hybrid, greedy baseline solvers
- **`report.py`** — Factory floor shift report and solver comparison output

## Dependencies

D-Wave Ocean SDK (`dwave-ocean-sdk`), `numpy`. Python 3.13.
