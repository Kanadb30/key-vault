"""Lexer + LALR parser + AST transformer (README §1–§2, grammar verbatim).

Interface: SQLParser.parse(text) -> ast_nodes.Select (raises CompilerError on
lex/parse errors); SQLParser.tokenize(text) -> list[Token].
Invariants: keywords case-insensitive; identifiers case-preserved (the binder
lowercases); every node carries a SqlSpan with char offsets AND line:col.
Side effects: none.
"""
from __future__ import annotations

from pathlib import Path

from lark import Lark, Token, Transformer, v_args
from lark.exceptions import UnexpectedInput

from . import ast_nodes as ast
from .errors import CompilerError, lark_error

_GRAMMAR_PATH = Path(__file__).with_name("grammar.lark")


@v_args(meta=True)
class _SQLTransformer(Transformer):
    def _loc(self, meta) -> ast.SqlSpan:
        return ast.SqlSpan(
            char_start=getattr(meta, "start_pos", None),
            char_end=getattr(meta, "end_pos", None),
            line=getattr(meta, "line", None),
            col=getattr(meta, "column", None),
            end_line=getattr(meta, "end_line", None),
            end_col=getattr(meta, "end_column", None),
        )

    def start(self, meta, items):
        columns = items[0]
        from_table = items[1]
        rest = items[2:]
        join = next((i for i in rest if isinstance(i, ast.JoinClause)), None)
        where = next((i for i in rest if isinstance(i, tuple)), ())
        return ast.Select(
            columns=columns,
            from_table=from_table,
            join=join,
            where=where,
            locator=self._loc(meta),
        )

    def select_list(self, meta, items):
        return tuple(items)

    def table_ref(self, meta, items):
        return ast.TableRef(name=str(items[0]), locator=self._loc(meta))

    def join_clause(self, meta, items):
        # table_ref has already been transformed; keep its precise name span.
        table = items[0]
        return ast.JoinClause(
            table=table.name,
            table_locator=table.locator,
            on_left=items[1],
            on_right=items[3],
            locator=self._loc(meta),
        )

    def where_clause(self, meta, items):
        return tuple(items)

    def comparison(self, meta, items):
        # children: column_ref, Token(EQ|COMP_OP), literal
        return ast.Compare(
            column=items[0],
            op=str(items[1]),
            literal=items[2],
            locator=self._loc(meta),
        )

    def column_ref(self, meta, items):
        # children: [IDENT] or [IDENT, IDENT] (the anonymous DOT is filtered)
        if len(items) == 2:
            return ast.ColumnRef(qualifier=str(items[0]), name=str(items[1]), locator=self._loc(meta))
        return ast.ColumnRef(qualifier=None, name=str(items[0]), locator=self._loc(meta))

    def literal(self, meta, items):
        tok = items[0]
        if isinstance(tok, Token) and tok.type == "INT":
            return ast.IntLiteral(value=int(str(tok), 10), locator=self._loc(meta))
        raw = str(tok)[1:-1].replace("''", "'")
        return ast.StrLiteral(value=raw, locator=self._loc(meta))


class SQLParser:
    def __init__(self) -> None:
        self._lark = Lark(
            _GRAMMAR_PATH.read_text(encoding="utf-8"),
            parser="lalr",
            lexer="basic",
            propagate_positions=True,
            strict=True,
        )
        self._transformer = _SQLTransformer()

    def parse(self, text: str) -> ast.Select:
        try:
            tree = self._lark.parse(text)
        except UnexpectedInput as exc:
            raise CompilerError(lark_error(exc)) from exc
        return self._transformer.transform(tree)

    def tokenize(self, text: str) -> list[Token]:
        """Expose the real basic lexer; invalid characters fail at lex."""
        try:
            return list(self._lark.lex(text))
        except UnexpectedInput as exc:
            raise CompilerError(lark_error(exc)) from exc
