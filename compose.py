"""Composition root — the only module allowed to import both sql_compiler and
storage (dependency-direction rule, enforced by tests/test_deps.py).

Interface:
- default_run(sql, *, frontend_id="sql", verify=True) -> QueryRun bundle
  wired to the in-memory fixture backend with the SQLite oracle verifier.
- make_verify_runner(fixture_adapter) -> verify_runner(bound, pre_rows,
  post_rows) implementing the Counter cross-check over in-memory fixtures
  only (the live backend is excluded from the correctness loop).

Side effects: in-memory SQLite inside the verify runner; adapter.scan side
effects for real backends.
"""
from __future__ import annotations

from collections import Counter
from itertools import islice
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile
import threading

from core.types import validate_rows
from demo.presets import PRESETS
from frontends.registry import PREPARE, LEXERS
from frontends.supported_matrix import SUPPORTED
from storage.fixtures import FIXTURE_SETS, default_fixtures, open_fixture_set
from storage.sqlite_adapter import SQLiteAdapter
from storage.kb_bridge import KbAdapter, BridgeError

ROOT = Path(__file__).resolve().parent
# Schema metadata, not an NL sentence template or a same-name-column heuristic.
NL_RELATIONSHIPS = (("student", "dept_id", "department", "id"),)


class Runtime:
    """One warm engine and one session dataset for this local demo
    application's lifespan, not per query.

    The session dataset is the Python fixture adapter; SQLite and the Rust
    engine are seeded replicas. Every insert applies to all stores, so any
    backend yields the same rows and the SQLite cross-check stays valid.
    A dataset switch or reset rebuilds the replicas (the engine is restarted
    on a fresh file — kb_db is append-only and has no delete).
    """
    def __init__(self, *, warm_engine=True, fixture_set="default-v1"):
        self.engine = None
        self.reason = "Rust binary not built; run cargo build --manifest-path key-vault/Cargo.toml"
        self.temp = tempfile.TemporaryDirectory(prefix="sql-compiler-")
        self._lock = threading.RLock()
        self._generation = 0
        self._binary = Path(os.environ.get("KB_DB_BIN", ROOT / "key-vault/target/debug/kb_db"))
        self.warm_engine = warm_engine
        self._sqlite = None
        self._load_dataset(fixture_set)
        if warm_engine and self._binary.is_file():
            self._start_engine()

    def _load_dataset(self, fixture_set: str) -> None:
        self.dataset = fixture_set
        self.fixtures, self.registry = open_fixture_set(fixture_set)
        self._generation += 1
        if self._sqlite is not None:
            self._sqlite.close()
        self._sqlite = SQLiteAdapter()
        for table, schema in self.registry.tables().items():
            self._sqlite.create_table(table, schema.columns)
            self._sqlite.insert_rows(table, self.fixtures.scan(table).rows)

    def _start_engine(self) -> None:
        if self.engine is not None:
            self.engine.close()
            self.engine = None
        try:
            engine = KbAdapter(self._binary, Path(self.temp.name) / f"engine-{self._generation}.db")
            try:
                for table, schema in self.registry.tables().items():
                    engine.create_table(table, schema.columns)
                    engine.insert_rows(table, self.fixtures.scan(table).rows)
                self.registry.validate_catalog(engine.open_catalog())
                engine.fixture_set = self.dataset
            except Exception:
                engine.close()
                raise
            self.engine = engine
            self.reason = ""
        except Exception as exc:
            self.engine = None
            self.reason = str(exc)

    def insert_rows(self, table: str, rows) -> dict:
        """Append rows to the session dataset and every seeded store."""
        with self._lock:
            schema = self.registry.table(table)
            if schema is None:
                raise KeyError(f"unknown table '{table}'. Available tables: {', '.join(self.registry.tables())}")
            validate_rows(schema.columns, rows)
            self.fixtures.insert_rows(table, rows)
            self._sqlite.insert_rows(table, rows)
            if self.engine is not None and self.engine.probe()["available"]:
                try:
                    self.engine.insert_rows(table, rows)
                except Exception as exc:
                    # close() is idempotent: a bridge error already closed it.
                    self.engine.close()
                    self.engine = None
                    self.reason = str(exc)
            return self.data_snapshot()

    def reset(self, dataset_id: str | None = None) -> dict:
        """Restore a dataset to its pristine rows (or switch datasets)."""
        with self._lock:
            dataset_id = dataset_id or self.dataset
            if dataset_id not in FIXTURE_SETS:
                raise ValueError(f"unknown dataset '{dataset_id}'. Available: {', '.join(FIXTURE_SETS)}")
            self._load_dataset(dataset_id)
            if self.warm_engine and self._binary.is_file():
                self._start_engine()
            return self.data_snapshot()

    def catalog_snapshot(self) -> list:
        return [
            {"name": schema.name, "columns": [
                {"name": column.name, "type": column.type} for column in schema.columns
            ], "row_count": len(self.fixtures.scan(schema.name).rows)}
            for schema in self.registry.tables().values()
        ]

    def data_snapshot(self) -> dict:
        return {"dataset": self.dataset, "catalog": self.catalog_snapshot(), "engine": self.engine_status()}

    def close(self):
        if self.engine: self.engine.close()
        if self._sqlite is not None: self._sqlite.close()
        self.temp.cleanup()

    def engine_status(self):
        available = self.engine is not None and self.engine.probe()["available"]
        return {"available": available, "reason": "" if available else self.reason or "Engine process is not running"}

    @contextmanager
    def backend(self, name):
        if name == "fixtures":
            yield self.fixtures, self.registry
        elif name == "sqlite":
            yield self._sqlite, self.registry
        elif name == "kb_db":
            if not self.engine_status()["available"]:
                raise BridgeError("BRIDGE_UNAVAILABLE", self.engine_status()["reason"])
            yield self.engine, self.registry
        else:
            raise ValueError("Unknown backend")


