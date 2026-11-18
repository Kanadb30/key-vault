# SQL compiler

## Interface

`pipeline.run_query(source, registry=..., adapter=..., verify_runner=...)`
returns a JSON-only QueryRun v1 bundle. `compose.default_run` wires the default
fixtures and SQLite oracle; `cli.py` renders the walkthrough.

| Module | Responsibility |
| --- | --- |
| `grammar.lark`, `parser.py` | Basic lexer, strict LALR parser, source-located AST |
| `ast_nodes.py` | AST and Locator variants |
| `binder.py` | Name resolution, ambiguity, type/operator/i64 checks |
| `plan.py` | Scan/Filter/Join/Project IR, stable IDs, JSON and ASCII plans |
| `pushdown.py` | Pure pre/post rewrite and term-ID movement evidence |
| `exec.py` | Python relational execution and fresh per-node counters |
| `errors.py` | Error envelopes, normalized diagnostics, source carets |
| `bundle.py`, `pipeline.py` | JSON artifacts and the seven stage boundaries |

## Invariants

- Imports core, never storage, frontends, API, or the composition root.
- One optional inner equijoin; WHERE comparisons are AND-only. The grammar
  and binder deliberately reject unsupported SQL.
- The binder qualifies names and canonicalizes join operand order.
- Pushdown does not mutate its input; surviving nodes keep their IDs.
- The interpreter alone attaches `(table, column)` keys to scan values.
- Execution preserves duplicates. Join candidates are counted before ON is
  tested, separately for original and optimized plans.
- All stages appear in every bundle; failures are envelopes, later stages are
  skipped, and successful artifacts remain inspectable.
- The browser and CLI consume emitted evidence, not re-created query logic.

## Side effects

The parser loads its adjacent grammar at initialization. Execution probes and
reads the injected adapter; verification calls the injected oracle runner.
No database backend is created or selected inside this package.

Contracts: [`bundle schema`](../docs/bundle_schema.md) and
[`adapter contract`](../docs/adapter.md). Tests: `tests/spine/` and
`tests/test_deps.py`.
