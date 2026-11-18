"""Compositional NL compiler: lexer → parser → NL AST → shared query AST."""
from sql_compiler.bundle import json_value
from sql_compiler.errors import CompilerError, ErrorEnvelope

from . import Prepared
from .nl_lowering import Lowerer, to_sql
from .nl_parser import GRAMMAR, NLParser
from .nl_ast import render

_parser = NLParser()


def tokenize(source):
    return _parser.tokenize(source)


def prepare(source, *, registry=None, relationships=()):
    query = _parser.parse(source)
    artifact = {"nl_ast": json_value(query), "nl_ast_text": render(query), "nl_grammar": GRAMMAR, "nl_language_version": 1}
    if registry is None:
        raise CompilerError(ErrorEnvelope("parse", "NL_SCHEMA_REQUIRED",
            "NL lowering requires an injected schema registry", query.locator.to_dict(), "nl_frontend"))
    try:
        select, evidence = Lowerer(registry, relationships, source=source).lower(query)
    except CompilerError as exc:
        exc.artifact = artifact
        raise
    sql = to_sql(select)
    return Prepared(select, sql, {**artifact, "generated_sql": sql, "nl_lowering": evidence})
