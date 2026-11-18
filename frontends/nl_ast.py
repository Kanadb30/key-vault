"""Surface-language AST. No table names, projections, or joins are guessed here."""
from dataclasses import dataclass

from sql_compiler.ast_nodes import NlSpan


@dataclass(frozen=True)
class Field:
    words: tuple[str, ...]
    owner: tuple[str, ...] | None
    form: str
    locator: NlSpan


@dataclass(frozen=True)
class Projection:
    fields: tuple[Field, ...]
    all: bool
    locator: NlSpan


@dataclass(frozen=True)
class Table:
    words: tuple[str, ...]
    locator: NlSpan


@dataclass(frozen=True)
class Source:
    tables: tuple[Table, ...]
    on: tuple[Field, Field] | None
    locator: NlSpan


@dataclass(frozen=True)
class Literal:
    value: int | str
    kind: str
    locator: NlSpan


@dataclass(frozen=True)
class Operator:
    value: str
    locator: NlSpan


@dataclass(frozen=True)
class Comparison:
    field: Field
    operator: Operator
    literal: Literal
    locator: NlSpan


@dataclass(frozen=True)
class Between:
    field: Field
    lower: Literal
    upper: Literal
    locator: NlSpan


@dataclass(frozen=True)
class Query:
    command: str
    projection: Projection
    source: Source | None
    conditions: tuple[Comparison | Between, ...]
    locator: NlSpan


def render(query: Query) -> str:
    def field(value):
        owner = " ".join(value.owner) if value.owner else None
        words = " ".join(value.words)
        return f"{owner}.{words}" if owner else words
    lines = [f"NLQuery({query.command})", "├── Projection"]
    lines.extend(f"│   {'└' if i == len(query.projection.fields) - 1 else '├'}── Field({field(value)})"
                 for i, value in enumerate(query.projection.fields))
    source = ", ".join(" ".join(table.words) for table in query.source.tables) if query.source else "omitted"
    lines.append(f"├── Source({source})")
    if query.source and query.source.on:
        lines.append("│   └── On(" + " = ".join(field(ref) for ref in query.source.on) + ")")
    lines.append("└── Conditions")
    if not query.conditions:
        lines.append("    └── none")
    for i, condition in enumerate(query.conditions):
        if isinstance(condition, Between):
            label = f"Between({field(condition.field)}, {condition.lower.value!r}, {condition.upper.value!r})"
        else:
            label = f"Compare({field(condition.field)}, {condition.operator.value}, {condition.literal.value!r})"
        lines.append(f"    {'└' if i == len(query.conditions) - 1 else '├'}── {label}")
    return "\n".join(lines)
