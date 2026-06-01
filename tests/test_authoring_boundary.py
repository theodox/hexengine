"""Strict import boundary: runtime hexengine must not import hexengine.authoring."""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_HEXENGINE = _REPO_ROOT / "src" / "hexengine"

_ALLOWED_RUNTIME_IMPORTERS = frozenset(
    {
        "hooks/internal/authoring_bridge.py",
        "hooks/internal/contracts.py",
    }
)

_AUTHORING_PREFIX = "hexengine.authoring"


def _imports_authoring(module_path: Path, source: str) -> list[int]:
    rel = module_path.relative_to(_HEXENGINE).as_posix()
    if rel.startswith("authoring/"):
        return []
    if rel in _ALLOWED_RUNTIME_IMPORTERS:
        return []

    tree = ast.parse(source, filename=str(module_path))
    hits: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name == "hexengine.authoring" or name.startswith(
                    _AUTHORING_PREFIX + "."
                ):
                    hits.append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            if node.module and (
                node.module == "hexengine.authoring"
                or node.module.startswith("hexengine.authoring.")
            ):
                hits.append(node.lineno)
    return hits


def test_runtime_modules_do_not_import_authoring() -> None:
    violations: list[str] = []
    for path in _HEXENGINE.rglob("*.py"):
        rel = path.relative_to(_HEXENGINE).as_posix()
        if rel.startswith("authoring/"):
            continue
        text = path.read_text(encoding="utf-8")
        lines = _imports_authoring(path, text)
        for ln in lines:
            violations.append(f"{rel}:{ln}")
    assert not violations, "Runtime imports of hexengine.authoring:\n" + "\n".join(
        violations
    )
