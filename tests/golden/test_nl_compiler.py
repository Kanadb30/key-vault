"""Grammar and semantic tests, not a whitelist of accepted sentences."""
from dataclasses import fields, is_dataclass
import pytest

from compose import NL_RELATIONSHIPS, console_run, make_verify_runner
from core.types import Column, SchemaRegistry, TableSchema
from frontends import nl_ast as nl
from frontends.common import normalized_ast
from frontends.nl_frontend import prepare
from frontends.nl_parser import NLParser
from sql_compiler.ast_nodes import NlSpan
from sql_compiler.errors import CompilerError
from sql_compiler.parser import SQLParser
from sql_compiler.pipeline import run_query
from storage.fixtures import FixtureAdapter

USER_QUERY = "show student names and department names and marks where marks > 80"


def test_user_sentence_with_an_extra_projection_works():
    bundle = console_run(USER_QUERY, frontend_id="nl")
    assert bundle["errors"] == []
    assert bundle["rows"] == {
        "columns": ["name", "dept_name", "marks"],
        "rows": [["Asha", "CSE", 91], ["Meera", "ECE", 86]], "count": 2,
    }
    assert bundle["metrics"]["join_pairs_tried"] == {"pre": 12, "post": 6}
    assert bundle["sqlite_cross_check"]["passed"]


@pytest.mark.parametrize("command", ["show", "list", "display", "get", "find", "give me", "fetch", "select"])
@pytest.mark.parametrize("comparison", ["> 80", "above 80", "over 80", "greater than 80", "more than 80", "is greater than 80", "are above 80"])
def test_independent_grammar_productions_compose(command, comparison):
    bundle = console_run(
        f"{command} student names, department names and marks where marks {comparison}",
        frontend_id="nl",
    )
    assert bundle["errors"] == []
    assert bundle["rows"]["rows"] == [["Asha", "CSE", 91], ["Meera", "ECE", 86]]


@pytest.mark.parametrize("phrase", [
    "student names", "students names", "names of students", "names of the student",
    "student.name", "student's names", "students' names",
])
def test_field_reference_syntaxes(phrase):
    bundle = console_run(f"please show me the {phrase} where marks above 80.", frontend_id="nl")
    assert not bundle["errors"]
    assert bundle["rows"]["rows"] == [["Asha"], ["Meera"]]


@pytest.mark.parametrize("owner", ["student's", "students'", "STUDENT'S"])
def test_possessive_owner_does_not_steal_a_later_quoted_literal(owner):
    bundle = console_run(f"show {owner} names where name is 'Asha'", frontend_id="nl")
    assert not bundle["errors"]
    assert bundle["rows"]["rows"] == [["Asha"]]
    tokens = bundle["stages"][0]["artifact"]["tokens"]
    assert [(token["type"], token["value"]) for token in tokens if token["type"] in {"POSSESSED", "STRING"}] == [
        ("POSSESSED", owner), ("STRING", "'Asha'"),
    ]


@pytest.mark.parametrize(("operator", "expected"), [
    ("at least 80", ["Asha", "Ravi", "Meera"]),
    ("no less than 80", ["Asha", "Ravi", "Meera"]),
    ("is greater than or equal to 80", ["Asha", "Ravi", "Meera"]),
    ("at most 80", ["Ravi", "Kabir"]),
    ("no more than 80", ["Ravi", "Kabir"]),
    ("less than or equal to 80", ["Ravi", "Kabir"]),
    ("below 80", ["Kabir"]),
    ("under 80", ["Kabir"]),
    ("is 80", ["Ravi"]),
    ("equals 80", ["Ravi"]),
    ("equal to 80", ["Ravi"]),
    ("exactly 80", ["Ravi"]),
    ("is not 80", ["Asha", "Meera", "Kabir"]),
    ("not equal to 80", ["Asha", "Meera", "Kabir"]),
    ("!= 80", ["Asha", "Meera", "Kabir"]),
])
def test_comparison_synonyms_share_the_integer_operators(operator, expected):
    bundle = console_run(f"show names from students with marks {operator}", frontend_id="nl")
    assert not bundle["errors"]
    assert bundle["rows"]["rows"] == [[name] for name in expected]
    assert bundle["sqlite_cross_check"]["passed"]


def test_projection_order_duplicates_and_multiple_predicates():
    bundle = console_run(
        "display marks, student names and student names from students where marks >= 80 and marks < 90",
        frontend_id="nl",
    )
    assert not bundle["errors"]
    assert bundle["rows"]["rows"] == [[80, "Ravi", "Ravi"], [86, "Meera", "Meera"]]


