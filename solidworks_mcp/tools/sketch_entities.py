"""
Sketch entity tools for the active 2D sketch.

Covers the primitive entities that the legacy server tools do not expose:
centerline, sketch point, radius circle, rectangle variants, parallelogram,
ellipse, elliptical arc and parabola. Every call is a mutation on the active
sketch, so each tool declares OperationClass.MUTATE.

The SolidWorks signatures were read from sldworks.tlb (ISketchManager), not
guessed; see docs/api-findings.md section 0.
"""

import math

from ..comutil import com
from ..constants import SwErrors
from ..core.policy import OperationClass
from ..registry import tool


UNIT_SCHEMA = {
    "type": "string",
    "enum": ["mm", "cm", "m", "inch"],
    "default": "mm",
}


def _is_number(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _invalid(sw, message):
    return sw._result(
        False, message, SwErrors.swInvalidInput, {"code": "VALIDATION_FAILED"}
    )


def _convert_coordinates(sw, unit, values):
    """Convert flat user-unit coordinates to meters; return (meters, error)."""
    if any(not _is_number(value) for value in values):
        return None, _invalid(sw, "All coordinates and dimensions must be finite numbers.")
    try:
        return [sw._units.to_meters(value, unit) for value in values], None
    except (KeyError, TypeError, ValueError) as conversion_error:
        return None, _invalid(sw, f"Invalid unit or coordinate: {conversion_error}")


def _create_entity(sw, method, coordinates, unit, message, data, leading=(), trailing=()):
    """Call one SketchManager create method with metre coordinates.

    ``leading`` and ``trailing`` carry non-coordinate arguments (an arc
    direction flag, a slot creation type) that must not be unit-converted.
    """
    document, error = sw.get_active_doc()
    if error:
        return error
    meters, conversion_error = _convert_coordinates(sw, unit, coordinates)
    if conversion_error:
        return conversion_error
    arguments = list(leading) + list(meters) + list(trailing)
    try:
        entity = com(com(document, "SketchManager"), method, *arguments)
    except Exception as create_error:
        return sw._result(
            False, f"{message} failed: {create_error}", SwErrors.swSketchError
        )
    if entity is None:
        return sw._result(
            False,
            f"{message} failed. Ensure a sketch is active and the geometry is valid.",
            SwErrors.swSketchError,
        )
    result_data = dict(data)
    result_data["unit"] = unit
    result_data["sketch_method"] = method
    return sw._result(True, message, SwErrors.swSuccess, result_data)


@tool(
    name="draw_centerline",
    description=(
        "Draw a centerline in the active sketch. Centerlines are construction "
        "geometry and are the usual revolve axis."
    ),
    schema={"type": "object", "properties": {
        "x1": {"type": "number", "default": 0},
        "y1": {"type": "number", "default": -50},
        "x2": {"type": "number", "default": 0},
        "y2": {"type": "number", "default": 50},
        "unit": UNIT_SCHEMA,
    }, "required": []},
    operation_class=OperationClass.MUTATE,
)
def draw_centerline(sw, x1: float = 0, y1: float = -50, x2: float = 0, y2: float = 50,
                    unit: str = "mm") -> dict:
    if x1 == x2 and y1 == y2:
        return _invalid(sw, "Centerline start and end points must differ.")
    return _create_entity(
        sw, "CreateCenterLine", [x1, y1, 0.0, x2, y2, 0.0], unit,
        "Centerline created.",
        {"start": [x1, y1], "end": [x2, y2]},
    )


@tool(
    name="draw_point",
    description="Draw a sketch point in the active sketch.",
    schema={"type": "object", "properties": {
        "x": {"type": "number", "default": 0},
        "y": {"type": "number", "default": 0},
        "unit": UNIT_SCHEMA,
    }, "required": []},
    operation_class=OperationClass.MUTATE,
)
def draw_point(sw, x: float = 0, y: float = 0, unit: str = "mm") -> dict:
    return _create_entity(
        sw, "CreatePoint", [x, y, 0.0], unit,
        "Sketch point created.",
        {"position": [x, y]},
    )


@tool(
    name="draw_circle_radius",
    description=(
        "Draw a circle from its center and an exact radius. Use this instead of "
        "draw_circle when the radius is known and no edge point is needed."
    ),
    schema={"type": "object", "properties": {
        "cx": {"type": "number", "default": 0},
        "cy": {"type": "number", "default": 0},
        "radius": {"type": "number", "exclusiveMinimum": 0, "default": 25},
        "unit": UNIT_SCHEMA,
    }, "required": ["radius"]},
    operation_class=OperationClass.MUTATE,
)
def draw_circle_radius(sw, cx: float = 0, cy: float = 0, radius: float = 25,
                       unit: str = "mm") -> dict:
    if not _is_number(radius) or radius <= 0:
        return _invalid(sw, "Circle radius must be a positive finite number.")
    return _create_entity(
        sw, "CreateCircleByRadius", [cx, cy, 0.0, radius], unit,
        f"Circle created with radius {radius}{unit}.",
        {"center": [cx, cy], "radius": radius},
    )


@tool(
    name="draw_center_rectangle",
    description="Draw a center-to-corner rectangle from its center, width and height.",
    schema={"type": "object", "properties": {
        "cx": {"type": "number", "default": 0},
        "cy": {"type": "number", "default": 0},
        "width": {"type": "number", "exclusiveMinimum": 0, "default": 50},
        "height": {"type": "number", "exclusiveMinimum": 0, "default": 25},
        "unit": UNIT_SCHEMA,
    }, "required": ["width", "height"]},
    operation_class=OperationClass.MUTATE,
)
def draw_center_rectangle(sw, cx: float = 0, cy: float = 0, width: float = 50,
                          height: float = 25, unit: str = "mm") -> dict:
    if not _is_number(width) or not _is_number(height) or width <= 0 or height <= 0:
        return _invalid(sw, "Rectangle width and height must be positive finite numbers.")
    half_width = width / 2.0
    half_height = height / 2.0
    return _create_entity(
        sw, "CreateCenterRectangle",
        [cx - half_width, cy - half_height, 0.0, cx + half_width, cy + half_height, 0.0],
        unit,
        f"Center rectangle created: {width}x{height}{unit}.",
        {"center": [cx, cy], "width": width, "height": height},
    )


def _three_point_rectangle(sw, method, label, points, unit):
    coordinates = []
    for x, y in points:
        coordinates.extend([x, y, 0.0])
    return _create_entity(
        sw, method, coordinates, unit,
        f"{label} created.",
        {"points": [list(point) for point in points]},
    )


@tool(
    name="draw_rectangle_3point_corner",
    description=(
        "Draw a 3-point corner rectangle. The first two points define one edge; "
        "the third sets the opposite corner."
    ),
    schema={"type": "object", "properties": {
        "x1": {"type": "number"}, "y1": {"type": "number"},
        "x2": {"type": "number"}, "y2": {"type": "number"},
        "x3": {"type": "number"}, "y3": {"type": "number"},
        "unit": UNIT_SCHEMA,
    }, "required": ["x1", "y1", "x2", "y2", "x3", "y3"]},
    operation_class=OperationClass.MUTATE,
)
def draw_rectangle_3point_corner(sw, x1: float, y1: float, x2: float, y2: float,
                                 x3: float, y3: float, unit: str = "mm") -> dict:
    return _three_point_rectangle(
        sw, "Create3PointCornerRectangle", "3-point corner rectangle",
        [(x1, y1), (x2, y2), (x3, y3)], unit,
    )


@tool(
    name="draw_rectangle_3point_center",
    description=(
        "Draw a 3-point center rectangle. The first two points define the center "
        "and one corner; the third sets the width direction."
    ),
    schema={"type": "object", "properties": {
        "x1": {"type": "number"}, "y1": {"type": "number"},
        "x2": {"type": "number"}, "y2": {"type": "number"},
        "x3": {"type": "number"}, "y3": {"type": "number"},
        "unit": UNIT_SCHEMA,
    }, "required": ["x1", "y1", "x2", "y2", "x3", "y3"]},
    operation_class=OperationClass.MUTATE,
)
def draw_rectangle_3point_center(sw, x1: float, y1: float, x2: float, y2: float,
                                 x3: float, y3: float, unit: str = "mm") -> dict:
    return _three_point_rectangle(
        sw, "Create3PointCenterRectangle", "3-point center rectangle",
        [(x1, y1), (x2, y2), (x3, y3)], unit,
    )


@tool(
    name="draw_parallelogram",
    description="Draw a parallelogram through three ordered corner points.",
    schema={"type": "object", "properties": {
        "x1": {"type": "number"}, "y1": {"type": "number"},
        "x2": {"type": "number"}, "y2": {"type": "number"},
        "x3": {"type": "number"}, "y3": {"type": "number"},
        "unit": UNIT_SCHEMA,
    }, "required": ["x1", "y1", "x2", "y2", "x3", "y3"]},
    operation_class=OperationClass.MUTATE,
)
def draw_parallelogram(sw, x1: float, y1: float, x2: float, y2: float,
                       x3: float, y3: float, unit: str = "mm") -> dict:
    return _three_point_rectangle(
        sw, "CreateParallelogram", "Parallelogram",
        [(x1, y1), (x2, y2), (x3, y3)], unit,
    )


@tool(
    name="draw_ellipse",
    description=(
        "Draw a full ellipse from center, major radius, minor radius and an "
        "optional in-plane rotation."
    ),
    schema={"type": "object", "properties": {
        "cx": {"type": "number", "default": 0},
        "cy": {"type": "number", "default": 0},
        "major_radius": {"type": "number", "exclusiveMinimum": 0},
        "minor_radius": {"type": "number", "exclusiveMinimum": 0},
        "rotation_deg": {"type": "number", "default": 0},
        "unit": UNIT_SCHEMA,
    }, "required": ["major_radius", "minor_radius"]},
    operation_class=OperationClass.MUTATE,
)
def draw_ellipse(sw, cx: float = 0, cy: float = 0, major_radius: float = 25,
                 minor_radius: float = 12.5, rotation_deg: float = 0,
                 unit: str = "mm") -> dict:
    if (
        not _is_number(major_radius)
        or not _is_number(minor_radius)
        or major_radius <= 0
        or minor_radius <= 0
    ):
        return _invalid(sw, "Ellipse radii must be positive finite numbers.")
    rotation = math.radians(rotation_deg)
    major_x = cx + major_radius * math.cos(rotation)
    major_y = cy + major_radius * math.sin(rotation)
    minor_x = cx - minor_radius * math.sin(rotation)
    minor_y = cy + minor_radius * math.cos(rotation)
    return _create_entity(
        sw, "CreateEllipse",
        [cx, cy, 0.0, major_x, major_y, 0.0, minor_x, minor_y, 0.0],
        unit,
        f"Ellipse created: {major_radius}x{minor_radius}{unit}.",
        {
            "center": [cx, cy],
            "major_radius": major_radius,
            "minor_radius": minor_radius,
            "rotation_deg": rotation_deg,
        },
    )


@tool(
    name="draw_elliptical_arc",
    description=(
        "Draw a partial elliptical arc between two parametric angles of an "
        "ellipse defined by center, radii and in-plane rotation."
    ),
    schema={"type": "object", "properties": {
        "cx": {"type": "number", "default": 0},
        "cy": {"type": "number", "default": 0},
        "major_radius": {"type": "number", "exclusiveMinimum": 0},
        "minor_radius": {"type": "number", "exclusiveMinimum": 0},
        "rotation_deg": {"type": "number", "default": 0},
        "start_angle_deg": {"type": "number", "default": 0},
        "end_angle_deg": {"type": "number", "exclusiveMinimum": 0, "maximum": 360},
        "counter_clockwise": {"type": "boolean", "default": True},
        "unit": UNIT_SCHEMA,
    }, "required": ["major_radius", "minor_radius", "end_angle_deg"]},
    operation_class=OperationClass.MUTATE,
)
def draw_elliptical_arc(sw, cx: float = 0, cy: float = 0, major_radius: float = 25,
                        minor_radius: float = 12.5, rotation_deg: float = 0,
                        start_angle_deg: float = 0, end_angle_deg: float = 180,
                        counter_clockwise: bool = True, unit: str = "mm") -> dict:
    if (
        not _is_number(major_radius)
        or not _is_number(minor_radius)
        or major_radius <= 0
        or minor_radius <= 0
    ):
        return _invalid(sw, "Elliptical arc radii must be positive finite numbers.")
    if not _is_number(end_angle_deg) or not 0 < end_angle_deg <= 360:
        return _invalid(sw, "end_angle_deg must be in (0, 360].")

    rotation = math.radians(rotation_deg)

    def point_at(angle_deg):
        angle = math.radians(angle_deg)
        return (
            cx + major_radius * math.cos(angle) * math.cos(rotation)
            - minor_radius * math.sin(angle) * math.sin(rotation),
            cy + major_radius * math.cos(angle) * math.sin(rotation)
            + minor_radius * math.sin(angle) * math.cos(rotation),
        )

    major_x = cx + major_radius * math.cos(rotation)
    major_y = cy + major_radius * math.sin(rotation)
    minor_x = cx - minor_radius * math.sin(rotation)
    minor_y = cy + minor_radius * math.cos(rotation)
    start_x, start_y = point_at(start_angle_deg)
    end_x, end_y = point_at(end_angle_deg)
    direction = 1 if counter_clockwise else -1
    return _create_entity(
        sw, "CreateEllipticalArc",
        [
            cx, cy, 0.0,
            major_x, major_y, 0.0,
            minor_x, minor_y, 0.0,
            start_x, start_y, 0.0,
            end_x, end_y, 0.0,
        ],
        unit,
        f"Elliptical arc created from {start_angle_deg} to {end_angle_deg} degrees.",
        {
            "center": [cx, cy],
            "major_radius": major_radius,
            "minor_radius": minor_radius,
            "rotation_deg": rotation_deg,
            "start_angle_deg": start_angle_deg,
            "end_angle_deg": end_angle_deg,
            "counter_clockwise": counter_clockwise,
        },
        trailing=[direction],
    )


@tool(
    name="draw_tangent_arc",
    description=(
        "Draw a tangent arc from an existing segment endpoint to a second point. "
        "The first point must be an endpoint of an existing sketch segment."
    ),
    schema={"type": "object", "properties": {
        "start_x": {"type": "number"},
        "start_y": {"type": "number"},
        "end_x": {"type": "number"},
        "end_y": {"type": "number"},
        "unit": UNIT_SCHEMA,
    }, "required": ["start_x", "start_y", "end_x", "end_y"]},
    operation_class=OperationClass.MUTATE,
)
def draw_tangent_arc(sw, start_x: float, start_y: float, end_x: float, end_y: float,
                     unit: str = "mm") -> dict:
    if (start_x, start_y) == (end_x, end_y):
        return _invalid(sw, "Tangent arc start and end points must differ.")
    # ArcType was probed live in SW 2025: values 0-3 all produce an identical
    # arc for a 2D tangent arc, so the flag is fixed at 0 rather than exposed.
    return _create_entity(
        sw, "CreateTangentArc",
        [start_x, start_y, 0.0, end_x, end_y, 0.0],
        unit,
        "Tangent arc created.",
        {"start": [start_x, start_y], "end": [end_x, end_y]},
        trailing=[0],
    )


# swSketchSlotCreationType_e: line=0, center_line=1, arc=2, 3pointarc=3
SW_SLOT_ARC = 2
SW_SLOT_3POINT_ARC = 3

# swSketchSlotLengthType_e: CenterCenter=0, FullLength=1
SW_SLOT_CENTER_CENTER = 0


# CreateSketchSlot order is
# (SlotCreationType, SlotLengthType, Width, X1..Z1, X2..Z2, X3..Z3,
#  CenterArcDirection, AddDimension): two non-coordinate arguments lead, two
# trail, and only the width plus the nine coordinates are unit-converted.
def _slot_call(sw, creation_type, width, points, unit, message, data):
    coordinates = [width]
    for x, y in points:
        coordinates.extend([x, y, 0.0])
    return _create_entity(
        sw, "CreateSketchSlot",
        coordinates,
        unit,
        message,
        data,
        leading=[creation_type, SW_SLOT_CENTER_CENTER],
        trailing=[1, False],
    )


@tool(
    name="draw_arc_slot",
    description=(
        "Draw an arc slot from an arc center, an arc start point and an arc end "
        "point, plus the slot width."
    ),
    schema={"type": "object", "properties": {
        "center_x": {"type": "number"},
        "center_y": {"type": "number"},
        "start_x": {"type": "number"},
        "start_y": {"type": "number"},
        "end_x": {"type": "number"},
        "end_y": {"type": "number"},
        "width": {"type": "number", "exclusiveMinimum": 0},
        "unit": UNIT_SCHEMA,
    }, "required": ["center_x", "center_y", "start_x", "start_y",
                   "end_x", "end_y", "width"]},
    operation_class=OperationClass.MUTATE,
)
def draw_arc_slot(sw, center_x: float, center_y: float, start_x: float, start_y: float,
                  end_x: float, end_y: float, width: float, unit: str = "mm") -> dict:
    points = [(center_x, center_y), (start_x, start_y), (end_x, end_y)]
    if len(set(points)) < 3:
        return _invalid(sw, "Arc slot center, start and end points must be distinct.")
    if not _is_number(width) or width <= 0:
        return _invalid(sw, "Slot width must be a positive finite number.")
    return _slot_call(
        sw, SW_SLOT_ARC, width, points, unit,
        f"Arc slot created with width {width}{unit}.",
        {"center": [center_x, center_y], "start": [start_x, start_y],
         "end": [end_x, end_y], "width": width},
    )


@tool(
    name="draw_arc_slot_3point",
    description=(
        "Draw a 3-point arc slot through three points on the slot centerline, "
        "plus the slot width."
    ),
    schema={"type": "object", "properties": {
        "x1": {"type": "number"}, "y1": {"type": "number"},
        "x2": {"type": "number"}, "y2": {"type": "number"},
        "x3": {"type": "number"}, "y3": {"type": "number"},
        "width": {"type": "number", "exclusiveMinimum": 0},
        "unit": UNIT_SCHEMA,
    }, "required": ["x1", "y1", "x2", "y2", "x3", "y3", "width"]},
    operation_class=OperationClass.MUTATE,
)
def draw_arc_slot_3point(sw, x1: float, y1: float, x2: float, y2: float,
                         x3: float, y3: float, width: float,
                         unit: str = "mm") -> dict:
    points = [(x1, y1), (x2, y2), (x3, y3)]
    if len(set(points)) < 3:
        return _invalid(sw, "Arc slot points must be distinct.")
    if not _is_number(width) or width <= 0:
        return _invalid(sw, "Slot width must be a positive finite number.")
    return _slot_call(
        sw, SW_SLOT_3POINT_ARC, width, points, unit,
        f"3-point arc slot created with width {width}{unit}.",
        {"points": [list(point) for point in points], "width": width},
    )


@tool(
    name="draw_parabola",
    description=(
        "Draw a parabolic segment from a focus, an apex and the two end points "
        "on the curve."
    ),
    schema={"type": "object", "properties": {
        "focus_x": {"type": "number"}, "focus_y": {"type": "number"},
        "apex_x": {"type": "number"}, "apex_y": {"type": "number"},
        "start_x": {"type": "number"}, "start_y": {"type": "number"},
        "end_x": {"type": "number"}, "end_y": {"type": "number"},
        "unit": UNIT_SCHEMA,
    }, "required": ["focus_x", "focus_y", "apex_x", "apex_y",
                   "start_x", "start_y", "end_x", "end_y"]},
    operation_class=OperationClass.MUTATE,
)
def draw_parabola(sw, focus_x: float, focus_y: float, apex_x: float, apex_y: float,
                  start_x: float, start_y: float, end_x: float, end_y: float,
                  unit: str = "mm") -> dict:
    if (focus_x, focus_y) == (apex_x, apex_y):
        return _invalid(sw, "Parabola focus and apex must differ.")
    if (start_x, start_y) == (end_x, end_y):
        return _invalid(sw, "Parabola start and end points must differ.")
    return _create_entity(
        sw, "CreateParabola",
        [
            focus_x, focus_y, 0.0,
            apex_x, apex_y, 0.0,
            start_x, start_y, 0.0,
            end_x, end_y, 0.0,
        ],
        unit,
        "Parabolic segment created.",
        {
            "focus": [focus_x, focus_y],
            "apex": [apex_x, apex_y],
            "start": [start_x, start_y],
            "end": [end_x, end_y],
        },
    )