def make_verify_runner(fixture_adapter, *, source_sql: str | None = None):
    """Counter-based, order-insensitive cross-check against SQLite."""

    def verify_runner(bound, pre_rows, post_rows) -> dict:
        sql_sent = source_sql if source_sql is not None else _sql_for_sqlite(bound)
        with SQLiteAdapter() as oracle:
            for name, schema in fixture_adapter.open_catalog().items():
                oracle.create_table(name, schema.columns)
                oracle.insert_rows(name, fixture_adapter.scan(name).rows)
            sqlite_rows = oracle.execute_sql(sql_sent)

        c_sql = Counter(sqlite_rows)
        c_pre = Counter(pre_rows)
        c_post = Counter(post_rows)
        passed = c_pre == c_sql and c_post == c_sql
        counter_diff = None
        if not passed:
            counter_diff = {
                version: {
                    "python_only": [list(row) for row in islice((actual - c_sql).elements(), 10)],
                    "sqlite_only": [list(row) for row in islice((c_sql - actual).elements(), 10)],
                }
                for version, actual in (("pre", c_pre), ("post", c_post))
            }
        result = {
            "sql_sent": sql_sent,
            "sqlite_rows": [list(r) for r in sqlite_rows],
            "counter_diff": counter_diff,
            "passed": passed,
            "compared": {"pre": c_pre == c_sql, "post": c_post == c_sql},
        }
        if not passed:
            # A failed check is a result, not a crash — recorded and returned.
            from sql_compiler.errors import ErrorEnvelope

            result["error"] = ErrorEnvelope(
                stage="verify",
                code="VERIFY_MISMATCH",
                message="Plan output does not match SQLite (see counter_diff)",
            ).to_dict()
        return result

    return verify_runner


def _sql_for_sqlite(bound) -> str:
    cols = ", ".join(c.qualified() for c in bound.columns)
    q = f"SELECT {cols} FROM {bound.from_table}"
    if bound.join is not None:
        q += (
            f" JOIN {bound.join.table} "
            f"ON {bound.join.left.qualified()} = {bound.join.right.qualified()}"
        )
    if bound.where:
        q += " WHERE " + " AND ".join(t.label() for t in bound.where)
    return q + ";"


def default_run(sql: str, *, frontend_id: str = "sql", verify: bool = True) -> dict:
    from sql_compiler.pipeline import run_query

    fixture_adapter, registry = default_fixtures()
    return run_query(
        sql,
        registry=registry,
        adapter=fixture_adapter,
        frontend_id=frontend_id,
        verify=verify,
        verify_runner=make_verify_runner(fixture_adapter, source_sql=sql) if verify else None,
    )


