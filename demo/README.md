# Demo tools and replay evidence

## Interface

`bash demo/run_demo.sh` serves the prebuilt console. `PORT` requires an exact
port; without it, the launcher searches from 8001 and prints its chosen URL.
`python -m demo.generate` regenerates eight real QueryRun bundles.
`python -m demo.generate --only nl` refreshes only the NL replay.
See [`docs/demo_script.md`](../docs/demo_script.md) for the walkthrough.

## Invariants

The launcher binds its socket before starting Uvicorn and reuses that socket,
so no check/bind race can send the user to another service. It never kills
or reconfigures another app. Recorded bundles are generated, not hand-edited;
their UI replay state is distinct from a live compiler run.

## Side effects

Starts the local API, writes generated JSON under `bundles/`, and opens an
ephemeral Rust demo database through the application's runtime when available.
