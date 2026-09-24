"""Reference geometry creation tools."""

import math

import pythoncom
import win32com.client

from ..comutil import com
from ..constants import SwErrors
from ..core.policy import OperationClass
from ..registry import tool


SW_REF_PLANE_DISTANCE = 8
SW_REF_PLANE_DISTANCE_REVERSED = 264


@tool(
    name="create_reference_axis",
    description="Create an axis along the intersection of two distinct, exactly named planes.",
    schema={"type": "object", "properties": {
        "first_plane": {"type": "string", "minLength": 1},
        "second_plane": {"type": "string", "minLength": 1},
    }, "required": ["first_plane", "second_plane"]},
    operation_class=OperationClass.MUTATE,
)
def create_reference_axis(sw, first_plane: str, second_plane: str) -> dict:
    if (not isinstance(first_plane, str) or not first_plane.strip()
            or not isinstance(second_plane, str) or not second_plane.strip()
            or first_plane.strip() == second_plane.strip()):
        return sw._result(False, "Select two distinct named planes.",
                          SwErrors.swInvalidInput, {"code": "VALIDATION_FAILED"})
    document, error = sw.get_active_doc()
    if error:
        return error
    if com(document, "GetType") != 1:
        return sw._result(False, "An axis requires a part.", SwErrors.swInvalidFileType)
    def axes():
        found = []
        feature = com(document, "FirstFeature")
        while feature is not None:
            if com(feature, "GetTypeName2") == "RefAxis":
                found.append(str(com(feature, "Name")))
            feature = com(feature, "GetNextFeature")
        return found
    try:
        before = axes()
        com(document, "ClearSelection2", True)
        empty = win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)
        extension = com(document, "Extension")
        for index, name in enumerate((first_plane, second_plane)):
            if not com(extension, "SelectByID2", name, "PLANE", 0.0, 0.0, 0.0,
                       index > 0, 0, empty, 0):
                return sw._result(False, f"Plane not found: {name}",
                                  SwErrors.swSelectionError)
        inserted = com(document, "InsertAxis2", True)
        created = [name for name in axes() if name not in before]
        if not inserted or not created:
            return sw._result(False, "SolidWorks did not create a reference axis.",
                              SwErrors.swFeatureError)
        return sw._result(True, f"Created reference axis {created[-1]}.", data={
            "feature_name": created[-1], "first_plane": first_plane,
            "second_plane": second_plane,
        })
    except Exception as create_error:
        return sw._result(False, f"Reference axis failed: {create_error}",
                          SwErrors.swFeatureError)
    finally:
        com(document, "ClearSelection2", True)


@tool(
    name="create_reference_plane",
    description="Create an offset reference plane from one exactly named existing plane.",
    schema={"type": "object", "properties": {
        "base_plane": {"type": "string", "description": "Exact plane name from list_planes."},
        "offset": {"type": "number", "exclusiveMinimum": 0},
        "unit": {"type": "string", "enum": ["mm", "cm", "m", "inch"], "default": "mm"},
        "reverse_direction": {"type": "boolean", "default": False},
    }, "required": ["base_plane", "offset"]},
    operation_class=OperationClass.MUTATE,
)
def create_reference_plane(sw, base_plane: str, offset: float, unit: str = "mm",
                           reverse_direction: bool = False) -> dict:
    if (
        not isinstance(base_plane, str)
        or not base_plane.strip()
        or isinstance(offset, bool)
        or not isinstance(offset, (int, float))
        or not math.isfinite(offset)
        or offset <= 0
    ):
        return sw._result(
            False,
            "base_plane must be non-empty and offset must be a finite positive number.",
            SwErrors.swInvalidInput,
            {"code": "VALIDATION_FAILED"},
        )

    try:
        offset_m = sw._units.to_meters(offset, unit)
    except (KeyError, TypeError, ValueError) as conversion_error:
        return sw._result(
            False,
            f"Invalid reference-plane offset: {conversion_error}",
            SwErrors.swInvalidInput,
            {"code": "VALIDATION_FAILED"},
        )

    document, error = sw.get_active_doc()
    if error:
        return error

    try:
        com(document, "ClearSelection2", True)
        extension = com(document, "Extension")
        empty = win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)
        selected = com(
            extension,
            "SelectByID2",
            base_plane,
            "PLANE",
            0.0,
            0.0,
            0.0,
            False,
            0,
            empty,
            0,
        )
        if not selected:
            return sw._result(
                False,
                f"Reference plane not found by exact name: {base_plane}",
                SwErrors.swSelectionError,
            )

        constraint = (
            SW_REF_PLANE_DISTANCE_REVERSED
            if reverse_direction
            else SW_REF_PLANE_DISTANCE
        )
        feature_manager = com(document, "FeatureManager")
        reference_plane = com(
            feature_manager, "InsertRefPlane", constraint, offset_m, 0, 0, 0, 0
        )
        if reference_plane is None:
            return sw._result(
                False,
                "SolidWorks did not create the reference plane.",
                SwErrors.swFeatureError,
            )
    except Exception as create_error:
        return sw._result(
            False,
            f"Reference plane creation failed: {create_error}",
            SwErrors.swFeatureError,
        )
    finally:
        com(document, "ClearSelection2", True)

    return sw._result(
        True,
        f"Created an offset reference plane from {base_plane}.",
        data={
            "base_plane": base_plane,
            "offset": offset,
            "unit": unit,
            "offset_m": offset_m,
            "reverse_direction": reverse_direction,
            "constraint": constraint,
            "next_step": "Call list_planes to read the generated plane name.",
        },
    )
