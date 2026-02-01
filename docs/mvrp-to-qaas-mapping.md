# MVRP to QAAS Mapping

How D-Wave's Multi-Vehicle Routing Problem (MVRP) maps to Quantum Agent Annealed Swarm (QAAS).

## The Insight

Vehicle routing and agent task routing are the same optimization problem with different names.

## Concept Mapping

| MVRP (D-Wave) | QAAS (Intenter) | Description |
|---------------|-----------------|-------------|
| Vehicle | Agent | The worker that handles tasks |
| Client/Location | Intent | A task to be completed |
| Depot | - | Not needed (agents don't return home) |
| Capacity | Agent Load Limit | Max concurrent tasks per agent |
| Demand | Task Weight | Complexity/resource requirement |
| Distance/Cost | Execution Cost | Cost to assign intent to agent |
| Route | Assignment Batch | Set of intents assigned to one agent |

## Problem Structure

**MVRP asks:** Given vehicles with capacity limits and clients with demands, find routes that minimize total travel distance while satisfying all demands.

**QAAS asks:** Given agents with load limits and intents with complexity weights, find assignments that minimize total cost while completing all intents.

## Key Difference: No Ordering

MVRP cares about *order* - vehicles visit clients in sequence, so distance between stops matters.

QAAS (basic version) doesn't care about order - agents execute intents in parallel or in any order. This *simplifies* the problem:

- MVRP = Assignment + TSP (Traveling Salesman per route)
- QAAS = Assignment only

This means QAAS can use just the **clustering** step from MVRP, skipping the TSP step entirely.

## Cost Function Differences

### MVRP Cost
```
cost(client_i, client_j) = physical distance between locations
```

### QAAS Cost
```
cost(intent_i, agent_j) = base_cost_j
                        + token_rate_j × tokens_i
                        + capability_mismatch_penalty
                        + privacy_violation_penalty
```

QAAS cost is intent-to-agent, not intent-to-intent. This changes the formulation slightly.

## Constraints Comparison

| Constraint | MVRP | QAAS |
|------------|------|------|
| Each task assigned once | Each client visited by exactly one vehicle | Each intent assigned to exactly one agent |
| Capacity | Vehicle can't carry more than capacity | Agent can't exceed concurrent task limit |
| Capability | All vehicles can visit all clients | Some agents can't handle some intents (complexity, privacy) |
| Privacy | N/A | Private intents must stay on local agents |
| Dependencies | Visit order within route | Intent A must complete before Intent B starts |

## D-Wave Solvers for QAAS

### Option 1: NL Hybrid Solver (Recommended)

Use the built-in generator, treating agents as vehicles:

```python
from dwave.optimization.generators import capacitated_vehicle_routing
from dwave.system import LeapHybridNLSampler

# demand[i] = complexity weight of intent i
# capacity = max load per agent
# distances[i][j] = cost matrix

model = capacitated_vehicle_routing(
    demand=intent_weights,
    num_vehicles=num_agents,
    vehicle_capacity=agent_capacity,
    distances=cost_matrix
)

sampler = LeapHybridNLSampler()
sampler.sample(model, time_limit=10)
```

### Option 2: DQM for Clustering Only

If you don't need ordering (QAAS usually doesn't):

```python
from dimod import DiscreteQuadraticModel
from dwave.system import LeapHybridDQMSampler

dqm = DiscreteQuadraticModel()

# Variable for each intent: which agent handles it?
for intent in intents:
    dqm.add_variable(num_agents, intent.id)

# Add capacity constraints
# Add cost objectives
# ...

sampler = LeapHybridDQMSampler()
result = sampler.sample_dqm(dqm, time_limit=10)
```

### Option 3: BQM (Binary Quadratic Model)

For finer control, build the QUBO manually (see `quantum-routing.ipynb`).

## Extending Beyond MVRP

QAAS has features MVRP doesn't model:

| Feature | How to Handle |
|---------|---------------|
| **Capability constraints** | Pre-filter: set `cost[i][j] = ∞` if agent j can't handle intent i |
| **Privacy constraints** | Pre-filter: set `cost[i][j] = ∞` if intent i is private and agent j is cloud |
| **Intent dependencies** | Add ordering constraints or solve in waves (phase 1 intents, then phase 2) |
| **Heterogeneous agents** | Different capacities per agent (already supported) |
| **Dynamic arrivals** | Re-solve periodically as new intents arrive |

## Implementation Path

1. **Start simple**: Use `capacitated_vehicle_routing` with uniform agents
2. **Add constraints**: Pre-filter cost matrix for capability/privacy
3. **Benchmark**: Compare quantum vs greedy at different scales
4. **Extend**: Add dependencies, dynamic re-optimization
5. **Integrate**: Plug into Intenterator as optional optimizer

## References

- D-Wave MVRP example: `/Users/gman/Git/mvrp/`
- D-Wave CVRP generator: https://docs.ocean.dwavesys.com/en/stable/docs_optimization/reference/generated/dwave.optimization.generators.capacitated_vehicle_routing.html
- QAAS notebook: `./quantum-routing.ipynb`
