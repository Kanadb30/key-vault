"""Snapshot semantic bundle evidence, excluding clocks and source layout."""
import json
from pathlib import Path

from compose import default_run

SNAPSHOTS = Path(__file__).with_name("snapshots")


def test_join_bundle_evidence(join_sql):
    bundle = default_run(join_sql)
    keys = ("plans_ascii", "plan_diff", "rows", "metrics", "sqlite_cross_check", "errors")
    evidence = {key: bundle[key] for key in keys}
    expected = json.loads((SNAPSHOTS / "join.json").read_text())
    assert evidence == expected


def test_starter_plan_snapshot():
    bundle = default_run("SELECT name FROM student WHERE marks > 80;")
    assert bundle["plans_ascii"] == {
        "pre": "Project(name)\n└── Filter(student.marks > 80)\n    └── Scan(student)",
        "post": "Project(name)\n└── Filter(student.marks > 80)\n    └── Scan(student)",
    }
    assert bundle["rows"] == {"columns": ["name"], "rows": [["Asha"], ["Meera"]], "count": 2}
    assert bundle["sqlite_cross_check"]["passed"]
