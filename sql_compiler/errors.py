"""Error envelope + codes (docs/bundle_schema.md — frozen v1).

Interface: ErrorEnvelope, CompilerError, format_error(env), caret_line(),
lark_error(exc).
Invariants: raw exceptions never cross a boundary — everything user-visible
is an envelope; envelope.message is the raw message; format_error prepends
the "Parse/Semantic error at line:col." prefix and ensures a trailing period.
Side effects: none.
"""
from __future__ import annotations

from dataclasses import dataclass

STAGES = ("lex", "parse", "bind", "plan", "optimize", "execute", "verify")

CODES = {
    "PARSE_UNEXPECTED_TOKEN",
    "PARSE_UNEXPECTED_CHAR",
    "BIND_UNKNOWN_TABLE",
    "BIND_UNKNOWN_COLUMN",
    "BIND_AMBIGUOUS_COLUMN",
    "BIND_TYPE_MISMATCH",
    "BIND_UNSUPPORTED_OP_FOR_TEXT",
    "BIND_INT_OUT_OF_RANGE",
    "BIND_DUPLICATE_TABLE_REF",
    "BIND_JOIN_MISMATCH",
    "VERIFY_MISMATCH",
    "INTERNAL",
}


@dataclass(frozen=True)
class ErrorEnvelope:
    stage: str
    code: str
    message: str
    locator: dict | None = None
    origin: str = "sql_compiler"

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "code": self.code,
            "message": self.message,
            "locator": self.locator,
            "origin": self.origin,
        }


class CompilerError(Exception):
    """The only exception type allowed to cross a pipeline boundary."""

    def __init__(self, envelope: ErrorEnvelope) -> None:
        super().__init__(envelope.message)
        self.envelope = envelope


def format_error(env: ErrorEnvelope) -> str:
    loc = env.locator or {}
    line, col = loc.get("line"), loc.get("col")
    label = (
        "Parse error" if env.stage in ("lex", "parse")
        else "Semantic error" if env.stage == "bind"
        else f"{env.stage.capitalize()} error"
    )
    prefix = f"{label} at {line}:{col}. " if line is not None and col is not None else f"{label}. "
    message = env.message if env.message.endswith(".") else env.message + "."
    return f"{prefix}{message}"


def caret_line(source: str, env: ErrorEnvelope) -> str | None:
    """The source line plus a caret under the offending column, README-style."""
    loc = env.locator or {}
    line, col = loc.get("line"), loc.get("col")
    if line is None or col is None:
        return None
    src_lines = source.splitlines()
    src_line = src_lines[line - 1] if 0 < line <= len(src_lines) else ""
    pad = " " * max(int(col) - 1, 0)
    return f"{src_line}\n{pad}^"


def lark_error(exc: Exception) -> ErrorEnvelope:
    """Normalize Lark's noisy parse errors into one clean envelope."""
    from lark.exceptions import UnexpectedInput, UnexpectedToken

    loc: dict = {"kind": "sql_span"}
    line = getattr(exc, "line", None)
    col = getattr(exc, "column", None)
    if line is not None:
        loc["line"] = int(line)
    if col is not None:
        loc["col"] = int(col)

    if isinstance(exc, UnexpectedToken):
        token = getattr(exc, "token", None)
        got = getattr(token, "value", None)
        if got is None:
            got = getattr(token, "type", "?")
        expected = list(getattr(exc, "expected", None) or [])
        message = "Unexpected end of input" if token.type == "$END" else f"Unexpected token {got!r}"
        if expected:
            preview = ", ".join(sorted(str(e) for e in expected)[:8])
            message += f". Expected one of: {preview}"
        if token is not None:
            start_pos = getattr(token, "start_pos", None)
            end_pos = getattr(token, "end_pos", None)
            if start_pos is not None:
                loc["char_start"] = int(start_pos)
            if end_pos is not None:
                loc["char_end"] = int(end_pos)
            for attr, key in (("end_line", "end_line"), ("end_column", "end_col")):
                value = getattr(token, attr, None)
                if value is not None:
                    loc[key] = int(value)
        return ErrorEnvelope(stage="parse", code="PARSE_UNEXPECTED_TOKEN", message=message, locator=loc)

    if isinstance(exc, UnexpectedInput):
        # UnexpectedCharacters and friends
        char = getattr(exc, "char", None)
        message = f"Unexpected character {char!r}" if char is not None else "Unexpected input"
        pos = getattr(exc, "pos_in_stream", None)
        if pos is not None:
            loc["char_start"] = int(pos)
            loc["char_end"] = int(pos) + 1
        return ErrorEnvelope(stage="lex", code="PARSE_UNEXPECTED_CHAR", message=message, locator=loc)

    return ErrorEnvelope(stage="parse", code="INTERNAL", message=f"{type(exc).__name__}: {exc}", locator=loc)
