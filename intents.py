"""Intent generation and workflow dependency chains for QAAS."""

import datetime
import config as cfg

INTENT_TEMPLATES = {
    'trivial': [
        'fix-typo', 'fix-lint', 'fix-whitespace', 'fix-indent',
        'rename-var', 'sort-imports', 'remove-unused-import',
        'add-newline-eof', 'remove-console-log', 'fix-semicolon',
    ],
    'simple': [
        'add-type-hint', 'update-version-bump', 'fix-trailing-comma',
        'update-todo-comment', 'fix-bracket-style', 'swap-quotes',
        'add-missing-return', 'fix-null-check', 'update-env-var', 'fix-off-by-one',
    ],
    'moderate': [
        'implement-helper-function', 'write-unit-test', 'add-input-validation',
        'fix-bug-in-handler', 'add-error-handling', 'refactor-loop',
        'add-api-endpoint', 'update-db-query', 'add-retry-logic',
        'implement-dto', 'add-request-logging', 'fix-async-await',
        'add-rate-limiter', 'update-middleware', 'add-cache-layer',
        'implement-pagination', 'fix-memory-leak', 'add-health-check',
        'update-serializer', 'implement-webhook-handler',
        # absorbed from code-analysis
        'review-pr-for-bugs', 'find-security-vulns', 'analyze-dep-tree',
        'audit-test-coverage', 'find-dead-code', 'measure-cyclomatic-complexity',
        'review-error-handling', 'find-code-duplication',
    ],
    'complex': [
        'architect-new-service', 'design-db-schema', 'implement-auth-flow',
        'build-ci-cd-pipeline', 'migrate-to-graphql', 'optimize-query-perf',
        'implement-search-index', 'design-rest-api', 'build-admin-dashboard',
        'implement-job-queue', 'design-caching-strategy', 'build-monitoring',
        'implement-oauth2', 'design-microservice-split', 'build-etl-pipeline',
        'implement-graphql-schema', 'design-event-bus', 'build-deploy-pipeline',
        'implement-rate-limiting', 'design-db-sharding',
        # absorbed from reasoning
        'review-pr-architecture', 'debug-prod-incident', 'plan-migration-strategy',
        'evaluate-framework-choice', 'design-for-scale', 'analyze-security-surface',
        'plan-tech-debt-paydown', 'review-system-design', 'analyze-perf-bottleneck',
        'plan-rollback-strategy', 'evaluate-buy-vs-build', 'design-disaster-recovery',
    ],
    'very-complex': [
        'design-distributed-system', 'implement-consensus-protocol',
        'build-real-time-pipeline', 'architect-multi-region-deploy',
        'design-zero-downtime-migration', 'implement-cqrs-event-sourcing',
        'build-observability-platform', 'design-api-gateway',
        'implement-distributed-cache', 'architect-data-mesh',
    ],
    'epic': [
        'redesign-platform-architecture', 'build-ml-training-infra',
        'implement-multi-tenant-isolation', 'architect-global-cdn',
        'design-compliance-framework', 'build-developer-platform',
    ],
}

DISTRIBUTION = [
    ('trivial',       200, 0.40),
    ('simple',        300, 0.50),
    ('moderate',      250, 0.70),
    ('complex',       150, 0.85),
    ('very-complex',   70, 0.90),
    ('epic',           30, 0.95),
]

# --- Project Timeline ---
# Based on the goal to replace browsers/IDEs by the end of 2027.
PROJECT_START_DATE = datetime.date(2025, 1, 1)
PROJECT_END_DATE = datetime.date(2027, 12, 31)
PROJECT_DURATION_DAYS = (PROJECT_END_DATE - PROJECT_START_DATE).days
# Time buffer (in days) for each step in a dependency chain.
TIME_PER_STEP = {
    'trivial': 3, 'simple': 7, 'moderate': 14, 'complex': 21,
    'very-complex': 30, 'epic': 60,
}


def generate_intents():
    """Generate the full list of intents from templates and distribution."""
    intents = []
    intent_id = 0

    for complexity, count, min_quality in DISTRIBUTION:
        templates = INTENT_TEMPLATES[complexity]
        for i in range(count):
            template = templates[i % len(templates)]
            intents.append({
                'id': f'{template}-{intent_id}',
                'complexity': complexity,
                'min_quality': min_quality,
                'depends': [],
                'deadline': -1,  # Placeholder, will be set in build_workflow_chains
                'estimated_tokens': cfg.TOKEN_ESTIMATES[complexity],
                'story_points': cfg.STORY_POINTS[complexity],
            })
            intent_id += 1

    return intents


def build_workflow_chains(intents):
    """Create dependency chains between intents to model workflows.

    Mutates the intents list in-place (sets 'depends' and 'deadline' fields).

    Returns:
        workflow_chains: list of (chain_type, step_indices) tuples.
    """
    workflow_chains = []
    used_in_chains = set()

    def find_free_task(complexity):
        for idx, t in enumerate(intents):
            if t['complexity'] == complexity and idx not in used_in_chains and not t['depends']:
                return idx
        return None

    # 25 feature dev chains: spec -> impl -> review -> integrate
    for _ in range(25):
        steps = [
            find_free_task('trivial'),
            find_free_task('simple'),
            find_free_task('complex'),
            find_free_task('very-complex'),
        ]
        if all(s is not None for s in steps):
            for k in range(1, len(steps)):
                intents[steps[k]]['depends'] = [steps[k - 1]]
            used_in_chains.update(steps)
            workflow_chains.append(('feature-dev', steps))

    # 15 bug fix chains: triage -> reproduce -> fix
    for _ in range(15):
        steps = [
            find_free_task('simple'),
            find_free_task('moderate'),
            find_free_task('complex'),
        ]
        if all(s is not None for s in steps):
            for k in range(1, len(steps)):
                intents[steps[k]]['depends'] = [steps[k - 1]]
            used_in_chains.update(steps)
            workflow_chains.append(('bug-fix', steps))

    # 10 infra chains: design -> provision -> integrate
    for _ in range(10):
        steps = [
            find_free_task('moderate'),
            find_free_task('complex'),
            find_free_task('very-complex'),
        ]
        if all(s is not None for s in steps):
            for k in range(1, len(steps)):
                intents[steps[k]]['depends'] = [steps[k - 1]]
            used_in_chains.update(steps)
            workflow_chains.append(('infra', steps))

    # --- Assign Deadlines ---
    # Deadline = days from project start (smaller is more urgent)
    num_chains = len(workflow_chains)
    chain_completion_days = [
        int(PROJECT_DURATION_DAYS * (i + 1) / (num_chains + 1))
        for i in range(num_chains)
    ]

    chained_indices = set()
    for i, (chain_type, steps) in enumerate(workflow_chains):
        intents[steps[-1]]['deadline'] = chain_completion_days[i]
        chained_indices.add(steps[-1])

        for j in range(len(steps) - 2, -1, -1):
            next_task_complexity = intents[steps[j + 1]]['complexity']
            buffer_days = TIME_PER_STEP.get(next_task_complexity, 14)
            intents[steps[j]]['deadline'] = intents[steps[j + 1]]['deadline'] - buffer_days
            chained_indices.add(steps[j])

    independent_tasks = [
        i for i, intent in enumerate(intents) if i not in chained_indices
    ]
    num_independent = len(independent_tasks)
    for i, task_idx in enumerate(independent_tasks):
        deadline = int(PROJECT_DURATION_DAYS * (i + 1) / (num_independent + 1))
        intents[task_idx]['deadline'] = deadline

    for intent in intents:
        if intent['deadline'] < 0:
            intent['deadline'] = 0

    return workflow_chains

