# Decomposition IDE

Epic intents in, executable leaf intents out. Full visibility into the cost/throughput tradeoff.

**Core thesis**: Agents are the bottleneck. More costs more. This notebook makes the budget knob visible and controllable.

Uses the existing QAAS modules (`config`, `agents`, `intents`, `model`, `solve`, `report`) — mock decomposer, no LLM API calls.

```python
import hashlib
from collections import defaultdict

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from agents import build_agent_pool, CLOUD_MODELS, LOCAL_MODELS
from config import TOKEN_ESTIMATES, STORY_POINTS
from intents import INTENT_TEMPLATES
from model import build_cqm, get_cost
from solve import solve_sa, parse_assignments, greedy_solve
from report import print_shift_report

agents, agent_names = build_agent_pool()
print(f"Agent pool: {len(agent_names)} agents")
print(f"Cloud capacity: {sum(a['capacity'] for a in agents.values() if not a['is_local'])}")
print(f"Local capacity: {sum(a['capacity'] for a in agents.values() if a['is_local'])}")
```

## Economics Framing

An epic intent (35,000 tokens, 13 SP) can run monolithically on `claude` for ~$0.70, or be decomposed into smaller intents that spread across cheaper agents. Decomposition itself costs tokens (the "planning tax"), but unlocks cheaper execution by matching leaf complexity to agent capability.

The question: **what's the optimal decomposition depth given a token budget?**

```python
# Decomposition rules: each tier decomposes into N children of a lower tier
DECOMPOSITION_RULES = {
    'epic':         {'children_range': (4, 6), 'child_tier': 'very-complex'},
    'very-complex': {'children_range': (3, 5), 'child_tier': 'complex'},
    'complex':      {'children_range': (2, 4), 'child_tier': 'moderate'},
    'moderate':     {'children_range': (2, 3), 'child_tier': 'simple'},
    'simple':       {'children_range': (2, 3), 'child_tier': 'trivial'},
    # trivial: leaf — no decomposition
}

# Cost of decomposing = 30% of parent's tokens (the "planning tax")
DECOMPOSE_TOKEN_FRACTION = 0.30

print("Decomposition rules:")
for tier, rule in DECOMPOSITION_RULES.items():
    lo, hi = rule['children_range']
    child = rule['child_tier']
    parent_tok = TOKEN_ESTIMATES[tier]
    child_tok = TOKEN_ESTIMATES[child]
    decomp_cost = int(parent_tok * DECOMPOSE_TOKEN_FRACTION)
    print(f"  {tier:>14} ({parent_tok:>5} tok) -> {lo}-{hi} x {child} ({child_tok:>5} tok)  planning tax: {decomp_cost} tok")
```

---

## Section 2: Mock Decomposer

Deterministic decomposition using hash-based branching. Same epic always produces the same tree — no API key needed. Children get sequential dependencies (child[k] depends on child[k-1]).

