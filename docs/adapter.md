# Storage adapter contract (v1)

Status: **frozen 2026-11-14.** Module: `storage/adapter.py` (a
`typing.Protocol`). The Python schema registry (`core/types.py`) is the
**single source of truth** for schemas; adapters mirror it and are validated
against it — never the reverse.

## Interface

```python
class StorageAdapter(Protocol):
    def probe(self) -> dict: ...
        # availability + metadata, e.g. {"backend": "fixtures", "available": True}
    def open_catalog(self) -> dict[str, TableSchema]: ...
        # schema view; validated against the registry on connect
    def create_table(self, name: str, columns: Sequence[Column]) -> None: ...
    def insert_rows(self, table: str, rows: Sequence[Sequence[object]]) -> None: ...
    def scan(self, table: str) -> Relation: ...
```

```python
Column   = (name: str, type: "INTEGER" | "TEXT")
Relation = (columns: tuple[Column, ...], rows: tuple[tuple[object, ...], ...])
```

## Semantics (part of the contract — adapters must state them)

* **Row order** = physical scan order = insertion order (append-only v1, no
  updates/deletes).
* **Duplicates are preserved** end to end.
* Rows are **positional and hashable**; the interpreter's `Scan` operator is
  the **single owner of row keying** (`("table", "column")` tuples). No
  adapter ever returns keyed dicts.
* Values are typed: `int` for INTEGER, `str` for TEXT. No `None`, no floats,
  no bools (v1 is non-null by spec).
* The engine adapter is a **dumb scan store**: no filtering, no joins, no
  projection. Every relational operator lives in `sql_compiler/exec.py`.

## Registry validation

* On connect, the adapter's `open_catalog()` is validated against the
  registry: same table set, same column names, **same column order**, same
  types. Mismatch = loud error, never silent rebinding.
* `scan()` results are re-validated on every scan (cheap drift detection
  mid-session).

## Fallback policy

The fixtures fallback is decided by the **console layer**, never inside an
adapter: it is per-session, loudly flagged in the UI and metrics, and refused
outright if the engine catalog contains tables absent from the registry
(silently showing different data is the one failure the fallback must never
have).

## Implementations (v1)

| Adapter | Backend | Role |
| --- | --- | --- |
| `storage/fixtures.py` | in-memory dicts | graded demo, deterministic |
| `storage/sqlite_adapter.py` | stdlib `sqlite3` | correctness oracle — the **third implementation of the same contract**, exercised by the cross-check |
| `storage/kb_bridge/` | Rust `kb_db` via NDJSON stdio | portfolio; verified by the matrix test, **excluded from the SQLite correctness loop** |

The SQLite cross-check (`Counter`-comparison, order-insensitive) runs over
fixtures; kb_db is verified separately by contract + matrix tests against the
same fixture data.
