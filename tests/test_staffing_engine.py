"""Tests for quantum_routing.staffing_engine.

Covers:
    - assign_profile(): tag/phase routing, priority order, input formats
    - compute_waves(): topological ordering, error cases
    - generate_staffing_plan(): structure, cost, serialization
"""

from __future__ import annotations

import json

import pytest

from quantum_routing.feature_decomposer import Intent
from quantum_routing.staffing_engine import (
    PROFILES,
    assign_profile,
    compute_waves,
    generate_staffing_plan,
)


# ═══════════════════════════════════════════════════════════════════════════════
# assign_profile()
# ═══════════════════════════════════════════════════════════════════════════════


class TestAssignProfile:
    """Profile routing based on tags, phase, and complexity."""

    # --- Tag-based routing ---

    def test_bug_tags_route_to_bug_hunter(self):
        for tag in ("fix", "reproduce", "diagnose", "root-cause", "hotfix"):
            intent = {"id": "t", "tags": [tag], "complexity": "moderate"}
            assert assign_profile(intent) == "bug-hunter", f"tag={tag}"

    def test_test_tags_route_to_testing_guru(self):
        for tag in ("test", "testing", "integration", "regression"):
            intent = {"id": "t", "tags": [tag], "complexity": "moderate"}
            assert assign_profile(intent) == "testing-guru", f"tag={tag}"

    def test_simple_test_routes_to_tenacious_unit_tester(self):
        intent = {"id": "t", "tags": ["unit"], "complexity": "simple"}
        assert assign_profile(intent) == "tenacious-unit-tester"

    def test_trivial_test_routes_to_tenacious_unit_tester(self):
        intent = {"id": "t", "tags": ["test"], "complexity": "trivial"}
        assert assign_profile(intent) == "tenacious-unit-tester"

    def test_docs_tags_route_to_docs_wizard(self):
        for tag in ("docs", "document", "api-docs", "user-guide", "documentation"):
            intent = {"id": "t", "tags": [tag], "complexity": "moderate"}
            assert assign_profile(intent) == "docs-logs-wizard", f"tag={tag}"

    def test_planning_tags_route_to_task_predator(self):
        for tag in ("analysis", "analyze", "requirements", "research", "design"):
            intent = {"id": "t", "tags": [tag], "complexity": "moderate"}
            assert assign_profile(intent) == "task-predator", f"tag={tag}"

    def test_impl_tags_route_to_feature_trailblazer(self):
        for tag in ("implement", "backend", "frontend", "refactor"):
            intent = {"id": "t", "tags": [tag], "complexity": "moderate"}
            assert assign_profile(intent) == "feature-trailblazer", f"tag={tag}"

    # --- Phase-based routing (dict with 'phase' key) ---

    def test_verify_phase_routes_to_code_ace_reviewer(self, sample_intent_dict_verify):
        assert assign_profile(sample_intent_dict_verify) == "code-ace-reviewer"

    def test_diagnose_phase_routes_to_bug_hunter(self):
        intent = {"id": "t", "phase": "diagnose", "complexity": "moderate"}
        assert assign_profile(intent) == "bug-hunter"

    # --- Priority order: verify > bug > test > docs > planning > epic > impl ---

    def test_verify_beats_bug(self):
        intent = {"id": "t", "tags": ["verify", "fix"], "complexity": "moderate"}
        assert assign_profile(intent) == "code-ace-reviewer"

    def test_bug_beats_test(self):
        intent = {"id": "t", "tags": ["fix", "test"], "complexity": "moderate"}
        assert assign_profile(intent) == "bug-hunter"

    def test_test_beats_docs(self):
        intent = {"id": "t", "tags": ["test", "docs"], "complexity": "moderate"}
        assert assign_profile(intent) == "testing-guru"

    def test_docs_beats_planning(self):
        intent = {"id": "t", "tags": ["docs", "analysis"], "complexity": "moderate"}
        assert assign_profile(intent) == "docs-logs-wizard"

    # --- Complexity-based routing ---

    def test_epic_complexity_routes_to_task_predator(self):
        intent = {"id": "t", "tags": [], "complexity": "epic"}
        assert assign_profile(intent) == "task-predator"

    def test_unknown_complexity_still_routes(self):
        intent = {"id": "t", "tags": ["implement"], "complexity": "unknown-tier"}
        assert assign_profile(intent) == "feature-trailblazer"

    # --- Fallback ---

    def test_no_tags_fallback_to_feature_trailblazer(self):
        intent = {"id": "t", "tags": [], "complexity": "moderate"}
        assert assign_profile(intent) == "feature-trailblazer"

    def test_empty_intent_fallback(self):
        intent = {"id": "unknown"}
        assert assign_profile(intent) == "feature-trailblazer"

    # --- Input formats ---

    def test_dataclass_intent(self, sample_intent_dataclass):
        profile = assign_profile(sample_intent_dataclass)
        assert profile == "feature-trailblazer"

    def test_dataclass_bug_intent(self, sample_intent_dataclass_bug):
        profile = assign_profile(sample_intent_dataclass_bug)
        assert profile == "bug-hunter"

    def test_dict_intent(self, sample_intent_dict):
        profile = assign_profile(sample_intent_dict)
        assert profile == "task-predator"  # "analysis" tag

    def test_all_profiles_reachable(self, slider_bug_intents, collab_intents):
        """Every profile should be assigned to at least one intent across both DAGs."""
        all_intents = slider_bug_intents + collab_intents
        assigned_profiles = {assign_profile(i) for i in all_intents}
        for p in PROFILES:
            assert p in assigned_profiles, f"Profile {p} never assigned"


