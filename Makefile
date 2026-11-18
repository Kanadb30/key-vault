.PHONY: test test-python test-engine test-integration test-console console demo web-demo demo-bundles build

test: test-python test-engine test-integration

test-python:
	uv run pytest

test-engine:
	cargo test --manifest-path key-vault/Cargo.toml

test-integration:
	cargo build --manifest-path key-vault/Cargo.toml
	KB_DB_BIN="$(CURDIR)/key-vault/target/debug/kb_db" uv run pytest tests/contract tests/matrix

build: console
	cargo build --manifest-path key-vault/Cargo.toml

demo-bundles:
	uv run python -m demo.generate

demo:
	uv run python cli.py "SELECT student.name, department.dept_name FROM student JOIN department ON student.dept_id = department.id WHERE student.marks > 80;"

console:
	npm --prefix console ci
	npm --prefix console run build

test-console:
	npm --prefix console run build
	npm --prefix console run test:e2e

web-demo:
	bash demo/run_demo.sh
