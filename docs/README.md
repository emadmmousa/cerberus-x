# Firebreak documentation index

Authorized security testing only.

## Operator docs

| Doc | Description |
|-----|-------------|
| [../README.md](../README.md) | Full product guide (architecture, UI, compose, env, troubleshooting) |
| [user_manual.md](user_manual.md) | Mission Control quick start and day-to-day use |
| [api_reference.md](api_reference.md) | HTTP / MCP API surface |
| [developer_guide.md](developer_guide.md) | Layout, wrappers, tests, AI/payload hooks |
| [waf_evasion.md](waf_evasion.md) | Outbound WAF evasion profiles and inventory |
| [sql_injection.md](sql_injection.md) | SQLi catalog → sqlmap strategy |

## Design specs & plans (`superpowers/`)

Historical implementation records. Prefer operator docs above for current behavior.

| Spec / plan | Topic |
|-------------|--------|
| [specs/2026-07-20-mission-control-focus-launch.md](superpowers/specs/2026-07-20-mission-control-focus-launch.md) | Focus Launch UI |
| [specs/2026-07-20-ai-mcp-orchestration-design.md](superpowers/specs/2026-07-20-ai-mcp-orchestration-design.md) | AI + MCP |
| [specs/2026-07-20-payload-strategy-design.md](superpowers/specs/2026-07-20-payload-strategy-design.md) | Metasploit PAYLOAD/LHOST |
| [specs/2026-07-19-maximum-evasion-default-design.md](superpowers/specs/2026-07-19-maximum-evasion-default-design.md) | Default aggressive evasion |
| [specs/2026-07-18-metasploit-rpc-design.md](superpowers/specs/2026-07-18-metasploit-rpc-design.md) | MSF RPC |
| [specs/2026-07-19-mission-integrated-exploitation-design.md](superpowers/specs/2026-07-19-mission-integrated-exploitation-design.md) | Mission exploitation |
| [specs/2026-07-19-human-readable-results-design.md](superpowers/specs/2026-07-19-human-readable-results-design.md) | Finding summaries |
| [specs/2026-07-19-proxy-settings-ui-design.md](superpowers/specs/2026-07-19-proxy-settings-ui-design.md) | Proxy settings UI |
| [specs/2026-07-19-oxylabs-proxy-react-console-design.md](superpowers/specs/2026-07-19-oxylabs-proxy-react-console-design.md) | Oxylabs console |

Matching plans live under `superpowers/plans/`.

## Code pointers

| Path | Role |
|------|------|
| `src/tools/waf_evasion.py` | Evasion implementation |
| `src/tools/sql_injection.py` | SQLi strategy |
| `src/tools/cve_exploit_map.py` | CVE / port → MSF |
| `src/tools/payload_strategy.py` | Payload + LHOST/LPORT |
| `docker/ollama/Modelfile` | Authorized `firebreak` persona on DeepSeek Instant |
| `.env.example` | Environment reference |
