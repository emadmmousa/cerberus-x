# Prompt injection defenses (Firebreak)

## Why

AI security agents that feed untrusted HTTP/tool text into an LLM can be
hijacked when that text is treated as instructions (data/code confusion,
analogous to XSS). See public research such as
[arXiv:2508.21669](https://arxiv.org/abs/2508.21669) on prompt injection
against cybersecurity AI agents.

Firebreak already limits execution to Celery wrappers (`_TASK_MAP`) — there is
no freeform `generic_linux_command`. Remaining risk is **planner steering**.

## Mitigations in this repo

| Layer | Mechanism |
|-------|-----------|
| Architecture | Tools only via allowlisted wrappers |
| Input sanitize | `orchestrator.ai.prompt_guard` on tool digests + memory |
| Prompt policy | Planner / Modelfile: treat tool_results as DATA only |
| Training | Seed examples that ignore injection-shaped tool errors |
| Auth | Auth0 / RBAC for who can launch missions (W4) |

## Operator checklist (CISA / industry hygiene)

- MFA on operator accounts (Auth0)
- Least privilege + RBAC enforce when ready (`FIREBREAK_RBAC_ENFORCE`)
- Audit log + optional ES/Splunk sinks
- Authorized targets only (`FIREBREAK_REQUIRE_AUTHZ` / allowlists)

## Knowledge grounding

Training/eval knowledge draws educational framing from:

- [CyBOK Knowledgebase 1.1](https://www.cybok.org/knowledgebase1_1/)
- [CrowdStrike Cybersecurity 101](https://www.crowdstrike.com/en-us/cybersecurity-101/)
- [CISA Resources & Tools](https://www.cisa.gov/resources-tools/all-resources-tools?search=cybersecurity&sort_by=date&url=)

Rebuild the Ollama model after Modelfile changes:

```bash
docker compose run --rm ollama-pull
```
