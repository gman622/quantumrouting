"""Staffing Engine -- maps decomposer output to agent team execution plans.

Three public functions form the pipeline:

    assign_profile(intent)         -> str          # who does this intent?
    compute_waves(intents)         -> [[intent]]   # what order?
    generate_staffing_plan(intents) -> dict         # full execution plan

Accepts intent objects from any of the three decomposers:
  - agent_decomposer.py  (dataclass with .dependencies, no .tags/.phase)
  - feature_decomposer.py (dataclass with .tags, .depends, .title)
  - github_tickets.py     (plain dict with 'phase', 'depends', 'ticket_id')
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Union


# ---------------------------------------------------------------------------
# Agent profiles -- the roles a staffing plan can assign
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


# ---------------------------------------------------------------------------
# Tag / phase keywords that drive profile selection
# ---------------------------------------------------------------------------

_BUG_KEYWORDS = frozenset([
    "reproduce", "diagnose", "fix", "root-cause", "hotfix",
])

_TEST_KEYWORDS = frozenset([
    "test", "testing", "unit", "integration", "regression",
])

_DOCS_KEYWORDS = frozenset([
    "docs", "document", "api-docs", "user-guide", "documentation",
])

_PLANNING_KEYWORDS = frozenset([
    "analysis", "analyze", "requirements", "research", "design",
    "architecture", "plan", "decompose", "prioritize",
])

_IMPL_KEYWORDS = frozenset([
    "implement", "backend", "frontend", "sync", "locking",
    "session", "release", "feature-flag", "polish",
    "error-handling", "refactor",
])

_VERIFY_KEYWORDS = frozenset([
    "verify",
])


# ---------------------------------------------------------------------------
# Normalization helper
# ---------------------------------------------------------------------------

def _extract_intent_fields(intent: Any) -> Dict[str, Any]:
    """Normalize any decomposer output into a uniform dict.

    Returns:
        {
            "id":         str,
            "tags":       list[str],   # merged from .tags and/or .phase
            "complexity": str,
            "phase":      str | None,  # only from github_tickets dicts
        }

    Handles:
        - feature_decomposer.Intent  (has .tags, .depends, .title)
        - agent_decomposer.Intent    (has .dependencies, no .tags)
        - github_tickets dict        (has 'phase', 'ticket_id')
        - any other dict with at least 'id' and 'complexity'
    """
    if isinstance(intent, dict):
        # Plain dict -- github_tickets.decompose_ticket() or similar
        tags = list(intent.get("tags", []))
        phase = intent.get("phase")
        if phase and phase not in tags:
            tags.append(phase)
        return {
            "id": intent.get("id", "unknown"),
            "tags": tags,
            "complexity": intent.get("complexity", "moderate"),
            "phase": phase,
        }

    # Dataclass / object with attributes
    tags: List[str] = []
    if hasattr(intent, "tags"):
        tags = list(getattr(intent, "tags") or [])

    phase: Optional[str] = None
    if hasattr(intent, "phase"):
        phase = getattr(intent, "phase")
        if phase and phase not in tags:
            tags.append(phase)

    # If the intent has a description but no tags/phase, try to infer
    # a coarse tag from the id (e.g. "bug2-5-add-debounce" -> "fix" is
    # already captured by feature_decomposer tags; agent_decomposer has
    # neither, so tags may remain empty -- that is fine, fallback applies).

    return {
        "id": getattr(intent, "id", "unknown"),
        "tags": tags,
        "complexity": getattr(intent, "complexity", "moderate"),
        "phase": phase,
    }


# ---------------------------------------------------------------------------
# Profile assignment
# ---------------------------------------------------------------------------

def assign_profile(intent: Any) -> str:
    """Map an intent (from any decomposer) to an agent profile name.

    Decision order (first match wins):
        1. verify phase at the *end* of a pipeline   -> code-ace-reviewer
        2. bug-related tags/phase                     -> bug-hunter
        3. test-related tags/phase                    -> testing-guru or
                                                        tenacious-unit-tester
        4. docs-related tags/phase                    -> docs-logs-wizard
        5. planning/analysis tags/phase               -> task-predator
        6. epic complexity                            -> task-predator
        7. implementation tags/phase                  -> feature-trailblazer
        8. fallback                                   -> feature-trailblazer

    Args:
        intent: A dataclass instance (from agent_decomposer or
                feature_decomposer) or a plain dict (from github_tickets).

    Returns:
        One of the profile strings defined in PROFILES.
    """
    fields = _extract_intent_fields(intent)
    tags = fields["tags"]
    complexity = fields["complexity"]

    # Build a set of lowercase tokens from tags for fast matching.
    tag_tokens = set()
    for t in tags:
        tag_tokens.add(t.lower())
        # Also split on hyphens so "root-cause" matches both "root-cause"
        # as a unit and its parts if needed.  The keyword sets already
        # contain hyphenated forms so we keep both.
        for part in t.lower().split("-"):
            tag_tokens.add(part)

    # 1. Verify at end of pipeline -> code-ace-reviewer
    #    "verify" as an explicit phase/tag signals a final review step.
    if _VERIFY_KEYWORDS & tag_tokens:
        return "code-ace-reviewer"

    # 2. Bug-related
    if _BUG_KEYWORDS & tag_tokens:
        return "bug-hunter"

    # 3. Test-related -- split by complexity
    if _TEST_KEYWORDS & tag_tokens:
        if complexity in ("trivial", "simple"):
            return "tenacious-unit-tester"
        return "testing-guru"

    # 4. Docs
    if _DOCS_KEYWORDS & tag_tokens:
        return "docs-logs-wizard"

    # 5. Planning / analysis
    if _PLANNING_KEYWORDS & tag_tokens:
        return "task-predator"

    # 6. Epic complexity always needs a planner regardless of tags
    if complexity == "epic":
        return "task-predator"

    # 7. Implementation keywords
    if _IMPL_KEYWORDS & tag_tokens:
        return "feature-trailblazer"

    # 8. Fallback
    return "feature-trailblazer"


# ---------------------------------------------------------------------------
# Dependency helpers (shared by compute_waves and generate_staffing_plan)
# ---------------------------------------------------------------------------

def _get_id(intent: Any) -> str:
    """Return the string ID regardless of whether *intent* is a dataclass or dict."""
    if isinstance(intent, dict):
        return intent["id"]
    return intent.id


def _get_deps(intent: Any) -> List[str]:
    """Return the dependency list, probing ``depends`` then ``dependencies``."""
    if isinstance(intent, dict):
        return list(intent.get("depends", intent.get("dependencies", [])))
    if hasattr(intent, "depends") and intent.depends:
        return list(intent.depends)
    if hasattr(intent, "dependencies") and intent.dependencies:
        return list(intent.dependencies)
    return []


def _get_estimated_tokens(intent: Any) -> int:
    """Return estimated token count from any intent format."""
    if isinstance(intent, dict):
        return intent.get("estimated_tokens", 1000)
    return getattr(intent, "estimated_tokens", 1000)


def _get_complexity(intent: Any) -> str:
    """Return complexity from any intent format."""
    if isinstance(intent, dict):
        return intent.get("complexity", "moderate")
    return getattr(intent, "complexity", "moderate")


# ---------------------------------------------------------------------------
# Wave scheduler (topological-level decomposition via Kahn's algorithm)
# ---------------------------------------------------------------------------

def compute_waves(intents: Sequence[Any]) -> List[List[Any]]:
    """Partition *intents* into parallel execution waves.

    Wave 0 contains intents with no dependencies. Wave N contains intents
    whose deps are all in waves < N.

    Raises ValueError on circular deps or missing dependency references.
    """
    if not intents:
        return []

    id_to_intent: Dict[str, Any] = {}
    for intent in intents:
        id_to_intent[_get_id(intent)] = intent

    # Validate: every dependency must reference a known intent
    for intent in intents:
        iid = _get_id(intent)
        for dep in _get_deps(intent):
            if dep not in id_to_intent:
                raise ValueError(
                    f"Intent '{iid}' depends on '{dep}', "
                    f"which does not exist. "
                    f"Known IDs: {sorted(id_to_intent.keys())}"
                )

    # Kahn's algorithm (BFS topological sort by level)
    in_degree: Dict[str, int] = {_get_id(i): 0 for i in intents}
    dependents: Dict[str, List[str]] = {_get_id(i): [] for i in intents}

    for intent in intents:
        iid = _get_id(intent)
        deps = _get_deps(intent)
        in_degree[iid] = len(deps)
        for dep in deps:
            dependents[dep].append(iid)

    current_wave_ids: List[str] = [
        iid for iid, deg in in_degree.items() if deg == 0
    ]

    waves: List[List[Any]] = []
    assigned: Set[str] = set()

    while current_wave_ids:
        wave = [id_to_intent[iid] for iid in sorted(current_wave_ids)]
        waves.append(wave)
        assigned.update(current_wave_ids)

        next_wave_ids: List[str] = []
        for iid in current_wave_ids:
            for dep_id in dependents[iid]:
                in_degree[dep_id] -= 1
                if in_degree[dep_id] == 0:
                    next_wave_ids.append(dep_id)

        current_wave_ids = next_wave_ids

    if len(assigned) < len(intents):
        remaining = set(id_to_intent.keys()) - assigned
        cycle = _find_cycle(remaining, id_to_intent)
        cycle_str = " -> ".join(cycle) if cycle else ", ".join(sorted(remaining))
        raise ValueError(f"Circular dependency detected: {cycle_str}")

    return waves


def _find_cycle(node_ids: Set[str], id_to_intent: Dict[str, Any]) -> List[str]:
    """Return a list of IDs forming one cycle, or []."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[str, int] = {nid: WHITE for nid in node_ids}
    parent: Dict[str, Optional[str]] = {nid: None for nid in node_ids}

    def dfs(nid: str) -> Optional[List[str]]:
        color[nid] = GRAY
        for dep in _get_deps(id_to_intent[nid]):
            if dep not in node_ids:
                continue
            if color[dep] == GRAY:
                cycle = [dep, nid]
                cur = nid
                while cur != dep:
                    cur = parent[cur]  # type: ignore[assignment]
                    if cur is None:
                        break
                    cycle.append(cur)
                cycle.reverse()
                return cycle
            if color[dep] == WHITE:
                parent[dep] = nid
                result = dfs(dep)
                if result is not None:
                    return result
        color[nid] = BLACK
        return None

    for nid in node_ids:
        if color[nid] == WHITE:
            result = dfs(nid)
            if result is not None:
                return result
    return []


