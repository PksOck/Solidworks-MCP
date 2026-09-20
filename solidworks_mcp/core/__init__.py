"""Shared, COM-independent contracts for SolidWorks MCP operations."""

from .contracts import DocumentRef, OperationError, OperationResult, OperationStatus
from .evidence import OperationJournal

__all__ = [
    "DocumentRef",
    "OperationError",
    "OperationJournal",
    "OperationResult",
    "OperationStatus",
]