def test_between_lowers_to_two_and_terms():
    bundle = console_run("list names of students whose marks are between 80 and 90", frontend_id="nl")
    assert not bundle["errors"]
    lowered = bundle["stages"][1]["artifact"]["tree"]["where"]
    assert [term["op"] for term in lowered] == [">=", "<="]
    assert bundle["rows"]["rows"] == [["Ravi"], ["Meera"]]


@pytest.mark.parametrize("projection", ["all students", "students", "all columns from students", "all fields from student"])
def test_entity_and_all_columns_expand_to_explicit_projection(projection):
    bundle = console_run(f"show {projection} where marks > 80", frontend_id="nl")
    assert not bundle["errors"]
    assert bundle["rows"]["columns"] == ["id", "name", "marks", "dept_id"]
    assert bundle["rows"]["rows"][0] == [1, "Asha", 91, 10]
    assert "*" not in bundle["inputs"]["generated_sql"]


def test_no_where_clause_is_not_a_template_special_case():
    bundle = console_run("GET student names and department names and marks!", frontend_id="nl")
    assert not bundle["errors"]
    assert bundle["rows"]["count"] == 4


@pytest.mark.parametrize("source", [
    "show the student names and the marks where the marks are above 80",
    "please give me all the names of the students with the marks > 80",
    "show the student.name from the student where the student.marks > 80",
    "list the student's names whose the marks are at least 81",
])
def test_articles_are_grammar_sugar_not_fixed_sentence_slots(source):
    bundle = console_run(source, frontend_id="nl")
    assert not bundle["errors"]
    assert [row[0] for row in bundle["rows"]["rows"]] == ["Asha", "Meera"]


def test_quoted_text_preserves_case_and_embedded_quotes(fixtures):
    for text in ['"Asha"', "'Asha'"]:
        bundle = console_run(f"show names from student where names are {text}", frontend_id="nl")
        assert not bundle["errors"]
        assert bundle["rows"]["rows"] == [["Asha"]]
    prepared = prepare("show name from student where name equals 'O''Brien'", registry=fixtures[1])
    assert prepared.ast.where[0].literal.value == "O'Brien"
    assert "'O''Brien'" in prepared.sql


def test_nl_has_a_distinct_typed_ast_before_lowering():
    query = NLParser().parse(USER_QUERY)
    assert isinstance(query, nl.Query)
    assert isinstance(query.projection, nl.Projection)
    assert len(query.projection.fields) == 3
    assert isinstance(query.conditions[0], nl.Comparison)
    assert query.conditions[0].operator.value == ">"


def test_all_nl_ast_nodes_have_real_source_positions():
    def visit(value):
        if isinstance(value, NlSpan):
            assert value.kind == "nl_span"
            assert 0 <= value.char_start < value.char_end <= len(USER_QUERY)
        elif is_dataclass(value):
            assert hasattr(value, "locator")
            for field in fields(value):
                visit(getattr(value, field.name))
        elif isinstance(value, tuple):
            for item in value:
                visit(item)
    visit(NLParser().parse(USER_QUERY))


def test_nl_tokens_are_not_tokens_of_generated_sql():
    bundle = console_run(USER_QUERY, frontend_id="nl")
    tokens = bundle["stages"][0]["artifact"]["tokens"]
    assert tokens[0]["type"] == "COMMAND" and tokens[0]["value"] == "show"
    assert all(token["locator"]["kind"] == "nl_span" for token in tokens)
    assert not any(token["value"] == "SELECT" for token in tokens)
    for token in tokens:
        loc = token["locator"]
        assert USER_QUERY[loc["char_start"]:loc["char_end"]] == token["value"]


def test_nl_builds_shared_ast_without_reparsing_sql(monkeypatch, fixtures):
    def forbidden(*args, **kwargs):
        raise AssertionError("NL semantics must not be implemented by SQL reparsing")
    monkeypatch.setattr(SQLParser, "parse", forbidden)
    result = prepare(USER_QUERY, registry=fixtures[1], relationships=NL_RELATIONSHIPS)
    assert [column.name for column in result.ast.columns] == ["name", "dept_name", "marks"]


def test_lowered_ast_matches_explicit_sql(fixtures):
    nl_ast = prepare(USER_QUERY, registry=fixtures[1], relationships=NL_RELATIONSHIPS).ast
    sql_ast = SQLParser().parse(
        "SELECT student.name, department.dept_name, student.marks FROM student "
        "JOIN department ON student.dept_id = department.id WHERE student.marks > 80;"
    )
    assert normalized_ast(nl_ast) == normalized_ast(sql_ast)


