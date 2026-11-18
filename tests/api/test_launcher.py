import socket

import pytest

from demo.serve import bind_socket


def test_explicit_port_conflict_does_not_stop_the_other_service(monkeypatch):
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        monkeypatch.setenv("PORT", str(occupied.getsockname()[1]))
        with pytest.raises(OSError, match="no other process was stopped"):
            bind_socket()
        assert occupied.fileno() != -1


def test_explicit_free_port_is_retained_for_uvicorn(monkeypatch):
    # PORT 0 is intentionally forbidden for human-readable demo URLs.
    monkeypatch.setenv("PORT", "0")
    with pytest.raises(ValueError, match="between"):
        bind_socket()
