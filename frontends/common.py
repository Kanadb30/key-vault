import json
import re
from dataclasses import fields, is_dataclass, replace

from sql_compiler.ast_nodes import Locator
from sql_compiler.errors import CompilerError, ErrorEnvelope


def fail(code, message, locator=None):
    raise CompilerError(ErrorEnvelope(
        stage="parse", code=code, message=message,
        locator=locator.to_dict() if locator else None, origin="console",
    ))


def document(source):
    try:
        value = json.loads(source)
    except (ValueError, RecursionError) as exc:
        fail("FRONTEND_INVALID_JSON", f"Invalid JSON: {exc}")
    if not isinstance(value, dict):
        fail("FRONTEND_INVALID_JSON", "Expected a JSON object")
    return value


def identifier(value, loc=None, *, qualified=True):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?", value):
        fail("FRONTEND_INVALID_IDENTIFIER", "Use a table or column identifier, not SQL expressions", loc)
    if (not qualified and "." in value) or any(part.lower() in {"select", "from", "join", "on", "where", "and"} for part in value.split(".")):
        fail("FRONTEND_INVALID_IDENTIFIER", "Use an unreserved identifier; table names cannot be qualified", loc)
    return value.lower()


def literal(value, loc=None):
    if type(value) is int:
        return str(value)
    if type(value) is str:
        return "'" + value.replace("'", "''") + "'"
    fail("DSL_TYPE_MISMATCH", "Values must be INTEGER or TEXT; no floats, booleans, or nulls", loc)


def remap(value, locate, path="query"):
    if isinstance(value, Locator):
        return locate(path)
    if is_dataclass(value):
        return replace(value, **{field.name: remap(getattr(value, field.name), locate, f"{path}.{field.name}") for field in fields(value)})
    if isinstance(value, tuple):
        return tuple(remap(item, locate, f"{path}[{i}]") for i, item in enumerate(value))
    return value


def normalized_ast(value):
    """Semantic golden-test view: ignore locators, normalize identifier case."""
    if isinstance(value, Locator):
        return None
    if is_dataclass(value):
        return {
            field.name: (getattr(value, field.name).lower()
                if field.name in {"name", "qualifier", "table"} and isinstance(getattr(value, field.name), str)
                else normalized_ast(getattr(value, field.name)))
            for field in fields(value) if "locator" not in field.name
        }
    if isinstance(value, tuple):
        return [normalized_ast(item) for item in value]
    return value
