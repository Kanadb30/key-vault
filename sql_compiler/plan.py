"""Logical plan IR + construction (README §3).

Interface: build_plan(bound) -> Project root; plan_to_json(node);
render_ascii(plan_json) -> list[str].
Invariants: node_id is assigned at construction and is stable across the
deep-copied pre/post plan pair; every node exposes .tables (the set of input
table names) used by pushdown attribution; labels mirror the README's
tree art (Scan(student), Filter(student.marks > 80), Project(name, dept_name)).
Side effects: none.
"""
from __future__ import annotations

from dataclasses import dataclass

from .binder import BoundColumn, BoundCompare, BoundSelect


@dataclass
class Scan:
    table: str
    node_id: int

    @property
    def operator(self) -> str:
        return "Scan"

    @property
    def tables(self) -> set[str]:
        return {self.table}

    def label(self) -> str:
        return self.table

    def children(self) -> list:
        return []


@dataclass
class Filter:
    terms: tuple[BoundCompare, ...]
    term_ids: tuple[str, ...]
    child: object
    node_id: int

    @property
    def operator(self) -> str:
        return "Filter"

    @property
    def tables(self) -> set[str]:
        return self.child.tables

    def label(self) -> str:
        return " AND ".join(t.label() for t in self.terms)

    def children(self) -> list:
        return [self.child]


@dataclass
class Join:
    on_left: BoundColumn
    on_right: BoundColumn
    left: object
    right: object
    node_id: int

    @property
    def operator(self) -> str:
        return "Join"

    @property
    def tables(self) -> set[str]:
        return self.left.tables | self.right.tables

    def label(self) -> str:
        return f"{self.on_left.qualified()} = {self.on_right.qualified()}"

    def children(self) -> list:
        return [self.left, self.right]


@dataclass
class Project:
    columns: tuple[BoundColumn, ...]
    child: object
    node_id: int

    @property
    def operator(self) -> str:
        return "Project"

    @property
    def tables(self) -> set[str]:
        return self.child.tables

    def label(self) -> str:
        return ", ".join(c.column for c in self.columns)

    def children(self) -> list:
        return [self.child]


class _NodeIds:
    def __init__(self, start: int = 0) -> None:
        self._n = start

    def next(self) -> int:
        self._n += 1
        return self._n


def build_plan(bound: BoundSelect) -> Project:
    ids = _NodeIds()
    left = Scan(bound.from_table, ids.next())
    if bound.join is not None:
        right = Scan(bound.join.table, ids.next())
        node = Join(bound.join.left, bound.join.right, left, right, ids.next())
    else:
        node = left
    if bound.where:
        term_ids = tuple(f"term#{i + 1}" for i in range(len(bound.where)))
        node = Filter(bound.where, term_ids, node, ids.next())
    return Project(bound.columns, node, ids.next())


def plan_to_json(node) -> dict:
    out: dict = {
        "node_id": node.node_id,
        "operator": node.operator,
        "label": node.label(),
        "children": [plan_to_json(c) for c in node.children()],
    }
    detail: dict = {}
    if isinstance(node, Scan):
        detail["table"] = node.table
    elif isinstance(node, Filter):
        detail = {"terms": [t.label() for t in node.terms], "term_ids": list(node.term_ids)}
    elif isinstance(node, Join):
        detail = {"on_left": node.on_left.qualified(), "on_right": node.on_right.qualified()}
    elif isinstance(node, Project):
        detail = {"columns": [c.column for c in node.columns]}
    out["detail"] = detail
    return out


def render_ascii(node: dict) -> list[str]:
    lines = [f"{node['operator']}({node['label']})"]
    kids = node.get("children", [])
    for i, child in enumerate(kids):
        last = i == len(kids) - 1
        branch = "\u2514\u2500\u2500 " if last else "\u251c\u2500\u2500 "  # └── | ├──
        sub = render_ascii(child)
        lines.append(branch + sub[0])
        continuation = "\u2502   " if not last else "    "  # │   | (4 spaces)
        lines.extend(continuation + extra for extra in sub[1:])
    return lines


def max_node_id(node) -> int:
    return max([node.node_id, *(max_node_id(c) for c in node.children())])