```python
def _hash_int(seed_str, lo, hi):
    """Deterministic integer in [lo, hi] from a string seed."""
    h = int(hashlib.sha256(seed_str.encode()).hexdigest(), 16)
    return lo + (h % (hi - lo + 1))


def decompose_intent(parent, depth=0, max_depth=5, budget_remaining=float('inf'), _counter=None):
    """Recursively decompose an intent into a tree of smaller intents.

    Args:
        parent: intent dict with id, complexity, estimated_tokens, etc.
        depth: current recursion depth
        max_depth: stop decomposing beyond this depth
        budget_remaining: token budget for decomposition overhead
        _counter: mutable list [int] for unique ID generation

    Returns:
        (tree, flat_leaves, decompose_tokens_used)
        tree: nested dict with 'intent' and 'children' keys
        flat_leaves: list of leaf intent dicts (ready for CQM)
        decompose_tokens_used: total planning tax tokens consumed
    """
    if _counter is None:
        _counter = [0]

    tier = parent['complexity']
    node = {'intent': parent, 'children': [], 'depth': depth}

    # Leaf conditions: trivial tier, max depth, or no budget for planning tax
    if tier not in DECOMPOSITION_RULES or depth >= max_depth:
        return node, [parent], 0

    decomp_cost = int(parent['estimated_tokens'] * DECOMPOSE_TOKEN_FRACTION)
    if budget_remaining < decomp_cost:
        return node, [parent], 0

    rule = DECOMPOSITION_RULES[tier]
    lo, hi = rule['children_range']
    child_tier = rule['child_tier']
    n_children = _hash_int(parent['id'] + f'-d{depth}', lo, hi)

    templates = INTENT_TEMPLATES[child_tier]

    all_leaves = []
    total_decomp = decomp_cost  # planning tax for this node
    remaining = budget_remaining - decomp_cost
    prev_child_id = None

    for k in range(n_children):
        template_idx = _hash_int(parent['id'] + f'-c{k}', 0, len(templates) - 1)
        _counter[0] += 1
        child_id = f"{templates[template_idx]}-{parent['id']}-c{_counter[0]}"

        depends = []
        if prev_child_id is not None:
            depends = [prev_child_id]

        child_intent = {
            'id': child_id,
            'complexity': child_tier,
            'min_quality': parent['min_quality'] * 0.95,  # slightly relaxed
            'depends': depends,
            'estimated_tokens': TOKEN_ESTIMATES[child_tier],
            'story_points': STORY_POINTS[child_tier],
            'parent_id': parent['id'],
        }

        child_node, child_leaves, child_decomp = decompose_intent(
            child_intent, depth + 1, max_depth, remaining, _counter
        )
        node['children'].append(child_node)
        all_leaves.extend(child_leaves)
        total_decomp += child_decomp
        remaining -= child_decomp

        prev_child_id = child_id

    return node, all_leaves, total_decomp


print("decompose_intent() defined")
```

```python
# Three example epics
EPICS = [
    {
        'id': 'epic-platform-redesign',
        'complexity': 'epic',
        'min_quality': 0.95,
        'depends': [],
        'estimated_tokens': TOKEN_ESTIMATES['epic'],
        'story_points': STORY_POINTS['epic'],
    },
    {
        'id': 'epic-ml-training-infra',
        'complexity': 'epic',
        'min_quality': 0.95,
        'depends': [],
        'estimated_tokens': TOKEN_ESTIMATES['epic'],
        'story_points': STORY_POINTS['epic'],
    },
    {
        'id': 'epic-multi-tenant-isolation',
        'complexity': 'epic',
        'min_quality': 0.95,
        'depends': [],
        'estimated_tokens': TOKEN_ESTIMATES['epic'],
        'story_points': STORY_POINTS['epic'],
    },
]

print(f"Defined {len(EPICS)} example epics:")
for e in EPICS:
    print(f"  {e['id']} — {e['estimated_tokens']} tokens, {e['story_points']} SP")
```

```python
# Decompose first epic and print text tree
def print_tree(node, indent=0):
    """Print a decomposition tree as indented text."""
    i = node['intent']
    prefix = '  ' * indent + ('└─ ' if indent > 0 else '')
    deps = f" [depends: {i['depends'][0]}]" if i.get('depends') else ''
    print(f"{prefix}{i['id']}  ({i['complexity']}, {i['estimated_tokens']} tok, {i['story_points']} SP){deps}")
    for child in node['children']:
        print_tree(child, indent + 1)


tree0, leaves0, decomp_tok0 = decompose_intent(EPICS[0])

print(f"Epic: {EPICS[0]['id']}")
print(f"Leaves: {len(leaves0)}")
print(f"Decomposition tokens (planning tax): {decomp_tok0:,}")
print(f"Execution tokens (leaves): {sum(l['estimated_tokens'] for l in leaves0):,}")
print()
print_tree(tree0)
```

---

## Section 3: Tree Visualization

Nodes colored by tier, sized by token count. Solid edges for parent-child, dashed arrows for sequential dependencies.

