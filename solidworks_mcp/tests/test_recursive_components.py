import unittest

from solidworks_mcp.tools.assembly import list_components


class Component:
    def __init__(self, name, path, children=()):
        self.Name2 = name
        self.GetPathName = path
        self.IsFixed = False
        self.GetSuppression = 1
        self.GetChildren = list(children)


class Assembly:
    def __init__(self, components):
        self.GetComponents = list(components)
        self.GetType = 2


class Automation:
    def __init__(self, assembly):
        self.assembly = assembly

    def get_active_doc(self):
        return self.assembly, None

    def _result(self, success, message, error_code=0, data=None):
        return {"success": success, "message": message, "data": data or {}}


class RecursiveComponentTests(unittest.TestCase):
    def test_lists_nested_instance_paths_without_deduplicating_repeated_parts(self):
        part1 = Component("Frame-1", "C:/output/frame.SLDPRT")
        part2 = Component("Frame-2", "C:/output/frame.SLDPRT")
        subassembly = Component("Sub-1", "C:/output/sub.SLDASM", (part1, part2))

        result = list_components(Automation(Assembly((subassembly,))))

        components = result["data"]["components"]
        self.assertEqual(["Sub-1", "Sub-1/Frame-1", "Sub-1/Frame-2"],
                         [component["instance_path"] for component in components])
        self.assertEqual(3, result["data"]["coverage"]["visited_count"])
        self.assertTrue(result["data"]["coverage"]["complete"])


if __name__ == "__main__":
    unittest.main()
