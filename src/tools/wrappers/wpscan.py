"""WPScan — WordPress vulnerability scanner."""

from __future__ import annotations

from tools.wrappers._generic_cli import _web_url, generic_cli_scan


def scan(target, args=None, evasion=None):
    url = _web_url(target)

    def build_argv(_host, cli_args, web_url, _raw):
        argv = list(cli_args) if cli_args else ["--url", web_url, "--no-update", "--random-user-agent"]
        if "--url" not in argv:
            argv = ["--url", web_url, *argv]
        return ["wpscan", *argv]

    return generic_cli_scan(
        "wpscan",
        target,
        args,
        evasion,
        binary="wpscan",
        build_argv=build_argv,
        timeout=300,
    )
