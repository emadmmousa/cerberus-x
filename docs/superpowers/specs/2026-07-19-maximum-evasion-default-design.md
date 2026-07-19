# Maximum Evasion Default

## Goal

Make the existing `aggressive` WAF-evasion profile the default for unified
missions while preserving the operator's ability to select a lower level.

## Architecture

No new profile or API is required. The existing `evasion` request field and
`evasion_profile("aggressive")` implementation remain authoritative.

## Changes

- Set `evasion: "aggressive"` in `playbooks/default.yaml`.
- Initialize Mission Control's evasion selector to `aggressive`.
- Keep `off`, `low`, `medium`, and `high` available.

## Behavior

New missions default to randomized headers, payload obfuscation, 1–4 second
jitter, and eight configured retries. Explicit operator selections continue
to override the default.

## Testing

- Assert the default playbook declares `aggressive`.
- Assert Mission Control submits `evasion: "aggressive"` by default.
- Run Python tests, frontend tests, and the frontend production build.
