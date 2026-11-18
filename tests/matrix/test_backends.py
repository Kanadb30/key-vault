import os
from pathlib import Path

import pytest

from compose import Runtime, FRONTEND_EXAMPLES, console_run


def test_four_frontends_times_three_backends():
    binary = os.environ.get("KB_DB_BIN")
    if not binary or not Path(binary).is_file():
        pytest.skip("Set KB_DB_BIN for the complete frontend/backend matrix")
    runtime = Runtime()
    try:
        assert runtime.engine_status()["available"], runtime.reason
        reference = None
        for backend in ["fixtures", "sqlite", "kb_db"]:
            for frontend, source in FRONTEND_EXAMPLES.items():
                bundle = console_run(source, frontend_id=frontend, backend=backend, runtime=runtime)
                assert not bundle["errors"], (backend, frontend, bundle["errors"])
                assert bundle["metrics"]["join_pairs_tried"] == {"pre": 12, "post": 6}
                assert bundle["provenance"]["backend"] == backend
                assert bundle["sqlite_cross_check"]["passed"]
                if reference is None: reference = bundle["rows"]
                assert bundle["rows"] == reference
    finally:
        runtime.close()


def test_compositional_nl_queries_across_all_storage_backends():
    binary = os.environ.get("KB_DB_BIN")
    if not binary or not Path(binary).is_file():
        pytest.skip("Set KB_DB_BIN for NL/backend equivalence")
    runtime = Runtime()
    try:
        for source in [
            "show student names and department names and marks where marks > 80",
            "please give me all students whose marks are between 80 and 90.",
            "list names and marks from students with marks at least 80 and name is not 'Ravi'",
        ]:
            reference = console_run(source, frontend_id="nl", runtime=runtime)
            for backend in ["fixtures", "sqlite", "kb_db"]:
                bundle = console_run(source, frontend_id="nl", backend=backend, runtime=runtime)
                assert bundle["errors"] == []
                assert bundle["rows"] == reference["rows"]
                assert bundle["plans"] == reference["plans"]
                assert bundle["sqlite_cross_check"]["passed"]
    finally:
        runtime.close()
