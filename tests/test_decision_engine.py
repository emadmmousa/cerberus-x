import json
import pytest
from orchestrator import database
from orchestrator.decision_engine import DecisionEngine


@pytest.fixture(autouse=True)
def isolated_state_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "results.db"))


def test_decision_engine_evaluate_condition():
    eng = DecisionEngine("test")
    eng.state = {'vuln_found': True, 'some_number': 5}
    assert eng._evaluate_condition("vuln_found == True") is True
    assert eng._evaluate_condition("some_number > 3") is True
    assert eng._evaluate_condition("vuln_found == False") is False
    assert eng._evaluate_condition("some_number == 5") is True

def test_decision_engine_generate_actions_for_cve():
    eng = DecisionEngine("test")
    eng.state = {
        'vuln_found': True,
        'vulnerabilities': [{'cve': 'CVE-2021-41773', 'severity': 'high'}]
    }
    actions = eng.generate_post_phase_actions("vulnerability_scan", [])
    found = any('exploit/multi/http/apache_path_traversal' in str(a) for a in actions)
    assert found is True

def test_decision_engine_generate_actions_for_session():
    eng = DecisionEngine("test")
    eng.state = {
        'has_session': True,
        'sessions': [{'id': '42', 'type': 'meterpreter'}],
    }
    actions = eng.generate_post_phase_actions("exploitation", [])
    post_hashdump = any('post/windows/gather/hashdump' in str(a) for a in actions)
    assert post_hashdump is True

def test_decision_engine_nuclei_processing():
    eng = DecisionEngine("test")
    item = {
        'tool': 'nuclei',
        'result': {
            'findings': [
                {'title': 'CVE-2021-41773 Path Traversal', 'severity': 'critical'},
                {'title': 'CVE-2021-42013 Path Traversal', 'severity': 'critical'}
            ]
        }
    }
    eng._process_nuclei_results(item)
    assert 'vuln_found' in eng.state
    assert len(eng.state['vulnerabilities']) == 2
    assert eng.state['vulnerabilities'][0]['cve'] == 'CVE-2021-41773'

def test_decision_engine_metasploit_session():
    eng = DecisionEngine("test")
    item = {
        'tool': 'metasploit',
        'result': {'sessions': [{'id': 1, 'type': 'meterpreter'}]}
    }
    eng._process_metasploit_results(item)
    assert eng.state['has_session'] is True
    assert len(eng.state['sessions']) == 1


def test_decision_engine_accepts_flat_wrapper_payloads():
    eng = DecisionEngine("flat-target")
    eng.evaluate_phase(
        "recon",
        [
            {
                "tool": "nmap",
                "ports": [{"port": "443", "state": "open"}],
            },
            {
                "tool": "nuclei",
                "findings": [
                    {"title": "CVE-2021-41773 Path Traversal", "severity": "critical"}
                ],
            },
        ],
    )
    assert eng.state["vuln_found"] is True
    assert eng.state["open_ports"][0]["port"] == "443"
    assert eng.state["vulnerabilities"][0]["cve"] == "CVE-2021-41773"


def test_generate_actions_dedupes_same_cve_within_job():
    eng = DecisionEngine("t", job_id="j1")
    eng.state = {
        "vuln_found": True,
        "vulnerabilities": [{"cve": "CVE-2021-41773", "severity": "high"}],
    }
    first = eng.generate_post_phase_actions("vulnerability_scan", [])
    assert len(first) == 1
    assert first[0]["phase"] == "proof_of_impact"
    eng.mark_actions_fired(first)
    second = eng.generate_post_phase_actions("vulnerability_scan", [])
    assert second == []


def test_post_ex_uses_real_session_ids_not_hardcoded_one():
    eng = DecisionEngine("t", job_id="j1")
    eng.state = {
        "has_session": True,
        "sessions": [{"id": "42", "type": "meterpreter"}],
    }
    actions = eng.generate_post_phase_actions("access_gained", [])
    assert actions
    assert all("SESSION=42" in a["args"] for a in actions)
    assert all("SESSION=1" not in a["args"] for a in actions)
    assert all(a["phase"] == "post_exploitation" for a in actions)


def test_should_run_phase_allows_partial_dependency_failures():
    eng = DecisionEngine("t")
    eng.results_cache["recon"] = [{"tool": "nmap", "error": "timed out"}, {"tool": "nuclei"}]
    assert eng.should_run_phase({"name": "scan", "depends_on": ["recon"]}) == (True, None)


def test_should_run_phase_blocks_all_failed_dependency():
    eng = DecisionEngine("t")
    eng.results_cache["recon"] = [{"tool": "nmap", "error": "timed out"}]
    assert eng.should_run_phase({"name": "scan", "depends_on": ["recon"]}) == (
        False,
        "dependency recon failed",
    )


def test_should_run_phase_blocks_unmet_condition():
    eng = DecisionEngine("t")
    eng.state = {"vuln_found": False}
    assert eng.should_run_phase({"name": "exploit", "when": "vuln_found == True"}) == (
        False,
        "condition not met: vuln_found == True",
    )
