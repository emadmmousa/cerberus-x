# CAI Standalone — ROLLED BACK

**Date:** 2026-07-20  
**Status:** **ROLLED BACK (2026-07-21)** — do not implement.

## Reason

Firebreak direction changed: Firebreak will train and ship its **own** cybersecurity model (`firebreak`), not integrate Alias Robotics CAI framework / `CAI_LICENSE_OFF`.

See instead:
- [`docs/superpowers/plans/2026-07-21-firebreak-upgrade-plan.md`](../plans/2026-07-21-firebreak-upgrade-plan.md)
- [`docs/superpowers/specs/2026-07-21-firebreak-own-model-design.md`](./2026-07-21-firebreak-own-model-design.md)

Original CAI-beside-Firebreak design is archived below for history only.

---

<details>
<summary>Archived original design (not to be built)</summary>

Run Alias `cai-framework` with `CAI_LICENSE_OFF=1` beside Firebreak using Ollama. Out of scope permanently unless product direction reverses.

</details>
