"""Tests for quantum_routing.quality_gates.

Covers:
    - validate_intent(): per-profile validation, status edge cases
    - validate_wave(): aggregate validation
    - final_review(): verdict thresholds, subscores
    - recommend_action(): escalation ladder
"""

from __future__ import annotations

import pytest

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


# ═══════════════════════════════════════════════════════════════════════════════
# validate_intent() — Gate 1
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidateIntent:
    """Per-intent validation with profile-specific criteria."""

    # --- Passing results per profile ---

    @pytest.mark.parametrize("profile", [
        "bug-hunter",
        "feature-trailblazer",
        "testing-guru",
        "tenacious-unit-tester",
        "docs-logs-wizard",
        "task-predator",
        "code-ace-reviewer",
    ])
    def test_passing_result(self, make_intent_result, profile):
        result = make_intent_result(profile)
        validation = validate_intent(result)
        assert validation.passed, (
            f"{profile} should pass with good defaults, "
            f"issues: {validation.issues}"
        )
        assert validation.score > 0

    # --- Status edge cases ---

    def test_failed_status_not_passed(self, make_intent_result):
        result = make_intent_result(
            "feature-trailblazer",
            status="failed",
            quality_score=0.0,
            tests_passed=False,
            artifacts=[],
            error_message="Build failed",
        )
        validation = validate_intent(result)
        assert not validation.passed
        assert validation.score == 0.0
        assert any("failed" in i.lower() or "Build failed" in i for i in validation.issues)

    def test_in_progress_not_passed(self, make_intent_result):
        result = make_intent_result(
            "feature-trailblazer",
            status="in_progress",
            quality_score=0.0,
            tests_passed=False,
            artifacts=[],
        )
        validation = validate_intent(result)
        assert not validation.passed
        assert validation.score == 0.0
        assert any("in progress" in i.lower() for i in validation.issues)

    # --- Bug-hunter profile-specific ---

    def test_bug_hunter_tests_failed(self, make_intent_result):
        result = make_intent_result("bug-hunter", tests_passed=False)
        validation = validate_intent(result)
        assert not validation.passed
        assert any("test" in i.lower() for i in validation.issues)

    def test_bug_hunter_zero_quality(self, make_intent_result):
        result = make_intent_result("bug-hunter", quality_score=0.0)
        validation = validate_intent(result)
        assert not validation.passed

    # --- Testing-guru profile-specific ---

    def test_testing_guru_coverage_zero(self, make_intent_result):
        result = make_intent_result("testing-guru", coverage_delta=0.0)
        validation = validate_intent(result)
        # coverage_delta >= 0 still passes, but no bonus
        assert validation.passed
        # Score should be lower than with positive delta
        good = validate_intent(make_intent_result("testing-guru", coverage_delta=0.1))
        assert validation.score <= good.score

    def test_testing_guru_negative_coverage(self, make_intent_result):
        result = make_intent_result("testing-guru", coverage_delta=-0.05)
        validation = validate_intent(result)
        assert not validation.passed
        assert any("coverage" in i.lower() for i in validation.issues)

    # --- Code-ace-reviewer profile-specific ---

    def test_code_ace_reviewer_low_quality_fails(self, make_intent_result):
        result = make_intent_result("code-ace-reviewer", quality_score=0.5)
        validation = validate_intent(result)
        assert not validation.passed
        assert any("quality" in i.lower() or "review" in i.lower()
                    for i in validation.issues)

    def test_code_ace_reviewer_medium_quality_has_issues(self, make_intent_result):
        result = make_intent_result("code-ace-reviewer", quality_score=0.65)
        validation = validate_intent(result)
        # Acceptable but with issues
        assert any("could be more thorough" in i for i in validation.issues)

    # --- Docs-logs-wizard profile-specific ---

    def test_docs_wizard_no_doc_artifact(self, make_intent_result):
        result = make_intent_result(
            "docs-logs-wizard",
            artifacts=["PR #105", "feature/branch"],
        )
        validation = validate_intent(result)
        assert not validation.passed
        assert any("doc" in i.lower() for i in validation.issues)

    # --- Task-predator profile-specific ---

    def test_task_predator_no_plan_artifact(self, make_intent_result):
        result = make_intent_result(
            "task-predator",
            artifacts=["PR #106"],
        )
        validation = validate_intent(result)
        assert not validation.passed
        assert any("plan" in i.lower() or "design" in i.lower()
                    for i in validation.issues)

    # --- Unknown profile ---

    def test_unknown_profile(self):
        result = IntentResult(
            intent_id="test",
            profile="nonexistent-profile",
            status="completed",
            quality_score=0.9,
            tests_passed=True,
            coverage_delta=0.0,
            artifacts=["PR #1"],
        )
        validation = validate_intent(result)
        assert not validation.passed
        assert any("Unknown profile" in i for i in validation.issues)


