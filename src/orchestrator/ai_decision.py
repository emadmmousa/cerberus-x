"""AI decision engine for aggressive follow-on actions (Ollama + fallback)."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import requests
from celery import chain

from utils.redis_utils import get_redis
from utils.threat_intel import ThreatIntelFetcher
from workers.tasks import run_tool

logger = logging.getLogger(__name__)


class AIDecisionEngine:
    def __init__(self) -> None:
        self.redis = get_redis()
        self.intel = ThreatIntelFetcher()
        self.ollama_url = os.environ.get(
            "CERBERUS_OLLAMA_GENERATE_URL", "http://ollama:11434/api/generate"
        )
        self.model = os.environ.get("CERBERUS_LLM_MODEL", "cerberus-x")

    def decide(self, session_id: str, scan_results: dict) -> list[dict]:
        services = self._extract_services(scan_results or {})
        intel_hits = self.intel.fetch_for_services(services)
        prompt = self._build_prompt(scan_results or {}, intel_hits)
        response = self._ollama_generate(prompt)
        plan = self._parse_plan(response)
        if not plan:
            plan = self._fallback_plan(services, scan_results or {})
        try:
            self.redis.hset(
                f"session:{session_id}:plan",
                mapping={
                    "next_steps": json.dumps(plan),
                    "generated": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception:
            pass
        return plan

    def _extract_services(self, data: dict) -> list[str]:
        services: list[str] = []
        for host in data.get("hosts") or []:
            if not isinstance(host, dict):
                continue
            for port in host.get("ports") or []:
                if not isinstance(port, dict):
                    continue
                svc = port.get("service")
                if isinstance(svc, dict) and svc.get("name"):
                    services.append(str(svc["name"]))
                elif isinstance(svc, str):
                    services.append(svc)
                elif port.get("name"):
                    services.append(str(port["name"]))
        # Flat nmap-style results: {"ports":[{"port":"80","service":"http"}]}
        for port in data.get("ports") or []:
            if isinstance(port, dict) and port.get("service"):
                services.append(str(port["service"]))
        return sorted(set(services))

    def _build_prompt(self, results: dict, intel: dict) -> str:
        from orchestrator.ai.prompts import DECISION_SYSTEM_PROMPT

        return (
            f"{DECISION_SYSTEM_PROMPT}\n"
            "Return JSON only: a list of [tool_name, params_dict] pairs "
            "or {\"tools\":[{\"tool\":\"name\",\"args\":[]}]}.\n"
            "Allowed tools: nmap, masscan, rustscan, whatweb, nuclei, nikto, ffuf, "
            "sqlmap, xsstrike, hydra, metasploit, gobuster.\n"
            "Prefer thorough exploitation and credential checks when services are open.\n\n"
            f"Scan results (truncated):\n{json.dumps(results, default=str)[:2000]}\n\n"
            f"Threat intel hints:\n{json.dumps(intel, default=str)[:1000]}\n"
        )

    def _ollama_generate(self, prompt: str) -> str:
        # Prefer OpenAI-compatible client already used by AI mode when configured.
        try:
            from orchestrator.ai import llm
            from orchestrator.ai.prompts import DECISION_SYSTEM_PROMPT, planner_temperature

            if llm.llm_configured():
                content = llm.chat_completion(
                    [
                        {"role": "system", "content": DECISION_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=planner_temperature(),
                    timeout=90.0,
                )
                if content:
                    return content
        except Exception as exc:
            logger.debug("LLM client path failed: %s", exc)

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": float(os.environ.get("CERBERUS_LLM_TEMPERATURE", "0.9")),
                "top_p": float(os.environ.get("CERBERUS_LLM_TOP_P", "0.95")),
            },
        }
        try:
            resp = requests.post(self.ollama_url, json=payload, timeout=90)
            resp.raise_for_status()
            return resp.json().get("response", "[]")
        except Exception as exc:
            logger.warning("Ollama generate failed: %s", exc)
            return "[]"

    def _parse_plan(self, raw: str) -> list[dict]:
        if not raw:
            return []
        text = raw.strip()
        if text.startswith("```"):
            lines = [ln for ln in text.splitlines() if not ln.strip().startswith("```")]
            text = "\n".join(lines).strip()
        try:
            from orchestrator.ai.llm import parse_json_object

            # Accept either object or bare list embedded in text.
            obj = parse_json_object(text)
            if obj and isinstance(obj.get("tools"), list):
                out = []
                for entry in obj["tools"]:
                    if isinstance(entry, dict) and entry.get("tool"):
                        out.append(
                            {
                                "tool": entry["tool"],
                                "params": entry.get("params")
                                or {"args": entry.get("args") or []},
                            }
                        )
                return out
        except Exception:
            pass
        try:
            start = text.find("[")
            end = text.rfind("]")
            if start >= 0 and end > start:
                plan = json.loads(text[start : end + 1])
            else:
                plan = json.loads(text)
            if not isinstance(plan, list):
                return []
            out = []
            for item in plan:
                if isinstance(item, list) and len(item) == 2:
                    out.append({"tool": str(item[0]), "params": item[1] or {}})
                elif isinstance(item, dict) and item.get("tool"):
                    out.append(
                        {
                            "tool": str(item["tool"]),
                            "params": item.get("params") or item.get("args") or {},
                        }
                    )
            return out
        except Exception:
            logger.warning("Failed to parse LLM plan")
            return []

    def _fallback_plan(self, services: list[str], results: dict) -> list[dict]:
        target = results.get("target") or results.get("url") or ""
        plan: list[dict] = []
        if not any(s in {"http", "https", "www"} for s in services) and "80" not in str(
            results
        ):
            plan.append(
                {
                    "tool": "nmap",
                    "params": {
                        "target": target or "127.0.0.1",
                        "args": ["-sV", "-p21,22,80,443,8080,8443", "-T4"],
                    },
                }
            )
        else:
            plan.append(
                {
                    "tool": "whatweb",
                    "params": {"target": target or "https://example.com", "args": ["-a", "3"]},
                }
            )
            plan.append(
                {
                    "tool": "nuclei",
                    "params": {
                        "target": target or "https://example.com",
                        "args": ["-severity", "critical,high", "-silent"],
                    },
                }
            )
        return plan

    def execute_next(self, session_id: str, current_results: dict) -> int:
        plan = self.decide(session_id, current_results)
        if not plan:
            logger.info("No aggressive actions suggested, stopping.")
            return 0
        tasks = [
            run_tool.s(action["tool"], action.get("params") or {}, session_id)
            for action in plan
            if action.get("tool")
        ]
        if not tasks:
            return 0
        if len(tasks) > 1:
            chain(*tasks).apply_async()
        else:
            tasks[0].apply_async()
        logger.info("Scheduled %s aggressive actions for session %s", len(tasks), session_id)
        return len(tasks)
