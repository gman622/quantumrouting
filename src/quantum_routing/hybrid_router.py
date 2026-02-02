"""Hybrid router for AI intent assignment.

Intelligently routes problems to the appropriate solver based on problem characteristics:
- Greedy: Fast heuristic for small/simple problems
- CP-SAT: OR-Tools for medium-scale problems with linear constraints
- Wave-decomposed: Breaks large problems into parallelizable subproblems
- D-Wave Hybrid: Quantum-classical hybrid for very large or complex problems

Usage:
    from hybrid_router import HybridRouter, RouteResult
    
    router = HybridRouter()
    result = router.route(intents, agents, dependencies)
    
    if result.success:
        print(f"Assigned {len(result.assignments)} tasks using {result.solver_used}")
"""

import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Any
import logging

# Import existing solvers
from .solve_10k_ortools import solve_cpsat, greedy_solve as ortools_greedy

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SolverType(Enum):
    """Available solver backends."""
    GREEDY = auto()
    CP_SAT = auto()
    WAVE_DECOMPOSED = auto()
    DWAVE_HYBRID = auto()


@dataclass
class ProblemCharacteristics:
    """Analysis of a routing problem."""
    num_tasks: int
    num_agents: int
    num_dependencies: int
    dep_density: float  # dependencies / (tasks^2)
    avg_chain_length: float
    max_wave_size: int  # if decomposed
    estimated_variables: int
    complexity_score: float  # 0-1, higher = more complex


@dataclass
class RouteResult:
    """Result from a routing attempt."""
    success: bool
    assignments: Dict[int, str]  # intent_idx -> agent_name
    solver_used: SolverType
    solve_time: float
    objective_value: Optional[float]
    gap: Optional[float]  # optimality gap (0 = optimal)
    violations: List[str]
    metadata: Dict[str, Any]


