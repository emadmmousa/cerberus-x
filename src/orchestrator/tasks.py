from celery import chain, group
from .celery_app import app
from tools.wrappers import nmap, gobuster, whatweb, sqlmap, nuclei, metasploit

@app.task(bind=True)
def run_nmap_task(self, target, args=None):
    self.update_state(state='STARTED', meta={'status': 'Nmap scanning...'})
    return nmap.scan(target, args)

@app.task(bind=True)
def run_gobuster_task(self, target, args=None):
    self.update_state(state='STARTED', meta={'status': 'Gobuster brute-forcing...'})
    return gobuster.scan(target, args)

@app.task(bind=True)
def run_whatweb_task(self, target, args=None):
    self.update_state(state='STARTED', meta={'status': 'WhatWeb fingerprinting...'})
    return whatweb.scan(target, args)

@app.task(bind=True)
def run_sqlmap_task(self, target, args=None):
    self.update_state(state='STARTED', meta={'status': 'SQLMap testing...'})
    return sqlmap.scan(target, args)

@app.task(bind=True)
def run_nuclei_task(self, target, args=None):
    self.update_state(state='STARTED', meta={'status': 'Nuclei scanning...'})
    return nuclei.scan(target, args)

@app.task(bind=True)
def run_metasploit_task(self, target, args=None):
    self.update_state(state='STARTED', meta={'status': 'Metasploit module execution...'})
    return metasploit.scan(target, args)

def build_phase_workflow(phase_name, tools_list, target, parallel=False):
    """
    Build a workflow for a phase.
    If parallel=True, use group() to run tools concurrently.
    Otherwise, use chain() for sequential execution.
    """
    task_list = []
    for tool in tools_list:
        tool_name = tool.get('tool')
        args = [
            arg.replace('{{target}}', target) if isinstance(arg, str) else arg
            for arg in tool.get('args', [])
        ]
        if tool_name == 'nmap':
            task_list.append(run_nmap_task.si(target, args))
        elif tool_name == 'gobuster':
            task_list.append(run_gobuster_task.si(target, args))
        elif tool_name == 'whatweb':
            task_list.append(run_whatweb_task.si(target, args))
        elif tool_name == 'sqlmap':
            task_list.append(run_sqlmap_task.si(target, args))
        elif tool_name == 'nuclei':
            task_list.append(run_nuclei_task.si(target, args))
        elif tool_name == 'metasploit':
            task_list.append(run_metasploit_task.si(target, args))
        else:
            # Placeholder – extend as needed
            pass

    if not task_list:
        return None

    if parallel:
        # Run all tools concurrently
        return group(*task_list)
    else:
        # Run tools sequentially
        return chain(*task_list)