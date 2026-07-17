import subprocess
import json
import re

def scan(target, args=None):
    if args is None:
        args = ['-a', '3']
    cmd = ['whatweb'] + args + [target]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        return {'tool': 'whatweb', 'target': target, 'raw_output': output}
    except FileNotFoundError:
        return {'tool': 'whatweb', 'target': target, 'error': 'whatweb binary not found'}
    except subprocess.CalledProcessError as e:
        return {'tool': 'whatweb', 'target': target, 'error': str(e.output)}