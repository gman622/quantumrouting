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
print(f'  Solved in {time.time() - t0:.1f}s — {len(assignments)}/{len(intents)} assigned')

# Current state — updated on re-solve
current_assignments = assignments
current_constraints = {
    'quality_floor': 0.0,
    'budget_cap': 10000.0,
    'overkill_weight': 2.0,
    'dep_penalty': 100.0,
    'context_bonus': 0.5,
}

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
    global current_assignments
    # Find the latest completed job and use its assignments
    latest = None
    for job in solver.jobs.values():
        if job.status == 'completed' and job.assignments is not None:
            if latest is None or job.elapsed > 0:
                latest = job
    if latest and latest.assignments:
        current_assignments = latest.assignments

    meta = get_assignments_metadata(current_assignments, intents, agents)
    meta['constraints'] = current_constraints
    socketio.emit('assignments_updated', meta)


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
