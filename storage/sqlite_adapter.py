"""SQLite backend (stdlib) — the third implementation of the adapter contract
and the correctness oracle for the cross-check.

Interface: StorageAdapter over a sqlite3 connection (default :memory:), plus
`execute_sql` for the cross-check's raw query (SQLite-specific, not part of
the Protocol).
Invariants: scan returns rows in rowid (insertion) order for v1; values map
int ↔ INTEGER, str ↔ TEXT. One connection may be shared across threads (the
demo server's session database is built at startup and used by request worker
threads), so every operation serializes on an internal lock.
Side effects: DDL/DML on its own connection.
"""
from __future__ import annotations

import sqlite3
import threading
from typing import Sequence

from core.types import Column, Relation, TableSchema, validate_rows


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


class SQLiteAdapter:
    backend_name = "sqlite"

    def __init__(self, db_path: str = ":memory:") -> None:
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> SQLiteAdapter:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def probe(self) -> dict:
        return {"backend": self.backend_name, "available": True}

    def open_catalog(self) -> dict[str, TableSchema]:
        with self._lock:
            tables = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
            return {
                name: TableSchema(name, tuple(
                    Column(row[1], row[2]) for row in self._conn.execute(f"PRAGMA table_info({_quote(name)})")
                ))
                for (name,) in tables
            }

    def create_table(self, name: str, columns: Sequence[Column]) -> None:
        schema = TableSchema(name.lower(), tuple(columns))
        cols_sql = ", ".join(f'{_quote(c.name)} {c.type} NOT NULL' for c in schema.columns)
        with self._lock, self._conn:
            self._conn.execute(f'CREATE TABLE {_quote(schema.name)} ({cols_sql})')

    def insert_rows(self, table: str, rows: Sequence[Sequence[object]]) -> None:
        if not rows:
            return
        rel = self.open_catalog()[table.lower()]
        validate_rows(rel.columns, rows)
        placeholders = ", ".join("?" for _ in rel.columns)
        with self._lock, self._conn:
            self._conn.executemany(
                f'INSERT INTO {_quote(table.lower())} VALUES ({placeholders})', [tuple(r) for r in rows]
            )

    def scan(self, table: str) -> Relation:
        key = table.lower()
        schema = self.open_catalog()[key]
        hidden_rowid = next(
            (alias for alias in ("rowid", "_rowid_", "oid") if alias not in schema.column_names()),
            None,
        )
        order = f" ORDER BY {hidden_rowid}" if hidden_rowid else ""
        with self._lock:
            cur = self._conn.execute(f'SELECT * FROM {_quote(key)}{order}')
            rows = tuple(tuple(r) for r in cur.fetchall())
        return Relation(schema.columns, rows)

    def execute_sql(self, sql: str) -> list[tuple]:
        """Raw SQL passthrough — used by the pipeline's SQLite cross-check."""
        with self._lock:
            return [tuple(r) for r in self._conn.execute(sql).fetchall()]
