"""Intent generation and CSS pipeline dependency chains for 10K CSS Renderer."""

import css_renderer_config as cfg

# CSS Renderer task templates by pipeline stage
CSS_TASK_TEMPLATES = {
    'parsing': {
        'trivial': [
            'tokenize-whitespace', 'tokenize-comment', 'tokenize-delimiter',
            'tokenize-number', 'tokenize-string', 'tokenize-ident',
            'skip-invalid-token', 'record-line-number', 'normalize-newline',
        ],
        'simple': [
            'parse-property-name', 'parse-property-value', 'parse-declaration-end',
            'parse-selector-class', 'parse-selector-id', 'parse-selector-tag',
            'parse-selector-universal', 'parse-at-rule-start', 'parse-rule-end',
            'handle-syntax-error', 'recover-from-error', 'build-ast-node',
        ],
        'moderate': [
            'parse-at-rule-media', 'parse-at-rule-import', 'parse-at-rule-font-face',
            'parse-at-rule-keyframes', 'parse-complex-selector', 'parse-pseudo-class',
            'parse-pseudo-element', 'parse-attribute-selector', 'parse-combinator',
            'handle-nested-rules', 'parse-css-variables', 'validate-property-syntax',
        ],
        'complex': [
            'parse-selector-specificity', 'parse-at-rule-supports', 'parse-at-rule-layer',
            'parse-at-rule-container', 'parse-nesting-selector', 'parse-scope-pseudo',
            'parse-has-pseudo', 'parse-is-where-pseudo', 'build-selector-graph',
            'optimize-selector-match', 'parse-custom-media', 'parse-color-mix',
        ],
        'very-complex': [
            'implement-tokenizer-optimization', 'build-parser-cache',
            'implement-incremental-parse', 'optimize-ast-memory-layout',
        ],
    },
    'style_computation': {
        'trivial': [
            'lookup-inherited-property', 'lookup-initial-value', 'copy-computed-value',
            'resolve-css-variable-ref', 'apply-default-style', 'check-property-inheritance',
        ],
        'simple': [
            'match-class-selector', 'match-id-selector', 'match-tag-selector',
            'match-attribute-selector', 'compute-simple-specificity', 'resolve-color-value',
            'resolve-length-value', 'resolve-percentage-value', 'apply-user-agent-style',
        ],
        'moderate': [
            'match-complex-selector', 'match-pseudo-class', 'match-pseudo-element',
            'compute-cascade-priority', 'resolve-style-conflict', 'apply-important-declaration',
            'resolve-css-variable-definition', 'handle-style-invalidation', 'compute-font-metrics',
            'resolve-timing-function', 'resolve-transform-function', 'apply-media-query',
        ],
        'complex': [
            'compute-selector-specificity', 'resolve-cascade-for-property',
            'implement-style-sharing', 'handle-dynamic-pseudo-classes', 'compute-animated-values',
            'resolve-container-query', 'apply-container-style', 'compute-style-for-pseudo-element',
            'handle-style-recalc-optimization', 'implement-matched-property-cache',
        ],
        'very-complex': [
            'optimize-style-recalc', 'implement-incremental-style-update',
            'build-style-invalidation-graph', 'optimize-cascade-resolution',
        ],
    },
    'layout': {
        'trivial': [
            'compute-margin-top', 'compute-margin-bottom', 'compute-padding-left',
            'compute-border-width', 'compute-content-width', 'compute-min-height',
            'resolve-width-auto', 'resolve-height-auto', 'apply-box-sizing',
        ],
        'simple': [
            'compute-inline-layout', 'compute-block-layout', 'position-static-element',
            'compute-replaced-element-size', 'handle-overflow-clipping', 'compute-line-height',
            'resolve-vertical-align', 'compute-text-indent', 'handle-white-space',
        ],
        'moderate': [
            'compute-float-layout', 'compute-clearance', 'position-relative-element',
            'position-absolute-element', 'compute-containing-block', 'resolve-percentage-dimensions',
            'compute-margin-collapsing', 'handle-z-index-stacking', 'compute-scrollable-overflow',
            'implement-text-wrapping', 'compute-baseline-alignment', 'handle-writing-mode',
        ],
        'complex': [
            'compute-flexbox-layout', 'compute-flex-item-sizing', 'resolve-flex-grow',
            'resolve-flex-shrink', 'compute-flex-line-alignment', 'compute-grid-layout',
            'place-grid-items', 'resolve-grid-track-sizing', 'handle-grid-auto-placement',
            'compute-grid-alignment', 'implement-subgrid', 'compute-aspect-ratio',
        ],
        'very-complex': [
            'optimize-flexbox-performance', 'optimize-grid-performance',
            'implement-layout-pass-optimization', 'handle-layout-containment',
            'implement-layout-ng-migration', 'optimize-layout-cache',
        ],
        'epic': [
            'design-layout-engine-architecture', 'implement-parallel-layout',
            'build-layout-performance-profiler', 'design-layout-fragmentation',
        ],
    },
    'painting': {
        'trivial': [
            'paint-background-color', 'paint-solid-border', 'paint-text-run',
            'paint-decoration-line', 'paint-caret', 'paint-selection-highlight',
        ],
        'simple': [
            'paint-background-image', 'paint-linear-gradient', 'paint-radial-gradient',
            'paint-border-radius', 'paint-box-shadow', 'paint-text-shadow',
            'paint-outline', 'paint-column-rule', 'paint-scrollbars',
        ],
        'moderate': [
            'paint-conic-gradient', 'paint-repeating-gradient', 'paint-multiple-backgrounds',
            'paint-complex-border', 'paint-dashed-border', 'paint-image-border',
            'paint-filter-effects', 'paint-backdrop-filter', 'paint-clip-path',
            'paint-mask-image', 'paint-mix-blend-mode', 'paint-opacity-layer',
        ],
        'complex': [
            'paint-css-transforms', 'paint-3d-transforms', 'paint-perspective',
            'paint-complex-clip', 'paint-svg-background', 'paint-css-shapes',
            'paint-print-styles', 'paint-forced-colors', 'implement-paint-recorder',
            'optimize-paint-operations', 'handle-paint-containment', 'paint-will-change',
        ],
        'very-complex': [
            'implement-gpu-rasterization', 'optimize-paint-layerization',
            'implement-display-list-optimization', 'build-paint-performance-profiler',
        ],
    },
    'compositing': {
        'simple': [
            'create-compositing-layer', 'destroy-compositing-layer', 'update-layer-bounds',
            'set-layer-transform', 'set-layer-opacity', 'set-layer-clip',
        ],
        'moderate': [
            'build-layer-tree', 'update-layer-tree', 'compute-layer-overlap',
            'handle-layer-promotion', 'implement-scroll-layer', 'handle-fixed-position-layer',
            'implement-sticky-position-layer', 'compute-layer-transform-hierarchy',
        ],
        'complex': [
            'generate-gpu-texture', 'update-gpu-texture', 'implement-tile-manager',
            'handle-layer-eviction', 'implement-layer-animation', 'optimize-layer-memory',
            'handle-high-dpi-rendering', 'implement-raster-worker', 'composite-layers-gpu',
            'handle-surface-synchronization', 'implement-damage-rect-tracking',
        ],
        'very-complex': [
            'implement-gpu-command-buffer', 'optimize-compositing-performance',
            'implement-frame-rate-optimization', 'handle-gpu-memory-pressure',
            'implement-compositor-thread', 'optimize-scrolling-performance',
        ],
        'epic': [
            'design-gpu-architecture', 'implement-vulkan-backend',
            'build-gpu-performance-profiler', 'design-compositor-architecture',
            'implement-webgpu-integration',
        ],
    },
}


