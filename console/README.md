# Compiler console

## Interface

Vite + React + TypeScript, plain CSS. The production build is served by
`api/server.py` on the same origin as `/api/workspace` and `/api/query`.

```bash
npm --prefix console ci
npm --prefix console run build
bash demo/run_demo.sh
```

## Invariants

- The browser renders the QueryRun v1 bundle; it never parses SQL or computes
  relational semantics, plan rewrites, verification, or execution metrics.
- Changed editor text is marked as different from the displayed run.
- Imported bundles are labeled recorded evidence and validated before display.
- SQL, Builder, NL, and Elastic are enabled and keep separate editor drafts.
- Backend selection is explicit. Rust is warmed at startup if built; its
  absence does not disable fixture or SQLite execution, and never causes a
  silent fallback after the user selects Rust.
- The Data section talks to `/api/data/*` only: dataset switching, row
  inserts, and reset. It never mutates bundle evidence directly; a data
  change flags the displayed run as stale until it is rerun.
- No fonts, images, or scripts are fetched from a CDN at runtime.
- The browser supports safe JSON integers only. Use the CLI for full i64
  precision; the HTTP boundary rejects unsafe numeric artifacts explicitly.

## Side effects

Runs HTTP requests against the local compiler, reads user-selected bundle
files, and exports JSON downloads. No queries are persisted in browser storage.

## Development and verification

```bash
# Run the API in another terminal first.
npm --prefix console run dev

# Browser tests start and stop their own backend on port 8765.
npm --prefix console exec -- playwright install chromium
make test-console
```

If a Chromium-based browser is already installed:

```bash
PLAYWRIGHT_CHROMIUM_EXECUTABLE=/path/to/browser make test-console
```

The override launches a new isolated test profile, not the user's existing
browser session. Desktop and mobile suites cover all frontends, backends, stages, source changes,
keyboard execution, semantic diagnostics, transport errors, and bundle replay.
The first test also records screenshots under `/tmp/opencode/`.

`PRODUCT.md` records product truth. `DESIGN.md` records the implemented visual
system. `console/index.html` carries the surface's direction contract.
