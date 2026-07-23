"""ProjectDiscovery naabu — fast port scanner."""

from __future__ import annotations

from tools.wrappers._generic_cli import generic_cli_scan


def scan(target, args=None, evasion=None):
    def build_argv(host, cli_args, _url, _raw):
        argv = list(cli_args) if cli_args else ["-host", host, "-silent"]
        if "-host" not in argv and "-l" not in argv:
            argv = ["-host", host, *argv]
        return ["naabu", *argv]

    return generic_cli_scan("naabu", target, args, evasion, binary="naabu", build_argv=build_argv)
