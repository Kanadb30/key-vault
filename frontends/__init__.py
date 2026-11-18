"""Four inputs, one compiler AST. No storage dependencies."""
from dataclasses import dataclass

from sql_compiler.ast_nodes import Select


@dataclass
class Prepared:
    ast: Select
    sql: str
    artifact: dict
