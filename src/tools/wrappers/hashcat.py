import subprocess
import json
import os
import tempfile

def scan(target, args=None):
    # Hashcat needs a hash file and a wordlist; we default to a basic attack.
    if args is None:
        args = ['-m', '0', '-a', '0', target, '/usr/share/wordlists/rockyou.txt']
    # target is expected to be a hash file path
    if not os.path.exists(target):
        return {'tool': 'hashcat', 'target': target, 'error': 'Hash file not found'}
    cmd = ['hashcat'] + args
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        # Parse output: look for lines with "Hash.Target:" and "Hash.Type:" and cracked hashes
        cracked_hashes = []
        for line in output.split('\n'):
            if 'Hash.Target:' in line:
                # Extract hash:value pair
                parts = line.split(':')
                if len(parts) >= 2:
                    h = parts[1].strip()
                    # Cracked line appears later as "hash:password"
        # Simpler: after run, use --show to get cracked
        show_cmd = ['hashcat', '--show', target]
        show_out = subprocess.check_output(show_cmd, stderr=subprocess.STDOUT, text=True)
        for line in show_out.split('\n'):
            if ':' in line:
                hash_val, password = line.split(':', 1)
                cracked_hashes.append({'hash': hash_val.strip(), 'password': password.strip()})
        return {'tool': 'hashcat', 'target': target, 'cracked': cracked_hashes, 'raw_output': output}
    except FileNotFoundError:
        return {'tool': 'hashcat', 'target': target, 'error': 'hashcat binary not found'}
    except subprocess.CalledProcessError as e:
        return {'tool': 'hashcat', 'target': target, 'error': str(e.output)}