def console_run(source: str, *, frontend_id="sql", backend="fixtures", runtime=None, verify: bool = True, browser_safe=True) -> dict:
    """Keep the browser's JSON parser from rounding valid i64 compiler values."""
    from sql_compiler.bundle import new_bundle
    from sql_compiler.errors import ErrorEnvelope
    from sql_compiler.pipeline import run_query

    owned = runtime is None
    runtime = runtime or Runtime(warm_engine=backend == "kb_db")
    try:
        with runtime.backend(backend) as (adapter, registry):
            bundle = run_query(
                source, registry=registry, adapter=adapter, frontend_id=frontend_id,
                prepare=(lambda text: PREPARE["nl"](text, registry=registry, relationships=NL_RELATIONSHIPS))
                    if frontend_id == "nl" else PREPARE.get(frontend_id),
                frontend_lexer=LEXERS.get(frontend_id),
                verify=verify, verify_runner=make_verify_runner(runtime.fixtures, source_sql=source if frontend_id == "sql" else None),
            )
    except Exception as exc:
        bundle = new_bundle(source, frontend_id)
        bundle["provenance"]["backend"] = backend
        bundle["errors"].append(ErrorEnvelope(
            stage=getattr(exc, "stage", "storage"), code=getattr(exc, "code", "INTERNAL"),
            message=str(exc), origin=getattr(exc, "origin", "console"),
        ).to_dict())
    finally:
        if owned: runtime.close()

    if not browser_safe:
        return bundle

    def unsafe(value):
        if type(value) is int:
            return abs(value) > 2**53 - 1
        if isinstance(value, dict):
            return any(unsafe(item) for item in value.values())
        if isinstance(value, list):
            return any(unsafe(item) for item in value)
        return False

    if unsafe(bundle):
        rejected = new_bundle(source, frontend_id)
        rejected["provenance"] = bundle["provenance"]
        rejected["stages"][2]["status"] = "error"
        rejected["errors"] = [ErrorEnvelope(
            stage="bind", code="CONSOLE_INTEGER_PRECISION", origin="console",
            message=(
                "This console supports integers from -9007199254740991 to 9007199254740991. "
                "Use cli.py for full signed 64-bit precision"
            ),
        ).to_dict()]
        return rejected
    return bundle


def workspace(runtime=None) -> dict:
    """Composition-time metadata; never let the browser infer backend state."""
    owned = runtime is None
    session = runtime or Runtime(warm_engine=False)
    try:
        return {
            "v": 1,
            "catalog": session.catalog_snapshot(),
            "backend": session.fixtures.probe(),
            "dataset": session.dataset,
            "datasets": [
                {"id": set_id, "label": meta["label"], "description": meta["description"]}
                for set_id, meta in FIXTURE_SETS.items()
            ],
            "engine": session.engine_status() if runtime else {"available": False, "reason": "Runtime not started"},
            "frontends": [
                {"id": "sql", "label": "SQL", "available": True},
                {"id": "builder", "label": "Visual builder", "available": True},
                {"id": "nl", "label": "Natural language", "available": True},
                {"id": "elastic", "label": "Elastic DSL", "available": True},
            ],
            "supported": SUPPORTED,
            "nl_language": {"version": 1, "parser": "Lark LALR", "relationships": NL_RELATIONSHIPS},
            "examples": FRONTEND_EXAMPLES,
            "presets": PRESETS,
            "initial_bundle": console_run(PRESETS[0]["source"], runtime=runtime),
        }
    finally:
        if owned:
            session.close()


BUILDER_EXAMPLE = {
    "table": "student", "columns": ["student.name", "department.dept_name"],
    "join": {"table": "department", "left": "student.dept_id", "right": "department.id"},
    "filters": [{"column": "student.marks", "op": ">", "value": 80}],
}
DSL_EXAMPLE = {
    "version": 1, "table": "student", "_source": ["student.name", "department.dept_name"],
    "join": BUILDER_EXAMPLE["join"],
    "query": {"bool": {"filter": [{"range": {"student.marks": {"gt": 80}}}]}},
}
FRONTEND_EXAMPLES = {
    "sql": PRESETS[0]["source"], "builder": json.dumps(BUILDER_EXAMPLE, indent=2),
    "nl": "show student names and department names where marks > 80",
    "elastic": json.dumps(DSL_EXAMPLE, indent=2),
}
