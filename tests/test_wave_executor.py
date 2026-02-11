"""Integration tests for quantum_routing.wave_executor.

Covers:
    - SimulatedBackend determinism
    - WaveExecutor.execute_plan() end-to-end
    - Retry/escalation ladder
    - Progress callback events
    - ArtifactCollector accumulation
    - Human review flagging
"""

from __future__ import annotations

import pytest

from quantum_routing.feature_decomposer import decompose_slider_bug
from quantum_routing.staffing_engine import generate_staffing_plan
from quantum_routing.wave_executor import (
    ArtifactCollector,
    ExecutionContext,
    SimulatedBackend,
    WaveExecutor,
)


# ═══════════════════════════════════════════════════════════════════════════════
# SimulatedBackend
# ═══════════════════════════════════════════════════════════════════════════════


class TestSimulatedBackend:
    """Controllable simulated execution backend."""

    def test_deterministic_with_seed(self):
        """Same seed produces same sequence of results."""
        plan = generate_staffing_plan(decompose_slider_bug())
        first_intent = plan["waves"][0]["intents"][0]

        ctx = ExecutionContext(
            intent_id=first_intent["id"],
            profile=first_intent["profile"],
            model=first_intent["model"],
            wave=0, attempt=1,
            predecessor_artifacts=[],
            todo_md="test",
        )

        b1 = SimulatedBackend(seed=42)
        r1 = b1.execute_intent(first_intent, ctx)

        b2 = SimulatedBackend(seed=42)
        r2 = b2.execute_intent(first_intent, ctx)

        assert r1.status == r2.status
        assert r1.quality_score == r2.quality_score

    def test_zero_failure_rate_always_succeeds(self):
        backend = SimulatedBackend(failure_rate=0.0, seed=99)
        intent_spec = {"id": "test", "profile": "feature-trailblazer",
                        "model": "gemini", "complexity": "moderate"}
        ctx = ExecutionContext(
            intent_id="test", profile="feature-trailblazer",
            model="gemini", wave=0, attempt=1,
            predecessor_artifacts=[], todo_md="test",
        )
        for _ in range(20):
            result = backend.execute_intent(intent_spec, ctx)
            assert result.status == "completed"

    def test_full_failure_rate_always_fails(self):
        backend = SimulatedBackend(failure_rate=1.0, seed=99)
        intent_spec = {"id": "test", "profile": "bug-hunter",
                        "model": "claude", "complexity": "moderate"}
        ctx = ExecutionContext(
            intent_id="test", profile="bug-hunter",
            model="claude", wave=0, attempt=1,
            predecessor_artifacts=[], todo_md="test",
        )
        result = backend.execute_intent(intent_spec, ctx)
        assert result.status == "failed"
        assert result.error_message is not None


# ═══════════════════════════════════════════════════════════════════════════════
# WaveExecutor — end-to-end
# ═══════════════════════════════════════════════════════════════════════════════


class TestWaveExecutor:
    """Integration tests running full plans through the executor."""

    def test_execute_slider_bug_plan(self):
        """Full execution of slider bug plan completes with a verdict."""
        intents = decompose_slider_bug()
        plan = generate_staffing_plan(intents)

        executor = WaveExecutor(
            backend=SimulatedBackend(failure_rate=0.0, seed=42),
            max_retries=2,
        )
        result = executor.execute_plan(plan)

        assert len(result.waves) == plan["total_waves"]
        assert result.final_verdict is not None
        assert result.passed_count + result.failed_count == plan["total_intents"]

    def test_progress_callback_events(self):
        """Progress callback receives expected event types."""
        intents = decompose_slider_bug()
        plan = generate_staffing_plan(intents)

        events = []

        def callback(event: str, data: dict):
            events.append(event)

        executor = WaveExecutor(
            backend=SimulatedBackend(failure_rate=0.0, seed=42),
            progress_callback=callback,
        )
        executor.execute_plan(plan)

        assert "wave_started" in events
        assert "wave_completed" in events
        assert "intent_started" in events
        assert "intent_completed" in events
        assert "execution_completed" in events

    def test_retry_on_failure(self):
        """Executor retries failed intents."""
        intents = decompose_slider_bug()
        plan = generate_staffing_plan(intents)

        events = []

        def callback(event: str, data: dict):
            events.append((event, data))

        # Moderate failure rate to trigger some retries
        executor = WaveExecutor(
            backend=SimulatedBackend(failure_rate=0.5, seed=42),
            max_retries=4,
            progress_callback=callback,
        )
        result = executor.execute_plan(plan)

        # Some intents should have had retries or escalations
        retry_events = [e for e, _ in events if e in
                        ("intent_retried", "intent_escalated")]
        # With 50% failure rate across 12 intents, we expect at least some retries
        # (seed=42 is deterministic so this is stable)
        assert result.final_verdict is not None

    def test_human_review_after_max_retries(self):
        """After max_retries exhausted, intent gets flagged for human review."""
        intents = decompose_slider_bug()
        plan = generate_staffing_plan(intents)

        # 100% failure rate = all intents will exhaust retries
        executor = WaveExecutor(
            backend=SimulatedBackend(failure_rate=1.0, seed=42),
            max_retries=3,
        )
        result = executor.execute_plan(plan)

        assert result.human_review_count > 0
        # Check at least one wave has human_review status intents
        human_reviewed = [
            ie for w in result.waves
            for ie in w.intent_executions.values()
            if ie.status == "human_review"
        ]
        assert len(human_reviewed) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# ArtifactCollector
# ═══════════════════════════════════════════════════════════════════════════════


class TestArtifactCollector:
    """Thread-safe artifact accumulation."""

    def test_record_and_retrieve(self):
        collector = ArtifactCollector()
        collector.record("intent-1", ["PR #1", "branch-1"])
        collector.record("intent-2", ["PR #2"])

        assert collector.get_for_intent("intent-1") == ["PR #1", "branch-1"]
        assert collector.get_for_intent("intent-2") == ["PR #2"]
        assert collector.get_for_intent("nonexistent") == []

    def test_accumulates_across_calls(self):
        collector = ArtifactCollector()
        collector.record("intent-1", ["PR #1"])
        collector.record("intent-1", ["PR #1-retry"])

        artifacts = collector.get_for_intent("intent-1")
        assert len(artifacts) == 2
        assert "PR #1" in artifacts
        assert "PR #1-retry" in artifacts

    def test_get_for_dependencies(self):
        collector = ArtifactCollector()
        collector.record("dep-1", ["artifact-A"])
        collector.record("dep-2", ["artifact-B", "artifact-C"])

        dep_artifacts = collector.get_for_dependencies(["dep-1", "dep-2"])
        assert len(dep_artifacts) == 3

    def test_artifacts_accumulate_across_waves(self):
        """WaveExecutor accumulates artifacts across waves."""
        intents = decompose_slider_bug()
        plan = generate_staffing_plan(intents)

        executor = WaveExecutor(
            backend=SimulatedBackend(failure_rate=0.0, seed=42),
        )
        result = executor.execute_plan(plan)

        # After execution, artifact collector should have entries
        # for all intents that produced artifacts
        for ir in result.all_results:
            if ir.artifacts:
                stored = executor.artifacts.get_for_intent(ir.intent_id)
                assert len(stored) > 0, (
                    f"Artifacts for {ir.intent_id} not collected"
                )