# ---------------------------------------------------------------------------
# Wave analysis
# ---------------------------------------------------------------------------

@dataclass
class WaveStats:
    """Summary statistics for a wave decomposition."""
    total_intents: int
    total_waves: int
    peak_parallelism: int
    serial_depth: int
    bottleneck_wave: int
    critical_path: List[str] = field(default_factory=list)


def analyze_waves(waves: List[List[Any]], intents: Sequence[Any]) -> WaveStats:
    """Compute summary statistics over a wave decomposition."""
    if not waves:
        return WaveStats(0, 0, 0, 0, 0, [])

    wave_sizes = [len(w) for w in waves]
    peak = max(wave_sizes)
    bottleneck_idx = wave_sizes.index(peak)
    critical_path = _compute_critical_path(intents)

    return WaveStats(
        total_intents=sum(wave_sizes),
        total_waves=len(waves),
        peak_parallelism=peak,
        serial_depth=len(waves),
        bottleneck_wave=bottleneck_idx,
        critical_path=critical_path,
    )


def _compute_critical_path(intents: Sequence[Any]) -> List[str]:
    """Find the longest dependency chain via DP on the DAG."""
    id_to_intent: Dict[str, Any] = {_get_id(i): i for i in intents}
    memo: Dict[str, List[str]] = {}

    def longest_ending_at(iid: str) -> List[str]:
        if iid in memo:
            return memo[iid]
        deps = _get_deps(id_to_intent[iid])
        if not deps:
            memo[iid] = [iid]
            return memo[iid]
        best_prefix: List[str] = []
        for dep in deps:
            if dep in id_to_intent:
                candidate = longest_ending_at(dep)
                if len(candidate) > len(best_prefix):
                    best_prefix = candidate
        memo[iid] = best_prefix + [iid]
        return memo[iid]

    overall_best: List[str] = []
    for iid in id_to_intent:
        candidate = longest_ending_at(iid)
        if len(candidate) > len(overall_best):
            overall_best = candidate
    return overall_best


