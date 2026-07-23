"""Commix — automated command injection detection."""

from __future__ import annotations

import os

from tools.wrappers._generic_cli import _web_url, generic_cli_scan


def _commix_bin() -> str:
    env = os.environ.get("FIREBREAK_COMMIX_PATH")
    if env and os.path.isfile(env):
        return env
    return "/opt/commix/commix.py"


def scan(target, args=None, evasion=None):
    url = _web_url(target)
    commix = _commix_bin()

    def build_argv(_host, cli_args, web_url, _raw):
        argv = list(cli_args) if cli_args else ["--url", web_url, "--batch"]
        if "--url" not in argv and "-u" not in argv:
            argv = ["--url", web_url, *argv]
        return ["python3", commix, *argv]

    return generic_cli_scan(
        "commix",
        target,
        args,
        evasion,
        binary="python3",
        build_argv=build_argv,
        timeout=300,
    )
