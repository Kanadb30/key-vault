"""Recursive interpreter (README §4) with per-node, per-plan-version stats.

Interface: execute(plan_root, adapter, registry) -> ExecResult(columns, rows,
stats ordered by node_id).
Invariants: the Scan operator is the single owner of row keying
(("table","column") tuples); rows preserve order and duplicates end to end;
join_pairs_tried is incremented *before* testing the ON condition; each run
starts with a fresh stats table; adapter relations are re-validated against
the registry on every scan (loud drift detection).
Side effects: reads through adapter.scan (I/O on real backends).
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from .binder import BoundCompare
from .plan import Filter, Join, Project, Scan


@dataclass
class NodeStat:
    node_id: int
    operator: str
    label: str
    rows_in: int | None = None
    left_in: int | None = None
    right_in: int | None = None
    rows_out: int = 0
    join_pairs_tried: int = 0
    join_pairs_matched: int = 0
    time_ns: int = 0

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "operator": self.operator,
            "label": self.label,
            "rows_in": self.rows_in,
            "left_in": self.left_in,
            "right_in": self.right_in,
            "rows_out": self.rows_out,
            "join_pairs_tried": self.join_pairs_tried,
            "join_pairs_matched": self.join_pairs_matched,
            "time_ns": self.time_ns,
        }


@dataclass
class ExecResult:
    columns: list[str]
    rows: list[tuple]
    stats: list[NodeStat]

    def stat(self, operator: str) -> NodeStat | None:
        for s in self.stats:
            if s.operator == operator:
                return s
        return None


_OPS = {
    "=": lambda a, b: a == b,
    "<>": lambda a, b: a != b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
}


def _passes(row: dict, cmp: BoundCompare) -> bool:
    value = row[(cmp.column.table, cmp.column.column)]
    return _OPS[cmp.op](value, cmp.literal_value)


def execute(root, adapter, registry) -> ExecResult:
    stats: dict[int, NodeStat] = {}

    def run(node) -> tuple[list, list[str] | None]:
        st = NodeStat(node.node_id, node.operator, node.label())
        stats[node.node_id] = st
        started = time.perf_counter_ns()
        if isinstance(node, Scan):
            relation = adapter.scan(node.table)
            registry.validate_relation(node.table, relation)
            keyed = [
                dict(zip(((node.table, c.name) for c in relation.columns), row))
                for row in relation.rows
            ]
            st.rows_out = len(keyed)
            st.time_ns = time.perf_counter_ns() - started
            return keyed, None

        if isinstance(node, Filter):
            rows, _ = run(node.child)
            st.rows_in = len(rows)
            kept = [r for r in rows if all(_passes(r, t) for t in node.terms)]
            st.rows_out = len(kept)
            st.time_ns = time.perf_counter_ns() - started
            return kept, None

        if isinstance(node, Join):
            left, _ = run(node.left)
            right, _ = run(node.right)
            st.left_in = len(left)
            st.right_in = len(right)
            st.rows_in = len(left) + len(right)
            lkey = node.on_left.key()
            rkey = node.on_right.key()
            out: list[dict] = []
            match = _OPS["="]
            for lrow in left:
                lval = lrow[lkey]
                for rrow in right:
                    st.join_pairs_tried += 1
                    if match(lval, rrow[rkey]):
                        st.join_pairs_matched += 1
                        out.append({**lrow, **rrow})
            st.rows_out = len(out)
            st.time_ns = time.perf_counter_ns() - started
            return out, None

        if isinstance(node, Project):
            rows, _ = run(node.child)
            st.rows_in = len(rows)
            names = [c.column for c in node.columns]
            labels = [
                c.column if names.count(c.column) == 1 else c.qualified()
                for c in node.columns
            ]
            out = [tuple(r[c.key()] for c in node.columns) for r in rows]
            st.rows_out = len(out)
            st.time_ns = time.perf_counter_ns() - started
            return out, labels

        raise ValueError(f"unknown plan node {node!r}")

    rows, labels = run(root)
    return ExecResult(
        columns=list(labels or []),
        rows=list(rows),
        stats=[stats[node_id] for node_id in sorted(stats)],
    )