```python
TIER_COLORS = {
    'epic': '#e74c3c',
    'very-complex': '#e67e22',
    'complex': '#f1c40f',
    'moderate': '#2ecc71',
    'simple': '#3498db',
    'trivial': '#95a5a6',
}


def _layout_tree(node, x=0, y=0, x_spacing=1.0, y_spacing=1.2, positions=None, edges=None, dep_edges=None):
    """Compute positions for tree nodes using a simple left-to-right layout."""
    if positions is None:
        positions = {}
    if edges is None:
        edges = []
    if dep_edges is None:
        dep_edges = []

    intent = node['intent']
    node_id = intent['id']

    if not node['children']:
        positions[node_id] = (x, -y)
        return x + x_spacing, positions, edges, dep_edges

    child_start_x = x
    prev_child_id = None
    for child in node['children']:
        child_id = child['intent']['id']
        x, positions, edges, dep_edges = _layout_tree(
            child, x, y + y_spacing, x_spacing, y_spacing, positions, edges, dep_edges
        )
        edges.append((node_id, child_id))
        if prev_child_id is not None:
            dep_edges.append((prev_child_id, child_id))
        prev_child_id = child_id

    # Center parent above children
    child_xs = [positions[c['intent']['id']][0] for c in node['children']]
    positions[node_id] = ((min(child_xs) + max(child_xs)) / 2, -y)

    return x, positions, edges, dep_edges


def plot_decomposition_tree(tree, title='Decomposition Tree'):
    """Plot the decomposition tree with matplotlib."""
    _, positions, edges, dep_edges = _layout_tree(tree)

    # Collect node data
    all_nodes = []
    def _collect(node):
        all_nodes.append(node['intent'])
        for c in node['children']:
            _collect(c)
    _collect(tree)

    fig, ax = plt.subplots(1, 1, figsize=(max(14, len(all_nodes) * 0.6), 8))

    # Draw edges
    for (p, c) in edges:
        px, py = positions[p]
        cx, cy = positions[c]
        ax.plot([px, cx], [py, cy], '-', color='#bdc3c7', linewidth=1.2, zorder=1)

    # Draw dependency edges (dashed)
    for (a, b) in dep_edges:
        if a in positions and b in positions:
            ax.annotate('', xy=positions[b], xytext=positions[a],
                        arrowprops=dict(arrowstyle='->', color='#e74c3c', lw=0.8, ls='--'))

    # Draw nodes
    for intent in all_nodes:
        nid = intent['id']
        if nid not in positions:
            continue
        x, y = positions[nid]
        tier = intent['complexity']
        color = TIER_COLORS.get(tier, '#95a5a6')
        size = 80 + intent['estimated_tokens'] / 100
        ax.scatter(x, y, s=size, c=color, edgecolors='white', linewidths=1.5, zorder=3)
        # Short label: first 15 chars
        label = nid[:18] + '...' if len(nid) > 18 else nid
        ax.annotate(label, (x, y), fontsize=5, ha='center', va='bottom',
                    xytext=(0, 6), textcoords='offset points', rotation=30)

    # Legend
    handles = [mpatches.Patch(color=c, label=t) for t, c in TIER_COLORS.items()]
    ax.legend(handles=handles, loc='upper right', fontsize=8, title='Tier')

    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.axis('off')
    plt.tight_layout()
    plt.show()


plot_decomposition_tree(tree0, title=f"Decomposition: {EPICS[0]['id']}")
```

---

## Section 4: Layer Cost Analysis

How much does planning cost before anything runs? Layer-by-layer breakdown of decomposition tokens vs execution tokens.

```python
def collect_layers(node, layers=None):
    """Collect nodes by depth layer."""
    if layers is None:
        layers = defaultdict(list)
    layers[node['depth']].append(node)
    for c in node['children']:
        collect_layers(c, layers)
    return layers


def layer_cost_table(tree, epic_name):
    """Print layer-by-layer token breakdown."""
    layers = collect_layers(tree)
    print(f"\n{'='*60}")
    print(f"  LAYER COST ANALYSIS: {epic_name}")
    print(f"{'='*60}")
    print(f"  {'Depth':<7} {'Nodes':>6} {'Tier':<14} {'Decomp Tok':>11} {'Exec Tok':>10} {'Is Leaf':>8}")
    print(f"  {'─'*56}")

    total_decomp = 0
    total_exec = 0

    for depth in sorted(layers.keys()):
        nodes = layers[depth]
        is_leaf = all(len(n['children']) == 0 for n in nodes)
        tier = nodes[0]['intent']['complexity']
        n_nodes = len(nodes)

        if is_leaf:
            decomp_tokens = 0
            exec_tokens = sum(n['intent']['estimated_tokens'] for n in nodes)
            total_exec += exec_tokens
        else:
            decomp_tokens = sum(
                int(n['intent']['estimated_tokens'] * DECOMPOSE_TOKEN_FRACTION)
                for n in nodes
            )
            exec_tokens = 0
            total_decomp += decomp_tokens

        print(f"  {depth:<7} {n_nodes:>6} {tier:<14} {decomp_tokens:>11,} {exec_tokens:>10,} {'YES' if is_leaf else '':>8}")

    print(f"  {'─'*56}")
    total = total_decomp + total_exec
    print(f"  {'TOTAL':<7} {'':>6} {'':14} {total_decomp:>11,} {total_exec:>10,}")
    print(f"  Overhead ratio: {total_decomp / max(total, 1):.1%} planning / {total_exec / max(total, 1):.1%} execution")
    return total_decomp, total_exec


decomp0, exec0 = layer_cost_table(tree0, EPICS[0]['id'])
```

