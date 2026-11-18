"""Session-dataset tests: preloaded sets, inserts fanned out to every store,
and validation that never guesses."""
import os
from pathlib import Path

import pytest

from compose import NL_RELATIONSHIPS, Runtime, console_run, make_verify_runner, workspace
from frontends.nl_frontend import prepare
from sql_compiler.pipeline import run_query
from storage.fixtures import FIXTURE_SETS, default_fixtures, open_fixture_set


def test_default_set_is_untouched():
    adapter = default_fixtures()[0]
    assert adapter.probe()["fixture_set"] == "default-v1"
    assert adapter.scan("student").rows[:2] == ((1, "Asha", 91, 10), (2, "Ravi", 80, 20))


def test_classroom_set_is_large_deterministic_and_consistent():
    adapter, registry = open_fixture_set("classroom-60")
    students = adapter.scan("student")
    departments = adapter.scan("department")
    assert len(students.rows) == 60 and len(departments.rows) == 6
    again = open_fixture_set("classroom-60")[0]
    assert again.scan("student").rows == students.rows  # no randomness
    assert len({row[1] for row in students.rows}) == 60  # unique names
    dept_ids = {row[0] for row in departments.rows}
    assert all(row[3] in dept_ids for row in students.rows)  # every FK resolves
    registry.validate_catalog(adapter.open_catalog())


def test_classroom_set_runs_the_shared_pipeline_and_stays_verified():
    adapter, registry = open_fixture_set("classroom-60")
    sql = "SELECT student.name, department.dept_name FROM student JOIN department ON student.dept_id = department.id WHERE student.marks > 80;"
    bundle = run_query(sql, registry=registry, adapter=adapter,
                       verify_runner=make_verify_runner(adapter, source_sql=sql))
    assert not bundle["errors"]
    assert bundle["rows"]["count"] == 23
    assert bundle["metrics"]["join_pairs_tried"] == {"pre": 360, "post": 138}
    assert bundle["sqlite_cross_check"]["passed"]


def test_nl_and_sql_agree_on_the_classroom_set():
    adapter, registry = open_fixture_set("classroom-60")
    prepared = prepare("show student names and department names and marks where marks > 80",
                       registry=registry, relationships=NL_RELATIONSHIPS)
    assert [column.name for column in prepared.ast.columns] == ["name", "dept_name", "marks"]


def test_insert_fans_out_to_fixtures_and_sqlite():
    runtime = Runtime(warm_engine=False)
    try:
        runtime.insert_rows("student", [[5, "Zara", 95, 20]])
        for backend in ["fixtures", "sqlite"]:
            bundle = console_run("SELECT name FROM student WHERE marks > 90;", backend=backend, runtime=runtime)
            assert not bundle["errors"]
            assert bundle["rows"]["rows"] == [["Asha"], ["Zara"]]
            assert bundle["sqlite_cross_check"]["passed"]
    finally:
        runtime.close()


def test_insert_fans_out_to_the_rust_engine_too():
    binary = os.environ.get("KB_DB_BIN")
    if not binary or not Path(binary).is_file():
        pytest.skip("Set KB_DB_BIN for engine insert fan-out")
    runtime = Runtime()
    try:
        runtime.insert_rows("student", [[5, "Zara", 95, 20]])
        bundle = console_run("SELECT name FROM student WHERE marks > 90;", backend="kb_db", runtime=runtime)
        assert not bundle["errors"]
        assert bundle["rows"]["rows"] == [["Asha"], ["Zara"]]
        assert bundle["sqlite_cross_check"]["passed"]
        assert bundle["provenance"]["fixture_set"] == "default-v1"
    finally:
        runtime.close()


