"""Arjun — HTTP parameter discovery."""

from __future__ import annotations

from tools.wrappers._generic_cli import _web_url, generic_cli_scan


def scan(target, args=None, evasion=None):
    url = _web_url(target)

    def build_argv(_host, cli_args, web_url, _raw):
        argv = list(cli_args) if cli_args else ["-u", web_url, "--stable"]
        if "-u" not in argv:
            argv = ["-u", web_url, *argv]
        return ["arjun", *argv]

    return generic_cli_scan(
        "arjun",
        target,
        args,
        evasion,
        binary="arjun",
        build_argv=build_argv,
        timeout=180,
    )