class ProblemClassifier:
    """Analyzes routing problems and recommends solver selection."""
    
    # Thresholds for solver selection
    GREEDY_MAX_TASKS = 500
    GREEDY_MAX_DEP_DENSITY = 0.01
    
    CP_SAT_MAX_TASKS = 50000
    CP_SAT_MAX_DEP_DENSITY = 0.1
    
    WAVE_MAX_TASKS = 500000
    
    def analyze(self, intents: List[Dict], agents: Dict, 
                dependencies: Optional[List[Tuple[int, int]]] = None) -> ProblemCharacteristics:
        """Analyze problem characteristics."""
        num_tasks = len(intents)
        num_agents = len(agents)
        
        # Count dependencies
        if dependencies is None:
            dependencies = self._extract_dependencies(intents)
        num_dependencies = len(dependencies)
        dep_density = num_dependencies / (num_tasks ** 2) if num_tasks > 0 else 0
        
        # Estimate chain lengths
        chain_lengths = self._compute_chain_lengths(intents, dependencies)
        avg_chain_length = sum(chain_lengths) / len(chain_lengths) if chain_lengths else 0
        
        # Estimate max wave size (for decomposition)
        waves = self._estimate_waves(intents, dependencies)
        max_wave_size = max(len(w) for w in waves) if waves else num_tasks
        
        # Estimate CP-SAT variables (tasks × model types, assuming ~10 types)
        estimated_variables = num_tasks * 10
        
        # Compute complexity score (0-1)
        complexity_score = self._compute_complexity_score(
            num_tasks, dep_density, avg_chain_length
        )
        
        return ProblemCharacteristics(
            num_tasks=num_tasks,
            num_agents=num_agents,
            num_dependencies=num_dependencies,
            dep_density=dep_density,
            avg_chain_length=avg_chain_length,
            max_wave_size=max_wave_size,
            estimated_variables=estimated_variables,
            complexity_score=complexity_score
        )
    
    def recommend_solver(self, chars: ProblemCharacteristics) -> SolverType:
        """Recommend solver based on problem characteristics."""
        # Greedy for small, sparse problems
        if (chars.num_tasks <= self.GREEDY_MAX_TASKS and 
            chars.dep_density <= self.GREEDY_MAX_DEP_DENSITY):
            return SolverType.GREEDY
        
        # CP-SAT for medium problems
        if (chars.num_tasks <= self.CP_SAT_MAX_TASKS and 
            chars.dep_density <= self.CP_SAT_MAX_DEP_DENSITY):
            return SolverType.CP_SAT
        
        # Wave decomposition for large but decomposable problems
        if chars.num_tasks <= self.WAVE_MAX_TASKS:
            return SolverType.WAVE_DECOMPOSED
        
        # D-Wave hybrid for massive problems
        return SolverType.DWAVE_HYBRID
    
    def _extract_dependencies(self, intents: List[Dict]) -> List[Tuple[int, int]]:
        """Extract dependency edges from intents."""
        deps = []
        intent_idx = {intent.get('id', i): i for i, intent in enumerate(intents)}
        
        for i, intent in enumerate(intents):
            for dep in intent.get('depends', []):
                # Handle different dependency formats: int, str, or dict
                if isinstance(dep, int):
                    dep_id = dep
                elif isinstance(dep, str):
                    dep_id = dep
                elif isinstance(dep, dict):
                    dep_id = dep.get('intent')
                else:
                    continue
                
                # If dep_id is an int, use it directly as index
                if isinstance(dep_id, int):
                    if 0 <= dep_id < len(intents):
                        deps.append((dep_id, i))
                elif dep_id in intent_idx:
                    deps.append((intent_idx[dep_id], i))
        
        return deps
    
    def _compute_chain_lengths(self, intents: List[Dict], 
                               dependencies: List[Tuple[int, int]]) -> List[int]:
        """Compute length of each dependency chain."""
        # Build adjacency list
        graph = {i: [] for i in range(len(intents))}
        for src, dst in dependencies:
            graph[src].append(dst)
        
        # DFS to find longest path from each node
        memo = {}
        
        def longest_path(node):
            if node in memo:
                return memo[node]
            if not graph[node]:
                memo[node] = 1
                return 1
            length = 1 + max(longest_path(child) for child in graph[node])
            memo[node] = length
            return length
        
        return [longest_path(i) for i in range(len(intents))]
    
    def _estimate_waves(self, intents: List[Dict], 
                       dependencies: List[Tuple[int, int]]) -> List[List[int]]:
        """Estimate wave decomposition using Kahn's algorithm."""
        from collections import defaultdict, deque
        
        n = len(intents)
        graph = defaultdict(list)
        in_degree = [0] * n
        
        for src, dst in dependencies:
            graph[src].append(dst)
            in_degree[dst] += 1
        
        waves = []
        remaining = set(range(n))
        
        while remaining:
            # Find all nodes with no remaining dependencies
            wave = [i for i in remaining if in_degree[i] == 0]
            if not wave:
                # Circular dependency - put remaining in one wave
                wave = list(remaining)
                waves.append(wave)
                break
            
            waves.append(wave)
            
            # Remove this wave
            for i in wave:
                remaining.remove(i)
                for j in graph[i]:
                    in_degree[j] -= 1
        
        return waves
    
    def _compute_complexity_score(self, num_tasks: int, dep_density: float, 
                                  avg_chain_length: float) -> float:
        """Compute normalized complexity score (0-1)."""
        # Normalize each factor
        task_factor = min(num_tasks / 100000, 1.0)
        density_factor = min(dep_density * 10, 1.0)  # 0.1 density = max
        chain_factor = min(avg_chain_length / 10, 1.0)  # 10 avg = max
        
        # Weighted average
        return 0.4 * task_factor + 0.4 * density_factor + 0.2 * chain_factor


