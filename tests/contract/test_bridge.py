import os
from pathlib import Path
import sys

import pytest

from core.types import Column
from storage.fixtures import default_fixtures
from storage.kb_bridge import KbAdapter, BridgeError


@pytest.fixture
def binary():
    path = os.environ.get("KB_DB_BIN")
    if not path or not Path(path).is_file():
        pytest.skip("Set KB_DB_BIN to the built kb_db binary for cross-language contract tests")
    return path


def test_bridge_fixture_round_trip_and_reopen(binary, tmp_path):
    fixture, registry = default_fixtures()
    path = tmp_path / "persist.db"
    for first in [True, False]:
        with KbAdapter(binary, path) as adapter:
            if first:
                for name, schema in registry.tables().items():
                    adapter.create_table(name, schema.columns)
                    adapter.insert_rows(name, fixture.scan(name).rows)
            registry.validate_catalog(adapter.open_catalog())
            for name in registry.tables():
                assert adapter.scan(name) == fixture.scan(name)
            assert adapter.probe()["protocol"] == 1


def test_streamed_scan_spans_many_pages_and_batches(binary, tmp_path):
    columns = (Column("id", "INTEGER"), Column("name", "TEXT"))
    rows = tuple((i, "x" * 1000) for i in range(600))
    with KbAdapter(binary, tmp_path / "large.db") as adapter:
        adapter.create_table("items", columns)
        adapter.insert_rows("items", rows)
        assert adapter.scan("items").rows == rows


def test_typed_errors_do_not_desynchronize_bridge(binary, tmp_path):
    with KbAdapter(binary, tmp_path / "typed.db") as adapter:
        adapter.create_table("items", [Column("id", "INTEGER")])
        with pytest.raises(BridgeError, match="requires i64"):
            adapter.insert_rows("items", [[True]])
        adapter.insert_rows("items", [[1]])
        assert adapter.scan("items").rows == ((1,),)


@pytest.mark.parametrize(("output", "code"), [
    ("print('bad json',flush=True)", "BRIDGE_BAD_JSON"),
    ("print('{}',flush=True)", "BRIDGE_PROTOCOL_MISMATCH"),
    ("print('{\"type\":\"hello\",\"protocol\":true}',flush=True)", "BRIDGE_PROTOCOL_MISMATCH"),
    ("pass", "BRIDGE_CHILD_EXIT"),
])
def test_broken_child_handshakes_are_bounded(tmp_path, output, code):
    script = tmp_path / "fake-engine"
    script.write_text(f"#!{sys.executable}\n{output}\n")
    script.chmod(0o700)
    with pytest.raises(BridgeError) as caught:
        KbAdapter(script, tmp_path / "unused.db", timeout=0.2)
    assert caught.value.code == code


def test_child_timeout_is_bounded_and_diagnostics_capture_stderr(tmp_path):
    script = tmp_path / "slow-engine"
    script.write_text(f"#!{sys.executable}\nimport sys,time\nprint('engine startup failed',file=sys.stderr,flush=True)\ntime.sleep(5)\n")
    script.chmod(0o700)
    with pytest.raises(BridgeError) as caught:
        KbAdapter(script, tmp_path / "unused.db", timeout=0.05)
    assert caught.value.code == "BRIDGE_TIMEOUT"
    assert "engine startup failed" in caught.value.diagnostics["stderr"]


def test_child_panic_code_is_preserved(tmp_path):
    script = tmp_path / "panic-engine"
    script.write_text(f"#!{sys.executable}\nimport sys\nprint('panic reproduction',file=sys.stderr,flush=True)\nsys.exit(101)\n")
    script.chmod(0o700)
    with pytest.raises(BridgeError) as caught:
        KbAdapter(script, tmp_path / "unused.db", timeout=0.2)
    assert caught.value.code == "BRIDGE_CHILD_PANIC"
    assert caught.value.diagnostics["exit_code"] == 101
