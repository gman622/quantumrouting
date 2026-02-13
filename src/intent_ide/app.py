"""Intent IDE — Flask backend with WebSocket support.

Entry point: python -m intent_ide.app
Serves the React frontend from frontend/build/ and provides REST + WebSocket APIs.
"""

import os
import sys
import time

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO

# Add src/ to path so quantum_routing imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from quantum_routing.css_renderer_agents import build_agent_pool, get_agent_stats
from quantum_routing.css_renderer_intents import generate_intents, build_workflow_chains
from quantum_routing.solve_10k_ortools import solve_cpsat
from quantum_routing.telemetry import compute_metrics
from quantum_routing.github_tickets import (
    import_all_issues,
    import_issue,
    decompose_ticket,
    decompose_ticket_smart,
)
from quantum_routing.staffing_engine import generate_staffing_plan
from quantum_routing.github_backend import (
    ensure_agent_labels,
    create_companion_issues,
)
from quantum_routing.feature_decomposer import (
    decompose_realtime_collab_feature,
    decompose_slider_bug,
    simulate_routing,
)

from .graph_data import get_graph, get_assignments_metadata, get_agent_summary
from .solver_worker import SolverWorker

# ── Flask app setup ──────────────────────────────────────────────────────

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'build')

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

# ── Data initialization ─────────────────────────────────────────────────

print('Initializing agent pool...')
agents, agent_names = build_agent_pool()
agent_stats = get_agent_stats(agents)
print(f'  {agent_stats["total_agents"]} agents ({agent_stats["cloud_agents"]} cloud, {agent_stats["local_agents"]} local)')

print('Generating 10K intents...')
intents = generate_intents()
workflow_chains = build_workflow_chains(intents)
print(f'  {len(intents)} intents, {len(workflow_chains)} workflow chains')

print('Running initial CP-SAT solve (time_limit=30s)...')
t0 = time.time()
assignments = solve_cpsat(intents, agents, agent_names, time_limit=30)
solve_duration = time.time() - t0
print(f'  Solved in {solve_duration:.1f}s — {len(assignments)}/{len(intents)} assigned')

# Current state — updated on re-solve
current_assignments = assignments
current_constraints = {
    'quality_floor': 0.0,
    'budget_cap': 10000.0,
    'overkill_weight': 2.0,
    'dep_penalty': 100.0,
    'context_bonus': 0.5,
}

# Telemetry — compute metrics from initial solve
print('Computing telemetry metrics...')
current_metrics = compute_metrics(
    assignments, intents, agents, workflow_chains,
    solver_duration_s=solve_duration,
)
cc = current_metrics['chain_coherence']
cq = current_metrics['cost_quality']
gp = current_metrics['gate_pass']
print(f'  Chain coherence: {cc["score"]:.1%} ({cc["chains_single_model"]}/{cc["total_chains"]} single-model)')
print(f'  Cost/quality: ${cq["total_cost"]:.2f} total, ratio {cq["cost_quality_ratio"]:.4f}')
print(f'  Gate 1 pass: {gp["gate_1_pass_rate"]:.1%} ({gp["gate_1_passed"]}/{gp["gate_1_passed"] + gp["gate_1_failed"]})')

# Solver worker
solver = SolverWorker(intents, agents, agent_names, socketio)

# ── REST API ─────────────────────────────────────────────────────────────


@app.route('/api/graph')
def api_graph():
    zoom = request.args.get('zoom', 0, type=int)
    data = get_graph(zoom, intents, agents, current_assignments, workflow_chains)
    return jsonify(data)


@app.route('/api/assignments')
def api_assignments():
    meta = get_assignments_metadata(current_assignments, intents, agents)
    meta['constraints'] = current_constraints
    return jsonify(meta)


@app.route('/api/agents')
def api_agents():
    summary = get_agent_summary(current_assignments, intents, agents)
    stats = get_agent_stats(agents)
    return jsonify({'agents': summary, 'stats': stats})


@app.route('/api/intent/<int:intent_idx>')
def api_intent_detail(intent_idx):
    if intent_idx < 0 or intent_idx >= len(intents):
        return jsonify({'error': 'Invalid intent index'}), 404
    intent = intents[intent_idx]
    agent_name = current_assignments.get(intent_idx)
    agent = agents[agent_name] if agent_name else None
    cost = 0
    if agent_name:
        cost = intent['estimated_tokens'] * agents[agent_name]['token_rate']
    return jsonify({
        'intent': intent,
        'agentName': agent_name,
        'agent': agent,
        'cost': round(cost, 4),
    })


