# Staffing Engine Usage Guide

This guide walks through the staffing engine end-to-end: from a feature request or bug report to a fully executed, quality-gated plan.

## Overview

The staffing engine turns decomposed intents into an execution plan:

```
GitHub Issue / Feature Request
        │
        ▼
   Decomposer           (feature_decomposer, github_tickets, or agent_decomposer)
        │
        ▼
   Staffing Engine       (assign profiles, schedule waves, estimate costs)
        │
        ▼
   Wave Executor         (execute wave-by-wave with quality gates)
        │
        ▼
   Final Verdict          (SHIP_IT / REVISE / RETHINK)
```

## Quick Start

```bash
source .venv/bin/activate
pip install -e .

# Run the staffing engine CLI (slider bug demo)
python -m quantum_routing.staffing_engine

# Run the wave executor (simulated execution)
python -m quantum_routing.wave_executor

# Run against live GitHub issues
python -m quantum_routing.wave_executor --github
python -m quantum_routing.wave_executor --github --issue 13

# Target any GitHub repo
python -m quantum_routing.wave_executor --repo facebook/react --issue 42

# Create real companion issues on GitHub
python -m quantum_routing.wave_executor --issue 13 --materialize
python -m quantum_routing.wave_executor --repo owner/repo --issue 42 --materialize
```

## End-to-End Example

### Step 1: Decompose a ticket

The decomposer breaks a high-level request into atomic intents:

```python
from quantum_routing.feature_decomposer import decompose_slider_bug

intents = decompose_slider_bug()
print(f"{len(intents)} intents")  # 12 intents
```

Each intent has an ID, complexity, tags, dependencies, and estimated token count:

```python
intent = intents[0]
print(intent.id)          # "bug2-1-reproduce"
print(intent.complexity)  # "trivial"
print(intent.tags)        # ["reproduce"]
print(intent.depends)     # []
```

For GitHub issues, use the `github_tickets` module:

```python
from quantum_routing.github_tickets import import_issue, decompose_ticket_smart

ticket = import_issue(10)
intents = decompose_ticket_smart(ticket)  # Uses LLM with template fallback
```

### Step 2: Generate a staffing plan

```python
from quantum_routing.staffing_engine import generate_staffing_plan

plan = generate_staffing_plan(intents)
```

The plan is a JSON-serializable dict:

```python
print(f"Waves:       {plan['total_waves']}")        # 8
print(f"Parallelism: {plan['peak_parallelism']}")    # 3
print(f"Cost:        ${plan['total_estimated_cost']:.4f}")
print(f"Profiles:    {plan['profile_load']}")
# {'bug-hunter': 4, 'testing-guru': 2, 'feature-trailblazer': 3, ...}
```

Each wave contains intent assignments:

```python
for wave in plan["waves"]:
    print(f"\nWave {wave['wave']} ({wave['agents_needed']} agents):")
    for intent in wave["intents"]:
        print(f"  {intent['id']} -> {intent['profile']} ({intent['model']})")
```

### Step 3: Execute the plan

```python
from quantum_routing.wave_executor import WaveExecutor, SimulatedBackend

executor = WaveExecutor(
    backend=SimulatedBackend(failure_rate=0.15, seed=42),
    max_retries=4,
    progress_callback=lambda event, data: print(f"  [{event}] {data}"),
)

result = executor.execute_plan(plan)
```

### Step 4: Check the verdict

```python
verdict = result.final_verdict
print(f"Verdict:    {verdict.verdict.value}")          # "ship_it"
print(f"Score:      {verdict.score}/100")
print(f"Fitness:    {verdict.production_fitness}/100")
print(f"Arch:       {verdict.architecture_score}/100")
print(f"Docs:       {verdict.consumability_score}/100")
print(f"Passed:     {result.passed_count}")
print(f"Failed:     {result.failed_count}")
print(f"Human:      {result.human_review_count}")
```

## CLI Usage

### Staffing Engine CLI

```bash
python -m quantum_routing.staffing_engine
```

Prints staffing plans for both the slider bug (12 intents) and the real-time collaboration feature (25 intents), including profile load, wave breakdown, critical path, and a JSON export sample.

### Wave Executor CLI

**Default demo** (slider bug with simulated backend):
```bash
python -m quantum_routing.wave_executor
```

**GitHub issues** (fetch, decompose, staff, execute):
```bash
# All open issues from current repo
python -m quantum_routing.wave_executor --github

# Single issue
python -m quantum_routing.wave_executor --github --issue 13

# Force template decomposition (skip LLM)
python -m quantum_routing.wave_executor --github --template

# Target any GitHub repo (--repo implies --github)
python -m quantum_routing.wave_executor --repo facebook/react --issue 42

# Create real companion issues on GitHub (--materialize)
python -m quantum_routing.wave_executor --issue 13 --materialize
python -m quantum_routing.wave_executor --repo owner/repo --issue 42 --materialize
```

