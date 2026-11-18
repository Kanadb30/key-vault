#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ ! -f "$ROOT/console/dist/index.html" ]]; then
  echo "Console not built. Run: npm --prefix \"$ROOT/console\" ci"
  echo "Then: npm --prefix \"$ROOT/console\" run build"
  exit 1
fi
exec uv run python -m demo.serve
