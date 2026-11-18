# Repository layout

The complete project is tracked in one repository:

- `console/`: React web console.
- `api/`: local HTTP API.
- `core/`, `frontends/`, `sql_compiler/`: shared types and compiler pipeline.
- `storage/`: fixture, SQLite, and Rust bridge adapters.
- `key-vault/`: Rust database engine, including its Cargo manifest and tests.
- `tests/`, `demo/`, `docs/`: project tests, runnable examples, and contracts.

## Packaging change

Previously, the Python/console project was a separate local repository with
`key-vault/` tracked as an embedded Git repository. Cloning that parent repository
did not include the engine sources.

The complete-project PR instead starts from the existing `Kanadb30/key-vault`
history, moves the engine into `key-vault/`, and includes the parent project's
tracked files at the root. There are no Git links or nested repositories in
this layout. One clone contains all source code.

The engine files include the typed-storage and NDJSON bridge changes also
proposed in PR #1. The full-project PR is an alternative to that backend-only
PR, not a second independent feature.

## Build paths

Run project commands from the repository root:

```bash
uv venv
uv pip install -r requirements.txt
make build
make test
bash demo/run_demo.sh
```

For engine-only work, use `cargo test --manifest-path key-vault/Cargo.toml`
or run Cargo from `key-vault/`.

Build outputs, virtual environments, installed JavaScript dependencies,
temporary databases, and test caches remain ignored. Project presentation
decks are included because they are tracked project deliverables.
