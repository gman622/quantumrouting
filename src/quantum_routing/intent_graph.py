"""Visualize the 10K intent graph: what the IDE canvas actually looks like."""

import sys
from pathlib import Path
DOCS_DIR = Path(__file__).parent.parent.parent / 'docs'

from collections import defaultdict

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch

from quantum_routing.css_renderer_agents import build_agent_pool
from quantum_routing.css_renderer_intents import generate_intents, build_workflow_chains
from quantum_routing.solve_10k_ortools import solve_cpsat, greedy_solve
from quantum_routing import css_renderer_config as cfg

# --- Generate data ---
print("Building agent pool...")
agents, agent_names = build_agent_pool()
print("Generating intents...")
intents = generate_intents()
print("Building workflow chains...")
workflow_chains = build_workflow_chains(intents)
print("Solving with CP-SAT...")
assignments = solve_cpsat(intents, agents, agent_names)
print(f"Assigned {len(assignments)}/{len(intents)} tasks\n")

# --- Color maps ---
STAGE_COLORS = {
    'parsing': '#3498db',
    'style_computation': '#9b59b6',
    'layout': '#2ecc71',
    'painting': '#e67e22',
    'compositing': '#e74c3c',
}

COMPLEXITY_SIZES = {
    'trivial': 4,
    'simple': 8,
    'moderate': 16,
    'complex': 28,
    'very-complex': 44,
    'epic': 70,
}

STATUS_COLORS = {
    'satisfied': '#2ecc71',   # green — all constraints met
    'overkill': '#f1c40f',    # yellow — soft violation
    'violated': '#e74c3c',    # red — hard violation
}


def get_status(i, intent, assignments, agents):
    """Determine constraint status for an intent."""
    if i not in assignments:
        return 'violated'
    agent = agents[assignments[i]]
    # Overkill: expensive agent on trivial/simple task
    if intent['complexity'] in ('trivial', 'simple') and agent['token_rate'] > 0.00001:
        return 'overkill'
    return 'satisfied'


# ==========================================================
# FIGURE 1: Pipeline Stage Overview (macro view)
# ==========================================================
print("Drawing Figure 1: Pipeline macro view...")

fig, ax = plt.subplots(figsize=(20, 10))
ax.set_xlim(-1, 52)
ax.set_ylim(-2, 12)
ax.set_aspect('equal')
ax.axis('off')
ax.set_title('Intent Graph: CSS Renderer Pipeline (10K tasks)',
             fontsize=18, fontweight='bold', pad=20)

stage_x = {'parsing': 0, 'style_computation': 10, 'layout': 20, 'painting': 32, 'compositing': 42}
stage_counts = defaultdict(lambda: defaultdict(int))
stage_status_counts = defaultdict(lambda: defaultdict(int))

for i, intent in enumerate(intents):
    stage = intent['stage']
    complexity = intent['complexity']
    stage_counts[stage][complexity] += 1
    status = get_status(i, intent, assignments, agents)
    stage_status_counts[stage][status] += 1

