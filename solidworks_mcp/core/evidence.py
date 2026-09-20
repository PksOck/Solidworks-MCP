"""In-memory operation journal used to make tool retries safe and explicit."""

from __future__ import annotations

from collections.abc import Callable

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
