"""sslscan — SSL/TLS cipher and certificate audit."""

from __future__ import annotations

from tools.wrappers._generic_cli import generic_cli_scan


def scan(target, args=None, evasion=None):
    def build_argv(host, cli_args, _url, _raw):
        argv = list(cli_args) if cli_args else [host]
        if not argv:
            argv = [host]
        return ["sslscan", *argv]

    return generic_cli_scan(
        "sslscan",
        target,
        args,
        evasion,
        binary="sslscan",
        build_argv=build_argv,
        timeout=120,
    )