### Materializing Companion Issues

The `--materialize` flag creates real GitHub issues following the 4-agent pattern:

```
Parent #20: Add caching to API layer
  ├── #21 [Agent: feature-trailblazer] Add caching to API layer
  ├── #22 [Agent: tenacious-unit-tester] Add caching to API layer
  ├── #23 [Agent: docs-logs-wizard] Add caching to API layer
  └── #24 [Agent: code-ace-reviewer] Add caching to API layer  (blocked by #21, #22, #23)
```

Each companion issue includes:
- Assigned intents from the staffing plan
- Quality gates checklist specific to the agent role
- The reviewer issue links to the other 3 as dependencies

A summary comment is posted on the parent issue with all companion links and staffing plan stats.

### Frontend: Staffing Panel

The Intent IDE frontend includes a **Staff** tab in the left panel:

1. Enter a repository (optional — defaults to current repo)
2. Enter an issue number
3. Click **Staff It**
4. The backend decomposes the issue, generates a staffing plan, and creates 4 companion issues
5. Results display: companion issue links, plan stats (intents, waves, parallelism, cost), and profile load bars

The endpoint is `POST /api/materialize` — see the API reference for details.

## Understanding the Output

### Profile Load

Shows how many intents each agent profile is handling:

```
Profile load:
  bug-hunter                 4  ####
  feature-trailblazer        3  ###
  testing-guru               2  ##
  tenacious-unit-tester      1  #
  code-ace-reviewer          1  #
  task-predator              1  #
```

### Wave Breakdown

Each wave runs in parallel. Waves execute sequentially:

```
Wave 0 (1 agent, $0.0000):
  [trivial     ] bug2-1-reproduce    → bug-hunter  (kimi2.5, $0.0010)

Wave 1 (2 agents, $0.0060):
  [simple      ] bug2-2-profile      → bug-hunter  (kimi2.5, $0.0030)
  [simple      ] bug2-3-analyze      → bug-hunter  (kimi2.5, $0.0030)
```

### Quality Gates

The executor validates at three checkpoints:

- **Gate 1 (per-intent)**: After each attempt. Profile-specific criteria (see API reference). Triggers retry/escalation on failure.
- **Gate 2 (per-wave)**: After all intents in a wave complete. Checks status, quality floor, and test results.
- **Gate 3 (final)**: After all waves. Produces `SHIP_IT` / `REVISE` / `RETHINK` verdict with subscores.

### Retry Ladder

When an intent fails validation:

1. **Attempt 1**: Retry with the same agent
2. **Attempt 2**: Escalate to a higher-quality model
3. **Attempt 3+**: Flag for human review

## Extending the Engine

### Adding a New Profile

1. Add the profile name to `PROFILES` in `staffing_engine.py`
2. Add tag keywords to drive routing in `assign_profile()`
3. Add model mappings to `PROFILE_AGENT_MODELS`
4. Add a validator function in `quality_gates.py` and register it in `_PROFILE_VALIDATORS`
5. Create `.claude/agents/{profile-name}.md` with Mission, Workflow, and Quality Gates sections
6. Add artifact templates to `_ARTIFACT_TEMPLATES` in `wave_executor.py`

### Adding a New Decomposer

The staffing engine accepts any intent format. Your decomposer output needs:

- `id` (str) — unique identifier
- `depends` or `dependencies` (list[str]) — IDs of prerequisite intents
- `complexity` (str) — one of: `trivial`, `simple`, `moderate`, `complex`, `very-complex`, `epic`
- `tags` (list[str]) — keywords that drive profile routing
- `estimated_tokens` (int) — token estimate for cost calculation

Can be a dataclass or a plain dict.

### Custom Execution Backend

Implement the `ExecutionBackend` protocol:

```python
from quantum_routing.wave_executor import ExecutionBackend, ExecutionContext
from quantum_routing.quality_gates import IntentResult

class MyBackend:
    def execute_intent(
        self, intent_spec: dict, context: ExecutionContext
    ) -> IntentResult:
        # Your execution logic here
        return IntentResult(
            intent_id=context.intent_id,
            profile=context.profile,
            status="completed",
            quality_score=0.9,
            tests_passed=True,
            coverage_delta=0.0,
            artifacts=["PR #42"],
        )

executor = WaveExecutor(backend=MyBackend())
```

## Troubleshooting

**`ValueError: Circular dependency detected`** — Your intent graph has a cycle. Check the `depends` fields. The error message shows the cycle path.

**`ValueError: ... does not exist`** — An intent depends on an ID that isn't in the intent list. Check for typos in dependency IDs.

**All intents flagged for human review** — The failure rate is too high or quality thresholds are too strict. With `SimulatedBackend`, lower `failure_rate` or increase `max_retries`.

**`RETHINK` verdict on good results** — Check `consumability_score`. It penalizes lack of documentation artifacts. Ensure doc-related intents produce `.md` files.
