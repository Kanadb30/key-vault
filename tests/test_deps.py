"""Check imports structurally, including imports inside functions."""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(("package", "forbidden"), [
    ("core", {"sql_compiler", "storage", "frontends", "api", "compose"}),
    ("sql_compiler", {"storage", "frontends", "api", "compose"}),
    ("storage", {"sql_compiler", "frontends", "api", "compose"}),
    ("frontends", {"storage", "api", "compose"}),
])
def test_dependency_direction(package, forbidden):
    for file in (ROOT / package).rglob("*.py"):
        for node in ast.walk(ast.parse(file.read_text(), filename=str(file))):
            imports = []
            if isinstance(node, ast.Import):
                imports = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imports = [node.module or ""]
            assert not {name.split(".")[0] for name in imports} & forbidden, file
