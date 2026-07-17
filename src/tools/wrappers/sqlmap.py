import subprocess

def scan(target, args=None):
    if args is None:
        args = ['--batch', '--level=2']
    cmd = ['sqlmap', '-u', target] + args
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        vulnerable = 'vulnerable' in output.lower() or 'sql injection' in output.lower()
        return {'tool': 'sqlmap', 'target': target, 'vulnerable': vulnerable, 'raw_output': output}
    except FileNotFoundError:
        return {'tool': 'sqlmap', 'target': target, 'error': 'sqlmap binary not found'}
    except subprocess.CalledProcessError as e:
        return {'tool': 'sqlmap', 'target': target, 'error': str(e.output)}