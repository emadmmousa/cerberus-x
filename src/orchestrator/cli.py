#!/usr/bin/env python3
import argparse
import yaml
import sys
import json
from celery.result import AsyncResult
from .tasks import build_phase_workflow
from .celery_app import app

def collect_chain_results(async_result, timeout=600):
    """
    Traverse a Celery chain result and collect all individual task results.
    Returns a list of results in chain order.
    """
    # Wait for the final task to complete
    final_result = async_result.get(timeout=timeout)
    # If the chain has no parent, just return the single result
    if not async_result.parent:
        return [final_result]
    # Recursively collect from the parent chain
    parent_results = collect_chain_results(async_result.parent, timeout)
    parent_results.append(final_result)
    return parent_results

def main():
    parser = argparse.ArgumentParser(description='Cerberus-X orchestrator')
    parser.add_argument('--target', required=True, help='Target URL or IP')
    parser.add_argument('--playbook', default='playbooks/default.yaml', help='Playbook YAML file')
    parser.add_argument('--background', action='store_true', help='Run tasks asynchronously')
    args = parser.parse_args()

    with open(args.playbook) as f:
        playbook = yaml.safe_load(f)

    target = args.target
    phases = playbook.get('phases', [])
    results = {}

    for phase in phases:
        phase_name = phase.get('name')
        tools = phase.get('tools', [])
        print(f"[*] Running phase: {phase_name}")

        workflow = build_phase_workflow(phase_name, tools, target)
        if workflow is None:
            results[phase_name] = {'error': 'No valid tools in phase'}
            continue

        # Apply the workflow asynchronously
        async_result = workflow.apply_async()

        if not args.background:
            # Wait for the entire chain and collect all results
            phase_outputs = collect_chain_results(async_result, timeout=600)
            results[phase_name] = phase_outputs
        else:
            print(f"[+] Phase submitted: {async_result.id}")
            results[phase_name] = {'task_id': async_result.id}

    print(json.dumps(results, indent=2))

if __name__ == '__main__':
    main()