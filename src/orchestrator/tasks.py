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
    darkweb,
    httpx_probe,
    breach_intel,
    katana,
    subfinder,
    gau,
    sherlock,
    feroxbuster,
    naabu,
    dnsx,
    amass,
    dalfox,
    waybackurls,
    sslscan,
    arjun,
    enum4linux,
    commix,
    wpscan,
)
from tools.wrappers import scaffold_bundle

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
        "feroxbuster",
        "dalfox",
        "commix",
        "arjun",
        "wpscan",
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


@app.task(bind=True, soft_time_limit=150, time_limit=180)
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


@app.task(bind=True, soft_time_limit=270, time_limit=300)
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
def run_darkweb_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "Dark web OSINT..."})
    return darkweb.scan(target, args)


@app.task(bind=True, soft_time_limit=120, time_limit=150)
def run_breach_intel_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "Breach intel lookup..."})
    return breach_intel.run(target, args)


@app.task(bind=True, soft_time_limit=120, time_limit=150)
def run_subfinder_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "Subfinder scraping..."})
    return subfinder.scan(target, args)


@app.task(bind=True, soft_time_limit=120, time_limit=150)
def run_gau_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "GAU archive scrape..."})
    return gau.scan(target, args)


@app.task(bind=True, soft_time_limit=200, time_limit=240)
def run_sherlock_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "Sherlock username scrape..."})
    return sherlock.scan(target, args)


@app.task(bind=True, soft_time_limit=200, time_limit=240)
def run_katana_task(
    self, target, args=None, use_proxy=False, proxy_protocol="http", evasion=None
):
    self.update_state(state="STARTED", meta={"status": "Katana crawling..."})
    return katana.scan(
        target,
        args,
        use_proxy=use_proxy,
        proxy_protocol=proxy_protocol,
    )


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


@app.task(bind=True, soft_time_limit=120, time_limit=150)
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


@app.task(bind=True, soft_time_limit=210, time_limit=240)
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


@app.task(bind=True, soft_time_limit=75, time_limit=90)
def run_httpx_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "HTTP probing..."})
    return httpx_probe.scan(target, args, evasion=evasion)


@app.task(bind=True, soft_time_limit=300, time_limit=360)
def run_feroxbuster_task(
    self, target, args=None, use_proxy=False, proxy_protocol="http", evasion=None
):
    self.update_state(state="STARTED", meta={"status": "Feroxbuster fuzzing..."})
    return feroxbuster.scan(target, args, evasion=evasion)


@app.task(bind=True, soft_time_limit=120, time_limit=150)
def run_naabu_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "Naabu port scanning..."})
    return naabu.scan(target, args, evasion=evasion)


@app.task(bind=True, soft_time_limit=120, time_limit=150)
def run_dnsx_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "dnsx enumeration..."})
    return dnsx.scan(target, args, evasion=evasion)


@app.task(bind=True, soft_time_limit=300, time_limit=360)
def run_amass_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "Amass subdomain enum..."})
    return amass.scan(target, args, evasion=evasion)


@app.task(bind=True, soft_time_limit=240, time_limit=300)
def run_dalfox_task(
    self, target, args=None, use_proxy=False, proxy_protocol="http", evasion=None
):
    self.update_state(state="STARTED", meta={"status": "Dalfox XSS scanning..."})
    return dalfox.scan(target, args, evasion=evasion)


@app.task(bind=True, soft_time_limit=120, time_limit=150)
def run_waybackurls_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "Wayback URL harvest..."})
    return waybackurls.scan(target, args, evasion=evasion)


@app.task(bind=True, soft_time_limit=120, time_limit=150)
def run_sslscan_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "SSL/TLS audit..."})
    return sslscan.scan(target, args, evasion=evasion)


@app.task(bind=True, soft_time_limit=180, time_limit=210)
def run_arjun_task(
    self, target, args=None, use_proxy=False, proxy_protocol="http", evasion=None
):
    self.update_state(state="STARTED", meta={"status": "Arjun param discovery..."})
    return arjun.scan(target, args, evasion=evasion)


@app.task(bind=True, soft_time_limit=180, time_limit=210)
def run_enum4linux_task(self, target, args=None, evasion=None):
    self.update_state(state="STARTED", meta={"status": "enum4linux-ng scanning..."})
    return enum4linux.scan(target, args, evasion=evasion)


@app.task(bind=True, soft_time_limit=300, time_limit=360)
def run_commix_task(
    self, target, args=None, use_proxy=False, proxy_protocol="http", evasion=None
):
    self.update_state(state="STARTED", meta={"status": "Commix command injection..."})
    return commix.scan(target, args, evasion=evasion)


@app.task(bind=True, soft_time_limit=300, time_limit=360)
def run_wpscan_task(
    self, target, args=None, use_proxy=False, proxy_protocol="http", evasion=None
):
    self.update_state(state="STARTED", meta={"status": "WPScan auditing..."})
    return wpscan.scan(target, args, evasion=evasion)


