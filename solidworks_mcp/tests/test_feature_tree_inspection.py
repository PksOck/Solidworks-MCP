import unittest

from solidworks_mcp.inspection.documents import inspect_feature_tree


class Dimension:
    FullName = "D1@Sketch1"
    SystemValue = 0.125


class DisplayDimension:
    GetDimension2 = Dimension()


class Feature:
    def __init__(self, name, feature_type, child=None, next_sub=None, dimension=None):
        self.Name = name
        self.GetTypeName2 = feature_type
        self.IsSuppressed = False
        self.GetFirstSubFeature = child
        self.GetNextSubFeature = next_sub
        self.GetNextFeature = None
        self.GetFirstDisplayDimension = dimension

    def GetNextDisplayDimension(self, current):
        return None


class EquationManager:
    Count = 1

    def Equation(self, index):
        return '"Width" = 0.125'

    def Value(self, index):
        return 0.125

    def GlobalVariable(self, index):
        return True


class Document:
    def __init__(self, first_feature):
        self.FirstFeature = first_feature
        self.GetEquationMgr = EquationManager()


class FeatureTreeInspectionTests(unittest.TestCase):
    def test_preserves_unknown_subfeature_dimensions_and_equations(self):
        child = Feature("Imported oddity", "UnknownFeature")
        parent = Feature(
            "Boss-Extrude1", "BossExtrude", child=child,
            dimension=DisplayDimension(),
        )

        result = inspect_feature_tree(Document(parent))

        self.assertEqual("Imported oddity", result["features"][0]["children"][0]["name"])
        self.assertEqual("UnknownFeature", result["features"][0]["children"][0]["type"])
        dimension = result["features"][0]["parameters"][0]
        self.assertEqual("D1@Sketch1", dimension["name"])
        self.assertIsNone(dimension["raw_value"])
        self.assertEqual(0.125, dimension["resolved_value_m"])
        self.assertEqual('"Width" = 0.125', result["equations"][0]["raw_expression"])
        self.assertTrue(result["equations"][0]["global_variable"])


if __name__ == "__main__":
    unittest.main()