def generate_intents():
    """Generate the full list of 10K CSS renderer intents.

    Returns:
        list of intent dicts with keys: id, stage, complexity, min_quality,
        depends, estimated_tokens, story_points.
    """
    intents = []
    intent_id = 0

    for stage in cfg.PIPELINE_STAGES:
        stage_count = cfg.STAGE_DISTRIBUTION[stage]
        complexity_dist = cfg.STAGE_COMPLEXITY[stage]
        templates = CSS_TASK_TEMPLATES[stage]

        # Calculate actual counts per complexity
        complexity_counts = {}
        remaining = stage_count
        for complexity, fraction, min_quality in complexity_dist[:-1]:
            count = int(stage_count * fraction)
            complexity_counts[complexity] = {
                'count': count,
                'min_quality': min_quality,
            }
            remaining -= count

        # Last complexity gets remaining tasks
        last_complexity, _, last_quality = complexity_dist[-1]
        complexity_counts[last_complexity] = {
            'count': remaining,
            'min_quality': last_quality,
        }

        # Generate intents for each complexity
        for complexity, data in complexity_counts.items():
            count = data['count']
            min_quality = data['min_quality']
            task_list = templates.get(complexity, ['generic-task'])

            for i in range(count):
                template = task_list[i % len(task_list)]
                intents.append({
                    'id': f'{stage}-{template}-{intent_id}',
                    'stage': stage,
                    'complexity': complexity,
                    'min_quality': min_quality,
                    'depends': [],
                    'estimated_tokens': cfg.TOKEN_ESTIMATES[complexity],
                    'story_points': cfg.STORY_POINTS[complexity],
                })
                intent_id += 1

    return intents