@app.task(bind=True, soft_time_limit=900, time_limit=1080)
def run_scaffold_bundle_task(self, target, args=None, evasion=None, scaffold_id=None):
    """Run a specialist scaffold recipe (maps to multiple CLI wrappers)."""
    label = scaffold_id or "unknown"
    self.update_state(
        state="STARTED",
        meta={"status": f"Scaffold specialist {label}..."},
    )
    return scaffold_bundle.scan(
        target,
        args,
        evasion=evasion,
        scaffold_id=scaffold_id,
        tool_name=f"scaffold/{label}" if label else None,
    )


@app.task(bind=True, soft_time_limit=180, time_limit=210)
def run_custom_tool_task(self, target, args=None, tool_name=None, evasion=None):
    """Execute an operator-approved custom tool from the registry (argv, no shell)."""
    import subprocess

    from orchestrator.tools_registry import get_tool, render_argv, resolve_binary

    rec = get_tool(tool_name or "")
    if not rec:
        return {"tool": tool_name, "target": target, "error": "custom tool not found"}
    if not rec.get("enabled", True):
        return {"tool": tool_name, "target": target, "error": "custom tool disabled"}

    self.update_state(state="STARTED", meta={"status": f"Custom tool {tool_name}..."})
    if resolve_binary(rec["binary"]) is None:
        return {
            "tool": tool_name,
            "target": target,
            "error": f"binary '{rec['binary']}' not found on worker PATH",
        }
    argv = render_argv(rec, target, args or [])
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=170,
            check=False,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        return {
            "tool": tool_name,
            "target": target,
            "argv": argv,
            "returncode": proc.returncode,
            "raw_output": output[:20000],
        }
    except subprocess.TimeoutExpired:
        return {"tool": tool_name, "target": target, "error": "custom tool timed out"}
    except FileNotFoundError:
        return {"tool": tool_name, "target": target, "error": f"binary not found: {rec['binary']}"}
    except Exception as exc:  # noqa: BLE001 - surface any exec failure to the mission log
        return {"tool": tool_name, "target": target, "error": str(exc)}


@app.task(bind=True, soft_time_limit=30, time_limit=45)
def run_tools_health_task(self):
    """Probe worker PATH / artifacts for every registered wrapper."""
    from tools.inventory import probe_all_local

    self.update_state(state="STARTED", meta={"status": "Probing tool binaries..."})
    return probe_all_local()


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
    "subfinder": run_subfinder_task,
    "gau": run_gau_task,
    "sherlock": run_sherlock_task,
    "darkweb": run_darkweb_task,
    "breach_intel": run_breach_intel_task,
    "katana": run_katana_task,
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
    "httpx": run_httpx_task,
    "feroxbuster": run_feroxbuster_task,
    "naabu": run_naabu_task,
    "dnsx": run_dnsx_task,
    "amass": run_amass_task,
    "dalfox": run_dalfox_task,
    "waybackurls": run_waybackurls_task,
    "sslscan": run_sslscan_task,
    "arjun": run_arjun_task,
    "enum4linux": run_enum4linux_task,
    "commix": run_commix_task,
    "wpscan": run_wpscan_task,
}


def _register_scaffold_tasks() -> None:
    from orchestrator.ai.scaffold_tools import (
        EXPECTED_SCAFFOLD_COUNT,
        assert_all_scaffolds_wired,
        scaffold_tool_names,
    )

    assert_all_scaffolds_wired()
    names = scaffold_tool_names()
    for name in names:
        _TASK_MAP[name] = run_scaffold_bundle_task

    wired_scaffolds = {key for key in _TASK_MAP if key.startswith("scaffold/")}
    if len(wired_scaffolds) != EXPECTED_SCAFFOLD_COUNT:
        raise RuntimeError(
            f"expected {EXPECTED_SCAFFOLD_COUNT} scaffold/* tasks in _TASK_MAP, "
            f"got {len(wired_scaffolds)}"
        )
    if wired_scaffolds != names:
        missing = sorted(names - wired_scaffolds)
        extra = sorted(wired_scaffolds - names)
        raise RuntimeError(
            f"scaffold task map mismatch missing={missing[:5]} extra={extra[:5]}"
        )
    for name in names:
        if _TASK_MAP[name] is not run_scaffold_bundle_task:
            raise RuntimeError(f"{name} must map to run_scaffold_bundle_task")


_register_scaffold_tasks()


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
    from orchestrator.ai.scaffold_tools import expand_phase_tools, is_scaffold_tool, resolve_scaffold_id
    from tools.normalize_args import normalize_tool_args

    tools_list = expand_phase_tools(tools_list or [])

    task_list = []
    for tool in tools_list:
        tool_name = tool.get("tool")
        args = normalize_tool_args(
            tool_name, target, tool.get("args", []), evasion=evasion
        )
        if is_scaffold_tool(tool_name):
            sid = resolve_scaffold_id(tool_name)
            if sid:
                task_list.append(
                    run_scaffold_bundle_task.si(target, args, evasion, sid)
                )
            continue
        task_fn = _TASK_MAP.get(tool_name)
        if task_fn is None:
            # Operator-approved custom tool from the runtime registry.
            try:
                from orchestrator.tools_registry import get_tool

                if get_tool(tool_name):
                    task_list.append(
                        run_custom_tool_task.si(target, args, tool_name, evasion)
                    )
            except Exception:
                pass
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