# Staffing Engine API Reference

The staffing engine maps decomposed intents to agent profiles, schedules them into parallel execution waves, validates quality at three checkpoints, and orchestrates execution with retry/escalation logic.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INPUT SOURCES                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   feature_    │  │   github_    │  │   agent_     │              │
│  │  decomposer   │  │   tickets    │  │  decomposer  │              │
│  │  (dataclass)  │  │   (dict)     │  │  (dataclass) │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         └─────────────┬───┴──────────────────┘                      │
│                       ▼                                             │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                  STAFFING ENGINE                             │    │
│  │                                                             │    │
│  │  assign_profile() ──→ compute_waves() ──→ generate_plan()  │    │
│  │       │                     │                    │          │    │
│  │   tag/phase             Kahn's alg          cost estimate   │    │
│  │   matching              (topo sort)         + profile load  │    │
│  └─────────────────────────┬───────────────────────────────────┘    │
│                            ▼                                        │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    WAVE EXECUTOR                             │    │
│  │                                                             │    │
│  │  for each wave (sequential):                                │    │
│  │    ┌─────────────────────────────────────────────┐          │    │
│  │    │  for each intent (parallel):                │          │    │
│  │    │    Backend.execute_intent()                  │          │    │
│  │    │         │                                    │          │    │
│  │    │         ▼                                    │          │    │
│  │    │  ┌─── GATE 1: validate_intent() ───┐        │          │    │
│  │    │  │  pass → record artifacts         │        │          │    │
│  │    │  │  fail → retry / escalate / human │        │          │    │
│  │    │  └──────────────────────────────────┘        │          │    │
│  │    └─────────────────────────────────────────────┘          │    │
│  │         │                                                   │    │
│  │         ▼                                                   │    │
│  │  ┌─── GATE 2: validate_wave() ───┐                         │    │
│  │  │  all completed + quality ok    │                         │    │
│  │  └────────────────────────────────┘                         │    │
│  │         │                                                   │    │
│  │         ▼  (repeat for next wave)                           │    │
│  │                                                             │    │
│  │  ┌─── GATE 3: final_review() ───┐                          │    │
│  │  │  SHIP_IT (≥85)               │                          │    │
│  │  │  REVISE  (60-84)             │                          │    │
│  │  │  RETHINK (<60)               │                          │    │
│  │  └───────────────────────────────┘                          │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                            ▼                                        │
│                    ExecutionResult                                   │
│           (waves, verdicts, stats, artifacts)                       │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Intent (any format)
  → _extract_intent_fields() → {id, tags, complexity, phase}
  → assign_profile() → profile string
  → compute_waves() → [[intents per wave]]
  → generate_staffing_plan() → {waves, costs, profiles}
  → WaveExecutor.execute_plan() → ExecutionResult
     ├── per intent: Backend → IntentResult → validate_intent()
     ├── per wave: validate_wave()
     └── final: final_review() → ReviewVerdict
```

## Modules

Three modules form the pipeline:

```
staffing_engine.py    assign_profile → compute_waves → generate_staffing_plan
quality_gates.py      validate_intent → validate_wave → final_review
wave_executor.py      WaveExecutor.execute_plan (ties it all together)
```

---

## `staffing_engine` module

### `assign_profile(intent) → str`

Map an intent to an agent profile name.

**Input**: Any of three intent formats:
- `feature_decomposer.Intent` dataclass (has `.tags`, `.depends`, `.title`)
- `agent_decomposer.Intent` dataclass (has `.dependencies`, no `.tags`)
- Plain `dict` from `github_tickets` (has `"phase"`, `"depends"`, `"ticket_id"`)

**Output**: One of the `PROFILES` strings.

**Decision order** (first match wins):

| Priority | Matching keywords | Profile assigned |
|----------|-------------------|------------------|
| 1 | `verify` | `code-ace-reviewer` |
| 2 | `reproduce`, `diagnose`, `fix`, `root-cause`, `hotfix` | `bug-hunter` |
| 3 | `test`, `testing`, `unit`, `integration`, `regression` | `testing-guru` (or `tenacious-unit-tester` if complexity is `trivial`/`simple`) |
| 4 | `docs`, `document`, `api-docs`, `user-guide`, `documentation` | `docs-logs-wizard` |
| 5 | `analysis`, `analyze`, `requirements`, `research`, `design` | `task-predator` |
| 6 | complexity = `epic` | `task-predator` |
| 7 | `implement`, `backend`, `frontend`, `refactor`, etc. | `feature-trailblazer` |
| 8 | (fallback) | `feature-trailblazer` |

Tags are extracted from `.tags` and `.phase`. Hyphenated tags are split into parts for matching (e.g., `"root-cause"` matches both `"root-cause"` and `"root"`, `"cause"`).

```python
from quantum_routing.staffing_engine import assign_profile

