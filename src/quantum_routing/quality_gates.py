"""Quality Gates -- three-level validation for agent-produced intent results.

Enforces quality at three checkpoints in the agent execution pipeline:

    Gate 1: Per-Intent Validation   validate_intent(result)
    Gate 2: Per-Wave Validation     validate_wave(wave_results, min_quality)
    Gate 3: Final Review            final_review(all_results)

Also provides retry/escalation recommendations for failed intents.

See plans/agent-team-decomposer-ops.md (Part 5) for the design rationale.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Profiles (re-exported from staffing_engine for self-contained usage)
# ---------------------------------------------------------------------------

PROFILES = [
    "bug-hunter",
    "feature-trailblazer",
    "testing-guru",
    "tenacious-unit-tester",
    "docs-logs-wizard",
    "task-predator",
    "code-ace-reviewer",
]

# File extensions that count as documentation artifacts
_DOC_EXTENSIONS = frozenset([
    ".md", ".rst", ".txt", ".adoc", ".html", ".pdf",
])

# File extensions / path fragments that count as plan/design artifacts
_PLAN_KEYWORDS = frozenset([
    "plan", "design", "architecture", "roadmap", "rfc", "spec",
])


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class IntentResult:
    """Outcome of a single intent execution by an agent."""

    intent_id: str
    profile: str              # one of PROFILES
    status: str               # "completed", "failed", "in_progress"
    quality_score: float      # 0.0 - 1.0
    tests_passed: bool
    coverage_delta: float     # change in coverage (can be 0 for non-test intents)
    artifacts: List[str]      # PR links, branch names, doc paths
    error_message: Optional[str] = None


class Verdict(Enum):
    """Final review outcome."""

    SHIP_IT = "ship_it"    # aggregate score >= 85
    REVISE = "revise"      # aggregate score 60-84
    RETHINK = "rethink"    # aggregate score < 60


@dataclass
class ValidationResult:
    """Result of a single gate check (Gate 1 or Gate 2)."""

    passed: bool
    score: float             # 0-100
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class ReviewVerdict:
    """Result of the final Gate 3 review."""

    verdict: Verdict
    score: float              # 0-100
    production_fitness: float  # 0-100
    architecture_score: float  # 0-100
    consumability_score: float # 0-100
    risk_items: List[str] = field(default_factory=list)
    feedback: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helper: artifact classification
# ---------------------------------------------------------------------------

def _has_doc_artifact(artifacts: List[str]) -> bool:
    """Return True if at least one artifact looks like a documentation file."""
    for artifact in artifacts:
        lower = artifact.lower()
        for ext in _DOC_EXTENSIONS:
            if lower.endswith(ext):
                return True
    return False


def _has_plan_artifact(artifacts: List[str]) -> bool:
    """Return True if at least one artifact looks like a plan/design document."""
    for artifact in artifacts:
        lower = artifact.lower()
        # Must be a doc-like file AND contain a plan-related keyword
        is_doc = any(lower.endswith(ext) for ext in _DOC_EXTENSIONS)
        has_keyword = any(kw in lower for kw in _PLAN_KEYWORDS)
        if is_doc and has_keyword:
            return True
    return False


# ---------------------------------------------------------------------------
# Gate 1: Per-Intent Validation
# ---------------------------------------------------------------------------

def _validate_bug_hunter(result: IntentResult) -> ValidationResult:
    """Bug-hunter: bug no longer reproduces, regression test exists."""
    issues: List[str] = []
    score = 0.0

    # Bug should no longer reproduce -- quality_score > 0 indicates successful fix
    if result.quality_score > 0:
        score += 40.0
    else:
        issues.append("Bug appears to still reproduce (quality_score is 0)")

    # Regression test must exist and pass
    if result.tests_passed:
        score += 40.0
    else:
        issues.append("Regression tests did not pass or were not created")

    # Status must be completed
    if result.status == "completed":
        score += 10.0
    else:
        issues.append(f"Intent status is '{result.status}', expected 'completed'")

    # Artifacts should include a PR or branch
    if result.artifacts:
        score += 10.0
    else:
        issues.append("No artifacts produced (expected PR link or branch name)")

    passed = len(issues) == 0
    return ValidationResult(passed=passed, score=score, issues=issues)


def _validate_feature_trailblazer(result: IntentResult) -> ValidationResult:
    """Feature-trailblazer: code compiles (tests pass), quality meets floor."""
    issues: List[str] = []
    score = 0.0

    # Code compiles / basic tests pass
    if result.tests_passed:
        score += 35.0
    else:
        issues.append("Tests did not pass (code may not compile or have errors)")

    # Quality meets a reasonable floor (0.7 for implementation work)
    quality_floor = 0.7
    if result.quality_score >= quality_floor:
        # Scale 0-35 based on quality above the floor
        quality_bonus = min(1.0, (result.quality_score - quality_floor) / (1.0 - quality_floor))
        score += 25.0 + (10.0 * quality_bonus)
    else:
        issues.append(
            f"Quality score {result.quality_score:.2f} below floor {quality_floor}"
        )

    # Status
    if result.status == "completed":
        score += 15.0
    else:
        issues.append(f"Intent status is '{result.status}', expected 'completed'")

    # Artifacts
    if result.artifacts:
        score += 15.0
    else:
        issues.append("No artifacts produced (expected PR link or branch name)")

    passed = len(issues) == 0
    return ValidationResult(passed=passed, score=score, issues=issues)


def _validate_testing_guru(result: IntentResult) -> ValidationResult:
    """Testing-guru: all tests pass, coverage target met."""
    issues: List[str] = []
    score = 0.0

    # All tests must pass
    if result.tests_passed:
        score += 40.0
    else:
        issues.append("Not all tests passed")

    # Coverage target met (coverage_delta >= 0 means at least no regression)
    if result.coverage_delta >= 0:
        score += 30.0
        # Bonus for positive coverage improvement
        if result.coverage_delta > 0:
            coverage_bonus = min(10.0, result.coverage_delta * 100.0)
            score += coverage_bonus
    else:
        issues.append(
            f"Coverage decreased by {abs(result.coverage_delta):.2%}"
        )

    # Quality score
    if result.quality_score >= 0.7:
        score += 10.0
    else:
        issues.append(
            f"Quality score {result.quality_score:.2f} below 0.70 threshold"
        )

    # Status
    if result.status == "completed":
        score += 10.0
    else:
        issues.append(f"Intent status is '{result.status}', expected 'completed'")

    passed = len(issues) == 0
    return ValidationResult(passed=passed, score=min(100.0, score), issues=issues)


def _validate_tenacious_unit_tester(result: IntentResult) -> ValidationResult:
    """Tenacious-unit-tester: coverage_delta > 0, tests pass."""
    issues: List[str] = []
    score = 0.0

    # Coverage must increase
    if result.coverage_delta > 0:
        score += 40.0
        # Bonus proportional to coverage gain
        coverage_bonus = min(10.0, result.coverage_delta * 200.0)
        score += coverage_bonus
    else:
        issues.append(
            f"Coverage did not increase (delta: {result.coverage_delta:+.2%})"
        )

    # Tests must pass
    if result.tests_passed:
        score += 30.0
    else:
        issues.append("Tests did not pass")

    # Status
    if result.status == "completed":
        score += 10.0
    else:
        issues.append(f"Intent status is '{result.status}', expected 'completed'")

    # Artifacts
    if result.artifacts:
        score += 10.0
    else:
        issues.append("No artifacts produced")

    passed = len(issues) == 0
    return ValidationResult(passed=passed, score=min(100.0, score), issues=issues)


def _validate_docs_logs_wizard(result: IntentResult) -> ValidationResult:
    """Docs-logs-wizard: artifacts include at least one doc file."""
    issues: List[str] = []
    score = 0.0

    # Must have at least one documentation artifact
    if _has_doc_artifact(result.artifacts):
        score += 40.0
    else:
        issues.append(
            "No documentation artifact found (expected .md, .rst, .txt, .adoc, .html, or .pdf)"
        )

    # Quality
    if result.quality_score >= 0.6:
        quality_bonus = min(25.0, result.quality_score * 25.0)
        score += quality_bonus
    else:
        issues.append(
            f"Quality score {result.quality_score:.2f} below 0.60 threshold"
        )

    # Status
    if result.status == "completed":
        score += 15.0
    else:
        issues.append(f"Intent status is '{result.status}', expected 'completed'")

    # General artifacts (PR links, branches, etc.)
    if result.artifacts:
        score += 10.0

    # Tests (docs examples should be verified if possible)
    if result.tests_passed:
        score += 10.0

    passed = len(issues) == 0
    return ValidationResult(passed=passed, score=min(100.0, score), issues=issues)


def _validate_task_predator(result: IntentResult) -> ValidationResult:
    """Task-predator: artifacts include a plan/design doc."""
    issues: List[str] = []
    score = 0.0

    # Must produce a plan/design document
    if _has_plan_artifact(result.artifacts):
        score += 40.0
    else:
        issues.append(
            "No plan/design artifact found "
            "(expected a doc file with 'plan', 'design', 'architecture', "
            "'roadmap', 'rfc', or 'spec' in the name)"
        )

    # Quality reflects plan completeness
    if result.quality_score >= 0.7:
        quality_bonus = min(25.0, result.quality_score * 25.0)
        score += quality_bonus
    else:
        issues.append(
            f"Quality score {result.quality_score:.2f} below 0.70 threshold"
        )

    # Status
    if result.status == "completed":
        score += 15.0
    else:
        issues.append(f"Intent status is '{result.status}', expected 'completed'")

    # Any artifacts at all
    if result.artifacts:
        score += 10.0

    # Tests (plan validation)
    if result.tests_passed:
        score += 10.0

    passed = len(issues) == 0
    return ValidationResult(passed=passed, score=min(100.0, score), issues=issues)


def _validate_code_ace_reviewer(result: IntentResult) -> ValidationResult:
    """Code-ace-reviewer: quality_score reflects review completeness."""
    issues: List[str] = []
    score = 0.0

    # Quality score is the primary metric for review completeness
    if result.quality_score >= 0.8:
        score += 50.0
    elif result.quality_score >= 0.6:
        score += 30.0
        issues.append(
            f"Review quality {result.quality_score:.2f} is acceptable but could be more thorough"
        )
    else:
        issues.append(
            f"Review quality {result.quality_score:.2f} is insufficient (below 0.60)"
        )

    # Status
    if result.status == "completed":
        score += 20.0
    else:
        issues.append(f"Intent status is '{result.status}', expected 'completed'")

    # Artifacts (review comments, PR review link, etc.)
    if result.artifacts:
        score += 20.0
    else:
        issues.append("No review artifacts produced (expected PR review link or comments)")

    # Tests are not primary for reviewers, but passing is a bonus
    if result.tests_passed:
        score += 10.0

    passed = len(issues) == 0
    return ValidationResult(passed=passed, score=min(100.0, score), issues=issues)


# Profile validator dispatch table
_PROFILE_VALIDATORS: Dict[str, type(lambda: None)] = {
    "bug-hunter": _validate_bug_hunter,
    "feature-trailblazer": _validate_feature_trailblazer,
    "testing-guru": _validate_testing_guru,
    "tenacious-unit-tester": _validate_tenacious_unit_tester,
    "docs-logs-wizard": _validate_docs_logs_wizard,
    "task-predator": _validate_task_predator,
    "code-ace-reviewer": _validate_code_ace_reviewer,
}


def validate_intent(result: IntentResult) -> ValidationResult:
    """Gate 1: Per-Intent Validation.

    Checks profile-specific success criteria for a single intent result.
    Each profile has different requirements -- a bug-hunter must show the
    bug no longer reproduces, a testing-guru must show all tests pass with
    coverage targets met, etc.

    Args:
        result: The outcome of executing a single intent.

    Returns:
        ValidationResult with pass/fail, score (0-100), issues, and
        recommendations.
    """
    # Basic validation: reject obviously invalid results
    if result.status == "in_progress":
        return ValidationResult(
            passed=False,
            score=0.0,
            issues=["Intent is still in progress -- cannot validate"],
            recommendations=["Wait for intent execution to complete"],
        )

    if result.status == "failed":
        issues = [f"Intent failed: {result.error_message or 'no error message provided'}"]
        recommendations = [recommend_action(result, attempt=1)]
        return ValidationResult(
            passed=False,
            score=0.0,
            issues=issues,
            recommendations=recommendations,
        )

    # Dispatch to profile-specific validator
    validator = _PROFILE_VALIDATORS.get(result.profile)
    if validator is None:
        return ValidationResult(
            passed=False,
            score=0.0,
            issues=[f"Unknown profile '{result.profile}'"],
            recommendations=[f"Valid profiles: {', '.join(PROFILES)}"],
        )

    validation = validator(result)

    # Add recommendations for any issues found
    if not validation.passed:
        for issue in validation.issues:
            if "tests" in issue.lower():
                validation.recommendations.append(
                    "Fix failing tests before marking intent as completed"
                )
            elif "coverage" in issue.lower():
                validation.recommendations.append(
                    "Add more tests to improve coverage delta"
                )
            elif "quality" in issue.lower():
                validation.recommendations.append(
                    "Improve implementation quality or request review feedback"
                )
            elif "artifact" in issue.lower() or "doc" in issue.lower() or "plan" in issue.lower():
                validation.recommendations.append(
                    "Ensure all required deliverables are produced and listed in artifacts"
                )

    return validation


# ---------------------------------------------------------------------------
# Gate 2: Per-Wave Validation
# ---------------------------------------------------------------------------

def validate_wave(
    wave_results: List[IntentResult],
    min_quality: float = 0.7,
) -> ValidationResult:
    """Gate 2: Per-Wave Validation.

    Checks that all intents in a wave meet minimum requirements before
    the orchestrator advances to the next wave.

    Criteria:
        - All intents must have status "completed"
        - All quality scores must meet min_quality
        - All tests must pass

    Args:
        wave_results: List of IntentResult for every intent in the wave.
        min_quality: Minimum quality score required (0.0-1.0, default 0.7).

    Returns:
        Aggregate ValidationResult with per-intent issues and
        recommendations for failed intents (retry, escalate).
    """
    if not wave_results:
        return ValidationResult(
            passed=True,
            score=100.0,
            issues=[],
            recommendations=["Wave is empty -- nothing to validate"],
        )

    issues: List[str] = []
    recommendations: List[str] = []
    intent_scores: List[float] = []

    for result in wave_results:
        # Check completion status
        if result.status != "completed":
            issues.append(
                f"[{result.intent_id}] status is '{result.status}', "
                f"expected 'completed'"
            )
            if result.status == "failed":
                action = recommend_action(result, attempt=1)
                recommendations.append(
                    f"[{result.intent_id}] {action}"
                )
            elif result.status == "in_progress":
                recommendations.append(
                    f"[{result.intent_id}] Wait for execution to finish"
                )

        # Check quality threshold
        if result.quality_score < min_quality:
            issues.append(
                f"[{result.intent_id}] quality_score {result.quality_score:.2f} "
                f"below minimum {min_quality:.2f}"
            )
            recommendations.append(
                f"[{result.intent_id}] Retry with same agent or escalate "
                f"to higher-quality agent"
            )

        # Check tests
        if not result.tests_passed:
            issues.append(
                f"[{result.intent_id}] tests did not pass"
            )
            recommendations.append(
                f"[{result.intent_id}] Fix test failures before proceeding"
            )

        # Run per-intent Gate 1 validation and use its score
        intent_validation = validate_intent(result)
        intent_scores.append(intent_validation.score)

    # Aggregate score: average of all per-intent Gate 1 scores
    aggregate_score = statistics.mean(intent_scores) if intent_scores else 0.0

    passed = len(issues) == 0
    return ValidationResult(
        passed=passed,
        score=round(aggregate_score, 2),
        issues=issues,
        recommendations=recommendations,
    )


# ---------------------------------------------------------------------------
# Gate 3: Final Review
# ---------------------------------------------------------------------------

def final_review(all_results: List[IntentResult]) -> ReviewVerdict:
    """Gate 3: Final Review -- holistic evaluation of the entire execution.

    Computes three sub-scores and combines them into an overall verdict:

    - **production_fitness**: Weighted average of quality scores across all
      intents, penalizing any failures.
    - **architecture_score**: Consistency of quality across related intents.
      Low variance = high score (agents maintained consistent quality).
    - **consumability_score**: Fraction of intents that produced
      documentation artifacts, scaled by overall doc quality.

    Verdict thresholds:
        - SHIP_IT:  score >= 85
        - REVISE:   score 60-84
        - RETHINK:  score < 60

    Args:
        all_results: Every IntentResult from all waves combined.

    Returns:
        ReviewVerdict with verdict, scores, risk items, and actionable
        feedback for REVISE cases.
    """
    if not all_results:
        return ReviewVerdict(
            verdict=Verdict.RETHINK,
            score=0.0,
            production_fitness=0.0,
            architecture_score=0.0,
            consumability_score=0.0,
            risk_items=["No results to review"],
            feedback=["Execute at least one intent before requesting final review"],
        )

    risk_items: List[str] = []
    feedback: List[str] = []

    # --- Production Fitness ---
    # Weighted average: completed intents count fully, failed intents
    # contribute 0 to the numerator but still count in the denominator.
    quality_scores: List[float] = []
    for r in all_results:
        if r.status == "completed":
            quality_scores.append(r.quality_score)
        else:
            quality_scores.append(0.0)
            risk_items.append(
                f"Intent '{r.intent_id}' has status '{r.status}'"
                + (f": {r.error_message}" if r.error_message else "")
            )

    production_fitness = (statistics.mean(quality_scores) * 100.0) if quality_scores else 0.0

    # Penalize if any tests failed among completed intents
    completed_results = [r for r in all_results if r.status == "completed"]
    failed_test_count = sum(1 for r in completed_results if not r.tests_passed)
    if failed_test_count > 0:
        penalty = min(20.0, failed_test_count * 5.0)
        production_fitness = max(0.0, production_fitness - penalty)
        risk_items.append(
            f"{failed_test_count} completed intent(s) have failing tests"
        )
        feedback.append("Fix all failing tests before shipping")

    production_fitness = min(100.0, production_fitness)

    # --- Architecture Score ---
    # Measures consistency: if all quality scores are close together,
    # the architecture is coherent. High variance signals uneven quality.
    if len(quality_scores) >= 2:
        stdev = statistics.stdev(quality_scores)
        # Map stdev to a score: stdev=0 -> 100, stdev>=0.3 -> 0
        architecture_score = max(0.0, 100.0 * (1.0 - stdev / 0.3))
    else:
        architecture_score = quality_scores[0] * 100.0 if quality_scores else 0.0

    # Flag any notably low-quality intents that drag down architecture score
    low_quality_intents = [
        r for r in all_results
        if r.quality_score < 0.5 and r.status == "completed"
    ]
    if low_quality_intents:
        for r in low_quality_intents:
            risk_items.append(
                f"Intent '{r.intent_id}' has low quality score ({r.quality_score:.2f})"
            )
        feedback.append(
            "Improve quality of low-scoring intents for architectural consistency"
        )

    architecture_score = min(100.0, architecture_score)

    # --- Consumability Score ---
    # Fraction of intents with doc artifacts, weighted by doc-profile quality.
    doc_profiles = {"docs-logs-wizard", "task-predator"}
    total = len(all_results)
    doc_count = sum(1 for r in all_results if _has_doc_artifact(r.artifacts))
    doc_fraction = doc_count / total if total > 0 else 0.0

    # Doc-profile quality bonus: how well did the doc-specific agents perform?
    doc_results = [r for r in all_results if r.profile in doc_profiles]
    if doc_results:
        doc_quality_avg = statistics.mean(r.quality_score for r in doc_results)
    else:
        doc_quality_avg = 0.5  # neutral if no doc-specific agents

    # Consumability = 60% doc coverage + 40% doc quality
    consumability_score = (doc_fraction * 60.0 + doc_quality_avg * 40.0)

    if doc_fraction < 0.1:
        risk_items.append(
            f"Only {doc_count}/{total} intents produced documentation artifacts"
        )
        feedback.append("Add documentation for key intents to improve consumability")

    consumability_score = min(100.0, consumability_score)

    # --- Aggregate Score ---
    # Weighted combination: production fitness is most important
    aggregate_score = (
        production_fitness * 0.50
        + architecture_score * 0.30
        + consumability_score * 0.20
    )
    aggregate_score = round(aggregate_score, 2)

    # --- Verdict ---
    if aggregate_score >= 85.0:
        verdict = Verdict.SHIP_IT
    elif aggregate_score >= 60.0:
        verdict = Verdict.REVISE
        if not feedback:
            feedback.append(
                "Score is close to SHIP_IT threshold -- address risk items to improve"
            )
    else:
        verdict = Verdict.RETHINK
        feedback.append(
            "Score is below 60 -- consider whether the decomposition itself "
            "needs to be revised before re-executing"
        )

    return ReviewVerdict(
        verdict=verdict,
        score=aggregate_score,
        production_fitness=round(production_fitness, 2),
        architecture_score=round(architecture_score, 2),
        consumability_score=round(consumability_score, 2),
        risk_items=risk_items,
        feedback=feedback,
    )


# ---------------------------------------------------------------------------
# Retry / Escalation Logic
# ---------------------------------------------------------------------------

def recommend_action(result: IntentResult, attempt: int) -> str:
    """Recommend a recovery action for a failed or low-quality intent.

    Escalation ladder:
        attempt 1  -> "retry_same_agent"
        attempt 2  -> "escalate_to_higher_agent"
        attempt 3+ -> "flag_for_human_review"

    Args:
        result: The IntentResult that needs remediation.
        attempt: Which attempt number this is (1-based).

    Returns:
        One of the three action strings.
    """
    if attempt <= 0:
        attempt = 1

    if attempt == 1:
        return "retry_same_agent"
    elif attempt == 2:
        return "escalate_to_higher_agent"
    else:
        return "flag_for_human_review"


# ---------------------------------------------------------------------------
# CLI demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 72)
    print("  QUALITY GATES DEMO")
    print("=" * 72)

    # --- Sample IntentResults ---

    sample_results: List[IntentResult] = [
        # Wave 0: task-predator produces a design doc
        IntentResult(
            intent_id="collab-1-analyze-requirements",
            profile="task-predator",
            status="completed",
            quality_score=0.92,
            tests_passed=True,
            coverage_delta=0.0,
            artifacts=["docs/design/collab-architecture-plan.md", "main...feature/collab"],
        ),
        # Wave 1: bug-hunter fixes a bug
        IntentResult(
            intent_id="bug-42-slider-freeze",
            profile="bug-hunter",
            status="completed",
            quality_score=0.88,
            tests_passed=True,
            coverage_delta=0.02,
            artifacts=["PR #101", "feature/fix-slider-freeze"],
        ),
        # Wave 2: feature-trailblazer implements core feature
        IntentResult(
            intent_id="collab-5-session-manager",
            profile="feature-trailblazer",
            status="completed",
            quality_score=0.85,
            tests_passed=True,
            coverage_delta=0.05,
            artifacts=["PR #102", "feature/session-manager"],
        ),
        # Wave 2: feature-trailblazer -- lower quality
        IntentResult(
            intent_id="collab-11-websocket-client",
            profile="feature-trailblazer",
            status="completed",
            quality_score=0.72,
            tests_passed=True,
            coverage_delta=0.01,
            artifacts=["PR #103", "feature/ws-client"],
        ),
        # Wave 3: testing-guru writes tests
        IntentResult(
            intent_id="collab-18-unit-tests-backend",
            profile="testing-guru",
            status="completed",
            quality_score=0.95,
            tests_passed=True,
            coverage_delta=0.12,
            artifacts=["PR #110", "feature/backend-tests"],
        ),
        # Wave 3: tenacious-unit-tester
        IntentResult(
            intent_id="collab-19-unit-tests-frontend",
            profile="tenacious-unit-tester",
            status="completed",
            quality_score=0.80,
            tests_passed=True,
            coverage_delta=0.08,
            artifacts=["PR #111", "feature/frontend-tests"],
        ),
        # Wave 4: docs-logs-wizard writes docs
        IntentResult(
            intent_id="collab-22-api-docs",
            profile="docs-logs-wizard",
            status="completed",
            quality_score=0.90,
            tests_passed=True,
            coverage_delta=0.0,
            artifacts=["docs/api/collab-api.md", "PR #115"],
        ),
        # Wave 5: code-ace-reviewer reviews
        IntentResult(
            intent_id="collab-25-final-review",
            profile="code-ace-reviewer",
            status="completed",
            quality_score=0.88,
            tests_passed=True,
            coverage_delta=0.0,
            artifacts=["PR #120 review", "review-comments.md"],
        ),
        # A failed intent for demo purposes
        IntentResult(
            intent_id="collab-9-conflict-resolution",
            profile="feature-trailblazer",
            status="failed",
            quality_score=0.0,
            tests_passed=False,
            coverage_delta=0.0,
            artifacts=[],
            error_message="Merge conflict in state_sync.py could not be auto-resolved",
        ),
    ]

    # -----------------------------------------------------------------------
    # Gate 1: Per-Intent Validation
    # -----------------------------------------------------------------------
    print("\n" + "-" * 72)
    print("  GATE 1: Per-Intent Validation")
    print("-" * 72)

    for result in sample_results:
        validation = validate_intent(result)
        status_marker = "PASS" if validation.passed else "FAIL"
        print(
            f"\n  [{status_marker}] {result.intent_id} "
            f"({result.profile}) -- score: {validation.score:.1f}/100"
        )
        if validation.issues:
            for issue in validation.issues:
                print(f"         issue: {issue}")
        if validation.recommendations:
            for rec in validation.recommendations:
                print(f"         recommendation: {rec}")

    # -----------------------------------------------------------------------
    # Gate 2: Per-Wave Validation (demo with wave of 3 intents)
    # -----------------------------------------------------------------------
    print("\n" + "-" * 72)
    print("  GATE 2: Per-Wave Validation")
    print("-" * 72)

    # Wave A: all passing
    wave_a = [sample_results[0], sample_results[1], sample_results[2]]
    wave_a_result = validate_wave(wave_a, min_quality=0.7)
    print(f"\n  Wave A (3 intents, all good):")
    print(f"    passed: {wave_a_result.passed}  score: {wave_a_result.score:.1f}/100")
    if wave_a_result.issues:
        for issue in wave_a_result.issues:
            print(f"    issue: {issue}")

    # Wave B: includes a failed intent
    wave_b = [sample_results[3], sample_results[8]]  # one low-quality, one failed
    wave_b_result = validate_wave(wave_b, min_quality=0.7)
    print(f"\n  Wave B (2 intents, one failed):")
    print(f"    passed: {wave_b_result.passed}  score: {wave_b_result.score:.1f}/100")
    if wave_b_result.issues:
        for issue in wave_b_result.issues:
            print(f"    issue: {issue}")
    if wave_b_result.recommendations:
        for rec in wave_b_result.recommendations:
            print(f"    recommendation: {rec}")

    # -----------------------------------------------------------------------
    # Gate 3: Final Review
    # -----------------------------------------------------------------------
    print("\n" + "-" * 72)
    print("  GATE 3: Final Review")
    print("-" * 72)

    # Review all results (including the failed one)
    review = final_review(sample_results)
    print(f"\n  Verdict:            {review.verdict.value}")
    print(f"  Aggregate Score:    {review.score:.1f}/100")
    print(f"  Production Fitness: {review.production_fitness:.1f}/100")
    print(f"  Architecture Score: {review.architecture_score:.1f}/100")
    print(f"  Consumability:      {review.consumability_score:.1f}/100")

    if review.risk_items:
        print("\n  Risk items:")
        for item in review.risk_items:
            print(f"    - {item}")

    if review.feedback:
        print("\n  Feedback:")
        for fb in review.feedback:
            print(f"    - {fb}")

    # -----------------------------------------------------------------------
    # Review without the failed intent (should be SHIP_IT)
    # -----------------------------------------------------------------------
    print("\n" + "-" * 72)
    print("  GATE 3: Final Review (without failed intent)")
    print("-" * 72)

    passing_results = [r for r in sample_results if r.status == "completed"]
    review_clean = final_review(passing_results)
    print(f"\n  Verdict:            {review_clean.verdict.value}")
    print(f"  Aggregate Score:    {review_clean.score:.1f}/100")
    print(f"  Production Fitness: {review_clean.production_fitness:.1f}/100")
    print(f"  Architecture Score: {review_clean.architecture_score:.1f}/100")
    print(f"  Consumability:      {review_clean.consumability_score:.1f}/100")

    if review_clean.risk_items:
        print("\n  Risk items:")
        for item in review_clean.risk_items:
            print(f"    - {item}")

    if review_clean.feedback:
        print("\n  Feedback:")
        for fb in review_clean.feedback:
            print(f"    - {fb}")

    # -----------------------------------------------------------------------
    # Retry / Escalation demo
    # -----------------------------------------------------------------------
    print("\n" + "-" * 72)
    print("  RETRY / ESCALATION LOGIC")
    print("-" * 72)

    failed_result = sample_results[8]
    for attempt in range(1, 5):
        action = recommend_action(failed_result, attempt)
        print(f"  Attempt {attempt}: {action}")

    print("\n" + "=" * 72)
    print("  DEMO COMPLETE")
    print("=" * 72)
