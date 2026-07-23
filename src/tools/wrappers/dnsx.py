"""ProjectDiscovery dnsx — DNS enumeration toolkit."""

from __future__ import annotations

from tools.wrappers._generic_cli import generic_cli_scan


def scan(target, args=None, evasion=None):
    def build_argv(host, cli_args, _url, _raw):
        argv = list(cli_args) if cli_args else ["-d", host, "-silent"]
        if "-d" not in argv and "-l" not in argv:
            argv = ["-d", host, *argv]
        return ["dnsx", *argv]

    return generic_cli_scan("dnsx", target, args, evasion, binary="dnsx", build_argv=build_argv)
