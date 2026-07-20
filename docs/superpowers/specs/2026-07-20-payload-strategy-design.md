# Payload strategy for Metasploit exploits (2026-07-20)

## Goal

Make mapped CVE auto-exploits able to open sessions by selecting workable
payloads (reverse/bind), LHOST/LPORT, and OS-aware post modules — with **no
confirmation gate**.

## Behavior

1. `tools/payload_strategy.py` resolves `PAYLOAD` / `LHOST` / `LPORT` / `RPORT`.
2. `DecisionEngine.generate_post_phase_actions` calls the strategy for every
   mapped exploit (never emits `LHOST=0.0.0.0`).
3. `tools/wrappers/metasploit.scan` re-applies the strategy for exploit modules
   so manual/API runs also get sane defaults; keeps MSF built-in handler
   (`DisablePayloadHandler=false`).
4. Post-ex modules follow session/platform (Linux gather vs Windows gather);
   unknown platforms get three non-destructive multi modules (`env`, `checkvm`,
   `local_exploit_suggester`).
5. Config: `CERBERUS_LHOST`, `CERBERUS_LPORT_START`, `CERBERUS_PAYLOAD_PREFER`.

## Status

Shipped in `src/tools/payload_strategy.py` and wired through decision engine +
metasploit wrapper. CVE map: `src/tools/cve_exploit_map.py`.
