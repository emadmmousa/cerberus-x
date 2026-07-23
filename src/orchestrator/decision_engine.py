import logging
import re
from typing import Any, Dict, List

from .database import load_state, save_state

from orchestrator.ai.posture import DEFAULT_POSTURE, normalize_posture
from tools.cve_exploit_map import lookup_cve, lookup_port
from tools.payload_strategy import (
    infer_os,
    post_modules_for_session,
    resolve_exploit_options,
)

logger = logging.getLogger(__name__)


def _payload(item: Dict[str, Any]) -> Dict[str, Any]:
    """Accept nested {result:...} or flat wrapper dicts."""
    if not isinstance(item, dict):
        return {}
    nested = item.get("result")
    if isinstance(nested, dict):
        return nested
    return item


class DecisionEngine:
    def __init__(
        self,
        target: str,
        job_id: str | None = None,
        posture: str = DEFAULT_POSTURE,
    ):
        self.target = target
        self.job_id = job_id
        self.posture = normalize_posture(posture)
        self.state = load_state(target, job_id=job_id) or {}
        self.results_cache = {}
        self._fired_actions: set[str] = set(self.state.get("fired_actions") or [])

    def evaluate_phase(self, phase_name: str, phase_results: List[Dict]) -> Dict[str, Any]:
        """Process results of a completed phase and update state."""
        if isinstance(phase_results, dict):
            phase_results = [phase_results]
        self.results_cache[phase_name] = phase_results or []

        for item in phase_results or []:
            if not isinstance(item, dict):
                continue
            tool = item.get("tool") or _payload(item).get("tool")
            if tool == "nuclei":
                self._process_nuclei_results(item)
            elif tool == "nikto":
                self._process_nikto_results(item)
            elif tool == "metasploit":
                self._process_metasploit_results(item)
            elif tool == "sqlmap":
                self._process_sqlmap_results(item)
            elif tool in ("nmap", "masscan", "rustscan"):
                self._process_nmap_results(item)
            elif tool == "gobuster":
                self._process_gobuster_results(item)
            elif tool == "ffuf":
                self._process_ffuf_results(item)
            elif tool == "whatweb":
                self._process_whatweb_results(item)

        save_state(self.target, self.state, job_id=self.job_id)
        self._publish_blackboard(phase_name)
        return self.state

    def _publish_blackboard(self, phase_name: str) -> None:
        """Share DecisionEngine state on the Firebreak Blackboard (best-effort)."""
        mission = self.job_id or self.target
        try:
            from orchestrator.ai import blackboard

            blackboard.put(
                mission,
                "decision.state",
                {
                    "phase": phase_name,
                    "target": self.target,
                    "ports": self.state.get("open_ports") or self.state.get("ports"),
                    "vulns": self.state.get("vulnerabilities")
                    or self.state.get("vulns"),
                    "fired_actions": list(self._fired_actions)[:40],
                },
            )
            proposals = self.state.get("pending_actions") or self.state.get(
                "proposed_actions"
            )
            if proposals:
                blackboard.put(mission, "proposed_action", proposals)
        except Exception as exc:
            logger.debug("blackboard publish skipped: %s", exc)

    def _process_nuclei_results(self, item):
        result = _payload(item)
        findings = result.get("findings", [])
        vulns = []
        for finding in findings:
            title = finding.get("title", "") or ""
            template_id = str(finding.get("template_id") or finding.get("id") or "")
            severity = str(finding.get("severity") or "unknown").lower()
            blob = f"{title} {template_id}"
            if severity in ("critical", "high", "medium"):
                self.state["vuln_found"] = True
            cve_match = re.search(r"CVE-\d{4}-\d+", blob, re.IGNORECASE)
            if cve_match:
                cve = cve_match.group(0).upper()
                vulns.append(
                    {
                        "cve": cve,
                        "severity": finding.get("severity", "unknown"),
                        "title": title or cve,
                        "template_id": template_id,
                    }
                )
            elif re.search(r"\brce\b|remote code|unauth", blob, re.IGNORECASE):
                # Keep high-signal nuclei hits even without a CVE id.
                self.state["vuln_found"] = True
        if vulns:
            self.state.setdefault("vulnerabilities", []).extend(vulns)
            self.state["vuln_found"] = True

    def _process_nikto_results(self, item):
        result = _payload(item)
        issues = result.get("issues", [])
        if issues:
            self.state.setdefault("nikto_issues", []).extend(issues)
            # Header fingerprints / Cloudflare banners are not actionable vulns.
            # Only promote phases when Nikto reports a stronger signal.
            serious = [
                line
                for line in issues
                if isinstance(line, str)
                and re.search(
                    r"OSVDB|CVE-\d{4}-\d+|outdated|vulnerable|injection|"
                    r"directory indexing|default credentials|shell|backup|"
                    r"interesting file|retrieved .+ from",
                    line,
                    re.IGNORECASE,
                )
                and not re.search(
                    r"Uncommon header|x-powered-by|x-nextjs|alt-svc|"
                    r"HTTP/3|Retrieved x-powered-by",
                    line,
                    re.IGNORECASE,
                )
            ]
            if serious:
                self.state["vuln_found"] = True

    def _process_metasploit_results(self, item):
        result = _payload(item)
        sessions = result.get("sessions", [])
        if sessions:
            self.state.setdefault("sessions", []).extend(sessions)
            self.state["has_session"] = True
        if result.get("vulnerable"):
            self.state["vuln_found"] = True

    def _process_sqlmap_results(self, item):
        result = _payload(item)
        if result.get("vulnerable"):
            self.state["sql_injection"] = True
            self.state["vuln_found"] = True
        # Capture DBMS hint from strategy or output for follow-on targeting.
        sqli_meta = result.get("sqli") or {}
        if sqli_meta.get("dbms"):
            self.state["sql_dbms"] = sqli_meta["dbms"]
        raw = (result.get("raw_output") or result.get("error") or "").lower()
        for needle, name in (
            ("mysql", "mysql"),
            ("mariadb", "mysql"),
            ("postgresql", "postgresql"),
            ("microsoft sql server", "mssql"),
            ("oracle", "oracle"),
        ):
            if needle in raw:
                self.state["sql_dbms"] = name
                break

    def _process_whatweb_results(self, item):
        result = _payload(item)
        if result.get("waf_blocked"):
            self.state["waf_blocked"] = True
            self.state["cdn"] = True
        for tech in result.get("technologies") or []:
            label = str(tech).strip()
            if not label:
                continue
            self.state.setdefault("technologies", [])
            if label not in self.state["technologies"]:
                self.state["technologies"].append(label)
            if label.lower() == "cloudflare":
                self.state["cdn"] = True

    def _all_service_names(self) -> list[str]:
        names: list[str] = []
        for entry in self.state.get("open_ports") or []:
            if not isinstance(entry, dict):
                continue
            for key in ("service", "name", "product", "version", "extrainfo"):
                val = entry.get(key)
                if val:
                    names.append(str(val))
        return names

    def _services_for_port(self, port: str) -> list[str]:
        names: list[str] = []
        for entry in self.state.get("open_ports") or []:
            if not isinstance(entry, dict):
                continue
            entry_port = str(entry.get("port", "")).split("/")[0]
            if entry_port != str(port):
                continue
            for key in ("service", "name", "product", "version", "extrainfo"):
                val = entry.get(key)
                if val:
                    names.append(str(val))
        return names

    def _process_nmap_results(self, item):
        result = _payload(item)
        ports = result.get("ports", [])
        if not ports:
            return
        self.state.setdefault("open_ports", []).extend(ports)
        for entry in ports:
            if not isinstance(entry, dict):
                continue
            port = str(entry.get("port", "")).split("/")[0]
            state = str(entry.get("state", "")).lower()
            service = str(entry.get("service", "")).lower()
            # masscan/rustscan omit state — treat missing as open.
            is_open = state in ("", "open")
            if not is_open:
                continue
            self.state.setdefault("open_port_numbers", [])
            if port and port not in self.state["open_port_numbers"]:
                self.state["open_port_numbers"].append(port)
            if port == "22":
                self.state["ssh_open"] = True
            elif port == "21":
                self.state["ftp_open"] = True
            elif port in ("445", "139"):
                self.state["smb_open"] = True
            elif port in ("80", "443", "8080", "8443"):
                self.state["http_open"] = True
            if "windows" in service or "microsoft" in service:
                self.state["target_os"] = "windows"
            elif any(token in service for token in ("linux", "ubuntu", "debian", "unix")):
                self.state["target_os"] = "linux"

    def _process_gobuster_results(self, item):
        result = _payload(item)
        dirs = result.get("directories", [])
        if dirs:
            self.state.setdefault("directories", []).extend(dirs)
            self.state["http_open"] = True

    def _process_ffuf_results(self, item):
        result = _payload(item)
        finds = result.get("results", [])
        if finds:
            self.state.setdefault("ffuf_finds", []).extend(finds)
            self.state["http_open"] = True
        if result.get("stalled"):
            self.state["ffuf_stalled"] = True

    def decide_next_phase(self, playbook_phases: List[Dict]) -> List[Dict]:
        """Given the playbook phases, decide which to run based on current state."""
        return [phase for phase in playbook_phases if self.should_run_phase(phase)[0]]

    def should_run_phase(self, phase: dict) -> tuple[bool, str | None]:
        """Return whether a playbook phase can run and its skip reason."""
        when_cond = phase.get("when")
        if when_cond and not self._evaluate_condition(when_cond):
            return False, f"condition not met: {when_cond}"

        for dep in phase.get("depends_on", []):
            dep_results = self.results_cache.get(dep)
            if dep_results and all(_payload(item).get("error") for item in dep_results):
                logger.warning(
                    "Skipping phase %s because dependency %s failed",
                    phase.get("name"),
                    dep,
                )
                return False, f"dependency {dep} failed"

        return True, None

    def _evaluate_condition(self, condition: str) -> bool:
        """Evaluate a condition string against the current state."""
        try:
            # Simple evaluator: replace known state keys with their values
            expr = condition
            for key, value in self.state.items():
                if isinstance(value, (str, int, float, bool)):
                    expr = expr.replace(key, repr(value))
                elif isinstance(value, list):
                    # For list membership, e.g., 'CVE-2021-41773' in vulnerabilities
                    # We'll just check if any element matches the condition? 
                    # For simplicity, we use a basic eval with restricted globals.
                    pass
            # Use eval with safe globals
            allowed = {'True': True, 'False': False, 'None': None}
            return eval(expr, allowed, {})
        except Exception as e:
            logger.error(f"Condition evaluation error: {e}")
            return False

    def generate_post_phase_actions(self, phase_name: str, phase_results: List[Dict]) -> List[Dict]:
        """Generate additional tasks based on phase results."""
        actions = []
        proposed_keys: set[str] = set()

        if self.state.get("sql_injection"):
            from tools.sql_injection import follow_on_sqlmap_actions

            dbms = self.state.get("dbms") or self.state.get("sql_dbms")
            for action in follow_on_sqlmap_actions(dbms=dbms, intensity="aggressive"):
                key = f"{action['stage']}:{action['finding_id']}:{action['args'][0]}"
                # Dedupe on finding_id
                fkey = f"aux:{action['finding_id']}"
                if fkey in proposed_keys or self._action_fired(
                    "aux", action["finding_id"], "--batch"
                ):
                    continue
                actions.append(action)
                proposed_keys.add(fkey)
                proposed_keys.add(key)

        os_hint = self.state.get("target_os") or "unknown"

        def _queue_exploit(finding_id: str, module: str, option_stubs: list[str]) -> None:
            # Aux scanners use stage aux; exploits use stage exploit.
            stage = "aux" if module.startswith("auxiliary/") else "exploit"
            if stage == "exploit" and (
                self.state.get("waf_blocked") or self.state.get("cdn")
            ):
                return
            key = f"{stage}:{finding_id}:{module}"
            if key in proposed_keys or self._action_fired(stage, finding_id, module):
                return
            if stage == "exploit":
                resolved = resolve_exploit_options(
                    module,
                    target=self.target,
                    os_hint=infer_os(module, os_hint),
                    existing=list(option_stubs),
                )
                args = [module, *resolved]
            else:
                args = [module, *option_stubs]
            module_short = module.rsplit("/", 1)[-1]
            actions.append(
                {
                    "tool": "metasploit",
                    "phase": f"proof_of_impact_{stage}_{finding_id}_{module_short}",
                    "stage": stage,
                    "finding_id": finding_id,
                    "args": args,
                }
            )
            proposed_keys.add(key)

        # CVE-driven exploits (nuclei / mapped findings) — no confirmation.
        if self.state.get("vuln_found") or self.state.get("vulnerabilities"):
            seen_cves: set[str] = set()
            for vuln in self.state.get("vulnerabilities", []):
                cve = vuln.get("cve")
                if not cve:
                    continue
                cve_key = str(cve).strip().upper()
                if cve_key in seen_cves:
                    continue
                seen_cves.add(cve_key)
                match = lookup_cve(cve_key)
                if not match:
                    continue
                module, option_stubs = match
                from tools.cve_exploit_map import module_matches_context

                vuln_blob = " ".join(
                    str(vuln.get(key) or "")
                    for key in ("title", "template_id", "cve")
                )
                if not module_matches_context(
                    module,
                    services=self._all_service_names(),
                    technologies=self.state.get("technologies") or [],
                    vuln_blob=vuln_blob,
                ):
                    continue
                _queue_exploit(cve_key, module, option_stubs)

        # Aggressive: open-port service exploits even without a CVE hit.
        seen_ports: set[str] = set()
        for port in self.state.get("open_port_numbers") or []:
            port_s = str(port)
            if port_s in seen_ports:
                continue
            seen_ports.add(port_s)
            services = self._services_for_port(port_s)
            for module, option_stubs in lookup_port(port_s, services=services):
                _queue_exploit(f"port-{port_s}", module, list(option_stubs))

        if self.state.get("has_session"):
            for session in self.state.get("sessions", []):
                if not isinstance(session, dict):
                    continue
                session_id = session.get("id")
                if session_id is None:
                    continue
                enriched = dict(session)
                if not enriched.get("platform") and self.state.get("target_os"):
                    enriched["platform"] = self.state["target_os"]
                for module in post_modules_for_session(enriched):
                    key = f"post:{session_id}:{module}"
                    if key in proposed_keys or self._action_fired(
                        "post", str(session_id), module
                    ):
                        continue
                    actions.append(
                        {
                            "tool": "metasploit",
                            "phase": "post_exploitation",
                            "stage": "post",
                            "finding_id": str(session_id),
                            "args": [module, f"SESSION={session_id}"],
                        }
                    )
                    proposed_keys.add(key)
        # Defensive posture: never auto-queue sqlmap/metasploit follow-ons.
        if self.posture == "defensive":
            from orchestrator.ai.posture import OFFENSIVE_TOOLS

            actions = [
                a
                for a in actions
                if str(a.get("tool") or "") not in OFFENSIVE_TOOLS
            ]
        # Firebreak W1.7: publish proposals so scaffolds/UI can observe before execute.
        self.state["proposed_actions"] = actions
        self._publish_proposals(phase_name, actions)
        return actions

    def _publish_proposals(self, phase_name: str, actions: list[dict]) -> None:
        mission = self.job_id or self.target
        try:
            from orchestrator.ai import blackboard

            blackboard.put(
                mission,
                "proposed_action",
                {
                    "phase": phase_name,
                    "target": self.target,
                    "posture": self.posture,
                    "actions": actions,
                    "count": len(actions),
                },
            )
        except Exception as exc:
            logger.debug("blackboard proposed_action skipped: %s", exc)

    def _action_fired(self, stage: str, finding_id: str, module: str) -> bool:
        return f"{stage}:{finding_id}:{module}" in self._fired_actions

    def mark_actions_fired(self, actions: list[dict]) -> None:
        for action in actions:
            key = f"{action.get('stage')}:{action.get('finding_id')}:{action['args'][0]}"
            self._fired_actions.add(key)
        self.state["fired_actions"] = sorted(self._fired_actions)
        save_state(self.target, self.state, job_id=self.job_id)