def build_workflow_chains(intents):
    """Create dependency chains between intents to model CSS pipeline workflows.

    Creates:
    - Intra-stage chains: Tasks within a stage that depend on each other
    - Cross-stage edges: API contracts between pipeline stages

    Mutates the intents list in-place (sets 'depends' fields).

    Returns:
        workflow_chains: list of (chain_type, step_indices) tuples.
    """
    workflow_chains = []
    used_in_chains = set()

    # Group intents by stage
    stage_intents = {stage: [] for stage in cfg.PIPELINE_STAGES}
    for idx, intent in enumerate(intents):
        stage_intents[intent['stage']].append(idx)

    def find_free_task(stage, min_complexity=None, max_complexity=None, exclude=None):
        """Find an unused intent in a stage with optional complexity filtering."""
        exclude = exclude or set()
        for idx in stage_intents[stage]:
            if idx in used_in_chains or idx in exclude:
                continue
            intent = intents[idx]
            if min_complexity and cfg.STORY_POINTS[intent['complexity']] < cfg.STORY_POINTS[min_complexity]:
                continue
            if max_complexity and cfg.STORY_POINTS[intent['complexity']] > cfg.STORY_POINTS[max_complexity]:
                continue
            return idx
        return None

    # Create intra-stage workflow chains
    chain_counts = cfg.WORKFLOW_CHAINS_PER_STAGE

    for stage in cfg.PIPELINE_STAGES:
        num_chains = chain_counts[stage]

        for _ in range(num_chains):
            # Different chain patterns based on stage
            if stage == 'parsing':
                # Tokenizer → Parser → Validator
                steps = [
                    find_free_task(stage, max_complexity='simple'),
                    find_free_task(stage, min_complexity='simple', max_complexity='moderate'),
                    find_free_task(stage, min_complexity='moderate'),
                ]
            elif stage == 'style_computation':
                # Selector match → Cascade → Apply
                steps = [
                    find_free_task(stage, max_complexity='simple'),
                    find_free_task(stage, min_complexity='simple', max_complexity='moderate'),
                    find_free_task(stage, min_complexity='moderate'),
                ]
            elif stage == 'layout':
                # Box model → Layout algorithm → Optimization
                steps = [
                    find_free_task(stage, max_complexity='simple'),
                    find_free_task(stage, min_complexity='simple', max_complexity='complex'),
                    find_free_task(stage, min_complexity='moderate'),
                ]
            elif stage == 'painting':
                # Background → Content → Effects
                steps = [
                    find_free_task(stage, max_complexity='simple'),
                    find_free_task(stage, min_complexity='simple', max_complexity='moderate'),
                    find_free_task(stage, min_complexity='moderate'),
                ]
            elif stage == 'compositing':
                # Layer creation → Tree build → GPU commands
                steps = [
                    find_free_task(stage, max_complexity='moderate'),
                    find_free_task(stage, min_complexity='simple', max_complexity='complex'),
                    find_free_task(stage, min_complexity='complex'),
                ]
            else:
                continue

            if all(s is not None for s in steps):
                # Create dependencies within the chain
                for k in range(1, len(steps)):
                    intents[steps[k]]['depends'].append(steps[k - 1])
                used_in_chains.update(steps)
                workflow_chains.append((f'{stage}-chain', steps))

    # Create cross-stage dependencies (API contracts)
    # Each stage has outputs that next stage depends on
    cross_stage_edges = 0
    max_cross_edges = cfg.CROSS_STAGE_EDGES

    for i in range(len(cfg.PIPELINE_STAGES) - 1):
        current_stage = cfg.PIPELINE_STAGES[i]
        next_stage = cfg.PIPELINE_STAGES[i + 1]

        # Find complex tasks in current stage that produce APIs
        current_complex = [idx for idx in stage_intents[current_stage]
                          if intents[idx]['complexity'] in ('complex', 'very-complex', 'epic')
                          and idx not in used_in_chains]

        # Find tasks in next stage that consume those APIs
        next_consumers = [idx for idx in stage_intents[next_stage]
                         if intents[idx]['complexity'] in ('moderate', 'complex')
                         and idx not in used_in_chains]

        # Create dependencies (each API producer → some consumers)
        edges_per_stage = max_cross_edges // (len(cfg.PIPELINE_STAGES) - 1)
        for producer in current_complex[:edges_per_stage]:
            if next_consumers:
                consumer = next_consumers.pop(0)
                intents[consumer]['depends'].append(producer)
                cross_stage_edges += 1
                used_in_chains.add(producer)
                used_in_chains.add(consumer)

    return workflow_chains


