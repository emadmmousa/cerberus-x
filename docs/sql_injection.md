# SQL injection strategy

Technique catalog and sqlmap argument builder for authorized engagements. Implemented in `src/tools/sql_injection.py`. Execution is via **sqlmap** and lightweight scanner probes — not standalone exploit PoCs.

## Intensity

```python
from tools.sql_injection import sqli_profile, build_sqlmap_args, list_techniques

profile = sqli_profile("aggressive", dbms="mysql")
args = build_sqlmap_args(profile, existing=["--batch", "--forms"], evasion=evasion)
```

| Source | Effect |
|--------|--------|
| `FIREBREAK_SQLI_INTENSITY` | Forces intensity (`off`/`low`/`medium`/`high`/`aggressive`) |
| Evasion `level` | Used when env unset (`resolve_sqli_intensity`) |
| Default | `aggressive` |

Aggressive sqlmap merge includes `--technique=BEUSTQ`, high `--level`/`--risk`, forms/crawl/threads, banner/user/db/schema/privileges/passwords, `--dump` (opt-in `--dump-all`), WAF tampers, optional `--hpp`.

## Technique coverage

| Family | Mapped to |
|--------|-----------|
| Classic in-band | Union / error / boolean / time / conditional → `BEUSTQ` + probe payloads |
| Out-of-band | `--dns-domain` when `FIREBREAK_SQLMAP_DNS_DOMAIN` set; MSSQL UNC / Oracle HTTP probes |
| DB-specific | MySQL / Postgres / MSSQL / Oracle payload sets + `--dbms=` |
| Advanced | Polyglots, stacked queries, second-order (`FIREBREAK_SQLMAP_SECOND_ORDER`), NoSQL probes |
| Blind refinements | Bit/ASCII/`SLEEP`/`BENCHMARK` payloads |
| Evasion | Comment/case/hex/whitespace + `waf_evasion` tampers |
| Exfil | Schema/user/db/hash enum + dump |

## Environment

```bash
FIREBREAK_SQLI_INTENSITY=aggressive
# FIREBREAK_SQLMAP_DNS_DOMAIN=exfil.yourdomain.com
# FIREBREAK_SQLMAP_SECOND_ORDER=https://target/profile
# FIREBREAK_SQLMAP_DUMP_ALL=false
# FIREBREAK_SQLMAP_OS_SHELL=false
```

## Wiring

- `tools.wrappers.sqlmap.scan` always merges strategy into args.
- `VulnerabilityScanner` runs `probe_payloads()` + `nosql_probe_payloads()`.
- `DecisionEngine` queues `follow_on_sqlmap_actions()` (enum + dump, MSSQL-aware) after confirmed SQLi.
- AI planner proposes BEUSTQ-oriented sqlmap phases.

## Related

- [`waf_evasion.md`](waf_evasion.md)
- [`api_reference.md`](api_reference.md)
- Tests: `tests/test_sql_injection.py`
