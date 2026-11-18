"""CLI walkthrough — the graded fallback artifact (README §5 demo script).

Usage: uv run python cli.py "SELECT ..." [--json] [--no-caret]

Invariants: pretty output mirrors the proposal's walkthrough (AST summary,
both plans as ASCII trees, per-node counts pre → post, rows, SQLite check);
errors render README-style with a caret under the offending column; --json
prints the bundle verbatim.
Side effects: prints to stdout. Exit code 0 even for handled error envelopes
(they are results); non-zero only on misuse.
"""
from __future__ import annotations

import argparse
import json
import sys

from compose import default_run, console_run
from sql_compiler.errors import ErrorEnvelope, caret_line, format_error


def _print_errors(bundle: dict, sql: str, caret: bool) -> None:
    for env in bundle.get("errors") or []:
        envelope = ErrorEnvelope(
            stage=env.get("stage", "internal"),
            code=env.get("code", "INTERNAL"),
            message=env.get("message", ""),
            locator=env.get("locator"),
            origin=env.get("origin", "sql_compiler"),
        )
        if caret:
            rendered = caret_line(sql, envelope)
            if rendered:
                print(rendered)
        print(format_error(envelope))


def _print_stages(bundle: dict) -> None:
    stages = bundle.get("stages") or []
    parts = [f"{s['name']}({s['status']}, {s['timing_ms']:.2f}ms)" for s in stages]
    print("Stages: " + " → ".join(parts))
    lex_artifact = next((s["artifact"] for s in stages if s["name"] == "lex"), {})
    if lex_artifact.get("tokens"):
        print("\nTokens:")
        print("  " + " ".join(f"{t['type']}({t['value']})" for t in lex_artifact["tokens"]))
    parse_artifact = next(
        (s.get("artifact", {}) for s in stages if s["name"] == "parse" and isinstance(s.get("artifact"), dict)),
        {},
    )
    if "ast" in parse_artifact:
        if "nl_ast_text" in parse_artifact:
            print("\nNatural-language AST:")
            print(parse_artifact["nl_ast_text"])
            print("\nLowered shared query AST:")
        else:
            print("\nAST:")
        print(parse_artifact["ast"])


def _print_plans(bundle: dict) -> None:
    plans = bundle.get("plans") or {}
    diff = bundle.get("plan_diff") or []
    if not plans:
        return
    print("\nPlan (before pushdown):")
    print(bundle["plans_ascii"]["pre"])
    print("\nPlan (after pushdown):")
    print(bundle["plans_ascii"]["post"])
    if diff:
        print("\nPushdown diff (emitted as data):")
        for rec in diff:
            if rec["target"] == "kept":
                print(f"  {rec['term_id']} kept above the join: {rec['term']}")
            else:
                print(
                    f"  {rec['term_id']} moved {rec['target']}: {rec['term']} "
                    f"(node {rec['from_node_id']} -> node {rec['to_node_id']})"
                )


def _print_stats(bundle: dict) -> None:
    node_stats = bundle.get("node_stats") or {}
    if not node_stats:
        return
    pre_by_id = {s["node_id"]: s for s in node_stats["pre"]}
    post_by_id = {s["node_id"]: s for s in node_stats["post"]}
    print("\nPer-node counts (pre -> post):")
    for node_id in sorted(set(pre_by_id) | set(post_by_id)):
        pre = pre_by_id.get(node_id)
        post = post_by_id.get(node_id)
        if not pre or not post:
            continue
        parts = [f"{pre['operator']}({pre['label']})"]
        fields = ("rows_in", "left_in", "right_in", "rows_out")
        if pre["operator"] == "Join":
            fields += ("join_pairs_tried", "join_pairs_matched")
        for field in fields:
            pv, pt = pre.get(field), post.get(field)
            if pv is None and pt is None:
                continue
            parts.append(f"{field}: {pv} -> {pt}" if pv != pt else f"{field}: {pv}")
        print("  " + "; ".join(parts))
    metrics = bundle.get("metrics") or {}
    jpt = metrics.get("join_pairs_tried") or {}
    if jpt.get("pre") is not None:
        print(f"\nCandidate pairs tested: {jpt['pre']} -> {jpt['post']}")


def _print_rows(bundle: dict) -> None:
    rows = bundle.get("rows") or {}
    if not rows:
        return
    print(f"\nRows ({rows['count']}):")
    for row in rows["rows"]:
        print("  (" + ", ".join(_cell(v) for v in row) + ")")


def _cell(value) -> str:
    return f"'{value}'" if isinstance(value, str) else str(value)


def _print_verify(bundle: dict) -> None:
    check = bundle.get("sqlite_cross_check")
    if not check:
        return
    status = "PASSED" if check.get("passed") else "FAILED"
    print(f"\nSQLite cross-check: {status}")
    print(f"  {check.get('sql_sent')}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sql_compiler", description="SQL query compiler demo CLI")
    ap.add_argument("sql", help="SQL text to compile and execute")
    ap.add_argument("--json", action="store_true", help="print the QueryRun bundle instead")
    ap.add_argument("--no-caret", action="store_true", help="omit the caret line for errors")
    ap.add_argument("--frontend", choices=["sql", "builder", "nl", "elastic"], default="sql")
    ap.add_argument("--backend", choices=["fixtures", "sqlite", "kb_db"], default="fixtures")
    args = ap.parse_args(argv)

    bundle = (default_run(args.sql) if args.frontend == "sql" and args.backend == "fixtures"
              else console_run(args.sql, frontend_id=args.frontend, backend=args.backend, browser_safe=False))

    if args.json:
        json.dump(bundle, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if bundle.get("errors"):
        _print_errors(bundle, args.sql, not args.no_caret)
        return 0

    _print_stages(bundle)
    _print_plans(bundle)
    _print_stats(bundle)
    _print_rows(bundle)
    _print_verify(bundle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
