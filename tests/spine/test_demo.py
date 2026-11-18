import json
from pathlib import Path
import subprocess
import sys

import pytest

from compose import default_run

ROOT = Path(__file__).resolve().parents[2]


def test_recorded_bundles_are_real_compiler_evidence():
    files = list((ROOT / "demo/bundles").glob("*.json"))
    assert len(files) == 8
    for file in files:
        bundle = json.loads(file.read_text())
        assert bundle["run_schema_version"] == 1
        if bundle["inputs"]["frontend_id"] == "sql":
            reference = default_run(bundle["inputs"]["verbatim"])
            assert bundle["rows"] == reference["rows"]
            assert bundle["metrics"] == reference["metrics"]
        if bundle["rows"] is not None:
            assert bundle["sqlite_cross_check"]["passed"]


def test_nl_replay_can_be_regenerated_without_touching_other_bundles(tmp_path):
    from demo.generate import main
    main(only="nl", directory=tmp_path)
    assert [file.name for file in tmp_path.iterdir()] == ["nl.json"]
    bundle = json.loads((tmp_path / "nl.json").read_text())
    assert bundle["stages"][0]["status"] == "ok"
    assert bundle["stages"][1]["artifact"]["nl_language_version"] == 1
    assert "template_trace" not in bundle["stages"][1]["artifact"]


def test_cli_supports_nl_on_sqlite_without_browser_precision_rules():
    proc = subprocess.run([sys.executable, "cli.py", "show name from student where marks > 80",
        "--frontend", "nl", "--backend", "sqlite", "--json"], cwd=ROOT, text=True, capture_output=True, check=True)
    bundle = json.loads(proc.stdout)
    assert not bundle["errors"]
    assert bundle["rows"]["rows"] == [["Asha"], ["Meera"]]
    assert bundle["provenance"]["backend"] == "sqlite"


def test_cli_nl_walkthrough_shows_native_tokens_and_both_asts():
    proc = subprocess.run([
        sys.executable, "cli.py",
        "show student names and department names and marks where marks > 80",
        "--frontend", "nl",
    ], cwd=ROOT, text=True, capture_output=True, check=True)
    assert "COMMAND(show)" in proc.stdout
    assert "Natural-language AST:" in proc.stdout
    assert "Lowered shared query AST:" in proc.stdout
    assert "('Asha', 'CSE', 91)" in proc.stdout
    assert "Candidate pairs tested: 12 -> 6" in proc.stdout


@pytest.mark.parametrize("backend", ["sqlite"])
def test_cli_keeps_full_i64_literals(backend):
    proc = subprocess.run([sys.executable, "cli.py", "SELECT name FROM student WHERE marks = 9223372036854775807;",
        "--backend", backend, "--json"], cwd=ROOT, text=True, capture_output=True, check=True)
    bundle = json.loads(proc.stdout)
    assert bundle["errors"] == []
    assert bundle["sqlite_cross_check"]["passed"]
