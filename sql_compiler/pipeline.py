"""SQL stages → one QueryRun bundle (docs/bundle_schema.md).

Interface: run_query(sql, *, registry, adapter, verify_runner=None, verify=True).
Storage and the verifier are injected; this package imports core only.
Invariants: both plans execute, counters are fresh, failures become envelopes,
and no browser code needs to re-create compiler artifacts.
Side effects: adapter probes/catalog/scans and the injected verifier.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import time

from core.types import SchemaRegistry
from .ast_nodes import render_ast
from .binder import bind
from .bundle import json_value, new_bundle, token_artifact
from .errors import CompilerError, ErrorEnvelope
from .exec import execute
from .parser import SQLParser
from .plan import build_plan, plan_to_json, render_ascii
from .pushdown import apply_pushdown


class _Pipeline:
    def __init__(self) -> None:
        self._parser = SQLParser()

    def run_query(
        self,
        sql: str,
        *,
        registry: SchemaRegistry,
        adapter,
        frontend_id: str = "sql",
        verify: bool = True,
        verify_runner=None,
        prepare=None,
        frontend_lexer=None,
    ) -> dict:
        bundle = new_bundle(sql, frontend_id)
        stages = {rec["name"]: rec for rec in bundle["stages"]}

        @contextmanager
        def stage(name: str):
            rec = stages[name]
            rec["status"] = "ok"
            started = time.perf_counter_ns()
            try:
                yield rec
            except CompilerError as exc:
                rec["status"] = "error"
                rec["artifact"].update(getattr(exc, "artifact", {}))
                raise
            except Exception as exc:
                rec["status"] = "error"
                if getattr(exc, "diagnostics", None):
                    bundle["bridge_diagnostics"] = exc.diagnostics
                raise CompilerError(ErrorEnvelope(
                    stage=getattr(exc, "stage", name), code=getattr(exc, "code", "INTERNAL"),
                    origin=getattr(exc, "origin", "sql_compiler"), message=f"{type(exc).__name__}: {exc}",
                )) from exc
            finally:
                rec["timing_ms"] = (time.perf_counter_ns() - started) / 1e6

        try:
            try:
                metadata = adapter.probe()
                if not metadata.get("available", False):
                    raise ValueError("storage backend is unavailable")
                bundle["provenance"].update({
                    "backend": metadata.get("backend", "unknown"),
                    "engine_commit": metadata.get("engine_commit"),
                    "fixture_set": metadata.get("fixture_set"),
                    "protocol": metadata.get("protocol"),
                })
            except Exception as exc:
                raise CompilerError(ErrorEnvelope(
                    stage="storage", code="INTERNAL", message=f"{type(exc).__name__}: {exc}",
                )) from exc

            if prepare is None:
                with stage("lex") as st:
                    tokens = self._parser.tokenize(sql)
                    st["artifact"] = {
                        "token_count": len(tokens),
                        "tokens": [token_artifact(token) for token in tokens],
                    }
                    bundle["inputs"]["normalized"] = " ".join(str(token) for token in tokens)
            elif frontend_lexer:
                with stage("lex") as st:
                    tokens = frontend_lexer(sql)
                    st["artifact"] = {"token_count": len(tokens), "tokens": tokens, "language": frontend_id}
            else:
                stages["lex"]["artifact"] = {"reason": "Frontend conversion is recorded in the parse stage"}

            with stage("parse") as st:
                prepared = prepare(sql) if prepare else None
                select_ast = prepared.ast if prepared else self._parser.parse(sql)
                st["artifact"] = {"ast": render_ast(select_ast), "tree": json_value(select_ast)}
                if prepared:
                    st["artifact"].update(prepared.artifact)
                    bundle["inputs"]["generated_sql"] = prepared.sql
                    bundle["inputs"]["normalized"] = prepared.sql

            with stage("bind") as st:
                bound = bind(select_ast, registry)
                scope = [bound.from_table] + ([bound.join.table] if bound.join else [])
                st["artifact"] = {"tables_in_scope": sorted(scope), "bound": json_value(bound)}

            with stage("plan") as st:
                plan = build_plan(bound)
                st["artifact"] = {"root": plan.operator, "plan": plan_to_json(plan)}

            with stage("optimize") as st:
                pre_plan, post_plan, moved = apply_pushdown(plan)
                bundle["plans"] = {"pre": plan_to_json(pre_plan), "post": plan_to_json(post_plan)}
                bundle["plans_ascii"] = {
                    key: "\n".join(render_ascii(tree)) for key, tree in bundle["plans"].items()
                }
                bundle["plan_diff"] = moved
                st["artifact"] = {"moved_terms": len(moved), "diff": moved}

            with stage("execute") as st:
                registry.validate_catalog(adapter.open_catalog())
                pre_exec = execute(pre_plan, adapter, registry)
                post_exec = execute(post_plan, adapter, registry)
                bundle["node_stats"] = {
                    "pre": [s.to_dict() for s in pre_exec.stats],
                    "post": [s.to_dict() for s in post_exec.stats],
                }
                bundle["rows"] = {
                    "columns": post_exec.columns,
                    "rows": [list(row) for row in post_exec.rows],
                    "count": len(post_exec.rows),
                }
                pre_join, post_join = pre_exec.stat("Join"), post_exec.stat("Join")
                bundle["metrics"] = {
                    field: {
                        "pre": getattr(pre_join, field) if pre_join else None,
                        "post": getattr(post_join, field) if post_join else None,
                    }
                    for field in ("join_pairs_tried", "join_pairs_matched", "left_in", "right_in")
                }
                bundle["metrics"]["rows_out"] = {"pre": len(pre_exec.rows), "post": len(post_exec.rows)}
                st["artifact"] = {
                    "pre_rows": json_value(pre_exec.rows),
                    "post_rows": json_value(post_exec.rows),
                }
                if Counter(pre_exec.rows) != Counter(post_exec.rows):
                    raise CompilerError(ErrorEnvelope(
                        stage="execute", code="VERIFY_MISMATCH",
                        message="Pushdown changed the result multiset",
                    ))

            if verify and verify_runner is not None:
                with stage("verify") as st:
                    check = verify_runner(bound, pre_exec.rows, post_exec.rows)
                    bundle["sqlite_cross_check"] = check
                    st["artifact"] = check
                    if not check["passed"]:
                        raise CompilerError(ErrorEnvelope(
                            stage="verify", code="VERIFY_MISMATCH",
                            message="Plan output does not match SQLite (see counter_diff)",
                        ))
            else:
                stages["verify"]["artifact"] = {
                    "reason": "verification disabled" if not verify else "no verify_runner wired",
                }
        except CompilerError as exc:
            bundle["errors"].append(exc.envelope.to_dict())
        return bundle


_pipeline = _Pipeline()


def run_query(sql: str, **kwargs) -> dict:
    return _pipeline.run_query(sql, **kwargs)
