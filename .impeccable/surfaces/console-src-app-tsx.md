---
version: 1
slug: "console-src-app-tsx"
primary_target: "console/src/App.tsx"
related_targets: ["console/src/Panels.tsx","console/src/styles.css","console/index.html"]
---

# Query workbench

- Scope: `/` in the prebuilt React console; `console/src/App.tsx` and its
  inspector panels. Mode: Operate.
- Audience: author and evaluator following a six-minute compiler walkthrough;
  portfolio readers inspecting executable evidence.
- Task: edit or load SQL, run it, inspect any of seven compiler stages, compare
  pushdown plans and measured work, inspect rows and SQLite evidence.
- Proof: real fixture query yields Asha/CSE and Meera/ECE, 12→6 candidate
  pairs and 4→2 left rows into the join. Every value comes from QueryRun.
- Direction: user-pinned Kibana-style workbench; light working surface for
  projection, navy navigation, side-by-side plan text, compact stage strip.
- Signature: the same predicate highlighted in its original and pushed-down
  positions, followed by recorded per-plan measurements.
- States: loading, request in progress, semantic/parse diagnostics with source
  selection, empty result, connection failure retaining explicitly previous
  evidence, changed source, imported recorded evidence.
- Constraints: all four frontends implemented; explicit fixtures/SQLite/Rust
  selection with actual engine availability. No browser compiler semantics. Offline static
  assets. Reject unsafe JSON integers rather than round valid i64 values.
- Review: desktop/mobile extension tests pass; mechanical detector clean.
  Existing workbench identity is retained; no new visual-world exercise.
- Open: deadline and whether console replaces the original CLI demo medium.
