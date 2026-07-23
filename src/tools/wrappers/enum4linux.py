"""enum4linux-ng — SMB/NetBIOS/LDAP enumeration."""

from __future__ import annotations

from tools.wrappers._generic_cli import generic_cli_scan


def scan(target, args=None, evasion=None):
    def build_argv(host, cli_args, _url, _raw):
        argv = list(cli_args) if cli_args else ["-A", host]
        if host not in argv and "-w" not in argv and "-u" not in argv:
            argv = ["-A", host, *argv]
        return ["enum4linux-ng", *argv]

    return generic_cli_scan(
        "enum4linux",
        target,
        args,
        evasion,
        binary="enum4linux-ng",
        build_argv=build_argv,
        timeout=180,
    )
