"""Core value types — see package docstring in __init__.py."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Literal, Mapping, Sequence

Type = Literal["INTEGER", "TEXT"]

def validate_name(name: str) -> None:
    if not isinstance(name, str) or re.fullmatch(r"[a-z_][a-z0-9_]*", name) is None:
        raise ValueError(f"expected a lowercase SQL identifier, got {name!r}")


@dataclass(frozen=True)
class Column:
    name: str
    type: Type

    def __post_init__(self) -> None:
        validate_name(self.name)
        if self.type not in ("INTEGER", "TEXT"):
            raise ValueError(f"unsupported column type {self.type!r}")


@dataclass(frozen=True)
class TableSchema:
    name: str
    columns: tuple[Column, ...]

    def __post_init__(self) -> None:
        validate_name(self.name)
        names = self.column_names()
        if not names or len(set(names)) != len(names):
            raise ValueError("a schema needs nonempty, distinct columns")

    def column_names(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.columns)

    def column_type(self, name: str) -> Type | None:
        for c in self.columns:
            if c.name == name:
                return c.type
        return None

    def has_column(self, name: str) -> bool:
        return self.column_type(name) is not None


@dataclass(frozen=True)
class Relation:
    columns: tuple[Column, ...]
    rows: tuple[tuple[object, ...], ...]


def validate_rows(columns: Sequence[Column], rows: Sequence[Sequence[object]]) -> None:
    """Check a whole batch before mutation. bool is not an INTEGER in v1."""
    for row in rows:
        if len(row) != len(columns):
            raise ValueError(f"row width {len(row)} != column count {len(columns)}")
        for col, value in zip(columns, row):
            expected = int if col.type == "INTEGER" else str
            if type(value) is not expected:
                raise ValueError(f"column '{col.name}' requires {col.type}, got {type(value).__name__}")
            if col.type == "INTEGER" and not -(2**63) <= value <= 2**63 - 1:
                raise ValueError(f"column '{col.name}' is outside the signed 64-bit range")


class SchemaRegistry:
    """Single source of truth for table schemas.

    Adapters mirror the registry and are validated against it on connect and
    on every scan — never the other way around (docs/adapter.md).
    """

    def __init__(
        self,
        tables: Mapping[str, TableSchema] | Iterable[TableSchema] | None = None,
    ) -> None:
        self._tables: dict[str, TableSchema] = {}
        if tables:
            items: Iterable[TableSchema] = (
                tables.values() if isinstance(tables, Mapping) else tables
            )
            for schema in items:
                self.add(schema)

    def add(self, schema: TableSchema) -> None:
        key = schema.name.lower()
        if key in self._tables:
            raise ValueError(f"table '{key}' already registered")
        self._tables[key] = schema

    def table(self, name: str) -> TableSchema | None:
        return self._tables.get(name.lower())

    def tables(self) -> dict[str, TableSchema]:
        return dict(self._tables)

    def validate_catalog(self, catalog: Mapping[str, TableSchema]) -> None:
        if dict(catalog) != self._tables:
            raise ValueError("backend catalog does not match the schema registry (tables, column order, or types)")

    def validate_relation(self, table: str, relation: Relation) -> None:
        """Registry is authoritative: names, order, and types must match."""
        schema = self.table(table)
        if schema is None:
            raise KeyError(f"table '{table}' is not registered")
        actual = tuple((c.name, c.type) for c in relation.columns)
        expected = tuple((c.name, c.type) for c in schema.columns)
        if actual != expected:
            raise ValueError(
                f"backend schema drift for table '{table}': "
                f"registry={expected!r} backend={actual!r}"
            )
        validate_rows(relation.columns, relation.rows)
