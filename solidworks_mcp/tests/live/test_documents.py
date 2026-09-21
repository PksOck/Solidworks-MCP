import os
import unittest

from solidworks_mcp.automation import SolidWorksAutomation
from solidworks_mcp.core.session import TargetMismatchError
from solidworks_mcp.tools.inspection import inspect_document


@unittest.skipUnless(
    os.environ.get("SW_MCP_LIVE_TESTS") == "1",
    "Set SW_MCP_LIVE_TESTS=1 to run SolidWorks COM tests.",
)
class LiveDocumentTargetTests(unittest.TestCase):
    def setUp(self):
        self.automation = SolidWorksAutomation()
        result = self.automation.connect()
        if not result["success"]:
            self.skipTest(result["message"])
        self.created_titles = []

    def tearDown(self):
        for title in reversed(self.created_titles):
            try:
                self.automation.app.CloseDoc(title)
            except Exception:
                pass
        self.automation.disconnect()

    def _new_part(self):
        result = self.automation.create_new_part()
        self.assertTrue(result["success"], result["message"])
        title = result["data"]["name"]
        self.created_titles.append(title)
        return title

    def test_focus_change_rejects_old_target_until_explicit_rebind(self):
        first_title = self._new_part()
        first = self.automation.bind_active_document()
        second_title = self._new_part()

        with self.assertRaises(TargetMismatchError) as raised:
            self.automation.require_bound_active_document()

        self.assertEqual("WRONG_DOCUMENT", raised.exception.operation_error.code)
        second = self.automation.bind_active_document()
        current = self.automation.require_bound_active_document()
        self.assertEqual(second.document_id, current.document_id)
        self.assertNotEqual(first.document_id, second.document_id)
        self.assertNotEqual(first_title, second_title)
        self.assertIsNone(first.path)
        self.assertIsNone(second.path)

    def test_two_connections_remain_on_the_same_com_owner_thread(self):
        owner = self.automation._com_owner_thread_id

        result = self.automation.connect()

        self.assertTrue(result["success"], result["message"])
        self.assertEqual(owner, self.automation._com_owner_thread_id)

    def test_inspect_unsaved_part_returns_versioned_summary_without_saving(self):
        self._new_part()

        result = inspect_document(self.automation, sections=["summary"])

        self.assertTrue(result["success"], result["message"])
        snapshot = result["data"]["snapshot"]
        self.assertEqual("part", snapshot["documents"][0]["document_type"])
        self.assertIsNone(snapshot["documents"][0]["path"])
        self.assertEqual("known", snapshot["observations"][0]["state"])


if __name__ == "__main__":
    unittest.main()
