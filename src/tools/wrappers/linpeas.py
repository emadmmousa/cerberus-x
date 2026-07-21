"""LinPEAS artifact preparer for authorized Linux post-ex."""

from __future__ import annotations

import os
import urllib.request
from typing import Any

DEST = "/app/tools/linpeas.sh"
URL = "https://github.com/peass-ng/PEASS-ng/releases/latest/download/linpeas.sh"


def scan(target, args=None) -> dict[str, Any]:
    dest = DEST
    if not os.path.exists(dest):
        try:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            urllib.request.urlretrieve(URL, dest)
            os.chmod(dest, 0o755)
        except Exception as exc:
            return {
                "tool": "linpeas",
                "target": target,
                "status": "missing_artifact",
                "ready": False,
                "error": f"Failed to download linPEAS: {exc}",
            }

    extra = " ".join(str(a) for a in (args or []))
    return {
        "tool": "linpeas",
        "target": target,
        "status": "ready",
        "ready": True,
        "maturity": "artifact",
        "download_path": dest,
        "command": f"bash linpeas.sh {extra}".strip(),
        "note": "Artifact ready for authorized execution on a Linux host",
    }
