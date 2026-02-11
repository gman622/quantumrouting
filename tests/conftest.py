"""Shared fixtures for staffing engine tests."""

from __future__ import annotations

import pytest

from quantum_routing.feature_decomposer import (
    Intent,
    decompose_realtime_collab_feature,
    decompose_slider_bug,
)
from quantum_routing.quality_gates import IntentResult


# ---------------------------------------------------------------------------
# Intent fixtures — dataclass format (feature_decomposer.Intent)
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_intent_dataclass():
    """A single feature_decomposer.Intent with tags."""
    return Intent(
        id="test-intent-1",
        title="Test intent",
        description="A test intent for unit tests",
        complexity="moderate",
        min_quality=0.75,
        depends=[],
        estimated_tokens=5000,
        tags=["implement", "backend"],
    )


@pytest.fixture
def sample_intent_dataclass_bug():
    """A bug-tagged dataclass intent."""
    return Intent(
        id="test-bug-1",
        title="Fix login crash",
        description="Fix the crash on login",
        complexity="simple",
        min_quality=0.6,
        depends=[],
        estimated_tokens=1500,
        tags=["fix", "hotfix"],
    )


# ---------------------------------------------------------------------------
# Intent fixtures — dict format (github_tickets style)
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_intent_dict():
    """A plain dict intent (github_tickets.decompose_ticket style)."""
    return {
        "id": "gh-42-1",
        "title": "Analyze the issue",
        "complexity": "moderate",
        "depends": [],
        "tags": ["analysis"],
        "phase": "analyze",
        "estimated_tokens": 3000,
    }


@pytest.fixture
def sample_intent_dict_verify():
    """A dict intent with phase='verify'."""
    return {
        "id": "gh-42-5",
        "title": "Verify the fix",
        "complexity": "trivial",
        "depends": ["gh-42-4"],
        "tags": [],
        "phase": "verify",
        "estimated_tokens": 500,
    }


# ---------------------------------------------------------------------------
# Full DAG fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def slider_bug_intents():
    """Full 12-intent DAG from decompose_slider_bug()."""
    return decompose_slider_bug()


@pytest.fixture
def collab_intents():
    """Full 25-intent DAG from decompose_realtime_collab_feature()."""
    return decompose_realtime_collab_feature()


# ---------------------------------------------------------------------------
# IntentResult factory
# ---------------------------------------------------------------------------


@pytest.fixture
def make_intent_result():
    """Factory fixture for IntentResult with profile-appropriate defaults."""

    _defaults = {
        "bug-hunter": dict(
            quality_score=0.88,
            tests_passed=True,
            coverage_delta=0.02,
            artifacts=["PR #101", "fix/test-bug"],
        ),
        "feature-trailblazer": dict(
            quality_score=0.85,
            tests_passed=True,
            coverage_delta=0.0,
            artifacts=["PR #102", "feature/test-feat"],
        ),
        "testing-guru": dict(
            quality_score=0.90,
            tests_passed=True,
            coverage_delta=0.08,
            artifacts=["PR #103", "tests/test_file.py"],
        ),
        "tenacious-unit-tester": dict(
            quality_score=0.80,
            tests_passed=True,
            coverage_delta=0.05,
            artifacts=["PR #104", "tests/unit/test_unit.py"],
        ),
        "docs-logs-wizard": dict(
            quality_score=0.85,
            tests_passed=True,
            coverage_delta=0.0,
            artifacts=["docs/api.md", "PR #105"],
        ),
        "task-predator": dict(
            quality_score=0.90,
            tests_passed=True,
            coverage_delta=0.0,
            artifacts=["docs/design/plan.md", "PR #106"],
        ),
        "code-ace-reviewer": dict(
            quality_score=0.88,
            tests_passed=True,
            coverage_delta=0.0,
            artifacts=["PR #107 review", "review-comments.md"],
        ),
    }

    def _factory(profile: str, intent_id: str = "test-intent", **overrides):
        defaults = _defaults.get(profile, _defaults["feature-trailblazer"]).copy()
        defaults.update(overrides)
        return IntentResult(
            intent_id=intent_id,
            profile=profile,
            status=defaults.pop("status", "completed"),
            quality_score=defaults.pop("quality_score"),
            tests_passed=defaults.pop("tests_passed"),
            coverage_delta=defaults.pop("coverage_delta"),
            artifacts=defaults.pop("artifacts"),
            error_message=defaults.pop("error_message", None),
        )

    return _factory


@pytest.fixture
def passing_results(make_intent_result):
    """One passing IntentResult per profile."""
    from quantum_routing.quality_gates import PROFILES

    return [
        make_intent_result(profile, intent_id=f"pass-{i}")
        for i, profile in enumerate(PROFILES)
    ]
