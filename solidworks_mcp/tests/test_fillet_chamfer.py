"""Feature fillet and chamfer use the sldworks.tlb signatures (live, §34)."""

import math
import unittest

from solidworks_mcp.automation.features import FeatureOperations


class FeatureManager:
    def __init__(self):
        self.calls = []

    def FeatureFillet3(self, *args):
        self.calls.append(("FeatureFillet3", args))
        return object()

    def InsertFeatureChamfer(self, *args):
        self.calls.append(("InsertFeatureChamfer", args))
        return object()


class Extension:
    def __init__(self, hits):
        self.hits = hits
        self.picks = []

    def SelectByID2(self, name, kind, x, y, z, append, mark, callout, option):
        self.picks.append((kind, (x, y, z), append))
        return self.hits


class Document:
    def __init__(self, hits=True):
        self.FeatureManager = FeatureManager()
        self.Extension = Extension(hits)

    def ClearSelection2(self, all_):
        return True


class Units:
    def to_meters(self, value, unit):
        return value / 1000.0

    class default_unit:
        value = "mm"


class Automation(FeatureOperations):
    def __init__(self, document):
        self.document = document
        self._units = Units()

    def get_active_doc(self):
        return self.document, None

    def _result(self, success, message, error_code=0, data=None):
        return {"success": success, "message": message, "data": data or {}}


class FeatureFilletTests(unittest.TestCase):
    def test_fillet_passes_the_fourteen_argument_signature(self):
        document = Document()
        result = Automation(document).fillet_edges(5, "mm")

        self.assertTrue(result["success"], result["message"])
        name, args = document.FeatureManager.calls[0]
        self.assertEqual("FeatureFillet3", name)
        self.assertEqual(14, len(args))
        # Propagate + uniform radius, R1 = 5 mm, simple fillet.
        self.assertEqual((3, 0.005, 0.0, 0.0, 0), args[:5])

    def test_fillet_selects_edges_at_the_given_points(self):
        document = Document()
        result = Automation(document).fillet_edges(
            5, "mm", edge_points=[[0, 50, 50], [40, 50, 0]])

        self.assertTrue(result["success"], result["message"])
        self.assertEqual(
            [("EDGE", (0.0, 0.05, 0.05), False), ("EDGE", (0.04, 0.05, 0.0), True)],
            document.Extension.picks)

    def test_fillet_reports_an_edge_point_that_hits_nothing(self):
        document = Document(hits=False)
        result = Automation(document).fillet_edges(5, "mm", edge_points=[[1, 2, 3]])

        self.assertFalse(result["success"])
        self.assertEqual("SELECTION_EMPTY", result["data"]["code"])
        self.assertEqual([], document.FeatureManager.calls)


class FeatureChamferTests(unittest.TestCase):
    def test_chamfer_passes_the_eight_argument_signature(self):
        document = Document()
        result = Automation(document).chamfer_edges(5, 45, "mm")

        self.assertTrue(result["success"], result["message"])
        name, args = document.FeatureManager.calls[0]
        self.assertEqual("InsertFeatureChamfer", name)
        # Tangent propagation, angle-distance, width 5 mm at 45 degrees.
        self.assertEqual((4, 1, 0.005, math.radians(45), 0.0, 0.0, 0.0, 0.0), args)

    def test_chamfer_selects_edges_at_the_given_points(self):
        document = Document()
        Automation(document).chamfer_edges(5, 45, "mm", edge_points=[[0, 50, 50]])

        self.assertEqual([("EDGE", (0.0, 0.05, 0.05), False)],
                         document.Extension.picks)


if __name__ == "__main__":
    unittest.main()
