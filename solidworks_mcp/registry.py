"""
Tool registry for SolidWorks MCP server extensions.

Lets new tools be added by writing a single decorated function in
solidworks_mcp/tools/, without editing server.py. The 25 original tools stay
in server.py and are not affected.
"""

import logging
from typing import Callable, Dict, List, Optional

from mcp.types import Tool

logger = logging.getLogger("SolidWorksMCP")

_TOOLS: Dict[str, Dict] = {}
_loaded = False


def tool(name: str, description: str, schema: Dict) -> Callable:
    """
    Register a function as an MCP tool.

    The handler receives the SolidWorksAutomation instance as its first
    argument, followed by the schema arguments as keywords, and returns a
    result dictionary built with sw._result().

    Args:
        name: Tool name, snake_case
        description: One sentence: what it does and what it acts on
        schema: JSON schema for the tool input

    Returns:
        Decorator that registers the function
    """
    def decorator(fn: Callable) -> Callable:
        if name in _TOOLS:
            raise ValueError(f"Tool already registered: {name}")
        _TOOLS[name] = {
            "tool": Tool(name=name, description=description, inputSchema=schema),
            "handler": fn
        }
        return fn
    return decorator


def _load() -> None:
    """Import the tools package once, so the decorators run"""
    global _loaded
    if _loaded:
        return
    try:
        from . import tools  # noqa: F401
    except Exception as e:
        logger.error(f"Failed to import tools package: {e}")
        raise
    _loaded = True


def registered_tools() -> List[Tool]:
    """All registered tool definitions"""
    _load()
    return [entry["tool"] for entry in _TOOLS.values()]


def dispatch(name: str, sw, arguments: Dict) -> Optional[Dict]:
    """
    Run a registered tool.

    Args:
        name: Tool name
        sw: SolidWorksAutomation instance
        arguments: Tool arguments

    Returns:
        Result dictionary, or None if no tool with that name is registered
    """
    _load()
    entry = _TOOLS.get(name)
    if entry is None:
        return None
    result = entry["handler"](sw, **arguments)
    if result is None:
        raise ValueError(f"Tool returned no result: {name}")
    return result
