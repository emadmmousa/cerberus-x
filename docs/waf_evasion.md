# WAF evasion (outbound)

Authorized testing helpers that shape **outbound** scanner/tool traffic so engagements continue past CDN/WAF friction. Implemented in `src/tools/waf_evasion.py`.

This is **not** the inbound orchestrator WAF (`security.waf`).

## Profiles

```python
from tools.waf_evasion import evasion_profile, list_techniques

evasion_profile("aggressive", target_waf="cloudflare")
list_techniques()
```

| Level | Behavior (summary) |
|-------|--------------------|
| `off` | No headers / delays / obfuscation |
| `low` | Random headers, short delay |
| `medium` | + payload obfuscation, light header injection, HPP |
| `high` | + trusted UA, static extensions, JSON wrap, stronger delays |
| `aggressive` | Full stack: injection, multipart/dual-param, origin discovery, AI payload rewrite, size pad, sqlmap tampers |

Playbooks set `evasion: aggressive` by default (`playbooks/default.yaml`). Mission Control stealth maps into these levels.

## Technique families

| Category | Examples |
|----------|----------|
| Encoding | URL×1–3, Unicode, HTML entities, Base64, hex, overlong UTF-8, mixed case, null byte, whitespace, comments, char-dup |
| Protocol-ish | Method swap GET→POST, method-override headers, header reorder, oversized body pad |
| Parameters | HPP, split, URL/body/header fragmentation, JSON wrap, multipart, dual URL+body |
| Headers | XFF family, X-Original/Rewrite-URL, Referer spoof, custom debug headers, Host hints |
| Contextual | Whitelist path probes, static `.jpg`/`.png`, trusted bots, session cookies, delays, proxy rotation flags |
| Infrastructure | DNS origin candidates, direct-origin IP rewrite |
| WAF-specific | Cloudflare / Imperva / AWS / Azure / F5 / ModSecurity overlays |
| Advanced | `ai_adversarial_payload()` via local LLM |

## Intentionally not implemented

Raw chunked/CL smuggling, HTTP/0.9, HTTP/2 smuggling, malformed wire headers, RST crafting — see `list_techniques()["not_implemented_protocol"]`.

## Wiring

Applied by:

- `tools.wrappers` — sqlmap, ffuf, nuclei, nikto, xsstrike, …
- `tools.http_session.EvasiveSession`
- `scanner.vulnerability_scanner.VulnerabilityScanner`
- Dashboard `_resolve_evasion()` → job metadata

## Related

- [`sql_injection.md`](sql_injection.md) — sqlmap tampers + intensity
- Spec history: `docs/superpowers/specs/2026-07-19-maximum-evasion-default-design.md`
