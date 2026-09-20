"""In-memory operation journal used to make tool retries safe and explicit."""

from __future__ import annotations

from collections.abc import Callable
import json
import os
from pathlib import Path
from typing import Any, Iterable

from .contracts import OperationResult


class OperationJournal:
    """Record one result per client operation id, including unknown outcomes."""

    def __init__(self) -> None:
        self._results: dict[str, OperationResult] = {}

    def get(self, operation_id: str) -> OperationResult | None:
        return self._results.get(operation_id)

    def record(self, result: OperationResult) -> OperationResult:
        existing = self._results.get(result.operation_id)
        if existing is not None:
            return existing
        self._results[result.operation_id] = result
        return result

    def run(self, operation_id: str, callback: Callable[[], OperationResult]) -> OperationResult:
        """Execute an operation once; never replay a known or unknown outcome."""

        existing = self.get(operation_id)
        if existing is not None:
            return existing
        result = callback()
        if result.operation_id != operation_id:
            raise ValueError("Callback result operation_id does not match requested operation_id.")
        return self.record(result)


class EvidenceValidationError(ValueError):
    """Raised when an evidence record would be ambiguous or non-verifiable."""


class EvidenceWriter:
    """Append redacted, schema-versioned operation evidence as JSONL."""

    _VERIFICATION_STATUSES = frozenset({"passed", "failed", "blocked", "not_run", "static_only"})

    def __init__(self, destination: Path, protected_roots: Iterable[Path] = ()) -> None:
        self.destination = destination
        self.protected_roots = tuple(str(root.resolve(strict=False)) for root in protected_roots)

    def _redact(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._redact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._redact(item) for item in value]
        if isinstance(value, str):
            normalized = os.path.normcase(value)
            for root in self.protected_roots:
                normalized_root = os.path.normcase(root)
                if normalized == normalized_root or normalized.startswith(normalized_root + os.sep):
                    suffix = value[len(root):].lstrip("\\/")
                    return "<protected-root>" + (f"/{suffix}" if suffix else "")
        return value

    def append(
        self, result: OperationResult, *, commit: str, verification_status: str
    ) -> dict[str, Any]:
        if verification_status not in self._VERIFICATION_STATUSES:
            raise EvidenceValidationError(f"Unknown verification status: {verification_status}")
        record = self._redact(
            {
                "schema_version": 1,
                "commit": commit,
                "verification_status": verification_status,
                "operation": result.to_dict(),
            }
        )
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        with self.destination.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        return record
