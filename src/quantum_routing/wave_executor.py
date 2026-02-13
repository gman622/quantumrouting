"""Wave Executor -- orchestrates agent execution wave-by-wave.

Takes a staffing plan (from generate_staffing_plan) and executes it:
  - Runs waves sequentially, intents within each wave in parallel
  - Validates quality gates at each checkpoint (per-intent, per-wave, final)
  - Handles failures with retry -> escalate -> human-flag ladder
  - Generates agent todo markdown per intent
  - Collects artifacts across waves

Usage:
    python -m quantum_routing.wave_executor

See plans/agent-team-decomposer-ops.md (Part 6) for the design rationale.
"""

from __future__ import annotations

import os
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple

from quantum_routing.quality_gates import (
    IntentResult,
    ReviewVerdict,
    ValidationResult,
    Verdict,
    final_review,
    recommend_action,
    validate_intent,
    validate_wave,
)
from quantum_routing.staffing_engine import (
    PROFILE_AGENT_MODELS,
    TOKEN_RATES,
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ExecutionContext:
    """Everything a backend needs to execute a single intent."""

    intent_id: str
    profile: str
    model: str
    wave: int
    attempt: int
    predecessor_artifacts: List[str]
    todo_md: str
    timeout: float = 120.0


@dataclass
class IntentExecution:
    """Tracks one intent across retries."""

    intent_id: str
    profile: str
    model: str
    attempts: List[IntentResult] = field(default_factory=list)
    final_result: Optional[IntentResult] = None
    validation: Optional[ValidationResult] = None
    status: str = "pending"  # pending, passed, failed, human_review


@dataclass
class WaveExecution:
    """Tracks one wave of parallel intent executions."""

    wave_index: int
    intent_executions: Dict[str, IntentExecution] = field(default_factory=dict)
    wave_validation: Optional[ValidationResult] = None
    start_time: float = 0.0
    end_time: float = 0.0
    status: str = "pending"  # pending, running, passed, failed


@dataclass
class ExecutionResult:
    """Final output of a complete plan execution."""

    waves: List[WaveExecution] = field(default_factory=list)
    all_results: List[IntentResult] = field(default_factory=list)
    final_verdict: Optional[ReviewVerdict] = None
    total_cost: float = 0.0
    total_time: float = 0.0
    passed_count: int = 0
    failed_count: int = 0
    human_review_count: int = 0


class ExecutionBackend(Protocol):
    """Protocol for pluggable execution backends."""

    def execute_intent(
        self, intent_spec: Dict[str, Any], context: ExecutionContext
    ) -> IntentResult: ...


# ---------------------------------------------------------------------------
# ArtifactCollector
# ---------------------------------------------------------------------------

class ArtifactCollector:
    """Thread-safe accumulator of artifacts across waves."""

    def __init__(self) -> None:
        self._artifacts: Dict[str, List[str]] = {}
        self._lock = threading.Lock()

    def record(self, intent_id: str, artifacts: List[str]) -> None:
        with self._lock:
            self._artifacts.setdefault(intent_id, []).extend(artifacts)

    def get_for_intent(self, intent_id: str) -> List[str]:
        with self._lock:
            return list(self._artifacts.get(intent_id, []))

    def get_for_dependencies(self, dep_ids: List[str]) -> List[str]:
        with self._lock:
            result: List[str] = []
            for dep_id in dep_ids:
                result.extend(self._artifacts.get(dep_id, []))
            return result

    def collect_wave_artifacts(self, wave_exec: WaveExecution) -> Dict[str, List[str]]:
        with self._lock:
            return {
                iid: list(self._artifacts.get(iid, []))
                for iid in wave_exec.intent_executions
            }


# ---------------------------------------------------------------------------
# AgentTodoGenerator
# ---------------------------------------------------------------------------

class AgentTodoGenerator:
    """Reads .claude/agents/{profile}.md and generates per-intent todo markdown."""

    def __init__(self, agents_dir: Optional[str] = None) -> None:
        if agents_dir is None:
            # Walk up from this file to find .claude/agents/
            repo_root = Path(__file__).resolve().parent.parent.parent
            agents_dir = str(repo_root / ".claude" / "agents")
        self._agents_dir = Path(agents_dir)
        self._profiles: Dict[str, Dict[str, str]] = {}
        self._load_profiles()

    def _load_profiles(self) -> None:
        for md_file in self._agents_dir.glob("*.md"):
            profile_name = md_file.stem
            content = md_file.read_text()
            self._profiles[profile_name] = self._parse_sections(content)

    @staticmethod
    def _parse_sections(content: str) -> Dict[str, str]:
        """Extract Mission, Workflow, Quality Gates sections from markdown."""
        sections: Dict[str, str] = {}
        current_section: Optional[str] = None
        current_lines: List[str] = []

        for line in content.splitlines():
            heading_match = re.match(r'^##\s+(.+)', line)
            if heading_match:
                if current_section is not None:
                    sections[current_section] = "\n".join(current_lines).strip()
                current_section = heading_match.group(1).strip()
                current_lines = []
            elif current_section is not None:
                current_lines.append(line)

        if current_section is not None:
            sections[current_section] = "\n".join(current_lines).strip()

        return sections

    def generate_todo(
        self,
        intent_spec: Dict[str, Any],
        wave_index: int,
        predecessor_artifacts: List[str],
        output_dir: Optional[str] = None,
    ) -> str:
        """Generate agent-todo.md content for an intent.

        Args:
            intent_spec: Intent dict from staffing plan wave.
            wave_index: Which wave this intent belongs to.
            predecessor_artifacts: Artifacts from dependency intents.
            output_dir: If set, write the todo to disk.

        Returns:
            The generated markdown string.
        """
        profile = intent_spec["profile"]
        sections = self._profiles.get(profile, {})

        mission = sections.get("Mission", "Execute the assigned intent.")
        workflow = sections.get("Workflow: git-pr", "Follow standard git-pr workflow.")
        quality_gates = sections.get("Quality Gates", "Verify all tests pass.")

        lines = [
            f"# Agent Todo: {intent_spec['id']}",
            "",
            f"**Profile:** {profile}",
            f"**Model:** {intent_spec['model']}",
            f"**Wave:** {wave_index}",
            f"**Complexity:** {intent_spec['complexity']}",
            "",
            "## Mission",
            "",
            mission,
            "",
            "## Task",
            "",
            f"Execute intent `{intent_spec['id']}` as part of wave {wave_index}.",
        ]

        if intent_spec.get("depends_on"):
            lines.append("")
            lines.append("**Dependencies:** " + ", ".join(intent_spec["depends_on"]))

        if predecessor_artifacts:
            lines.append("")
            lines.append("## Predecessor Artifacts")
            lines.append("")
            for art in predecessor_artifacts:
                lines.append(f"- {art}")

        lines.extend([
            "",
            "## Workflow",
            "",
            workflow,
            "",
            "## Quality Gates Checklist",
            "",
            quality_gates,
        ])

        todo_md = "\n".join(lines) + "\n"

        if output_dir:
            out_path = Path(output_dir) / f"{intent_spec['id']}-todo.md"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(todo_md)

        return todo_md


# ---------------------------------------------------------------------------
# SimulatedBackend
# ---------------------------------------------------------------------------

# Profile-appropriate artifact templates
_ARTIFACT_TEMPLATES: Dict[str, List[str]] = {
    "bug-hunter": ["PR #{pr}", "fix/{id}", "tests/regression/{id}_test.py"],
    "feature-trailblazer": ["PR #{pr}", "feature/{id}", "src/{id}.py"],
    "testing-guru": ["PR #{pr}", "tests/{id}_test.py", "coverage-report.html"],
    "tenacious-unit-tester": ["PR #{pr}", "tests/unit/{id}_test.py"],
    "docs-logs-wizard": ["docs/{id}.md", "PR #{pr}", "docs/api/{id}-reference.md"],
    "task-predator": ["docs/design/{id}-plan.md", "PR #{pr}", "docs/architecture/{id}-rfc.md"],
    "code-ace-reviewer": ["PR #{pr} review", "review-comments/{id}.md"],
}


class SimulatedBackend:
    """Controllable simulated execution backend.

    Args:
        failure_rate: Base probability of failure on first attempt (0.0-1.0).
        quality_mean: Mean quality score for successful executions.
        quality_std: Std deviation of quality scores.
        seed: Random seed for reproducibility.
    """

    def __init__(
        self,
        failure_rate: float = 0.15,
        quality_mean: float = 0.85,
        quality_std: float = 0.08,
        seed: int = 42,
    ) -> None:
        self.failure_rate = failure_rate
        self.quality_mean = quality_mean
        self.quality_std = quality_std
        self._rng = random.Random(seed)
        self._pr_counter = 100

    def execute_intent(
        self, intent_spec: Dict[str, Any], context: ExecutionContext
    ) -> IntentResult:
        # Failure rate decreases on retries (simulates real retry success)
        effective_failure_rate = self.failure_rate / context.attempt

        if self._rng.random() < effective_failure_rate:
            return IntentResult(
                intent_id=context.intent_id,
                profile=context.profile,
                status="failed",
                quality_score=0.0,
                tests_passed=False,
                coverage_delta=0.0,
                artifacts=[],
                error_message=self._random_error(context.profile),
            )

        # Successful execution
        quality = max(0.0, min(1.0, self._rng.gauss(
            self.quality_mean, self.quality_std
        )))

        # Higher-quality models produce slightly better results
        model_bonus = TOKEN_RATES.get(context.model, 0) * 1000
        quality = min(1.0, quality + model_bonus)

        self._pr_counter += 1
        pr_num = self._pr_counter

        templates = _ARTIFACT_TEMPLATES.get(context.profile, ["PR #{pr}"])
        artifacts = [
            t.format(pr=pr_num, id=context.intent_id)
            for t in templates
        ]

        coverage_delta = 0.0
        if context.profile in ("testing-guru", "tenacious-unit-tester"):
            coverage_delta = max(0.01, self._rng.gauss(0.05, 0.02))
        elif context.profile == "bug-hunter":
            coverage_delta = max(0.0, self._rng.gauss(0.02, 0.01))

        # Simulate execution time
        time.sleep(self._rng.uniform(0.01, 0.05))

        return IntentResult(
            intent_id=context.intent_id,
            profile=context.profile,
            status="completed",
            quality_score=round(quality, 4),
            tests_passed=True,
            coverage_delta=round(coverage_delta, 4),
            artifacts=artifacts,
        )

    def _random_error(self, profile: str) -> str:
        errors = {
            "bug-hunter": [
                "Could not reproduce bug in test environment",
                "Regression test timeout after 30s",
            ],
            "feature-trailblazer": [
                "Build failed: type mismatch in interface",
                "Integration test failure in dependent module",
            ],
            "testing-guru": [
                "Flaky test detected: non-deterministic ordering",
                "Coverage tool segfault on large file",
            ],
            "tenacious-unit-tester": [
                "Mock setup error: unexpected call sequence",
                "Assertion error in edge case test",
            ],
            "docs-logs-wizard": [
                "Markdown lint errors in generated docs",
                "Broken internal links in API reference",
            ],
            "task-predator": [
                "Plan validation failed: circular dependency in proposed architecture",
                "Missing requirements traceability",
            ],
            "code-ace-reviewer": [
                "Review blocked: PR has merge conflicts",
                "Static analysis found critical issues",
            ],
        }
        pool = errors.get(profile, ["Unexpected execution error"])
        return self._rng.choice(pool)


# ---------------------------------------------------------------------------
# WaveExecutor
# ---------------------------------------------------------------------------

def _next_higher_model(profile: str, current_model: str) -> str:
    """Pick the next-higher-quality model from PROFILE_AGENT_MODELS."""
    models = PROFILE_AGENT_MODELS.get(profile, [])
    # Sort by token rate (proxy for quality) descending
    sorted_models = sorted(models, key=lambda m: TOKEN_RATES.get(m, 0), reverse=True)

    found = False
    for m in reversed(sorted_models):
        if found:
            return m  # return the one above current
        if m == current_model:
            found = True

    # If current is already the best or not found, return the best available
    return sorted_models[0] if sorted_models else current_model


ProgressCallback = Callable[[str, Dict[str, Any]], None]


class WaveExecutor:
    """Orchestrates wave-by-wave execution of a staffing plan.

    Args:
        backend: Execution backend (default: SimulatedBackend).
        max_retries: Maximum attempts per intent before human flag (default 4).
        max_workers: Thread pool size for parallel intent execution.
        progress_callback: Optional callback for progress events.
    """

    def __init__(
        self,
        backend: Optional[ExecutionBackend] = None,
        max_retries: int = 4,
        max_workers: int = 8,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> None:
        self.backend = backend or SimulatedBackend()
        self.max_retries = max_retries
        self.max_workers = max_workers
        self.progress_callback = progress_callback
        self.artifacts = ArtifactCollector()
        self.todo_generator = AgentTodoGenerator()

    def _emit(self, event: str, data: Dict[str, Any]) -> None:
        if self.progress_callback:
            self.progress_callback(event, data)

    def execute_plan(self, staffing_plan: Dict[str, Any]) -> ExecutionResult:
        """Execute a full staffing plan wave-by-wave.

        Args:
            staffing_plan: Output of generate_staffing_plan().

        Returns:
            ExecutionResult with all wave results, final verdict, and stats.
        """
        result = ExecutionResult()
        plan_start = time.time()

        for wave_plan in staffing_plan["waves"]:
            wave_exec = self._execute_wave(wave_plan)
            result.waves.append(wave_exec)

            # Collect results from this wave
            for ie in wave_exec.intent_executions.values():
                if ie.final_result:
                    result.all_results.append(ie.final_result)

        # Gate 3: Final review
        result.final_verdict = final_review(result.all_results)

        # Tally stats
        result.total_time = time.time() - plan_start

        # Build token/model lookup from the staffing plan
        intent_specs: Dict[str, Dict[str, Any]] = {}
        for wp in staffing_plan["waves"]:
            for ispec in wp["intents"]:
                intent_specs[ispec["id"]] = ispec

        for ie_result in result.all_results:
            spec = intent_specs.get(ie_result.intent_id, {})
            tokens = spec.get("estimated_tokens", 0)
            model = spec.get("model", "gemini")
            rate = TOKEN_RATES.get(model, 0.000005)
            result.total_cost += tokens * rate

            if ie_result.status == "completed":
                result.passed_count += 1
            else:
                result.failed_count += 1

        # Count human reviews
        for wave_exec in result.waves:
            for ie in wave_exec.intent_executions.values():
                if ie.status == "human_review":
                    result.human_review_count += 1

        self._emit("execution_completed", {
            "verdict": result.final_verdict.verdict.value if result.final_verdict else "unknown",
            "passed": result.passed_count,
            "failed": result.failed_count,
            "human_review": result.human_review_count,
        })

        return result

    def _execute_wave(self, wave_plan: Dict[str, Any]) -> WaveExecution:
        """Execute all intents in a wave in parallel."""
        wave_index = wave_plan["wave"]
        wave_exec = WaveExecution(wave_index=wave_index)
        wave_exec.start_time = time.time()
        wave_exec.status = "running"

        self._emit("wave_started", {
            "wave": wave_index,
            "intent_count": len(wave_plan["intents"]),
        })

        # Execute intents in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {}
            for intent_spec in wave_plan["intents"]:
                future = pool.submit(
                    self._execute_intent_with_retries,
                    intent_spec, wave_index,
                )
                futures[future] = intent_spec["id"]

            for future in as_completed(futures):
                intent_id = futures[future]
                ie = future.result()
                wave_exec.intent_executions[intent_id] = ie

        # Gate 2: Wave validation
        wave_results = [
            ie.final_result
            for ie in wave_exec.intent_executions.values()
            if ie.final_result
        ]
        wave_exec.wave_validation = validate_wave(wave_results)
        wave_exec.end_time = time.time()
        wave_exec.status = "passed" if wave_exec.wave_validation.passed else "failed"

        self._emit("wave_completed", {
            "wave": wave_index,
            "status": wave_exec.status,
            "score": wave_exec.wave_validation.score,
            "duration": round(wave_exec.end_time - wave_exec.start_time, 3),
        })

        return wave_exec

    def _execute_intent_with_retries(
        self, intent_spec: Dict[str, Any], wave_index: int,
    ) -> IntentExecution:
        """Execute a single intent with retry/escalation ladder."""
        intent_id = intent_spec["id"]
        profile = intent_spec["profile"]
        current_model = intent_spec["model"]

        ie = IntentExecution(
            intent_id=intent_id,
            profile=profile,
            model=current_model,
        )

        self._emit("intent_started", {
            "intent_id": intent_id,
            "profile": profile,
            "model": current_model,
            "wave": wave_index,
        })

        for attempt in range(1, self.max_retries + 1):
            # Generate todo markdown
            pred_artifacts = self.artifacts.get_for_dependencies(
                intent_spec.get("depends_on", [])
            )
            todo_md = self.todo_generator.generate_todo(
                intent_spec, wave_index, pred_artifacts,
            )

            context = ExecutionContext(
                intent_id=intent_id,
                profile=profile,
                model=current_model,
                wave=wave_index,
                attempt=attempt,
                predecessor_artifacts=pred_artifacts,
                todo_md=todo_md,
            )

            # Execute via backend
            result = self.backend.execute_intent(intent_spec, context)
            ie.attempts.append(result)

            # Gate 1: Per-intent validation
            validation = validate_intent(result)

            if validation.passed:
                ie.final_result = result
                ie.validation = validation
                ie.status = "passed"
                self.artifacts.record(intent_id, result.artifacts)

                self._emit("intent_completed", {
                    "intent_id": intent_id,
                    "status": "passed",
                    "score": validation.score,
                    "attempt": attempt,
                })
                return ie

            # Validation failed -- decide next action
            if attempt >= self.max_retries:
                break

            action = recommend_action(result, attempt)

            if action == "retry_same_agent":
                self._emit("intent_retried", {
                    "intent_id": intent_id,
                    "attempt": attempt + 1,
                    "model": current_model,
                    "reason": validation.issues[0] if validation.issues else "validation failed",
                })

            elif action == "escalate_to_higher_agent":
                new_model = _next_higher_model(profile, current_model)
                self._emit("intent_escalated", {
                    "intent_id": intent_id,
                    "from_model": current_model,
                    "to_model": new_model,
                    "attempt": attempt + 1,
                })
                current_model = new_model

            else:  # flag_for_human_review
                break

        # All retries exhausted or flagged for human review
        ie.final_result = ie.attempts[-1] if ie.attempts else None
        ie.validation = validate_intent(ie.final_result) if ie.final_result else None
        ie.status = "human_review"

        if ie.final_result:
            self.artifacts.record(intent_id, ie.final_result.artifacts)

        self._emit("intent_human_review", {
            "intent_id": intent_id,
            "attempts": len(ie.attempts),
            "last_error": ie.final_result.error_message if ie.final_result else "no result",
        })

        return ie


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _cli_progress(event: str, data: Dict[str, Any]) -> None:
    """Pretty-print progress events to stdout."""
    indent = "    "
    if event == "wave_started":
        print(f"\n  {'='*64}")
        print(f"  WAVE {data['wave']} ({data['intent_count']} intent"
              f"{'s' if data['intent_count'] != 1 else ''})")
        print(f"  {'='*64}")
    elif event == "wave_completed":
        status = "PASS" if data["status"] == "passed" else "FAIL"
        print(f"\n  {indent}Wave {data['wave']} [{status}] "
              f"score={data['score']:.1f}  "
              f"duration={data['duration']:.3f}s")
    elif event == "intent_started":
        print(f"  {indent}[start] {data['intent_id']} "
              f"({data['profile']} / {data['model']})")
    elif event == "intent_completed":
        marker = "PASS" if data["status"] == "passed" else "FAIL"
        retry_note = f" (attempt {data['attempt']})" if data["attempt"] > 1 else ""
        print(f"  {indent}[{marker}]  {data['intent_id']}  "
              f"score={data['score']:.1f}{retry_note}")
    elif event == "intent_retried":
        print(f"  {indent}[retry] {data['intent_id']} -> "
              f"attempt {data['attempt']} ({data['model']}): "
              f"{data['reason']}")
    elif event == "intent_escalated":
        print(f"  {indent}[escalate] {data['intent_id']} "
              f"{data['from_model']} -> {data['to_model']} "
              f"(attempt {data['attempt']})")
    elif event == "intent_human_review":
        print(f"  {indent}[HUMAN] {data['intent_id']} "
              f"after {data['attempts']} attempts: {data['last_error']}")
    elif event == "execution_completed":
        print(f"\n  {'='*64}")
        print(f"  EXECUTION COMPLETE")
        print(f"  {'='*64}")
        print(f"  {indent}Verdict: {data['verdict']}")
        print(f"  {indent}Passed:  {data['passed']}  "
              f"Failed: {data['failed']}  "
              f"Human review: {data['human_review']}")


def _run_demo() -> None:
    """Original slider-bug demo (default when no args)."""
    from quantum_routing.feature_decomposer import decompose_slider_bug
    from quantum_routing.staffing_engine import generate_staffing_plan

    print("=" * 72)
    print("  WAVE EXECUTOR -- Simulated Execution of Slider Bug Fix")
    print("=" * 72)

    intents = decompose_slider_bug()
    print(f"\n  Decomposed into {len(intents)} intents")

    plan = generate_staffing_plan(intents)
    print(f"  Staffing plan: {plan['total_waves']} waves, "
          f"peak parallelism {plan['peak_parallelism']}, "
          f"est. cost ${plan['total_estimated_cost']:.4f}")

    _execute_and_report(plan)


def _run_github(
    issue_number: Optional[int] = None,
    use_template: bool = False,
    repo: Optional[str] = None,
    materialize: bool = False,
) -> None:
    """Fetch GitHub issues, decompose, staff, execute."""
    from quantum_routing.github_tickets import (
        decompose_ticket,
        decompose_ticket_smart,
        import_all_issues,
        import_issue,
    )
    from quantum_routing.staffing_engine import generate_staffing_plan

    decompose = decompose_ticket if use_template else decompose_ticket_smart
    mode = "template" if use_template else "LLM (template fallback)"

    print("=" * 72)
    print(f"  WAVE EXECUTOR -- GitHub Issues ({mode})")
    if repo:
        print(f"  Repo: {repo}")
    print("=" * 72)

    # Fetch tickets
    if issue_number is not None:
        ticket = import_issue(issue_number, repo=repo)
        if ticket is None:
            print(f"\n  Error: could not fetch issue #{issue_number}")
            return
        tickets = [ticket]
    else:
        tickets = import_all_issues(state="open", repo=repo)
        if not tickets:
            print("\n  No open issues found (or gh CLI not configured)")
            return

    print(f"\n  Found {len(tickets)} issue{'s' if len(tickets) != 1 else ''}")

    # Decompose all tickets into intents
    all_intents: List[Dict[str, Any]] = []
    for ticket in tickets:
        intents = decompose(ticket)
        source = intents[0].get("_source", "template") if intents else "template"
        print(f"  #{ticket.id}: {ticket.title}  "
              f"-> {len(intents)} intents ({source})")
        all_intents.extend(intents)

    if not all_intents:
        print("\n  No intents generated")
        return

    print(f"\n  Total: {len(all_intents)} intents from {len(tickets)} issues")

    # Staff
    plan = generate_staffing_plan(all_intents)
    print(f"  Staffing plan: {plan['total_waves']} waves, "
          f"peak parallelism {plan['peak_parallelism']}, "
          f"est. cost ${plan['total_estimated_cost']:.4f}")

    # Materialize companion issues on GitHub
    if materialize and issue_number is not None:
        from quantum_routing.github_backend import (
            GitHubProgressReporter,
            create_companion_issues,
            ensure_agent_labels,
        )

        print(f"\n  Materializing companion issues...")
        label_results = ensure_agent_labels(repo=repo)
        print(f"  Labels: {sum(label_results.values())}/{len(label_results)} created")

        parent_title = tickets[0].title
        created = create_companion_issues(
            parent_issue_number=issue_number,
            parent_title=parent_title,
            staffing_plan=plan,
            repo=repo,
        )
        for agent, num in created.items():
            print(f"  Created #{num} [{agent}]")

        # Chain progress reporters: CLI + GitHub
        gh_reporter = GitHubProgressReporter(issue_number, repo=repo)

        def _combined_progress(event: str, data: Dict[str, Any]) -> None:
            _cli_progress(event, data)
            gh_reporter(event, data)

        _execute_and_report(plan, progress_callback=_combined_progress)
    else:
        _execute_and_report(plan)


def _execute_and_report(
    plan: Dict[str, Any],
    progress_callback: Optional[ProgressCallback] = None,
) -> None:
    """Shared execution + reporting logic."""
    executor = WaveExecutor(
        backend=SimulatedBackend(failure_rate=0.15, seed=42),
        progress_callback=progress_callback or _cli_progress,
    )
    result = executor.execute_plan(plan)

    print(f"\n{'='*72}")
    print("  FINAL REPORT")
    print(f"{'='*72}")
    print(f"  Total time:      {result.total_time:.3f}s")
    print(f"  Intents passed:  {result.passed_count}")
    print(f"  Intents failed:  {result.failed_count}")
    print(f"  Human review:    {result.human_review_count}")
    print(f"  Total attempts:  {sum(len(ie.attempts) for w in result.waves for ie in w.intent_executions.values())}")

    if result.final_verdict:
        v = result.final_verdict
        print(f"\n  Gate 3 Verdict:       {v.verdict.value}")
        print(f"  Aggregate Score:      {v.score:.1f}/100")
        print(f"  Production Fitness:   {v.production_fitness:.1f}/100")
        print(f"  Architecture Score:   {v.architecture_score:.1f}/100")
        print(f"  Consumability:        {v.consumability_score:.1f}/100")

        if v.risk_items:
            print(f"\n  Risk items:")
            for item in v.risk_items:
                print(f"    - {item}")

        if v.feedback:
            print(f"\n  Feedback:")
            for fb in v.feedback:
                print(f"    - {fb}")

    # Sample todo from first wave
    if plan["waves"]:
        print(f"\n{'='*72}")
        print("  SAMPLE AGENT TODO (first intent)")
        print(f"{'='*72}")
        first_intent = plan["waves"][0]["intents"][0]
        sample_todo = executor.todo_generator.generate_todo(
            first_intent, wave_index=0, predecessor_artifacts=[],
        )
        for line in sample_todo.splitlines():
            print(f"  {line}")

    print(f"\n{'='*72}")
    print("  DONE")
    print(f"{'='*72}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Wave Executor — orchestrate agent execution of intent plans",
    )
    parser.add_argument(
        "--github", action="store_true",
        help="Fetch open GitHub issues, decompose, staff, and execute",
    )
    parser.add_argument(
        "--issue", type=int, default=None, metavar="N",
        help="Target a single GitHub issue number (requires --github)",
    )
    parser.add_argument(
        "--template", action="store_true",
        help="Force template-only decomposition, skip LLM (with --github)",
    )
    parser.add_argument(
        "--repo", type=str, default=None, metavar="OWNER/REPO",
        help="Target a specific GitHub repo (implies --github)",
    )
    parser.add_argument(
        "--materialize", action="store_true",
        help="Create real companion issues on GitHub (requires --issue)",
    )
    args = parser.parse_args()

    if args.repo or args.github or args.issue is not None:
        _run_github(
            issue_number=args.issue,
            use_template=args.template,
            repo=args.repo,
            materialize=args.materialize,
        )
    else:
        _run_demo()
