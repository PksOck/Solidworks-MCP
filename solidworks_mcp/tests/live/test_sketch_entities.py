import os
import unittest

from solidworks_mcp.automation import SolidWorksAutomation
from solidworks_mcp.comutil import com
from solidworks_mcp.tools.sketch_entities import (
    draw_center_rectangle, draw_centerline, draw_circle_radius, draw_ellipse,
    draw_elliptical_arc, draw_parallelogram, draw_parabola, draw_point,
    draw_rectangle_3point_center, draw_rectangle_3point_corner,
)


@unittest.skipUnless(
    os.environ.get("SW_MCP_LIVE_TESTS") == "1",
    "Set SW_MCP_LIVE_TESTS=1 to run SolidWorks COM tests.",
)
class LiveSketchEntityTests(unittest.TestCase):
    """Each entity is drawn in its own scratch sketch and verified by counting."""

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
        title = result["data"]["name"]
        self.created_titles.append(title)
        return title

    def _active_sketch(self):
        document, error = self.automation.get_active_doc()
        self.assertIsNone(error)
        sketch = com(document, "GetActiveSketch2")
        self.assertIsNotNone(sketch, "expected an active sketch")
        return sketch

    def _segment_count(self):
        segments = com(self._active_sketch(), "GetSketchSegments")
        return 0 if segments is None else len(segments)

    def _count(self, getter):
        value = com(self._active_sketch(), getter)
        return 0 if value is None else int(value)

    def _draw_in_new_sketch(self, call):
        sketch = self.automation.create_sketch("Front", exact_geometry=True)
        self.assertTrue(sketch["success"], sketch["message"])
        before = self._segment_count()
        result = call()
        self.assertTrue(result["success"], result["message"])
        after = self._segment_count()
        self.automation.exit_sketch()
        return result, before, after

    def test_sketch_entity_tools_create_geometry_without_saving(self):
        self._new_part()

        cases = [
            ("centerline", lambda: draw_centerline(self.automation, 0, -40, 0, 40), 1),
            ("circle radius", lambda: draw_circle_radius(self.automation, -60, 0, 10), 1),
            ("center rectangle",
             lambda: draw_center_rectangle(self.automation, 40, 0, 20, 10), 4),
            ("3-point corner rectangle",
             lambda: draw_rectangle_3point_corner(
                 self.automation, 80, -5, 100, -5, 100, 5), 4),
            ("3-point center rectangle",
             lambda: draw_rectangle_3point_center(
                 self.automation, 130, 0, 145, 0, 130, 8), 4),
            ("parallelogram",
             lambda: draw_parallelogram(
                 self.automation, 170, -5, 190, -5, 180, 5), 4),
            ("ellipse", lambda: draw_ellipse(self.automation, -100, 40, 15, 8), 1),
            ("elliptical arc",
             lambda: draw_elliptical_arc(
                 self.automation, 0, 60, 20, 10, end_angle_deg=180), 1),
            ("parabola",
             lambda: draw_parabola(
                 self.automation, 60, 50, 60, 40, 40, 60, 80, 60), 1),
        ]

        for label, call, minimum_segments in cases:
            with self.subTest(entity=label):
                _result, before, after = self._draw_in_new_sketch(call)
                self.assertGreaterEqual(
                    after - before, minimum_segments,
                    f"{label} added {after - before} segments, expected {minimum_segments}",
                )

    def test_ellipse_parabola_and_point_getters_report_the_geometry(self):
        self._new_part()

        for label, call, getter in [
            ("ellipse", lambda: draw_ellipse(self.automation, 0, 0, 15, 8),
             "GetEllipseCount"),
            ("parabola",
             lambda: draw_parabola(self.automation, 60, 50, 60, 40, 40, 60, 80, 60),
             "GetParabolaCount"),
        ]:
            with self.subTest(entity=label):
                sketch = self.automation.create_sketch("Front", exact_geometry=True)
                self.assertTrue(sketch["success"], sketch["message"])
                result = call()
                self.assertTrue(result["success"], result["message"])
                self.assertEqual(1, self._count(getter))
                self.automation.exit_sketch()

        sketch = self.automation.create_sketch("Front", exact_geometry=True)
        self.assertTrue(sketch["success"], sketch["message"])
        point = draw_point(self.automation, -30, 0)
        self.assertTrue(point["success"], point["message"])
        self.assertEqual(1, self._count("GetUserPointsCount"))
        self.automation.exit_sketch()


if __name__ == "__main__":
    unittest.main()