@app.route('/api/solve', methods=['POST'])
def api_solve():
    global current_constraints
    data = request.get_json() or {}
    constraints = {
        'quality_floor': data.get('quality_floor', current_constraints['quality_floor']),
        'budget_cap': data.get('budget_cap', current_constraints['budget_cap']),
        'overkill_weight': data.get('overkill_weight', current_constraints['overkill_weight']),
        'dep_penalty': data.get('dep_penalty', current_constraints['dep_penalty']),
        'context_bonus': data.get('context_bonus', current_constraints['context_bonus']),
        'time_limit': data.get('time_limit', 30),
    }
    current_constraints = {k: v for k, v in constraints.items() if k != 'time_limit'}
    job_id = solver.submit(constraints)
    return jsonify({'jobId': job_id})


@app.route('/api/solve/<job_id>')
def api_solve_status(job_id):
    job = solver.get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify({
        'jobId': job.job_id,
        'status': job.status,
        'elapsed': round(job.elapsed, 1),
        'error': job.error,
    })


@app.route('/api/metrics')
def api_metrics():
    """Return current telemetry metrics from the latest solver run."""
    return jsonify(current_metrics)


@app.route('/api/issues')
def api_issues():
    """Fetch GitHub issues and their decomposed intents."""
    repo = request.args.get('repo')  # Optional: "owner/repo" format
    issues_data = []

    # Try to fetch from GitHub
    try:
        tickets = import_all_issues(state='open', repo=repo)
    except Exception as e:
        print(f'Warning: Could not fetch GitHub issues: {e}')
        tickets = []

    # For demo: if we have the specific issues we created, use detailed decomposition
    for ticket in tickets:
        if ticket.id == '1':
            # Real-time collaboration feature
            intents = decompose_realtime_collab_feature()
            result = simulate_routing(intents)
            issues_data.append({
                'id': ticket.id,
                'title': ticket.title,
                'body': ticket.body[:200] + '...' if len(ticket.body) > 200 else ticket.body,
                'labels': ticket.labels,
                'ticketType': 'feature',
                'url': ticket.url,
                'intentIds': [i.id for i in intents],
                'intentCount': len(intents),
                'completedCount': 0,
                'totalCost': result['total_cost'],
                'status': 'pending',
            })
        elif ticket.id == '2':
            # Slider bug
            intents = decompose_slider_bug()
            result = simulate_routing(intents)
            issues_data.append({
                'id': ticket.id,
                'title': ticket.title,
                'body': ticket.body[:200] + '...' if len(ticket.body) > 200 else ticket.body,
                'labels': ticket.labels,
                'ticketType': 'bug',
                'url': ticket.url,
                'intentIds': [i.id for i in intents],
                'intentCount': len(intents),
                'completedCount': 0,
                'totalCost': result['total_cost'],
                'status': 'pending',
            })
        else:
            # Generic decomposition
            intent_specs = decompose_ticket(ticket)
            issues_data.append({
                'id': ticket.id,
                'title': ticket.title,
                'body': ticket.body[:200] + '...' if len(ticket.body) > 200 else ticket.body,
                'labels': ticket.labels,
                'ticketType': ticket.ticket_type.name.lower(),
                'url': ticket.url,
                'intentIds': [i['id'] for i in intent_specs],
                'intentCount': len(intent_specs),
                'completedCount': 0,
                'totalCost': 0.0,  # Would need routing to calculate
                'status': 'pending',
            })

    return jsonify({'issues': issues_data, 'total': len(issues_data)})


