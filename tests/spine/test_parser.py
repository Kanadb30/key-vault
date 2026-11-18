from dataclasses import fields, is_dataclass

import pytest

from sql_compiler.ast_nodes import BuilderNode, IntLiteral, JsonPointer, Locator, SqlSpan, TemplateSlot
from sql_compiler.errors import CompilerError


def test_join_uses_table_reference_and_its_own_span(parser, join_sql):
    ast = parser.parse(join_sql)
    assert ast.from_table.name == "student"
    assert ast.join.table == "department"
    assert join_sql[ast.join.table_locator.char_start:ast.join.table_locator.char_end] == "department"
    assert ast.join.on_left.name == "dept_id"
    assert ast.join.on_right.name == "id"
    assert ast.where[0].literal == IntLiteral(80, ast.where[0].literal.locator)


def test_every_ast_node_has_source_positions(parser, join_sql):
    def visit(value):
        if isinstance(value, Locator):
            assert isinstance(value, SqlSpan)
            assert value.kind == "sql_span"
            assert 0 <= value.char_start < value.char_end <= len(join_sql)
            assert value.line >= 1 and value.col >= 1
        elif is_dataclass(value):
            assert hasattr(value, "locator")
            for field in fields(value):
                visit(getattr(value, field.name))
        elif isinstance(value, tuple):
            for item in value:
                visit(item)
    visit(parser.parse(join_sql))


def test_multiline_reference_span(parser):
    sql = "SELECT\n  student.name\nFROM student;"
    ref = parser.parse(sql).columns[0]
    assert (ref.locator.line, ref.locator.col, ref.locator.end_col) == (2, 3, 15)
    assert sql[ref.locator.char_start:ref.locator.char_end] == "student.name"


@pytest.mark.parametrize("sql", [
    "select NAME from STUDENT where MARKS > +80",
    "SELECT name FROM student;",
    "SELECT name FROM student",
    "SELECT name FROM student WHERE name = 'O''Brien';",
    "SELECT name FROM student WHERE marks >= -80 AND id <> 0;",
    "SELECT selectivity FROM from_table;",
])
def test_supported_syntax(parser, sql):
    assert parser.parse(sql).from_table.name


@pytest.mark.parametrize("sql", [
    "", "SELECT FROM student;", "SELECT * FROM student;",
    "SELECT name FROM student ORDER BY name;",
    "SELECT name FROM student WHERE marks > 80 OR marks < 20;",
    "SELECT name FROM student LIMIT 1;",
    "SELECT name FROM student WHERE marks = NULL;",
    "SELECT name FROM student WHERE marks = 1.2;",
    "SELECT name FROM student WHERE name = 'unterminated;",
    "SELECT name FROM student; SELECT name FROM student;",
])
def test_unsupported_syntax(parser, sql):
    with pytest.raises(CompilerError):
        parser.parse(sql)


def test_token_stream_is_real_lexer_output(parser):
    tokens = parser.tokenize("WHERE student.marks > 80")
    assert [(token.type, str(token)) for token in tokens] == [
        ("WHERE", "WHERE"), ("IDENT", "student"), ("DOT", "."),
        ("IDENT", "marks"), ("COMP_OP", ">"), ("INT", "80"),
    ]
    assert tokens[1].start_pos == 6


def test_lexer_does_not_hide_invalid_character(parser):
    with pytest.raises(CompilerError) as caught:
        parser.tokenize("SELECT @ FROM student;")
    env = caught.value.envelope
    assert (env.stage, env.code) == ("lex", "PARSE_UNEXPECTED_CHAR")
    assert env.locator["char_start"] == 7
    assert env.locator["kind"] == "sql_span"


@pytest.mark.parametrize(("locator", "expected"), [
    (JsonPointer(pointer="$.query.term"), {"kind": "json_pointer", "pointer": "$.query.term"}),
    (BuilderNode(node_id="filter-1"), {"kind": "builder_node", "node_id": "filter-1"}),
    (TemplateSlot(template_id="marks", slot="value", capture_offset=4),
     {"kind": "template_slot", "template_id": "marks", "slot": "value", "capture_offset": 4}),
])
def test_all_locator_variants_serialize_their_fields(locator, expected):
    assert locator.to_dict() == expected
