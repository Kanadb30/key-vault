# kb_db on-disk format — v1 (normative)

Status: **frozen 2026-11-14, before any schema-bearing `.db` file exists.**
Supersedes the draft at the top of `key-vault/page_layout.md`, which is kept
only as format history. This document is the single source of truth for v1.

## Page geometry (unchanged from v0)

* `PAGE_SIZE = 4096` bytes.
* 14-byte big-endian header on every page:
  `page_no (4B) | page_type (2B) | data_end (2B) | record_count (2B) | next_page_no (4B)`
* Page types: `0 = StartPage`, `1 = DataPage`, `2 = CatalogPage`.
* Sentinel `u32::MAX` means "none" for `next_page_no`, `catalog_page_no`,
  `next_table_id`.

## New in v1: format identification

The StartPage free region (bytes 22+, never used by v0 — StartPage never holds
records) gains two fields. **No existing header or metadata byte shifts.**

| Offset (StartPage) | Size | Field | Notes |
| --- | --- | --- | --- |
| 14 | 4 | `next_table_id` | unchanged (v0) |
| 18 | 4 | `catalog_page_no` | unchanged (v0) |
| 22 | 4 | magic `KBDB` | literal bytes `0x4B 0x42 0x44 0x42` |
| 26 | 4 | `format_version` | u32 BE, `1` for this layout |

* A v0 file (no magic) is **refused at `Database::new` with an explicit
  migration error** — no silent reinterpretation, no automatic migration.
  There is no v0 data worth preserving; fixtures live on the Python side.
* The magic/version check runs **before** the catalog walk.
* `data_end` on a StartPage stays `14` (it describes the header-terminated
  record area, not the metadata region; the header's meaning is documented,
  not redefined).

## Catalog record v1 (schema-bearing)

Length-prefixed, uniform with data records:

```text
len (2B, big-endian, counts everything after the length field)
  table_id      4B
  start_page    4B
  col_count     2B
  per column:
    col_name_len  2B
    col_name      <col_name_len> B (UTF-8)
    col_type      1B   (0 = INTEGER, 1 = TEXT)
  table_name_len 2B
  table_name     <table_name_len> B (UTF-8)
```

* The length prefix makes the record **skip-safe**: a reader that does not
  understand the column block can still walk record boundaries.
* Writer and reader share one stride rule: advance by `len + 2`.

## Row encoding (DataPage records)

Rows are **schema-positional, not self-describing** — the catalog's column
order defines the layout. Data records keep the v0 length-prefix form
(`len(2B) | row bytes`):

```text
per column, in catalog column order:
  INTEGER: 8B big-endian two's complement (i64)
  TEXT:    2B big-endian length + UTF-8 bytes
```

* **No NULLs in v1.** Every column is non-null. Any future NULL support is an
  explicit v2 migration (null bitmap).
* **Row cap:** `record_length` is u16 and the header is 14 B, so a row is at
  most `4096 - 14 - 2 = 4080` bytes. Larger rows are rejected with a **typed
  error distinct from "page full"** ("record too large for any page").
  Records may still chain across *pages* for catalog growth; a single record
  never spans pages.

## Validation at open

`Database::new` rejects, with structured errors: bad magic/version, a page
whose header fields are impossible (`data_end > PAGE_SIZE`, page_no out of
range), truncated final page, and catalog records whose declared length
overruns the page.

## Change policy

Any change to offsets, record layout, or row encoding ⇒ `format_version += 1`
and a new section here. v1 readers must refuse higher versions loudly.
