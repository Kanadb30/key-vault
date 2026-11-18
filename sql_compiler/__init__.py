"""SQL query compiler and optimizer — the graded spine.

Public interface: run_query (via pipeline), bind, build_plan, apply_pushdown,
execute, SQLParser, error envelopes.

Dependency direction: imports core only — never storage, frontends, or api
(enforced by tests/test_deps.py). The composition root (compose.py at the
repo root) wires storage backends in.
"""
from .errors import CompilerError, ErrorEnvelope, format_error

__version__ = "0.1.0"

__all__ = ["CompilerError", "ErrorEnvelope", "format_error", "__version__"]
