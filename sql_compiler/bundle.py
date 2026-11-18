"""JSON-only compiler artifacts. No storage or presentation recomputation.

Interface: new_bundle(), json_value(), token_artifact().
Invariants: all seven stages exist, unrun stages are skipped, locators survive.
Side effects: none.
"""
from __future__ import annotations

from dataclasses import fields, is_dataclass

from . import __version__
from .ast_nodes import Locator
from .errors import STAGES


def json_value(value):
    if isinstance(value, Locator):
        return value.to_dict()
    if is_dataclass(value):
        return {field.name: json_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    return value


def token_artifact(token) -> dict:
    return {
        "type": token.type,
        "value": str(token),
        "locator": {
            "kind": "sql_span",
            "char_start": token.start_pos,
            "char_end": token.end_pos,
            "line": token.line,
            "col": token.column,
            "end_line": token.end_line,
            "end_col": token.end_column,
        },
    }


def new_bundle(source: str, frontend_id: str) -> dict:
    return {
        "run_schema_version": 1,
        "compiler_version": __version__,
        "inputs": {"frontend_id": frontend_id, "verbatim": source, "normalized": source},
        "stages": [
            {"name": name, "status": "skipped", "timing_ms": 0.0, "artifact": {}}
            for name in STAGES
        ],
        "plans": None,
        "plans_ascii": None,
        "plan_diff": [],
        "node_stats": None,
        "rows": None,
        "metrics": None,
        "errors": [],
        "sqlite_cross_check": None,
        "provenance": {
            "backend": "unknown",
            "engine_commit": None,
            "fixture_set": None,
            "protocol": None,
        },
    }
