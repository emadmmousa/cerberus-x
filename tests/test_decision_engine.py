import json
import pytest
from orchestrator.decision_engine import DecisionEngine

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
    eng.state = {'has_session': True}
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