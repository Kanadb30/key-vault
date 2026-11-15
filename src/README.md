# Engine modules

## Interface

`database::Database` exposes create/open, typed create/insert/scan, catalog
inspection, page dumps, and flush. `main.rs` supplies the CLI and stdio bridge.
`codec.rs` owns the v1 binary record layout.

## Invariants

No SQL/query operators in Rust. Catalog types and positional rows are shared
by the CLI and bridge; all page access in Database uses scoped guards.

## Side effects

Database methods perform disk I/O; main also owns process stdio. See the
storage/catalog contracts below and the crate README for durability limits.
