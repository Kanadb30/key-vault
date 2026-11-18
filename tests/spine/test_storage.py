import pytest

from core.types import Column, Relation, SchemaRegistry, TableSchema
from sql_compiler.pipeline import run_query
from storage.fixtures import FixtureAdapter
from storage.sqlite_adapter import SQLiteAdapter


@pytest.fixture(params=["fixtures", "sqlite"])
def adapter(request):
    result = FixtureAdapter() if request.param == "fixtures" else SQLiteAdapter()
    yield result
    if isinstance(result, SQLiteAdapter):
        result.close()


def test_adapter_contract_preserves_typed_order_and_duplicates(adapter):
    columns = (Column("id", "INTEGER"), Column("label", "TEXT"))
    rows = ((-9223372036854775808, "O'Brien"), (9223372036854775807, "नमस्ते"), (1, ""), (1, ""))
    adapter.create_table("items", columns)
    adapter.insert_rows("items", rows)
    assert adapter.probe()["available"]
    assert adapter.open_catalog() == {"items": TableSchema("items", columns)}
    assert adapter.scan("items") == Relation(columns, rows)


@pytest.mark.parametrize("row", [
    (True, "bad"), (None, "bad"), (1.0, "bad"), (1, False),
    (1, None), (1, 2), (2**63, "bad"), (-(2**63) - 1, "bad"), (1,),
])
def test_adapter_rejects_invalid_batch_before_mutation(adapter, row):
    adapter.create_table("items", (Column("id", "INTEGER"), Column("label", "TEXT")))
    with pytest.raises(ValueError):
        adapter.insert_rows("items", [(1, "valid"), row])
    assert adapter.scan("items").rows == ()


def test_duplicate_table_names_are_rejected(adapter):
    columns = (Column("id", "INTEGER"),)
    adapter.create_table("items", columns)
    with pytest.raises(Exception):
        adapter.create_table("items", columns)
    assert adapter.open_catalog() == {"items": TableSchema("items", columns)}


def test_empty_insert(adapter):
    adapter.create_table("items", (Column("id", "INTEGER"),))
    adapter.insert_rows("items", [])
    assert adapter.scan("items").rows == ()


def test_sqlite_catalog_and_rows_survive_reopen(tmp_path):
    path = str(tmp_path / "oracle.db")
    columns = (Column("id", "INTEGER"), Column("label", "TEXT"))
    with SQLiteAdapter(path) as adapter:
        adapter.create_table("items", columns)
        adapter.insert_rows("items", [(1, "persisted")])
    with SQLiteAdapter(path) as adapter:
        assert adapter.open_catalog() == {"items": TableSchema("items", columns)}
        assert adapter.scan("items").rows == ((1, "persisted"),)


def test_sqlite_scan_order_uses_a_hidden_rowid_not_a_user_column():
    with SQLiteAdapter() as adapter:
        adapter.create_table("items", (Column("rowid", "INTEGER"),))
        adapter.insert_rows("items", [(9,), (1,)])
        assert adapter.scan("items").rows == ((9,), (1,))


def test_sqlite_can_execute_the_same_interpreter_plan(fixtures, join_sql):
    fixtures_adapter, registry = fixtures
    with SQLiteAdapter() as adapter:
        for name, schema in registry.tables().items():
            adapter.create_table(name, schema.columns)
            adapter.insert_rows(name, fixtures_adapter.scan(name).rows)
        bundle = run_query(join_sql, adapter=adapter, registry=registry, verify=False)
    assert bundle["errors"] == []
    assert bundle["rows"]["rows"] == [["Asha", "CSE"], ["Meera", "ECE"]]
    assert bundle["metrics"]["join_pairs_tried"] == {"pre": 12, "post": 6}
    assert bundle["provenance"]["backend"] == "sqlite"
    assert bundle["provenance"]["fixture_set"] is None


def test_registry_checks_column_order_not_only_names():
    columns = (Column("id", "INTEGER"), Column("label", "TEXT"))
    registry = SchemaRegistry([TableSchema("items", columns)])
    with pytest.raises(ValueError, match="schema drift"):
        registry.validate_relation("items", Relation(columns[::-1], ()))


def test_scan_validates_row_values_even_if_adapter_lies(fixtures):
    adapter, registry = fixtures
    columns = registry.table("student").columns
    adapter.scan = lambda _: Relation(columns, ((True, "Asha", 91, 10),))
    bundle = run_query("SELECT name FROM student;", adapter=adapter, registry=registry)
    assert bundle["errors"][0]["stage"] == "execute"
    assert "requires INTEGER" in bundle["errors"][0]["message"]


@pytest.mark.parametrize("columns", [
    (), (Column("id", "INTEGER"), Column("id", "TEXT")),
])
def test_invalid_schemas_cannot_be_registered(columns):
    with pytest.raises(ValueError):
        SchemaRegistry([TableSchema("items", columns)])