for stage in cfg.PIPELINE_STAGES:
    x = stage_x[stage]
    color = STAGE_COLORS[stage]
    total = sum(stage_counts[stage].values())

    # Stage box
    rect = plt.Rectangle((x - 0.5, 0), 8, 10, linewidth=2,
                          edgecolor=color, facecolor=color, alpha=0.08,
                          zorder=1, linestyle='-')
    ax.add_patch(rect)

    # Stage label
    ax.text(x + 3.5, 10.3, stage.replace('_', ' ').upper(),
            ha='center', va='bottom', fontsize=11, fontweight='bold', color=color)
    ax.text(x + 3.5, 9.6, f'{total:,} tasks',
            ha='center', va='top', fontsize=9, color='#666')

    # Complexity breakdown as stacked dots
    y_pos = 0.8
    for complexity in ['trivial', 'simple', 'moderate', 'complex', 'very-complex', 'epic']:
        count = stage_counts[stage].get(complexity, 0)
        if count == 0:
            continue
        # Draw a row of dots proportional to count
        dot_count = max(1, count // 50)  # 1 dot per 50 tasks
        size = COMPLEXITY_SIZES[complexity]
        xs = np.linspace(x + 0.3, x + 7.0, min(dot_count, 40))
        ys = [y_pos] * len(xs)
        ax.scatter(xs, ys, s=size, c=color, alpha=0.5, zorder=2)
        ax.text(x + 7.5, y_pos, f'{complexity} ({count})',
                fontsize=6, va='center', color='#888')
        y_pos += 1.2

    # Status summary
    sat = stage_status_counts[stage].get('satisfied', 0)
    ovk = stage_status_counts[stage].get('overkill', 0)
    vio = stage_status_counts[stage].get('violated', 0)
    ax.text(x + 3.5, -0.3,
            f'{sat} ok  {ovk} overkill  {vio} violated',
            ha='center', va='top', fontsize=7, color='#666')

# Draw pipeline arrows between stages
stages = cfg.PIPELINE_STAGES
for idx in range(len(stages) - 1):
    x1 = stage_x[stages[idx]] + 7.5
    x2 = stage_x[stages[idx + 1]] - 0.5
    mid_y = 5
    ax.annotate('', xy=(x2, mid_y), xytext=(x1, mid_y),
                arrowprops=dict(arrowstyle='->', color='#bdc3c7', lw=2.5))

    # Edge label: dependency count
    dep_count = sum(
        1 for i, intent in enumerate(intents)
        if intent['stage'] == stages[idx + 1]
        for dep in intent.get('depends', [])
        if intents[dep]['stage'] == stages[idx]
    )
    if dep_count > 0:
        ax.text((x1 + x2) / 2, mid_y + 0.4, f'{dep_count} deps',
                ha='center', va='bottom', fontsize=7, color='#999')

# Legend
legend_elements = [mpatches.Patch(facecolor=c, label=s.replace('_', ' '))
                   for s, c in STAGE_COLORS.items()]
legend_elements.extend([
    plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#2ecc71',
               markersize=8, label='Satisfied'),
    plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#f1c40f',
               markersize=8, label='Overkill (soft)'),
    plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#e74c3c',
               markersize=8, label='Violated (hard)'),
])
ax.legend(handles=legend_elements, loc='lower right', fontsize=8, ncol=2)

plt.tight_layout()
plt.savefig(DOCS_DIR / 'intent_graph_macro.png', dpi=150, bbox_inches='tight')
print("  Saved intent_graph_macro.png")
plt.close()


# ==========================================================
# FIGURE 2: Workflow chain detail (zoomed intent graph)
# ==========================================================
print("Drawing Figure 2: Workflow chain detail...")

# Pick 8 chains across different stages
sample_chains = []
seen_stages = set()
for wf_type, steps in workflow_chains:
    stage = wf_type.replace('-chain', '')
    if stage not in seen_stages and len(steps) >= 3:
        sample_chains.append((wf_type, steps))
        seen_stages.add(stage)
    if len(sample_chains) >= 5:
        break
# Add a few more for density
for wf_type, steps in workflow_chains[50:]:
    if len(sample_chains) >= 8:
        break
    sample_chains.append((wf_type, steps))

fig, ax = plt.subplots(figsize=(20, 12))
ax.axis('off')
ax.set_title('Intent Graph: Workflow Chains (zoomed view)\nEach node = 1 intent, edges = dependencies',
             fontsize=16, fontweight='bold', pad=20)

y_offset = 0
node_positions = {}

for chain_idx, (wf_type, steps) in enumerate(sample_chains):
    y = 10 - chain_idx * 1.3
    chain_stage = intents[steps[0]]['stage']
    color = STAGE_COLORS.get(chain_stage, '#95a5a6')

    # Chain label
    ax.text(-0.5, y, wf_type, ha='right', va='center', fontsize=8,
            fontweight='bold', color=color)

    for step_idx, intent_idx in enumerate(steps):
        intent = intents[intent_idx]
        x = step_idx * 2.5

        # Node color by status
        status = get_status(intent_idx, intent, assignments, agents)
        node_color = STATUS_COLORS[status]
        node_size = COMPLEXITY_SIZES[intent['complexity']] * 8

        ax.scatter(x, y, s=node_size, c=node_color, edgecolors=color,
                   linewidths=1.5, zorder=3, alpha=0.85)

        # Label: complexity + agent
        agent_label = ''
        if intent_idx in assignments:
            agent_name = assignments[intent_idx]
            agent_label = agent_name.split('-')[0]

        ax.text(x, y - 0.45, f'{intent["complexity"][:4]}',
                ha='center', va='top', fontsize=5.5, color='#666')
        ax.text(x, y + 0.45, agent_label,
                ha='center', va='bottom', fontsize=5.5, color=color, fontweight='bold')

        node_positions[intent_idx] = (x, y)

        # Dependency edge
        if step_idx > 0:
            prev_idx = steps[step_idx - 1]
            if prev_idx in node_positions:
                px, py = node_positions[prev_idx]
                ax.annotate('', xy=(x - 0.3, y), xytext=(px + 0.3, py),
                            arrowprops=dict(arrowstyle='->', color=color,
                                            lw=1.2, alpha=0.6))

