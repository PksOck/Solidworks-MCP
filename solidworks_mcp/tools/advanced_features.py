"""Advanced part features that do not belong to the sketch workflow."""

import math

from ..comutil import com
from ..constants import SwErrors
from ..core.policy import OperationClass
from ..registry import tool
from .export import _get_planar_face_by_index


SW_DOC_PART = 1


def _feature_signatures(document):
    """Return stable top-level feature signatures while retaining COM proxies."""
    signatures = []
    proxies = []
    feature = com(document, "FirstFeature")
    while feature is not None:
        proxies.append(feature)
        signatures.append((com(feature, "Name"), com(feature, "GetTypeName2")))
        feature = com(feature, "GetNextFeature")
    return signatures, proxies


@tool(
    name="shell_feature",
    description=(
        "Shell the active part and optionally remove planar faces identified by "
        "indices from list_planar_faces on the current model state."
    ),
    schema={"type": "object", "properties": {
        "thickness": {"type": "number", "exclusiveMinimum": 0},
        "unit": {"type": "string", "enum": ["mm", "cm", "m", "inch"], "default": "mm"},
        "remove_face_indices": {
            "type": "array",
            "items": {"type": "integer", "minimum": 0},
            "uniqueItems": True,
            "default": [],
        },
        "outward": {"type": "boolean", "default": False},
    }, "required": ["thickness"]},
    operation_class=OperationClass.MUTATE,
)
def shell_feature(sw, thickness: float, unit: str = "mm",
                  remove_face_indices=None, outward: bool = False) -> dict:
    face_indices = [] if remove_face_indices is None else remove_face_indices
    indices_valid = (
        isinstance(face_indices, list)
        and all(
            isinstance(index, int) and not isinstance(index, bool) and index >= 0
            for index in face_indices
        )
        and len(face_indices) == len(set(face_indices))
    )
    if (
        isinstance(thickness, bool)
        or not isinstance(thickness, (int, float))
        or not math.isfinite(thickness)
        or thickness <= 0
        or not indices_valid
        or not isinstance(outward, bool)
    ):
        return sw._result(
            False,
            "thickness must be a finite positive number; face indices must be "
            "distinct non-negative integers; outward must be boolean.",
            SwErrors.swInvalidInput,
            {"code": "VALIDATION_FAILED"},
        )

    try:
        thickness_m = sw._units.to_meters(thickness, unit)
    except (KeyError, TypeError, ValueError) as conversion_error:
        return sw._result(
            False,
            f"Invalid shell thickness: {conversion_error}",
            SwErrors.swInvalidInput,
            {"code": "VALIDATION_FAILED"},
        )

    document, error = sw.get_active_doc()
    if error:
        return error
    if com(document, "GetType") != SW_DOC_PART:
        return sw._result(
            False, "Active document is not a part.", SwErrors.swInvalidFileType
        )

    before, before_proxies = _feature_signatures(document)
    try:
        com(document, "ClearSelection2", True)
        selection_manager = com(document, "SelectionManager")
        for position, face_index in enumerate(face_indices):
            face = _get_planar_face_by_index(document, face_index)
            if face is None:
                return sw._result(
                    False,
                    f"remove_face_indices contains no current planar face at "
                    f"index {face_index}; re-run list_planar_faces.",
                    SwErrors.swSelectionError,
                )
            select_data = com(selection_manager, "CreateSelectData")
            select_data.Mark = 1
            if not com(face, "Select4", position > 0, select_data):
                return sw._result(
                    False,
                    f"Could not select planar face {face_index} for removal.",
                    SwErrors.swSelectionError,
                )

        com(document, "InsertFeatureShell", thickness_m, outward)
        after, after_proxies = _feature_signatures(document)
        del before_proxies, after_proxies
        new_shells = [
            signature for signature in after
            if signature not in before and "shell" in signature[1].casefold()
        ]
        if not new_shells:
            return sw._result(
                False,
                "SolidWorks did not create a shell feature. The thickness may "
                "be too large for the current geometry.",
                SwErrors.swFeatureError,
            )
        feature_name, feature_type = new_shells[-1]
    except Exception as create_error:
        return sw._result(
            False, f"Shell creation failed: {create_error}", SwErrors.swFeatureError
        )
    finally:
        com(document, "ClearSelection2", True)

    return sw._result(
        True,
        f"Created shell feature {feature_name}.",
        data={
            "feature_name": feature_name,
            "feature_type": feature_type,
            "thickness": thickness,
            "unit": unit,
            "thickness_m": thickness_m,
            "remove_face_indices": face_indices,
            "outward": outward,
        },
    )
