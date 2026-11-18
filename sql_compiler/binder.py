"""Name resolution + type checking (README §2 "Bind and validate").

Interface: bind(select_ast, registry) -> BoundSelect; raises CompilerError.
Invariants: identifiers lowercased; an unqualified name must match exactly one
column in scope (ambiguity names every candidate); INTEGER allows all six ops,
TEXT only '=' and '<>'; literal type must match column type; integer literals
are range-checked to i64 (the engine and SQLite are 64-bit — Python is not);
the two ON columns must share a type and come from opposite inputs, in either
operand order.
Side effects: none.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.types import TableSchema, Type
from .ast_nodes import ColumnRef, Compare, IntLiteral, Select, StrLiteral
from .errors import CompilerError, ErrorEnvelope

I64_MIN, I64_MAX = -(2**63), 2**63 - 1
INT_OPS = {"=", "<>", "<", "<=", ">", ">="}
TEXT_OPS = {"=", "<>"}


@dataclass(frozen=True)
class BoundColumn:
    table: str
    column: str
    type: Type

    def key(self) -> tuple[str, str]:
        return (self.table, self.column)

    def qualified(self) -> str:
        return f"{self.table}.{self.column}"


@dataclass(frozen=True)
class BoundCompare:
    column: BoundColumn
    op: str
    literal_value: object
    literal_kind: str  # "int" | "str"
    locator: dict | None

    def label(self) -> str:
        lit = (
            str(self.literal_value)
            if self.literal_kind == "int"
            else "'" + str(self.literal_value).replace("'", "''") + "'"
        )
        return f"{self.column.qualified()} {self.op} {lit}"


@dataclass(frozen=True)
class BoundJoin:
    table: str
    left: BoundColumn   # column from the FROM table
    right: BoundColumn  # column from the JOIN table


@dataclass(frozen=True)
class BoundSelect:
    columns: tuple[BoundColumn, ...]
    from_table: str
    join: BoundJoin | None
    where: tuple[BoundCompare, ...]


def _d(loc) -> dict | None:
    return loc.to_dict() if loc is not None else None


def _err(code: str, message: str, locator: dict | None) -> CompilerError:
    return CompilerError(ErrorEnvelope(stage="bind", code=code, message=message, locator=locator))


def bind(select: Select, registry) -> BoundSelect:
    scope: dict[str, TableSchema] = {}

    from_name = select.from_table.name.lower()
    from_schema = registry.table(from_name)
    if from_schema is None:
        raise _err(
            "BIND_UNKNOWN_TABLE",
            f"Unknown table '{from_name}'",
            _d(select.from_table.locator),
        )
    scope[from_name] = from_schema

    join_schema: TableSchema | None = None
    join_name: str | None = None
    if select.join is not None:
        join_name = select.join.table.lower()
        if join_name == from_name:
            raise _err(
                "BIND_DUPLICATE_TABLE_REF",
                f"Table '{join_name}' appears more than once in this query",
                _d(select.join.table_locator),
            )
        join_schema = registry.table(join_name)
        if join_schema is None:
            raise _err(
                "BIND_UNKNOWN_TABLE",
                f"Unknown table '{join_name}'",
                _d(select.join.table_locator),
            )
        scope[join_name] = join_schema

    def resolve(ref: ColumnRef):
        if ref.qualifier is not None:
            qualifier = ref.qualifier.lower()
            schema = scope.get(qualifier)
            if schema is None:
                raise _err(
                    "BIND_UNKNOWN_TABLE",
                    f"Unknown table '{qualifier}'",
                    _d(ref.locator),
                )
            column = ref.name.lower()
            ctype = schema.column_type(column)
            if ctype is None:
                raise _err(
                    "BIND_UNKNOWN_COLUMN",
                    f"Unknown column '{column}' in table '{qualifier}'",
                    _d(ref.locator),
                )
            return BoundColumn(qualifier, column, ctype)

        column = ref.name.lower()
        candidates = [(t, s) for t, s in scope.items() if s.has_column(column)]
        if not candidates:
            searched = ", ".join(f"'{t}'" for t in sorted(scope))
            where = f"in table {searched}" if len(candidates) == 0 and len(scope) == 1 else f"in tables {searched}"
            raise _err(
                "BIND_UNKNOWN_COLUMN",
                f"Unknown column '{column}' {where}",
                _d(ref.locator),
            )
        if len(candidates) > 1:
            names = ", ".join(f"'{t}.{column}'" for t, _ in sorted(candidates))
            raise _err(
                "BIND_AMBIGUOUS_COLUMN",
                f"Column reference '{column}' is ambiguous: could be {names}",
                _d(ref.locator),
            )
        tname, schema = candidates[0]
        return BoundColumn(tname, column, schema.column_type(column))

    def check_compare(cmp: Compare) -> BoundCompare:
        col = resolve(cmp.column)
        literal = cmp.literal
        if isinstance(literal, IntLiteral):
            if col.type != "INTEGER":
                raise _err(
                    "BIND_TYPE_MISMATCH",
                    f"Literal {literal.value} is an integer but column '{col.qualified()}' is {col.type}",
                    _d(cmp.locator),
                )
            if not (I64_MIN <= literal.value <= I64_MAX):
                raise _err(
                    "BIND_INT_OUT_OF_RANGE",
                    f"Integer literal {literal.value} is outside the signed 64-bit range",
                    _d(literal.locator),
                )
            if cmp.op not in INT_OPS:
                raise _err(
                    "BIND_TYPE_MISMATCH",
                    f"Comparison '{cmp.op}' is not supported for INTEGER column '{col.qualified()}'",
                    _d(cmp.locator),
                )
            return BoundCompare(col, cmp.op, literal.value, "int", _d(cmp.locator))
        if isinstance(literal, StrLiteral):
            if col.type != "TEXT":
                raise _err(
                    "BIND_TYPE_MISMATCH",
                    f"Literal '{literal.value}' is text but column '{col.qualified()}' is {col.type}",
                    _d(cmp.locator),
                )
            if cmp.op not in TEXT_OPS:
                raise _err(
                    "BIND_UNSUPPORTED_OP_FOR_TEXT",
                    f"Comparison '{cmp.op}' is not supported for TEXT column '{col.qualified()}' (use '=' or '<>')",
                    _d(cmp.locator),
                )
            return BoundCompare(col, cmp.op, literal.value, "str", _d(cmp.locator))
        raise _err("INTERNAL", f"Unknown literal node {literal!r}", None)

    columns = tuple(resolve(c) for c in select.columns)
    where = tuple(check_compare(c) for c in select.where)

    join: BoundJoin | None = None
    if select.join is not None:
        lcol = resolve(select.join.on_left)
        rcol = resolve(select.join.on_right)
        if lcol.type != rcol.type:
            raise _err(
                "BIND_TYPE_MISMATCH",
                f"Join columns must have the same type: {lcol.qualified()} is {lcol.type}, "
                f"{rcol.qualified()} is {rcol.type}",
                _d(select.join.locator),
            )
        if {lcol.table, rcol.table} != {from_name, join_name}:
            raise _err(
                "BIND_JOIN_MISMATCH",
                f"Join columns must come from opposite inputs: {lcol.qualified()} and {rcol.qualified()}",
                _d(select.join.locator),
            )
        left, right = (lcol, rcol) if lcol.table == from_name else (rcol, lcol)
        join = BoundJoin(table=join_name, left=left, right=right)

    return BoundSelect(columns=columns, from_table=from_name, join=join, where=where)
