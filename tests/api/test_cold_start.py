import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("attempt", [1, 2])
def test_real_launcher_serves_console_and_correct_api_twice(attempt):
    if not (ROOT / "console/dist/index.html").is_file():
        pytest.skip("Build the static console to test real cold starts")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, "-m", "demo.serve"], cwd=ROOT,
        env={**os.environ, "PORT": str(port)}, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 10
        while True:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.5) as response:
                    health = json.load(response)
                break
            except (urllib.error.URLError, TimeoutError):
                if process.poll() is not None or time.monotonic() > deadline:
                    pytest.fail("Demo did not start in ten seconds")
                time.sleep(0.05)
        assert health["app"] == "sql-compiler"
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as response:
            assert "<title>SQL Compiler" in response.read().decode()
    finally:
        process.terminate()
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=2)
