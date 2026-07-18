#!/usr/bin/env python3
import argparse
import yaml
import json
from .tasks import build_phase_workflow
from .database import init_db, save_phase_result

def collect_chain_results(async_result, timeout=600):
    """Traverse a Celery chain result and collect all individual task results."""
    final_result = async_result.get(timeout=timeout)
    if not async_result.parent:
        return [final_result]
    parent_results = collect_chain_results(async_result.parent, timeout)
    parent_results.append(final_result)
    return parent_results

def collect_group_results(async_result, timeout=600):
    """Collect results from a group of tasks."""
    return async_result.get(timeout=timeout)

def main():
    parser = argparse.ArgumentParser(description='Cerberus-X orchestrator')
    parser.add_argument('--target', required=True, help='Target URL or IP')
    parser.add_argument('--playbook', default='playbooks/default.yaml', help='Playbook YAML file')
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
        else:
            print(f"[+] Phase submitted: {async_result.id}")
            results[phase_name] = {'task_id': async_result.id}

    print(json.dumps(results, indent=2))

if __name__ == '__main__':
    main()
