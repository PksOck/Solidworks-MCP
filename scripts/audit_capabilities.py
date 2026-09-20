"""Statically inventory MCP tools without importing the SolidWorks server."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any


class Capability:
    def __init__(self, name: str, registration: str, source: str, line: int, handler: str | None = None):
        self.name = name
        self.registration = registration
        self.source = source
        self.line = line
        self.handler = handler

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "registration": self.registration,
            "source": self.source,
            "line": self.line,
            "handler": self.handler,
            "verification": "static_only",
        }


def _call_name(call: ast.Call) -> str | None:
    for keyword in call.keywords:
        if keyword.arg == "name" and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            return keyword.value.value
    return None


def _is_named(call: ast.Call, expected: str) -> bool:
    if isinstance(call.func, ast.Name):
        return call.func.id == expected
    if isinstance(call.func, ast.Attribute):
        return call.func.attr == expected
    return False


def _scan_file(path: Path, root: Path) -> list[Capability]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    source = path.relative_to(root).as_posix()
    found: list[Capability] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_named(node, "Tool"):
            name = _call_name(node)
            if name:
                found.append(Capability(name, "server_tool", source, node.lineno))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call) and _is_named(decorator, "tool"):
                    name = _call_name(decorator)
                    if name:
                        found.append(Capability(name, "decorated", source, node.lineno, node.name))
    return found


def audit_repository(root: Path) -> list[Capability]:
    """Return public MCP capability declarations from source only (no imports)."""

    root = root.resolve()
    paths = [root / "solidworks_mcp" / "server.py"]
    tools_dir = root / "solidworks_mcp" / "tools"
    if tools_dir.exists():
        paths.extend(sorted(tools_dir.rglob("*.py")))
    found: list[Capability] = []
    for path in paths:
        if path.exists():
            found.extend(_scan_file(path, root))
    return sorted(found, key=lambda item: (item.name, item.source, item.line))


def audit_report(root: Path) -> dict[str, Any]:
    capabilities = audit_repository(root)
    counts: dict[str, int] = {}
    for capability in capabilities:
        counts[capability.name] = counts.get(capability.name, 0) + 1
    return {
        "verification": "static_only",
        "capabilities": [capability.to_dict() for capability in capabilities],
        "duplicates": sorted(name for name, count in counts.items() if count > 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--format", choices=("json",), default="json")
    args = parser.parse_args()
    print(json.dumps(audit_report(args.root), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
