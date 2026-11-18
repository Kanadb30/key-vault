# Verification

## Interface

- `uv run pytest`: Python/API/frontend suites; cross-language tests skip when
  `KB_DB_BIN` is unset.
- `cargo test --manifest-path key-vault/Cargo.toml`: Python-free engine tests.
- `make test-integration`: builds Rust and sets `KB_DB_BIN` for contract/matrix.
- `make test-console`: production build plus desktop/mobile Playwright checks.

## Invariants

`spine/` locks the graded SQL behavior and bundle evidence. `golden/` proves
frontend AST/plan equivalence. `contract/` exercises real persistence and
malformed child transports. `matrix/` compares all 12 frontend/backend
combinations. `api/` checks DTOs, explicit availability, and launcher behavior.
`test_deps.py` enforces import direction.

## Side effects

Temporary files/processes and localhost test servers; owned resources are
closed after each test. Browser artifacts are under `console/test-results/`
and `/tmp/opencode/`. No user's existing server or browser profile is reused.
