import asyncio
import json
import unittest

from solidworks_mcp import server

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


if __name__ == "__main__":
    unittest.main()