# Legend
legend_elements = [
    plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#2ecc71',
               markersize=10, label='Constraints satisfied'),
    plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#f1c40f',
               markersize=10, label='Overkill (soft violation)'),
    plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#e74c3c',
               markersize=10, label='Hard violation'),
    plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='white',
               markeredgecolor='#333', markersize=6, label='Node size = complexity'),
]
ax.legend(handles=legend_elements, loc='lower right', fontsize=9)

plt.tight_layout()
plt.savefig(DOCS_DIR / 'intent_graph_chains.png', dpi=150, bbox_inches='tight')
print("  Saved intent_graph_chains.png")
plt.close()


# ==========================================================
# FIGURE 3: The constraint surface — cost vs quality frontier
# ==========================================================
print("Drawing Figure 3: Constraint surface...")

fig, axes = plt.subplots(1, 3, figsize=(20, 6))

# Panel 1: Intent distribution by stage and complexity (the graph structure)
ax = axes[0]
stages = cfg.PIPELINE_STAGES
complexities = ['trivial', 'simple', 'moderate', 'complex', 'very-complex', 'epic']
data = np.zeros((len(complexities), len(stages)))
for i, intent in enumerate(intents):
    si = stages.index(intent['stage'])
    ci = complexities.index(intent['complexity'])
    data[ci][si] += 1

im = ax.imshow(data, aspect='auto', cmap='YlOrRd')
ax.set_xticks(range(len(stages)))
ax.set_xticklabels([s.replace('_', '\n') for s in stages], fontsize=8)
ax.set_yticks(range(len(complexities)))
ax.set_yticklabels(complexities, fontsize=8)
ax.set_title('Intent Distribution\n(stage x complexity)', fontweight='bold')
for ci in range(len(complexities)):
    for si in range(len(stages)):
        val = int(data[ci][si])
        if val > 0:
            ax.text(si, ci, str(val), ha='center', va='center', fontsize=7,
                    color='white' if val > 300 else 'black')
plt.colorbar(im, ax=ax, shrink=0.8, label='Task count')

# Panel 2: Cost distribution by agent type
ax = axes[1]
agent_costs = defaultdict(float)
agent_tasks = defaultdict(int)
for i, agent_name in assignments.items():
    model_type = agents[agent_name]['model_type']
    cost = intents[i]['estimated_tokens'] * agents[agent_name]['token_rate']
    agent_costs[model_type] += cost
    agent_tasks[model_type] += 1

models = sorted(agent_costs.keys(), key=lambda m: agent_costs[m], reverse=True)
colors = [STAGE_COLORS.get('parsing', '#3498db')] * len(models)
bars = ax.barh(range(len(models)), [agent_costs[m] for m in models],
               color=['#e74c3c' if agent_costs[m] > 100 else '#3498db' for m in models],
               alpha=0.8)
ax.set_yticks(range(len(models)))
ax.set_yticklabels(models, fontsize=9)
ax.set_xlabel('Total Cost ($)')
ax.set_title('Cost by Agent Type\n(the optimizer\'s allocation)', fontweight='bold')

for idx, m in enumerate(models):
    ax.text(agent_costs[m] + 2, idx,
            f'{agent_tasks[m]} tasks, ${agent_costs[m]:.0f}',
            va='center', fontsize=8, color='#666')

# Panel 3: Quality vs Cost per intent (the Pareto frontier)
ax = axes[2]
costs = []
qualities = []
stage_list = []
for i, agent_name in assignments.items():
    cost = intents[i]['estimated_tokens'] * agents[agent_name]['token_rate']
    quality = agents[agent_name]['quality']
    costs.append(cost)
    qualities.append(quality)
    stage_list.append(intents[i]['stage'])

for stage in cfg.PIPELINE_STAGES:
    mask = [s == stage for s in stage_list]
    sc = [c for c, m in zip(costs, mask) if m]
    sq = [q for q, m in zip(qualities, mask) if m]
    ax.scatter(sc, sq, s=4, alpha=0.3, label=stage.replace('_', ' '),
               color=STAGE_COLORS[stage])

ax.set_xlabel('Cost per Intent ($)')
ax.set_ylabel('Agent Quality')
ax.set_title('Cost vs Quality per Intent\n(each dot = 1 assignment)', fontweight='bold')
ax.legend(fontsize=7, markerscale=3)
ax.grid(True, alpha=0.2)

plt.tight_layout()
plt.savefig(DOCS_DIR / 'intent_graph_constraints.png', dpi=150, bbox_inches='tight')
print("  Saved intent_graph_constraints.png")
plt.close()

print("\nDone. Three figures saved to notebooks/")