# Dataclass intent
profile = assign_profile(intent)  # "bug-hunter"

# Dict intent
profile = assign_profile({"id": "fix-1", "tags": ["fix"], "complexity": "simple"})
# "bug-hunter"
```

---

### `compute_waves(intents) → list[list[intent]]`

Partition intents into parallel execution waves using Kahn's algorithm (BFS topological sort by level).

**Input**: Sequence of intents (any format). Dependencies resolved via `.depends`, `.dependencies`, or `dict["depends"]`.

**Output**: List of waves. Each wave is a list of intents that can execute in parallel. Wave 0 has no dependencies; wave N depends only on waves < N.

**Raises**:
- `ValueError` — circular dependency detected (includes cycle path)
- `ValueError` — dependency references a nonexistent intent ID

```python
from quantum_routing.staffing_engine import compute_waves

waves = compute_waves(intents)
# [[intent_A], [intent_B, intent_C], [intent_D]]
#   wave 0       wave 1                wave 2
```

---

### `generate_staffing_plan(intents) → dict`

Produce a full staffing plan combining `assign_profile()` and `compute_waves()` with cost estimates.

**Input**: Sequence of intents (any format).

**Output**: JSON-serializable dict with this schema:

```json
{
  "total_intents": 12,
  "total_waves": 8,
  "peak_parallelism": 3,
  "serial_depth": 8,
  "bottleneck_wave": 2,
  "critical_path": ["bug2-1-reproduce", "bug2-2-profile-performance", ...],
  "total_estimated_cost": 0.0435,
  "total_estimated_tokens": 48500,
  "profile_load": {
    "bug-hunter": 4,
    "feature-trailblazer": 3,
    "testing-guru": 2,
    ...
  },
  "waves": [
    {
      "wave": 0,
      "agents_needed": 1,
      "estimated_cost": 0.0,
      "intents": [
        {
          "id": "bug2-1-reproduce",
          "profile": "bug-hunter",
          "model": "gemini",
          "workflow": "git-pr",
          "complexity": "trivial",
          "estimated_tokens": 500,
          "estimated_cost": 0.0025,
          "depends_on": [],
          "wave": 0
        }
      ]
    }
  ]
}
```

Cost estimation selects the cheapest model capable of serving each profile (see `PROFILE_AGENT_MODELS` and `TOKEN_RATES`).

---

### Constants

| Name | Type | Description |
|------|------|-------------|
| `PROFILES` | `list[str]` | All 7 valid profile names |
| `PROFILE_AGENT_MODELS` | `dict[str, list[str]]` | Which models can serve each profile |

---

## `quality_gates` module

### Data Classes

#### `IntentResult`

Outcome of executing a single intent:

```python
@dataclass
class IntentResult:
    intent_id: str
    profile: str              # one of PROFILES
    status: str               # "completed", "failed", "in_progress"
    quality_score: float      # 0.0 - 1.0
    tests_passed: bool
    coverage_delta: float     # change in coverage
    artifacts: list[str]      # PR links, branch names, doc paths
    error_message: str | None = None
```

#### `ValidationResult`

Result of Gate 1 or Gate 2:

```python
@dataclass
class ValidationResult:
    passed: bool
    score: float             # 0-100
    issues: list[str]
    recommendations: list[str]
```

#### `ReviewVerdict`

Result of Gate 3:

```python
@dataclass
class ReviewVerdict:
    verdict: Verdict          # SHIP_IT, REVISE, or RETHINK
    score: float              # 0-100
    production_fitness: float  # 0-100
    architecture_score: float  # 0-100
    consumability_score: float # 0-100
    risk_items: list[str]
    feedback: list[str]
```

#### `Verdict` (Enum)

```python
class Verdict(Enum):
    SHIP_IT = "ship_it"    # aggregate score >= 85
    REVISE  = "revise"     # aggregate score 60-84
    RETHINK = "rethink"    # aggregate score < 60
