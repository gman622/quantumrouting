"""Reporting functions for 10K CSS Renderer routing results."""

from collections import defaultdict

from css_renderer_agents import (
    CLOUD_MODELS, LOCAL_MODELS, CLOUD_SESSIONS, CLOUD_CAPACITY, LOCAL_COUNT,
)
from css_renderer_intents import CSS_TASK_TEMPLATES
import css_renderer_config as cfg


def print_shift_report(assignments, intents, agents, workflow_chains):
    """Print the full factory floor shift report for CSS Renderer.

    Args:
        assignments: Dict mapping intent index to agent name
        intents: List of intent dicts
        agents: Dict of agent definitions
        workflow_chains: List of workflow chain tuples
    """
    num_intents = len(intents)

    # Count assignments per agent
    agent_counts = defaultdict(int)
    for agent in assignments.values():
        agent_counts[agent] += 1

    # Calculate costs and quality
    money_spent = sum(
        intents[i]['estimated_tokens'] * agents[a]['token_rate']
        for i, a in assignments.items()
    )
    quality_met = sum(
        1 for i, a in assignments.items()
        if agents[a]['quality'] >= intents[i]['min_quality']
    )
    unassigned = [i for i in range(num_intents) if i not in assignments]

    # Check capacity violations
    capacity_violations = []
    for name, count in agent_counts.items():
        if count > agents[name]['capacity']:
            capacity_violations.append(f"  {name}: {count}/{agents[name]['capacity']}")

    # Check dependency violations
    dep_violations = 0
    for i, intent in enumerate(intents):
        for dep_idx in intent.get('depends', []):
            if i in assignments and dep_idx in assignments:
                if agents[assignments[i]]['quality'] < agents[assignments[dep_idx]]['quality']:
                    dep_violations += 1

    # Check stage ordering (cross-stage dependencies)
    stage_order_violations = 0
    stage_order = {stage: i for i, stage in enumerate(cfg.PIPELINE_STAGES)}
    for i, intent in enumerate(intents):
        for dep_idx in intent.get('depends', []):
            if i in assignments and dep_idx in assignments:
                current_stage = intent['stage']
                dep_stage = intents[dep_idx]['stage']
                if stage_order.get(dep_stage, 0) > stage_order.get(current_stage, 0):
                    stage_order_violations += 1

    # Overkill: expensive models on simple tasks
    overkill = []
    for i, name in assignments.items():
        if intents[i]['complexity'] in ('trivial', 'simple') and agents[name]['token_rate'] > 0.00001:
            overkill.append(f"  {intents[i]['id']} -> {name}")

    # Print report header
    print("=" * 70)
    print("  CSS RENDERER FACTORY FLOOR SHIFT REPORT")
    print("  10K Tasks - Quantum Agent Annealed Swarm")
    print("=" * 70)

    # Summary metrics
    print(f"\n  Tasks completed:       {len(assignments)}/{num_intents}")
    print(f"  Tasks dropped:         {len(unassigned)}")
    print(f"  Money spent:           ${money_spent:.2f}")
    print(f"  Quality targets met:   {quality_met}/{len(assignments)}")
    print(f"  Capacity violations:   {len(capacity_violations)}")
    print(f"  Dep violations:        {dep_violations}")
    print(f"  Stage order violations: {stage_order_violations}")

    # Pipeline stage breakdown
    print(f"\n{'─' * 70}")
    print(f"  PIPELINE STAGE BREAKDOWN")
    print(f"{'─' * 70}")

    stage_stats = defaultdict(lambda: {'count': 0, 'sp': 0, 'cost': 0.0})
    for i, agent_name in assignments.items():
        stage = intents[i]['stage']
        sp = intents[i].get('story_points', 0)
        cost = intents[i]['estimated_tokens'] * agents[agent_name]['token_rate']
        stage_stats[stage]['count'] += 1
        stage_stats[stage]['sp'] += sp
        stage_stats[stage]['cost'] += cost

    print(f"  {'Stage':<20} {'Tasks':>8} {'SP':>8} {'Cost':>12}")
    print(f"  {'─' * 52}")
    for stage in cfg.PIPELINE_STAGES:
        s = stage_stats[stage]
        if s['count'] > 0:
            print(f"  {stage:<20} {s['count']:>8} {s['sp']:>8} ${s['cost']:>10.2f}")

    # Workflow chain quality progression
    print(f"\n{'─' * 70}")
    print(f"  WORKFLOW CHAIN QUALITY PROGRESSION (sample)")
    print(f"{'─' * 70}")

    shown = defaultdict(int)
    for wf_type, steps in workflow_chains[:20]:  # Show first 20
        if shown[wf_type] >= 2:
            continue
        shown[wf_type] += 1
        chain_info = []
        for s in steps:
            if s in assignments:
                a = assignments[s]
                q = agents[a]['quality']
                chain_info.append(f"{a.split('-')[0]}({q:.2f})")
            else:
                chain_info.append("UNASSIGNED")
        print(f"  {wf_type}: {' -> '.join(chain_info)}")

    remaining = len(workflow_chains) - sum(shown.values())
    if remaining > 0:
        print(f"  ... and {remaining} more chains")

    # Agent dispatch
    print(f"\n{'─' * 70}")
    print(f"  AGENT DISPATCH")
    print(f"{'─' * 70}")
    print(f"  {'Model':<20} {'Tasks':>8} {'Cap':>8} {'$/M tok':>10} {'Quality':>8}")
    print(f"  {'─' * 58}")

    # Cloud models
    for model in CLOUD_MODELS:
        total = sum(
            agent_counts[f"{model['name']}-{i}"]
            for i in range(CLOUD_SESSIONS)
            if f"{model['name']}-{i}" in agent_counts
        )
        rate_per_m = model['token_rate'] * 1_000_000
        print(f"  {model['name'] + f' (x{CLOUD_SESSIONS})':<20} {total:>8} "
              f"{CLOUD_SESSIONS * CLOUD_CAPACITY:>8} ${rate_per_m:>9.2f} {model['quality']:>8.2f}")

    print(f"  {'─' * 58}")

    # Local models
    for model in LOCAL_MODELS:
        count = sum(
            agent_counts[f"{model['name']}-{i}"]
            for i in range(LOCAL_COUNT)
            if f"{model['name']}-{i}" in agent_counts
        )
        total_cap = LOCAL_COUNT * model['capacity']
        print(f"  {model['name'] + f' (x{LOCAL_COUNT})':<20} {count:>8} "
              f"{total_cap:>8} $0.00     {model['quality']:>8.2f}")

    # Cost efficiency
    cloud_tasks = sum(1 for a in assignments.values() if not agents[a]['is_local'])
    local_tasks = len(assignments) - cloud_tasks

    print(f"\n{'─' * 70}")
    print(f"  COST EFFICIENCY")
    print(f"{'─' * 70}")
    print(f"  Local (free):   {local_tasks} tasks  - $0.00")
    print(f"  Cloud (paid):   {cloud_tasks} tasks  - ${money_spent:.2f}")
    print(f"  Avg cost/task:  ${money_spent / max(len(assignments), 1):.4f}")

    if overkill:
        print(f"\n  OVERKILL ({len(overkill)} expensive models on simple tasks)")
        for line in overkill[:5]:
            print(line)
        if len(overkill) > 5:
            print(f"  ... and {len(overkill) - 5} more")

    if capacity_violations:
        print(f"\n  OVERLOADED AGENTS")
        for line in capacity_violations[:5]:
            print(line)
        if len(capacity_violations) > 5:
            print(f"  ... and {len(capacity_violations) - 5} more")

    # Sprint economics
    total_sp = sum(intents[i].get('story_points', 0) for i in assignments)
    total_tokens = sum(intents[i]['estimated_tokens'] for i in assignments)

    print(f"\n{'─' * 70}")
    print(f"  SPRINT ECONOMICS")
    print(f"{'─' * 70}")
    print(f"  Total story points:  {total_sp}")
    print(f"  Cost per SP:         ${money_spent / max(total_sp, 1):.4f}")
    print(f"  Tokens per SP:       {total_tokens / max(total_sp, 1):.0f}")

    print(f"\n  {'Tier':<15} {'Count':>8} {'SP':>4} {'Total SP':>10} {'Cost':>12}")
    print(f"  {'─' * 53}")
    tier_stats = defaultdict(lambda: {'count': 0, 'sp': 0, 'cost': 0.0})
    for i, agent_name in assignments.items():
        tier = intents[i]['complexity']
        sp = intents[i].get('story_points', 0)
        cost = intents[i]['estimated_tokens'] * agents[agent_name]['token_rate']
        tier_stats[tier]['count'] += 1
        tier_stats[tier]['sp'] += sp
        tier_stats[tier]['cost'] += cost

    for complexity in ['trivial', 'simple', 'moderate', 'complex', 'very-complex', 'epic']:
        s = tier_stats[complexity]
        if s['count'] > 0:
            sp_val = cfg.STORY_POINTS.get(complexity, 0)
            print(f"  {complexity:<15} {s['count']:>8} {sp_val:>4} {s['sp']:>10} ${s['cost']:>10.2f}")

    print(f"\n  Sprint capacity projections:")
    print(f"    70% load:   {int(total_sp * 0.7):>6} SP   ${money_spent * 0.7:.2f}")
    print(f"   100% load:   {total_sp:>6} SP   ${money_spent:.2f}")
    print(f"   140% load:   {int(total_sp * 1.4):>6} SP   ${money_spent * 1.4:.2f}")


