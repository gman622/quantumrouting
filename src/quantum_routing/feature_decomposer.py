"""LLM-style feature decomposition into realistic intent graphs.

This simulates what an LLM decomposer would produce given a feature request.
In production, this would call Claude/GPT to analyze the ticket and generate intents.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


@dataclass
class Intent:
    """An atomic unit of work."""
    id: str
    title: str
    description: str
    complexity: str  # trivial, simple, moderate, complex, very-complex
    min_quality: float
    depends: List[str] = field(default_factory=list)
    estimated_tokens: int = 1000
    tags: List[str] = field(default_factory=list)

    # Populated after routing
    assigned_agent: Optional[str] = None
    estimated_cost: Optional[float] = None
    status: str = "pending"


# Token estimates by complexity
TOKEN_ESTIMATES = {
    'trivial': 500,
    'simple': 1500,
    'moderate': 5000,
    'complex': 12000,
    'very-complex': 25000,
}

# Quality floors by complexity
QUALITY_FLOORS = {
    'trivial': 0.50,
    'simple': 0.60,
    'moderate': 0.75,
    'complex': 0.85,
    'very-complex': 0.92,
}


def decompose_realtime_collab_feature() -> List[Intent]:
    """Decompose 'Add real-time collaboration to Intent IDE' into intents.

    This is a hand-crafted example showing what an LLM decomposer would produce.
    The feature breaks down into ~25 intents across multiple phases.
    """

    intents = []

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 1: ANALYSIS & DESIGN
    # ══════════════════════════════════════════════════════════════════════════

    intents.append(Intent(
        id="collab-1-analyze-requirements",
        title="Analyze collaboration requirements",
        description="Review the feature request and extract detailed requirements. Identify edge cases, security considerations, and performance constraints.",
        complexity="simple",
        min_quality=QUALITY_FLOORS["simple"],
        estimated_tokens=TOKEN_ESTIMATES["simple"],
        tags=["analysis", "requirements"],
    ))

    intents.append(Intent(
        id="collab-2-research-sync-approaches",
        title="Research sync approaches",
        description="Evaluate CRDT vs OT vs last-write-wins for intent graph sync. Consider Yjs, Automerge, Socket.IO. Document tradeoffs.",
        complexity="moderate",
        min_quality=QUALITY_FLOORS["moderate"],
        estimated_tokens=TOKEN_ESTIMATES["moderate"],
        depends=["collab-1-analyze-requirements"],
        tags=["research", "architecture"],
    ))

    intents.append(Intent(
        id="collab-3-design-data-model",
        title="Design collaboration data model",
        description="Define the data structures for: user presence, cursor positions, intent locks, change operations. Design for conflict-free merging.",
        complexity="complex",
        min_quality=QUALITY_FLOORS["complex"],
        estimated_tokens=TOKEN_ESTIMATES["complex"],
        depends=["collab-2-research-sync-approaches"],
        tags=["design", "data-model"],
    ))

    intents.append(Intent(
        id="collab-4-design-api",
        title="Design WebSocket API",
        description="Define WebSocket events: join_session, leave_session, cursor_move, intent_lock, intent_unlock, constraint_change, sync_state. Document payload schemas.",
        complexity="moderate",
        min_quality=QUALITY_FLOORS["moderate"],
        estimated_tokens=TOKEN_ESTIMATES["moderate"],
        depends=["collab-3-design-data-model"],
        tags=["design", "api"],
    ))

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 2: BACKEND IMPLEMENTATION
    # ══════════════════════════════════════════════════════════════════════════

    intents.append(Intent(
        id="collab-5-session-manager",
        title="Implement session manager",
        description="Create SessionManager class to track active sessions, connected users, and their permissions. Store in Redis for multi-instance support.",
        complexity="moderate",
        min_quality=QUALITY_FLOORS["moderate"],
        estimated_tokens=TOKEN_ESTIMATES["moderate"],
        depends=["collab-4-design-api"],
        tags=["backend", "session"],
    ))

    intents.append(Intent(
        id="collab-6-presence-tracking",
        title="Implement presence tracking",
        description="Track which users are viewing which intents. Broadcast presence updates via WebSocket. Handle disconnects gracefully with timeout.",
        complexity="simple",
        min_quality=QUALITY_FLOORS["simple"],
        estimated_tokens=TOKEN_ESTIMATES["simple"],
        depends=["collab-5-session-manager"],
        tags=["backend", "presence"],
    ))

    intents.append(Intent(
        id="collab-7-optimistic-locking",
        title="Implement optimistic locking",
        description="Add intent-level locks for constraint editing. Implement lock acquisition, release, and timeout. Handle lock contention with queuing.",
        complexity="complex",
        min_quality=QUALITY_FLOORS["complex"],
        estimated_tokens=TOKEN_ESTIMATES["complex"],
        depends=["collab-5-session-manager"],
        tags=["backend", "locking"],
    ))

    intents.append(Intent(
        id="collab-8-state-sync",
        title="Implement state synchronization",
        description="Sync intent graph state across clients. Implement delta updates for efficiency. Handle reconnection with full state refresh.",
        complexity="complex",
        min_quality=QUALITY_FLOORS["complex"],
        estimated_tokens=TOKEN_ESTIMATES["complex"],
        depends=["collab-5-session-manager", "collab-7-optimistic-locking"],
        tags=["backend", "sync"],
    ))

    intents.append(Intent(
        id="collab-9-conflict-resolution",
        title="Implement conflict resolution",
        description="Handle concurrent constraint slider changes. Implement last-write-wins with vector clocks for ordering. Notify users of overwritten changes.",
        complexity="complex",
        min_quality=QUALITY_FLOORS["complex"],
        estimated_tokens=TOKEN_ESTIMATES["complex"],
        depends=["collab-8-state-sync"],
        tags=["backend", "conflict"],
    ))

    intents.append(Intent(
        id="collab-10-activity-feed-backend",
        title="Implement activity feed backend",
        description="Store and broadcast activity events: user joined, constraint changed, intent assigned, solver completed. Implement pagination for history.",
        complexity="moderate",
        min_quality=QUALITY_FLOORS["moderate"],
        estimated_tokens=TOKEN_ESTIMATES["moderate"],
        depends=["collab-5-session-manager"],
        tags=["backend", "activity"],
    ))

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 3: FRONTEND IMPLEMENTATION
    # ══════════════════════════════════════════════════════════════════════════

    intents.append(Intent(
        id="collab-11-websocket-client",
        title="Implement WebSocket client",
        description="Create React hook useCollaboration() that manages WebSocket connection, reconnection, and event handling. Integrate with Zustand store.",
        complexity="moderate",
        min_quality=QUALITY_FLOORS["moderate"],
        estimated_tokens=TOKEN_ESTIMATES["moderate"],
        depends=["collab-4-design-api"],
        tags=["frontend", "websocket"],
    ))

    intents.append(Intent(
        id="collab-12-presence-ui",
        title="Implement presence indicators",
        description="Show avatars/cursors of other users on the intent canvas. Display who's viewing which intent. Show user list in sidebar.",
        complexity="moderate",
        min_quality=QUALITY_FLOORS["moderate"],
        estimated_tokens=TOKEN_ESTIMATES["moderate"],
        depends=["collab-11-websocket-client", "collab-6-presence-tracking"],
        tags=["frontend", "presence", "ui"],
    ))

    intents.append(Intent(
        id="collab-13-lock-ui",
        title="Implement lock indicators",
        description="Show visual indicator when an intent is locked by another user. Display lock owner and timeout. Show 'waiting for lock' state.",
        complexity="simple",
        min_quality=QUALITY_FLOORS["simple"],
        estimated_tokens=TOKEN_ESTIMATES["simple"],
        depends=["collab-11-websocket-client", "collab-7-optimistic-locking"],
        tags=["frontend", "locking", "ui"],
    ))

    intents.append(Intent(
        id="collab-14-realtime-canvas-updates",
        title="Implement real-time canvas updates",
        description="Update intent node colors/status in real-time as other users make changes. Animate transitions. Handle rapid updates efficiently.",
        complexity="moderate",
        min_quality=QUALITY_FLOORS["moderate"],
        estimated_tokens=TOKEN_ESTIMATES["moderate"],
        depends=["collab-11-websocket-client", "collab-8-state-sync"],
        tags=["frontend", "canvas", "ui"],
    ))

    intents.append(Intent(
        id="collab-15-constraint-sync-ui",
        title="Implement constraint slider sync",
        description="Sync constraint panel sliders across clients. Show 'being edited by X' indicator. Handle conflict notification toast.",
        complexity="moderate",
        min_quality=QUALITY_FLOORS["moderate"],
        estimated_tokens=TOKEN_ESTIMATES["moderate"],
        depends=["collab-11-websocket-client", "collab-9-conflict-resolution"],
        tags=["frontend", "constraints", "ui"],
    ))

    intents.append(Intent(
        id="collab-16-activity-feed-ui",
        title="Implement activity feed UI",
        description="Create collapsible activity feed panel showing recent changes. Include timestamps, user avatars, action descriptions. Support infinite scroll.",
        complexity="simple",
        min_quality=QUALITY_FLOORS["simple"],
        estimated_tokens=TOKEN_ESTIMATES["simple"],
        depends=["collab-11-websocket-client", "collab-10-activity-feed-backend"],
        tags=["frontend", "activity", "ui"],
    ))

    intents.append(Intent(
        id="collab-17-intent-comments",
        title="Implement intent comments",
        description="Add comment thread UI to intent detail panel. Support @mentions, markdown formatting. Sync comments in real-time.",
        complexity="moderate",
        min_quality=QUALITY_FLOORS["moderate"],
        estimated_tokens=TOKEN_ESTIMATES["moderate"],
        depends=["collab-11-websocket-client"],
        tags=["frontend", "comments", "ui"],
    ))

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 4: TESTING
    # ══════════════════════════════════════════════════════════════════════════

    intents.append(Intent(
        id="collab-18-unit-tests-backend",
        title="Write backend unit tests",
        description="Test SessionManager, locking, conflict resolution. Mock Redis. Test edge cases: disconnects, timeouts, race conditions.",
        complexity="moderate",
        min_quality=QUALITY_FLOORS["moderate"],
        estimated_tokens=TOKEN_ESTIMATES["moderate"],
        depends=["collab-9-conflict-resolution", "collab-10-activity-feed-backend"],
        tags=["testing", "backend"],
    ))

    intents.append(Intent(
        id="collab-19-unit-tests-frontend",
        title="Write frontend unit tests",
        description="Test useCollaboration hook, presence updates, lock handling. Mock WebSocket. Test reconnection logic.",
        complexity="moderate",
        min_quality=QUALITY_FLOORS["moderate"],
        estimated_tokens=TOKEN_ESTIMATES["moderate"],
        depends=["collab-17-intent-comments"],
        tags=["testing", "frontend"],
    ))

    intents.append(Intent(
        id="collab-20-integration-tests",
        title="Write integration tests",
        description="Test full collaboration flow with multiple simulated clients. Verify sync latency < 500ms. Test conflict scenarios.",
        complexity="complex",
        min_quality=QUALITY_FLOORS["complex"],
        estimated_tokens=TOKEN_ESTIMATES["complex"],
        depends=["collab-18-unit-tests-backend", "collab-19-unit-tests-frontend"],
        tags=["testing", "integration"],
    ))

    intents.append(Intent(
        id="collab-21-load-testing",
        title="Perform load testing",
        description="Test with 50+ concurrent users. Measure latency, memory, CPU. Identify bottlenecks. Document performance characteristics.",
        complexity="moderate",
        min_quality=QUALITY_FLOORS["moderate"],
        estimated_tokens=TOKEN_ESTIMATES["moderate"],
        depends=["collab-20-integration-tests"],
        tags=["testing", "performance"],
    ))

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 5: DOCUMENTATION & POLISH
    # ══════════════════════════════════════════════════════════════════════════

    intents.append(Intent(
        id="collab-22-api-docs",
        title="Write API documentation",
        description="Document WebSocket events, payloads, error codes. Include sequence diagrams for common flows. Add to docs/.",
        complexity="simple",
        min_quality=QUALITY_FLOORS["simple"],
        estimated_tokens=TOKEN_ESTIMATES["simple"],
        depends=["collab-20-integration-tests"],
        tags=["docs", "api"],
    ))

    intents.append(Intent(
        id="collab-23-user-guide",
        title="Write collaboration user guide",
        description="Document how to use collaboration features. Include screenshots. Explain conflict resolution behavior.",
        complexity="trivial",
        min_quality=QUALITY_FLOORS["trivial"],
        estimated_tokens=TOKEN_ESTIMATES["trivial"],
        depends=["collab-20-integration-tests"],
        tags=["docs", "user-guide"],
    ))

    intents.append(Intent(
        id="collab-24-error-handling",
        title="Polish error handling",
        description="Add user-friendly error messages for: connection lost, lock timeout, sync failure. Implement automatic retry with backoff.",
        complexity="simple",
        min_quality=QUALITY_FLOORS["simple"],
        estimated_tokens=TOKEN_ESTIMATES["simple"],
        depends=["collab-20-integration-tests"],
        tags=["polish", "error-handling"],
    ))

    intents.append(Intent(
        id="collab-25-feature-flag",
        title="Add feature flag",
        description="Gate collaboration features behind ENABLE_COLLABORATION flag. Allow gradual rollout. Default to disabled.",
        complexity="trivial",
        min_quality=QUALITY_FLOORS["trivial"],
        estimated_tokens=TOKEN_ESTIMATES["trivial"],
        depends=["collab-24-error-handling"],
        tags=["release", "feature-flag"],
    ))

    return intents


def print_intent_graph(intents: List[Intent]):
    """Print the intent graph in a readable format."""
    print(f"\n{'='*70}")
    print(f"FEATURE: Add real-time collaboration to Intent IDE")
    print(f"{'='*70}")
    print(f"Total intents: {len(intents)}")

    total_tokens = sum(i.estimated_tokens for i in intents)
    print(f"Total estimated tokens: {total_tokens:,}")

    # Group by phase (using tags)
    phases = {}
    for intent in intents:
        phase = intent.tags[0] if intent.tags else "other"
        if phase not in phases:
            phases[phase] = []
        phases[phase].append(intent)

    # Complexity breakdown
    complexity_counts = {}
    for intent in intents:
        c = intent.complexity
        complexity_counts[c] = complexity_counts.get(c, 0) + 1

    print(f"\nComplexity breakdown:")
    for c in ['trivial', 'simple', 'moderate', 'complex', 'very-complex']:
        count = complexity_counts.get(c, 0)
        if count:
            print(f"  {c:12}: {count}")

    print(f"\n{'-'*70}")
    print("INTENT GRAPH:")
    print(f"{'-'*70}\n")

    for intent in intents:
        deps = f" ← [{', '.join(d.split('-')[-1] for d in intent.depends)}]" if intent.depends else ""
        print(f"[{intent.complexity:12}] {intent.id}")
        print(f"               {intent.title}{deps}")
        print()


def simulate_routing(intents: List[Intent]) -> Dict:
    """Simulate routing intents to agents and calculate costs."""

    # Simplified agent pool for simulation
    agents = {
        'claude': {'quality': 0.95, 'rate': 0.000020, 'capabilities': ['complex', 'very-complex', 'moderate', 'simple', 'trivial']},
        'gpt5.2': {'quality': 0.92, 'rate': 0.000030, 'capabilities': ['complex', 'moderate', 'simple', 'trivial']},
        'gemini': {'quality': 0.88, 'rate': 0.000005, 'capabilities': ['moderate', 'simple', 'trivial']},
        'kimi':   {'quality': 0.85, 'rate': 0.000002, 'capabilities': ['moderate', 'simple', 'trivial']},
        'llama':  {'quality': 0.65, 'rate': 0.000000, 'capabilities': ['simple', 'trivial']},
    }

    assignments = []
    total_cost = 0.0

    for intent in intents:
        # Find cheapest capable agent
        best_agent = None
        best_cost = float('inf')

        for name, agent in agents.items():
            if intent.complexity not in agent['capabilities']:
                continue
            if agent['quality'] < intent.min_quality:
                continue

            cost = intent.estimated_tokens * agent['rate']
            if cost < best_cost:
                best_cost = cost
                best_agent = name

        if best_agent:
            intent.assigned_agent = best_agent
            intent.estimated_cost = best_cost
            total_cost += best_cost
            assignments.append({
                'intent': intent.id,
                'agent': best_agent,
                'cost': best_cost,
                'tokens': intent.estimated_tokens,
            })

    return {
        'assignments': assignments,
        'total_cost': total_cost,
        'total_tokens': sum(a['tokens'] for a in assignments),
        'by_agent': _group_by_agent(assignments),
    }


def _group_by_agent(assignments: List[Dict]) -> Dict:
    """Group assignments by agent."""
    by_agent = {}
    for a in assignments:
        agent = a['agent']
        if agent not in by_agent:
            by_agent[agent] = {'count': 0, 'cost': 0.0, 'tokens': 0}
        by_agent[agent]['count'] += 1
        by_agent[agent]['cost'] += a['cost']
        by_agent[agent]['tokens'] += a['tokens']
    return by_agent


def decompose_slider_bug() -> List[Intent]:
    """Decompose 'Constraint sliders become unresponsive' bug into intents.

    Bugs have a different shape than features:
    - Reproduce → Diagnose → Fix → Test → Verify
    - Typically fewer intents, more focused
    - Higher quality requirements (can't ship a broken fix)
    """

    intents = []

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 1: REPRODUCE & DIAGNOSE
    # ══════════════════════════════════════════════════════════════════════════

    intents.append(Intent(
        id="bug2-1-reproduce",
        title="Create minimal reproduction",
        description="Set up test environment matching bug report. Reproduce the slider freeze with 10K graph. Capture console logs, network tab, performance profile.",
        complexity="trivial",
        min_quality=QUALITY_FLOORS["trivial"],
        estimated_tokens=TOKEN_ESTIMATES["trivial"],
        tags=["reproduce"],
    ))

    intents.append(Intent(
        id="bug2-2-profile-performance",
        title="Profile performance during freeze",
        description="Use Chrome DevTools Performance tab to capture CPU profile during rapid slider adjustments. Identify hot paths and blocking operations.",
        complexity="simple",
        min_quality=QUALITY_FLOORS["simple"],
        estimated_tokens=TOKEN_ESTIMATES["simple"],
        depends=["bug2-1-reproduce"],
        tags=["diagnose", "performance"],
    ))

    intents.append(Intent(
        id="bug2-3-analyze-solver-calls",
        title="Analyze solver invocation pattern",
        description="Add logging to track solver invocations. Confirm multiple concurrent solver runs. Measure time between slider change and solver start.",
        complexity="simple",
        min_quality=QUALITY_FLOORS["simple"],
        estimated_tokens=TOKEN_ESTIMATES["simple"],
        depends=["bug2-1-reproduce"],
        tags=["diagnose", "logging"],
    ))

    intents.append(Intent(
        id="bug2-4-identify-root-cause",
        title="Identify root cause",
        description="Correlate performance profile with solver logs. Confirm hypothesis: no debouncing + concurrent solver runs = resource exhaustion. Document findings.",
        complexity="moderate",
        min_quality=QUALITY_FLOORS["moderate"],
        estimated_tokens=TOKEN_ESTIMATES["moderate"],
        depends=["bug2-2-profile-performance", "bug2-3-analyze-solver-calls"],
        tags=["diagnose", "root-cause"],
    ))

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 2: FIX
    # ══════════════════════════════════════════════════════════════════════════

    intents.append(Intent(
        id="bug2-5-add-debounce",
        title="Add debounce to constraint sliders",
        description="Implement 300ms debounce on ConstraintPanel slider onChange. Use lodash.debounce or custom implementation. Ensure final value is always sent.",
        complexity="simple",
        min_quality=QUALITY_FLOORS["simple"],
        estimated_tokens=TOKEN_ESTIMATES["simple"],
        depends=["bug2-4-identify-root-cause"],
        tags=["fix", "frontend"],
    ))

    intents.append(Intent(
        id="bug2-6-solver-cancellation",
        title="Implement solver run cancellation",
        description="Add ability to cancel in-progress solver run when new request arrives. Use AbortController pattern. Clean up resources on cancellation.",
        complexity="moderate",
        min_quality=QUALITY_FLOORS["moderate"],
        estimated_tokens=TOKEN_ESTIMATES["moderate"],
        depends=["bug2-4-identify-root-cause"],
        tags=["fix", "backend"],
    ))

    intents.append(Intent(
        id="bug2-7-solver-queue",
        title="Implement solver request queue",
        description="Queue solver requests, process one at a time. Drop stale requests if newer one waiting. Add 'solving...' indicator to UI.",
        complexity="moderate",
        min_quality=QUALITY_FLOORS["moderate"],
        estimated_tokens=TOKEN_ESTIMATES["moderate"],
        depends=["bug2-6-solver-cancellation"],
        tags=["fix", "backend"],
    ))

    intents.append(Intent(
        id="bug2-8-websocket-reconnect",
        title="Fix WebSocket reconnection",
        description="Handle WebSocket disconnect gracefully. Implement exponential backoff reconnection. Queue messages during disconnect, replay on reconnect.",
        complexity="simple",
        min_quality=QUALITY_FLOORS["simple"],
        estimated_tokens=TOKEN_ESTIMATES["simple"],
        depends=["bug2-4-identify-root-cause"],
        tags=["fix", "websocket"],
    ))

    # ══════════════════════════════════════════════════════════════════════════
    # PHASE 3: TEST & VERIFY
    # ══════════════════════════════════════════════════════════════════════════

    intents.append(Intent(
        id="bug2-9-unit-test-debounce",
        title="Test debounce behavior",
        description="Write unit tests for slider debouncing. Test rapid changes, verify only final value triggers solver. Test edge cases: exact timing, unmount during debounce.",
        complexity="simple",
        min_quality=QUALITY_FLOORS["simple"],
        estimated_tokens=TOKEN_ESTIMATES["simple"],
        depends=["bug2-5-add-debounce"],
        tags=["test", "unit"],
    ))

    intents.append(Intent(
        id="bug2-10-unit-test-cancellation",
        title="Test solver cancellation",
        description="Write unit tests for solver cancellation. Verify resources cleaned up. Test cancellation at various solver stages. Mock long-running solves.",
        complexity="simple",
        min_quality=QUALITY_FLOORS["simple"],
        estimated_tokens=TOKEN_ESTIMATES["simple"],
        depends=["bug2-7-solver-queue"],
        tags=["test", "unit"],
    ))

    intents.append(Intent(
        id="bug2-11-regression-test",
        title="Add regression test for rapid slider adjustment",
        description="Create automated test that reproduces original bug: rapid slider adjustments on 10K graph. Verify no freeze, no errors, responsive UI throughout.",
        complexity="moderate",
        min_quality=QUALITY_FLOORS["moderate"],
        estimated_tokens=TOKEN_ESTIMATES["moderate"],
        depends=["bug2-9-unit-test-debounce", "bug2-10-unit-test-cancellation"],
        tags=["test", "regression"],
    ))

    intents.append(Intent(
        id="bug2-12-verify-fix",
        title="Verify fix in original environment",
        description="Test fix in exact environment from bug report (macOS 14.2, Chrome 121). Confirm sliders remain responsive. No console errors. Update bug ticket with results.",
        complexity="trivial",
        min_quality=QUALITY_FLOORS["trivial"],
        estimated_tokens=TOKEN_ESTIMATES["trivial"],
        depends=["bug2-11-regression-test"],
        tags=["verify"],
    ))

    return intents


def print_bug_graph(intents: List[Intent], title: str):
    """Print a bug's intent graph."""
    print(f"\n{'='*70}")
    print(f"BUG: {title}")
    print(f"{'='*70}")
    print(f"Total intents: {len(intents)}")

    total_tokens = sum(i.estimated_tokens for i in intents)
    print(f"Total estimated tokens: {total_tokens:,}")

    # Complexity breakdown
    complexity_counts = {}
    for intent in intents:
        c = intent.complexity
        complexity_counts[c] = complexity_counts.get(c, 0) + 1

    print(f"\nComplexity breakdown:")
    for c in ['trivial', 'simple', 'moderate', 'complex', 'very-complex']:
        count = complexity_counts.get(c, 0)
        if count:
            print(f"  {c:12}: {count}")

    print(f"\n{'-'*70}")
    print("INTENT GRAPH:")
    print(f"{'-'*70}\n")

    for intent in intents:
        deps = f" ← [{', '.join(d.split('-')[-1] for d in intent.depends)}]" if intent.depends else ""
        print(f"[{intent.complexity:12}] {intent.id}")
        print(f"               {intent.title}{deps}")
        print()


if __name__ == '__main__':
    import sys

    # Check command line args
    if len(sys.argv) > 1 and sys.argv[1] == 'bug':
        intents = decompose_slider_bug()
        print_bug_graph(intents, "Constraint sliders become unresponsive after rapid adjustments")
    else:
        # Generate and display the feature intent graph
        intents = decompose_realtime_collab_feature()
        print_intent_graph(intents)

    # Simulate routing
    print(f"\n{'='*70}")
    print("ROUTING SIMULATION")
    print(f"{'='*70}\n")

    result = simulate_routing(intents)

    print(f"Total cost: ${result['total_cost']:.2f}")
    print(f"Total tokens: {result['total_tokens']:,}")
    print(f"\nBy agent:")
    for agent, stats in sorted(result['by_agent'].items(), key=lambda x: -x[1]['cost']):
        print(f"  {agent:8}: {stats['count']:2} intents, {stats['tokens']:6,} tokens, ${stats['cost']:.2f}")

    print(f"\n{'-'*70}")
    print("ASSIGNMENTS:")
    print(f"{'-'*70}\n")

    for a in result['assignments']:
        print(f"  {a['intent']:40} → {a['agent']:8} (${a['cost']:.3f})")
