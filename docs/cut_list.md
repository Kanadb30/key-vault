# Cut list (one page — enforced, not advisory)

Tier A and B are never cut; Tier C cuts strictly from the top, in order.

## Tier A — graded spine (never cut)

SQL frontend (Lark grammar per README §1) → AST → binder → plan IR
(`Scan/Filter/Join/Project`) → predicate pushdown (diff-as-data) → per-node
per-plan-version stats → interpreter → fixtures → SQLite `Counter`
cross-check → span-anchored errors → CLI walkthrough.
**Property: demoable from one `pytest`-green process, no Rust involved.**

## Tier B — portfolio core (cut features, never the tier)

Console inspector (stage stepper, tokens/AST/plans/rows/metrics/verification
panels, error cards), SQLite adapter, form-based query builder, bundle replay
mode, preset-query buttons, degraded "engine unavailable" state.

## Tier C — cuttable, in cut order (top first)

1. **Drag-and-drop builder** (form-based builder stays)
2. **Console graph view** (ASCII `<pre>` plan views stay — they are canonical)
3. **PyO3** — pre-committed trigger: only if the stdio bridge binary is done
   **and** ≥1 week remains before the deadline
4. **kb_db demotion** to "designed, tested, not wired": keep the engine's
   schema/rows/scan work + tests + contract README, drop the live console
   wiring. NL + Elastic DSL frontends are cheap (3–6 h) and are kept unless
   this tier is reached.

## Kill criterion

**kb_db gets cut before the console loses a feature.** The graded demo script
(`README.md` §Time) contains zero Rust; the engine is pure portfolio value.

## Enforcement

* `demo-ready` git tag at every demoable state; revisit this file at every
  phase boundary against actual remaining time.
* Rehearsal checklist lives in the demo freeze phase (Phase 5 of the plan).