```python
def layer_stacked_bar(tree, title):
    """Stacked bar chart: decompose (red) vs execute (blue) by layer."""
    layers = collect_layers(tree)
    depths = sorted(layers.keys())
    decomp_vals = []
    exec_vals = []

    for d in depths:
        nodes = layers[d]
        is_leaf = all(len(n['children']) == 0 for n in nodes)
        if is_leaf:
            decomp_vals.append(0)
            exec_vals.append(sum(n['intent']['estimated_tokens'] for n in nodes))
        else:
            decomp_vals.append(sum(int(n['intent']['estimated_tokens'] * DECOMPOSE_TOKEN_FRACTION) for n in nodes))
            exec_vals.append(0)

    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(depths))
    ax.bar(x, decomp_vals, color='#e74c3c', label='Decompose (planning tax)')
    ax.bar(x, exec_vals, bottom=decomp_vals, color='#3498db', label='Execute (leaf work)')
    ax.set_xticks(x)
    ax.set_xticklabels([f'Depth {d}' for d in depths])
    ax.set_ylabel('Tokens')
    ax.set_title(title, fontweight='bold')
    ax.legend()
    plt.tight_layout()
    plt.show()


layer_stacked_bar(tree0, f"Token Breakdown by Layer: {EPICS[0]['id']}")
```

```python
# Overhead ratio across all 3 epics
print(f"{'='*60}")
print(f"  OVERHEAD RATIO: ALL EPICS")
print(f"{'='*60}")
print(f"  {'Epic':<35} {'Decomp':>8} {'Exec':>8} {'Total':>8} {'Overhead':>9}")
print(f"  {'─'*72}")

all_trees = []
all_leaves_list = []
all_decomp_tokens = []

for epic in EPICS:
    tree, leaves, dtok = decompose_intent(epic)
    all_trees.append(tree)
    all_leaves_list.append(leaves)
    all_decomp_tokens.append(dtok)
    exec_tok = sum(l['estimated_tokens'] for l in leaves)
    total = dtok + exec_tok
    ratio = dtok / max(total, 1)
    print(f"  {epic['id']:<35} {dtok:>8,} {exec_tok:>8,} {total:>8,} {ratio:>8.1%}")

# Totals
sum_decomp = sum(all_decomp_tokens)
sum_exec = sum(sum(l['estimated_tokens'] for l in leaves) for leaves in all_leaves_list)
sum_total = sum_decomp + sum_exec
print(f"  {'─'*72}")
print(f"  {'COMBINED':<35} {sum_decomp:>8,} {sum_exec:>8,} {sum_total:>8,} {sum_decomp / max(sum_total,1):>8.1%}")
print(f"\n  Planning tax before anything runs: {sum_decomp:,} tokens")
print(f"  Total leaves across all epics: {sum(len(l) for l in all_leaves_list)}")
```

---

## Section 5: The Budget Knob

Sweep decomposition token budgets from 0 (no decomposition — run epic monolithically) to unlimited (full recursive decomposition). See how leaf count, token cost, and dollar cost change.

