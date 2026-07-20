# orchestrator/tasks.py
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
    zmap,
    nikto,
    xsstrike,
    impacket,
    crackmapexec,
    responder,
    bloodhound,
    sliver,
)

_PROXY_TOOLS = frozenset(
    {
        "sqlmap",
        "ffuf",
        "gobuster",
        "nuclei",
        "whatweb",
        "nikto",
        "hydra",
        "xsstrike",
    }
)


@app.task(bind=True)
def run_nmap_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "Nmap scanning..."})
    return nmap.scan(target, args)


@app.task(bind=True)
def run_gobuster_task(
    self, target, args=None, use_proxy=False, proxy_protocol="http", evasion=None
):
    self.update_state(state="STARTED", meta={"status": "Gobuster brute-forcing..."})
    return gobuster.scan(
        target, args, use_proxy=use_proxy, proxy_protocol=proxy_protocol
    )


@app.task(bind=True)
def run_whatweb_task(
    self, target, args=None, use_proxy=False, proxy_protocol="http", evasion=None
):
    self.update_state(state="STARTED", meta={"status": "WhatWeb fingerprinting..."})
    return whatweb.scan(
        target, args, use_proxy=use_proxy, proxy_protocol=proxy_protocol
    )


@app.task(bind=True)
def run_sqlmap_task(
    self, target, args=None, use_proxy=False, proxy_protocol="http", evasion=None
):
    self.update_state(state="STARTED", meta={"status": "SQLMap testing..."})
    return sqlmap.scan(
        target,
        args,
        use_proxy=use_proxy,
        proxy_protocol=proxy_protocol,
        evasion=evasion,
    )


@app.task(bind=True)
def run_nuclei_task(
    self, target, args=None, use_proxy=False, proxy_protocol="http", evasion=None
):
    self.update_state(state="STARTED", meta={"status": "Nuclei scanning..."})
    return nuclei.scan(
        target,
        args,
        use_proxy=use_proxy,
        proxy_protocol=proxy_protocol,
        evasion=evasion,
    )


@app.task(bind=True)
def run_metasploit_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "Metasploit module..."})
    return metasploit.scan(target, args)


@app.task(bind=True, soft_time_limit=90, time_limit=120)
def run_masscan_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "Masscan scanning..."})
    return masscan.scan(target, args)


@app.task(bind=True)
def run_rustscan_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "RustScan scanning..."})
    return rustscan.scan(target, args)


@app.task(bind=True)
def run_theharvester_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "theHarvester harvesting..."})
    return theharvester.scan(target, args)


@app.task(bind=True)
def run_ffuf_task(
    self, target, args=None, use_proxy=False, proxy_protocol="http", evasion=None
):
    self.update_state(state="STARTED", meta={"status": "FFUF fuzzing..."})
    return ffuf.scan(
        target,
        args,
        use_proxy=use_proxy,
        proxy_protocol=proxy_protocol,
        evasion=evasion,
    )


@app.task(bind=True)
def run_hydra_task(
    self, target, args=None, use_proxy=False, proxy_protocol="http", evasion=None
):
    self.update_state(state="STARTED", meta={"status": "Hydra brute-forcing..."})
    return hydra.scan(
        target, args, use_proxy=use_proxy, proxy_protocol=proxy_protocol
    )


@app.task(bind=True)
def run_john_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "John the Ripper cracking..."})
    return john.scan(target, args)


@app.task(bind=True)
def run_hashcat_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "Hashcat cracking..."})
    return hashcat.scan(target, args)


@app.task(bind=True)
def run_winpeas_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "WinPEAS preparation..."})
    return winpeas.scan(target, args)


@app.task(bind=True)
def run_linpeas_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "LinPEAS preparation..."})
    return linpeas.scan(target, args)


@app.task(bind=True)
def run_zmap_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "ZMap scanning..."})
    return zmap.scan(target, args)


@app.task(bind=True)
def run_nikto_task(
    self, target, args=None, use_proxy=False, proxy_protocol="http", evasion=None
):
    self.update_state(state="STARTED", meta={"status": "Nikto scanning..."})
    return nikto.scan(
        target,
        args,
        use_proxy=use_proxy,
        proxy_protocol=proxy_protocol,
        evasion=evasion,
    )


@app.task(bind=True)
def run_xsstrike_task(
    self, target, args=None, use_proxy=False, proxy_protocol="http", evasion=None
):
    self.update_state(state="STARTED", meta={"status": "XSStrike scanning..."})
    return xsstrike.scan(
        target,
        args,
        use_proxy=use_proxy,
        proxy_protocol=proxy_protocol,
        evasion=evasion,
    )


@app.task(bind=True)
def run_impacket_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "Impacket secretsdump..."})
    return impacket.scan(target, args)


@app.task(bind=True)
def run_crackmapexec_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "CrackMapExec scanning..."})
    return crackmapexec.scan(target, args)


@app.task(bind=True)
def run_responder_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "Responder poisoning..."})
    return responder.scan(target, args)


@app.task(bind=True)
def run_bloodhound_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "BloodHound data collection..."})
    return bloodhound.scan(target, args)


@app.task(bind=True)
def run_sliver_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "Sliver payload generation..."})
    return sliver.scan(target, args)


_TASK_MAP = {
    "nmap": run_nmap_task,
    "gobuster": run_gobuster_task,
    "whatweb": run_whatweb_task,
    "sqlmap": run_sqlmap_task,
    "nuclei": run_nuclei_task,
    "metasploit": run_metasploit_task,
    "masscan": run_masscan_task,
    "rustscan": run_rustscan_task,
    "theharvester": run_theharvester_task,
    "ffuf": run_ffuf_task,
    "hydra": run_hydra_task,
    "john": run_john_task,
    "hashcat": run_hashcat_task,
    "winpeas": run_winpeas_task,
    "linpeas": run_linpeas_task,
    "zmap": run_zmap_task,
    "nikto": run_nikto_task,
    "xsstrike": run_xsstrike_task,
    "impacket": run_impacket_task,
    "crackmapexec": run_crackmapexec_task,
    "responder": run_responder_task,
    "bloodhound": run_bloodhound_task,
    "sliver": run_sliver_task,
}


def build_phase_workflow(
    phase_name,
    tools_list,
    target,
    parallel=False,
    use_proxy=False,
    proxy_protocol="http",
    evasion=None,
):
    """
    Build a workflow for a phase.
    If parallel=True, use group() to run tools concurrently.
    Otherwise, use chain() for sequential execution.
    Substitutes {{target}} in argument strings.
    """
    if evasion is None:
        evasion = {}
    task_list = []
    for tool in tools_list:
        tool_name = tool.get("tool")
        args = [
            arg.replace("{{target}}", target) if isinstance(arg, str) else arg
            for arg in tool.get("args", [])
        ]
        task_fn = _TASK_MAP.get(tool_name)
        if task_fn is None:
            continue
        if tool_name in _PROXY_TOOLS:
            task_list.append(
                task_fn.si(target, args, use_proxy, proxy_protocol, evasion)
            )
        else:
            task_list.append(task_fn.si(target, args, evasion))

    if not task_list:
        return None

    if parallel:
        return group(*task_list)
    return chain(*task_list)