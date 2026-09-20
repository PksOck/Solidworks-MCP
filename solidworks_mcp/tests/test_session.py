import unittest

from solidworks_mcp.core.contracts import DocumentRef, OperationStatus
from solidworks_mcp.core.session import SessionState, SessionTarget, TargetMismatchError, require_target, with_operation_metadata


def reference(document_id="doc-1", configuration="Default", revision="r1"):
    return DocumentRef(document_id, "C:/output/frame.SLDPRT", "part", configuration, revision)


class SessionTargetTests(unittest.TestCase):
    def test_binds_document_configuration_and_revision_snapshot(self):
        state = SessionState()
        target = state.bind(reference())

        self.assertEqual("doc-1", target.document_id)
        self.assertEqual("Default", target.configuration)

    def test_rejects_mismatched_document_before_operation(self):
        state = SessionState()
        target = state.bind(reference())

        with self.assertRaises(TargetMismatchError):
            require_target(target, reference(document_id="doc-2"))

    def test_rejects_stale_revision_before_operation(self):
        state = SessionState()
        target = state.bind(reference())

        with self.assertRaises(TargetMismatchError):
            require_target(target, reference(revision="r2"))

    def test_metadata_adapter_preserves_legacy_fields(self):
        result = with_operation_metadata(
            {"success": True, "message": "Saved", "error_code": 0, "data": {"legacy": 1}},
            operation_id="op-5",
            target_before=reference(),
            target_after=reference(revision="r2"),
            status=OperationStatus.COMPLETED,
        )

        self.assertTrue(result["success"])
        self.assertEqual("Saved", result["message"])
        self.assertEqual("completed", result["status"])
        self.assertEqual("r2", result["target_after"]["revision_token"])


if __name__ == "__main__":
    unittest.main()