def print_comparison(anneal_assignments, greedy_assignments, greedy_cost, intents, agents):
    """Print head-to-head comparison of annealing vs greedy.

    Args:
        anneal_assignments: Dict from annealing solver
        greedy_assignments: Dict from greedy solver
        greedy_cost: Total cost from greedy
        intents: List of intent dicts
        agents: Dict of agent definitions
    """
    num_intents = len(intents)

    # Cloud vs local breakdown
    greedy_cloud = sum(1 for a in greedy_assignments.values() if not agents[a]['is_local'])
    greedy_local = len(greedy_assignments) - greedy_cloud

    anneal_cloud = sum(1 for a in anneal_assignments.values() if not agents[a]['is_local'])
    anneal_local = len(anneal_assignments) - anneal_cloud

    money_spent = sum(
        intents[i]['estimated_tokens'] * agents[a]['token_rate']
        for i, a in anneal_assignments.items()
    )
    unassigned = num_intents - len(anneal_assignments)

    # Dependency violations
    greedy_dep_violations = 0
    anneal_dep_violations = 0
    for i, intent in enumerate(intents):
        for dep_idx in intent.get('depends', []):
            if i in greedy_assignments and dep_idx in greedy_assignments:
                if agents[greedy_assignments[i]]['quality'] < agents[greedy_assignments[dep_idx]]['quality']:
                    greedy_dep_violations += 1
            if i in anneal_assignments and dep_idx in anneal_assignments:
                if agents[anneal_assignments[i]]['quality'] < agents[anneal_assignments[dep_idx]]['quality']:
                    anneal_dep_violations += 1

    # Story points
    greedy_sp = sum(intents[i].get('story_points', 0) for i in greedy_assignments)
    anneal_sp = sum(intents[i].get('story_points', 0) for i in anneal_assignments)
    greedy_cost_per_sp = greedy_cost / max(greedy_sp, 1)
    anneal_cost_per_sp = money_spent / max(anneal_sp, 1)

    # Print comparison
    print("=" * 70)
    print("  HEAD TO HEAD: GREEDY vs QUANTUM ANNEALING")
    print("  10K CSS Renderer Task Routing")
    print("=" * 70)
    print(f"\n  {'Metric':<30} {'Greedy':<15} {'Annealing':<15}")
    print(f"  {'─' * 62}")
    print(f"  {'Tasks shipped':<30} {len(greedy_assignments):<15} {len(anneal_assignments):<15}")
    print(f"  {'Tasks dropped':<30} {num_intents - len(greedy_assignments):<15} {unassigned:<15}")
    print(f"  {'Money spent':<30} ${greedy_cost:<14.2f} ${money_spent:<14.2f}")
    print(f"  {'Story points':<30} {greedy_sp:<15} {anneal_sp:<15}")
    print(f"  {'Cost per SP':<30} ${greedy_cost_per_sp:<14.4f} ${anneal_cost_per_sp:<14.4f}")
    print(f"  {'Cloud tasks':<30} {greedy_cloud:<15} {anneal_cloud:<15}")
    print(f"  {'Local tasks (free)':<30} {greedy_local:<15} {anneal_local:<15}")
    print(f"  {'Dep violations':<30} {greedy_dep_violations:<15} {anneal_dep_violations:<15}")

    # Insights
    print()
    if len(anneal_assignments) > len(greedy_assignments):
        print(f"  → Annealing shipped {len(anneal_assignments) - len(greedy_assignments)} more tasks")
    if money_spent < greedy_cost:
        print(f"  → Annealing saved ${greedy_cost - money_spent:.2f}")
    elif money_spent > greedy_cost:
        print(f"  → Greedy was ${money_spent - greedy_cost:.2f} cheaper")
    if anneal_sp > greedy_sp:
        print(f"  → Annealing delivered {anneal_sp - greedy_sp} more story points")
    if anneal_local > greedy_local:
        print(f"  → Annealing used {anneal_local - greedy_local} more free local agents")
    if greedy_dep_violations > anneal_dep_violations:
        print(f"  → Annealing had {greedy_dep_violations - anneal_dep_violations} fewer dependency violations")


