import pytest

from sql_compiler.binder import bind
from sql_compiler.errors import CompilerError


def bind_sql(parser, fixtures, sql):
    return bind(parser.parse(sql), fixtures[1])


@pytest.mark.parametrize(("sql", "code"), [
    ("SELECT name FROM missing;", "BIND_UNKNOWN_TABLE"),
    ("SELECT grade FROM student;", "BIND_UNKNOWN_COLUMN"),
    ("SELECT student.grade FROM student;", "BIND_UNKNOWN_COLUMN"),
    ("SELECT department.id FROM student;", "BIND_UNKNOWN_TABLE"),
    ("SELECT name FROM student WHERE marks = '80';", "BIND_TYPE_MISMATCH"),
    ("SELECT name FROM student WHERE name = 80;", "BIND_TYPE_MISMATCH"),
    ("SELECT name FROM student WHERE name > 'Asha';", "BIND_UNSUPPORTED_OP_FOR_TEXT"),
    ("SELECT name FROM student WHERE marks = 9223372036854775808;", "BIND_INT_OUT_OF_RANGE"),
    ("SELECT name FROM student WHERE marks = -9223372036854775809;", "BIND_INT_OUT_OF_RANGE"),
    ("SELECT name FROM student JOIN student ON student.id = student.id;", "BIND_DUPLICATE_TABLE_REF"),
    ("SELECT name FROM student JOIN missing ON student.id = missing.id;", "BIND_UNKNOWN_TABLE"),
    ("SELECT name FROM student JOIN department ON student.name = department.id;", "BIND_TYPE_MISMATCH"),
    ("SELECT name FROM student JOIN department ON student.id = student.dept_id;", "BIND_JOIN_MISMATCH"),
    ("SELECT id FROM student JOIN department ON student.dept_id = department.id;", "BIND_AMBIGUOUS_COLUMN"),
])
def test_binding_errors_have_specific_codes_and_spans(parser, fixtures, sql, code):
    with pytest.raises(CompilerError) as caught:
        bind_sql(parser, fixtures, sql)
    env = caught.value.envelope
    assert env.stage == "bind"
    assert env.code == code
    assert env.locator["kind"] == "sql_span"
    assert env.locator["col"] > 0


def test_ambiguity_names_both_candidates(parser, fixtures):
    with pytest.raises(CompilerError) as caught:
        bind_sql(parser, fixtures, "SELECT id FROM student JOIN department ON student.dept_id = department.id;")
    assert caught.value.envelope.message == (
        "Column reference 'id' is ambiguous: could be 'department.id', 'student.id'"
    )
    assert caught.value.envelope.locator["col"] == 8


@pytest.mark.parametrize("value", [-9223372036854775808, 9223372036854775807])
def test_i64_endpoints_are_valid(parser, fixtures, value):
    query = bind_sql(parser, fixtures, f"SELECT name FROM student WHERE marks = {value};")
    assert query.where[0].literal_value == value


def test_case_normalization(parser, fixtures):
    bound = bind_sql(parser, fixtures, "select STUDENT.NAME from STUDENT where MARKS > 80;")
    assert bound.from_table == "student"
    assert bound.columns[0].key() == ("student", "name")


def test_reversed_join_keys_are_canonical(parser, fixtures, join_sql):
    reversed_sql = join_sql.replace("student.dept_id = department.id", "department.id = student.dept_id")
    assert bind_sql(parser, fixtures, join_sql) == bind_sql(parser, fixtures, reversed_sql)


def test_literal_round_trip_preserves_quotes_and_spaces(parser, fixtures):
    bound = bind_sql(parser, fixtures, "SELECT name FROM student WHERE name = 'O''Brien  Jr';")
    assert bound.where[0].literal_value == "O'Brien  Jr"
    assert bound.where[0].label() == "student.name = 'O''Brien  Jr'"
