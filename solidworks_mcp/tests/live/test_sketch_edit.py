import math
import os
import unittest

from solidworks_mcp.automation import SolidWorksAutomation
from solidworks_mcp.comutil import com
from solidworks_mcp.tools.sketch_edit import (
    offset_entities, sketch_chamfer, sketch_fillet, sketch_mirror,
    sketch_pattern_circular, sketch_pattern_linear, split_entities,
)


@unittest.skipUnless(
    os.environ.get("SW_MCP_LIVE_TESTS") == "1",
    "Set SW_MCP_LIVE_TESTS=1 to run SolidWorks COM tests.",
)
class LiveSketchEditTests(unittest.TestCase):
    """Each edit runs on a scratch part and the part is closed unsaved."""

    def setUp(self):
        self.automation = SolidWorksAutomation()
        result = self.automation.connect()
        if not result["success"]:
            self.skipTest(result["message"])
        self.created_titles = []

    def tearDown(self):
        for title in reversed(self.created_titles):
            try:
                self.automation.app.CloseDoc(title)
            except Exception:
                pass
        self.automation.disconnect()

    def _new_part(self):
        result = self.automation.create_new_part()
        self.assertTrue(result["success"], result["message"])
        self.created_titles.append(result["data"]["name"])

    def _document(self):
        document, error = self.automation.get_active_doc()
        self.assertIsNone(error)
        return document

    def _feature(self, name):
        feature = com(self._document(), "FirstFeature")
        while feature is not None:
            if com(feature, "Name") == name:
                return feature
            feature = com(feature, "GetNextFeature")
        return None

    def _sketch(self, name):
        feature = self._feature(name)
        self.assertIsNotNone(feature, f"sketch not found: {name}")
        return com(feature, "GetSpecificFeature2")

    def _open_sketch(self, plane="Front"):
        sketch = self.automation.create_sketch(plane, exact_geometry=True)
        self.assertTrue(sketch["success"], sketch["message"])

    def _close_sketch(self):
        self.automation.exit_sketch()

    def _counts(self, name):
        sketch = self._sketch(name)
        return (int(com(sketch, "GetLineCount")), int(com(sketch, "GetArcCount")))

    def _centres_mm(self, name):
        """Arc/circle centres in the sketch's own 2D coordinate system."""
        centres = []
        for segment in com(self._sketch(name), "GetSketchSegments") or []:
            if int(com(segment, "GetType")) == 0:
                continue
            point = com(segment, "GetCenterPoint")
            centres.append((round(float(point[0]) * 1000, 3),
                            round(float(point[1]) * 1000, 3)))
        return centres

    def _assert_unsaved(self):
        active, error = self.automation.capture_active_document_ref()
        self.assertIsNone(error)
        self.assertIsNone(active.path)

    def test_fillet_and_chamfer_scratch_rectangle_without_saving(self):
        self._new_part()
        self._open_sketch()
        self.automation.draw_rectangle(-30, -20, 30, 20, "mm")
        self._close_sketch()
        self.assertEqual((4, 0), self._counts("Sketch1"))

        fillet = sketch_fillet(self.automation, "Sketch1", ["Line1", "Line2"],
                               radius=8, unit="mm")
        self.assertTrue(fillet["success"], fillet["message"])
        self.assertEqual((4, 1), self._counts("Sketch1"))

        chamfer = sketch_chamfer(self.automation, "Sketch1", ["Line3", "Line4"],
                                 distance=6, mode="distance_angle",
                                 angle_deg=45, unit="mm")
        self.assertTrue(chamfer["success"], chamfer["message"])
        self.assertEqual((5, 1), self._counts("Sketch1"))
        self._assert_unsaved()

    def test_offset_scratch_sketch_without_saving(self):
        self._new_part()
        self._open_sketch()
        self.automation.draw_rectangle(-30, -20, 30, 20, "mm")
        self._close_sketch()

        offset = offset_entities(self.automation, "Sketch1",
                                 ["Line1", "Line2", "Line3", "Line4"],
                                 offset=5, unit="mm")

        self.assertTrue(offset["success"], offset["message"])
        self.assertEqual((8, 0), self._counts("Sketch1"))
        self._assert_unsaved()

    def test_mirror_scratch_sketch_without_saving(self):
        self._new_part()
        self._open_sketch()
        self.automation.draw_centerline(0, -40, 0, 40, "mm")
        self.automation.draw_circle(20, 0, 8, "mm")
        self._close_sketch()

        mirror = sketch_mirror(self.automation, "Sketch1", ["Arc1"],
                               mirror_entity="Line1")

        self.assertTrue(mirror["success"], mirror["message"])
        self.assertEqual((1, 2), self._counts("Sketch1"))
        self.assertEqual(
            sorted([(20.0, 0.0), (-20.0, 0.0)]),
            sorted(self._centres_mm("Sketch1")),
        )
        self._assert_unsaved()

    def test_split_scratch_sketch_entity_without_saving(self):
        self._new_part()
        self._open_sketch()
        self.automation.draw_line(-30, 0, 30, 0, "mm")
        self._close_sketch()

        split = split_entities(self.automation, "Sketch1", ["Line1"],
                               x=0, y=0, unit="mm")

        self.assertTrue(split["success"], split["message"])
        self.assertEqual((2, 0), self._counts("Sketch1"))
        self._assert_unsaved()

    def test_linear_pattern_scratch_sketch_without_saving(self):
        self._new_part()
        self._open_sketch()
        self.automation.draw_circle(0, 0, 5, "mm")
        self._close_sketch()

        result = sketch_pattern_linear(
            self.automation, "Sketch1", ["Arc1"], spacing_x=20, spacing_y=15,
            count_x=2, count_y=3, unit="mm",
        )

        self.assertTrue(result["success"], result["message"])
        self.assertEqual((0, 6), self._counts("Sketch1"))
        self.assertEqual(
            sorted([
                (0.0, 0.0), (20.0, 0.0), (0.0, 15.0),
                (20.0, 15.0), (0.0, 30.0), (20.0, 30.0),
            ]),
            sorted(self._centres_mm("Sketch1")),
        )
        self._assert_unsaved()

    def test_circular_pattern_about_a_centre_without_saving(self):
        self._new_part()
        self._open_sketch()
        self.automation.draw_circle(20, 0, 4, "mm")
        self._close_sketch()

        result = sketch_pattern_circular(self.automation, "Sketch1", ["Arc1"],
                                         count=4, center_x=0, center_y=0,
                                         unit="mm")

        self.assertTrue(result["success"], result["message"])
        self.assertEqual((0, 4), self._counts("Sketch1"))
        self.assertAlmostEqual(20.0, result["data"]["arc_radius"], places=6)
        self.assertAlmostEqual(180.0, result["data"]["arc_angle_deg"], places=6)
        self.assertEqual(
            sorted([(20.0, 0.0), (0.0, 20.0), (-20.0, 0.0), (0.0, -20.0)]),
            sorted(self._centres_mm("Sketch1")),
        )
        self._assert_unsaved()

    def test_partial_circular_pattern_steps_counter_clockwise(self):
        self._new_part()
        self._open_sketch()
        self.automation.draw_circle(20, 0, 4, "mm")
        self._close_sketch()

        result = sketch_pattern_circular(self.automation, "Sketch1", ["Arc1"],
                                         count=3, total_angle_deg=90, unit="mm")

        self.assertTrue(result["success"], result["message"])
        expected = [(20.0, 0.0)]
        for index in range(1, 3):
            angle = math.radians(30.0 * index)
            expected.append((round(20.0 * math.cos(angle), 3),
                             round(20.0 * math.sin(angle), 3)))
        self.assertEqual(sorted(expected), sorted(self._centres_mm("Sketch1")))
        self._assert_unsaved()

    def test_circular_pattern_uses_sketch_coordinates_on_the_top_plane(self):
        self._new_part()
        self._open_sketch("Top")
        self.automation.draw_circle(20, 10, 4, "mm")
        self._close_sketch()

        result = sketch_pattern_circular(self.automation, "Sketch1", ["Arc1"],
                                         count=4, center_x=0, center_y=0,
                                         unit="mm")

        self.assertTrue(result["success"], result["message"])
        self.assertEqual((0, 4), self._counts("Sketch1"))
        radius = math.hypot(20.0, 10.0)
        phase = math.atan2(10.0, 20.0)
        expected = []
        for index in range(4):
            angle = phase + index * math.radians(90.0)
            expected.append((round(radius * math.cos(angle), 2),
                             round(radius * math.sin(angle), 2)))
        observed = [(round(u, 2), round(v, 2))
                    for u, v in self._centres_mm("Sketch1")]
        self.assertEqual(sorted(expected), sorted(observed))
        self.assertAlmostEqual(radius, result["data"]["arc_radius"], places=4)
        self._assert_unsaved()


if __name__ == "__main__":
    unittest.main()
