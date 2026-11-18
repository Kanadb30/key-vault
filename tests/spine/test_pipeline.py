import json
from pathlib import Path
import subprocess
import sys

import pytest

from compose import default_run, make_verify_runner
from sql_compiler.binder import bind
from sql_compiler.errors import ErrorEnvelope, caret_line, format_error, STAGES
from sql_compiler.pipeline import run_query

ROOT = Path(__file__).resolve().parents[2]


def test_parse_error_snapshot():
    bundle = default_run("SELECT FROM student;")
    env = ErrorEnvelope(**bundle["errors"][0])
    assert format_error(env) == "Parse error at 1:8. Unexpected token 'FROM'. Expected one of: IDENT."
    assert caret_line("SELECT FROM student;", env) == "SELECT FROM student;\n       ^"
    assert [stage["status"] for stage in bundle["stages"]] == [
        "ok", "error", "skipped", "skipped", "skipped", "skipped", "skipped",
    ]
    assert bundle["rows"] is None


def test_semantic_error_exactly_matches_proposal():
    sql = "SELECT grade FROM student;"
    bundle = default_run(sql)
    env = ErrorEnvelope(**bundle["errors"][0])
    assert format_error(env) == "Semantic error at 1:8. Unknown column 'grade' in table 'student'."
    assert caret_line(sql, env) == sql + "\n       ^"
    assert env.locator["char_start"] == 7
    assert [stage["status"] for stage in bundle["stages"]] == [
        "ok", "ok", "error", "skipped", "skipped", "skipped", "skipped",
    ]


def test_invalid_character_fails_at_lex():
    bundle = default_run("SELECT @ FROM student;")
    assert bundle["errors"][0]["stage"] == "lex"
    assert bundle["stages"][0]["status"] == "error"
    assert all(stage["status"] == "skipped" for stage in bundle["stages"][1:])


@pytest.mark.parametrize("sql", [
    "SELECT name FROM student WHERE marks > 80;",
    "SELECT grade FROM student;", "SELECT FROM student;", "", "SELECT @ FROM student;",
])
def test_bundle_shape_and_json_round_trip(sql):
    bundle = default_run(sql)
    assert json.loads(json.dumps(bundle, allow_nan=False)) == bundle
    assert bundle["run_schema_version"] == 1
    assert [stage["name"] for stage in bundle["stages"]] == list(STAGES)
    assert all(stage["timing_ms"] >= 0 for stage in bundle["stages"])
    assert bundle["provenance"] == {
        "backend": "fixtures", "engine_commit": None,
        "fixture_set": "default-v1", "protocol": None,
    }


def test_artifacts_include_tokens_structured_ast_and_bound_refs():
    bundle = default_run("SELECT name FROM student;")
    stages = {stage["name"]: stage["artifact"] for stage in bundle["stages"]}
    assert stages["lex"]["tokens"][1]["value"] == "name"
    assert stages["parse"]["tree"]["columns"][0]["locator"]["col"] == 8
    assert stages["bind"]["bound"]["columns"][0] == {
        "table": "student", "column": "name", "type": "TEXT",
    }
    assert stages["execute"]["pre_rows"] == stages["execute"]["post_rows"]


def test_normalization_does_not_change_string_contents():
    source = "SELECT  name  FROM student WHERE name = 'Asha  Kumari';"
    bundle = default_run(source)
    assert "'Asha  Kumari'" in bundle["inputs"]["normalized"]
    assert bundle["sqlite_cross_check"]["sql_sent"] == source


def test_verification_can_be_disabled():
    bundle = default_run("SELECT name FROM student;", verify=False)
    assert bundle["errors"] == []
    assert bundle["sqlite_cross_check"] is None
    assert bundle["stages"][-1]["status"] == "skipped"
    assert bundle["stages"][-1]["artifact"]["reason"] == "verification disabled"


def test_verifier_is_order_insensitive_but_duplicate_sensitive(parser, fixtures):
    adapter, registry = fixtures
    bound = bind(parser.parse("SELECT name FROM student;"), registry)
    verify = make_verify_runner(adapter)
    expected = [("Asha",), ("Ravi",), ("Meera",), ("Kabir",)]
    assert verify(bound, expected[::-1], expected)["passed"]
    mismatch = verify(bound, expected, expected + [("Asha",)])
    assert mismatch["compared"] == {"pre": True, "post": False}
    assert mismatch["counter_diff"] == {
        "pre": {"python_only": [], "sqlite_only": []},
        "post": {"python_only": [["Asha"]], "sqlite_only": []},
    }


def test_verification_failure_marks_stage_and_returns_envelope(fixtures):
    adapter, registry = fixtures
    def mismatch(*args):
        return {"passed": False, "counter_diff": {"post": "extra row"}}
    bundle = run_query("SELECT name FROM student;", adapter=adapter, registry=registry, verify_runner=mismatch)
    assert bundle["stages"][-1]["status"] == "error"
    assert bundle["errors"][0]["code"] == "VERIFY_MISMATCH"
    assert bundle["rows"]["count"] == 4
    assert not bundle["sqlite_cross_check"]["passed"]


def test_backend_failures_never_escape_the_boundary(fixtures):
    adapter, registry = fixtures
    adapter.scan = lambda _: (_ for _ in ()).throw(OSError("disk unavailable"))
    bundle = run_query("SELECT name FROM student;", adapter=adapter, registry=registry)
    assert bundle["errors"][0]["stage"] == "execute"
    assert bundle["errors"][0]["message"] == "OSError: disk unavailable"
    assert bundle["plans"] is not None
    assert bundle["rows"] is None
    assert bundle["stages"][-1]["status"] == "skipped"
    json.dumps(bundle)


def test_probe_failure_is_an_envelope(fixtures):
    adapter, registry = fixtures
    adapter.probe = lambda: (_ for _ in ()).throw(OSError("engine absent"))
    bundle = run_query("SELECT name FROM student;", adapter=adapter, registry=registry)
    assert bundle["errors"][0]["stage"] == "storage"
    assert all(stage["status"] == "skipped" for stage in bundle["stages"])


def test_backend_catalog_must_match_the_registry(fixtures):
    adapter, registry = fixtures
    adapter.create_table("unexpected", registry.table("department").columns)
    bundle = run_query("SELECT name FROM student;", adapter=adapter, registry=registry)
    assert bundle["errors"][0]["stage"] == "execute"
    assert "backend catalog" in bundle["errors"][0]["message"]


def test_cli_walkthrough(join_sql):
    proc = subprocess.run(
        [sys.executable, "cli.py", join_sql], cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert proc.stderr == ""
    for evidence in (
        "Tokens:", "AST:", "Scan(student)", "Filter(student.marks > 80)",
        "left_in: 4 -> 2", "Candidate pairs tested: 12 -> 6",
        "('Asha', 'CSE')", "('Meera', 'ECE')", "SQLite cross-check: PASSED",
    ):
        assert evidence in proc.stdout


def test_cli_error_json_is_valid():
    proc = subprocess.run(
        [sys.executable, "cli.py", "SELECT FROM student;", "--json"],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    assert json.loads(proc.stdout)["errors"][0]["code"] == "PARSE_UNEXPECTED_TOKEN"
    assert proc.stderr == ""
