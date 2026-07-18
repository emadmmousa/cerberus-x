import subprocess
import json
import re

def scan(target, args=None):
    if args is None:
        args = ['-t', '/root/nuclei-templates/http/cves/', '-severity', 'critical,high', '-silent']
    cmd = ['nuclei', '-u', target] + args
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        findings = []
        for line in output.split('\n'):
            if '[' in line and ']' in line:
                match = re.search(r'\[(.*?)\]\s*(.*?)(?:\s+\[(.*?)\])?', line)
                if match:
                    severity = match.group(1)
                    title = match.group(2)
                    findings.append({'severity': severity, 'title': title})
        return {'tool': 'nuclei', 'target': target, 'findings': findings, 'raw_output': output}
    except FileNotFoundError:
        return {'tool': 'nuclei', 'target': target, 'error': 'nuclei binary not found'}
    except subprocess.CalledProcessError as e:
        # nuclei exits non-zero when findings exist depending on flags; keep output
        output = e.output or ''
        findings = []
        for line in output.split('\n'):
            if '[' in line and ']' in line:
                match = re.search(r'\[(.*?)\]\s*(.*?)(?:\s+\[(.*?)\])?', line)
                if match:
                    findings.append({'severity': match.group(1), 'title': match.group(2)})
        if findings or output:
            return {'tool': 'nuclei', 'target': target, 'findings': findings, 'raw_output': output}
        return {'tool': 'nuclei', 'target': target, 'error': str(e.output)}