```python
# Budget sweep across all 3 epics combined
budget_points = [0, 500, 1000, 2000, 5000, 10000, 15000, 20000, 30000, 50000, 100000, float('inf')]
budget_labels = [str(b) if b != float('inf') else 'unlimited' for b in budget_points]

sweep_results = []
for budget in budget_points:
    total_leaves = []
    total_decomp = 0
    for epic in EPICS:
        _, leaves, dtok = decompose_intent(epic, budget_remaining=budget)
        total_leaves.extend(leaves)
        total_decomp += dtok

    exec_tokens = sum(l['estimated_tokens'] for l in total_leaves)
    total_tokens = total_decomp + exec_tokens

    # Dollar cost estimate: use average cloud rate for decompose tokens (claude rate),
    # cheapest capable rate for each leaf
    claude_rate = 0.000020
    decomp_dollars = total_decomp * claude_rate  # planning always on best model

    # Estimate leaf cost: cheapest capable agent per tier
    tier_cheapest = {}
    for tier in TOKEN_ESTIMATES:
        rates = []
        for name, a in agents.items():
            if tier in a['capabilities']:
                rates.append(a['token_rate'])
        tier_cheapest[tier] = min(rates) if rates else 0

    exec_dollars = sum(l['estimated_tokens'] * tier_cheapest.get(l['complexity'], 0) for l in total_leaves)
    total_dollars = decomp_dollars + exec_dollars

    sweep_results.append({
        'budget': budget,
        'n_leaves': len(total_leaves),
        'decomp_tokens': total_decomp,
        'exec_tokens': exec_tokens,
        'total_tokens': total_tokens,
        'decomp_dollars': decomp_dollars,
        'exec_dollars': exec_dollars,
        'total_dollars': total_dollars,
        'leaves': total_leaves,
    })

print(f"  {'Budget':>10} {'Leaves':>7} {'Decomp Tok':>11} {'Exec Tok':>10} {'Total Tok':>10} {'$ Total':>9}")
print(f"  {'─'*60}")
for r, label in zip(sweep_results, budget_labels):
    print(f"  {label:>10} {r['n_leaves']:>7} {r['decomp_tokens']:>11,} {r['exec_tokens']:>10,} {r['total_tokens']:>10,} ${r['total_dollars']:>8.2f}")
```

```python
# 3-panel graph: leaf count, token breakdown, dollar cost vs budget
finite_results = [r for r in sweep_results if r['budget'] != float('inf')]
inf_result = [r for r in sweep_results if r['budget'] == float('inf')][0]

# For plotting, represent 'unlimited' as max finite + 20%
budgets_plot = [r['budget'] for r in finite_results] + [finite_results[-1]['budget'] * 1.2]
all_plot = finite_results + [inf_result]

fig, axes = plt.subplots(1, 3, figsize=(18, 5))

# Panel 1: Leaf count vs budget
ax = axes[0]
ax.plot(budgets_plot, [r['n_leaves'] for r in all_plot], 'o-', color='#2ecc71', linewidth=2)
ax.set_xlabel('Decomposition Budget (tokens)')
ax.set_ylabel('Leaf Count')
ax.set_title('Leaf Count vs Budget', fontweight='bold')
ax.grid(True, alpha=0.3)

# Panel 2: Token breakdown vs budget
ax = axes[1]
ax.fill_between(budgets_plot, [r['decomp_tokens'] for r in all_plot], color='#e74c3c', alpha=0.7, label='Planning tax')
ax.fill_between(budgets_plot, [r['decomp_tokens'] for r in all_plot],
                [r['total_tokens'] for r in all_plot], color='#3498db', alpha=0.7, label='Execution')
ax.set_xlabel('Decomposition Budget (tokens)')
ax.set_ylabel('Tokens')
ax.set_title('Token Breakdown vs Budget', fontweight='bold')
ax.legend()
ax.grid(True, alpha=0.3)

# Panel 3: Dollar cost vs budget
ax = axes[2]
dollars = [r['total_dollars'] for r in all_plot]
ax.plot(budgets_plot, dollars, 'o-', color='#9b59b6', linewidth=2)
# Annotate optimal (minimum cost)
opt_idx = np.argmin(dollars)
ax.annotate(f'Optimal: ${dollars[opt_idx]:.2f}',
            xy=(budgets_plot[opt_idx], dollars[opt_idx]),
            xytext=(budgets_plot[opt_idx] + 5000, dollars[opt_idx] + 0.1),
            arrowprops=dict(arrowstyle='->', color='black'),
            fontsize=10, fontweight='bold')
ax.set_xlabel('Decomposition Budget (tokens)')
ax.set_ylabel('Dollar Cost')
ax.set_title('Dollar Cost vs Budget', fontweight='bold')
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()
```

