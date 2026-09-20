import importlib.util
import tempfile
import unittest
from pathlib import Path


def load_auditor():
    path = Path(__file__).parents[2] / "scripts" / "audit_capabilities.py"
    spec = importlib.util.spec_from_file_location("audit_capabilities", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CapabilityInventoryTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        (self.root / "solidworks_mcp" / "tools").mkdir(parents=True)

    def tearDown(self):
        self.tempdir.cleanup()

    def write(self, relative_path, content):
        path = self.root / relative_path
        path.write_text(content, encoding="utf-8")

    def test_discovers_server_tool_and_decorated_tool_without_importing_fixture(self):
        self.write(
            "solidworks_mcp/server.py",
            'TOOLS = [Tool(name="open_document", description="opens")]\n',
        )
        self.write(
            "solidworks_mcp/tools/extension.py",
            '@tool(name="export_pdf", description="exports", schema={})\ndef export_pdf(sw):\n    return {}\n',
        )
        self.write(
            "solidworks_mcp/tools/internal.py",
            'def helper():\n    raise RuntimeError("must never be imported")\n',
        )

        capabilities = load_auditor().audit_repository(self.root)

        self.assertEqual(["export_pdf", "open_document"], [item.name for item in capabilities])
        self.assertEqual("decorated", capabilities[0].registration)
        self.assertEqual("server_tool", capabilities[1].registration)

    def test_reports_duplicate_public_names(self):
        self.write("solidworks_mcp/server.py", 'TOOLS = [Tool(name="open_document")]\n')
        self.write(
            "solidworks_mcp/tools/extension.py",
            '@tool(name="open_document", description="duplicate", schema={})\ndef duplicate(sw):\n    return {}\n',
        )

        report = load_auditor().audit_report(self.root)

        self.assertEqual(["open_document"], report["duplicates"])
        self.assertEqual(2, len(report["capabilities"]))


if __name__ == "__main__":
    unittest.main()
