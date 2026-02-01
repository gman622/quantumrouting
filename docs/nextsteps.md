# QAAS Next Steps
## What We Learned

- CQM scales to 1000 intents: build 2.6s, CQM→BQM conversion 2.1s, SA 116s
- 19.5M quadratic terms — capacity constraints dominate (each cloud agent valid for ~800+ tasks)
- Greedy is hard to beat on pure cost when quality bars already enforce natural ordering
- The real value of annealing shows up when constraints conflict — need multi-objective tradeoffs
- At 1000 intents, this is approaching the limit of what local SA handles in a few minutes
- 147 overkill instances — simple tasks often routed to expensive cloud agents

## Next Steps

### 1. Token-Based Costs (Priority)

Real cost depends on output tokens, not flat per-task. This creates more optimization pressure.

```python
# Estimate tokens based on task complexity and length
TOKEN_RATES = {
    'claude': 0.003,   # $3/million tokens
    'gpt5.2': 0.005,
    'gemini': 0.0005,
    'kimi2.5': 0.0002,
}

def estimate_tokens(task):
    # Simple tasks: 200-500 tokens
    # Moderate: 500-2000 tokens
    # Complex: 2000-10000+ tokens
    complexity_multipliers = {
        'simple': 500,
        'moderate': 2000,
        'complex': 8000,
        'reasoning': 5000,
        'code-analysis': 3000,
    }
    return complexity_multipliers.get(task['complexity'], 1000)

def get_cost(intent, agent_name):
    agent = agents[agent_name]
    tokens = estimate_tokens(intent)
    token_cost = tokens * TOKEN_RATES.get(agent_name.split('-')[0], 0.001)
    
    # Existing cost components
    quality_surplus = agent['quality'] - intent['min_quality']
    overkill_cost = quality_surplus * token_cost * 2
    latency_cost = agent['latency'] * 0.001
    
    return token_cost + overkill_cost + latency_cost
```

**Why this matters:**
- A typo fix (200 tokens on Claude) costs $0.0006
- A complex feature (8000 tokens on Claude) costs $0.024
- Same agent, 40x cost difference — optimizer must factor task size
- Greedy's simple "pick cheapest agent" fails when task sizes vary

### 2. Add Deadlines

Urgent tasks should be prioritized even if it costs more.

```python
{'id': 'fix-prod-bug', 'complexity': 'complex', 'deadline': 1}     # urgent
{'id': 'refactor-utils', 'complexity': 'moderate', 'deadline': 100} # flexible

deadline_cost = max(0, (max_deadline - task_deadline) / max_deadline) * DEADLINE_WEIGHT
```

### 3. Context Affinity

Same agent doing related tasks avoids context switching overhead.

```python
CONTEXT_BONUS = 0.5
for (a, b) in dependency_edges:
    for j in range(num_agents):
        if (a, j) in x and (b, j) in x:
            objective -= CONTEXT_BONUS * x[a, j] * x[b, j]
```

### 4. Run on D-Wave Leap

At 40k+ variables, the hybrid solver should outperform local SA. Submit the CQM directly.

```python
sampler = LeapHybridCQMSampler()
sampleset = sampler.sample_cqm(cqm, time_limit=60)
feasible = sampleset.filter(lambda s: s.is_feasible)
```

### 5. Integrate into Intenter

Wire QAAS into the VS Code extension as an optional optimizer.

```
IntentWatcher detects pending .intent files
  → IntenteratorAgent.routeWithOptimizer(intents)
    → Build CQM from intent schemas
    → Solve (local SA or D-Wave hybrid)
    → Return assignments
  → Dispatch to agent terminals
```

**Files to modify:**
- `src/agents/IntenteratorAgent.ts` — add quantum routing option
- `src/intents/IntentSchema.ts` — add quality/deadline/token fields
- `src/intents/IntentWatcher.ts` — batch intents for optimization
- New: `src/routing/QAASRouter.ts` — CQM builder + solver

## Priority Order

1. **Token-based costs** — realistic cost model creates optimization pressure
2. **Add deadlines + context affinity** — richer multi-objective function
3. **Run on D-Wave Leap** — hybrid solver at this scale should beat SA
4. **Integrate into Intenter** — ship it
