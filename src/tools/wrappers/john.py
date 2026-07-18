import subprocess
import json
import os
import tempfile

def scan(target, args=None):
    # John the Ripper is a password cracker; it needs a hash file, not a target URL.
    # For automation, we expect target to be a path to a hash file inside the container.
    # If target is a URL, we can try to download a hash file? Not typical.
    # We'll assume target is a file path containing hashes.
    if args is None:
        args = ['--wordlist=/usr/share/wordlists/rockyou.txt', '--format=nt']
    if not os.path.exists(target):
        return {'tool': 'john', 'target': target, 'error': 'Hash file not found'}
    cmd = ['john'] + args + [target]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        # Parse cracked passwords: lines like "password (username)"
        cracked = []
        for line in output.split('\n'):
            if '(' in line and ')' in line and 'password' not in line.lower():
                # Example: "admin (admin)" -> password=admin, username=admin
                parts = line.split('(')
                if len(parts) == 2:
                    pwd = parts[0].strip()
                    user = parts[1].replace(')', '').strip()
                    cracked.append({'username': user, 'password': pwd})
        return {'tool': 'john', 'target': target, 'cracked': cracked, 'raw_output': output}
    except subprocess.CalledProcessError as e:
        return {'tool': 'john', 'target': target, 'error': str(e.output)}