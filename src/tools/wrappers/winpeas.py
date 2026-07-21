"""WinPEAS artifact preparer for authorized Windows post-ex."""

from __future__ import annotations

import os
import urllib.request
from typing import Any

DEST = "/app/tools/winPEASx64.exe"
URL = "https://github.com/peass-ng/PEASS-ng/releases/latest/download/winPEASx64.exe"


def scan(target, args=None) -> dict[str, Any]:
    dest = DEST
    if not os.path.exists(dest):
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            urllib.request.urlretrieve(URL, dest)
            os.chmod(dest, 0o755)
        except Exception as exc:
            return {
                "tool": "winpeas",
                "target": target,
                "status": "missing_artifact",
                "ready": False,
                "error": f"Failed to download winPEAS: {exc}",
            }

    extra = " ".join(str(a) for a in (args or []))
    return {
        "tool": "winpeas",
        "target": target,
        "status": "ready",
        "ready": True,
        "maturity": "artifact",
        "download_path": dest,
        "command": f"winPEASx64.exe {extra}".strip(),
        "note": "Artifact ready for authorized execution on a Windows host (not run inside Linux worker)",
    }
