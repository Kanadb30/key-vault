"""Bind first, then give the same socket to Uvicorn: no port-check race."""
import os
import socket

import uvicorn


def bind_socket():
    explicit = os.environ.get("PORT")
    preferred = int(explicit or 8001)
    if not 1024 <= preferred <= 65535:
        raise ValueError("PORT must be between 1024 and 65535")
    ports = [preferred] if explicit else range(preferred, min(preferred + 20, 65536))
    for port in ports:
        sock = socket.socket()
        try:
            sock.bind(("127.0.0.1", port))
            sock.listen(128)
            return sock
        except OSError:
            sock.close()
    raise OSError(f"No free demo port starting at {preferred}. Set PORT to a free port; no other process was stopped.")


def main():
    try:
        sock = bind_socket()
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    port = sock.getsockname()[1]
    print(f"\nSQL compiler console: http://127.0.0.1:{port}/", flush=True)
    print("API identity: /api/health → app: sql-compiler. Ctrl+C stops this demo only.\n", flush=True)
    try:
        uvicorn.Server(uvicorn.Config("api.server:app", host="127.0.0.1", port=port)).run(sockets=[sock])
    finally:
        sock.close()


if __name__ == "__main__":
    main()
