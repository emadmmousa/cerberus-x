"""waybackurls — historical URL discovery from Wayback."""

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
            "waybackurls",
            target,
            seeds=seeds,
            note="waybackurls requires a domain seed.",
        )

    def build_argv(_host, _cli, _url, _raw):
        return ["waybackurls", domain, *cli_args]

    def parse_output(output: str) -> dict:
        urls = sorted({line.strip() for line in output.splitlines() if line.strip().startswith("http")})
        return {"urls": urls[:500], "url_count": len(urls), "productive": bool(urls)}

    return generic_cli_scan(
        "waybackurls",
        domain,
        cli_args,
        None,
        binary="waybackurls",
        build_argv=build_argv,
        parse_output=parse_output,
    )
