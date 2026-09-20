"""Pure document-target validation and legacy result adaptation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .contracts import DocumentRef, OperationError, OperationResult, OperationStatus


class TargetMismatchError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.operation_error = OperationError(code=code, message=message, retryable=False)


@dataclass(frozen=True)
class SessionTarget:
    document_id: str
    canonical_path: str
    document_type: str
    configuration: str | None
    revision_token: str | None

    @classmethod
    def from_document(cls, document: DocumentRef) -> "SessionTarget":
        return cls(
            document_id=document.document_id,
            canonical_path=document.path,
            document_type=document.document_type,
            configuration=document.configuration,
            revision_token=document.revision_token,
        )


class SessionState:
    def __init__(self) -> None:
        self.target: SessionTarget | None = None

    def bind(self, document: DocumentRef) -> SessionTarget:
        self.target = SessionTarget.from_document(document)
        return self.target


def require_target(target: SessionTarget, actual: DocumentRef) -> None:
    """Reject a focus/configuration/revision change before calling COM."""

    if target.document_id != actual.document_id or target.canonical_path != actual.path:
        raise TargetMismatchError("WRONG_DOCUMENT", "The active document differs from the bound target.")
    if target.configuration != actual.configuration:
        raise TargetMismatchError("WRONG_DOCUMENT", "The active configuration differs from the bound target.")
    if target.revision_token != actual.revision_token:
        raise TargetMismatchError("STALE_REFERENCE", "The document revision differs from the bound target.")


def with_operation_metadata(
    legacy: Mapping[str, Any],
    *,
    operation_id: str,
    target_before: DocumentRef | None,
    target_after: DocumentRef | None,
    status: OperationStatus,
    warnings: tuple[str, ...] = (),
    errors: tuple[OperationError, ...] = (),
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Add the v1 envelope to an existing MCP response without removing fields."""

    result = OperationResult(
        operation_id=operation_id,
        status=status,
        target_before=target_before,
        target_after=target_after,
        data=dict(legacy.get("data", {})),
        warnings=warnings,
        errors=errors,
        evidence=dict(evidence or {}),
    )
    return result.to_dict(legacy=legacy)
