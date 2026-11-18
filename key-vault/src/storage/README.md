# Page storage

## Interface

DiskManager reads/writes exact 4096-byte pages. Page validates headers and
length-prefixed records. BufferPool caches five pages; PageGuard unpins on Drop.

## Invariants

Corruption is rejected before record slicing. Page-full and record-too-large
are distinct errors. Guarded scans retain only one page pin. Eviction preserves
pinned entries and never evicts a pinned page. New files are created exclusively.

## Side effects

File reads/writes, allocation, dirty-page flushing, and fsync. No filtering,
projection, join, or implicit file migration.
