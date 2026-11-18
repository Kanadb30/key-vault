# KB_DB - A Simple Relational Database Engine

**Status**: format-v1 append-only storage and protocol-v1 bridge implemented.

A lightweight, educational database engine written in Rust, implementing core database concepts including page-based storage, buffer pool management, and catalog management.

## Overview

KB_DB is a from-scratch implementation of a relational database engine focusing on fundamental database components. This project explores key concepts in database design such as:

- **Page-based storage management** (4KB pages)
- **Buffer pool with LRU eviction policy**
- **Disk I/O management**
- **Table catalog and metadata management**
- **Error handling and recovery**

## Interface

The engine stores schema-bearing tables and typed rows; SQL parsing, filtering,
joins, and optimization belong to the Python compiler in the parent project.

```bash
cargo build
cargo test
cargo run -- --db /absolute/demo.db dump-catalog
cargo run -- --db /absolute/demo.db create-table items '[{"name":"id","type":"INTEGER"}]'
cargo run -- --db /absolute/demo.db insert items '[[1],[2],[2]]'
cargo run -- --db /absolute/demo.db scan items
cargo run -- --db /absolute/demo.db --bridge
```

Other CLI command: `dump-page N`. `--bridge` speaks NDJSON on stdout and logs
only to stderr. It requires a protocol-1 ready handshake.

## Invariants

4096-byte pages, a five-page LRU buffer pool, RAII one-page scan pins,
length-prefixed catalog/data records, non-null i64/TEXT rows, and a 4080-byte
encoded-record cap. Opens reject legacy v0, unsupported versions, truncated
pages, malformed records, and cycles. Batch values are validated before
inserting; duplicates and insertion order survive reopen.

This is not a transactional database: no WAL, crash-atomic multi-page
operations, multi-process writer locking, updates, or deletes. Do not open
the same file for simultaneous writers. Explicit `flush` syncs data; Drop is
best-effort cleanup, not an error-reporting durability boundary.

## Side effects

Creates/opens the exact database path supplied (no implicit `.db` suffix),
appends pages/rows, and calls `sync_all` on flush. The bridge exits on stdin EOF.
Files created by the old format are refused, never migrated or overwritten.

## Architecture

### Layered Design

```
┌─────────────────────────────────┐
│   Application Layer             │
│   (Python compiler / bridge)    │
└────────────────┬────────────────┘
┌────────────────▼────────────────┐
│   Catalog Layer                 │
│   (Table Metadata, Schema)      │
└────────────────┬────────────────┘
┌────────────────▼────────────────┐
│   Buffer Pool Layer             │
│   (LRU Cache Management)        │
└────────────────┬────────────────┘
┌────────────────▼────────────────┐
│   Storage Layer                 │
│   (Disk I/O, Page Management)   │
└─────────────────────────────────┘
```

## Core Components

**Storage Layer** (`src/storage/`):
- `disk_manager.rs` - File I/O and page persistence
- `buffer_pool.rs` - five-page LRU cache and RAII page guards
- `page.rs` - Fixed 4KB pages with three types (Start, Catalog, Data)

**Catalog Layer** (`src/catalog/`):
- `manager.rs` - Table creation and metadata management
- `table.rs` - Table definitions and schema

`codec.rs` defines positional row and schema-bearing catalog encoding.

**Error Handling** (`src/error.rs`): Custom error types via `thiserror`

## Page Layout

See [page_layout.md](page_layout.md) for the v1 summary and legacy history;
the parent project's `docs/format_v1.md` is the normative full specification.

## Building & Development

Run the commands below from the `key-vault/` directory.

### Prerequisites

- **Rust** 1.85+ (edition 2024 requires 1.85 or newer)
- **Cargo**

### Dependencies

- `thiserror` (2.0) - Error handling
- `serde`, `serde_json` - typed bridge and CLI JSON

### Build Instructions

On Windows (via WSL):
```bash
wsl cargo build
```

On Linux/macOS:
```bash
cargo build
```

### Run & Test

```bash
# Linux/macOS
cargo run -- --db /absolute/demo.db dump-catalog
cargo test
```

### Example

```rust
use kb_db::database::Database;

fn main() -> kb_db::error::Result<()> {
    // Create or open a database
    let mut db = Database::new("/absolute/mydb.db")?;
    db.flush()?;

    Ok(())
}
```

## Contributing

This is a personal educational project. Feel free to fork and experiment!