# ---------------------------------------------------------------------------
# Profile-to-agent-model mapping (which models can serve each profile)
# ---------------------------------------------------------------------------

PROFILE_AGENT_MODELS: Dict[str, List[str]] = {
    "task-predator":         ["claude", "gpt5.2"],
    "bug-hunter":            ["claude", "gpt5.2"],
    "feature-trailblazer":   ["claude", "gpt5.2", "gemini", "kimi2.5"],
    "testing-guru":          ["claude", "gpt5.2", "gemini"],
    "tenacious-unit-tester": ["gemini", "kimi2.5", "codellama-7b", "llama3.1-8b"],
    "docs-logs-wizard":      ["gemini", "kimi2.5", "gpt5.2"],
    "code-ace-reviewer":     ["claude", "gpt5.2"],
}

# Token rates for cost estimation (from css_renderer_config.py)
TOKEN_RATES: Dict[str, float] = {
    "claude": 0.000020,
    "gpt5.2": 0.000030,
    "gemini": 0.000005,
    "kimi2.5": 0.000002,
    "llama3.2-1b": 0, "llama3.2-3b": 0, "llama3.1-8b": 0,
    "codellama-7b": 0, "mistral-7b": 0, "qwen2-7b": 0,
}


def _cheapest_model_for_profile(profile: str) -> str:
    """Return the cheapest capable model for a profile."""
    models = PROFILE_AGENT_MODELS.get(profile, ["gemini"])
    return min(models, key=lambda m: TOKEN_RATES.get(m, 0))


