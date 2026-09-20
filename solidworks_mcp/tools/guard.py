"""Shared guarded-mode adapters for MCP tool handlers."""

from pathlib import Path

from ..constants import SwErrors
from ..core.policy import OperationClass, WriteDeniedError


def require_output_write(sw, output_path: str):
    """Return a legacy denial result before a tool touches COM, if guarded."""
    policy = getattr(sw, "_path_policy", None)
    if policy is None:
        return None
    try:
        policy.require_write(Path(output_path), OperationClass.EXPORT)
    except WriteDeniedError as error:
        return sw._result(False, f"Write denied: {error}", SwErrors.swExportError)
    return None
