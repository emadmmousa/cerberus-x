import subprocess
import json
import os
import tempfile

def scan(target, args=None):
    # Similar to winpeas, we download the script and provide it.
    linpeas_url = "https://github.com/peass-ng/PEASS-ng/releases/latest/download/linpeas.sh"
    dest = "/app/tools/linpeas.sh"
    if not os.path.exists(dest):
        try:
            import urllib.request
            urllib.request.urlretrieve(linpeas_url, dest)
            os.chmod(dest, 0o755)
        except Exception as e:
            return {'tool': 'linpeas', 'target': target, 'error': f"Failed to download linPEAS: {str(e)}"}
    return {'tool': 'linpeas', 'target': target, 'download_path': dest, 'command': f"bash linpeas.sh {args if args else ''}"}