```

---

### `validate_intent(result: IntentResult) → ValidationResult`

**Gate 1: Per-Intent Validation.** Checks profile-specific success criteria.

Each profile has different requirements:

| Profile | Key criteria |
|---------|-------------|
| `bug-hunter` | quality > 0, tests pass, artifacts exist |
| `feature-trailblazer` | quality >= 0.7, tests pass, artifacts exist |
| `testing-guru` | tests pass, coverage_delta >= 0, quality >= 0.7 |
| `tenacious-unit-tester` | coverage_delta > 0, tests pass |
| `docs-logs-wizard` | doc artifact exists (.md/.rst/.txt/.adoc/.html/.pdf), quality >= 0.6 |
| `task-predator` | plan artifact exists (doc with "plan"/"design"/"architecture" etc.), quality >= 0.7 |
| `code-ace-reviewer` | quality >= 0.8 for full pass, >= 0.6 for partial |

Automatically rejects `status="in_progress"` or `status="failed"` with score 0.

---

### `validate_wave(wave_results, min_quality=0.7) → ValidationResult`

**Gate 2: Per-Wave Validation.** Checks that all intents in a wave meet minimum requirements before advancing to the next wave.

Criteria:
- All intents must have `status="completed"`
- All `quality_score` values must meet `min_quality`
- All tests must pass

Score is the average of per-intent Gate 1 scores.

---

### `final_review(all_results) → ReviewVerdict`

**Gate 3: Final Review.** Holistic evaluation across all intents.

Three sub-scores combined with weights:

| Sub-score | Weight | What it measures |
|-----------|--------|-----------------|
| `production_fitness` | 50% | Weighted avg of quality scores, penalizing failed tests |
| `architecture_score` | 30% | Consistency of quality (low stdev = high score) |
| `consumability_score` | 20% | Doc artifact coverage + doc-profile quality |

Verdict thresholds: `SHIP_IT` >= 85, `REVISE` >= 60, `RETHINK` < 60.

---

### `recommend_action(result, attempt) → str`

Escalation ladder for failed or low-quality intents:

| Attempt | Action |
|---------|--------|
| 1 | `"retry_same_agent"` |
| 2 | `"escalate_to_higher_agent"` |
| 3+ | `"flag_for_human_review"` |

---

## `wave_executor` module

### `WaveExecutor`

Orchestrates wave-by-wave execution of a staffing plan.

```python
executor = WaveExecutor(
    backend=SimulatedBackend(),  # or any ExecutionBackend
    max_retries=4,               # attempts per intent before human flag
    max_workers=8,               # thread pool size
    progress_callback=callback,  # optional (event, data) -> None
)
result = executor.execute_plan(staffing_plan)
```

#### `execute_plan(staffing_plan) → ExecutionResult`

Runs all waves sequentially, intents within each wave in parallel. Applies the three quality gates:

1. **Gate 1** after each intent attempt — retry/escalate on failure
2. **Gate 2** after each wave completes
3. **Gate 3** after all waves complete

Returns `ExecutionResult` with all wave results, final verdict, and stats.

#### Progress Events

The `progress_callback` receives these events:

| Event | Data keys |
|-------|-----------|
| `wave_started` | `wave`, `intent_count` |
| `wave_completed` | `wave`, `status`, `score`, `duration` |
| `intent_started` | `intent_id`, `profile`, `model`, `wave` |
| `intent_completed` | `intent_id`, `status`, `score`, `attempt` |
| `intent_retried` | `intent_id`, `attempt`, `model`, `reason` |
| `intent_escalated` | `intent_id`, `from_model`, `to_model`, `attempt` |
| `intent_human_review` | `intent_id`, `attempts`, `last_error` |
| `execution_completed` | `verdict`, `passed`, `failed`, `human_review` |

---

### `ExecutionResult`

```python
@dataclass
class ExecutionResult:
    waves: list[WaveExecution]
    all_results: list[IntentResult]
    final_verdict: ReviewVerdict | None
    total_cost: float
    total_time: float
    passed_count: int
    failed_count: int
    human_review_count: int
