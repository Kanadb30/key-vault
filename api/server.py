"""Serve the API and prebuilt console on one localhost origin.

Run: uv run uvicorn api.server:app --host 127.0.0.1 --port 8000
Invariants: v1 DTOs, bounded request bodies, structured HTTP errors; no CORS
needed for the prebuilt demo. A warm engine is owned by the app lifespan.
Side effects: HTTP service, static-file reads, compiler/SQLite work.
"""
from pathlib import Path
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .dto import DatasetRequest, InsertRequest, QueryRequest
from .query_service import DataError, QueryService

DIST = Path(__file__).resolve().parents[1] / "console" / "dist"
MAX_BODY_BYTES = 128 * 1024


def http_error(code: str, message: str) -> dict:
    return {"v": 1, "errors": [{
        "stage": "console", "code": code, "message": message,
        "locator": None, "origin": "console",
    }]}


class BoundedBody:
    """Enforce the body cap even for requests without Content-Length."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        messages = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > MAX_BODY_BYTES:
                response = JSONResponse(
                    http_error("REQUEST_TOO_LARGE", "Request exceeds the 128 KiB limit"),
                    status_code=413,
                )
                return await response(scope, receive, send)
            messages.append(message)
            if not message.get("more_body", False):
                break
        iterator = iter(messages)

        async def replay():
            try:
                return next(iterator)
            except StopIteration:
                return await receive()

        await self.app(scope, replay, send)


def create_app(*, dist: Path = DIST) -> FastAPI:
    service = QueryService()
    @asynccontextmanager
    async def lifespan(app):
        service.start()
        try: yield
        finally: service.close()
    app = FastAPI(title="SQL Compiler Console", version="0.1.0", lifespan=lifespan)
    app.add_middleware(BoundedBody)

    @app.middleware("http")
    async def response_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        return JSONResponse(http_error("REQUEST_INVALID", problems), status_code=422)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        logging.getLogger(__name__).error("Console request failed", exc_info=exc)
        return JSONResponse(http_error(
            "INTERNAL", "The console could not complete this request. Check the server log and retry.",
        ), status_code=500)

    @app.get("/api/health")
    def health():
        return {"v": 1, "app": "sql-compiler", "status": "ok", "backend": "fixtures",
                "engine_available": bool(service.runtime and service.runtime.engine_status()["available"])}

    @app.get("/api/workspace")
    def get_workspace():
        return service.workspace()

    @app.post("/api/query")
    def query(request: QueryRequest):
        return service.run(request)

    def guarded(action):
        try:
            return action()
        except DataError as exc:
            return JSONResponse(http_error(exc.code, exc.message), status_code=400)

    @app.post("/api/data/dataset")
    def select_dataset(request: DatasetRequest):
        return guarded(lambda: service.dataset(request))

    @app.post("/api/data/insert")
    def insert_rows(request: InsertRequest):
        return guarded(lambda: service.insert(request))

    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="console")
    else:
        @app.get("/")
        def not_built():
            return JSONResponse(http_error(
                "CONSOLE_NOT_BUILT", "Build the console first: npm --prefix console ci && npm --prefix console run build",
            ), status_code=503)
    return app


app = create_app()
