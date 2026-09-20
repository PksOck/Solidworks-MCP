import unittest

from solidworks_mcp.tools.measurements import get_body_bounding_box, get_mass_properties


class MassProperty:
    Volume = 1e-6
    SurfaceArea = 6e-4
    Mass = 0.00785
    Density = 7850.0
    CenterOfMass = (0.001, 0.002, 0.003)


class Extension:
    def CreateMassProperty(self):
        return MassProperty()


class Document:
    Extension = Extension()


class Automation:
    def get_active_doc(self):
        return Document(), None

    def _result(self, success, message, error_code=0, data=None):
        return {"success": success, "message": message, "data": data or {}}


class Body:
    def __init__(self, name, box):
        self.Name = name
        self.GetBodyBox = box


class BodyDocument:
    def GetBodies2(self, body_type, visible_only):
        return [
            Body("Body1", (0.0, -0.01, -0.02, 0.03, 0.01, 0.02)),
            Body("Body2", (0.04, -0.005, -0.005, 0.05, 0.005, 0.005)),
        ]


class BodyAutomation(Automation):
    def get_active_doc(self):
        return BodyDocument(), None


class MeasurementToolTests(unittest.TestCase):
    def test_mass_properties_include_si_display_values_and_density_evidence(self):
        result = get_mass_properties(Automation(), "mm")

        self.assertTrue(result["success"])
        data = result["data"]
        self.assertEqual(1e-6, data["si"]["volume_m3"])
        self.assertEqual(1000.0, data["display"]["volume"])
        self.assertEqual("mm^3", data["display"]["volume_unit"])
        self.assertEqual([1.0, 2.0, 3.0], data["display"]["center_of_mass"])
        self.assertEqual(7850.0, data["material_evidence"]["density_kg_m3"])
        self.assertEqual("IMassProperty", data["material_evidence"]["source"])

    def test_bounding_box_aggregates_all_bodies_and_marks_accuracy(self):
        result = get_body_bounding_box(BodyAutomation(), "mm")

        self.assertTrue(result["success"])
        combined = result["data"]["combined"]
        self.assertEqual({"x": 50.0, "y": 20.0, "z": 40.0}, combined["size"])
        self.assertEqual("approximate", result["data"]["accuracy"])
        self.assertEqual(2, len(result["data"]["bodies"]))


if __name__ == "__main__":
    unittest.main()
