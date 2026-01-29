"""Reporting functions for QAAS routing results."""

from collections import defaultdict

from agents import CLOUD_MODELS, LOCAL_MODELS
from intents import DISTRIBUTION
import config as cfg


def print_shift_report(assignments, intents, agents, workflow_chains):
    """Print the full factory floor shift report for a set of assignments."""
    num_intents = len(intents)

    agent_counts = defaultdict(int)
    for agent in assignments.values():
        agent_counts[agent] += 1

    money_spent = sum(intents[i]['estimated_tokens'] * agents[a]['token_rate'] for i, a in assignments.items())
    quality_met = sum(1 for i, a in assignments.items() if agents[a]['quality'] >= intents[i]['min_quality'])
    unassigned = [i for i in range(num_intents) if i not in assignments]

    capacity_violations = []
    for name, count in agent_counts.items():
        if count > agents[name]['capacity']:
            capacity_violations.append(f"  {name}: {count}/{agents[name]['capacity']}")

    dep_violations = 0
    for i, intent in enumerate(intents):
        for dep_idx in intent.get('depends', []):
            if i in assignments and dep_idx in assignments:
                if agents[assignments[i]]['quality'] < agents[assignments[dep_idx]]['quality']:
                    dep_violations += 1

    overkill = []
    for i, name in assignments.items():
        if intents[i]['complexity'] in ('trivial', 'simple') and agents[name]['token_rate'] > 0.00001:
            overkill.append(f"  {intents[i]['id']} -> {name}")

    print("=" * 60)
    print("  FACTORY FLOOR SHIFT REPORT")
    print("=" * 60)
    print(f"\n  Tasks completed:     {len(assignments)}/{num_intents}")
    print(f"  Tasks dropped:       {len(unassigned)}")
    print(f"  Money spent:         ${money_spent:.2f}")
    print(f"  Quality targets met: {quality_met}/{len(assignments)}")
    print(f"  Capacity violations: {len(capacity_violations)}")
    print(f"  Dep violations:      {dep_violations}")

    # Workflow chain quality progression (sample)
    print(f"\n{'─' * 60}")
    print(f"  WORKFLOW CHAIN QUALITY PROGRESSION (sample)")
    print(f"{'─' * 60}")

    shown = defaultdict(int)
    for wf_type, steps in workflow_chains:
        if shown[wf_type] >= 3:
            continue
        shown[wf_type] += 1
        chain_info = []
        for s in steps:
            if s in assignments:
                a = assignments[s]
                q = agents[a]['quality']
                chain_info.append(f"{a}({q})")
            else:
                chain_info.append("UNASSIGNED")
        print(f"  {wf_type}: {' -> '.join(chain_info)}")

    remaining = len(workflow_chains) - sum(shown.values())
    if remaining > 0:
        print(f"  ... and {remaining} more chains")

    # Agent dispatch
    print(f"\n{'─' * 60}")
    print(f"  AGENT DISPATCH")
    print(f"{'─' * 60}")
    print(f"  {'Model':<20} {'Tasks':<8} {'Cap':<6} {'$/M tok':<10} {'Quality'}")
    print(f"  {'─' * 54}")

    for model in CLOUD_MODELS:
        total = sum(agent_counts[f"{model['name']}-{i}"] for i in range(10))
        rate_per_m = model['token_rate'] * 1_000_000
        print(f"  {model['name'] + ' (x10)':<20} {total:<8} {250:<6} ${rate_per_m:<9.2f} {model['quality']}")

    print(f"  {'─' * 54}")

    for model in LOCAL_MODELS:
        count = agent_counts[model['name']]
        print(f"  {model['name']:<20} {count:<8} {model['capacity']:<6} $0.00     {model['quality']}")

    cloud_tasks = sum(1 for a in assignments.values() if not agents[a]['is_local'])
    local_tasks = len(assignments) - cloud_tasks

    print(f"\n{'─' * 60}")
    print(f"  COST EFFICIENCY")
    print(f"{'─' * 60}")
    print(f"  Local (free):  {local_tasks} tasks  - $0.00")
    print(f"  Cloud (paid):  {cloud_tasks} tasks  - ${money_spent:.2f}")
    print(f"  Avg cost/task: ${money_spent / max(len(assignments), 1):.4f}")

    if overkill:
        print(f"\n  OVERKILL ({len(overkill)} expensive models on simple tasks)")
        for line in overkill[:5]:
            print(line)
        if len(overkill) > 5:
            print(f"  ... and {len(overkill) - 5} more")

    if capacity_violations:
        print(f"\n  OVERLOADED AGENTS")
        for line in capacity_violations:
            print(line)

    # Sprint economics
    total_sp = sum(intents[i].get('story_points', 0) for i in assignments)
    total_tokens = sum(intents[i]['estimated_tokens'] for i in assignments)

    print(f"\n{'─' * 60}")
    print(f"  SPRINT ECONOMICS")
    print(f"{'─' * 60}")
    print(f"  Total story points:  {total_sp}")
    print(f"  Cost per SP:         ${money_spent / max(total_sp, 1):.4f}")
    print(f"  Tokens per SP:       {total_tokens / max(total_sp, 1):.0f}")

    print(f"\n  {'Tier':<15} {'Count':>6} {'SP':>4} {'Total SP':>9} {'Cost':>10}")
    print(f"  {'─' * 48}")
    tier_stats = defaultdict(lambda: {'count': 0, 'sp': 0, 'cost': 0.0})
    for i, agent_name in assignments.items():
        tier = intents[i]['complexity']
        sp = intents[i].get('story_points', 0)
        cost = intents[i]['estimated_tokens'] * agents[agent_name]['token_rate']
        tier_stats[tier]['count'] += 1
        tier_stats[tier]['sp'] += sp
        tier_stats[tier]['cost'] += cost

    for complexity, _, _ in DISTRIBUTION:
        s = tier_stats[complexity]
        if s['count'] > 0:
            print(f"  {complexity:<15} {s['count']:>6} {cfg.STORY_POINTS.get(complexity, 0):>4} {s['sp']:>9} ${s['cost']:>9.2f}")

    print(f"\n  Sprint capacity projections:")
    print(f"    70% load:  {int(total_sp * 0.7):>5} SP   ${money_spent * 0.7:.2f}")
    print(f"   100% load:  {total_sp:>5} SP   ${money_spent:.2f}")
    print(f"   140% load:  {int(total_sp * 1.4):>5} SP   ${money_spent * 1.4:.2f}")


