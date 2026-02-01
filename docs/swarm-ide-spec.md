# IIDE Specification
## Integrated Intent Decomposition Environment

---

## Core Philosophy

**You don't edit files. You orchestrate outcomes.**

The Swarm IDE replaces the file-centric paradigm with an **intent-centric** interface. Files become implementation details; what matters is defining goals, constraints, and letting the swarm execute.

---

## Interface Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  IIDE                                                           [$12.40/hr] │
├──────────────────┬──────────────────────────────┬───────────────────────────┤
│                  │                              │                           │
│  INTENT TREE     │   SWARM VISUALIZER           │   CONSTRAINT DASHBOARD    │
│                  │                              │                           │
│  🔷 epic-001     │   ┌─────────────────────┐    │   Budget: $50/day    [▓▓░]│
│  ├──🔶 task-1    │   │   AGENT POOL        │    │   Quality: >0.85     [▓▓▓]│
│  │  ├──✓ leaf-1  │   │                     │    │   Deadline: 3 days   [▓▓░]│
│  │  └──🔄 leaf-2  │   │  [C1] [C2] [C3]    │    │                           │
│  └──🔶 task-2    │   │  [K1] [K2] [G1]    │    │   [Optimize] [Pause]      │
│     └──⏳ leaf-3  │   │  [L1] [L2] ...     │    │                           │
│                  │   │                     │    │   Quantum: ON      [✓]    │
│  [+ New Epic]    │   │  6/50 active        │    │   Auto-decompose:  [✓]    │
│                  │   │  $2.40/hr current   │    │   Max depth: 4     [━━━]  │
│                  │   └─────────────────────┘    │                           │
│                  │                              │                           │
│                  │   ┌─────────────────────┐    │   ROUTER STATUS           │
│                  │   │   DEPENDENCY GRAPH  │    │   ━━━━━━━━━━━━━━          │
│                  │   │         ╱╲            │    │   CP-SAT:     23 solves   │
│                  │   │        ╱  ╲           │    │   Wave:        7 solves   │
│                  │   │       ╱    ╲          │    │   Quantum:     2 solves   │
│                  │   │      ●──────●         │    │   Fallback:    1 used     │
│                  │   │       \    /          │    │                           │
│                  │   │        \  /           │    │   Avg solve:   1.2s       │
│                  │   │         ╲╱            │    │   Cost saved:  $18.40     │
│                  │   └─────────────────────┘    │                           │
│                  │                              │                           │
├──────────────────┴──────────────────────────────┴───────────────────────────┤
│                                                                             │
│  OUTCOME VALIDATOR                                                          │
│  ━━━━━━━━━━━━━━━━━━                                                         │
│                                                                             │
│  ✅ epic-001: Authentication Service                                        │
│     Tests: 23/23 passed                                                     │
│     Coverage: 87%                                                           │
│     Cost: $8.40 (budget: $50)                                               │
│     Time: 2.3 hours                                                         │
│                                                                             │
│  ⚠️  epic-002: Payment Integration                                          │
│     Blocked: Waiting for API keys                                           │
│     Estimated: $12.00                                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Panel 1: Intent Tree

**What you see:**
- Hierarchical view of epics → tasks → leaf intents
- Real-time status: ⏳ pending | 🔄 in-progress | ✓ complete | ⚠️ blocked
- Cost accumulator per branch
- Assignment indicator (which agent is working on it)

**What you do:**
- Click to expand/collapse decomposition
- Drag to reprioritize
- Right-click to adjust constraints
- Double-click to view intent details

**Intent Detail View:**
```yaml
---
@id: implement-oauth2
@parent: build-auth-service
@complexity: complex
@budget: $10
@deadline: 2025-02-10
@min_quality: 0.85
@assigned_to: claude-3
@status: in_progress
@started: 2025-01-30T14:23:00Z
@estimated_cost: $8.40
@actual_cost: $2.10
---

Implement OAuth2 flow with PKCE support
```

---

## Panel 2: Swarm Visualizer

**Agent Pool Grid:**
- Each cell represents an agent instance
- Color-coded by model type (Claude=purple, GPT=blue, Local=green)
- Animated when active
- Hover for details: current task, cost/hr, success rate

**Dependency Graph:**
- D3.js force-directed layout
- Nodes = intents, Edges = dependencies
- Critical path highlighted in red
- Bottlenecks pulse

**Live Metrics:**
- Active agents / total pool
- Current burn rate ($/hr)
- Queue depth (waiting intents)
- Quantum routing events

---

