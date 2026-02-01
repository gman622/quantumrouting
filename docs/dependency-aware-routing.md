# Dependency-Aware Quantum Routing

How QAAS handles intent dependencies when optimizing task assignment.

## The Problem

Some intents depend on others:

```yaml
---
@id: generate-report
@depends:
  - fetch-data
  - run-analysis
---
Generate a report from the analysis results...
```

The router can't assign `generate-report` until `fetch-data` and `run-analysis` complete. This adds ordering constraints to the optimization.

## Dependency Syntax

### Simple (blocking by default)

```yaml
@depends:
  - fetch-data
  - run-analysis
```

### With options

```yaml
@depends:
  - intent: fetch-data
    outputs: [raw_data]
    blocking: true
  - intent: validate-schema
    outputs: [is_valid]
    blocking: false  # can run in parallel, just needs the output eventually
```

## Wave-Based Routing

The simplest approach: solve in waves.

### Algorithm

1. **Build dependency graph** from all pending intents
2. **Topological sort** to find execution order
3. **Group into waves** - intents with no unfinished dependencies
4. **Optimize each wave** independently with quantum annealer
5. **Execute wave**, collect outputs
6. **Repeat** for next wave

### Example

```
Intents:
  A: no dependencies
  B: no dependencies
  C: depends on A
  D: depends on A, B
  E: depends on C, D

Wave 1: [A, B]      → quantum optimize assignment
Wave 2: [C, D]      → quantum optimize (after wave 1 completes)
Wave 3: [E]         → quantum optimize (after wave 2 completes)
```

### Python Implementation

```python
from collections import defaultdict, deque

def build_waves(intents: list[dict]) -> list[list[str]]:
    """Group intents into dependency waves using Kahn's algorithm."""

    # Build adjacency and in-degree
    graph = defaultdict(list)
    in_degree = {i['id']: 0 for i in intents}
    intent_map = {i['id']: i for i in intents}

    for intent in intents:
        for dep in intent.get('depends', []):
            dep_id = dep if isinstance(dep, str) else dep['intent']
            graph[dep_id].append(intent['id'])
            in_degree[intent['id']] += 1

    # Process waves
    waves = []
    while in_degree:
        # Find all intents with no remaining dependencies
        wave = [id for id, deg in in_degree.items() if deg == 0]

        if not wave:
            raise ValueError("Circular dependency detected")

        waves.append(wave)

        # Remove this wave from consideration
        for id in wave:
            del in_degree[id]
            for successor in graph[id]:
                if successor in in_degree:
                    in_degree[successor] -= 1

    return waves


def route_with_waves(intents, agents):
    """Route intents using wave-based quantum optimization."""
    waves = build_waves(intents)
    all_assignments = {}

    for wave_num, wave in enumerate(waves):
        print(f"Wave {wave_num + 1}: {wave}")

        # Get intents for this wave
        wave_intents = [i for i in intents if i['id'] in wave]

        # Quantum optimize this wave
        assignments = quantum_optimize(wave_intents, agents)
        all_assignments.update(assignments)

        # Execute wave (in real system, wait for completion)
        execute_wave(wave_intents, assignments)

    return all_assignments
```

## Constraint-Based Routing (Advanced)

For finer control, encode dependencies directly in the QUBO.

### Time-Indexed Formulation

Add time slots and constrain start times:

```
x_ijt = 1 if intent i assigned to agent j starting at time t

Constraint: if i depends on k, then start_i > end_k
```

This explodes the variable count (intents × agents × time_slots) but allows the quantum solver to optimize globally.

### Precedence Constraints

For simple precedence without time slots:

```
If intent B depends on intent A:
  - If A and B assigned to SAME agent: A must be in earlier position
  - If A and B assigned to DIFFERENT agents: B's agent must wait for A's completion signal
```

This is harder to encode in QUBO without time indices.

## Hybrid Approach: Waves + Intra-Wave Optimization

Best of both worlds:

1. **Waves** handle inter-intent dependencies (simple, always correct)
2. **Quantum optimization** handles agent assignment within each wave (where the hard optimization is)

```
┌─────────────────────────────────────────────────────┐
│  Wave 1: [A, B, C]                                  │
│  ┌─────────────────────────────────────────────┐    │
│  │  Quantum Optimizer                          │    │
│  │  - 3 intents × 5 agents = 15 variables     │    │
│  │  - Minimize cost, respect capacity         │    │
│  │  - Output: A→agent1, B→agent2, C→agent1    │    │
│  └─────────────────────────────────────────────┘    │
│  Execute in parallel...                             │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  Wave 2: [D, E] (depend on wave 1)                  │
│  ┌─────────────────────────────────────────────┐    │
│  │  Quantum Optimizer                          │    │
│  │  - 2 intents × 5 agents = 10 variables     │    │
│  │  - Can now use outputs from A, B, C        │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

## Non-Blocking Dependencies

Some dependencies just need data, not strict ordering:

```yaml
@depends:
  - intent: fetch-schema
    blocking: false  # start anyway, just need the output eventually
```

For non-blocking deps:
- Assign intent immediately
- Agent waits for data before using it
- Enables more parallelism

## Integration with Intenterator

Update the router to be dependency-aware:

```typescript
// In IntenteratorAgent.ts

async routeWithDependencies(intents: ParsedIntent[]): Promise<RoutingResult[]> {
    // Build dependency graph
    const graph = this.buildDependencyGraph(intents);

    // Get waves
    const waves = this.topologicalWaves(graph);

    const results: RoutingResult[] = [];

    for (const wave of waves) {
        // Option 1: Use existing greedy router per wave
        for (const intent of wave) {
            results.push(this.analyzeIntent(intent.content, intent.filePath));
        }

        // Option 2: Use quantum optimizer for wave (when available)
        // const waveResults = await this.quantumOptimize(wave);
        // results.push(...waveResults);
    }

    return results;
}
```

## Scaling Considerations

| Approach | Variables per Wave | Best For |
|----------|-------------------|----------|
| Wave + Greedy | N/A | Small swarms, fast |
| Wave + Quantum | intents × agents | Medium swarms, optimal |
| Full Time-Indexed | intents × agents × time_slots | Research only |

For most real workloads, **Wave + Quantum** is the sweet spot:
- Waves handle dependencies correctly
- Quantum optimizes the hard part (assignment)
- Scales with hybrid solvers
