# Quantum-Only Agent Routing Specification
## Browser-From-Scratch: 1M Task Problem

### Current Problem Analysis (1K Tasks)

The existing QAAS system solves a **Constrained Quadratic Model (CQM)** with:
- **41,600 binary variables** (valid assignments only)
- **65,065 quadratic penalty terms** (dependency quality ordering)
- **1,048 linear constraints** (assignment + capacity)
- **Complexity**: NP-hard (generalized assignment with quadratic penalties)

**Classical solvers work because**:
- CQM-to-BQM conversion produces ~42K variables
- Simulated annealing handles this in 111 seconds
- Greedy finds "good enough" solutions (97% valid)

---

## What Makes a Problem "Quantum-Only"

A problem becomes quantum-advantaged when classical methods face:

### 1. **Exponential State Space Explosion**
| Tasks | Agents | Valid Assignments | Classical Viability |
|-------|--------|-------------------|---------------------|
| 1K    | 48     | 4.2 × 10⁴         | Easy (SA: 111s)     |
| 10K   | 100    | 5.0 × 10⁵         | Moderate            |
| 100K  | 500    | 2.5 × 10⁷         | Hard                |
| **1M**| **2K** | **5.0 × 10⁸**     | **Infeasible**      |

### 2. **Long-Range Correlation Constraints**
Current model has only **local** dependencies (chain-based). To break classical solvers, we need:
- **Global resource contention** (shared memory, build artifacts)
- **Cross-team synchronization** (API contracts, schema changes)
- **Temporal constraints** (deadlines, release trains)

### 3. **Rugged Energy Landscape**
Classical local search (SA, tabu) gets stuck in local minima when:
- Constraints create **frustrated systems** (satisfying A prevents satisfying B)
- **Glassy landscapes** with exponentially many local minima

---

## 1M-Task Browser Architecture

### Task Taxonomy (Chromium-scale)

Building a browser from scratch requires ~1 million tasks across these domains:

