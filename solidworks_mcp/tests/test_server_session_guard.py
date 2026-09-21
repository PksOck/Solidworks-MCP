import asyncio
import unittest

from solidworks_mcp import server
from solidworks_mcp.core.contracts import DocumentRef
from solidworks_mcp.core.session import TargetMismatchError


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

    def test_bind_active_document_is_advertised_and_returns_reference(self):
        server.sw_automation = FakeAutomation()

        names = [tool.name for tool in asyncio.run(server.list_tools())]
        response = asyncio.run(server.call_tool("bind_active_document", {}))

        self.assertIn("bind_active_document", names)
        self.assertIn('"document_id": "doc-1"', response[0].text)

    def test_legacy_mutation_rejects_focus_change_before_handler(self):
        automation = FakeAutomation(mismatch=True)
        server.sw_automation = automation

        response = asyncio.run(server.call_tool("draw_line", {}))

        self.assertIn("WRONG_DOCUMENT", response[0].text)
        self.assertEqual(0, automation.draw_calls)


if __name__ == "__main__":
    unittest.main()