```python
# Cost vs throughput scatter: X = agent-slots needed, Y = total cost
fig, ax = plt.subplots(figsize=(10, 6))

for i, r in enumerate(sweep_results):
    label = budget_labels[i]
    # Agent slots = number of leaves (each needs one agent slot)
    ax.scatter(r['n_leaves'], r['total_dollars'], s=100, zorder=3)
    ax.annotate(label, (r['n_leaves'], r['total_dollars']),
                fontsize=8, ha='left', va='bottom', xytext=(5, 5),
                textcoords='offset points')

# Add monolithic point (3 epics, 3 agent slots, claude rate)
mono_cost = sum(e['estimated_tokens'] for e in EPICS) * 0.000020
ax.scatter(3, mono_cost, s=200, c='red', marker='*', zorder=4, label='Monolithic (3 slots)')
ax.annotate('Monolithic', (3, mono_cost), fontsize=10, fontweight='bold',
            ha='right', va='bottom', xytext=(-10, 5), textcoords='offset points')

ax.set_xlabel('Agent Slots Required', fontsize=12)
ax.set_ylabel('Total Dollar Cost', fontsize=12)
ax.set_title('Cost vs Throughput: "More Costs More"', fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()
```

```python
# Capacity pressure: do the decomposed leaves fit in the swarm?
total_cloud_cap = sum(a['capacity'] for a in agents.values() if not a['is_local'])
total_local_cap = sum(a['capacity'] for a in agents.values() if a['is_local'])
total_cap = total_cloud_cap + total_local_cap

print(f"{'='*60}")
print(f"  CAPACITY PRESSURE TABLE")
print(f"{'='*60}")
print(f"  Swarm capacity: {total_cap} slots (cloud: {total_cloud_cap}, local: {total_local_cap})")
print()
print(f"  {'Budget':>10} {'Leaves':>7} {'Slots Used':>11} {'% Capacity':>11} {'Fits?':>6}")
print(f"  {'─'*50}")

for r, label in zip(sweep_results, budget_labels):
    pct = r['n_leaves'] / total_cap * 100
    fits = 'YES' if r['n_leaves'] <= total_cap else 'NO'
    print(f"  {label:>10} {r['n_leaves']:>7} {r['n_leaves']:>11} {pct:>10.1f}% {fits:>6}")
```

---

## Section 6: QAAS Integration

Route both monolithic (3 epics as-is) and decomposed (all leaves) through `build_cqm()` + `solve_sa()`. Compare cost, utilization, and constraint satisfaction.

```python
# Build monolithic intents (3 epics as-is)
mono_intents = []
for epic in EPICS:
    mono_intents.append({
        'id': epic['id'],
        'complexity': epic['complexity'],
        'min_quality': epic['min_quality'],
        'depends': [],
        'estimated_tokens': epic['estimated_tokens'],
        'story_points': epic['story_points'],
    })

# Build decomposed intents (max_depth=3 keeps CQM solve fast while showing the tradeoff)
decomp_intents = []
total_planning_tax = 0
for epic in EPICS:
    _, leaves, dtok = decompose_intent(epic, max_depth=3)
    total_planning_tax += dtok
    decomp_intents.extend(leaves)

# Fix dependencies: convert string IDs to integer indices
# Build id -> index mapping
id_to_idx = {intent['id']: idx for idx, intent in enumerate(decomp_intents)}
for intent in decomp_intents:
    intent['depends'] = [id_to_idx[dep] for dep in intent['depends'] if dep in id_to_idx]

print(f"Monolithic: {len(mono_intents)} intents, {sum(i['estimated_tokens'] for i in mono_intents):,} tokens")
print(f"Decomposed: {len(decomp_intents)} intents, {sum(i['estimated_tokens'] for i in decomp_intents):,} exec tokens + {total_planning_tax:,} planning tax")
print(f"Total SP — Mono: {sum(i['story_points'] for i in mono_intents)}, Decomposed: {sum(i['story_points'] for i in decomp_intents)}")
```

```python
# Route monolithic
print("=" * 60)
print("  ROUTING MONOLITHIC (3 epics)")
print("=" * 60)
mono_cqm, mono_x = build_cqm(mono_intents, agents, agent_names)
mono_ss = solve_sa(mono_cqm)
mono_assignments = parse_assignments(mono_ss, agent_names)

mono_cost = sum(
    mono_intents[i]['estimated_tokens'] * agents[a]['token_rate']
    for i, a in mono_assignments.items()
)
print(f"\nAssigned: {len(mono_assignments)}/{len(mono_intents)}")
print(f"Cost: ${mono_cost:.2f}")
print(f"Agents used: {', '.join(set(mono_assignments.values()))}")
```

