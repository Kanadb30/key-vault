# Unified-query v1 — 2026-11-15

## Implemented

- Four frontends: SQL, form-based builder, grammar-based controlled NL, and
  Elastic-style JSON DSL with native source locators.
- One shared AST/binder/IR/optimizer/interpreter with per-node before/after
  counters and duplicate-sensitive SQLite verification.
- Three selectable scan stores: fixtures, SQLite, and Rust `kb_db`.
- Rust v1 schema catalog, typed row codec, page chaining, RAII pins, reopen
  persistence, corruption validation, native CLI, and NDJSON bridge.
- Console with generated SQL, native NL tokens/AST/lowering evidence, path/field diagnostics, explicit
  backend state, replay/export, presets, and responsive stage inspection.
- Session dataset management: two preloaded fixture sets (4-row demo data,
  60-student classroom), per-table row inserts through a form or pasted JSON,
  and reset. Inserts apply to all three stores, so every backend and the
  SQLite cross-check see identical rows; switching datasets rebuilds them.
- Eight generated replay bundles, CLI fallback, six-minute script, and package
  Interface / Invariants / Side effects contracts.
- Race-free launcher defaults to a free port from 8001, identifies this app
  at `/api/health`, and never stops another service.

The canonical query returns Asha/CSE and Meera/ECE. Candidate pairs are 12→6;
left rows entering the join are 4→2, identically for all 12 frontend/backend
combinations.

## Verification

```bash
make test
KB_DB_BIN="$PWD/key-vault/target/debug/kb_db" uv run pytest
PLAYWRIGHT_CHROMIUM_EXECUTABLE=/path/to/chromium make test-console
```

The suites include native persistence across more than five pages, catalog
chaining, malformed records, v0/version refusal, typed protocol errors,
malformed/slow/crashed child processes, frontend AST equivalence, all backend
combinations, port-conflict safety, and two real HTTP cold starts.
Python-only runs skip cross-language tests when `KB_DB_BIN` is unset.

Final local results after the NL compiler upgrade: **326 Python/API/integration
tests**, **13 Rust tests**, and **32 desktop/mobile browser tests** passed.
The production console build and `git diff --check` also passed.
`make test` separately verifies
the Rust-free default run and the explicitly enabled cross-language layer.

NL coverage includes independently composed grammar productions, arbitrary
field lists, possessive owners alongside quoted literals, unrelated catalogs,
unique declared joins, native source diagnostics, direct AST lowering without
SQL reparsing, and execution across all three storage backends. Data coverage
includes deterministic larger fixtures, insert fan-out to every store, engine
reseeding on dataset switches, and rejection of malformed or oversized rows.

Browser tests on this machine use `/opt/brave-bin/brave` in an isolated
profile. Desktop/mobile screenshots for SQL, Builder, NL, and DSL are under
`/tmp/opencode/sql-{console,builder,nl,elastic}-{desktop,mobile}.png`.
The mechanical UI detector found no issues; the independent extension review
closed with a ship verdict.

## Deliberate v1 limits

NL is a compositional, schema-aware query language, not unrestricted English
or an LLM. Its lexer/parser build a separate AST; lowering requires a unique
declared join relationship or an explicit ON clause. DSL is a finite Elastic-style subset with
a documented local join extension, not an Elasticsearch client. No OR,
ordering, aggregates, NULLs, or multiple joins. Browser bigint transport,
drag-and-drop, graph visualization, and PyO3 remain outside this release.

The local app seeds one temporary Rust database per session dataset; switching
or resetting a dataset rebuilds it on a fresh file. Inserts never delete
anything: kb_db stays append-only. Native CLI databases persist at their
explicit path, and the CLI's default queries always read the immutable demo
fixtures, not session edits. There is no WAL,
crash-atomic transaction, multi-process writer locking, authentication, public
deployment, or arbitrary-dataset UI. Engine absence/failure is explicit, never
an automatic data-source substitution.

Automated cold starts do not establish a physical projector/reboot rehearsal;
those remain manual. The specialized EGM bootstrap tool is not installed in
this environment; package contracts were written against the actual code.

## Run

```bash
uv pip install -r requirements.txt
make build
bash demo/run_demo.sh
```

Open the **printed** URL, normally `http://127.0.0.1:8001/`, not an old server
tab. Stop an older compiler instance with Ctrl+C in its own terminal before
restarting if you want to reuse its port. `make demo` is the Rust-free fallback.
