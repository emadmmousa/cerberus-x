#!/usr/bin/env python3
"""Apply Cerberus-X hardening patches to an XSStrike install."""

from __future__ import annotations

from pathlib import Path

ROOT = Path("/opt/XSStrike")
WAF = ROOT / "core" / "wafDetector.py"
REQUESTER = ROOT / "core" / "requester.py"


def patch_waf_detector() -> None:
    text = WAF.read_text(encoding="utf-8")
    if "cerberus-x-patch" in text:
        return
    needle = (
        "    response = requester(url, params, headers, GET, delay, timeout)\n"
        "    page = response.text\n"
        "    code = str(response.status_code)\n"
    )
    patch = (
        "    response = requester(url, params, headers, GET, delay, timeout)\n"
        "    # cerberus-x-patch: empty Response has status_code None\n"
        "    if response is None or getattr(response, 'status_code', None) is None:\n"
        "        return None\n"
        "    page = response.text or ''\n"
        "    code = str(response.status_code)\n"
    )
    if needle not in text:
        raise SystemExit("XSStrike wafDetector.py layout changed; update patch")
    WAF.write_text(text.replace(needle, patch, 1), encoding="utf-8")


def patch_requester() -> None:
    text = REQUESTER.read_text(encoding="utf-8")
    if "cerberus-x-patch" in text:
        return
    old = (
        "        logger.warning('WAF is dropping suspicious requests.')\n"
        "        logger.warning('Scanning will continue after 10 minutes.')\n"
        "        time.sleep(600)\n"
    )
    new = (
        "        # cerberus-x-patch: never sleep 10 minutes in automation\n"
        "        logger.warning('WAF is dropping suspicious requests.')\n"
        "        return requests.Response()\n"
    )
    if old not in text:
        raise SystemExit("XSStrike requester.py layout changed; update patch")
    REQUESTER.write_text(text.replace(old, new, 1), encoding="utf-8")


if __name__ == "__main__":
    patch_waf_detector()
    patch_requester()
    print("xsstrike patches applied")
