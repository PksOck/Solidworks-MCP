import types
import unittest

from solidworks_mcp.constants import SwErrors
from solidworks_mcp.core.policy import OperationClass
from solidworks_mcp.registry import operation_class_for, registered_tools
from solidworks_mcp.tools.sketch_entities import (
    draw_center_rectangle, draw_centerline, draw_circle_radius, draw_ellipse,
    draw_elliptical_arc, draw_parallelogram, draw_parabola, draw_point,
    draw_rectangle_3point_center, draw_rectangle_3point_corner,
)


EXPECTED_TOOLS = {
    "draw_centerline": [1, 1, 0.0, 2, 2, 0.0],
    "draw_point": [1, 2, 0.0],
    "draw_circle_radius": [1, 2, 0.0, 3],
    "draw_center_rectangle": [0.5, 1.5, 0.0, 4.5, 5.5, 0.0],
    "draw_rectangle_3point_corner": [1, 2, 0.0, 3, 4, 0.0, 5, 6, 0.0],
    "draw_rectangle_3point_center": [1, 2, 0.0, 3, 4, 0.0, 5, 6, 0.0],
    "draw_parallelogram": [1, 2, 0.0, 3, 4, 0.0, 5, 6, 0.0],
}

# Millimetre arguments reused by the behaviour tests below.
ARGS = {
    "draw_centerline": dict(x1=1, y1=1, x2=2, y2=2),
    "draw_point": dict(x=1, y=2),
    "draw_circle_radius": dict(cx=1, cy=2, radius=3),
    "draw_center_rectangle": dict(cx=2.5, cy=3.5, width=4, height=4),
    "draw_rectangle_3point_corner": dict(x1=1, y1=2, x2=3, y2=4, x3=5, y3=6),
    "draw_rectangle_3point_center": dict(x1=1, y1=2, x2=3, y2=4, x3=5, y3=6),
    "draw_parallelogram": dict(x1=1, y1=2, x2=3, y2=4, x3=5, y3=6),
}

CALLABLES = {
    "draw_centerline": draw_centerline,
    "draw_point": draw_point,
    "draw_circle_radius": draw_circle_radius,
    "draw_center_rectangle": draw_center_rectangle,
    "draw_rectangle_3point_corner": draw_rectangle_3point_corner,
    "draw_rectangle_3point_center": draw_rectangle_3point_center,
    "draw_parallelogram": draw_parallelogram,
}


_DEFAULT_RESULT = object()


class SketchManager:
    def __init__(self, result=_DEFAULT_RESULT):
        self.result = object() if result is _DEFAULT_RESULT else result
        self.calls = []

    def __getattr__(self, name):
        if not name.startswith("Create"):
            raise AttributeError(name)

        def record(_bound_self, *args):
            self.calls.append((name, args))
            return self.result

        # Return a bound method, exactly like a real COM method wrapper:
        # comutil.com() only invokes the member when inspect.ismethod() is true.
        return types.MethodType(record, self)


class Document:
    def __init__(self, sketch_result=_DEFAULT_RESULT):
        self.SketchManager = SketchManager(sketch_result)


class Units:
    FACTORS = {"mm": 0.001, "cm": 0.01, "m": 1.0, "inch": 0.0254}

    def to_meters(self, value, unit):
        return value * self.FACTORS[unit]


class Automation:
    def __init__(self, document=None):
        self.document = document or Document()
        self._units = Units()
        self.active_doc_calls = 0

    def get_active_doc(self):
        self.active_doc_calls += 1
        return self.document, None

    def _result(self, success, message, error_code=0, data=None):
        return {
            "success": success,
            "message": message,
            "error_code": int(error_code),
            "data": data or {},
        }


class SketchEntityRegistrationTests(unittest.TestCase):
    def test_all_entity_tools_are_registered_mutations(self):
        tools = {item.name: item for item in registered_tools()}

        for name in EXPECTED_TOOLS:
            self.assertIn(name, tools)
            self.assertIs(OperationClass.MUTATE, operation_class_for(name))

    def test_unit_argument_accepts_the_documented_units(self):
        tools = {item.name: item for item in registered_tools()}

        for name in EXPECTED_TOOLS:
            unit = tools[name].inputSchema["properties"]["unit"]
            self.assertEqual(["mm", "cm", "m", "inch"], unit["enum"])
            self.assertEqual("mm", unit["default"])