def test_reset_restores_the_pristine_dataset_and_switch_sets():
    runtime = Runtime(warm_engine=False)
    try:
        runtime.insert_rows("student", [[5, "Zara", 95, 20]])
        snapshot = runtime.reset()
        assert snapshot["dataset"] == "default-v1"
        student = [table for table in snapshot["catalog"] if table["name"] == "student"][0]
        assert student["row_count"] == 4
        bundle = console_run("SELECT name FROM student WHERE marks > 90;", runtime=runtime)
        assert bundle["rows"]["rows"] == [["Asha"]]  # Zara is gone
        switched = runtime.reset("classroom-60")
        assert switched["dataset"] == "classroom-60"
        assert [table["row_count"] for table in switched["catalog"]] == [60, 6]
    finally:
        runtime.close()


def test_switching_datasets_keeps_all_backends_in_sync():
    runtime = Runtime(warm_engine=False)
    try:
        runtime.reset("classroom-60")
        for backend in ["fixtures", "sqlite"]:
            bundle = console_run("SELECT name FROM student WHERE marks > 96;", backend=backend, runtime=runtime)
            assert not bundle["errors"]
            assert bundle["rows"]["rows"] == [["Vikram Patel"], ["Rohan Nair"]]  # insertion order
    finally:
        runtime.close()


def test_reset_reseeds_the_rust_engine():
    binary = os.environ.get("KB_DB_BIN")
    if not binary or not Path(binary).is_file():
        pytest.skip("Set KB_DB_BIN for engine dataset reset")
    runtime = Runtime()
    try:
        runtime.insert_rows("student", [[99, "Ghost", 1, 10]])
        runtime.reset("classroom-60")
        bundle = console_run("SELECT name FROM student WHERE id = 99;", backend="kb_db", runtime=runtime)
        assert not bundle["errors"]
        assert bundle["rows"]["rows"] == []
        switched = console_run("SELECT name FROM student WHERE marks > 96;", backend="kb_db", runtime=runtime)
        assert switched["rows"]["rows"] == [["Vikram Patel"], ["Rohan Nair"]]
        assert switched["sqlite_cross_check"]["passed"]
    finally:
        runtime.close()


def test_insert_validation_never_guesses():
    runtime = Runtime(warm_engine=False)
    try:
        with pytest.raises(KeyError):
            runtime.insert_rows("ghost", [[1, "x"]])
        with pytest.raises(ValueError):
            runtime.insert_rows("student", [[5, "Zara", 95]])
        with pytest.raises(ValueError):
            runtime.insert_rows("student", [[5, "Zara", 95.5, 20]])
        with pytest.raises(ValueError):
            runtime.insert_rows("student", [[5, "Zara", True, 20]])
        with pytest.raises(ValueError):
            runtime.insert_rows("student", [[5, "Zara", 2**63, 20]])
        with pytest.raises(ValueError):
            runtime.reset("nope")
        # A rejected batch must not partially mutate the session data.
        assert len(runtime.fixtures.scan("student").rows) == 4
    finally:
        runtime.close()


def test_workspace_reports_dataset_choices_and_row_counts():
    runtime = Runtime(warm_engine=False)
    try:
        data = workspace(runtime)
        assert data["dataset"] == "default-v1"
        assert [item["id"] for item in data["datasets"]] == list(FIXTURE_SETS)
        assert [table["row_count"] for table in data["catalog"]] == [4, 3]
        runtime.reset("classroom-60")
        assert workspace(runtime)["dataset"] == "classroom-60"
    finally:
        runtime.close()


def test_default_run_stays_on_the_immutable_default_fixtures():
    """Replay bundles and CLI defaults never see session data."""
    runtime = Runtime(warm_engine=False)
    try:
        runtime.insert_rows("student", [[5, "Zara", 95, 20]])
        bundle = console_run("SELECT name FROM student WHERE marks > 90;", runtime=runtime)
        assert [row[0] for row in bundle["rows"]["rows"]] == ["Asha", "Zara"]
    finally:
        runtime.close()
    from compose import default_run
    assert default_run("SELECT name FROM student WHERE marks > 90;")["rows"]["rows"] == [["Asha"]]
