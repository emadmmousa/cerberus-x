"""Dynamic tool runner — bridges aggressive playbooks to scan wrappers."""

from __future__ import annotations

import logging
from typing import Any, Callable

from orchestrator.celery_app import app
from orchestrator.mcp.registry import known_tools
from tools.wrappers import (
    bloodhound,
    crackmapexec,
    ffuf,
    gobuster,
    hashcat,
    hydra,
    impacket,
    john,
    linpeas,
    masscan,
    metasploit,
    nikto,
    nmap,
    nuclei,
    responder,
    rustscan,
    sliver,
    sqlmap,
    theharvester,
    whatweb,
    winpeas,
    xsstrike,
    zmap,
)

logger = logging.getLogger(__name__)

_WRAPPERS: dict[str, Callable[..., Any]] = {
    "nmap": nmap.scan,
    "gobuster": gobuster.scan,
    "whatweb": whatweb.scan,
    "sqlmap": sqlmap.scan,
    "nuclei": nuclei.scan,
    "metasploit": metasploit.scan,
    "masscan": masscan.scan,
    "rustscan": rustscan.scan,
    "theharvester": theharvester.scan,
    "ffuf": ffuf.scan,
    "hydra": hydra.scan,
    "john": john.scan,
    "hashcat": hashcat.scan,
    "winpeas": winpeas.scan,
    "linpeas": linpeas.scan,
    "zmap": zmap.scan,
    "nikto": nikto.scan,
    "xsstrike": xsstrike.scan,
    "impacket": impacket.scan,
    "crackmapexec": crackmapexec.scan,
    "responder": responder.scan,
    "bloodhound": bloodhound.scan,
    "sliver": sliver.scan,
}


def _params_to_args(tool: str, params: dict | None) -> list[str]:
    params = params or {}
    if isinstance(params.get("args"), list):
        return [str(a) for a in params["args"]]
    args: list[str] = []
    if "ports" in params:
        args.extend(["-p", str(params["ports"])])
    if "script" in params and tool == "nmap":
        args.extend(["--script", str(params["script"])])
    if "rate" in params and tool == "masscan":
        args.append(f"--rate={params['rate']}")
    if "data" in params and tool == "sqlmap":
        args.extend(["--data", str(params["data"]), "--batch"])
    if "module" in params and tool == "metasploit":
        args.append(str(params["module"]))
    return args


@app.task(name="workers.tasks.run_tool", bind=True)
def run_tool(self, tool: str, params: dict | None = None, session_id: str = ""):
    """Run an allowlisted scanner wrapper (used by dynamic/AI playbooks)."""
    name = (tool or "").strip()
    if name not in known_tools() or name not in _WRAPPERS:
        return {"tool": name, "error": f"unknown tool: {name}", "session_id": session_id}

    params = dict(params or {})
    target = (
        params.get("target")
        or params.get("url")
        or params.get("rhosts")
        or params.get("host")
        or ""
    )
    if not target:
        return {"tool": name, "error": "target required", "session_id": session_id}

    args = _params_to_args(name, params)
    self.update_state(
        state="STARTED",
        meta={"status": f"Running {name}...", "session_id": session_id},
    )
    try:
        result = _WRAPPERS[name](target, args)
    except TypeError:
        result = _WRAPPERS[name](target)
    except Exception as exc:
        result = {"tool": name, "error": str(exc)}

    if isinstance(result, dict):
        result.setdefault("session_id", session_id)
        result.setdefault("tool", name)
    return result