class SketchEntityBehaviorTests(unittest.TestCase):
    def test_entities_convert_millimetres_to_metres(self):
        for name, expected in EXPECTED_TOOLS.items():
            with self.subTest(tool=name):
                automation = Automation()

                result = CALLABLES[name](automation, **ARGS[name])

                self.assertTrue(result["success"], result["message"])
                method, arguments = automation.document.SketchManager.calls[0]
                self.assertTrue(method.startswith("Create"))
                for actual, wanted in zip(arguments, expected):
                    self.assertAlmostEqual(wanted * 0.001, actual, places=12)
                self.assertEqual("mm", result["data"]["unit"])

    def test_center_rectangle_uses_opposite_corners_of_the_center(self):
        automation = Automation()

        result = draw_center_rectangle(automation, cx=2.5, cy=3.5, width=4, height=4)

        self.assertTrue(result["success"], result["message"])
        method, arguments = automation.document.SketchManager.calls[0]
        self.assertEqual("CreateCenterRectangle", method)
        self.assertAlmostEqual(0.0005, arguments[0], places=12)
        self.assertAlmostEqual(0.0055, arguments[4], places=12)

    def test_non_positive_radius_is_rejected_before_com(self):
        automation = Automation()

        result = draw_circle_radius(automation, radius=0)

        self.assertFalse(result["success"])
        self.assertEqual(SwErrors.swInvalidInput, result["error_code"])
        self.assertEqual(0, automation.active_doc_calls)
        self.assertEqual([], automation.document.SketchManager.calls)

    def test_non_positive_rectangle_side_is_rejected_before_com(self):
        automation = Automation()

        result = draw_center_rectangle(automation, width=-5, height=10)

        self.assertFalse(result["success"])
        self.assertEqual(SwErrors.swInvalidInput, result["error_code"])
        self.assertEqual([], automation.document.SketchManager.calls)

    def test_failed_create_reports_a_sketch_error(self):
        automation = Automation(Document(sketch_result=None))

        result = draw_point(automation, x=1, y=2)

        self.assertFalse(result["success"])
        self.assertEqual(SwErrors.swSketchError, result["error_code"])


class EllipseBehaviorTests(unittest.TestCase):
    def test_ellipse_axis_points_follow_the_rotation(self):
        automation = Automation()

        result = draw_ellipse(automation, cx=0, cy=0, major_radius=10,
                              minor_radius=5, rotation_deg=90)

        self.assertTrue(result["success"], result["message"])
        method, arguments = automation.document.SketchManager.calls[0]
        self.assertEqual("CreateEllipse", method)
        # Major axis at 90 degrees: (0, +0.010); minor axis at 180 degrees: (-0.005, 0).
        self.assertAlmostEqual(0.0, arguments[3], places=12)
        self.assertAlmostEqual(0.010, arguments[4], places=12)
        self.assertAlmostEqual(-0.005, arguments[6], places=12)
        self.assertAlmostEqual(0.0, arguments[7], places=12)

    def test_ellipse_rejects_non_positive_radii(self):
        automation = Automation()

        result = draw_ellipse(automation, major_radius=10, minor_radius=0)

        self.assertFalse(result["success"])
        self.assertEqual(SwErrors.swInvalidInput, result["error_code"])
        self.assertEqual([], automation.document.SketchManager.calls)

    def test_elliptical_arc_direction_follows_the_clockwise_flag(self):
        counter_clockwise = Automation()
        clockwise = Automation()

        draw_elliptical_arc(counter_clockwise, major_radius=10, minor_radius=5,
                            end_angle_deg=90)
        draw_elliptical_arc(clockwise, major_radius=10, minor_radius=5,
                            end_angle_deg=90, counter_clockwise=False)

        self.assertEqual(1, counter_clockwise.document.SketchManager.calls[0][1][-1])
        self.assertEqual(-1, clockwise.document.SketchManager.calls[0][1][-1])

    def test_elliptical_arc_end_point_lies_on_the_ellipse(self):
        automation = Automation()

        draw_elliptical_arc(automation, cx=1, cy=2, major_radius=10, minor_radius=5,
                            end_angle_deg=90)

        _method, arguments = automation.document.SketchManager.calls[0]
        end_x, end_y = arguments[12], arguments[13]
        # At 90 degrees the parametric point is the minor axis: center + (0, b).
        self.assertAlmostEqual(0.001, end_x, places=12)
        self.assertAlmostEqual(0.002 + 0.005, end_y, places=12)

    def test_elliptical_arc_rejects_out_of_range_end_angle(self):
        automation = Automation()

        result = draw_elliptical_arc(automation, major_radius=10, minor_radius=5,
                                     end_angle_deg=400)

        self.assertFalse(result["success"])
        self.assertEqual(SwErrors.swInvalidInput, result["error_code"])


class ParabolaBehaviorTests(unittest.TestCase):
    def test_parabola_passes_focus_apex_and_end_points(self):
        automation = Automation()

        result = draw_parabola(automation, focus_x=0, focus_y=5, apex_x=0, apex_y=0,
                               start_x=-10, start_y=5, end_x=10, end_y=5)

        self.assertTrue(result["success"], result["message"])
        method, arguments = automation.document.SketchManager.calls[0]
        self.assertEqual("CreateParabola", method)
        self.assertAlmostEqual(0.0, arguments[0], places=12)
        self.assertAlmostEqual(0.005, arguments[1], places=12)
        self.assertAlmostEqual(-0.010, arguments[6], places=12)

    def test_parabola_rejects_coincident_focus_and_apex(self):
        automation = Automation()

        result = draw_parabola(automation, focus_x=0, focus_y=0, apex_x=0, apex_y=0,
                               start_x=-10, start_y=5, end_x=10, end_y=5)

        self.assertFalse(result["success"])
        self.assertEqual(SwErrors.swInvalidInput, result["error_code"])
        self.assertEqual([], automation.document.SketchManager.calls)

    def test_parabola_rejects_coincident_end_points(self):
        automation = Automation()

        result = draw_parabola(automation, focus_x=0, focus_y=5, apex_x=0, apex_y=0,
                               start_x=1, start_y=1, end_x=1, end_y=1)

        self.assertFalse(result["success"])
        self.assertEqual(SwErrors.swInvalidInput, result["error_code"])


if __name__ == "__main__":
    unittest.main()
