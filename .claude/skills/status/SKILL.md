---
name: status
description: Produce a project status report for the T4 spectrum study — roadmap progress, gate states, registry statistics, blockers, and schedule position against the 8-week ICLR clock.
---

# Project status report

Assemble and present, in this order:

1. **Clock position.** Today vs the W1–W8 calendar in docs/ROADMAP.md (W1 began
   2026-07-14; submission target mid-September 2026). State weeks remaining and whether
   the active phase matches the calendar.
2. **Roadmap state.** Parse checkbox counts per phase from docs/ROADMAP.md; list the
   STATUS block; call out any phase behind its calendar week.
3. **Gates.** GATE (a–d) and Phase A0 calibration: passed / failed / pending, with
   registry evidence (grep results/registry.jsonl).
4. **Registry statistics.** Total runs, completed/failed/quarantined counts, runs in the
   last 7 days (`results/registry.jsonl`; it may legitimately be empty early on).
5. **Claims ledger.** Status distribution from paper/claims.md (untested/supported/
   refuted/mixed).
6. **Blockers & open questions.** From ROADMAP STATUS + plan §14; flag any that are now
   on the critical path (e.g., InstBuild sourcing blocks Gate-b in W1).
7. **Recommended next actions**, in phase order, respecting gate dependencies —
   specific ROADMAP task IDs, not generalities.

If the schedule has slipped, say so plainly and invoke the plan's rule: gates trigger
scope cuts (user decision), not schedule slips.
