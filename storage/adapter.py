"""Storage adapter contract (docs/adapter.md) — frozen v1.

Interface (typing.Protocol): probe / open_catalog / create_table /
insert_rows / scan.

Invariants (part of the contract):
- rows are positional and hashable, in insertion order; duplicates preserved;
- values are int (INTEGER) or str (TEXT), never None/float/bool;
- row keying ("table", "column") is owned by the interpreter's Scan
  operator — no adapter ever returns keyed dicts;
- the engine adapter is a dumb scan store: no filtering, no joins, no
  projection — every relational operator lives in sql_compiler.exec.

Side effects: create_table/insert_rows mutate backend storage; scan may
perform I/O on real backends.
"""
from __future__ import annotations

from typing import Protocol, Sequence

from core.types import Column, Relation, TableSchema


class StorageAdapter(Protocol):
    def probe(self) -> dict: ...

    def open_catalog(self) -> dict[str, TableSchema]: ...

    def create_table(self, name: str, columns: Sequence[Column]) -> None: ...

    def insert_rows(self, table: str, rows: Sequence[Sequence[object]]) -> None: ...

    def scan(self, table: str) -> Relation: ...
