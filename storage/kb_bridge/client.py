from collections import deque
import json
import os
from pathlib import Path
import selectors
import subprocess
import threading
import time

from core.types import Column, Relation, TableSchema, validate_rows

MAX_LINE = 8 * 1024 * 1024


class BridgeError(Exception):
    stage = "bridge"
    origin = "kb_bridge"

    def __init__(self, code, message, diagnostics=None):
        super().__init__(message)
        self.code = code
        self.diagnostics = diagnostics or {}


class KbAdapter:
    backend_name = "kb_db"

    def __init__(self, binary, db_path, *, timeout=5):
        self.timeout = timeout
        self.fixture_set = None
        self._lock = threading.RLock()
        self._buffer = bytearray()
        self._stderr = deque(maxlen=32)
        self._log = deque(maxlen=32)
        self._id = 0
        self._closed = False
        self._process = subprocess.Popen(
            [str(Path(binary).resolve()), "--bridge", "--db", str(Path(db_path).resolve())],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
        )
        os.set_blocking(self._process.stdin.fileno(), False)
        self._selector = selectors.DefaultSelector()
        self._selector.register(self._process.stdout, selectors.EVENT_READ)
        self._thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._thread.start()
        try:
            hello = self._read()
            if hello.get("type") == "error":
                self._fail(hello.get("code", "BRIDGE_STARTUP"), hello.get("message", "Engine startup failed"))
            if (hello.get("type") != "hello" or type(hello.get("protocol")) is not int or
                hello["protocol"] != 1 or hello.get("min_protocol") != 1 or
                hello.get("engine") != "kb_db" or hello.get("format_version") != 1):
                self._fail("BRIDGE_PROTOCOL_MISMATCH", "Expected kb_db protocol 1 / disk format 1")
            self._send({"type": "ready", "protocol": 1})
        except Exception as exc:
            self.close()
            if isinstance(exc, BridgeError):
                self._complete_diagnostics(exc)
            raise

    def _drain_stderr(self):
        # Bounded chunks, not readline(): a child can emit a huge line.
        while chunk := self._process.stderr.read(2048):
            self._stderr.append(chunk.decode("utf-8", errors="replace"))

    def _fail(self, code, message):
        raise BridgeError(code, message, {"stderr": "".join(self._stderr), "requests": list(self._log)})

    def _read(self, deadline=None):
        deadline = deadline or time.monotonic() + self.timeout
        if time.monotonic() >= deadline:
            self._fail("BRIDGE_TIMEOUT", "Engine request exceeded its time limit")
        while b"\n" not in self._buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not self._selector.select(max(0, remaining)):
                self._fail("BRIDGE_TIMEOUT", "Engine response timed out")
            chunk = os.read(self._process.stdout.fileno(), 65536)
            if not chunk:
                self._fail("BRIDGE_CHILD_EXIT", "Engine exited before completing its response")
            self._buffer.extend(chunk)
            if (b"\n" not in self._buffer and len(self._buffer) > MAX_LINE) or self._buffer.find(b"\n") > MAX_LINE:
                self._fail("BRIDGE_LINE_TOO_LARGE", "Engine response exceeds the 8 MiB line limit")
        raw, _, remainder = self._buffer.partition(b"\n")
        self._last_size = len(raw)
        self._buffer = bytearray(remainder)
        try:
            frame = json.loads(raw)
        except (ValueError, UnicodeError, RecursionError):
            self._fail("BRIDGE_BAD_JSON", "Engine emitted invalid JSON")
        if not isinstance(frame, dict):
            self._fail("BRIDGE_BAD_JSON", "Expected a JSON object frame")
        return frame

    def _send(self, frame):
        data = json.dumps(frame, ensure_ascii=False).encode() + b"\n"
        if len(data) > MAX_LINE:
            self._fail("BRIDGE_LINE_TOO_LARGE", "Request exceeds 8 MiB")
        with selectors.DefaultSelector() as writer:
            writer.register(self._process.stdin, selectors.EVENT_WRITE)
            view = memoryview(data)
            deadline = time.monotonic() + self.timeout
            while view:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not writer.select(max(remaining, 0)):
                    self._fail("BRIDGE_TIMEOUT", "Engine stopped reading requests")
                try:
                    count = os.write(self._process.stdin.fileno(), view)
                    view = view[count:]
                except BlockingIOError:
                    continue
                except (BrokenPipeError, OSError):
                    self._fail("BRIDGE_CHILD_EXIT", "Engine stdin closed")

    def _request(self, kind, **fields):
        with self._lock:
            self._id += 1
            request = {"type": kind, "id": self._id, **fields}
            self._log.append({"id": self._id, "type": kind, "table": fields.get("table")})
            try:
                deadline = time.monotonic() + self.timeout
                self._send(request)
                frames, response_bytes = [], 0
                while True:
                    frame = self._read(deadline)
                    response_bytes += self._last_size
                    if response_bytes > 64 * 1024 * 1024:
                        self._fail("BRIDGE_SCAN_LIMIT", "Scan response exceeds the 64 MiB demo limit")
                    if type(frame.get("id")) is not int or frame["id"] != self._id:
                        self._fail("BRIDGE_BAD_ID", "Engine response id does not match the request")
                    if frame.get("type") == "error":
                        self._fail(frame.get("code", "INTERNAL"), frame.get("message", "Engine error"))
                    if kind == "scan_table":
                        if frame.get("type") != "rows" or type(frame.get("done")) is not bool or not isinstance(frame.get("batch"), list):
                            self._fail("BRIDGE_BAD_FRAME", "Expected rows batch")
                        frames.append(frame)
                        if frame["done"]: return frames
                    else:
                        expected = "catalog" if kind == "open_catalog" else "ok"
                        if frame.get("type") != expected:
                            self._fail("BRIDGE_BAD_FRAME", f"Expected {expected}")
                        return frame
            except BridgeError as exc:
                if exc.code.startswith("BRIDGE_"):
                    self.close()  # Never reuse a desynchronized stream.
                    self._complete_diagnostics(exc)
                raise

    def _complete_diagnostics(self, exc):
        exc.diagnostics["stderr"] = "".join(self._stderr)
        exc.diagnostics["exit_code"] = self._process.returncode
        if exc.code == "BRIDGE_CHILD_EXIT" and self._process.returncode == 101:
            exc.code = "BRIDGE_CHILD_PANIC"

    def probe(self):
        return {"backend": "kb_db", "available": not self._closed and self._process.poll() is None, "protocol": 1, "fixture_set": self.fixture_set}

    def open_catalog(self):
        result = self._request("open_catalog")
        try:
            tables = result["tables"]
            catalog = {t["name"]: TableSchema(t["name"], tuple(Column(c["name"], c["type"]) for c in t["columns"])) for t in tables}
            if len(catalog) != len(tables): raise ValueError("duplicate table")
            return catalog
        except (KeyError, TypeError, ValueError):
            self._fail("BRIDGE_SCHEMA_MISMATCH", "Invalid engine catalog")

    def create_table(self, name, columns):
        self._request("create_table", name=name, columns=[{"name": c.name, "type": c.type} for c in columns])

    def insert_rows(self, table, rows):
        self._request("insert_rows", table=table, rows=rows)

    def scan(self, table):
        batches = self._request("scan_table", table=table)
        try:
            columns = tuple(Column(c["name"], c["type"]) for c in batches[0]["columns"])
            rows = []
            for batch in batches:
                if tuple(Column(c["name"], c["type"]) for c in batch["columns"]) != columns:
                    raise ValueError("schema changed during scan")
                validate_rows(columns, batch["batch"])
                rows.extend(tuple(row) for row in batch["batch"])
            return Relation(columns, tuple(rows))
        except (KeyError, TypeError, ValueError) as exc:
            self._fail("BRIDGE_SCHEMA_MISMATCH", str(exc))

    def close(self):
        if self._closed: return
        self._closed = True
        if self._process.stdin: self._process.stdin.close()
        try:
            self._process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=1)
        self._thread.join(timeout=1)
        self._selector.close()
        self._process.stdout.close()
        self._process.stderr.close()

    def __enter__(self): return self
    def __exit__(self, *exc): self.close()
