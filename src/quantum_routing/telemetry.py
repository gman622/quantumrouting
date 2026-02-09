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
class RoutingMetrics:
    """Metrics from a single CP-SAT routing run."""
    
    # Weights used for this run
    weights: Dict[str, float]
    
    # Chain coherence metrics
    chain_coherence_score: float  # % of chains on single model type
    avg_chain_length: float
    chains_single_model: int
    chains_one_switch: int
    chains_multi_switch: int
    total_chains: int
    
    # Cost/quality metrics
    total_token_cost: float
    avg_quality_score: float
    overkill_percentage: float  # % of tasks assigned higher quality than minimum
    cost_quality_ratio: float
    
    # Gate pass rates
    gate_1_pass_rate: float  # per-intent validation
    gate_2_pass_rate: float  # per-wave validation
    gate_3_pass_rate: float  # final review
    
    # Latency metrics
    avg_latency_ms: float
    latency_violation_rate: float  # % missed SLA
    deadline_violation_rate: float
    
    # Execution metadata
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    solver_duration_ms: float = 0.0
    num_intents: int = 0
    num_agents: int = 0
    
    # Raw assignments for deeper analysis
    assignments: Optional[Dict[int, str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "weights": self.weights,
            "chain_coherence": {
                "score": self.chain_coherence_score,
                "avg_chain_length": self.avg_chain_length,
                "chains_single_model": self.chains_single_model,
                "chains_one_switch": self.chains_one_switch,
                "chains_multi_switch": self.chains_multi_switch,
                "total_chains": self.total_chains,
            },
            "cost_quality": {
                "total_token_cost": self.total_token_cost,
                "avg_quality_score": self.avg_quality_score,
                "overkill_percentage": self.overkill_percentage,
                "cost_quality_ratio": self.cost_quality_ratio,
            },
            "gate_pass_rates": {
                "gate_1": self.gate_1_pass_rate,
                "gate_2": self.gate_2_pass_rate,
                "gate_3": self.gate_3_pass_rate,
            },
            "latency": {
                "avg_latency_ms": self.avg_latency_ms,
                "violation_rate": self.latency_violation_rate,
                "deadline_violation_rate": self.deadline_violation_rate,
            },
            "metadata": {
                "solver_duration_ms": self.solver_duration_ms,
                "num_intents": self.num_intents,
                "num_agents": self.num_agents,
            },
        }
    
    def to_json(self, path: Path) -> None:
        """Write metrics to JSON file."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RoutingMetrics":
        """Load metrics from dict."""
        chain_data = data["chain_coherence"]
        cost_data = data["cost_quality"]
        gate_data = data["gate_pass_rates"]
        latency_data = data["latency"]
        meta = data["metadata"]
        
        return cls(
            weights=data["weights"],
            chain_coherence_score=chain_data["score"],
            avg_chain_length=chain_data["avg_chain_length"],
            chains_single_model=chain_data["chains_single_model"],
            chains_one_switch=chain_data["chains_one_switch"],
            chains_multi_switch=chain_data["chains_multi_switch"],
            total_chains=chain_data["total_chains"],
            total_token_cost=cost_data["total_token_cost"],
            avg_quality_score=cost_data["avg_quality_score"],
            overkill_percentage=cost_data["overkill_percentage"],
            cost_quality_ratio=cost_data["cost_quality_ratio"],
            gate_1_pass_rate=gate_data["gate_1"],
            gate_2_pass_rate=gate_data["gate_2"],
            gate_3_pass_rate=gate_data["gate_3"],
            avg_latency_ms=latency_data["avg_latency_ms"],
            latency_violation_rate=latency_data["violation_rate"],
            deadline_violation_rate=latency_data["deadline_violation_rate"],
            solver_duration_ms=meta["solver_duration_ms"],
            num_intents=meta["num_intents"],
            num_agents=meta["num_agents"],
        )


@dataclass  
class TelemetryLog:
    """Log of multiple routing runs for comparison."""
    
    runs: List[RoutingMetrics] = field(default_factory=list)
    log_path: Optional[Path] = None
    
    def add_run(self, metrics: RoutingMetrics) -> None:
        """Add a new run to the log."""
        self.runs.append(metrics)
        if self.log_path:
            self.save()
    
    def save(self) -> None:
        """Save log to JSON."""
        if not self.log_path:
            return
        data = {
            "runs": [r.to_dict() for r in self.runs],
            "created": datetime.utcnow().isoformat(),
        }
        with open(self.log_path, "w") as f:
            json.dump(data, f, indent=2)
    
    def load(self, path: Path) -> "TelemetryLog":
        """Load log from JSON."""
        with open(path) as f:
            data = json.load(f)
        self.runs = [RoutingMetrics.from_dict(r) for r in data["runs"]]
        self.log_path = path
        return self
    
    def best_by_coherence(self, min_gate_pass: float = 0.90) -> Optional[RoutingMetrics]:
        """Find run with best coherence that meets gate pass threshold."""
        valid = [r for r in self.runs if r.gate_3_pass_rate >= min_gate_pass]
        if not valid:
            return None
        return max(valid, key=lambda r: r.chain_coherence_score)
    
    def best_by_cost_quality(self, min_gate_pass: float = 0.90) -> Optional[RoutingMetrics]:
        """Find run with best cost/quality ratio that meets gate pass threshold."""
        valid = [r for r in self.runs if r.gate_3_pass_rate >= min_gate_pass]
        if not valid:
            return None
        return min(valid, key=lambda r: r.cost_quality_ratio)
    
    def pareto_frontier(self, min_gate_pass: float = 0.90) -> List[RoutingMetrics]:
        """Find Pareto-optimal runs (no other run dominates on both coherence and cost)."""
        valid = [r for r in self.runs if r.gate_3_pass_rate >= min_gate_pass]
        pareto = []
        
        for candidate in valid:
            is_dominated = False
            for other in valid:
                if other is candidate:
                    continue
                # other dominates candidate if better on both metrics
                if (other.chain_coherence_score >= candidate.chain_coherence_score and 
                    other.cost_quality_ratio <= candidate.cost_quality_ratio and
                    (other.chain_coherence_score > candidate.chain_coherence_score or
                     other.cost_quality_ratio < candidate.cost_quality_ratio)):
                    is_dominated = True
                    break
            if not is_dominated:
                pareto.append(candidate)
        
        return pareto
    
    def summary(self) -> str:
        """Generate human-readable summary."""
        if not self.runs:
            return "No runs logged yet."
        
        best_coherence = self.best_by_coherence()
        best_cq = self.best_by_cost_quality()
        
        lines = [
            f"Telemetry Log: {len(self.runs)} runs",
            f"  Best coherence: {best_coherence.chain_coherence_score:.1%}" if best_coherence else "  No valid runs",
            f"  Best cost/quality: {best_cq.cost_quality_ratio:.4f}" if best_cq else "",
            f"  Pareto frontier: {len(self.pareto_frontier())} runs",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Metric computation functions
# ---------------------------------------------------------------------------

def compute_chain_metrics(
    assignments: Dict[int, str],
    intents: Sequence[Any],
    chains: Sequence[Sequence[int]],
    agent_qualities: Dict[str, float],
) -> Dict[str, Any]:
    """Compute chain coherence metrics from assignments.
    
    Args:
        assignments: intent_index -> agent_name mapping
        intents: List of intent dicts with 'complexity' and 'min_quality'
        chains: List of dependency chains (lists of intent indices)
        agent_qualities: agent_name -> quality_score mapping
    
    Returns:
        Dict with coherence metrics
    """
    chains_single = 0
    chains_one_switch = 0
    chains_multi = 0
    total_chain_length = 0
    
    for chain in chains:
        if len(chain) <= 1:
            continue
            
        total_chain_length += len(chain)
        models = []
        for idx in chain:
            agent = assignments.get(idx)
            if agent:
                models.append(agent)
        
        if not models:
            continue
            
        unique_models = set(models)
        if len(unique_models) == 1:
            chains_single += 1
        elif len(unique_models) == 2:
            chains_one_switch += 1
        else:
            chains_multi += 1
    
    total_chains = chains_single + chains_one_switch + chains_multi
    
    if total_chains == 0:
        coherence = 0.0
        avg_length = 0.0
    else:
        coherence = chains_single / total_chains
        avg_length = total_chain_length / total_chains
    
    return {
        "chain_coherence_score": coherence,
        "avg_chain_length": avg_length,
        "chains_single_model": chains_single,
        "chains_one_switch": chains_one_switch,
        "chains_multi_switch": chains_multi,
        "total_chains": total_chains,
    }


def compute_cost_quality_metrics(
    assignments: Dict[int, str],
    intents: Sequence[Any],
    agent_rates: Dict[str, float],
    agent_qualities: Dict[str, float],
) -> Dict[str, Any]:
    """Compute cost and quality metrics from assignments.
    
    Args:
        assignments: intent_index -> agent_name mapping
        intents: List of intent dicts with 'estimated_tokens', 'min_quality'
        agent_rates: agent_name -> token_rate ($ per token)
        agent_qualities: agent_name -> quality_score (0-1)
    
    Returns:
        Dict with cost/quality metrics
    """
    total_cost = 0.0
    quality_scores = []
    overkill_count = 0
    
    for idx, intent in enumerate(intents):
        agent_name = assignments.get(idx)
        if not agent_name:
            continue
            
        tokens = intent.get("estimated_tokens", 0)
        rate = agent_rates.get(agent_name, 0)
        total_cost += tokens * rate
        
        agent_quality = agent_qualities.get(agent_name, 0)
        min_quality = intent.get("min_quality", 0)
        quality_scores.append(agent_quality)
        
        if agent_quality > min_quality:
            overkill_count += 1
    
    n = len(quality_scores)
    if n == 0:
        return {
            "total_token_cost": 0,
            "avg_quality_score": 0,
            "overkill_percentage": 0,
            "cost_quality_ratio": float("inf"),
        }
    
    avg_quality = sum(quality_scores) / n
    overkill_pct = overkill_count / n
    
    if avg_quality == 0:
        cq_ratio = float("inf")
    else:
        cq_ratio = total_cost / avg_quality
    
    return {
        "total_token_cost": total_cost,
        "avg_quality_score": avg_quality,
        "overkill_percentage": overkill_pct,
        "cost_quality_ratio": cq_ratio,
    }


def compute_gate_metrics(
    intent_results: Optional[Sequence[Any]] = None,
) -> Dict[str, float]:
    """Compute gate pass rates from intent results.
    
    Args:
        intent_results: List of IntentResult or similar objects with status/score
    
    Returns:
        Dict with gate pass rates
    """
    # Placeholder: would integrate with quality_gates.py
    # For now, returns reasonable defaults
    return {
        "gate_1_pass_rate": 0.95,  # per-intent validation
        "gate_2_pass_rate": 0.92,  # per-wave validation  
        "gate_3_pass_rate": 0.90, # final review
    }


def compute_latency_metrics(
    assignments: Dict[int, str],
    intents: Sequence[Any],
    agent_latencies: Dict[str, float],
) -> Dict[str, float]:
    """Compute latency metrics from assignments.
    
    Args:
        assignments: intent_index -> agent_name mapping
        intents: List of intent dicts with 'deadline_ms'
        agent_latencies: agent_name -> avg_latency_ms
    
    Returns:
        Dict with latency metrics
    """
    latencies = []
    violations = 0
    deadline_violations = 0
    
    for idx, intent in enumerate(intents):
        agent_name = assignments.get(idx)
        if not agent_name:
            continue
            
        agent_lat = agent_latencies.get(agent_name, 0)
        latencies.append(agent_lat)
        
        deadline = intent.get("deadline_ms")
        if deadline and agent_lat > deadline:
            deadline_violations += 1
        
        # SLA violation (arbitrary 1000ms threshold if not specified)
        sla = intent.get("sla_ms", 1000)
        if agent_lat > sla:
            violations += 1
    
    n = len(latencies)
    if n == 0:
        return {
            "avg_latency_ms": 0,
            "latency_violation_rate": 0,
            "deadline_violation_rate": 0,
        }
    
    avg_lat = sum(latencies) / n
    violation_rate = violations / n
    deadline_rate = deadline_violations / n
    
    return {
        "avg_latency_ms": avg_lat,
        "latency_violation_rate": violation_rate,
        "deadline_violation_rate": deadline_rate,
    }


def collect_metrics(
    weights: Dict[str, float],
    assignments: Dict[int, str],
    intents: Sequence[Any],
    chains: Sequence[Sequence[int]],
    agent_rates: Dict[str, float],
    agent_qualities: Dict[str, float],
    agent_latencies: Optional[Dict[str, float]] = None,
    intent_results: Optional[Sequence[Any]] = None,
    solver_duration_ms: float = 0.0,
) -> RoutingMetrics:
    """Collect all metrics from a routing run.
    
    Args:
        weights: The weight configuration used for this run
        assignments: intent_index -> agent_name mapping from solver
        intents: List of intent dicts
        chains: List of dependency chains
        agent_rates: agent_name -> token_rate
        agent_qualities: agent_name -> quality_score
        agent_latencies: agent_name -> avg_latency_ms (optional)
        intent_results: Results from quality gates (optional)
        solver_duration_ms: How long the solver took
    
    Returns:
        Complete RoutingMetrics object
    """
    if agent_latencies is None:
        agent_latencies = {k: 100.0 for k in agent_qualities}  # defaults
    
    chain_metrics = compute_chain_metrics(assignments, intents, chains, agent_qualities)
    cost_metrics = compute_cost_quality_metrics(assignments, intents, agent_rates, agent_qualities)
    gate_metrics = compute_gate_metrics(intent_results)
    latency_metrics = compute_latency_metrics(assignments, intents, agent_latencies)
    
    return RoutingMetrics(
        weights=weights,
        chain_coherence_score=chain_metrics["chain_coherence_score"],
        avg_chain_length=chain_metrics["avg_chain_length"],
        chains_single_model=chain_metrics["chains_single_model"],
        chains_one_switch=chain_metrics["chains_one_switch"],
        chains_multi_switch=chain_metrics["chains_multi_switch"],
        total_chains=chain_metrics["total_chains"],
        total_token_cost=cost_metrics["total_token_cost"],
        avg_quality_score=cost_metrics["avg_quality_score"],
        overkill_percentage=cost_metrics["overkill_percentage"],
        cost_quality_ratio=cost_metrics["cost_quality_ratio"],
        gate_1_pass_rate=gate_metrics["gate_1_pass_rate"],
        gate_2_pass_rate=gate_metrics["gate_2_pass_rate"],
        gate_3_pass_rate=gate_metrics["gate_3_pass_rate"],
        avg_latency_ms=latency_metrics["avg_latency_ms"],
        latency_violation_rate=latency_metrics["latency_violation_rate"],
        deadline_violation_rate=latency_metrics["deadline_violation_rate"],
        solver_duration_ms=solver_duration_ms,
        num_intents=len(intents),
        num_agents=len(agent_qualities),
        assignments=assignments,
    )


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
