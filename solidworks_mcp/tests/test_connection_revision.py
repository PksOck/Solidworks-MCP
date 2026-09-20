import unittest
from unittest.mock import patch

from solidworks_mcp.automation.base import SolidWorksAutomation


class MethodRevisionApplication:
    def __init__(self):
        self.revision_calls = 0
        self.Visible = False

    def RevisionNumber(self):
        self.revision_calls += 1
        return "33.1.1"


class ConnectionRevisionTests(unittest.TestCase):
    def test_connect_calls_method_style_revision_number(self):
        app = MethodRevisionApplication()
        automation = SolidWorksAutomation()

        with patch("solidworks_mcp.automation.base.win32com.client.GetObject", return_value=app):
            self.assertTrue(automation._try_connect_com())

        self.assertEqual(1, app.revision_calls)


if __name__ == "__main__":
    unittest.main()
