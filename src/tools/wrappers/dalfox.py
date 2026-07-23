"""Dalfox — parameter-aware XSS scanner."""

from __future__ import annotations

from tools.wrappers._generic_cli import _web_url, generic_cli_scan


def scan(target, args=None, evasion=None):
    url = _web_url(target)

    def build_argv(_host, cli_args, web_url, _raw):
        argv = list(cli_args) if cli_args else [web_url, "--silence"]
        if web_url not in argv and "-u" not in argv:
            argv = [web_url, *argv]
        return ["dalfox", *argv]

    return generic_cli_scan(
        "dalfox",
        target,
        args,
        evasion,
        binary="dalfox",
        build_argv=build_argv,
        timeout=240,
    )