@app.route('/api/materialize', methods=['POST'])
def api_materialize():
    """Materialize companion issues for a GitHub issue.

    POST body: { "repo": "owner/repo" (optional), "issue_number": 13 }

    Decompose → staff → create 4 companion issues on GitHub.
    """
    data = request.get_json() or {}
    issue_number = data.get('issue_number')
    repo = data.get('repo') or None

    if not issue_number:
        return jsonify({'error': 'issue_number is required'}), 400

    try:
        issue_number = int(issue_number)
    except (ValueError, TypeError):
        return jsonify({'error': 'issue_number must be an integer'}), 400

    # Fetch the issue
    ticket = import_issue(issue_number, repo=repo)
    if ticket is None:
        return jsonify({'error': f'Could not fetch issue #{issue_number}'}), 404

    # Decompose into intents
    intent_specs = decompose_ticket_smart(ticket)
    if not intent_specs:
        return jsonify({'error': 'No intents generated from issue'}), 422

    # Generate staffing plan
    plan = generate_staffing_plan(intent_specs)

    # Ensure labels exist
    label_results = ensure_agent_labels(repo=repo)

    # Create companion issues
    created = create_companion_issues(
        parent_issue_number=issue_number,
        parent_title=ticket.title,
        staffing_plan=plan,
        repo=repo,
    )

    # Emit WebSocket event so frontend can update
    socketio.emit('materialize_completed', {
        'parent_issue': issue_number,
        'companion_issues': created,
        'staffing_plan': {
            'total_intents': plan['total_intents'],
            'total_waves': plan['total_waves'],
            'peak_parallelism': plan['peak_parallelism'],
            'total_estimated_cost': plan['total_estimated_cost'],
            'profile_load': plan['profile_load'],
        },
    })

    return jsonify({
        'parent_issue': issue_number,
        'parent_title': ticket.title,
        'companion_issues': created,
        'labels_created': sum(label_results.values()),
        'staffing_plan': {
            'total_intents': plan['total_intents'],
            'total_waves': plan['total_waves'],
            'peak_parallelism': plan['peak_parallelism'],
            'total_estimated_cost': plan['total_estimated_cost'],
            'profile_load': plan['profile_load'],
        },
    })


# ── WebSocket events ─────────────────────────────────────────────────────

@socketio.on('connect')
def handle_connect():
    print('Client connected')


@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')


@socketio.on('request_assignments')
def handle_request_assignments():
    """Client requests current assignments after solver completes."""
    global current_assignments, current_metrics
    # Find the latest completed job and use its assignments
    latest = None
    for job in solver.jobs.values():
        if job.status == 'completed' and job.assignments is not None:
            if latest is None or job.elapsed > 0:
                latest = job
    if latest and latest.assignments:
        current_assignments = latest.assignments
        # Recompute telemetry for the new assignments
        current_metrics = compute_metrics(
            current_assignments, intents, agents, workflow_chains,
            weights={
                'DEP_PENALTY': current_constraints['dep_penalty'],
                'OVERKILL_WEIGHT': current_constraints['overkill_weight'],
                'CONTEXT_BONUS': current_constraints['context_bonus'],
            },
            solver_duration_s=latest.elapsed,
        )

    meta = get_assignments_metadata(current_assignments, intents, agents)
    meta['constraints'] = current_constraints
    socketio.emit('assignments_updated', meta)
    socketio.emit('metrics_updated', current_metrics)


# ── Serve React frontend ─────────────────────────────────────────────────

@app.route('/')
def serve_index():
    if os.path.exists(os.path.join(FRONTEND_DIR, 'index.html')):
        return send_from_directory(FRONTEND_DIR, 'index.html')
    return '''
    <html><body style="font-family:monospace;padding:40px;background:#0f172a;color:#e2e8f0">
    <h1>Intent IDE</h1>
    <p>Backend is running. Frontend not built yet.</p>
    <p>API endpoints:</p>
    <ul>
        <li><a href="/api/graph?zoom=0" style="color:#60a5fa">/api/graph?zoom=0</a></li>
        <li><a href="/api/assignments" style="color:#60a5fa">/api/assignments</a></li>
        <li><a href="/api/agents" style="color:#60a5fa">/api/agents</a></li>
    </ul>
    </body></html>
    '''


@app.route('/<path:path>')
def serve_static(path):
    full = os.path.join(FRONTEND_DIR, path)
    if os.path.exists(full):
        return send_from_directory(FRONTEND_DIR, path)
    # SPA fallback
    index = os.path.join(FRONTEND_DIR, 'index.html')
    if os.path.exists(index):
        return send_from_directory(FRONTEND_DIR, 'index.html')
    return '', 404


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    port = int(os.environ.get('PORT', 5001))
    print(f'  Intent IDE running at http://localhost:{port}\n')
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)


if __name__ == '__main__':
    main()
