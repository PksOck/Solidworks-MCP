import asyncio
import json
import unittest
from pathlib import Path

from solidworks_mcp import server
from solidworks_mcp.knowledge import library

WORKFLOWS = Path(library.EXPERT) / "workflows"

FULL_CATALOG_BUDGET = 121_000


def catalog_bytes(tools):
    """Bytes a client loads for these tool definitions."""
    return sum(
        len(json.dumps({"name": item.name, "description": item.description,
                        "inputSchema": item.inputSchema}, ensure_ascii=False).encode("utf-8"))
        for item in tools
    )


class CatalogBudgetTests(unittest.TestCase):
    def test_full_catalog_stays_within_budget(self):
        tools = asyncio.run(server.list_tools())
        self.assertLessEqual(catalog_bytes(tools), FULL_CATALOG_BUDGET)

    def test_server_instructions_fit_the_client_limit(self):
        self.assertLessEqual(len(library.server_instructions()), 1_900)

    def test_instructions_keep_the_entry_points(self):
        text = library.server_instructions()
        for phrase in ("get_modeling_guide", "workflow/operating", "workflow/project-copy",
                       "workflow/parameter-ui", "workflow/engineering-package",
                       "list_components(mode=\"fast\", depth=1)", "operation_id",
                       "custom properties"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_details_removed_from_instructions_live_in_guides(self):
        project_copy = (WORKFLOWS / "project-copy.md").read_text(encoding="utf-8")
        parameter_ui = (WORKFLOWS / "parameter-ui.md").read_text(encoding="utf-8")
        package = (WORKFLOWS / "engineering-package.md").read_text(encoding="utf-8")
        self.assertIn("Shrani kot", project_copy)
        self.assertIn("lastnost", parameter_ui)
        self.assertIn("does not prove the user's desktop displays it", package)
        self.assertIn("process_parameter_workspace_job", package)
        self.assertIn("never promises rollback", package)


if __name__ == "__main__":
    unittest.main()
