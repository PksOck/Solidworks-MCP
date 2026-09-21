import tempfile
import unittest
from pathlib import Path

from solidworks_mcp.tools.assembly import insert_component


class FakeComponent:
    Name2 = "Component-1"


class FakeAssembly:
    GetType = 2

    def __init__(self):
        self.position = None

    def AddComponent5(self, filepath, options, configuration, use_named, transform_name, x, y, z):
        self.position = (x, y, z)
        return FakeComponent()


class FakeAutomation:
    def __init__(self, assembly):
        self.assembly = assembly

    def get_active_doc(self):
        return self.assembly, None

    def _result(self, success, message, error_code=0, data=None):
        return {"success": success, "message": message, "data": data or {}}


class AssemblyLegacyUnitTests(unittest.TestCase):
    def test_insert_component_position_remains_legacy_meters(self):
        assembly = FakeAssembly()
        automation = FakeAutomation(assembly)
        with tempfile.TemporaryDirectory() as directory:
            component_path = Path(directory) / "component.SLDPRT"
            component_path.touch()

            result = insert_component(automation, str(component_path), x=1, y=2, z=3)

        self.assertTrue(result["success"])
        self.assertEqual((1, 2, 3), assembly.position)


if __name__ == "__main__":
    unittest.main()
