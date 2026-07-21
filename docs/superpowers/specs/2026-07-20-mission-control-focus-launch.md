# Mission Control UI — Focus Launch

**Date:** 2026-07-20  
**Status:** Shipped

## Goal
Simplify Firebreak Mission Control to a single primary action: enter target → Start. Advanced controls live in a collapsed Options panel.

## Layout
1. Nav brand only (`Firebreak`)
2. Launch strip: target field + Start button + Options toggle
3. Options (collapsed): Stealth, Proxy, Smart plan
4. Run view: Status → Steps → Activity

## Copy
| Before | After |
|--------|--------|
| Launch Full Spectrum / AI Mission | Start / Running… |
| Attack Pipeline | Steps |
| Live Event Stream | Activity |
| WAF Evasion | Stealth |
| AI Mode | Smart plan |

## Defaults
- Stealth: High (maps to `aggressive` evasion for parity with prior default)
- Proxy / Smart plan: off until opened in Options
