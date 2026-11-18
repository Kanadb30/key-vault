"""AST + Locator union (docs/bundle_schema.md — frozen before these dataclasses).

Interface: source locators SqlSpan/NlSpan, BuilderNode, JsonPointer, and the
legacy replay-only TemplateSlot; plus the shared query AST
dataclasses TableRef, ColumnRef, IntLiteral, StrLiteral, Compare, JoinClause,
Select.
Invariants: every node carries a locator; identifiers keep their original
case (the binder lowercases); string literals are stored unescaped
('' → '); literals are python int/str.
Side effects: none.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Union


@dataclass(frozen=True)
class Locator:
    kind: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class SqlSpan(Locator):
    char_start: int | None = None
    char_end: int | None = None
    line: int | None = None
    col: int | None = None
    end_line: int | None = None
    end_col: int | None = None
    token_index_range: tuple[int, int] | None = None
    kind: str = "sql_span"

    def to_dict(self) -> dict:
        out: dict = {"kind": self.kind}
        for name in ("char_start", "char_end", "line", "col", "end_line", "end_col"):
            value = getattr(self, name)
            if value is not None:
                out[name] = int(value)
        if self.token_index_range is not None:
            out["token_index_range"] = list(self.token_index_range)
        return out


@dataclass(frozen=True)
class NlSpan(SqlSpan):
    """Character positions in the user's NL source, never generated SQL."""
    kind: str = "nl_span"


@dataclass(frozen=True)
class TemplateSlot(Locator):
    template_id: str = ""
    slot: str = ""
    capture_offset: int = 0
    kind: str = "template_slot"


@dataclass(frozen=True)
class BuilderNode(Locator):
    node_id: str = ""
    kind: str = "builder_node"


@dataclass(frozen=True)
class JsonPointer(Locator):
    pointer: str = ""
    kind: str = "json_pointer"


AnyLocator = Union[SqlSpan, NlSpan, TemplateSlot, BuilderNode, JsonPointer]


@dataclass(frozen=True)
class TableRef:
    name: str
    locator: AnyLocator


@dataclass(frozen=True)
class ColumnRef:
    qualifier: str | None
    name: str
    locator: AnyLocator


@dataclass(frozen=True)
class IntLiteral:
    value: int
    locator: AnyLocator


@dataclass(frozen=True)
class StrLiteral:
    value: str
    locator: AnyLocator


LiteralNode = Union[IntLiteral, StrLiteral]


@dataclass(frozen=True)
class Compare:
    column: ColumnRef
    op: str  # "=" "<>" "<" "<=" ">" ">="
    literal: LiteralNode
    locator: AnyLocator


@dataclass(frozen=True)
class JoinClause:
    table: str
    table_locator: AnyLocator
    on_left: ColumnRef
    on_right: ColumnRef
    locator: AnyLocator


@dataclass(frozen=True)
class Select:
    columns: tuple[ColumnRef, ...]
    from_table: TableRef
    join: JoinClause | None
    where: tuple[Compare, ...]
    locator: AnyLocator


def _qualified_ref(ref: "ColumnRef") -> str:
    return f"{ref.qualifier}.{ref.name}" if ref.qualifier else ref.name


def _literal_repr(lit) -> str:
    if isinstance(lit, IntLiteral):
        return str(lit.value)
    return "'" + lit.value.replace("'", "''") + "'"


def render_ast(select: "Select") -> str:
    """Compact README-style summary of the parsed SQL AST (parse-stage artifact)."""
    columns = ", ".join(_qualified_ref(c) for c in select.columns)
    lines = [
        "Select",
        f"\u251c\u2500\u2500 columns: [{columns}]",
        f"\u251c\u2500\u2500 from: {select.from_table.name}",
    ]
    if select.join is not None:
        lines.append(
            f"\u251c\u2500\u2500 join: {select.join.table} ON "
            f"{_qualified_ref(select.join.on_left)} = {_qualified_ref(select.join.on_right)}"
        )
    where = ", ".join(
        f'Compare({_qualified_ref(c.column)}, "{c.op}", {_literal_repr(c.literal)})'
        for c in select.where
    )
    lines.append(f"\u2514\u2500\u2500 where: [{where}]")
    return "\n".join(lines)
