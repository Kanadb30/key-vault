from collections import Counter

import pytest

from compose import default_run, make_verify_runner
from sql_compiler.binder import bind
from sql_compiler.exec import execute
from sql_compiler.pipeline import run_query
from sql_compiler.plan import build_plan, plan_to_json
from sql_compiler.pushdown import apply_pushdown


def test_demo_counts_and_results(join_sql):
    bundle = default_run(join_sql)
    assert bundle["errors"] == []
    assert bundle["rows"] == {
        "columns": ["name", "dept_name"],
        "rows": [["Asha", "CSE"], ["Meera", "ECE"]],
        "count": 2,
    }
    assert bundle["metrics"]["join_pairs_tried"] == {"pre": 12, "post": 6}
    assert bundle["metrics"]["left_in"] == {"pre": 4, "post": 2}
    assert bundle["metrics"]["right_in"] == {"pre": 3, "post": 3}
    assert bundle["sqlite_cross_check"]["compared"] == {"pre": True, "post": True}


def test_pushdown_is_pure_and_node_ids_are_stable(parser, fixtures, join_sql):
    plan = build_plan(bind(parser.parse(join_sql), fixtures[1]))
    original = plan_to_json(plan)
    pre, post, moved = apply_pushdown(plan)
    assert plan_to_json(plan) == original == plan_to_json(pre)
    assert pre is not post and pre.child is not post.child
    assert post.node_id == pre.node_id == 5
    assert post.child.node_id == 3  # surviving Join
    assert post.child.left.child.node_id == 1  # surviving Scan
    assert moved == [{
        "term_id": "term#1", "term": "student.marks > 80", "target": "left",
        "from_node_id": 4, "to_node_id": 6,
    }]
    assert plan_to_json(apply_pushdown(post)[1]) == plan_to_json(post)


def test_filters_push_to_both_sides_and_keep_term_ids(join_sql):
    bundle = default_run(join_sql[:-1] + " AND department.dept_name <> 'ECE' AND student.id >= 1;")
    assert not bundle["errors"]
    assert bundle["rows"]["rows"] == [["Asha", "CSE"]]
    assert bundle["metrics"]["join_pairs_tried"] == {"pre": 12, "post": 4}
    assert [(item["term_id"], item["target"]) for item in bundle["plan_diff"]] == [
        ("term#1", "left"), ("term#2", "right"), ("term#3", "left"),
    ]


def test_no_where_means_no_rewrite(join_sql):
    bundle = default_run(join_sql.split(" WHERE")[0] + ";")
    assert bundle["plans"]["pre"] == bundle["plans"]["post"]
    assert bundle["plan_diff"] == []
    assert bundle["metrics"]["join_pairs_tried"] == {"pre": 12, "post": 12}


def test_empty_filtered_input_does_zero_join_work(join_sql):
    bundle = default_run(join_sql.replace("> 80", "> 100"))
    assert bundle["rows"]["rows"] == []
    assert bundle["metrics"]["join_pairs_tried"] == {"pre": 12, "post": 0}
    assert bundle["sqlite_cross_check"]["passed"]


@pytest.mark.parametrize(("op", "expected"), [
    ("=", ["Ravi"]), ("<>", ["Asha", "Meera", "Kabir"]),
    (">", ["Asha", "Meera"]), (">=", ["Asha", "Ravi", "Meera"]),
    ("<", ["Kabir"]), ("<=", ["Ravi", "Kabir"]),
])
def test_six_integer_comparisons(op, expected):
    bundle = default_run(f"SELECT name FROM student WHERE marks {op} 80;")
    assert not bundle["errors"]
    assert bundle["rows"]["rows"] == [[name] for name in expected]
    assert bundle["sqlite_cross_check"]["passed"]


@pytest.mark.parametrize(("op", "expected"), [
    ("=", [["Asha"]]), ("<>", [["Ravi"], ["Meera"], ["Kabir"]]),
])
def test_text_comparisons(op, expected):
    bundle = default_run(f"SELECT name FROM student WHERE name {op} 'Asha';")
    assert bundle["rows"]["rows"] == expected
    assert bundle["sqlite_cross_check"]["passed"]


def test_duplicates_survive_scan_filter_join_project(parser, fixtures, join_sql):
    adapter, registry = fixtures
    adapter.insert_rows("student", [(1, "Asha", 91, 10)])
    adapter.insert_rows("department", [(10, "CSE")])
    bundle = run_query(
        join_sql, adapter=adapter, registry=registry,
        verify_runner=make_verify_runner(adapter),
    )
    assert not bundle["errors"]
    assert Counter(map(tuple, bundle["rows"]["rows"])) == Counter({
        ("Asha", "CSE"): 4, ("Meera", "ECE"): 1,
    })
    assert bundle["sqlite_cross_check"]["passed"]


def test_repeated_execution_does_not_accumulate_stats(parser, fixtures, join_sql):
    adapter, registry = fixtures
    plan = build_plan(bind(parser.parse(join_sql), registry))
    first = execute(plan, adapter, registry)
    second = execute(plan, adapter, registry)
    assert first.stat("Join").join_pairs_tried == second.stat("Join").join_pairs_tried == 12
    assert first.stat("Join") is not second.stat("Join")


def test_duplicate_projection_labels_are_qualified():
    sql = "SELECT student.id, department.id FROM student JOIN department ON student.dept_id = department.id;"
    bundle = default_run(sql)
    assert bundle["rows"]["columns"] == ["student.id", "department.id"]
    assert bundle["sqlite_cross_check"]["passed"]
