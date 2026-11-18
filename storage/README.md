# Storage adapters

## Interface

`adapter.StorageAdapter` specifies `probe`, `open_catalog`, `create_table`,
`insert_rows`, and `scan`. Implementations currently provided:

- `FixtureAdapter`: deterministic in-memory relations.
- `SQLiteAdapter`: stdlib SQLite with catalog discovery, ordered scans, and
  explicit connection cleanup. Its `execute_sql` method is oracle-specific,
  not part of the adapter protocol.

- `KbAdapter` (`kb_bridge/`): warm subprocess transport with bounded frames,
  request timeouts, typed errors, schema validation, and explicit cleanup.

## Invariants

- Imports core only; no compiler, frontend, API, or composition-root imports.
- Typed positional rows, insertion order, and duplicates are preserved.
- Entire insert batches are value-checked before mutation.
- Full catalogs and every scan are validated against the Python registry by
  the compiler boundary.
- Adapters do not execute the plan's predicates, projections, or joins.
- No implicit fixtures fallback occurs inside an adapter.

## Side effects

The fixture adapter mutates local memory. SQLite creates tables and commits
rows on its own connection; file-backed connections persist those changes.
Use its context manager or `close()` to release the connection.

The frozen [`adapter contract`](../docs/adapter.md) is normative.
`tests/spine/test_storage.py` exercises both current implementations.
