import json

import pytest

from compose import BUILDER_EXAMPLE, DSL_EXAMPLE, FRONTEND_EXAMPLES, NL_RELATIONSHIPS, console_run
from frontends.common import normalized_ast
from frontends.registry import PREPARE
from sql_compiler.parser import SQLParser


def test_four_frontends_produce_identical_ast_and_plans(fixtures):
    baseline = normalized_ast(SQLParser().parse(FRONTEND_EXAMPLES["sql"]))
    reference = console_run(FRONTEND_EXAMPLES["sql"])
    for name, prepare in PREPARE.items():
        ast = (prepare(FRONTEND_EXAMPLES[name], registry=fixtures[1], relationships=NL_RELATIONSHIPS)
               if name == "nl" else prepare(FRONTEND_EXAMPLES[name])).ast
        assert normalized_ast(ast) == baseline
        bundle = console_run(FRONTEND_EXAMPLES[name], frontend_id=name)
        assert bundle["errors"] == []
        assert bundle["plans"] == reference["plans"]
        assert bundle["rows"] == reference["rows"]
        assert bundle["sqlite_cross_check"]["passed"]


def test_ast_equivalence_normalizes_identifiers_not_string_values():
    parser = SQLParser()
    upper = parser.parse("select NAME from STUDENT where NAME = 'Asha';")
    lower = parser.parse("SELECT name FROM student WHERE name = 'Asha';")
    assert normalized_ast(upper) == normalized_ast(lower)
    assert normalized_ast(upper)["where"][0]["literal"]["value"] == "Asha"


@pytest.mark.parametrize("name", ["select", "student.department"])
def test_invalid_builder_table_retains_native_locator(name):
    bundle = console_run(json.dumps({**BUILDER_EXAMPLE, "table": name}), frontend_id="builder")
    assert bundle["errors"][0]["code"] == "FRONTEND_INVALID_IDENTIFIER"
    assert bundle["errors"][0]["locator"]["kind"] == "builder_node"


@pytest.mark.parametrize("frontend", ["builder", "nl", "elastic"])
def test_non_sql_ast_nodes_keep_native_locators(frontend, fixtures):
    prepared = (PREPARE[frontend](FRONTEND_EXAMPLES[frontend], registry=fixtures[1], relationships=NL_RELATIONSHIPS)
                if frontend == "nl" else PREPARE[frontend](FRONTEND_EXAMPLES[frontend]))
    expected = {"builder": "builder_node", "nl": "nl_span", "elastic": "json_pointer"}[frontend]
    assert prepared.ast.columns[0].locator.kind == expected
    assert prepared.ast.where[0].literal.locator.kind == expected


@pytest.mark.parametrize(("entry", "code"), [
    ({"wildcard": {"name": "*"}}, "DSL_UNSUPPORTED_OPERATOR"),
    ({"bool": {"filter": []}}, "DSL_UNSUPPORTED_OPERATOR"),
    ({"term": {"marks": True}}, "DSL_TYPE_MISMATCH"),
    ({"term": {"marks": None}}, "DSL_TYPE_MISMATCH"),
    ({"term": {"marks": 1.5}}, "DSL_TYPE_MISMATCH"),
    ({"range": {"marks": {"gt": "80"}}}, "DSL_TYPE_MISMATCH"),
    ({"range": {"marks": {"invalid": 80}}}, "DSL_TYPE_MISMATCH"),
])
def test_dsl_rejections_have_paths(entry, code):
    document = {**DSL_EXAMPLE, "query": {"bool": {"filter": [entry]}}}
    bundle = console_run(json.dumps(document), frontend_id="elastic")
    assert bundle["errors"][0]["code"] == code
    assert bundle["errors"][0]["locator"]["pointer"].startswith("$.query.bool.filter[0]")


def test_dsl_text_range_fails_at_shared_binder_with_json_path():
    data = {**DSL_EXAMPLE, "query": {"bool": {"filter": [{"range": {"student.name": {"gt": 80}}}]}}}
    bundle = console_run(json.dumps(data), frontend_id="elastic")
    assert bundle["errors"][0]["code"] == "BIND_TYPE_MISMATCH"
    assert bundle["errors"][0]["locator"]["kind"] == "json_pointer"


def test_dsl_should_is_not_silently_dropped():
    bundle = console_run(json.dumps({**DSL_EXAMPLE, "query": {"bool": {"should": []}}}), frontend_id="elastic")
    assert bundle["errors"][0]["code"] == "DSL_UNSUPPORTED_OPERATOR"
    assert bundle["errors"][0]["locator"]["pointer"] == "$.query.bool.should"


def test_nl_invalid_command_has_a_real_parse_diagnostic():
    bundle = console_run("delete everything", frontend_id="nl")
    assert bundle["errors"][0]["code"] == "NL_PARSE_UNEXPECTED_TOKEN"
    assert bundle["errors"][0]["locator"]["kind"] == "nl_span"
    assert bundle["stages"][0]["artifact"]["tokens"][0]["value"] == "delete"


def test_nl_success_records_lexer_ast_and_lowering_not_templates():
    bundle = console_run(FRONTEND_EXAMPLES["nl"], frontend_id="nl")
    assert bundle["stages"][0]["status"] == "ok"
    artifact = bundle["stages"][1]["artifact"]
    assert artifact["nl_ast"]["command"] == "show"
    assert artifact["nl_lowering"]["join"]["source"] == "declared relationship"
    assert "template_trace" not in artifact


def test_builder_unknown_column_points_to_builder_field():
    bundle = console_run(json.dumps({**BUILDER_EXAMPLE, "columns": ["grade"]}), frontend_id="builder")
    assert bundle["errors"][0]["locator"] == {"kind": "builder_node", "node_id": "columns"}


def test_builder_quotes_text_without_injection():
    data = {"table": "student", "columns": ["name"], "filters": [{"column": "name", "op": "=", "value": "O'Brien'; DROP TABLE student;"}]}
    bundle = console_run(json.dumps(data), frontend_id="builder")
    assert not bundle["errors"]
    assert bundle["rows"]["rows"] == []
    assert bundle["sqlite_cross_check"]["passed"]


@pytest.mark.parametrize("source", ["[]", "{", '{"table":false}', '{"version":1}'])
def test_invalid_frontend_documents_never_escape(source):
    for frontend in ["builder", "elastic"]:
        bundle = console_run(source, frontend_id=frontend)
        assert bundle["errors"]
        json.dumps(bundle)
