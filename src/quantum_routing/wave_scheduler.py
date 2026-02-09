"""Wave Scheduler -- extract parallel execution batches from an intent DAG.

Given a set of intents with dependency edges, compute_waves() partitions them
into waves where every intent in wave N depends only on intents in waves < N.
Wave 0 contains all root intents (no dependencies).  This is the canonical
topological-level decomposition used by the CP-SAT solver's dependency-aware
scheduling mode and by the Intent IDE's timeline view.

Supports three intent representations:
  - feature_decomposer.Intent  (field: depends)
  - agent_decomposer.Intent    (field: dependencies)
  - plain dict from github_tickets.decompose_ticket (key: 'depends')
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Union


# ---------------------------------------------------------------------------
# Helpers -- normalise heterogeneous intent representations
# ---------------------------------------------------------------------------

def _get_id(intent: Any) -> str:
    """Return the string ID regardless of whether *intent* is a dataclass or dict."""
    if isinstance(intent, dict):
        return intent["id"]
    return intent.id


def _get_deps(intent: Any) -> List[str]:
    """Return the dependency list, probing ``depends`` then ``dependencies``."""
    if isinstance(intent, dict):
        # github_tickets uses 'depends'; tolerate 'dependencies' too
        return list(intent.get("depends", intent.get("dependencies", [])))
    # Dataclass path -- feature_decomposer uses `depends`,
    # agent_decomposer uses `dependencies`.
    if hasattr(intent, "depends") and intent.depends:
        return list(intent.depends)
    if hasattr(intent, "dependencies") and intent.dependencies:
        return list(intent.dependencies)
    return []


# ---------------------------------------------------------------------------
# Core algorithm
# ---------------------------------------------------------------------------

def compute_waves(intents: Sequence[Any]) -> List[List[Any]]:
    """Partition *intents* into parallel execution waves (topological levels).

    Parameters
    ----------
    intents : list
        A list of intent objects.  Each element may be:
        * a ``feature_decomposer.Intent`` (has ``.id`` and ``.depends``)
        * an ``agent_decomposer.Intent`` (has ``.id`` and ``.dependencies``)
        * a plain ``dict`` with ``"id"`` and ``"depends"`` keys

    Returns
    -------
    List[List]
        ``waves[0]`` contains intents with zero dependencies, ``waves[1]``
        contains intents whose dependencies are all in wave 0, etc.

    Raises
    ------
    ValueError
        If a dependency references a non-existent intent ID, or if the
        dependency graph contains a cycle.
    """
    if not intents:
        return []

    # Build lookup structures
    id_to_intent: Dict[str, Any] = {}
    for intent in intents:
        iid = _get_id(intent)
        id_to_intent[iid] = intent

    # Validate: every dependency must reference a known intent
    for intent in intents:
        iid = _get_id(intent)
        for dep in _get_deps(intent):
            if dep not in id_to_intent:
                raise ValueError(
                    f"Intent '{iid}' depends on '{dep}', "
                    f"which does not exist in the intent set. "
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

    # Seed wave 0 with all zero-in-degree nodes
    current_wave_ids: List[str] = [
        iid for iid, deg in in_degree.items() if deg == 0
    ]

    waves: List[List[Any]] = []
    assigned: Set[str] = set()

    while current_wave_ids:
        # Record this wave (preserving original intent objects)
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

    # If we did not assign every intent, there is a cycle
    if len(assigned) < len(intents):
        remaining = set(id_to_intent.keys()) - assigned
        # Find one cycle for a clear error message
        cycle = _find_cycle(remaining, id_to_intent)
        cycle_str = " -> ".join(cycle) if cycle else ", ".join(sorted(remaining))
        raise ValueError(
            f"Circular dependency detected among intents: {cycle_str}"
        )

    return waves


def _find_cycle(node_ids: Set[str], id_to_intent: Dict[str, Any]) -> List[str]:
    """Return a list of IDs forming one cycle within *node_ids*, or []."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[str, int] = {nid: WHITE for nid in node_ids}
    parent: Dict[str, Optional[str]] = {nid: None for nid in node_ids}

    def dfs(nid: str) -> Optional[List[str]]:
        color[nid] = GRAY
        for dep in _get_deps(id_to_intent[nid]):
            if dep not in node_ids:
                continue
            if color[dep] == GRAY:
                # Back-edge found -- reconstruct cycle
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
# WaveStats
# ---------------------------------------------------------------------------

@dataclass
class WaveStats:
    """Summary statistics for a wave decomposition."""
    total_intents: int
    total_waves: int
    peak_parallelism: int        # max intents in any single wave
    serial_depth: int            # number of waves (same as total_waves)
    bottleneck_wave: int         # wave index with the most intents
    critical_path: List[str]     # longest chain of dependent intent IDs


def analyze_waves(waves: List[List[Any]], intents: Sequence[Any]) -> WaveStats:
    """Compute summary statistics over a wave decomposition.

    Parameters
    ----------
    waves : list[list]
        Output of :func:`compute_waves`.
    intents : list
        The original flat intent list (used to trace the critical path).

    Returns
    -------
    WaveStats
    """
    if not waves:
        return WaveStats(
            total_intents=0,
            total_waves=0,
            peak_parallelism=0,
            serial_depth=0,
            bottleneck_wave=0,
            critical_path=[],
        )

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
    """Find the longest dependency chain (by number of intents).

    Uses dynamic programming on the DAG.  For each intent, the longest path
    ending at that intent equals 1 + max(longest path ending at each dep).
    """
    id_to_intent: Dict[str, Any] = {}
    for intent in intents:
        id_to_intent[_get_id(intent)] = intent

    # Memoised longest-path-ending-at
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
# Pretty printing
# ---------------------------------------------------------------------------

def print_waves(waves: List[List[Any]], title: str = "Wave Schedule") -> None:
    """Print a human-readable wave schedule."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")
    for i, wave in enumerate(waves):
        ids = [_get_id(intent) for intent in wave]
        print(f"\n  Wave {i} ({len(wave)} intent{'s' if len(wave) != 1 else ''}):")
        for iid in ids:
            print(f"    - {iid}")


def print_stats(stats: WaveStats) -> None:
    """Print WaveStats in a human-readable format."""
    print(f"\n  {'- ' * 35}")
    print(f"  WaveStats:")
    print(f"    Total intents:    {stats.total_intents}")
    print(f"    Total waves:      {stats.total_waves}")
    print(f"    Peak parallelism: {stats.peak_parallelism}")
    print(f"    Serial depth:     {stats.serial_depth}")
    print(f"    Bottleneck wave:  {stats.bottleneck_wave}")
    print(f"    Critical path:    {' -> '.join(stats.critical_path)}")
    print(f"    Critical length:  {len(stats.critical_path)}")


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from quantum_routing.feature_decomposer import (
        decompose_realtime_collab_feature,
        decompose_slider_bug,
    )

    # -- Real-time collaboration feature (25 intents) -----------------------
    collab_intents = decompose_realtime_collab_feature()
    collab_waves = compute_waves(collab_intents)
    print_waves(collab_waves, "Real-Time Collaboration Feature (25 intents)")
    collab_stats = analyze_waves(collab_waves, collab_intents)
    print_stats(collab_stats)

    # -- Slider bug (12 intents) --------------------------------------------
    bug_intents = decompose_slider_bug()
    bug_waves = compute_waves(bug_intents)
    print_waves(bug_waves, "Slider Bug Fix (12 intents)")
    bug_stats = analyze_waves(bug_waves, bug_intents)
    print_stats(bug_stats)
