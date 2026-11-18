"""In-memory fixture backend — the graded demo path.

Interface: StorageAdapter over dict[table_name] = Relation.
Invariants: deterministic; insertion order preserved; schema validated against
the registry by the interpreter's Scan (adapters stay dumb).
Side effects: create_table/insert_rows mutate the dict.
"""
from __future__ import annotations

from typing import Sequence

from core.types import Column, Relation, SchemaRegistry, TableSchema, validate_rows


class FixtureAdapter:
    backend_name = "fixtures"

    def __init__(self, tables: dict[str, Relation] | None = None, *, fixture_set: str | None = None) -> None:
        self._fixture_set = fixture_set
        self._tables: dict[str, Relation] = dict(tables or {})
        for name, relation in self._tables.items():
            TableSchema(name, relation.columns)
            validate_rows(relation.columns, relation.rows)

    def probe(self) -> dict:
        return {"backend": self.backend_name, "available": True, "fixture_set": self._fixture_set}

    def open_catalog(self) -> dict[str, TableSchema]:
        return {
            name: TableSchema(name, rel.columns) for name, rel in self._tables.items()
        }

    def create_table(self, name: str, columns: Sequence[Column]) -> None:
        key = name.lower()
        if key in self._tables:
            raise ValueError(f"table '{key}' already exists")
        schema = TableSchema(key, tuple(columns))
        self._tables[key] = Relation(schema.columns, ())

    def insert_rows(self, table: str, rows: Sequence[Sequence[object]]) -> None:
        key = table.lower()
        rel = self._tables[key]
        validate_rows(rel.columns, rows)
        self._tables[key] = Relation(rel.columns, rel.rows + tuple(tuple(r) for r in rows))

    def scan(self, table: str) -> Relation:
        return self._tables[table.lower()]


def _student_department(students: tuple[tuple[int, str, int, int], ...], departments: tuple[tuple[int, str], ...], fixture_set: str):
    student = Relation(
        columns=(
            Column("id", "INTEGER"),
            Column("name", "TEXT"),
            Column("marks", "INTEGER"),
            Column("dept_id", "INTEGER"),
        ),
        rows=students,
    )
    department = Relation(
        columns=(Column("id", "INTEGER"), Column("dept_name", "TEXT")),
        rows=departments,
    )
    adapter = FixtureAdapter({"student": student, "department": department}, fixture_set=fixture_set)
    return adapter, SchemaRegistry(adapter.open_catalog().values())


def default_fixtures() -> tuple[FixtureAdapter, SchemaRegistry]:
    """The proposal's fixture data (README §4) — both plans and the SQLite
    check run on exactly this data."""
    return _student_department(
        (
            (1, "Asha", 91, 10),
            (2, "Ravi", 80, 20),
            (3, "Meera", 86, 20),
            (4, "Kabir", 67, 30),
        ),
        ((10, "CSE"), (20, "ECE"), (30, "ME")),
        "default-v1",
    )


_CLASSROOM_FIRST = (
    "Asha", "Ravi", "Meera", "Kabir", "Diya", "Arjun",
    "Nisha", "Vikram", "Sara", "Rohan", "Isha", "Aditya",
)
_CLASSROOM_LAST = ("Sharma", "Patel", "Nair", "Gupta", "Iyer")
_CLASSROOM_DEPARTMENTS = ("CSE", "ECE", "ME", "CE", "EE", "IT")


def classroom_fixtures() -> tuple[FixtureAdapter, SchemaRegistry]:
    """A larger, fully deterministic set: 60 students, 6 departments.

    Same schema as default-v1, so every frontend, relationship, and plan
    behaves identically — only the measured work changes. No randomness:
    repeated calls return identical rows.
    """
    departments = tuple((10 + index * 10, name) for index, name in enumerate(_CLASSROOM_DEPARTMENTS))
    students = tuple(
        (index + 1,
         f"{_CLASSROOM_FIRST[index % 12]} {_CLASSROOM_LAST[index // 12]}",
         52 + (index * 37) % 47,
         10 + (index % 6) * 10)
        for index in range(60)
    )
    return _student_department(
        students,
        departments,
        "classroom-60",
    )


FIXTURE_SETS = {
    "default-v1": {
        "label": "Demo · 4 students",
        "description": "The graded walkthrough data from README §4.",
    },
    "classroom-60": {
        "label": "Classroom · 60 students",
        "description": "A larger generated set for plan metrics and filters.",
    },
}

_BUILDERS = {"default-v1": default_fixtures, "classroom-60": classroom_fixtures}


def open_fixture_set(fixture_set: str) -> tuple[FixtureAdapter, SchemaRegistry]:
    """Open a named fixture set; raises ValueError with the valid choices."""
    try:
        builder = _BUILDERS[fixture_set]
    except KeyError:
        raise ValueError(f"unknown dataset '{fixture_set}'. Available: {', '.join(_BUILDERS)}") from None
    return builder()