## Panel 3: Constraint Dashboard

**Sliders:**
```
Budget:      [━━━●━━━━] $50/day        [Auto-adjust]
Quality:     [▓▓▓▓●▓▓▓] >0.85          [Strict|Balanced|Fast]
Deadline:    [━━●━━━━━] 3 days         [Calendar picker]
Parallelism: [▓▓▓●▓▓▓▓] 12 agents     [Max: 50]
```

**Toggles:**
- ☑ Quantum routing (fallback to D-Wave for hard problems)
- ☑ Auto-decompose (let decomposition agent break down epics)
- ☑ Cost alerts (notify at 80% budget)
- ☐ Dry run (estimate cost without executing)

**Action Buttons:**
- **[Optimize]** — re-run router with current constraints
- **[Pause]** — halt new assignments, finish in-progress
- **[Emergency Stop]** — cancel all, preserve state

---

## Panel 4: Outcome Validator

**Per-Epic Summary:**
```
┌────────────────────────────────────────────────────────┐
│ epic-001: Authentication Service              [✓ DONE] │
├────────────────────────────────────────────────────────┤
│ Tests:     23/23 passed                    [View logs] │
│ Coverage:  87%                             [View report]│
│ Security:  0 vulnerabilities               [Scan details]│
│ Cost:      $8.40 / $50 budget (17%)                    │
│ Time:      2.3 hours                                   │
│ Agents:    claude-3(4), kimi2.5-7(2), llama-8b(1)      │
│ Solver:    CP-SAT (optimal)                            │
└────────────────────────────────────────────────────────┘
```

**Validation Criteria:**
- Functional tests pass
- Performance benchmarks met
- Security scan clean
- Cost within budget
- Code review (automated + sampled human)

---

## Key Interactions

### 1. Create New Epic
```
[Ctrl+N] or [+ New Epic]
→ Opens intent composer
→ You write: "Build payment processing with Stripe"
→ Decomposition agent suggests breakdown
→ Router estimates cost/time
→ You approve or adjust constraints
→ Swarm begins execution
```

### 2. Tune Router Parameters
```
Click [Advanced] in dashboard
→ Shows hybrid router config
→ Adjust thresholds:
   Greedy max tasks: 500
   CP-SAT time limit: 600s
   Wave max size: 1000
   Quantum trigger: frustration > 0.7
→ [Apply] to re-optimize queue
```

### 3. Debug Blocked Intent
```
Click ⏳ blocked intent
→ Shows dependency chain
→ Highlights what's waiting
→ Option to:
   - View blocking intent details
   - Force reassign to different agent
   - Override dependency (risky)
   - Escalate to quantum solver
```

### 4. Review Quantum Routing Event
```
Notification: "Quantum solver used for epic-007"
Click to view:
→ Problem characteristics (frustration score: 0.82)
→ Classical attempts failed after 600s
→ D-Wave solution found in 45s
→ Cost savings: $3.20
→ [View QPU access log]
```

---

## Backend Integration

**Your Existing Components:**
- `decomposition-ide.ipynb` → Intent composer backend
- `hybrid_router.py` → Router API
- `css_renderer_*` modules → Agent pool definitions
- D-Wave Leap → Quantum fallback

**New Components Needed:**
- WebSocket server for real-time updates
- Intent database (SQLite/PostgreSQL)
- Agent execution orchestrator
- Cost tracking service
- Outcome validator (test runner + linter + security scan)

---

## File vs Intent: The Paradigm Shift

| Traditional IDE | IIDE |
|-----------------|-----------|
| Open file | Open epic |
| Edit code | Adjust constraints |
| Run debugger | Monitor swarm |
| Git commit | Intent checkpoint |
| Code review | Outcome validation |
| Build error | Constraint violation |
| Refactor | Re-decompose |
| Find references | Trace dependencies |

---

## MVP Features (Week 1)

1. Intent tree viewer (read-only from existing intents)
2. Agent pool status (mock data)
3. Constraint sliders (UI only)
4. Epic creation flow (integrate decomposition agent)
5. Basic outcome display (cost/time)

## V1 Features (Month 1)

1. Live agent status from actual executions
2. Router integration (real optimization)
3. Dependency graph visualization
4. Outcome validation pipeline
5. Quantum routing events display

## V2 Features (Quarter 1)

1. Multi-user swarm sharing
2. Historical cost analysis
3. Agent performance tuning
4. Custom constraint languages
5. Mobile companion app

---

This is IIDE — the Integrated Intent Decomposition Environment. Files are invisible; outcomes are everything.
