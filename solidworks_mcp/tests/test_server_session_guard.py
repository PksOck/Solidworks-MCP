import asyncio
import unittest

from solidworks_mcp import server
from solidworks_mcp.core.contracts import DocumentRef
from solidworks_mcp.core.policy import OperationClass
from solidworks_mcp.core.session import TargetMismatchError
from solidworks_mcp.registry import _TOOLS, tool


class FakeAutomation:
    def __init__(self, mismatch=False):
        self.mismatch = mismatch
        self.draw_calls = 0

    def has_bound_document(self):
        return True

    def require_bound_active_document(self):
        if self.mismatch:
            raise TargetMismatchError("WRONG_DOCUMENT", "focus changed")
        return DocumentRef("doc-1", None, "part", "Default", "mcp:0")

    def bind_active_document(self):
        return DocumentRef("doc-1", None, "part", "Default", "mcp:0")

    def mark_active_document_mutated(self, before):
        return DocumentRef(
            before.document_id, before.path, before.document_type,
            before.configuration, "mcp:1",
        )

    def draw_line(self, *args):
        self.draw_calls += 1
        return self._result(True, "line")

    def _result(self, success, message, error_code=0, data=None):
        return {
            "success": success,
            "message": message,
            "error_code": int(error_code),
            "error_name": "test",
            "data": data or {},
        }


class ServerSessionGuardTests(unittest.TestCase):
    def setUp(self):
        self.original_automation = server.sw_automation

    def tearDown(self):
        server.sw_automation = self.original_automation
        _TOOLS.pop("_test_server_registered_mutation", None)

    def test_bind_active_document_is_advertised_and_returns_reference(self):
        server.sw_automation = FakeAutomation()

        names = [tool.name for tool in asyncio.run(server.list_tools())]
        response = asyncio.run(server.call_tool("bind_active_document", {}))

        self.assertIn("bind_active_document", names)
        self.assertIn('"document_id": "doc-1"', response[0].text)

    def test_all_advertised_tools_accept_optional_operation_id(self):
        advertised = asyncio.run(server.list_tools())

        for advertised_tool in advertised:
            with self.subTest(tool=advertised_tool.name):
                self.assertIn("operation_id", advertised_tool.inputSchema["properties"])
                self.assertNotIn("operation_id", advertised_tool.inputSchema.get("required", []))

    def test_legacy_mutation_rejects_focus_change_before_handler(self):
        automation = FakeAutomation(mismatch=True)
        server.sw_automation = automation

        response = asyncio.run(server.call_tool("draw_line", {}))

        self.assertIn("WRONG_DOCUMENT", response[0].text)
        self.assertEqual(0, automation.draw_calls)

    def test_duplicate_operation_id_replays_without_second_mutation(self):
        automation = FakeAutomation()
        server.sw_automation = automation
        operation = {"operation_id": "repeat-draw-1"}

        first = asyncio.run(server.call_tool("draw_line", operation))
        replay = asyncio.run(server.call_tool("draw_line", operation))

        self.assertEqual(1, automation.draw_calls)
        self.assertIn("repeat-draw-1", first[0].text)
        self.assertEqual(first[0].text, replay[0].text)

    def test_registered_mutation_reports_before_and_after_revisions(self):
        @tool(
            name="_test_server_registered_mutation",
            description="test",
            schema={"type": "object", "properties": {}, "required": []},
            operation_class=OperationClass.MUTATE,
        )
        def registered_mutation(sw):
            return sw._result(True, "changed")

        server.sw_automation = FakeAutomation()

        response = asyncio.run(server.call_tool(
            "_test_server_registered_mutation", {"operation_id": "registered-op-1"}
        ))

        self.assertIn('"revision_token": "mcp:0"', response[0].text)
        self.assertIn('"revision_token": "mcp:1"', response[0].text)


if __name__ == "__main__":
    unittest.main()