def print_comparison(anneal_assignments, greedy_assignments, greedy_cost, intents, agents):
    """Print head-to-head comparison of annealing vs greedy."""
    num_intents = len(intents)

    greedy_cloud = sum(1 for a in greedy_assignments.values() if not agents[a]['is_local'])
    greedy_local = len(greedy_assignments) - greedy_cloud

    anneal_cloud = sum(1 for a in anneal_assignments.values() if not agents[a]['is_local'])
    anneal_local = len(anneal_assignments) - anneal_cloud

    money_spent = sum(intents[i]['estimated_tokens'] * agents[a]['token_rate'] for i, a in anneal_assignments.items())
    unassigned = num_intents - len(anneal_assignments)

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

    greedy_sp = sum(intents[i].get('story_points', 0) for i in greedy_assignments)
    anneal_sp = sum(intents[i].get('story_points', 0) for i in anneal_assignments)
    greedy_cost_per_sp = greedy_cost / max(greedy_sp, 1)
    anneal_cost_per_sp = money_spent / max(anneal_sp, 1)

    print("=" * 60)
    print("  HEAD TO HEAD: GREEDY vs ANNEALING")
    print("=" * 60)
    print(f"\n  {'Metric':<25} {'Greedy':<15} {'Annealing':<15}")
    print(f"  {'─' * 55}")
    print(f"  {'Tasks shipped':<25} {len(greedy_assignments):<15} {len(anneal_assignments):<15}")
    print(f"  {'Tasks dropped':<25} {num_intents - len(greedy_assignments):<15} {unassigned:<15}")
    print(f"  {'Money spent':<25} ${greedy_cost:<14.2f} ${money_spent:<14.2f}")
    print(f"  {'Story points':<25} {greedy_sp:<15} {anneal_sp:<15}")
    print(f"  {'Cost per SP':<25} ${greedy_cost_per_sp:<14.4f} ${anneal_cost_per_sp:<14.4f}")
    print(f"  {'Cloud tasks':<25} {greedy_cloud:<15} {anneal_cloud:<15}")
    print(f"  {'Local tasks (free)':<25} {greedy_local:<15} {anneal_local:<15}")
    print(f"  {'Dep violations':<25} {greedy_dep_violations:<15} {anneal_dep_violations:<15}")

    if len(anneal_assignments) > len(greedy_assignments):
        print(f"\n  -> Annealing shipped {len(anneal_assignments) - len(greedy_assignments)} more tasks")
    if money_spent < greedy_cost:
        print(f"  -> Annealing saved ${greedy_cost - money_spent:.2f}")
    elif money_spent > greedy_cost:
        print(f"  -> Greedy was ${money_spent - greedy_cost:.2f} cheaper")
    if anneal_sp > greedy_sp:
        print(f"  -> Annealing delivered {anneal_sp - greedy_sp} more story points")
    if anneal_local > greedy_local:
        print(f"  -> Annealing used {anneal_local - greedy_local} more free local agents")
    if greedy_dep_violations > anneal_dep_violations:
        print(f"  -> Annealing had {greedy_dep_violations - anneal_dep_violations} fewer dependency violations")