```

---

### `SimulatedBackend`

Controllable simulated execution backend for testing and demos.

```python
backend = SimulatedBackend(
    failure_rate=0.15,   # base probability of failure (decreases on retries)
    quality_mean=0.85,   # mean quality score for successes
    quality_std=0.08,    # std deviation
    seed=42,             # random seed for reproducibility
)
```

Implements the `ExecutionBackend` protocol. Generates profile-appropriate artifacts (PRs, test files, docs, review comments).

---

### `ArtifactCollector`

Thread-safe accumulator of artifacts across waves.

```python
collector = ArtifactCollector()
collector.record("intent-1", ["PR #1", "branch-1"])
collector.get_for_intent("intent-1")          # ["PR #1", "branch-1"]
collector.get_for_dependencies(["intent-1"])   # ["PR #1", "branch-1"]
```

---

### `AgentTodoGenerator`

Reads `.claude/agents/{profile}.md` files and generates per-intent todo markdown.

```python
gen = AgentTodoGenerator()
todo_md = gen.generate_todo(
    intent_spec={"id": "fix-1", "profile": "bug-hunter", ...},
    wave_index=0,
    predecessor_artifacts=["PR #99"],
    output_dir="tmp/todos",  # optional: write to disk
)
```

---

## `github_backend` module

Materializes a staffing plan as real GitHub issues following the 4-agent companion pattern.

### Constants

| Name | Type | Description |
|------|------|-------------|
| `COMPANION_AGENTS` | `list[str]` | The 4 companion roles in creation order |
| `AGENT_LABEL_COLORS` | `dict[str, str]` | Hex color for each agent's GitHub label |

### `ensure_agent_labels(repo=None) → dict[str, bool]`

Create GitHub labels for all agent profiles using `gh label create --force`. Idempotent.

**Args**: `repo` — optional `"owner/repo"`. Uses current repo if `None`.

**Returns**: Dict mapping profile name to success bool.

```python
from quantum_routing.github_backend import ensure_agent_labels

results = ensure_agent_labels(repo="octocat/hello")
# {"feature-trailblazer": True, "tenacious-unit-tester": True, ...}
```

---

### `create_companion_issues(parent_issue_number, parent_title, staffing_plan, repo=None) → dict[str, int]`

Create 4 companion issues for a parent GitHub issue:

1. **feature-trailblazer** — implements the feature
2. **tenacious-unit-tester** — writes tests
3. **docs-logs-wizard** — updates documentation
4. **code-ace-reviewer** — final review (blocked by the other 3)

Each issue gets:
- Title: `[Agent: profile] parent_title`
- Label: the agent profile name
- Body: parent link, assigned intents, quality gates checklist
- The reviewer issue body includes dependency links to the other 3

After creating all 4, posts a summary comment on the parent issue.

**Returns**: Dict mapping agent profile to created issue number.

```python
from quantum_routing.github_backend import create_companion_issues

created = create_companion_issues(
    parent_issue_number=20,
    parent_title="Add caching to API layer",
    staffing_plan=plan,
    repo="owner/repo",
)
# {"feature-trailblazer": 21, "tenacious-unit-tester": 22, ...}
```

---

### `post_comment(issue_number, body, repo=None) → bool`

Post a comment on a GitHub issue. Returns `True` on success.

---

### `GitHubProgressReporter`

Progress callback that posts comments on the parent issue at key milestones.

Only fires on `wave_completed` and `execution_completed` events to avoid spamming.

```python
from quantum_routing.github_backend import GitHubProgressReporter

reporter = GitHubProgressReporter(parent_issue_number=20, repo="owner/repo")

# Use as a progress callback
executor = WaveExecutor(progress_callback=reporter)
```

---

## Flask Endpoint: `/api/materialize`

**`POST /api/materialize`**

Decompose a GitHub issue, generate a staffing plan, and create companion issues.

**Request body**:
```json
{
  "issue_number": 13,
  "repo": "owner/repo"  // optional, uses current repo if omitted
}
```

**Response**:
```json
{
  "parent_issue": 13,
  "parent_title": "Wire telemetry into ViolationsDashboard",
  "companion_issues": {
    "feature-trailblazer": 21,
    "tenacious-unit-tester": 22,
    "docs-logs-wizard": 23,
    "code-ace-reviewer": 24
  },
  "labels_created": 7,
  "staffing_plan": {
    "total_intents": 5,
    "total_waves": 3,
    "peak_parallelism": 2,
    "total_estimated_cost": 0.0150
  }
}
```

Also emits a `materialize_completed` WebSocket event with the same payload.
