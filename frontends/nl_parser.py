"""Basic lexer + strict LALR parser + NL AST transformer, with real source spans."""
from dataclasses import replace
import json
from pathlib import Path

from lark import Lark, Token, Transformer, v_args
from lark.exceptions import UnexpectedInput, VisitError

from sql_compiler.ast_nodes import NlSpan
from sql_compiler.bundle import token_artifact
from sql_compiler.errors import CompilerError, ErrorEnvelope, lark_error
from . import nl_ast as nl

GRAMMAR = Path(__file__).with_name("nl_grammar.lark").read_text()


def span(meta):
    return NlSpan(
        char_start=meta.start_pos, char_end=meta.end_pos,
        line=meta.line, col=meta.column, end_line=meta.end_line, end_col=meta.end_column,
    )


@v_args(meta=True)
class _Build(Transformer):
    def phrase(self, meta, items):
        return tuple(str(item) for item in items)

    def plain_field(self, meta, items):
        return nl.Field(next(item for item in items if isinstance(item, tuple)), None, "words", span(meta))

    def qualified_field(self, meta, items):
        table, column = str(next(item for item in items if isinstance(item, Token) and item.type == "QUALIFIED")).split(".")
        return nl.Field((column,), (table,), "qualified", span(meta))

    def of_field(self, meta, items):
        phrases = [item for item in items if isinstance(item, tuple)]
        return nl.Field(phrases[0], phrases[-1], "of", span(meta))

    def possessive_field(self, meta, items):
        token = str(next(item for item in items if isinstance(item, Token) and item.type == "POSSESSED"))
        owner = token[:-2] if token.lower().endswith("'s") else token[:-1]
        words = next(item for item in items if isinstance(item, tuple))
        return nl.Field(words, (owner,), "possessive", span(meta))

    def table(self, meta, items):
        return nl.Table(items[0], span(meta))

    def projection(self, meta, items):
        return nl.Projection(tuple(item for item in items if isinstance(item, nl.Field)),
                             any(isinstance(item, Token) and item.type == "ALL" for item in items), span(meta))

    def command(self, meta, items):
        return str(items[0]).lower()

    def on_clause(self, meta, items):
        return tuple(item for item in items if isinstance(item, nl.Field))

    def source_clause(self, meta, items):
        return nl.Source(tuple(item for item in items if isinstance(item, nl.Table)),
                         next((item for item in items if isinstance(item, tuple)), None), span(meta))

    def literal(self, meta, items):
        token = items[0]
        if token.type == "INT":
            try:
                value = int(str(token))
            except ValueError:
                raise CompilerError(ErrorEnvelope("parse", "NL_INTEGER_TOO_LONG",
                    "Integer literal is too long; use a signed 64-bit integer", span(meta).to_dict(), "nl_frontend"))
            return nl.Literal(value, "integer", span(meta))
        raw = str(token)
        try:
            value = json.loads(raw) if raw.startswith('"') else raw[1:-1].replace("''", "'")
            value.encode("utf-8")
        except (ValueError, UnicodeError):
            raise CompilerError(ErrorEnvelope("parse", "NL_INVALID_LITERAL",
                "Invalid text literal; use valid quoted UTF-8 text and JSON escapes inside double quotes",
                span(meta).to_dict(), "nl_frontend"))
        return nl.Literal(value, "text", span(meta))

    def gt(self, meta, items): return nl.Operator(">", span(meta))
    def ge(self, meta, items): return nl.Operator(">=", span(meta))
    def lt(self, meta, items): return nl.Operator("<", span(meta))
    def le(self, meta, items): return nl.Operator("<=", span(meta))
    def eq(self, meta, items): return nl.Operator("=", span(meta))
    def ne(self, meta, items): return nl.Operator("<>", span(meta))

    def op_comparison(self, meta, items):
        return nl.Comparison(items[0], items[1], items[2], span(meta))

    def copula_comparison(self, meta, items):
        return nl.Comparison(items[0], items[2], items[3], span(meta))

    def is_comparison(self, meta, items):
        return nl.Comparison(items[0], nl.Operator("=", span(meta)), items[-1], span(meta))

    def between_comparison(self, meta, items):
        bounds = [item for item in items if isinstance(item, nl.Literal)]
        return nl.Between(items[0], bounds[0], bounds[1], span(meta))

    def where_clause(self, meta, items):
        return tuple(item for item in items if isinstance(item, (nl.Comparison, nl.Between)))

    def start(self, meta, items):
        return nl.Query(
            next(item for item in items if type(item) is str),
            next(item for item in items if isinstance(item, nl.Projection)),
            next((item for item in items if isinstance(item, nl.Source)), None),
            next((item for item in items if isinstance(item, tuple)), ()),
            span(meta),
        )


class NLParser:
    def __init__(self):
        self.parser = Lark(GRAMMAR, parser="lalr", lexer="basic", strict=True, propagate_positions=True)

    def _error(self, exc, source):
        env = lark_error(exc)
        locator = {**(env.locator or {}), "kind": "nl_span"}
        code, message = "NL_" + env.code, env.message
        if getattr(getattr(exc, "token", None), "type", None) == "$END":
            line = source.count("\n") + 1
            col = len(source.rsplit("\n", 1)[-1]) + 1
            locator = {"kind": "nl_span", "char_start": len(source), "char_end": len(source),
                       "line": line, "col": col, "end_line": line, "end_col": col}
        if str(getattr(exc, "token", "")).lower() == "or":
            code, message = "NL_UNSUPPORTED_CONJUNCTION", "OR conditions are not supported; use AND. 'Greater than or equal to' is supported as one comparison"
        return CompilerError(replace(env, code=code, message=message, locator=locator, origin="nl_frontend"))

    def tokenize(self, source):
        try:
            tokens = list(self.parser.lex(source))
        except UnexpectedInput as exc:
            raise self._error(exc, source) from exc
        artifacts = [token_artifact(token) for token in tokens]
        for artifact in artifacts:
            artifact["locator"]["kind"] = "nl_span"
        return artifacts

    def parse(self, source):
        try:
            return _Build().transform(self.parser.parse(source))
        except UnexpectedInput as exc:
            raise self._error(exc, source) from exc
        except VisitError as exc:
            if isinstance(exc.orig_exc, CompilerError):
                raise exc.orig_exc from exc
            if isinstance(exc.orig_exc, (ValueError, json.JSONDecodeError)):
                raise CompilerError(ErrorEnvelope("parse", "NL_INVALID_LITERAL",
                    "Invalid literal; use an integer or properly quoted text", None, "nl_frontend")) from exc
            raise