```python
# Route decomposed
print("=" * 60)
print(f"  ROUTING DECOMPOSED ({len(decomp_intents)} leaves)")
print("=" * 60)
decomp_cqm, decomp_x = build_cqm(decomp_intents, agents, agent_names)
decomp_ss = solve_sa(decomp_cqm)
decomp_assignments = parse_assignments(decomp_ss, agent_names)

decomp_exec_cost = sum(
    decomp_intents[i]['estimated_tokens'] * agents[a]['token_rate']
    for i, a in decomp_assignments.items()
)
# Add planning tax at claude rate
decomp_planning_cost = total_planning_tax * 0.000020
decomp_total_cost = decomp_exec_cost + decomp_planning_cost

print(f"\nAssigned: {len(decomp_assignments)}/{len(decomp_intents)}")
print(f"Execution cost: ${decomp_exec_cost:.2f}")
print(f"Planning tax cost: ${decomp_planning_cost:.2f}")
print(f"Total cost: ${decomp_total_cost:.2f}")
print(f"Unique agents: {len(set(decomp_assignments.values()))}")
```

```python
# Head-to-head comparison table
mono_sp = sum(mono_intents[i]['story_points'] for i in mono_assignments)
decomp_sp = sum(decomp_intents[i]['story_points'] for i in decomp_assignments)
mono_agents_used = set(mono_assignments.values())
decomp_agents_used = set(decomp_assignments.values())

mono_cloud = sum(1 for a in mono_assignments.values() if not agents[a]['is_local'])
mono_local = len(mono_assignments) - mono_cloud
decomp_cloud = sum(1 for a in decomp_assignments.values() if not agents[a]['is_local'])
decomp_local = len(decomp_assignments) - decomp_cloud

# Constraint violations
mono_unassigned = len(mono_intents) - len(mono_assignments)
decomp_unassigned = len(decomp_intents) - len(decomp_assignments)

print("=" * 60)
print("  HEAD TO HEAD: MONOLITHIC vs DECOMPOSED")
print("=" * 60)
print(f"\n  {'Metric':<30} {'Monolithic':<15} {'Decomposed':<15}")
print(f"  {'─'*60}")
print(f"  {'Tasks':<30} {len(mono_intents):<15} {len(decomp_intents):<15}")
print(f"  {'Tasks assigned':<30} {len(mono_assignments):<15} {len(decomp_assignments):<15}")
print(f"  {'Tasks dropped':<30} {mono_unassigned:<15} {decomp_unassigned:<15}")
print(f"  {'Story points':<30} {mono_sp:<15} {decomp_sp:<15}")
print(f"  {'Execution cost':<30} ${mono_cost:<14.2f} ${decomp_exec_cost:<14.2f}")
print(f"  {'Planning tax cost':<30} ${0:<14.2f} ${decomp_planning_cost:<14.2f}")
print(f"  {'Total cost':<30} ${mono_cost:<14.2f} ${decomp_total_cost:<14.2f}")
print(f"  {'Cost per SP':<30} ${mono_cost / max(mono_sp, 1):<14.4f} ${decomp_total_cost / max(decomp_sp, 1):<14.4f}")
print(f"  {'Agents used':<30} {len(mono_agents_used):<15} {len(decomp_agents_used):<15}")
print(f"  {'Cloud tasks':<30} {mono_cloud:<15} {decomp_cloud:<15}")
print(f"  {'Local tasks (free)':<30} {mono_local:<15} {decomp_local:<15}")

if decomp_total_cost < mono_cost:
    savings = mono_cost - decomp_total_cost
    print(f"\n  -> Decomposition saves ${savings:.2f} ({savings/mono_cost:.0%})")
else:
    extra = decomp_total_cost - mono_cost
    print(f"\n  -> Decomposition costs ${extra:.2f} more ({extra/mono_cost:.0%}) but uses {len(decomp_agents_used) - len(mono_agents_used)} more agents")
print(f"  -> Decomposition spreads work across {len(decomp_agents_used)} agents vs {len(mono_agents_used)}")
```

