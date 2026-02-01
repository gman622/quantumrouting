# QAAS: Quantum Agent Annealed Swarm

## Problem

Routing tasks to agents in a large swarm is a combinatorial optimization problem. With N intents and M agents, the solution space is M^N. Greedy heuristics (current Intenterator) work for small swarms but don't scale.

## Concept

Use quantum annealing to find optimal task-to-agent assignments across the entire swarm simultaneously.

## QUBO Formulation

### Decision Variables

```
x_ij = 1 if intent i is assigned to agent j, else 0
```

### Objective Function

```
Minimize:
  Σ_ij cost_ij × x_ij           # total execution cost
  + Σ_ij latency_ij × x_ij      # total latency
  + λ₁ × constraint_violations   # penalties
```

### Constraints (encoded as penalties)

1. **Assignment**: Each intent assigned to exactly one agent
   ```
   Σ_j x_ij = 1  for all i
   ```

2. **Capacity**: Agent j can handle at most cap_j concurrent tasks
   ```
   Σ_i x_ij ≤ cap_j  for all j
   ```

3. **Capabilities**: Intent i only assigned to agent j if j has required capabilities
   ```
   x_ij = 0  if capabilities_i ⊄ capabilities_j
   ```

4. **Privacy**: Private intents only assigned to local agents
   ```
   x_ij = 0  if private_i AND cloud_j
   ```

5. **Dependencies**: Intent i must complete before intent k starts
   ```
   encoded via ordering constraints in batch scheduling
   ```

## Cost Matrix

```
cost_ij = base_cost_j
        + token_rate_j × estimated_tokens_i
        + capability_mismatch_penalty
        + complexity_factor
```

| Agent Type | Base Cost | Token Rate | Capabilities |
|------------|-----------|------------|--------------|
| ollama-1b  | 0         | 0          | simple tasks |
| ollama-7b  | 0         | 0          | moderate tasks |
| claude     | 0.01      | 0.00001    | complex, long-context, code |

## Hybrid Solver Approach

For swarms larger than qubit capacity:

1. **Decomposition**: Partition problem into subproblems that fit on QPU
2. **Classical preprocessing**: Eliminate obvious assignments (privacy, capability mismatches)
3. **Quantum core**: Solve hard combinatorial subproblem via annealing
4. **Classical postprocessing**: Validate and refine solution

D-Wave Hybrid Solvers handle this automatically - submit full problem, solver decides what runs on QPU vs classical.

## Scale Estimates

| Swarm Size | Variables | Fits on 2048 QPU | Fits on 5000 QPU | Hybrid |
|------------|-----------|------------------|------------------|--------|
| 10 agents × 20 intents | 200 | Yes | Yes | Yes |
| 50 agents × 100 intents | 5000 | No | Marginal | Yes |
| 100 agents × 1000 intents | 100,000 | No | No | Yes |

## Implementation Path

1. **Phase 1**: Formulate routing as QUBO, test on D-Wave Leap with toy problems
2. **Phase 2**: Benchmark quantum vs greedy heuristic on increasing swarm sizes
3. **Phase 3**: Integrate hybrid solver into Intenterator as optional optimizer
4. **Phase 4**: Real-time streaming - re-optimize as new intents arrive

## Research Questions

- At what swarm size does quantum routing outperform greedy?
- Can we maintain solution quality with streaming intent arrival?
- How does annealing time trade off against solution quality?
- Can we encode agent learning/improvement over time?

## References

- D-Wave Ocean SDK: https://docs.ocean.dwavesys.com/
- QUBO formulation guide: https://docs.dwavesys.com/docs/latest/
- Hybrid solver documentation: https://docs.ocean.dwavesys.com/en/stable/docs_hybrid/