class HybridRouter:
    """Intelligent router that selects and orchestrates solvers."""
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize router with optional configuration.
        
        Args:
            config: Dictionary with keys:
                - greedy_time_limit: seconds (default: 5)
                - cp_sat_time_limit: seconds (default: 600)
                - wave_time_limit: seconds per wave (default: 300)
                - dwave_time_limit: seconds (default: 600)
                - enable_fallback: bool (default: True)
                - verbose: bool (default: True)
        """
        self.config = config or {}
        self.classifier = ProblemClassifier()
        
        # Time limits
        self.greedy_time_limit = self.config.get('greedy_time_limit', 5)
        self.cp_sat_time_limit = self.config.get('cp_sat_time_limit', 600)
        self.wave_time_limit = self.config.get('wave_time_limit', 300)
        self.dwave_time_limit = self.config.get('dwave_time_limit', 600)
        
        # Behavior
        self.enable_fallback = self.config.get('enable_fallback', True)
        self.verbose = self.config.get('verbose', True)
    
    def route(self, intents: List[Dict], agents: Dict, 
              agent_names: Optional[List[str]] = None,
              dependencies: Optional[List[Tuple[int, int]]] = None,
              force_solver: Optional[SolverType] = None) -> RouteResult:
        """Route intents to agents using the best solver.
        
        Args:
            intents: List of intent dictionaries
            agents: Dictionary of agent definitions
            agent_names: Optional list of agent names (extracted from agents if None)
            dependencies: Optional list of (src_idx, dst_idx) dependency tuples
            force_solver: Optional solver to force (overrides classification)
        
        Returns:
            RouteResult with assignments and metadata
        """
        if agent_names is None:
            agent_names = list(agents.keys())
        
        # Analyze problem
        chars = self.classifier.analyze(intents, agents, dependencies)
        
        if self.verbose:
            logger.info(f"Problem analysis: {chars.num_tasks} tasks, "
                       f"{chars.num_agents} agents, "
                       f"{chars.num_dependencies} deps "
                       f"(density: {chars.dep_density:.4f})")
            logger.info(f"Complexity score: {chars.complexity_score:.2f}")
        
        # Select solver
        if force_solver:
            solver_type = force_solver
        else:
            solver_type = self.classifier.recommend_solver(chars)
        
        if self.verbose:
            logger.info(f"Selected solver: {solver_type.name}")
        
        # Execute with fallback chain
        return self._solve_with_fallback(
            intents, agents, agent_names, dependencies, 
            solver_type, chars
        )
    
    def _solve_with_fallback(self, intents: List[Dict], agents: Dict,
                            agent_names: List[str], 
                            dependencies: Optional[List[Tuple[int, int]]],
                            primary_solver: SolverType,
                            chars: ProblemCharacteristics) -> RouteResult:
        """Try primary solver, fall back to simpler ones if needed."""
        
        solvers_to_try = self._get_fallback_chain(primary_solver)
        
        for solver_type in solvers_to_try:
            if self.verbose:
                logger.info(f"Attempting solve with {solver_type.name}...")
            
            result = self._execute_solver(
                solver_type, intents, agents, agent_names, dependencies
            )
            
            if result.success:
                if self.verbose:
                    logger.info(f"Success with {solver_type.name} "
                               f"({result.solve_time:.1f}s)")
                return result
            
            if self.verbose:
                logger.warning(f"{solver_type.name} failed: {result.violations}")
            
            if not self.enable_fallback:
                break
        
        # All solvers failed
        return RouteResult(
            success=False,
            assignments={},
            solver_used=primary_solver,
            solve_time=0,
            objective_value=None,
            gap=None,
            violations=["All solvers failed"],
            metadata={}
        )
    
    def _get_fallback_chain(self, primary: SolverType) -> List[SolverType]:
        """Get ordered list of solvers to try."""
        chains = {
            SolverType.GREEDY: [SolverType.GREEDY],
            SolverType.CP_SAT: [SolverType.CP_SAT, SolverType.GREEDY],
            SolverType.WAVE_DECOMPOSED: [
                SolverType.WAVE_DECOMPOSED, 
                SolverType.CP_SAT, 
                SolverType.GREEDY
            ],
            SolverType.DWAVE_HYBRID: [
                SolverType.DWAVE_HYBRID,
                SolverType.WAVE_DECOMPOSED,
                SolverType.CP_SAT,
                SolverType.GREEDY
            ]
        }
        return chains.get(primary, [primary])
    
    def _execute_solver(self, solver_type: SolverType, 
                       intents: List[Dict], agents: Dict,
                       agent_names: List[str],
                       dependencies: Optional[List[Tuple[int, int]]]) -> RouteResult:
        """Execute a specific solver."""
        start_time = time.time()
        
        try:
            if solver_type == SolverType.GREEDY:
                return self._solve_greedy(intents, agents, start_time)
            
            elif solver_type == SolverType.CP_SAT:
                return self._solve_cp_sat(intents, agents, agent_names, start_time)
            
            elif solver_type == SolverType.WAVE_DECOMPOSED:
                return self._solve_wave_decomposed(
                    intents, agents, agent_names, dependencies, start_time
                )
            
            elif solver_type == SolverType.DWAVE_HYBRID:
                return self._solve_dwave_hybrid(intents, agents, agent_names, start_time)
            
            else:
                raise ValueError(f"Unknown solver type: {solver_type}")
                
        except Exception as e:
            solve_time = time.time() - start_time
            return RouteResult(
                success=False,
                assignments={},
                solver_used=solver_type,
                solve_time=solve_time,
                objective_value=None,
                gap=None,
                violations=[str(e)],
                metadata={"error": str(e)}
            )
    
    def _solve_greedy(self, intents: List[Dict], agents: Dict,
                     start_time: float) -> RouteResult:
        """Solve using greedy heuristic."""
        assignments, cost = ortools_greedy(intents, agents)
        solve_time = time.time() - start_time
        
        # Validate
        violations = self._validate_assignments(assignments, intents, agents)
        
        return RouteResult(
            success=len(violations) == 0,
            assignments=assignments,
            solver_used=SolverType.GREEDY,
            solve_time=solve_time,
            objective_value=cost,
            gap=None,  # No optimality guarantee
            violations=violations,
            metadata={"num_assigned": len(assignments)}
        )
    
    def _solve_cp_sat(self, intents: List[Dict], agents: Dict,
                     agent_names: List[str], start_time: float) -> RouteResult:
        """Solve using OR-Tools CP-SAT."""
        assignments = solve_cpsat(
            intents, agents, agent_names, 
            time_limit=self.cp_sat_time_limit
        )
        solve_time = time.time() - start_time
        
        violations = self._validate_assignments(assignments, intents, agents)
        
        # Estimate cost
        total_cost = 0
        for intent_idx, agent_name in assignments.items():
            intent = intents[intent_idx]
            agent = agents[agent_name]
            total_cost += intent.get('estimated_tokens', 0) * agent.get('token_rate', 0)
        
        return RouteResult(
            success=len(assignments) == len(intents) and len(violations) == 0,
            assignments=assignments,
            solver_used=SolverType.CP_SAT,
            solve_time=solve_time,
            objective_value=total_cost,
            gap=None,  # Could extract from CP-SAT solver
            violations=violations,
            metadata={"num_assigned": len(assignments)}
        )
    
    def _solve_wave_decomposed(self, intents: List[Dict], agents: Dict,
                              agent_names: List[str],
                              dependencies: Optional[List[Tuple[int, int]]],
                              start_time: float) -> RouteResult:
        """Solve using wave decomposition + CP-SAT per wave."""
        if dependencies is None:
            dependencies = self.classifier._extract_dependencies(intents)
        
        # Build waves
        waves = self.classifier._estimate_waves(intents, dependencies)
        
        all_assignments = {}
        total_cost = 0
        wave_results = []
        
        for wave_idx, wave_indices in enumerate(waves):
            wave_intents = [intents[i] for i in wave_indices]
            
            # Create index mapping
            idx_map = {new_idx: old_idx for new_idx, old_idx in enumerate(wave_indices)}
            
            # Solve this wave
            wave_assignments = solve_cpsat(
                wave_intents, agents, agent_names,
                time_limit=self.wave_time_limit
            )
            
            # Map back to original indices
            for new_idx, agent_name in wave_assignments.items():
                old_idx = idx_map[new_idx]
                all_assignments[old_idx] = agent_name
                
                intent = intents[old_idx]
                agent = agents[agent_name]
                total_cost += intent.get('estimated_tokens', 0) * agent.get('token_rate', 0)
            
            wave_results.append({
                'wave': wave_idx,
                'size': len(wave_indices),
                'assigned': len(wave_assignments)
            })
        
        solve_time = time.time() - start_time
        violations = self._validate_assignments(all_assignments, intents, agents)
        
        return RouteResult(
            success=len(all_assignments) == len(intents) and len(violations) == 0,
            assignments=all_assignments,
            solver_used=SolverType.WAVE_DECOMPOSED,
            solve_time=solve_time,
            objective_value=total_cost,
            gap=None,
            violations=violations,
            metadata={
                "num_waves": len(waves),
                "wave_results": wave_results,
                "num_assigned": len(all_assignments)
            }
        )
    
    def _solve_dwave_hybrid(self, intents: List[Dict], agents: Dict,
                           agent_names: List[str], start_time: float) -> RouteResult:
        """Solve using D-Wave Leap hybrid sampler."""
        # Build CQM
        from .css_renderer_model import build_cqm
        from dwave.system import LeapHybridCQMSampler
        
        cqm, x_vars = build_cqm(intents, agents, agent_names)
        sampler = LeapHybridCQMSampler()
        sampleset = sampler.sample_cqm(cqm)
        
        # Extract assignments
        assignments = {}
        for intent_idx in range(len(intents)):
            for agent_name in agent_names:
                var_name = f"x_{intent_idx}_{agent_name}"
                if var_name in sampleset.first.sample:
                    if sampleset.first.sample[var_name] == 1:
                        assignments[intent_idx] = agent_name
                        break
        
        solve_time = time.time() - start_time
        violations = self._validate_assignments(assignments, intents, agents)
        
        return RouteResult(
            success=len(assignments) == len(intents) and len(violations) == 0,
            assignments=assignments,
            solver_used=SolverType.DWAVE_HYBRID,
            solve_time=solve_time,
            objective_value=sampleset.first.energy if assignments else None,
            gap=None,
            violations=violations,
            metadata={
                "qpu_access_time": sampleset.info.get('qpu_access_time', 'N/A'),
                "num_assigned": len(assignments)
            }
        )
    
    def _validate_assignments(self, assignments: Dict[int, str],
                             intents: List[Dict], agents: Dict) -> List[str]:
        """Validate assignments for constraint violations."""
        violations = []
        
        # Check all intents assigned
        for i in range(len(intents)):
            if i not in assignments:
                violations.append(f"Intent {i} not assigned")
        
        # Check agent capacities
        load = {}
        for intent_idx, agent_name in assignments.items():
            load[agent_name] = load.get(agent_name, 0) + 1
        
        for agent_name, count in load.items():
            capacity = agents[agent_name].get('capacity', float('inf'))
            if count > capacity:
                violations.append(
                    f"Agent {agent_name} overloaded: {count} > {capacity}"
                )
        
        # Check capabilities
        for intent_idx, agent_name in assignments.items():
            intent = intents[intent_idx]
            agent = agents[agent_name]
            
            if intent.get('complexity') not in agent.get('capabilities', set()):
                violations.append(
                    f"Intent {intent_idx} assigned to incapable agent {agent_name}"
                )
            
            if agent.get('quality', 0) < intent.get('min_quality', 0):
                violations.append(
                    f"Intent {intent_idx} quality requirement not met by {agent_name}"
                )
        
        return violations


# Convenience function for simple usage
def route_intents(intents: List[Dict], agents: Dict, 
                  **kwargs) -> RouteResult:
    """Simple interface to route intents using the hybrid router.
    
    Args:
        intents: List of intent dictionaries
        agents: Dictionary of agent definitions
        **kwargs: Passed to HybridRouter.route()
    
    Returns:
        RouteResult with assignments
    """
    router = HybridRouter()
    return router.route(intents, agents, **kwargs)


if __name__ == '__main__':
    # Test the hybrid router
    from quantum_routing.css_renderer_agents import build_agent_pool
    from quantum_routing.css_renderer_intents import generate_intents, build_workflow_chains
    
    print("Testing Hybrid Router for AI Intent Routing")
    print("=" * 60)
    
    # Build test data
    agents, agent_names = build_agent_pool()
    intents = generate_intents()
    workflow_chains = build_workflow_chains(intents)
    
    print(f"Generated {len(intents)} intents")
    print(f"Agent pool: {len(agent_names)} agents")
    
    # Create router
    router = HybridRouter(config={'verbose': True})
    
    # Route
    result = router.route(intents, agents, agent_names)
    
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Success: {result.success}")
    print(f"Solver used: {result.solver_used.name}")
    print(f"Solve time: {result.solve_time:.2f}s")
    print(f"Tasks assigned: {len(result.assignments)}/{len(intents)}")
    if result.objective_value:
        print(f"Objective value: ${result.objective_value:.2f}")
    if result.violations:
        print(f"Violations: {len(result.violations)}")
        for v in result.violations[:5]:
            print(f"  - {v}")
    print(f"Metadata: {result.metadata}")
