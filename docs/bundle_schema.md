# QueryRun bundle schema — v1 (with Locator + ErrorEnvelope)

Status: **frozen 2026-11-14, before the AST dataclasses exist.**
One versioned JSON document — the **QueryRun bundle** — is the only thing the
console, the CLI, and the tests consume. The console is a *pure projection* of
this document: zero recomputation, zero compiler semantics in JavaScript.

## Top-level shape

```jsonc
{
  "run_schema_version": 1,
  "inputs": { "frontend_id": "sql", "verbatim": "SELECT ...", "normalized": "..." },
  "stages": [ { "name": "lex|parse|bind|plan|optimize|execute|verify",
                "status": "ok|error|skipped",
                "timing_ms": 0.0, "artifact": { ... } } ],
  "plans":   { "pre": <plan_json>, "post": <plan_json> },
  "plan_diff": [ <moved-node record> ],
  "node_stats": { "pre": [ <node_stat> ], "post": [ <node_stat> ] },
  "rows":    { "columns": [...], "rows": [[...]], "count": 0 },
  "metrics": { "join_pairs_tried": {"pre": 12, "post": 6}, ... },
  "errors":  [ <error_envelope> ],
  "sqlite_cross_check": { "sql_sent": "...", "sqlite_rows": [[...]],
                          "counter_diff": null | "...", "passed": true },
  "provenance": { "backend": "fixtures", "engine_commit": null,
                  "fixture_set": "default-v1", "protocol": null }
}
```

## Node stat (per-node, per-plan-version)

The implementation also emits `plans_ascii: {pre: string, post: string}` so
renderers can show canonical plan text without rebuilding it. Parse artifacts
include both readable `ast` and structured `tree`; lex artifacts contain the
actual token list and its locators. All seven stages are present even on
failure; stages not reached have status `skipped`. Verification mismatches mark
the verify stage as `error` and add a `VERIFY_MISMATCH` envelope while retaining
the result and comparison evidence. Metrics also include `left_in` / `right_in`
for the join inputs.

The demo's headline numbers ("student rows reaching the join: 4 → 2",
"candidate pairs: 12 → 6") require **per-node counters emitted separately for
the pre- and post-pushdown plans**. A flat counter cannot do this.

```jsonc
{ "node_id": 3, "operator": "Join",
  "label": "student.dept_id = department.id",
  "rows_in": 7, "left_in": 4, "right_in": 3, "rows_out": 4,
  "join_pairs_tried": 12, "join_pairs_matched": 4, "time_ns": 0 }
```

`node_id` is assigned at plan construction and is stable across the pre/post
copies of the same tree. New Filter nodes created by the rewrite get fresh ids.

## Plan JSON + diff-as-data

```jsonc
<plan_json> ::= { "node_id": n, "operator": "Scan|Filter|Join|Project",
                  "label": "Scan(student)", "detail": {...},
                  "children": [ <plan_json>... ] }

<moved-node record> ::= { "term_id": "term#1",
                          "term": "student.marks > 80",
                          "target": "left" | "right" | "kept",
                          "from_node_id": 4, "to_node_id": 6 }
```

The pushdown diff is **emitted as data** by the compiler. The UI never
computes diffs; it highlights whatever `plan_diff` says moved. Each `AND`
term gets a stable `term_id` (`term#k`, WHERE order) threaded through the
rewrite.

## Locator union (on every AST node, from day one)

```jsonc
{ "kind": "sql_span",      "char_start": 7, "char_end": 12,
  "line": 1, "col": 8, "end_line": 1, "end_col": 13,
  "token_index_range": [2, 2] | null }
{ "kind": "template_slot", "template_id": "...", "slot": "...", "capture_offset": 0 }
{ "kind": "nl_span", "char_start": 5, "char_end": 18,
  "line": 1, "col": 6, "end_line": 1, "end_col": 19 }
{ "kind": "builder_node",  "node_id": "..." }
{ "kind": "json_pointer",  "pointer": "$.bool.filter[2].term" }
```

Each frontend emits its native locator from this union so diagnostics stay
location-accurate in every frontend tab.
`propagate_positions=True` must preserve **both**
line:col and char offsets.

NL language v1 replaces sentence templates with a real lexer/LALR parser.
`template_slot` remains readable for legacy replay bundles only. Current NL
tokens and both ASTs retain `nl_span` positions in the original NL text.
Offsets count Unicode code points; the browser converts them to UTF-16 indices
only when selecting text in an editor.

NL lex artifacts contain `{language: "nl", tokens, token_count}`. Parse
artifacts include `nl_ast`/`nl_ast_text` (surface AST), `nl_grammar`,
`nl_language_version`, and `nl_lowering` (resolved fields, tables, join evidence),
alongside the existing `tree`/`ast` shared-query AST. Generated SQL is a display
artifact, not a hidden NL-to-SQL reparse. The workspace also advertises
`nl_language.version` so a new console can detect a stale template-era server.

## Session data

The server owns one session dataset for its lifespan: a Python fixture adapter
(canonical), a seeded SQLite database, and, when built, a seeded Rust `kb_db`
engine. `POST /api/data/insert {v, table, rows}` validates rows against the
registry and appends them to **all** stores, so every backend and the SQLite
cross-check see identical rows. `POST /api/data/dataset {v, dataset}` switches
to a preloaded fixture set (`default-v1`, `classroom-60`) or re-selects the
current one to reset; the engine is restarted on a fresh file because kb_db is
append-only. The workspace reports `dataset`, `datasets`, and per-table
`row_count`. Designed failures: `DATA_UNKNOWN_TABLE`, `DATA_INVALID_ROW`,
`DATA_INTEGER_PRECISION` (browser-safe range), `DATA_UNKNOWN_DATASET`.
Replay bundles and the CLI (`default_run`) stay on the immutable default
fixtures, so recorded evidence never depends on session edits.

## Error envelope

```jsonc
{ "stage": "lex|parse|bind|plan|optimize|execute|verify|bridge|storage",
  "code": "PARSE_UNEXPECTED_TOKEN | BIND_UNKNOWN_TABLE | BIND_UNKNOWN_COLUMN
         | BIND_AMBIGUOUS_COLUMN | BIND_TYPE_MISMATCH | BIND_UNSUPPORTED_OP_FOR_TEXT
         | BIND_INT_OUT_OF_RANGE | BIND_DUPLICATE_TABLE_REF | BIND_JOIN_MISMATCH
         | VERIFY_MISMATCH | INTERNAL",
  "message": "Unknown column 'grade' in table 'student'",
  "locator": <locator> | null,
  "origin": "sql_compiler" | "kb_bridge" | "console" }
```

* Rendered form: `Semantic error at 1:8. Unknown column 'grade' in table
  'student'.` — the renderer prepends `Semantic error at line:col.` and may
  draw a caret line; the envelope itself stores only the raw message + locator.
* Raw exceptions are forbidden at any boundary; everything user-visible is an
  envelope.

## Versioning

`run_schema_version` bumps additively only. Stale bundles (e.g. replayed demo
bundles) are detectable via the version + `provenance`.

## Browser boundary

The Python compiler and CLI retain signed 64-bit integer support. The initial
console deliberately follows the v1 UI non-goal: integers outside
`[-9007199254740991, 9007199254740991]` are not supported in browser artifacts.
`compose.console_run` rejects such bundles with
`CONSOLE_INTEGER_PRECISION` before HTTP serialization; it never sends a rounded
value as a successful result. The console also rejects unsafe integers in
imported replay files. A lossless bigint wire encoding would be a separate
versioned contract, not an implicit conversion of INTEGER cells to TEXT.