# ═══════════════════════════════════════════════════════════════════════════════
# compute_waves()
# ═══════════════════════════════════════════════════════════════════════════════


class TestComputeWaves:
    """Topological wave decomposition."""

    def test_slider_bug_wave_count(self, slider_bug_intents):
        waves = compute_waves(slider_bug_intents)
        assert len(waves) == 8

    def test_collab_wave_count(self, collab_intents):
        waves = compute_waves(collab_intents)
        assert len(waves) > 0
        # All 25 intents accounted for
        total = sum(len(w) for w in waves)
        assert total == 25

    def test_single_intent_no_deps(self):
        intent = {"id": "solo", "depends": []}
        waves = compute_waves([intent])
        assert len(waves) == 1
        assert len(waves[0]) == 1

    def test_all_independent(self):
        intents = [{"id": f"i{i}", "depends": []} for i in range(5)]
        waves = compute_waves(intents)
        assert len(waves) == 1
        assert len(waves[0]) == 5

    def test_linear_chain(self):
        intents = [
            {"id": "A", "depends": []},
            {"id": "B", "depends": ["A"]},
            {"id": "C", "depends": ["B"]},
            {"id": "D", "depends": ["C"]},
        ]
        waves = compute_waves(intents)
        assert len(waves) == 4
        for wave in waves:
            assert len(wave) == 1

    def test_diamond_pattern(self):
        intents = [
            {"id": "A", "depends": []},
            {"id": "B", "depends": ["A"]},
            {"id": "C", "depends": ["A"]},
            {"id": "D", "depends": ["B", "C"]},
        ]
        waves = compute_waves(intents)
        assert len(waves) == 3
        assert len(waves[0]) == 1  # A
        assert len(waves[1]) == 2  # B, C
        assert len(waves[2]) == 1  # D

    def test_circular_dependency_raises(self):
        intents = [
            {"id": "A", "depends": ["B"]},
            {"id": "B", "depends": ["A"]},
        ]
        with pytest.raises(ValueError, match="Circular dependency"):
            compute_waves(intents)

    def test_missing_dependency_raises(self):
        intents = [
            {"id": "A", "depends": ["nonexistent"]},
        ]
        with pytest.raises(ValueError, match="does not exist"):
            compute_waves(intents)

    def test_empty_input(self):
        waves = compute_waves([])
        assert waves == []

    def test_dataclass_intents(self, slider_bug_intents):
        """compute_waves works with dataclass Intent objects."""
        waves = compute_waves(slider_bug_intents)
        # First wave should have the root intent (no deps)
        root_ids = {i.id for i in waves[0]}
        assert "bug2-1-reproduce" in root_ids


# ═══════════════════════════════════════════════════════════════════════════════
# generate_staffing_plan()
# ═══════════════════════════════════════════════════════════════════════════════


class TestGenerateStaffingPlan:
    """Full staffing plan generation."""

    def test_slider_bug_plan_structure(self, slider_bug_intents):
        plan = generate_staffing_plan(slider_bug_intents)
        assert plan["total_intents"] == 12
        assert plan["total_waves"] == 8
        assert "peak_parallelism" in plan
        assert "critical_path" in plan
        assert "waves" in plan
        assert len(plan["waves"]) == 8

    def test_collab_plan_structure(self, collab_intents):
        plan = generate_staffing_plan(collab_intents)
        assert plan["total_intents"] == 25
        assert plan["total_waves"] > 0

    def test_cost_estimates_positive(self, slider_bug_intents):
        plan = generate_staffing_plan(slider_bug_intents)
        assert plan["total_estimated_cost"] >= 0
        for wave in plan["waves"]:
            assert wave["estimated_cost"] >= 0
            for intent in wave["intents"]:
                assert intent["estimated_cost"] >= 0

    def test_peak_parallelism(self, slider_bug_intents):
        plan = generate_staffing_plan(slider_bug_intents)
        max_wave_size = max(len(w["intents"]) for w in plan["waves"])
        assert plan["peak_parallelism"] == max_wave_size

    def test_profile_load_sums_to_total(self, slider_bug_intents):
        plan = generate_staffing_plan(slider_bug_intents)
        total_from_profiles = sum(plan["profile_load"].values())
        assert total_from_profiles == plan["total_intents"]

    def test_wave_intent_required_keys(self, slider_bug_intents):
        plan = generate_staffing_plan(slider_bug_intents)
        required_keys = {
            "id", "profile", "model", "complexity",
            "estimated_tokens", "estimated_cost", "depends_on",
        }
        for wave in plan["waves"]:
            for intent in wave["intents"]:
                assert required_keys <= set(intent.keys()), (
                    f"Missing keys in intent {intent['id']}: "
                    f"{required_keys - set(intent.keys())}"
                )

    def test_empty_input(self):
        plan = generate_staffing_plan([])
        assert plan["total_intents"] == 0
        assert plan["total_waves"] == 0
        assert plan["waves"] == []

    def test_json_serializable(self, slider_bug_intents):
        plan = generate_staffing_plan(slider_bug_intents)
        serialized = json.dumps(plan)
        assert isinstance(serialized, str)
        roundtrip = json.loads(serialized)
        assert roundtrip["total_intents"] == 12
