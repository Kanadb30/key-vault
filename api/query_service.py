"""Small facade: HTTP DTOs in, unchanged compiler bundles out.

Invariants: composition remains in compose.py, no session state or fallback
beyond the Runtime's own session dataset. Data errors become designed
envelopes, never a bare traceback.
Side effects: fixture/SQLite/engine work delegated to the composition root.
"""
from compose import Runtime, console_run, workspace
from .dto import DatasetRequest, InsertRequest, QueryRequest

# The browser console cannot represent larger integers in JSON round-trips.
BROWSER_MAX_INT = 2**53 - 1


class DataError(Exception):
    """A designed data-management failure surfaced as an HTTP error envelope."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class QueryService:
    def __init__(self):
        self.runtime = None

    def start(self):
        self.runtime = Runtime()

    def close(self):
        if self.runtime: self.runtime.close()

    def workspace(self) -> dict:
        return workspace(self.runtime)

    def run(self, request: QueryRequest) -> dict:
        bundle = console_run(
            request.source, frontend_id=request.frontend_id, backend=request.backend,
            runtime=self.runtime, verify=request.verify,
        )
        return {"v": 1, "bundle": bundle, "engine": self.runtime.engine_status() if self.runtime else {"available": False, "reason": "Runtime not started"}}

    def dataset(self, request: DatasetRequest) -> dict:
        if self.runtime is None:
            raise DataError("INTERNAL", "Runtime not started")
        try:
            snapshot = self.runtime.reset(request.dataset)
        except ValueError as exc:
            raise DataError("DATA_UNKNOWN_DATASET", str(exc)) from exc
        return {"v": 1, **snapshot}

    def insert(self, request: InsertRequest) -> dict:
        if self.runtime is None:
            raise DataError("INTERNAL", "Runtime not started")
        for row in request.rows:
            for value in row:
                if type(value) is int and abs(value) > BROWSER_MAX_INT:
                    raise DataError(
                        "DATA_INTEGER_PRECISION",
                        "Integers in the console must be within ±9007199254740991 "
                        "(JavaScript's safe range).",
                    )
        try:
            snapshot = self.runtime.insert_rows(request.table, request.rows)
        except KeyError as exc:
            raise DataError("DATA_UNKNOWN_TABLE", str(exc.args[0])) from exc
        except ValueError as exc:
            raise DataError("DATA_INVALID_ROW", str(exc)) from exc
        return {"v": 1, **snapshot}
