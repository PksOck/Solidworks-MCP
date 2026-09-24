"""Operations on explicitly selected solid bodies.

SOLIDWORKS 2025 TLB: IBody2.Select2(Append, Data),
IFeatureManager.InsertScale(Type, Uniform, Xscale, YScale, ZScale).
swScaleAboutCentroid=0, swScaleAboutOrigin=1 (swconst.tlb).
"""

import math

from ..comutil import com
from ..constants import SwErrors
from ..core.policy import OperationClass
from ..registry import tool


@tool(
    name="scale_body",
    description="Uniformly scale one solid body by index about its centroid or the part origin.",
    schema={"type": "object", "properties": {
        "body_index": {"type": "integer", "minimum": 0,
                       "description": "Zero-based index in the visible solid body list."},
        "factor": {"type": "number", "exclusiveMinimum": 0},
        "origin": {"type": "string", "enum": ["centroid", "origin"],
                   "default": "centroid"},
    }, "required": ["body_index", "factor"]},
    operation_class=OperationClass.MUTATE,
)
def scale_body(sw, body_index: int, factor: float, origin: str = "centroid") -> dict:
    if (isinstance(body_index, bool) or not isinstance(body_index, int)
            or body_index < 0 or isinstance(factor, bool)
            or not isinstance(factor, (int, float)) or not math.isfinite(factor)
            or factor <= 0 or origin not in ("centroid", "origin")):
        return sw._result(False, "Invalid body index, scale factor, or origin.",
                          SwErrors.swInvalidInput, {"code": "VALIDATION_FAILED"})
    document, error = sw.get_active_doc()
    if error:
        return error
    if com(document, "GetType") != 1:
        return sw._result(False, "Scaling requires a part.", SwErrors.swInvalidFileType)
    try:
        bodies = com(document, "GetBodies2", 0, True) or []
        if body_index >= len(bodies):
            return sw._result(False, "Solid body index is out of range.",
                              SwErrors.swInvalidInput, {"code": "BODY_NOT_FOUND"})
        com(document, "ClearSelection2", True)
        select_data = com(com(document, "SelectionManager"), "CreateSelectData")
        if not com(bodies[body_index], "Select2", False, select_data):
            return sw._result(False, "Could not select solid body.",
                              SwErrors.swSelectionError)
        feature = com(com(document, "FeatureManager"), "InsertScale",
                      0 if origin == "centroid" else 1, True,
                      float(factor), float(factor), float(factor))
        if feature is None:
            return sw._result(False, "SolidWorks did not create a Scale feature.",
                              SwErrors.swFeatureError)
        return sw._result(True, "Scaled solid body.", data={
            "feature_name": str(com(feature, "Name")), "body_index": body_index,
            "factor": factor, "origin": origin,
        })
    except Exception as exc:
        return sw._result(False, f"Scaling solid body failed: {exc}",
                          SwErrors.swFeatureError)
    finally:
        com(document, "ClearSelection2", True)


@tool(
    name="delete_body",
    description="Delete a selected solid body or keep only that body in a multibody part.",
    schema={"type": "object", "properties": {
        "body_index": {"type": "integer", "minimum": 0},
        "keep_only": {"type": "boolean", "default": False},
    }, "required": ["body_index"]},
    operation_class=OperationClass.MUTATE,
)
def delete_body(sw, body_index: int, keep_only: bool = False) -> dict:
    if (isinstance(body_index, bool) or not isinstance(body_index, int)
            or body_index < 0 or not isinstance(keep_only, bool)):
        return sw._result(False, "Invalid body index or keep_only flag.",
                          SwErrors.swInvalidInput, {"code": "VALIDATION_FAILED"})
    document, error = sw.get_active_doc()
    if error:
        return error
    if com(document, "GetType") != 1:
        return sw._result(False, "Delete/Keep Body requires a part.",
                          SwErrors.swInvalidFileType)
    try:
        bodies = com(document, "GetBodies2", 0, True) or []
        if len(bodies) < 2 or body_index >= len(bodies):
            return sw._result(False, "Select a body in a multibody part.",
                              SwErrors.swInvalidInput, {"code": "BODY_NOT_FOUND"})
        before_count = len(bodies)
        before_volume = sum(float(com(body, "GetMassProperties", 0.0)[3]) * 1e9
                            for body in bodies)
        com(document, "ClearSelection2", True)
        selection = com(com(document, "SelectionManager"), "CreateSelectData")
        if not com(bodies[body_index], "Select2", False, selection):
            return sw._result(False, "Could not select solid body.",
                              SwErrors.swSelectionError)
        # SW2025 IFeatureManager.InsertDeleteBody2(KeepBodies)
        feature = com(com(document, "FeatureManager"), "InsertDeleteBody2", keep_only)
        remaining = com(document, "GetBodies2", 0, True) or []
        after_volume = sum(float(com(body, "GetMassProperties", 0.0)[3]) * 1e9
                           for body in remaining)
        expected_count = 1 if keep_only else before_count - 1
        if feature is None or len(remaining) != expected_count or after_volume >= before_volume:
            return sw._result(False, "Delete/Keep Body did not remove expected geometry.",
                              SwErrors.swFeatureError,
                              {"bodies_before": before_count, "bodies_after": len(remaining),
                               "volume_before_mm3": before_volume,
                               "volume_after_mm3": after_volume})
        return sw._result(True, f"Created Delete/Keep Body {com(feature, 'Name')}.", data={
            "feature_name": str(com(feature, "Name")), "keep_only": keep_only,
            "body_index": body_index, "bodies_before": before_count,
            "bodies_after": len(remaining), "volume_before_mm3": before_volume,
            "volume_after_mm3": after_volume,
        })
    except Exception as exc:
        return sw._result(False, f"Delete/Keep Body failed: {exc}",
                          SwErrors.swFeatureError)
    finally:
        com(document, "ClearSelection2", True)
