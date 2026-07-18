from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO, emit
from celery.result import AsyncResult
from .celery_app import app as celery_app
from .database import get_results, init_db, save_phase_result
from .tasks import build_phase_workflow
from .cli import collect_chain_results, collect_group_results
from .metasploit_api import metasploit_blueprint
from .metasploit_socketio import register_metasploit_socketio
import yaml
import time
import os
import uuid
import threading

app = Flask(__name__)
app.config['SECRET_KEY'] = 'cerberus-x-secret'
app.register_blueprint(metasploit_blueprint)
socketio = SocketIO(app, cors_allowed_origins="*")
register_metasploit_socketio(socketio)

log_store = []
playbook_jobs = {}
DEFAULT_PLAYBOOK = os.environ.get('PLAYBOOK_PATH', 'playbooks/default.yaml')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/status/<task_id>')
def task_status(task_id):
    if task_id in playbook_jobs:
        return jsonify(playbook_jobs[task_id])
    result = AsyncResult(task_id, app=celery_app)
    response = {
        'task_id': task_id,
        'state': result.state,
        'info': result.info,
    }
    if result.state == 'SUCCESS':
        response['result'] = result.result
    return jsonify(response)

@app.route('/results')
def results():
    """Return recent results as JSON."""
    target = request.args.get('target')
    limit = int(request.args.get('limit', 100))
    rows = get_results(target, limit)
    return jsonify(rows)

def _run_playbook_job(job_id, target, playbook):
    job = playbook_jobs[job_id]
    job['state'] = 'STARTED'
    try:
        for phase in playbook.get('phases', []):
            phase_name = phase.get('name')
            tools = phase.get('tools', [])
            parallel = phase.get('parallel', False)
            add_log(f'Running phase {phase_name} for {target} (parallel={parallel})')
            workflow = build_phase_workflow(phase_name, tools, target, parallel=parallel)
            if workflow is None:
                job['phases'].append({'phase': phase_name, 'error': 'No valid tools'})
                continue
            async_result = workflow.apply_async()
            job['phases'].append({'phase': phase_name, 'task_id': async_result.id})
            if parallel:
                phase_outputs = collect_group_results(async_result, timeout=600)
            else:
                phase_outputs = collect_chain_results(async_result, timeout=600)
            job.setdefault('results', {})[phase_name] = phase_outputs
            save_phase_result(target, phase_name, phase_outputs)
            add_log(f'Completed phase {phase_name}')
        job['state'] = 'SUCCESS'
        add_log(f'Playbook finished for {target}')
    except Exception as exc:
        job['state'] = 'FAILURE'
        job['error'] = str(exc)
        add_log(f'Playbook failed for {target}: {exc}', level='ERROR')

@app.route('/api/run', methods=['POST'])
def api_run():
    """Submit a playbook for a target; phases run in order (honors depends_on by sequence)."""
    target = request.args.get('target') or (request.json or {}).get('target')
    if not target:
        return jsonify({'error': 'target is required'}), 400

    playbook_path = request.args.get('playbook', DEFAULT_PLAYBOOK)
    try:
        with open(playbook_path) as f:
            playbook = yaml.safe_load(f)
    except FileNotFoundError:
        return jsonify({'error': f'playbook not found: {playbook_path}'}), 404

    job_id = str(uuid.uuid4())
    playbook_jobs[job_id] = {
        'task_id': job_id,
        'target': target,
        'state': 'PENDING',
        'phases': [],
    }
    thread = threading.Thread(
        target=_run_playbook_job,
        args=(job_id, target, playbook),
        daemon=True,
    )
    thread.start()
    add_log(f'Submitted playbook job {job_id} for {target}')
    return jsonify({'task_id': job_id, 'target': target, 'state': 'PENDING'})

@socketio.on('connect')
def handle_connect():
    emit('log', {'message': 'Connected to Cerberus-X dashboard', 'level': 'INFO'})
    for entry in log_store[-50:]:
        emit('log', entry)

def add_log(message, level='INFO'):
    """Add a log entry and broadcast via WebSocket."""
    entry = {'message': message, 'level': level, 'timestamp': time.time()}
    log_store.append(entry)
    if len(log_store) > 1000:
        log_store.pop(0)
    socketio.emit('log', entry)

if __name__ == '__main__':
    init_db()
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )
