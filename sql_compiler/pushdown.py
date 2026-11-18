"""Predicate pushdown rewrite (README §3 rewrite rule), emitting the diff as data.

Interface: apply_pushdown(plan) -> (pre, post, moved) — never mutates the
input; pre/post are deep copies, `moved` is the diff-as-data record list
(docs/bundle_schema.md).
Invariants: applies to a Filter directly above an inner equijoin; each AND
term is attributed by its bound table and pushed to the input that supplies
its columns (terms spanning both inputs are kept above the join — cannot
arise in the v1 grammar, kept for safety); the join's ON condition is
unchanged; surviving nodes keep their node_id, new Filters get fresh ids.
Side effects: none.
"""
from __future__ import annotations

import copy

from .binder import BoundCompare
from .plan import Filter, Join, Project, _NodeIds, max_node_id


def apply_pushdown(plan: Project) -> tuple[Project, Project, list[dict]]:
    pre = copy.deepcopy(plan)
    post = copy.deepcopy(plan)
    moved: list[dict] = []
    ids = _NodeIds(max_node_id(post))
    _rewrite(post, moved, ids)
    return pre, post, moved


def _rewrite(node, moved: list[dict], ids: _NodeIds):
    if isinstance(node, Project):
        node.child = _rewrite(node.child, moved, ids)
        return node

    if isinstance(node, Filter):
        child = node.child
        if isinstance(child, Join):
            join = child
            left_terms: list[BoundCompare] = []
            left_ids: list[str] = []
            right_terms: list[BoundCompare] = []
            right_ids: list[str] = []
            kept_terms: list[BoundCompare] = []
            kept_ids: list[str] = []
            records: dict[str, dict] = {}
            for term, term_id in zip(node.terms, node.term_ids):
                refs = {term.column.table}
                if refs <= join.left.tables:
                    left_terms.append(term)
                    left_ids.append(term_id)
                    target = "left"
                elif refs <= join.right.tables:
                    right_terms.append(term)
                    right_ids.append(term_id)
                    target = "right"
                else:
                    kept_terms.append(term)
                    kept_ids.append(term_id)
                    target = "kept"
                records[term_id] = {
                    "term_id": term_id,
                    "term": term.label(),
                    "target": target,
                    "from_node_id": node.node_id,
                    "to_node_id": None,
                }
            new_left = Filter(tuple(left_terms), tuple(left_ids), join.left, ids.next()) if left_terms else join.left
            new_right = (
                Filter(tuple(right_terms), tuple(right_ids), join.right, ids.next()) if right_terms else join.right
            )
            new_join = Join(join.on_left, join.on_right, new_left, new_right, join.node_id)
            for term_id in left_ids:
                records[term_id]["to_node_id"] = new_left.node_id
            for term_id in right_ids:
                records[term_id]["to_node_id"] = new_right.node_id
            for term_id in kept_ids:
                records[term_id]["to_node_id"] = node.node_id
            moved.extend(records.values())
            if kept_terms:
                return Filter(tuple(kept_terms), tuple(kept_ids), new_join, node.node_id)
            return new_join
        node.child = _rewrite(node.child, moved, ids)
        return node

    if isinstance(node, Join):
        node.left = _rewrite(node.left, moved, ids)
        node.right = _rewrite(node.right, moved, ids)
        return node

    return node  # Scan — nothing below it
