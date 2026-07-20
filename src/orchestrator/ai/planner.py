"""AI phase planner — heuristic + optional LLM (Phases 2 & 4)."""

from __future__ import annotations

from typing import Any, Optional

from orchestrator.ai import llm, memory
from orchestrator.ai.prompts import system_prompt_for_planner
from orchestrator.mcp.registry import known_tools


SYSTEM_PROMPT = system_prompt_for_planner()  # legacy alias for tests/imports


def _ports_from_results(results_by_phase: dict) -> set[str]:
    ports: set[str] = set()
    for payload in results_by_phase.values():
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            for p in item.get("ports") or []:
                if isinstance(p, dict) and p.get("port") is not None:
                    ports.add(str(p["port"]))
                elif p is not None:
                    ports.add(str(p))
    return ports


def _sanitize_plan(plan: dict, allow: set[str]) -> Optional[dict]:
    if not isinstance(plan, dict):
        return None
    tools_in = plan.get("tools") or []
    if not isinstance(tools_in, list):
        return None
    tools = []
    for entry in tools_in:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("tool") or "").strip()
        if name not in allow:
            continue
        args = entry.get("args") or []
        if isinstance(args, str):
            from tools.wrappers._argv import coerce_argv

            clean_args = coerce_argv(args)
        elif isinstance(args, dict):
            from tools.wrappers._argv import coerce_argv

            clean_args = coerce_argv(args)
        elif isinstance(args, list):
            clean_args = [str(a) for a in args if isinstance(a, (str, int, float))]
        else:
            clean_args = []
        # Tool-specific sanitizers (LLM invents illegal flags frequently).
        if name == "masscan":
            from tools.wrappers import masscan as masscan_mod

            clean_args = masscan_mod.sanitize_args(clean_args)
        elif name == "nmap":
            from tools.wrappers import nmap as nmap_mod

            clean_args = nmap_mod.sanitize_args(clean_args)
        elif name == "nuclei":
            # Drop invented -template; wrapper also rewrites, but keep plan clean.
            rewritten: list[str] = []
            skip = False
            for i, a in enumerate(clean_args):
                if skip:
                    skip = False
                    continue
                if a in {"-template", "--template", "-templates"}:
                    rewritten.append("-t")
                    if i + 1 < len(clean_args) and not str(clean_args[i + 1]).startswith(
                        "-"
                    ):
                        rewritten.append(str(clean_args[i + 1]))
                        skip = True
                    else:
                        rewritten.append("http/cves/")
                    continue
                rewritten.append(a)
            clean_args = rewritten
        tools.append({"tool": name, "args": clean_args})
    return {
        "phase_name": str(plan.get("phase_name") or "ai_phase")[:80],
        "reason": str(plan.get("reason") or "AI suggested next actions")[:500],
        "parallel": bool(plan.get("parallel", True)),
        "stop": bool(plan.get("stop", False)),
        "tools": tools,
    }


