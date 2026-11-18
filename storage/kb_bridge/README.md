# Rust bridge adapter

## Interface

`KbAdapter(binary, db_path, timeout=5)` implements `StorageAdapter` and is a
context manager. The binary receives `--bridge --db /absolute/path`.
Wire contract: [`docs/protocol.md`](../../docs/protocol.md).

## Invariants

One outstanding request under a reentrant lock. Exact protocol/format
handshake, echoed IDs, terminal response checks, schema revalidation, 8 MiB
line/request and 64 MiB total response bounds. Requests have a total deadline,
including writes and all row batches. Rows preserve order and duplicates.
No query operators or automatic fixture fallback.

## Side effects

Spawns a child, reads protocol stdout, drains stderr into a bounded ring, and
owns termination/descriptor cleanup. Transport faults close the stream;
typed request errors remain recoverable. Diagnostics include recent request
metadata, stderr, and the child's exit code when available.
