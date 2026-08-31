# KB_DB - A Simple Relational Database Engine

**Status**: 🚧 **ONGOING** - Active Development

A lightweight, educational database engine written in Rust, implementing core database concepts including page-based storage, buffer pool management, and catalog management.

## Overview

KB_DB is a from-scratch implementation of a relational database engine focusing on fundamental database components. This project explores key concepts in database design such as:

- **Page-based storage management** (4KB pages)
- **Buffer pool with LRU eviction policy**
- **Disk I/O management**
- **Table catalog and metadata management**
- **Error handling and recovery**



## Architecture

### Layered Design

```
┌─────────────────────────────────┐
│   Application Layer             │
│   (SQL Parser, Query Engine)    │
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
- `buffer_pool.rs` - LRU cache with configurable capacity
- `page.rs` - Fixed 4KB pages with three types (Start, Catalog, Data)

**Catalog Layer** (`src/catalog/`):
- `manager.rs` - Table creation and metadata management
- `table.rs` & `metadata.rs` - Table definitions and schema

**Error Handling** (`src/error.rs`): Custom error types via `thiserror`

## Page Layout

See [page_layout.md](page_layout.md) for detailed page structure specifications and byte-level layout.

## Building & Development

### Prerequisites

- **Rust** 1.70+ (edition 2024)
- **Cargo**

### Dependencies

- `thiserror` (2.0) - Error handling

### Build Instructions

On Windows (via WSL):
```bash
wsl cargo build
```

On Linux/macOS:
```bash
cargo build
```
 & Run

**Prerequisites**: Rust 1.70+, WSL for Windows

```bash
# Windows (via WSL)
wsl cargo build

# Linux/macOS
cargo build

# Run
cargo run

# Test
cargo test> Result<()> {
    // Create or open a database
    let db = Database::new("mydb")?;
    
    // Future: Add tables, insert records, execute queries
    
    Ok(())
}
```



## Contributing

This is a personal educational project. Feel free to fork and experiment!