def heuristic_plan(
    target: str,
    results_by_phase: dict,
    *,
    nl_goal: str = "",
    step: int = 0,
) -> dict:
    """Deterministic planner used when LLM is unavailable."""
    allow = known_tools()
    ports = _ports_from_results(results_by_phase)
    done_tools = set()
    for payload in results_by_phase.values():
        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if isinstance(item, dict) and item.get("tool"):
                done_tools.add(item["tool"])

    goal = (nl_goal or "").lower()
    prefer_sqli = "sql" in goal
    prefer_xss = "xss" in goal
    prefer_shell = "shell" in goal or "exploit" in goal

    if step == 0 or not results_by_phase:
        tools = []
        for name, args in (
            ("rustscan", ["--ulimit", "5000", "--top"]),
            ("nmap", ["-sV", "-p21,22,80,443,8080,8443", "-T4"]),
            ("whatweb", ["-a", "3"]),
        ):
            if name in allow:
                tools.append({"tool": name, "args": args})
        return {
            "phase_name": "ai_recon",
            "reason": "Initial reconnaissance of ports and web stack.",
            "parallel": True,
            "stop": False,
            "tools": tools,
        }

    web_open = bool(ports & {"80", "443", "8080", "8443"}) or not ports
    if web_open and not ({"nuclei", "nikto", "ffuf"} & done_tools):
        tools = []
        for name, args in (
            ("ffuf", ["-u", f"https://{target}/FUZZ", "-w", "/usr/share/dirb/wordlists/common.txt", "-ac"]),
            ("nuclei", ["-t", "http/cves/", "-severity", "critical,high", "-silent"]),
            ("nikto", ["-maxtime", "60"]),
        ):
            if name in allow and name not in done_tools:
                # ffuf target URL may be wrong if target already has scheme — keep simple
                if name == "ffuf":
                    args = ["-ac"]
                tools.append({"tool": name, "args": args})
        if tools:
            return {
                "phase_name": "ai_vuln",
                "reason": "Web ports observed; running vulnerability and content discovery.",
                "parallel": False,
                "stop": False,
                "tools": tools,
            }

    if prefer_xss and "xsstrike" in allow and "xsstrike" not in done_tools:
        return {
            "phase_name": "ai_xss",
            "reason": "Goal prefers XSS checks.",
            "parallel": False,
            "stop": False,
            "tools": [{"tool": "xsstrike", "args": ["--timeout", "20", "--skip"]}],
        }

    if prefer_sqli and "sqlmap" in allow and "sqlmap" not in done_tools:
        return {
            "phase_name": "ai_sqli",
            "reason": "Goal prefers SQL injection testing.",
            "parallel": False,
            "stop": False,
            "tools": [{"tool": "sqlmap", "args": ["--batch", "--forms", "--technique=BEUSTQ"]}],
        }

    if prefer_shell and "metasploit" in allow and "metasploit" not in done_tools:
        return {
            "phase_name": "ai_exploit",
            "reason": "Goal requests exploitation; proposing Metasploit probe.",
            "parallel": False,
            "stop": False,
            "tools": [{"tool": "metasploit", "args": []}],
        }

    # Aggressive default: keep pushing sqlmap / metasploit / hydra before stopping.
    if "sqlmap" in allow and "sqlmap" not in done_tools and web_open:
        return {
            "phase_name": "ai_sqli",
            "reason": "Aggressive follow-up: SQL injection checks.",
            "parallel": False,
            "stop": False,
            "tools": [
                {
                    "tool": "sqlmap",
                    "args": [
                        "--batch",
                        "--forms",
                        "--crawl=2",
                        "--level=5",
                        "--risk=3",
                        "--technique=BEUSTQ",
                    ],
                }
            ],
        }

    if "metasploit" in allow and "metasploit" not in done_tools:
        return {
            "phase_name": "ai_exploit",
            "reason": "Aggressive follow-up: Metasploit module against observed surface.",
            "parallel": False,
            "stop": False,
            "tools": [{"tool": "metasploit", "args": []}],
        }

    return {
        "phase_name": "ai_done",
        "reason": "No further high-value automated steps suggested.",
        "parallel": False,
        "stop": True,
        "tools": [],
    }


def suggest_next_phase(
    target: str,
    results_by_phase: dict,
    *,
    nl_goal: str = "",
    step: int = 0,
) -> dict:
    allow = known_tools()
    recalled = memory.recall(f"{target} {nl_goal}", k=3)
    memory_bits = "; ".join(r["summary"] for r in recalled) if recalled else ""

    if llm.llm_configured():
        user = {
            "target": target,
            "nl_goal": nl_goal,
            "step": step,
            "results_keys": list(results_by_phase.keys()),
            "open_ports": sorted(_ports_from_results(results_by_phase)),
            "allowlist": sorted(allow),
            "memory": memory_bits,
        }
        content = llm.chat_completion(
            [
                {"role": "system", "content": system_prompt_for_planner()},
                {"role": "user", "content": str(user)},
            ]
        )
        parsed = llm.parse_json_object(content or "")
        cleaned = _sanitize_plan(parsed or {}, allow) if parsed else None
        if cleaned is not None:
            if cleaned["stop"] or cleaned["tools"]:
                cleaned["source"] = "llm"
                return cleaned

    plan = heuristic_plan(target, results_by_phase, nl_goal=nl_goal, step=step)
    plan["source"] = "heuristic"
    if memory_bits:
        plan["reason"] = f"{plan['reason']} Memory: {memory_bits[:160]}"
    return plan


def plan_from_nl(target: str, nl_goal: str) -> dict:
    """Phase 4: natural-language mission → initial plan."""
    return suggest_next_phase(target, {}, nl_goal=nl_goal, step=0)
