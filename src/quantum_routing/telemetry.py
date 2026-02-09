"""Telemetry Layer -- metrics collection for self-tuning weight optimization.

Provides:
    - Chain coherence analysis
    - Cost/quality ratio computation
    - Gate pass rate tracking
    - Run logging and comparison

See: Minimal viable weight tuning in CLAUDE.md
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TelemetryLog:
    """Append-only log of routing runs for comparison and tuning.

    Each run is the dict returned by compute_metrics(). The log provides
    filtering by gate pass rate and Pareto frontier extraction — the
    primitives needed for a future self-tuning loop.
    """

    runs: List[Dict[str, Any]] = field(default_factory=list)
    log_path: Optional[Path] = None

    def add_run(self, metrics: Dict[str, Any]) -> None:
        self.runs.append(metrics)
        if self.log_path:
            self._save()

    def _save(self) -> None:
        if not self.log_path:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "w") as f:
            json.dump({"runs": self.runs}, f, indent=2)

    @classmethod
    def load(cls, path: Path) -> "TelemetryLog":
        with open(path) as f:
            data = json.load(f)
        log = cls(runs=data.get("runs", []), log_path=path)
        return log

    def best_by_coherence(self, min_gate_pass: float = 0.90) -> Optional[Dict]:
        """Best chain coherence among runs meeting gate threshold."""
        valid = [
            r for r in self.runs
            if r["gate_pass"]["gate_1_pass_rate"] >= min_gate_pass
        ]
        if not valid:
            return None
        return max(valid, key=lambda r: r["chain_coherence"]["score"])

    def best_by_cost(self, min_gate_pass: float = 0.90) -> Optional[Dict]:
        """Best cost/quality ratio among runs meeting gate threshold."""
        valid = [
            r for r in self.runs
            if r["gate_pass"]["gate_1_pass_rate"] >= min_gate_pass
        ]
        if not valid:
            return None
        return min(valid, key=lambda r: r["cost_quality"]["cost_quality_ratio"])

    def summary(self) -> str:
        if not self.runs:
            return "No runs logged."
        best_c = self.best_by_coherence()
        best_cq = self.best_by_cost()
        lines = [f"Telemetry: {len(self.runs)} runs"]
        if best_c:
            lines.append(f"  Best coherence: {best_c['chain_coherence']['score']:.1%}")
        if best_cq:
            lines.append(f"  Best cost/quality: {best_cq['cost_quality']['cost_quality_ratio']:.4f}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Metric computation functions
# ---------------------------------------------------------------------------

def compute_chain_metrics(
    assignments: Dict[int, str],
    agents: Dict[str, Any],
    workflow_chains: Sequence[Any],
) -> Dict[str, Any]:
    """Compute chain coherence metrics from assignments.

    Coherence = % of chains where all intents land on the same model TYPE
    (not instance — claude-0 and claude-59 are the same type).

    Args:
        assignments: intent_index -> agent_name mapping
        agents: Full agent pool dict (agent_name -> agent dict with 'model_type')
        workflow_chains: List of (chain_type, [intent_indices]) tuples
            from build_workflow_chains()

    Returns:
        Dict with coherence metrics
    """
    chains_single = 0
    chains_one_switch = 0
    chains_multi = 0
    total_chain_length = 0

    for entry in workflow_chains:
        # workflow_chains entries are (chain_type_str, [step_indices])
        if isinstance(entry, (list, tuple)) and len(entry) == 2:
            _, steps = entry
        else:
            steps = entry

        if len(steps) <= 1:
            continue

        total_chain_length += len(steps)
        model_types = []
        for idx in steps:
            agent_name = assignments.get(idx)
            if agent_name and agent_name in agents:
                model_types.append(agents[agent_name]['model_type'])

        if not model_types:
            continue

        unique = set(model_types)
        if len(unique) == 1:
            chains_single += 1
        elif len(unique) == 2:
            chains_one_switch += 1
        else:
            chains_multi += 1

    total_chains = chains_single + chains_one_switch + chains_multi

    if total_chains == 0:
        return {
            "score": 0.0,
            "avg_chain_length": 0.0,
            "chains_single_model": 0,
            "chains_one_switch": 0,
            "chains_multi_switch": 0,
            "total_chains": 0,
        }

    return {
        "score": chains_single / total_chains,
        "avg_chain_length": total_chain_length / total_chains,
        "chains_single_model": chains_single,
        "chains_one_switch": chains_one_switch,
        "chains_multi_switch": chains_multi,
        "total_chains": total_chains,
    }


def compute_cost_quality_metrics(
    assignments: Dict[int, str],
    intents: Sequence[Any],
    agents: Dict[str, Any],
) -> Dict[str, Any]:
    """Compute cost and quality metrics from assignments.

    Args:
        assignments: intent_index -> agent_name mapping
        intents: List of intent dicts with 'estimated_tokens', 'min_quality'
        agents: Full agent pool dict (agent_name -> agent dict)

    Returns:
        Dict with cost/quality metrics
    """
    total_cost = 0.0
    total_story_points = 0
    quality_scores = []
    overkill_count = 0

    for idx, intent in enumerate(intents):
        agent_name = assignments.get(idx)
        if not agent_name or agent_name not in agents:
            continue

        agent = agents[agent_name]
        tokens = intent.get("estimated_tokens", 0)
        total_cost += tokens * agent['token_rate']
        total_story_points += intent.get('story_points', 0)

        quality_scores.append(agent['quality'])
        if agent['quality'] > intent.get("min_quality", 0):
            overkill_count += 1

    n = len(quality_scores)
    if n == 0:
        return {
            "total_cost": 0.0,
            "avg_quality": 0.0,
            "overkill_pct": 0.0,
            "cost_quality_ratio": 0.0,
            "cost_per_story_point": 0.0,
            "assigned_count": 0,
        }

    avg_quality = sum(quality_scores) / n
    cq_ratio = total_cost / avg_quality if avg_quality > 0 else 0.0
    cost_per_sp = total_cost / total_story_points if total_story_points > 0 else 0.0

    return {
        "total_cost": round(total_cost, 4),
        "avg_quality": round(avg_quality, 4),
        "overkill_pct": round(overkill_count / n, 4),
        "cost_quality_ratio": round(cq_ratio, 4),
        "cost_per_story_point": round(cost_per_sp, 4),
        "assigned_count": n,
    }


def compute_gate_metrics(
    assignments: Dict[int, str],
    intents: Sequence[Any],
    agents: Dict[str, Any],
) -> Dict[str, Any]:
    """Compute predicted gate pass rates from assignments.

    Gate 1 (per-intent): agent quality >= intent min_quality
    Gate 3 (architecture): quality consistency across assignments
        (mirrors quality_gates.py architecture_score: max(0, 100*(1 - stdev/0.3)))

    Args:
        assignments: intent_index -> agent_name mapping
        intents: List of intent dicts with 'min_quality'
        agents: Full agent pool dict

    Returns:
        Dict with gate pass rates and counts
    """
    passed = 0
    failed = 0
    quality_scores = []

    for idx, intent in enumerate(intents):
        agent_name = assignments.get(idx)
        if not agent_name or agent_name not in agents:
            continue

        agent_quality = agents[agent_name]['quality']
        min_quality = intent.get('min_quality', 0)
        quality_scores.append(agent_quality)

        if agent_quality >= min_quality:
            passed += 1
        else:
            failed += 1

    total = passed + failed
    gate_1_rate = passed / total if total > 0 else 0.0

    # Architecture score: low quality variance = high score
    if len(quality_scores) >= 2:
        stdev = statistics.stdev(quality_scores)
        architecture_score = max(0.0, 1.0 - stdev / 0.3)
    else:
        architecture_score = 1.0

    return {
        "gate_1_pass_rate": round(gate_1_rate, 4),
        "gate_1_passed": passed,
        "gate_1_failed": failed,
        "architecture_score": round(architecture_score, 4),
    }


def compute_deadline_metrics(
    assignments: Dict[int, str],
    intents: Sequence[Any],
    agents: Dict[str, Any],
) -> Dict[str, Any]:
    """Compute deadline and dependency violation metrics.

    For each assigned intent with a deadline, estimates whether the agent's
    latency characteristic would cause a miss. Also checks dependency quality
    ordering (downstream quality should not drop below upstream).

    Args:
        assignments: intent_index -> agent_name mapping
        intents: List of intent dicts with 'deadline' (days), 'depends'
        agents: Full agent pool dict

    Returns:
        Dict with deadline and dependency violation metrics
    """
    total_with_deadline = 0
    deadline_violations = 0
    dep_violations = 0
    dep_pairs_checked = 0
    avg_latency = 0.0
    latency_count = 0

    for idx, intent in enumerate(intents):
        agent_name = assignments.get(idx)
        if not agent_name or agent_name not in agents:
            continue

        agent = agents[agent_name]
        avg_latency += agent['latency']
        latency_count += 1

        # Deadline check: intents with tight deadlines assigned to slow agents
        deadline = intent.get('deadline', -1)
        if deadline >= 0:
            total_with_deadline += 1
            # Heuristic: local models (latency < 2.0) are slower to complete
            # complex tasks despite lower per-token latency. Estimate completion
            # days from complexity token count / throughput.
            tokens = intent.get('estimated_tokens', 1000)
            # tokens_per_day estimate: cloud ~50k/day, local ~10k/day
            tokens_per_day = 50000 if not agent.get('is_local') else 10000
            est_days = tokens / tokens_per_day
            if est_days > deadline:
                deadline_violations += 1

        # Dependency quality check: downstream agent quality >= upstream
        for dep_idx in intent.get('depends', []):
            dep_agent = assignments.get(dep_idx)
            if dep_agent and dep_agent in agents:
                dep_pairs_checked += 1
                if agents[dep_agent]['quality'] > agent['quality']:
                    dep_violations += 1

    n = latency_count
    return {
        "avg_agent_latency": round(avg_latency / n, 4) if n > 0 else 0.0,
        "deadline_violation_rate": round(
            deadline_violations / total_with_deadline, 4
        ) if total_with_deadline > 0 else 0.0,
        "deadline_violations": deadline_violations,
        "total_with_deadline": total_with_deadline,
        "dep_quality_violations": dep_violations,
        "dep_pairs_checked": dep_pairs_checked,
        "dep_violation_rate": round(
            dep_violations / dep_pairs_checked, 4
        ) if dep_pairs_checked > 0 else 0.0,
    }


def compute_metrics(
    assignments: Dict[int, str],
    intents: Sequence[Any],
    agents: Dict[str, Any],
    workflow_chains: Sequence[Any],
    weights: Optional[Dict[str, float]] = None,
    solver_duration_s: float = 0.0,
) -> Dict[str, Any]:
    """Compute all telemetry metrics from a solver run.

    This is the single entry point. Takes raw solver output — no
    pre-extraction of rates/qualities/latencies needed.

    Args:
        assignments: intent_index -> agent_name from solve_cpsat()
        intents: List of intent dicts from generate_intents()
        agents: Agent pool dict from build_agent_pool()
        workflow_chains: From build_workflow_chains() — list of
            (chain_type, [intent_indices]) tuples
        weights: Weight config used for this run (optional)
        solver_duration_s: How long the solver took in seconds

    Returns:
        JSON-serializable dict with all metrics
    """
    if weights is None:
        weights = dict(DEFAULT_WEIGHTS)

    chain = compute_chain_metrics(assignments, agents, workflow_chains)
    cost = compute_cost_quality_metrics(assignments, intents, agents)
    gate = compute_gate_metrics(assignments, intents, agents)
    deadline = compute_deadline_metrics(assignments, intents, agents)

    return {
        "chain_coherence": chain,
        "cost_quality": cost,
        "gate_pass": gate,
        "deadline": deadline,
        "weights": weights,
        "metadata": {
            "solver_duration_s": round(solver_duration_s, 2),
            "num_intents": len(intents),
            "num_assigned": len(assignments),
            "num_agents": len(agents),
            "num_chains": len(workflow_chains),
            "timestamp": datetime.utcnow().isoformat(),
        },
    }


# ---------------------------------------------------------------------------
# Weight perturbation for self-tuning (future use)
# ---------------------------------------------------------------------------

def perturb_weights(
    weights: Dict[str, float],
    perturbation_pct: float = 0.1,
) -> Dict[str, float]:
    """Perturb weights by a percentage (for exploration).
    
    Args:
        weights: Current weight configuration
        perturbation_pct: ±percentage to perturb (e.g., 0.1 = ±10%)
    
    Returns:
        Perturbed weight configuration
    """
    import random
    
    perturbed = {}
    for k, v in weights.items():
        factor = random.uniform(1 - perturbation_pct, 1 + perturbation_pct)
        perturbed[k] = v * factor
    return perturbed


# ---------------------------------------------------------------------------
# Default weights (mirrors css_renderer_config.py)
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS: Dict[str, float] = {
    "DEP_PENALTY": 100.0,
    "OVERKILL_WEIGHT": 2.0,
    "LATENCY_WEIGHT": 0.001,
    "DEADLINE_WEIGHT": 1.5,
    "CONTEXT_BONUS": 0.5,
}
