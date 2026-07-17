import subprocess
import json

def scan(target, args=None):
    if args is None:
        args = ['dir', '-u', target, '-w', '/usr/share/dirb/wordlists/common.txt']
    cmd = ['gobuster'] + args
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        directories = []
        for line in output.split('\n'):
            if 'Status:' in line:
                parts = line.split()
                if len(parts) >= 3:
                    path = parts[0]
                    status = parts[1].strip('()')
                    directories.append({'path': path, 'status': status})
        return {'tool': 'gobuster', 'target': target, 'directories': directories, 'raw_output': output}
    except FileNotFoundError:
        return {'tool': 'gobuster', 'target': target, 'error': 'gobuster binary not found'}
    except subprocess.CalledProcessError as e:
        return {'tool': 'gobuster', 'target': target, 'error': str(e.output)}