# Shared value types

## Interface

`core/types.py` defines `Column`, `TableSchema`, `Relation`, `SchemaRegistry`,
and batch value validation. The registry validates full catalogs and scan
relations against the authoritative schemas.

## Invariants

- Schemas use distinct, lowercase SQL identifiers and nonempty column lists.
- Values are exact Python `int` in the signed i64 range, or exact `str`;
  booleans, floats, and NULLs are not valid column values.
- Relations use positional, hashable rows. Adapter rows do not contain the
  interpreter's `(table, column)` keys.
- This package imports no compiler, frontend, storage, or API code.

## Side effects

Registry registration mutates its local schema mapping. No file, process, or
network I/O.
