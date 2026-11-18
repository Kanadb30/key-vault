# Console API

## Interface

- `GET /api/health`: fixture backend and explicit engine availability.
- `GET /api/workspace`: registry schema, presets, available frontends, and an
  initial real QueryRun bundle.
- `POST /api/query`: `{v: 1, frontend_id: "sql"|"builder"|"nl"|"elastic",
  backend: "fixtures"|"sqlite"|"kb_db", source: string, verify: bool}` →
  `{v: 1, bundle: QueryRun}`.
- `/`: prebuilt console, or an actionable 503 if it has not been built.

## Invariants

Compiler errors are successful HTTP responses containing bundle diagnostics.
Invalid DTOs use HTTP 422 with an error envelope. Request bodies are capped
at 128 KiB and source text at 16,384 characters. Extra request fields are
rejected. The composition root is `compose.py`; no compiler semantics live in
this package.

## Side effects

Reads static files, invokes fixture/SQLite execution, and logs unexpected
server failures without exposing internal exception text to the client.
The demo launcher binds localhost only; this is not an authenticated public
service. A single warm engine owns a temporary, seeded demo database for the
application lifespan; requests are serialized by its adapter lock. Native
`kb_db --db ...` CLI databases persist at the explicit path instead.
