# Human-Readable Mission Results Design

## Goal

Make Mission Control results understandable to nontechnical users by default, while keeping full technical detail behind an Advanced toggle for operators.

## Decisions (approved)

| Topic | Choice |
| --- | --- |
| Audience | Both nontechnical and junior operators |
| Default depth | Mission summary + plain-English tool cards |
| Expert detail | Collapsed Advanced / raw JSON |
| Implementation | Frontend-only summarizer (no wrapper/DB changes) |

## Architecture

Keep existing result JSON from workers. Add a pure frontend mapping layer:

```text
ResultRow.result (JSON)
  -> summarizeFinding(tool, result)
  -> { title, status, bullets, severity? }
  -> ResultCard (default) + Advanced (raw)
Mission rollup <- reduce all summaries
```

No Celery, wrapper, or schema changes in this pass.

## UX

### Mission summary panel

Shown when a mission is active or complete:

- Target
- Overall status: Running / Finished / Failed
- Counts: open ports · possible issues · confirmed vulnerabilities · failed tools
- One plain sentence derived from the rollup (e.g. “Found open web ports; some web checks could not reach the site through the proxy.”)

### Phase cards

- Friendly phase names: Reconnaissance, Vulnerability checks, Exploitation checks, Credential checks
- Badge: “N results” (not always “findings”)
- Status chips unchanged in meaning: Queued / Running / Complete / Failed / Skipped

### Tool cards (default)

- Title: human tool name, e.g. “Port scan (nmap)”
- Status: Worked / Partial / Failed / Skipped
- 1–4 plain bullets
- No ANSI codes, stack traces, or JSON by default

### Advanced

- Collapsed control: “Show technical details”
- Reveals raw structured output / JSON (existing behavior)

## Summarizer rules

`summarizeFinding(tool, result)` prefers structured fields over `raw_output`.

| Tool | Success example | Failure example |
| --- | --- | --- |
| masscan, rustscan, nmap | “Open ports: 22, 80, 443” | “No open ports found” |
| theHarvester | “Found 18 related hostnames” | Ignore banner author emails |
| whatweb, gobuster, ffuf, nuclei, xsstrike, sqlmap | Tool-specific success bullets | “Couldn’t reach the site through the proxy” on timeout/SSL/proxy errors |
| nikto | Issue count if real | “Web check didn’t run correctly” if help-text / unknown option |
| hydra, john, crackmapexec | “No credentials found” / skip reasons | Timeout / error wording |
| unknown | “Finished” or “Failed” from `error` / emptiness | Never dump JSON as the default body |

Additional rules:

- Strip ANSI escape sequences from any displayed text
- Failures labeled Failed, not findings
- Confirmed vulnerabilities only when explicit (e.g. `vulnerable: true`, non-empty nuclei findings)

Mission rollup aggregates: unique open ports, possible issues, confirmed vulns, failed tool count.

## Files

- Create: `frontend/src/lib/summarizeFinding.ts`
- Create: `frontend/src/components/MissionSummary.tsx`
- Modify: `frontend/src/components/ResultCard.tsx`
- Modify: `frontend/src/components/PhaseCard.tsx`
- Modify: `frontend/src/views/MissionControl.tsx`
- Modify: `frontend/src/styles/global.css` (minimal)
- Tests: `frontend/src/__tests__/summarizeFinding.test.ts`, update ResultCard/MissionControl tests as needed

## Testing

- Unit: port lists, empty ports, proxy timeout, sqlmap not vulnerable, empty nuclei, nikto help-text failure, ANSI strip, unknown fallback
- Component: ResultCard shows bullets by default; Advanced reveals JSON
- Existing Mission Control launch tests remain green

## Out of scope

- Fixing Oxylabs connectivity
- Nikto `-Add-header` / ffuf scheme bugs
- Backend-emitted summary fields
- Replacing the live phase timeline with a separate report page
