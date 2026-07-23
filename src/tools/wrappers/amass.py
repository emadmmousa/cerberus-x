"""OWASP Amass — passive subdomain enumeration."""

from __future__ import annotations

from tools.osint_scrape import parse_seeds, pick_harvest_domain, skip_result, strip_osint_seed_args
from tools.wrappers._generic_cli import generic_cli_scan


def scan(target, args=None, evasion=None):
    del evasion
    seeds = parse_seeds(target, args)
    cli_args = strip_osint_seed_args(args)
    domain = pick_harvest_domain(target, seeds)
    if not domain:
        return skip_result(
            "amass",
            target,
            seeds=seeds,
            note="Amass requires a domain or email domain seed.",
        )

    def build_argv(_host, _cli, _url, _raw):
        argv = list(cli_args) if cli_args else ["enum", "-passive", "-d", domain]
        return ["amass", *argv]

    return generic_cli_scan(
        "amass",
        domain,
        cli_args,
        None,
        binary="amass",
        build_argv=build_argv,
        timeout=300,
    )
