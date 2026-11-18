# kb_db bridge protocol — v1

Status: **frozen 2026-11-14, before the bridge binary exists.**
Implemented in the first release. Contract completion: `open_catalog` was
added before shipping any v1 peer because registry validation must discover
unknown tables; this does not change existing frames.
The Python compiler owns all query semantics; the engine is a dumb scan store
(`create_table` / `insert_rows` / `scan_table` only — never filters, never
joins). If the engine ever executed predicates, `join_pairs` and the
pushdown metrics would silently differ per backend.

## Transport

* NDJSON over stdio: one JSON object per line, UTF-8, `\n` frame delimiter,
  flush after every frame.
* stdout = protocol frames only. stderr = human logs (Rust panic output lands
  there; Python captures it verbatim and attaches it to error cards).
* One outstanding request at a time in v1 (bounded work: fixture-scale scans).

## Handshake (exact integer match — no silent negotiation)

1. Engine's first stdout line, before any request:
   `{"type":"hello","protocol":1,"min_protocol":1,"engine":"kb_db","engine_version":"0.1.0","format_version":1}`
2. Python replies: `{"type":"ready","protocol":1}`
3. Protocol mismatch ⇒ loud refuse (structured error card). The only
   degradation path is the explicit per-session fixtures fallback, which is
   UI-flagged and refused if the engine catalog holds tables the Python
   registry does not know.
4. `protocol` (wire) and `format_version` (disk) evolve independently.

## Requests / responses

* Every request carries `"id"`; every response echoes it.
* Terminal rule: **exactly one terminal response per request** — either
  result frames or an error frame.
* Rows stream in batches:
  `{"type":"rows","id":n,"batch":[[...],...],"done":false}` … `"done":true`.
  Batch cap ~256 rows / ~1 MB. Python enforces a max-line guard (~8 MB) so a
  garbage child cannot OOM the console.
* Values on the wire: INTEGER = JSON integer (i64), TEXT = JSON string.
  No floats, booleans, or nulls are valid column values in v1.

## Error frames

```json
{"type":"error","id":n,"code":"...","message":"..."}
```

Stable codes (mapped 1:1 from Rust `CustomError` variants):

| Code | Meaning |
| --- | --- |
| `IO` | filesystem error |
| `CORRUPT` | bad magic/version/header/record bounds |
| `SCHEMA_MISMATCH` | table/column unknown or type mismatch |
| `RECORD_TOO_LARGE` | row exceeds the 4080 B v1 cap |
| `DUPLICATE_TABLE` | table id or name collision |
| `UNSUPPORTED` | request outside the v1 surface |
| `INTERNAL` | everything else |

## Panic & lifecycle semantics

* Panic semantics are explicit: the child **exits** with a reserved exit code
  (0 clean, 74 protocol error, 101 engine fatal); Python synthesizes the error
  frame client-side and surfaces an "engine crashed" card — never a hang, and
  never silent death.
* The child exits on stdin EOF; Python owns spawn/kill/cleanup.
* The local, unauthenticated demo uses one ephemeral subprocess and seeded
  database per application lifespan, spawned **warm at startup**, with requests
  serialized across browsers. It is not a multi-tenant session service.
* The `.db` path is passed explicitly (`--db` or env var) — never CWD-relative,
  which would silently create an empty database from the wrong directory.
* Scan discipline: the engine's scan iterator holds **one page pin at a time**
  (fetch → read → copy → unpin). `BufferPool` capacity is 5 and every fetch
  pins; holding pins across a scan wedges eviction at the 6th page.

## Commands (v1 surface)

| Request | Response |
| --- | --- |
| `{"type":"open_catalog","id":n}` | `{"type":"catalog","id":n,"tables":[{"name":"...","columns":[...]}]}` |
| `{"type":"create_table","id":n,"name":"...","columns":[{"name":"...","type":"INTEGER"\|"TEXT"},...]}` | `{"type":"ok","id":n}` |
| `{"type":"insert_rows","id":n,"table":"...","rows":[[...],...]}` | `{"type":"ok","id":n,"count":k}` |
| `{"type":"scan_table","id":n,"table":"..."}` | `rows` frames; each `rows` frame echoes the table's schema: `"columns":[{"name","type"},...]` |

`scan_table` responses always carry the schema; Python re-validates it against
the registry on every scan (cheap mid-session drift detection).

The Python client caps an entire response at 64 MiB and a request at 5 seconds
by default, including all batches. It closes a desynchronized child rather
than reusing the stream. These are local-demo resource limits, not query
operators or implicit LIMIT semantics; exceeding them returns an error.

## Versioning policy

Any frame change ⇒ `protocol += 1`. v1 peers refuse unknown protocols with a
structured error. Stored console bundles record the protocol version in
`provenance`.
