from celery import chain, group
from .celery_app import app
from tools.wrappers import (
    nmap,
    gobuster,
    whatweb,
    sqlmap,
    nuclei,
    metasploit,
    masscan,
    rustscan,
    theharvester,
    ffuf,
    hydra,
    john,
    hashcat,
    winpeas,
    linpeas,
)


@app.task(bind=True)
def run_nmap_task(self, target, args=None):
    self.update_state(state="STARTED", meta={"status": "Nmap scanning..."})
    return nmap.scan(target, args)


@app.task(bind=True)
def run_gobuster_task(self, target, args=None):
    self.update_state(state="STARTED", meta={"status": "Gobuster brute-forcing..."})
    return gobuster.scan(target, args)


@app.task(bind=True)
def run_whatweb_task(self, target, args=None):
    self.update_state(state="STARTED", meta={"status": "WhatWeb fingerprinting..."})
    return whatweb.scan(target, args)


@app.task(bind=True)
def run_sqlmap_task(self, target, args=None):
    self.update_state(state="STARTED", meta={"status": "SQLMap testing..."})
    return sqlmap.scan(target, args)


@app.task(bind=True)
def run_nuclei_task(self, target, args=None):
    self.update_state(state="STARTED", meta={"status": "Nuclei scanning..."})
    return nuclei.scan(target, args)


@app.task(bind=True)
def run_metasploit_task(self, target, args=None):
    self.update_state(state="STARTED", meta={"status": "Metasploit module execution..."})
    return metasploit.scan(target, args)


@app.task(bind=True)
def run_masscan_task(self, target, args=None):
    self.update_state(state="STARTED", meta={"status": "Masscan scanning..."})
    return masscan.scan(target, args)


@app.task(bind=True)
def run_rustscan_task(self, target, args=None):
    self.update_state(state="STARTED", meta={"status": "RustScan scanning..."})
    return rustscan.scan(target, args)


@app.task(bind=True)
def run_theharvester_task(self, target, args=None):
    self.update_state(state="STARTED", meta={"status": "theHarvester harvesting..."})
    return theharvester.scan(target, args)


@app.task(bind=True)
def run_ffuf_task(self, target, args=None):
    self.update_state(state="STARTED", meta={"status": "FFUF fuzzing..."})
    return ffuf.scan(target, args)


@app.task(bind=True)
def run_hydra_task(self, target, args=None):
    self.update_state(state="STARTED", meta={"status": "Hydra unavailable..."})
    return hydra.scan(target, args)


@app.task(bind=True)
def run_john_task(self, target, args=None):
    self.update_state(state="STARTED", meta={"status": "John the Ripper cracking..."})
    return john.scan(target, args)


@app.task(bind=True)
def run_hashcat_task(self, target, args=None):
    self.update_state(state="STARTED", meta={"status": "Hashcat cracking..."})
    return hashcat.scan(target, args)


@app.task(bind=True)
def run_winpeas_task(self, target, args=None):
    self.update_state(state="STARTED", meta={"status": "WinPEAS preparation..."})
    return winpeas.scan(target, args)


@app.task(bind=True)
def run_linpeas_task(self, target, args=None):
    self.update_state(state="STARTED", meta={"status": "LinPEAS preparation..."})
    return linpeas.scan(target, args)


def build_phase_workflow(phase_name, tools_list, target, parallel=False):
    """
    Build a workflow for a phase.
    If parallel=True, use group() to run tools concurrently.
    Otherwise, use chain() for sequential execution.
    """
    task_list = []
    for tool in tools_list:
        tool_name = tool.get("tool")
        args = [
            arg.replace("{{target}}", target) if isinstance(arg, str) else arg
            for arg in tool.get("args", [])
        ]
        if tool_name == "nmap":
            task_list.append(run_nmap_task.si(target, args))
        elif tool_name == "gobuster":
            task_list.append(run_gobuster_task.si(target, args))
        elif tool_name == "whatweb":
            task_list.append(run_whatweb_task.si(target, args))
        elif tool_name == "sqlmap":
            task_list.append(run_sqlmap_task.si(target, args))
        elif tool_name == "nuclei":
            task_list.append(run_nuclei_task.si(target, args))
        elif tool_name == "metasploit":
            task_list.append(run_metasploit_task.si(target, args))
        elif tool_name == "masscan":
            task_list.append(run_masscan_task.si(target, args))
        elif tool_name == "rustscan":
            task_list.append(run_rustscan_task.si(target, args))
        elif tool_name == "theharvester":
            task_list.append(run_theharvester_task.si(target, args))
        elif tool_name == "ffuf":
            task_list.append(run_ffuf_task.si(target, args))
        elif tool_name == "hydra":
            task_list.append(run_hydra_task.si(target, args))
        elif tool_name == "john":
            task_list.append(run_john_task.si(target, args))
        elif tool_name == "hashcat":
            task_list.append(run_hashcat_task.si(target, args))
        elif tool_name == "winpeas":
            task_list.append(run_winpeas_task.si(target, args))
        elif tool_name == "linpeas":
            task_list.append(run_linpeas_task.si(target, args))
        else:
            pass

    if not task_list:
        return None

    if parallel:
        return group(*task_list)
    return chain(*task_list)
