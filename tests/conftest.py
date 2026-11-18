import pytest

from sql_compiler.parser import SQLParser
from storage.fixtures import default_fixtures


@pytest.fixture
def parser():
    return SQLParser()


@pytest.fixture
def fixtures():
    return default_fixtures()


@pytest.fixture
def join_sql():
    return (
        "SELECT student.name, department.dept_name "
        "FROM student JOIN department ON student.dept_id = department.id "
        "WHERE student.marks > 80;"
    )