def get_intent_stats(intents):
    """Get statistics about the generated intents.

    Args:
        intents: List of intent dicts

    Returns:
        Dict with intent statistics
    """
    stats = {
        'total': len(intents),
        'by_stage': {},
        'by_complexity': {},
        'total_story_points': 0,
        'dependent_tasks': 0,
    }

    for intent in intents:
        stage = intent['stage']
        complexity = intent['complexity']

        stats['by_stage'][stage] = stats['by_stage'].get(stage, 0) + 1
        stats['by_complexity'][complexity] = stats['by_complexity'].get(complexity, 0) + 1
        stats['total_story_points'] += intent['story_points']
        if intent['depends']:
            stats['dependent_tasks'] += 1

    return stats


if __name__ == '__main__':
    # Test intent generation
    intents = generate_intents()
    workflow_chains = build_workflow_chains(intents)
    stats = get_intent_stats(intents)

    print("CSS Renderer Intents (10K Tasks)")
    print("=" * 50)
    print(f"Total intents: {stats['total']}")
    print(f"Total story points: {stats['total_story_points']}")
    print(f"Dependent tasks: {stats['dependent_tasks']}")
    print(f"Workflow chains: {len(workflow_chains)}")
    print()

    print("By Stage:")
    for stage in cfg.PIPELINE_STAGES:
        count = stats['by_stage'].get(stage, 0)
        print(f"  {stage}: {count}")

    print()
    print("By Complexity:")
    for complexity in ['trivial', 'simple', 'moderate', 'complex', 'very-complex', 'epic']:
        count = stats['by_complexity'].get(complexity, 0)
        sp = cfg.STORY_POINTS[complexity]
        print(f"  {complexity}: {count} tasks, {count * sp} SP")
