import unittest

from solidworks_mcp.core.policy import OperationClass
from solidworks_mcp.registry import _TOOLS, _load, operation_class_for, tool_module_for

READ, SESSION, MUTATE = OperationClass.READ, OperationClass.SESSION, OperationClass.MUTATE


class MovedToolTests(unittest.TestCase):
    def assertMoved(self, module, expected):
        _load()
        for name, (operation_class, postflight) in expected.items():
            with self.subTest(tool=name):
                self.assertEqual(f"solidworks_mcp.tools.{module}", tool_module_for(name))
                self.assertIs(operation_class, operation_class_for(name))
                self.assertEqual(postflight, _TOOLS[name]["postflight"])

    def test_features_basic(self):
        self.assertMoved("features_basic", {
            "extrude_sketch": (MUTATE, None), "cut_extrude": (MUTATE, None),
            "revolve_sketch": (MUTATE, None), "fillet_edges": (MUTATE, None),
            "chamfer_edges": (MUTATE, None), "list_features": (READ, None),
        })


if __name__ == "__main__":
    unittest.main()
