#!/usr/bin/env python3
import argparse
import yaml
import sys
import json
from celery.result import AsyncResult
from .celery_errors import format_celery_collect_error
from .tasks import build_phase_workflow
from .celery_app import app
from .database import init_db, save_phase_result, get_results
from .decision_engine import DecisionEngine

def collect_chain_results(async_result, timeout=600):
    try:
        final_result = async_result.get(timeout=timeout)
    except Exception as exc:
        raise RuntimeError(format_celery_collect_error(exc)) from exc
    if not async_result.parent:
        return [final_result]
    parent_results = collect_chain_results(async_result.parent, timeout)
    parent_results.append(final_result)
    return parent_results

def collect_group_results(async_result, timeout=600):
    try:
        return async_result.get(timeout=timeout)
    except Exception as exc:
        raise RuntimeError(format_celery_collect_error(exc)) from exc

def main():
    parser = argparse.ArgumentParser(description='Firebreak orchestrator')
    parser.add_argument('--target', required=True, help='Target URL or IP')
    parser.add_argument(
        '--playbook',
        default='playbooks/complete_dark_arsenal.yaml',
        help='Playbook YAML file',
    )
    parser.add_argument('--background', action='store_true', help='Run tasks asynchronously')
    parser.add_argument('--no-persist', action='store_true', help='Skip saving results to database')
    args = parser.parse_args()

    with open(args.playbook) as f:
        playbook = yaml.safe_load(f)

    target = args.target
    phases = playbook.get('phases', [])
    results = {}

    if not args.no_persist:
        init_db()

    decision_engine = DecisionEngine(target)

    for phase in phases:
        phase_name = phase.get('name')
        tools = phase.get('tools', [])
        parallel = phase.get('parallel', False)
        print(f"[*] Running phase: {phase_name} (parallel={parallel})")

        workflow = build_phase_workflow(phase_name, tools, target, parallel=parallel)
        if workflow is None:
            results[phase_name] = {'error': 'No valid tools in phase'}
            continue

        async_result = workflow.apply_async()

        if not args.background:
            if parallel:
                phase_outputs = collect_group_results(async_result, timeout=600)
            else:
                phase_outputs = collect_chain_results(async_result, timeout=600)
            results[phase_name] = phase_outputs
            if not args.no_persist:
                save_phase_result(target, phase_name, phase_outputs)
                decision_engine.evaluate_phase(phase_name, phase_outputs)

            # Check for post‑phase actions
            actions = decision_engine.generate_post_phase_actions(phase_name, phase_outputs)
            if actions:
                print(f"[*] Generating post‑phase actions for {phase_name}")
                for action in actions:
                    action_phase_name = f"auto_{action['tool']}_{phase_name}"
                    action_tools = [{'tool': action['tool'], 'args': action['args']}]
                    action_workflow = build_phase_workflow(action_phase_name, action_tools, target, parallel=False)
                    if action_workflow:
                        action_result = action_workflow.apply_async()
                        action_output = action_result.get(timeout=300)
                        if not args.no_persist:
                            save_phase_result(target, action_phase_name, action_output)
                        print(f"[+] Action {action['tool']} completed")
        else:
            print(f"[+] Phase submitted: {async_result.id}")
            results[phase_name] = {'task_id': async_result.id}

    print(json.dumps(results, indent=2))

if __name__ == '__main__':
    main()