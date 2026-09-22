import math
import types
import unittest

from solidworks_mcp.constants import SwErrors
from solidworks_mcp.core.policy import OperationClass
from solidworks_mcp.registry import operation_class_for, registered_tools
from solidworks_mcp.tools.sketch_entities import (
    draw_arc_slot, draw_arc_slot_3point, draw_center_rectangle, draw_centerline,
    draw_circle_radius, draw_ellipse, draw_elliptical_arc, draw_equation_curve,
    draw_parallelogram, draw_parabola, draw_point, draw_rectangle_3point_center,
    draw_rectangle_3point_corner, draw_tangent_arc,
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
        self.document = None

    def __getattr__(self, name):
        if not name.startswith("Create"):
            raise AttributeError(name)

        def record(_bound_self, *args):
            self.calls.append((name, args))
            if self.document is not None and name == "CreateEquationSpline":
                self.document.segments.append(Segment(3))
            return self.result

        # Return a bound method, exactly like a real COM method wrapper:
        # comutil.com() only invokes the member when inspect.ismethod() is true.
        return types.MethodType(record, self)


class Segment:
    def __init__(self, kind):
        self.kind = kind

    def GetType(self):
        return self.kind


class SketchPoint:
    def __init__(self, x, y, z=0.0):
        self.X = x
        self.Y = y
        self.Z = z


class Spline:
    def __init__(self, length=0.0, points=()):
        self.length = length
        self.points = list(points)

    def GetLength(self):
        return self.length

    def GetPoints2(self):
        return list(self.points)


class Sketch:
    def __init__(self, document):
        self.document = document

    def GetSketchSegments(self):
        return list(self.document.segments)


class Document:
    def __init__(self, sketch_result=_DEFAULT_RESULT, linear_unit=0):
        self.linear_unit = linear_unit
        self.segments = []
        self.SketchManager = SketchManager(sketch_result)
        self.SketchManager.document = self

    def GetUnits(self):
        return (self.linear_unit, 0)

    def GetActiveSketch2(self):
        return Sketch(self)


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

    def test_the_equation_curve_tool_is_registered_as_a_mutation(self):
        tools = {item.name: item for item in registered_tools()}

        self.assertIn("draw_equation_curve", tools)
        self.assertIs(OperationClass.MUTATE,
                      operation_class_for("draw_equation_curve"))
        properties = tools["draw_equation_curve"].inputSchema["properties"]
        self.assertEqual(["mm", "cm", "m", "inch"], properties["unit"]["enum"])
        self.assertEqual(["expression", "range_start", "range_end"],
                         tools["draw_equation_curve"].inputSchema["required"])

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


class TangentArcAndSlotBehaviorTests(unittest.TestCase):
    def test_tangent_arc_is_registered_as_a_mutation(self):
        tools = {item.name: item for item in registered_tools()}

        for name in ("draw_tangent_arc", "draw_arc_slot", "draw_arc_slot_3point"):
            self.assertIn(name, tools)
            self.assertIs(OperationClass.MUTATE, operation_class_for(name))

    def test_tangent_arc_passes_zero_arc_type_after_the_coordinates(self):
        automation = Automation()

        result = draw_tangent_arc(automation, start_x=20, start_y=0, end_x=30, end_y=10)

        self.assertTrue(result["success"], result["message"])
        method, arguments = automation.document.SketchManager.calls[0]
        self.assertEqual("CreateTangentArc", method)
        self.assertEqual(7, len(arguments))
        self.assertAlmostEqual(0.020, arguments[0], places=12)
        self.assertAlmostEqual(0.030, arguments[3], places=12)
        self.assertEqual(0, arguments[6])

    def test_tangent_arc_rejects_coincident_points_before_com(self):
        automation = Automation()

        result = draw_tangent_arc(automation, start_x=5, start_y=5, end_x=5, end_y=5)

        self.assertFalse(result["success"])
        self.assertEqual(SwErrors.swInvalidInput, result["error_code"])
        self.assertEqual(0, automation.active_doc_calls)

    def test_arc_slot_splits_non_coordinate_arguments_around_the_geometry(self):
        automation = Automation()

        result = draw_arc_slot(automation, center_x=0, center_y=0, start_x=10, start_y=0,
                              end_x=0, end_y=10, width=4)

        self.assertTrue(result["success"], result["message"])
        method, arguments = automation.document.SketchManager.calls[0]
        self.assertEqual("CreateSketchSlot", method)
        # (CreationType, LengthType, Width, center, start, end, direction, add-dim)
        self.assertEqual(2, arguments[0])
        self.assertEqual(0, arguments[1])
        self.assertAlmostEqual(0.004, arguments[2], places=12)
        self.assertAlmostEqual(0.0, arguments[3], places=12)
        self.assertAlmostEqual(0.010, arguments[6], places=12)
        self.assertAlmostEqual(0.0, arguments[9], places=12)
        self.assertAlmostEqual(0.010, arguments[10], places=12)
        self.assertEqual((1, False), arguments[12:14])

    def test_3point_arc_slot_uses_the_three_point_creation_type(self):
        automation = Automation()

        result = draw_arc_slot_3point(automation, x1=-10, y1=0, x2=0, y2=8, x3=10, y3=0,
                                     width=3)

        self.assertTrue(result["success"], result["message"])
        _method, arguments = automation.document.SketchManager.calls[0]
        self.assertEqual(3, arguments[0])
        self.assertAlmostEqual(0.003, arguments[2], places=12)

    def test_arc_slot_rejects_zero_width_and_coincident_points(self):
        zero_width = Automation()
        coincident = Automation()

        width_result = draw_arc_slot(zero_width, center_x=0, center_y=0, start_x=10,
                                     start_y=0, end_x=0, end_y=10, width=0)
        point_result = draw_arc_slot_3point(coincident, x1=1, y1=1, x2=1, y2=1,
                                            x3=1, y3=1, width=3)

        self.assertFalse(width_result["success"])
        self.assertFalse(point_result["success"])
        self.assertEqual([], zero_width.document.SketchManager.calls)
        self.assertEqual([], coincident.document.SketchManager.calls)


class EquationCurveTests(unittest.TestCase):
    """The live call takes the range in the document unit and the offsets in
    metres; the measured evidence is in docs/api-findings.md section 26."""

    @staticmethod
    def sine():
        return Spline(0.0076404, [SketchPoint(0.0, 0.0), SketchPoint(0.0062832, 0.0)])

    def test_range_uses_the_document_unit_while_the_offsets_use_metres(self):
        document = Document(self.sine(), linear_unit=3)  # an inch document
        automation = Automation(document)

        result = draw_equation_curve(automation, "sin(x)", 0, 25.4, x_offset=1,
                                     y_offset=2, unit="mm")

        self.assertTrue(result["success"], result["message"])
        method, arguments = document.SketchManager.calls[0]
        self.assertEqual("CreateEquationSpline", method)
        self.assertEqual("sin(x)", arguments[0])
        self.assertAlmostEqual(0.0, arguments[1], places=9)
        self.assertAlmostEqual(1.0, arguments[2], places=9)  # 25.4 mm = 1 inch
        self.assertIs(False, arguments[3])
        self.assertAlmostEqual(0.0, arguments[4], places=9)
        self.assertAlmostEqual(0.001, arguments[5], places=9)  # 1 mm in metres
        self.assertAlmostEqual(0.002, arguments[6], places=9)
        self.assertEqual("inch", result["data"]["document_unit"])
        self.assertEqual([0.0, 1.0], result["data"]["range_in_document_unit"])

    def test_rotation_is_radians_and_measurements_come_back_in_the_unit(self):
        document = Document(self.sine(), linear_unit=0)
        automation = Automation(document)

        result = draw_equation_curve(automation, "sin(x)", 0, 6.2831853,
                                     rotation_deg=90, unit="mm")

        _method, arguments = document.SketchManager.calls[0]
        self.assertAlmostEqual(math.pi / 2, arguments[4], places=12)
        self.assertAlmostEqual(7.6404, result["data"]["curve_length"], places=4)
        self.assertEqual([[0.0, 0.0, 0.0], [6.2832, 0.0, 0.0]],
                         result["data"]["endpoints"])
        self.assertEqual(1, result["data"]["spline_count"])

    def test_bad_input_is_rejected_before_any_com_call(self):
        cases = (
            {"expression": "   "},
            {"range_start": 1, "range_end": 1},
            {"range_start": "0"},
            {"rotation_deg": None},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                automation = Automation()
                call = {"expression": "sin(x)", "range_start": 0, "range_end": 1}
                call.update(overrides)

                result = draw_equation_curve(automation, **call)

                self.assertFalse(result["success"])
                self.assertEqual(0, automation.active_doc_calls)
                self.assertEqual([], automation.document.SketchManager.calls)

    def test_an_unsupported_document_unit_is_reported(self):
        automation = Automation(Document(linear_unit=5))  # feet and inches

        result = draw_equation_curve(automation, "sin(x)", 0, 10)

        self.assertFalse(result["success"])
        self.assertEqual("UNSUPPORTED_DOCUMENT_UNIT", result["data"]["code"])

    def test_a_curve_that_adds_no_spline_is_a_failure(self):
        automation = Automation()
        automation.document.segments.append(Segment(3))
        automation.document.SketchManager.document = None

        result = draw_equation_curve(automation, "sin(x)", 0, 10)

        self.assertFalse(result["success"])
        self.assertEqual("EQUATION_CURVE_FAILED", result["data"]["code"])


if __name__ == "__main__":
    unittest.main()