@pytest.mark.parametrize(("query", "code"), [
    ("show grade from student", "BIND_UNKNOWN_COLUMN"),
    ("show id from student and department", "BIND_AMBIGUOUS_COLUMN"),
    ("show id", "NL_AMBIGUOUS_TABLE"),
    ("show unknown fields", "NL_TABLE_REQUIRED"),
    ("show name from missing", "NL_UNKNOWN_TABLE"),
    ("show name from student where name above 'Asha'", "BIND_UNSUPPORTED_OP_FOR_TEXT"),
    ("show name from student where marks equal '80'", "BIND_TYPE_MISMATCH"),
    ("show name from student where marks > 80 or marks < 70", "NL_UNSUPPORTED_CONJUNCTION"),
])
def test_ambiguity_types_and_unsupported_constructs_are_not_guessed(query, code):
    bundle = console_run(query, frontend_id="nl")
    assert bundle["errors"][0]["code"] == code
    assert bundle["errors"][0]["locator"]["kind"] == "nl_span"
    assert bundle["rows"] is None


@pytest.mark.parametrize("query", [
    "", "show", "show name where", "show name from student where marks >", "delete all rows",
    "show name from student where marks = 1.5", "show name from student limit 1",
    "show name from student where name = 'unterminated", "show name from student @",
    "show name from student; drop table student",
])
def test_malformed_or_unsupported_input_returns_designed_diagnostics(query):
    bundle = console_run(query, frontend_id="nl")
    assert bundle["errors"]
    assert bundle["errors"][0]["code"] != "INTERNAL"
    assert bundle["rows"] is None


def test_multiline_bind_error_highlights_the_nl_input():
    source = "show names from student\nwhere grade > 80"
    bundle = console_run(source, frontend_id="nl")
    error = bundle["errors"][0]
    assert error["code"] == "BIND_UNKNOWN_COLUMN"
    loc = error["locator"]
    assert (loc["line"], loc["col"]) == (2, 7)
    assert source[loc["char_start"]:loc["char_end"]] == "grade"


def test_incomplete_query_diagnostic_points_to_the_actual_end():
    source = "show names from student\nwhere marks > "
    error = console_run(source, frontend_id="nl")["errors"][0]
    assert error["code"] == "NL_PARSE_UNEXPECTED_TOKEN"
    assert error["locator"]["char_start"] == len(source)
    assert error["locator"]["char_end"] == len(source)
    assert (error["locator"]["line"], error["locator"]["col"]) == (2, len("where marks > ") + 1)


def test_invalid_escape_keeps_the_literal_source_span():
    source = 'show names from student where name is "bad\\q"'
    error = console_run(source, frontend_id="nl")["errors"][0]
    assert error["code"] == "NL_INVALID_LITERAL"
    loc = error["locator"]
    assert source[loc["char_start"]:loc["char_end"]] == '"bad\\q"'


def test_other_schemas_and_declared_relationships_are_not_hardcoded():
    adapter = FixtureAdapter()
    adapter.create_table("employee", [
        Column("id", "INTEGER"), Column("name", "TEXT"), Column("team_id", "INTEGER"), Column("salary", "INTEGER"),
    ])
    adapter.create_table("team", [Column("id", "INTEGER"), Column("team_name", "TEXT")])
    adapter.insert_rows("employee", [(1, "Ada", 10, 70000), (2, "Lin", 20, 40000)])
    adapter.insert_rows("team", [(10, "Compilers"), (20, "Storage")])
    registry = SchemaRegistry(adapter.open_catalog())
    source = "display employee names and team names and salaries where salaries above 50000"
    bundle = run_query(source, adapter=adapter, registry=registry, frontend_id="nl",
        frontend_lexer=NLParser().tokenize,
        prepare=lambda s: prepare(s, registry=registry, relationships=(("employee", "team_id", "team", "id"),)),
        verify_runner=make_verify_runner(adapter))
    assert not bundle["errors"]
    assert bundle["rows"]["rows"] == [["Ada", "Compilers", 70000]]
    assert bundle["sqlite_cross_check"]["passed"]


def test_join_inference_requires_unique_declared_metadata(fixtures):
    source = "show student names and department names"
    with pytest.raises(CompilerError) as caught:
        prepare(source, registry=fixtures[1])
    assert caught.value.envelope.code == "NL_JOIN_REQUIRED"
    with pytest.raises(CompilerError) as caught:
        prepare(source, registry=fixtures[1], relationships=(
            *NL_RELATIONSHIPS, ("student", "id", "department", "id"),
        ))
    assert caught.value.envelope.code == "NL_JOIN_REQUIRED"


def test_explicit_join_works_without_inference_metadata(fixtures):
    source = ("show student names and department names from student join department "
              "on student.dept_id equals department.id")
    prepared = prepare(source, registry=fixtures[1])
    assert prepared.ast.join.on_left.name == "dept_id"
    assert prepared.artifact["nl_lowering"]["join"]["source"] == "explicit ON"