def _estimate_intent_cost(intent: Any, profile: str) -> float:
    """Estimate the cost of running an intent with a given profile."""
    tokens = _get_estimated_tokens(intent)
    model = _cheapest_model_for_profile(profile)
    rate = TOKEN_RATES.get(model, 0.000005)
    return tokens * rate


# ---------------------------------------------------------------------------
# Staffing plan generator
# ---------------------------------------------------------------------------

def generate_staffing_plan(intents: Sequence[Any]) -> Dict[str, Any]:
    """Produce a full staffing plan from decomposer output.

    Combines assign_profile() and compute_waves() into a complete
    execution plan with cost estimates, profile load, and wave metadata.

    Returns a dict suitable for JSON serialization.
    """
    waves = compute_waves(intents)
    stats = analyze_waves(waves, intents)

    profile_load: Dict[str, int] = {}
    total_cost = 0.0
    total_tokens = 0
    wave_plans: List[Dict[str, Any]] = []

    for i, wave in enumerate(waves):
        wave_intents: List[Dict[str, Any]] = []
        wave_cost = 0.0

        for intent in wave:
            iid = _get_id(intent)
            profile = assign_profile(intent)
            tokens = _get_estimated_tokens(intent)
            cost = _estimate_intent_cost(intent, profile)
            model = _cheapest_model_for_profile(profile)

            profile_load[profile] = profile_load.get(profile, 0) + 1
            total_cost += cost
            total_tokens += tokens
            wave_cost += cost

            wave_intents.append({
                "id": iid,
                "profile": profile,
                "model": model,
                "workflow": "git-pr",
                "complexity": _get_complexity(intent),
                "estimated_tokens": tokens,
                "estimated_cost": round(cost, 4),
                "depends_on": _get_deps(intent),
            })

        wave_plans.append({
            "wave": i,
            "agents_needed": len(wave),
            "estimated_cost": round(wave_cost, 4),
            "intents": wave_intents,
        })

    return {
        "total_intents": stats.total_intents,
        "total_waves": stats.total_waves,
        "peak_parallelism": stats.peak_parallelism,
        "serial_depth": stats.serial_depth,
        "bottleneck_wave": stats.bottleneck_wave,
        "critical_path": stats.critical_path,
        "total_estimated_cost": round(total_cost, 4),
        "total_estimated_tokens": total_tokens,
        "profile_load": profile_load,
        "waves": wave_plans,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from quantum_routing.feature_decomposer import (
        decompose_realtime_collab_feature,
        decompose_slider_bug,
    )

    def _print_plan(plan: Dict[str, Any], title: str) -> None:
        print(f"\n{'=' * 72}")
        print(f"  STAFFING PLAN: {title}")
        print(f"{'=' * 72}")
        print(f"  Intents: {plan['total_intents']}  |  "
              f"Waves: {plan['total_waves']}  |  "
              f"Peak parallelism: {plan['peak_parallelism']}  |  "
              f"Cost: ${plan['total_estimated_cost']:.2f}  |  "
              f"Tokens: {plan['total_estimated_tokens']:,}")
        print()

        # Profile load
        print("  Profile load:")
        for profile in PROFILES:
            count = plan["profile_load"].get(profile, 0)
            if count:
                bar = "#" * count
                print(f"    {profile:<26} {count:3}  {bar}")
        print()

        # Waves
        for wp in plan["waves"]:
            print(f"  Wave {wp['wave']} ({wp['agents_needed']} agent"
                  f"{'s' if wp['agents_needed'] != 1 else ''}"
                  f", ${wp['estimated_cost']:.4f}):")
            for intent in wp["intents"]:
                print(f"    [{intent['complexity']:<12}] "
                      f"{intent['id']:<42} "
                      f"→ {intent['profile']:<24} "
                      f"({intent['model']}, ${intent['estimated_cost']:.4f})")
            print()

        # Critical path
        print(f"  Critical path ({len(plan['critical_path'])} intents):")
        print(f"    {' -> '.join(plan['critical_path'][:6])}")
        if len(plan["critical_path"]) > 6:
            print(f"    -> {' -> '.join(plan['critical_path'][6:])}")

    # Feature decomposition
    feature_intents = decompose_realtime_collab_feature()
    feature_plan = generate_staffing_plan(feature_intents)
    _print_plan(feature_plan, "Real-time Collaboration Feature (25 intents)")

    # Bug decomposition
    bug_intents = decompose_slider_bug()
    bug_plan = generate_staffing_plan(bug_intents)
    _print_plan(bug_plan, "Slider Bug Fix (12 intents)")

    # JSON export demo
    print(f"\n{'=' * 72}")
    print("  JSON EXPORT (bug plan, first 2 waves)")
    print(f"{'=' * 72}")
    preview = {**bug_plan, "waves": bug_plan["waves"][:2]}
    print(json.dumps(preview, indent=2))