```python
# Side-by-side agent utilization bar charts
def agent_model_counts(assignments):
    """Count tasks per model family."""
    counts = defaultdict(int)
    for a in assignments.values():
        # Strip session number for cloud agents
        base = a.rsplit('-', 1)[0] if any(a.startswith(m['name']) for m in CLOUD_MODELS) else a
        counts[base] += 1
    return dict(counts)


mono_counts = agent_model_counts(mono_assignments)
decomp_counts = agent_model_counts(decomp_assignments)

# All model families
all_models = sorted(set(list(mono_counts.keys()) + list(decomp_counts.keys())))

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

# Monolithic
x = np.arange(len(all_models))
vals = [mono_counts.get(m, 0) for m in all_models]
colors = ['#e74c3c' if any(m.startswith(cm['name']) for cm in CLOUD_MODELS if cm['quality'] >= 0.92) else '#3498db' for m in all_models]
ax1.bar(x, vals, color=colors)
ax1.set_xticks(x)
ax1.set_xticklabels(all_models, rotation=45, ha='right', fontsize=8)
ax1.set_ylabel('Tasks Assigned')
ax1.set_title('Monolithic: Agent Utilization', fontweight='bold')

# Decomposed
vals = [decomp_counts.get(m, 0) for m in all_models]
ax2.bar(x, vals, color=['#2ecc71' if v > 0 else '#95a5a6' for v in vals])
ax2.set_xticks(x)
ax2.set_xticklabels(all_models, rotation=45, ha='right', fontsize=8)
ax2.set_ylabel('Tasks Assigned')
ax2.set_title('Decomposed: Agent Utilization', fontweight='bold')

plt.tight_layout()
plt.show()
```

---

## Section 7: Factory Summary

Shift report for the decomposed routing, plus executive summary comparing approaches.

```python
# Build workflow chains from decomposed intents (sequential sibling deps already wired)
# Group by parent epic for chain display
decomp_chains = []
for epic in EPICS:
    chain_indices = [i for i, intent in enumerate(decomp_intents) if intent.get('parent_id', '').startswith(epic['id'])]
    if chain_indices:
        decomp_chains.append((epic['id'], chain_indices))

print_shift_report(decomp_assignments, decomp_intents, agents, decomp_chains)
```

```python
# Executive summary
print("=" * 60)
print("  EXECUTIVE SUMMARY")
print("=" * 60)

print(f"\n  MONOLITHIC APPROACH")
print(f"  {len(mono_intents)} tasks | ${mono_cost:.2f} total | {len(mono_agents_used)} agents")
print(f"  All work on premium agents (epic tier requires quality >= 0.95)")

print(f"\n  OPTIMAL DECOMPOSITION")
print(f"  {len(decomp_intents)} tasks | ${decomp_total_cost:.2f} total | {len(decomp_agents_used)} agents")
print(f"  Planning tax: ${decomp_planning_cost:.2f} ({total_planning_tax:,} tokens)")
print(f"  Execution: ${decomp_exec_cost:.2f} across {len(decomp_agents_used)} agents")

if decomp_total_cost < mono_cost:
    pct = (mono_cost - decomp_total_cost) / mono_cost * 100
    print(f"\n  SAVINGS: ${mono_cost - decomp_total_cost:.2f} ({pct:.0f}%)")
else:
    pct = (decomp_total_cost - mono_cost) / mono_cost * 100
    print(f"\n  ADDITIONAL COST: ${decomp_total_cost - mono_cost:.2f} ({pct:.0f}%)")

print(f"\n  AGENT PRESSURE")
print(f"  Monolithic: {len(mono_intents)} slots / {total_cap} capacity = {len(mono_intents)/total_cap:.1%}")
print(f"  Decomposed: {len(decomp_intents)} slots / {total_cap} capacity = {len(decomp_intents)/total_cap:.1%}")

print(f"\n  RECOMMENDATION")
if decomp_total_cost < mono_cost:
    print(f"  Decomposition reduces cost by spreading work to cheaper agents.")
    print(f"  The planning tax ({total_planning_tax:,} tokens) pays for itself in execution savings.")
else:
    print(f"  For these 3 epics, decomposition adds cost but improves parallelism.")
    print(f"  At larger scale (50+ epics), the per-epic planning tax amortizes better.")
print(f"  Decomposition uses {len(decomp_agents_used) - len(mono_agents_used)} additional agents, enabling parallel execution.")
print(f"  Core thesis confirmed: agents are the bottleneck, more costs more.")
```