```
┌─────────────────────────────────────────────────────────────────┐
│                    BROWSER ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────┤
│  Layer 1: Platform Abstraction (200K tasks)                     │
│    ├── IPC / Mojo bindings (50K)                                │
│    ├── Sandboxing (30K)                                         │
│    ├── Process management (40K)                                 │
│    ├── Memory management (50K)                                  │
│    └── Threading / scheduling (30K)                             │
│                                                                 │
│  Layer 2: Rendering Engine (300K tasks)                         │
│    ├── HTML/CSS parser (60K)                                    │
│    ├── DOM implementation (80K)                                 │
│    ├── Layout engine (70K)                                      │
│    ├── Compositor / GPU (60K)                                   │
│    └── Accessibility (30K)                                      │
│                                                                 │
│  Layer 3: JavaScript Engine (200K tasks)                        │
│    ├── Parser / AST (40K)                                       │
│    ├── Bytecode compiler (50K)                                  │
│    ├── JIT compiler (60K)                                       │
│    ├── Garbage collector (30K)                                  │
│    └── Runtime / builtins (20K)                                 │
│                                                                 │
│  Layer 4: Network Stack (150K tasks)                            │
│    ├── HTTP/2/3 implementation (50K)                            │
│    ├── TLS / certificate handling (40K)                         │
│    ├── Caching layer (30K)                                      │
│    └── WebSocket / WebRTC (30K)                                 │
│                                                                 │
│  Layer 5: Security & Features (150K tasks)                      │
│    ├── CSP / CORS / SOP (40K)                                   │
│    ├── Permission system (30K)                                  │
│    ├── Storage APIs (40K)                                       │
│    └── Extension system (40K)                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Constraint Classes That Break Classical Solvers

#### 1. **Layer Dependency DAG**
Each layer depends on the layer below. This creates a **deep dependency graph**:
```
Layer 5 → Layer 4 → Layer 3 → Layer 2 → Layer 1
```
Cross-layer dependencies: ~500K edges

#### 2. **Interface Contracts (Global Constraints)**
When Layer 3 changes an API signature, all callers in Layers 4-5 must update:
- **Fan-out**: 1 API change → 10K-100K dependent tasks
- **Fan-in**: 100 components → 1 shared interface

This creates **all-to-all coupling** that greedy cannot optimize locally.

#### 3. **Resource Contention (Quadratic Constraints)**
Build artifacts, test runners, and CI slots are shared:
```
If Task A uses Build-Server-X AND Task B uses Build-Server-X
→ Conflict penalty: M * x_A * x_B
```

With 1M tasks and 10K shared resources → **10B quadratic terms**

#### 4. **Temporal Release Constraints**
Features must ship in specific release trains:
```
Sum of story points in Release-N must equal Target-N
```
This is a **hard global equality constraint** across 200K tasks.

#### 5. **Team Skill Matching (Bipartite Matching at Scale)**
200 teams × 5K agents = 1M agent pool
Each task requires specific expertise combinations:
```
Task requires: (C++ AND GPU) OR (Rust AND Security)
```
This is **3-SAT embedded in assignment** — NP-complete and hard to approximate.

---

## Problem Scale Summary

| Metric | Current (1K) | Target (1M) | Growth |
|--------|--------------|-------------|--------|
| Tasks | 1,000 | 1,000,000 | 1000× |
| Agents | 48 | 1,000,000 | 20000× |
| Binary variables | 4.2 × 10⁴ | 5.0 × 10⁸ | 12000× |
| Quadratic terms | 6.5 × 10⁴ | 1.0 × 10¹⁰ | 150000× |
| Linear constraints | 1,048 | 2,000,000 | 1900× |
| **Problem class** | NP-hard | **NP-hard, glassy** | — |

---

## Why Classical Solvers Fail at 1M Tasks

### Simulated Annealing
- **Time per sweep**: O(variables + quadratic terms) = O(10¹⁰)
- **Sweeps needed**: ~10⁶ for glassy landscape
- **Total time**: 10¹⁶ operations ≈ **years**

### Integer Linear Programming (Gurobi/CPLEX)
- **Memory for Q matrix**: 10¹⁰ terms × 8 bytes = **80 GB**
- **Branch-and-bound tree**: Exponential in constraints
- **Practical limit**: ~100K variables

### Greedy / Local Search
- **Dependency violations**: ~50K (5% of tasks)
- **Resource conflicts**: ~100K (unresolvable locally)
- **Result**: 15% of tasks invalid, requires manual rework

---

## D-Wave Hybrid Advantage

The D-Wave **LeapHybridCQMSampler** uses:

### 1. **Problem Decomposition**
- Splits 1M tasks into ~100 subproblems
- Each subproblem: 10K tasks → fits on Advantage QPU

### 2. **Quantum Annealing per Subproblem**
- **QPU access**: 20ms per subproblem
- **Coherent evolution**: Explores landscape globally
- **Tunneling**: Escapes local minima classical SA cannot

### 3. **Classical Post-Processing**
- Combines subproblem solutions
- Resolves boundary conflicts
- Iterates until global convergence

### Expected Performance
| Phase | Time | Classical Equivalent |
|-------|------|---------------------|
| Decomposition | 10s | Hours (graph partitioning) |
| QPU solves (×100) | 2s | Days (SA on each) |
| Classical merge | 60s | Fails (global constraints) |
| **Total** | **~2 minutes** | **Infeasible** |

---

## Success Criteria

A valid solution must satisfy:

1. **All 1M tasks assigned** (no drops)
2. **Zero dependency violations** (Layer N before Layer N+1)
3. **Zero resource conflicts** (no double-booked build servers)
4. **Release targets met** (temporal constraints satisfied)
5. **Cost within 5% of theoretical minimum**

**Classical solvers**: Achieve 1, 2, 4 but fail 3, 5  
**Quantum hybrid**: Achieves all 5

---

## Next Steps

1. **Validate scale assumptions** with Chromium/Firefox codebase analysis
2. **Design subproblem decomposition** strategy
3. **Prototype 10K-task version** on D-Wave Leap
4. **Benchmark against classical** (Gurobi, OR-Tools)
5. **Scale to 100K, then 1M** tasks