# ═══════════════════════════════════════════════════════════════════════════════
# validate_wave() — Gate 2
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidateWave:
    """Wave-level validation aggregating per-intent results."""

    def test_all_passing(self, passing_results):
        validation = validate_wave(passing_results)
        assert validation.passed
        assert validation.score > 0

    def test_one_failed_result(self, make_intent_result, passing_results):
        failed = make_intent_result(
            "feature-trailblazer",
            intent_id="bad-intent",
            status="failed",
            quality_score=0.0,
            tests_passed=False,
            artifacts=[],
            error_message="crash",
        )
        results = passing_results + [failed]
        validation = validate_wave(results)
        assert not validation.passed
        assert len(validation.issues) > 0

    def test_empty_results(self):
        validation = validate_wave([])
        assert validation.passed  # empty wave passes vacuously
        assert validation.score == 100.0

    def test_custom_min_quality(self, make_intent_result):
        result = make_intent_result("feature-trailblazer", quality_score=0.6)
        # Default min_quality=0.7 should fail the wave quality check
        v_strict = validate_wave([result], min_quality=0.7)
        assert not v_strict.passed
        assert any("quality" in i.lower() for i in v_strict.issues)
        # Relaxed threshold removes the wave-level quality issue
        v_relaxed = validate_wave([result], min_quality=0.5)
        quality_issues = [i for i in v_relaxed.issues if "quality" in i.lower()]
        assert len(quality_issues) == 0

    def test_low_quality_below_threshold(self, make_intent_result):
        result = make_intent_result("feature-trailblazer", quality_score=0.5)
        validation = validate_wave([result], min_quality=0.7)
        assert not validation.passed
        assert any("quality" in i.lower() for i in validation.issues)


# ═══════════════════════════════════════════════════════════════════════════════
# final_review() — Gate 3
# ═══════════════════════════════════════════════════════════════════════════════


class TestFinalReview:
    """Final holistic review across all intents."""

    def test_all_high_quality_ship_it(self, make_intent_result):
        results = [
            make_intent_result(
                "feature-trailblazer",
                intent_id=f"good-{i}",
                quality_score=0.95,
                artifacts=[f"docs/file{i}.md", f"PR #{i}"],
            )
            for i in range(5)
        ]
        review = final_review(results)
        assert review.verdict == Verdict.SHIP_IT
        assert review.score >= 85.0

    def test_mixed_results_revise(self, make_intent_result):
        results = [
            make_intent_result("feature-trailblazer", intent_id="ok-1",
                               quality_score=0.75),
            make_intent_result("feature-trailblazer", intent_id="ok-2",
                               quality_score=0.70),
            make_intent_result("testing-guru", intent_id="ok-3",
                               quality_score=0.80,
                               coverage_delta=0.05),
        ]
        review = final_review(results)
        assert review.verdict in (Verdict.REVISE, Verdict.SHIP_IT)
        assert review.score >= 60.0

    def test_all_failures_rethink(self, make_intent_result):
        results = [
            make_intent_result(
                "feature-trailblazer",
                intent_id=f"bad-{i}",
                status="failed",
                quality_score=0.0,
                tests_passed=False,
                artifacts=[],
                error_message="crash",
            )
            for i in range(3)
        ]
        review = final_review(results)
        assert review.verdict == Verdict.RETHINK
        assert review.score < 60.0

    def test_single_result_no_stdev_crash(self, make_intent_result):
        result = make_intent_result("feature-trailblazer", intent_id="solo")
        review = final_review([result])
        assert review.verdict in (Verdict.SHIP_IT, Verdict.REVISE, Verdict.RETHINK)
        assert 0 <= review.score <= 100

    def test_empty_results_rethink(self):
        review = final_review([])
        assert review.verdict == Verdict.RETHINK
        assert review.score == 0.0

    def test_subscores_in_range(self, passing_results):
        review = final_review(passing_results)
        assert 0 <= review.production_fitness <= 100
        assert 0 <= review.architecture_score <= 100
        assert 0 <= review.consumability_score <= 100
        assert 0 <= review.score <= 100


# ═══════════════════════════════════════════════════════════════════════════════
# recommend_action()
# ═══════════════════════════════════════════════════════════════════════════════


class TestRecommendAction:
    """Retry/escalation ladder."""

    def test_attempt_1_retry(self, make_intent_result):
        result = make_intent_result(
            "feature-trailblazer",
            status="failed",
            quality_score=0.0,
            tests_passed=False,
            artifacts=[],
        )
        assert recommend_action(result, attempt=1) == "retry_same_agent"

    def test_attempt_2_escalate(self, make_intent_result):
        result = make_intent_result(
            "feature-trailblazer",
            status="failed",
            quality_score=0.0,
            tests_passed=False,
            artifacts=[],
        )
        assert recommend_action(result, attempt=2) == "escalate_to_higher_agent"

    def test_attempt_3_human_review(self, make_intent_result):
        result = make_intent_result(
            "feature-trailblazer",
            status="failed",
            quality_score=0.0,
            tests_passed=False,
            artifacts=[],
        )
        assert recommend_action(result, attempt=3) == "flag_for_human_review"

    def test_attempt_4_still_human_review(self, make_intent_result):
        result = make_intent_result(
            "feature-trailblazer",
            status="failed",
            quality_score=0.0,
            tests_passed=False,
            artifacts=[],
        )
        assert recommend_action(result, attempt=4) == "flag_for_human_review"
