import tempfile
import unittest
from pathlib import Path

from solidworks_mcp.tools.assembly import _component_faces, insert_component


class FakeComponent:
    Name2 = "Component-1"


class FakeBody:
    def __init__(self, box=(0.0, 0.0, 0.0, 0.0, 0.0, 0.0), kinds=()):
        self._box = list(box)
        self._kinds = list(kinds)

    def GetBodyBox(self):
        return list(self._box)

    def GetFaces(self):
        return [FakeFace(kind) for kind in self._kinds]


class FakeSurface:
    def __init__(self, kind):
        self._kind = kind

    def IsPlane(self):
        return self._kind == "planar"

    def IsCylinder(self):
        return self._kind == "cylindrical"


class FakeFace:
    def __init__(self, kind):
        self._surface = FakeSurface(kind)

    def GetSurface(self):
        return self._surface


class FakeComponentWithBodies:
    """A component whose part has several bodies (api-findings.md 21.5)."""

    def __init__(self, body_kinds):
        self._bodies = [FakeBody(kinds=kinds) for kinds in body_kinds]

    def GetBodies2(self, body_type, visible_only):
        return self._bodies

    def GetBody(self):
        return self._bodies[0]


class FakePart:
    def __init__(self, boxes):
        self._boxes = [FakeBody(b) for b in boxes]

    def GetBodies2(self, body_type, visible_only):
        return self._boxes


class FakeApp:
    def __init__(self, part):
        self._part = part

    def GetOpenDocumentByName(self, filepath):
        return self._part


class FakeAssembly:
    GetType = 2

    def __init__(self):
        self.position = None

    def AddComponent5(self, filepath, options, configuration, use_named, transform_name, x, y, z):
        self.position = (x, y, z)
        return FakeComponent()


class FakeAutomation:
    def __init__(self, assembly, part=None):
        self.assembly = assembly
        self.app = FakeApp(part) if part is not None else None

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


class AssemblyPlacementUnitTests(unittest.TestCase):
    """api-findings.md 21.2: AddComponent5 centres the bounding box, so
    place='origin' must subtract it."""

    def _run(self, place, boxes):
        assembly = FakeAssembly()
        part = FakePart(boxes)
        automation = FakeAutomation(assembly, part)
        with tempfile.TemporaryDirectory() as directory:
            component_path = Path(directory) / "component.SLDPRT"
            component_path.touch()
            result = insert_component(automation, str(component_path),
                                      x=0.0, y=0.0, z=0.125, place=place)
        return result, assembly.position

    def test_origin_placement_subtracts_box_centre(self):
        # a 84 mm long part along X starting at 0, 125 mm along Z
        result, position = self._run("origin", [(0.0, -0.0275, 0.0,
                                                 0.084, 0.0275, 0.0)])
        self.assertTrue(result["success"], result["message"])
        self.assertAlmostEqual(-0.042, position[0], places=9)
        self.assertAlmostEqual(0.0, position[1], places=9)
        self.assertAlmostEqual(0.125, position[2], places=9)

    def test_origin_placement_unions_multiple_bodies(self):
        result, position = self._run("origin", [(0.0, 0.0, 0.0, 0.016, 0.0375, 0.0375),
                                                (0.0, 0.0, 0.0, 0.016, 0.026, 0.026)])
        self.assertTrue(result["success"], result["message"])
        self.assertAlmostEqual(-0.008, position[0], places=9)

    def test_center_is_default_and_passes_through(self):
        result, position = self._run("center", [(0.0, 0.0, 0.0, 1.0, 1.0, 1.0)])
        self.assertTrue(result["success"], result["message"])
        self.assertEqual((0.0, 0.0, 0.125), position)

    def test_origin_without_open_part_is_rejected(self):
        assembly = FakeAssembly()
        automation = FakeAutomation(assembly)
        with tempfile.TemporaryDirectory() as directory:
            component_path = Path(directory) / "component.SLDPRT"
            component_path.touch()
            result = insert_component(automation, str(component_path), place="origin")
        self.assertFalse(result["success"])
        self.assertIn("already open", result["message"])
        self.assertIsNone(assembly.position)

    def test_unknown_place_is_rejected(self):
        assembly = FakeAssembly()
        automation = FakeAutomation(assembly)
        with tempfile.TemporaryDirectory() as directory:
            component_path = Path(directory) / "component.SLDPRT"
            component_path.touch()
            result = insert_component(automation, str(component_path), place="middle")
        self.assertFalse(result["success"])
        self.assertIn("place must be", result["message"])
        self.assertIsNone(assembly.position)


class ComponentFaceEnumerationTests(unittest.TestCase):
    """api-findings.md 21.5: a multi-body component must expose the faces of
    every body, not just the first."""

    def test_faces_are_collected_from_every_body(self):
        component = FakeComponentWithBodies([["planar", "cylindrical"],
                                            ["cylindrical"]])
        kinds = [kind for _face, kind in _component_faces(component)]
        self.assertEqual(["planar", "cylindrical", "cylindrical"], kinds)

    def test_single_body_still_works_via_getbody_fallback(self):
        component = FakeComponentWithBodies([["cylindrical"]])

        class Legacy(FakeComponentWithBodies):
            def GetBodies2(self, body_type, visible_only):
                return []

        kinds = [kind for _face, kind in _component_faces(Legacy([["cylindrical"]]))]
        self.assertEqual(["cylindrical"], kinds)
        self.assertEqual(1, len(_component_faces(component)))


if __name__ == "__main__":
    unittest.main()
