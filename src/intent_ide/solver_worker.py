"""Background solver thread for Intent IDE.

Runs CP-SAT solver with updated constraint overrides in a background thread.
Emits progress and completion events via Flask-SocketIO.
"""

import threading
import time
import uuid
from collections import defaultdict

from ortools.sat.python import cp_model

from quantum_routing import css_renderer_config as cfg
from quantum_routing.css_renderer_agents import can_assign


COST_SCALE = 1_000_000
QUALITY_SCALE = 100


class SolverJob:
    __slots__ = ('job_id', 'status', 'started', 'elapsed', 'assignments', 'error')

    def __init__(self, job_id):
        self.job_id = job_id
        self.status = 'pending'
        self.started = None
        self.elapsed = 0
        self.assignments = None
        self.error = None


class SolverWorker:
    """Manages background solve jobs."""

    def __init__(self, intents, agents, agent_names, socketio):
        self.intents = intents
        self.agents = agents
        self.agent_names = agent_names
        self.socketio = socketio
        self.jobs = {}
        self._lock = threading.Lock()

        # Pre-compute model types (collapse identical agents)
        self.model_types, self.type_index = self._build_model_types()

    def _build_model_types(self):
        type_map = {}
        model_types = []
        for name in self.agent_names:
            a = self.agents[name]
            mt = a['model_type']
            if mt not in type_map:
                type_map[mt] = len(model_types)
                model_types.append({
                    'name': mt,
                    'token_rate': a['token_rate'],
                    'quality': a['quality'],
                    'capabilities': a['capabilities'],
                    'is_local': a['is_local'],
                    'capacity': a['capacity'],
                    'latency': a['latency'],
                    'instances': [],
                    'total_capacity': 0,
                })
            idx = type_map[mt]
            model_types[idx]['instances'].append(name)
            model_types[idx]['total_capacity'] += a['capacity']

        type_index = {}
        for name in self.agent_names:
            mt = self.agents[name]['model_type']
            type_index[name] = type_map[mt]

        return model_types, type_index

    def submit(self, constraints):
        """Submit a new solve job. Returns job_id."""
        job_id = str(uuid.uuid4())[:8]
        job = SolverJob(job_id)
        with self._lock:
            self.jobs[job_id] = job

        thread = threading.Thread(
            target=self._run_solve,
            args=(job, constraints),
            daemon=True,
        )
        thread.start()
        return job_id

    def get_job(self, job_id):
        with self._lock:
            return self.jobs.get(job_id)

    def _run_solve(self, job, constraints):
        job.status = 'running'
        job.started = time.time()

        # Start progress ticker
        stop_event = threading.Event()
        ticker = threading.Thread(
            target=self._tick_progress, args=(job, stop_event), daemon=True
        )
        ticker.start()

        try:
            assignments = self._solve_cpsat(constraints)
            job.assignments = assignments
            job.status = 'completed'
        except Exception as e:
            job.error = str(e)
            job.status = 'failed'
        finally:
            job.elapsed = time.time() - job.started
            stop_event.set()
            self.socketio.emit('solver_completed', {
                'jobId': job.job_id,
                'status': job.status,
                'elapsed': round(job.elapsed, 1),
                'error': job.error,
            })

    def _tick_progress(self, job, stop_event):
        while not stop_event.is_set():
            elapsed = time.time() - job.started
            self.socketio.emit('solver_progress', {
                'jobId': job.job_id,
                'elapsed': round(elapsed, 1),
            })
            stop_event.wait(1.0)

    def _solve_cpsat(self, constraints):
        """Run CP-SAT with constraint overrides."""
        intents = self.intents
        model_types = self.model_types
        num_intents = len(intents)
        num_types = len(model_types)

        # Apply constraint overrides
        quality_floor = constraints.get('quality_floor', 0.0)
        overkill_weight = constraints.get('overkill_weight', cfg.OVERKILL_WEIGHT)
        dep_penalty = constraints.get('dep_penalty', cfg.DEP_PENALTY)
        context_bonus = constraints.get('context_bonus', cfg.CONTEXT_BONUS)
        time_limit = constraints.get('time_limit', 30)

        # Override min_quality if quality_floor is set
        effective_intents = []
        for intent in intents:
            eff = dict(intent)
            if quality_floor > 0:
                eff['min_quality'] = max(intent['min_quality'], quality_floor)
            effective_intents.append(eff)

        model = cp_model.CpModel()

        # Decision variables
        x = {}
        valid_types = defaultdict(list)
        for i, intent in enumerate(effective_intents):
            for t, mt in enumerate(model_types):
                if intent['complexity'] not in mt['capabilities']:
                    continue
                if mt['quality'] < intent['min_quality']:
                    continue
                x[i, t] = model.new_bool_var(f'x_{i}_{t}')
                valid_types[i].append(t)

        # Constraints
        for i in range(num_intents):
            if valid_types[i]:
                model.add_exactly_one(x[i, t] for t in valid_types[i])
        for t, mt in enumerate(model_types):
            model.add(
                sum(x[i, t] for i in range(num_intents) if (i, t) in x)
                <= mt['total_capacity']
            )

        # Objective
        objective_terms = []

        # Base cost + overkill
        for (i, t), var in x.items():
            intent = effective_intents[i]
            mt = model_types[t]
            token_cost = intent['estimated_tokens'] * mt['token_rate']
            surplus = mt['quality'] - intent['min_quality']
            overkill_cost = surplus * token_cost * overkill_weight
            latency_cost = mt['latency'] * cfg.LATENCY_WEIGHT
            cost = token_cost + overkill_cost + latency_cost
            objective_terms.append(int(cost * COST_SCALE) * var)

        # Dependency penalty
        dep_penalty_scaled = int(dep_penalty * COST_SCALE)
        for i, intent in enumerate(effective_intents):
            for dep_idx in intent.get('depends', []):
                if not valid_types[i] or not valid_types[dep_idx]:
                    continue
                q_i = sum(
                    int(model_types[t]['quality'] * QUALITY_SCALE) * x[i, t]
                    for t in valid_types[i]
                )
                q_dep = sum(
                    int(model_types[t]['quality'] * QUALITY_SCALE) * x[dep_idx, t]
                    for t in valid_types[dep_idx]
                )
                deficit = model.new_int_var(0, QUALITY_SCALE, f'def_{i}_{dep_idx}')
                model.add(deficit >= q_dep - q_i)
                objective_terms.append(dep_penalty_scaled * deficit)

        # Context affinity bonus
        affinity_scaled = int(context_bonus * COST_SCALE)
        if affinity_scaled > 0:
            for i, intent in enumerate(effective_intents):
                for dep_idx in intent.get('depends', []):
                    for t in valid_types[i]:
                        if t in valid_types[dep_idx]:
                            aff = model.new_bool_var(f'aff_{i}_{dep_idx}_{t}')
                            model.add_implication(aff, x[i, t])
                            model.add_implication(aff, x[dep_idx, t])
                            model.add_bool_or([aff, x[i, t].Not(), x[dep_idx, t].Not()])
                            objective_terms.append(-affinity_scaled * aff)

        model.minimize(sum(objective_terms))

        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit
        solver.parameters.num_workers = 0
        status = solver.solve(model)

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return {}

        # Extract type assignments
        type_assignments = {}
        for i in range(num_intents):
            for t in valid_types[i]:
                if solver.value(x[i, t]):
                    type_assignments[i] = t
                    break

        # Distribute to instances
        return self._distribute(type_assignments)

    def _distribute(self, type_assignments):
        instance_load = defaultdict(int)
        next_instance = defaultdict(int)
        assignments = {}

        for i, t in sorted(type_assignments.items()):
            mt = self.model_types[t]
            instances = mt['instances']
            num_inst = len(instances)
            per_cap = mt['capacity']

            assigned = False
            for _ in range(num_inst):
                idx = next_instance[t] % num_inst
                name = instances[idx]
                next_instance[t] += 1
                if instance_load[name] < per_cap:
                    assignments[i] = name
                    instance_load[name] += 1
                    assigned = True
                    break

            if not assigned:
                assignments[i] = instances[0]
                instance_load[instances[0]] += 1

        return assignments