def print_pipeline_flow(assignments, intents, agents):
    """Print the flow of work through the CSS pipeline stages.

    Args:
        assignments: Dict mapping intent index to agent name
        intents: List of intent dicts
        agents: Dict of agent definitions
    """
    print("\n" + "=" * 70)
    print("  CSS PIPELINE FLOW ANALYSIS")
    print("=" * 70)

    # Analyze each stage
    for stage in cfg.PIPELINE_STAGES:
        stage_intents = [(i, intent) for i, intent in enumerate(intents) if intent['stage'] == stage]
        assigned = [i for i, _ in stage_intents if i in assignments]

        # Quality distribution
        quality_dist = defaultdict(int)
        for i in assigned:
            q = agents[assignments[i]]['quality']
            if q >= 0.9:
                quality_dist['excellent (0.9+)'] += 1
            elif q >= 0.8:
                quality_dist['good (0.8-0.9)'] += 1
            elif q >= 0.6:
                quality_dist['fair (0.6-0.8)'] += 1
            else:
                quality_dist['basic (<0.6)'] += 1

        print(f"\n  {stage.upper()}")
        print(f"    Tasks: {len(assigned)}/{len(stage_intents)} assigned")
        print(f"    Quality distribution:")
        for q_class, count in sorted(quality_dist.items()):
            pct = 100 * count / max(len(assigned), 1)
            print(f"      {q_class}: {count} ({pct:.1f}%)")


if __name__ == '__main__':
    # Test reporting
    from css_renderer_intents import generate_intents, build_workflow_chains
    from css_renderer_agents import build_agent_pool
    from solve_10k import greedy_solve

    print("Testing 10K Reporting")
    print("=" * 50)

    agents, agent_names = build_agent_pool()
    intents = generate_intents()
    workflow_chains = build_workflow_chains(intents)

    # Run greedy to get some assignments
    greedy_assignments, greedy_cost = greedy_solve(intents, agents)

    print("\n")
    print_shift_report(greedy_assignments, intents, agents, workflow_chains)
