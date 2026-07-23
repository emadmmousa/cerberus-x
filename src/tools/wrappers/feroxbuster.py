"""Feroxbuster — fast recursive content discovery."""

from __future__ import annotations

from tools.wrappers._generic_cli import _web_url, generic_cli_scan
from tools.wrappers._wordlists import DEFAULT_WORDLIST


def scan(target, args=None, evasion=None):
    url = _web_url(target)

    def build_argv(host, cli_args, web_url, _raw):
        del host
        argv = list(cli_args) if cli_args else ["-u", web_url, "-w", DEFAULT_WORDLIST, "-q"]
        if "-u" not in argv and "--url" not in argv:
            argv = ["-u", web_url, *argv]
        return ["feroxbuster", *argv]

    return generic_cli_scan(
        "feroxbuster",
        target,
        args,
        evasion,
        binary="feroxbuster",
        build_argv=build_argv,
        timeout=300,
    )
