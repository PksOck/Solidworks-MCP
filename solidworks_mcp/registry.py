"""
Tool registry for SolidWorks MCP server extensions.

Lets new tools be added by writing a single decorated function in
solidworks_mcp/tools/, without editing server.py. The 25 original tools stay
in server.py and are not affected.
"""

import logging
from typing import Callable, Dict, List, Optional

from mcp.types import Tool

from .constants import SwErrors
from .core.policy import OperationClass
from .core.session import TargetMismatchError

logger = logging.getLogger("SolidWorksMCP")

_TOOLS: Dict[str, Dict] = {}
_loaded = False


def tool(
    name: str,
    description: str,
    schema: Dict,
    operation_class: OperationClass,
) -> Callable:
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
            "handler": fn,
            "operation_class": operation_class,
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


def operation_class_for(name: str) -> OperationClass | None:
    """Return declared execution semantics for a registered tool."""
    _load()
    entry = _TOOLS.get(name)
    return entry["operation_class"] if entry is not None else None


def dispatch(name: str, sw, arguments: Dict, *, preflight: bool = True) -> Optional[Dict]:
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
    operation_class = entry["operation_class"]
    guarded_classes = {
        OperationClass.STATEFUL_READ,
        OperationClass.MUTATE,
        OperationClass.EXPORT,
    }
    before = None
    if preflight and operation_class in guarded_classes and hasattr(sw, "bind_active_document"):
        try:
            if hasattr(sw, "has_bound_document") and sw.has_bound_document():
                before = sw.require_bound_active_document()
            else:
                before = sw.bind_active_document()
        except TargetMismatchError as error:
            detail = error.operation_error
            return sw._result(
                False,
                str(error),
                SwErrors.swInvalidInput,
                {"code": detail.code, "retryable": detail.retryable},
            )
    result = entry["handler"](sw, **arguments)
    if result is None:
        raise ValueError(f"Tool returned no result: {name}")
    if (
        before is not None
        and preflight
        and operation_class is OperationClass.MUTATE
        and result.get("success")
        and hasattr(sw, "mark_active_document_mutated")
    ):
        sw.mark_active_document_mutated(before)
    return result
