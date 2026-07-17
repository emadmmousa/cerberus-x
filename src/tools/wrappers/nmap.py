import subprocess
from urllib.parse import urlparse

def _host(target):
    """nmap expects a host/IP, not a full URL."""
    if '://' in target:
        return urlparse(target).hostname or target
    return target.split('/')[0] or target

def scan(target, args=None):
    if args is None:
        args = ['-sV', '-p-', '-T4']
    host = _host(target)
    cmd = ['nmap'] + args + [host]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        ports = []
        for line in output.split('\n'):
            if '/tcp' in line or '/udp' in line:
                parts = line.split()
                if len(parts) >= 3:
                    port = parts[0].split('/')[0]
                    state = parts[1]
                    service = ' '.join(parts[2:])
                    ports.append({'port': port, 'state': state, 'service': service})
        return {'tool': 'nmap', 'target': target, 'ports': ports, 'raw_output': output}
    except FileNotFoundError:
        return {'tool': 'nmap', 'target': target, 'error': 'nmap binary not found'}
    except subprocess.CalledProcessError as e:
        return {'tool': 'nmap', 'target': target, 'error': str(e.output)}