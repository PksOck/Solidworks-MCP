"""Advanced part features that do not belong to the sketch workflow."""

import math

from ..comutil import com
from ..constants import SwErrors
from ..core.policy import OperationClass
from ..registry import tool
from .export import _get_planar_face_by_index


SW_DOC_PART = 1
SW_FM_SWEEP = 17
SW_LOFT_GUIDE_INFLUENCE_GLOBAL = 3


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


def _find_feature(document, name):
    feature = com(document, "FirstFeature")
    while feature is not None:
        if com(feature, "Name") == name:
            return feature
        feature = com(feature, "GetNextFeature")
    return None


def _select_with_mark(document, feature, append, mark):
    selection_manager = com(document, "SelectionManager")
    select_data = com(selection_manager, "CreateSelectData")
    select_data.Mark = mark
    return com(feature, "Select4", append, select_data)


def _remove_broken_feature(sw, document, feature):
    """Delete a feature SolidWorks created with a rebuild error; return error text."""
    try:
        com(document, "ClearSelection2", True)
        com(feature, "Select2", False, 0)
        com(document, "EditDelete")
    except Exception as remove_error:
        return str(remove_error)
    finally:
        com(document, "ClearSelection2", True)
    return None


def _finish_feature(sw, document, feature, success_message, data):
    """Validate a newly created feature, removing it when SolidWorks reports an error."""
    if feature is None:
        return sw._result(False, "SolidWorks did not create the feature.",
                          SwErrors.swFeatureError)
    feature_name = com(feature, "Name")
    error_code = com(feature, "GetErrorCode")
    if error_code:
        cleanup_error = _remove_broken_feature(sw, document, feature)
        return sw._result(
            False,
            f"SolidWorks created {feature_name} but the feature has error code "
            f"{error_code}; the broken feature was removed. Check that the "
            "selected profiles and path produce valid geometry.",
            SwErrors.swFeatureError,
            {
                "code": "FEATURE_REBUILD_FAILED",
                "feature_name": feature_name,
                "feature_error_code": int(error_code),
                "removed": cleanup_error is None,
                "cleanup_error": cleanup_error,
            },
        )
    data = dict(data)
    data["feature_name"] = feature_name
    return sw._result(True, success_message.format(name=feature_name), data=data)


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


@tool(
    name="sweep_sketch",
    description=(
        "Sweep one closed profile sketch along one path sketch on the active "
        "part. Use exact sketch feature names and keep the path perpendicular "
        "to the profile at its start."
    ),
    schema={"type": "object", "properties": {
        "profile_sketch": {"type": "string"},
        "path_sketch": {"type": "string"},
    }, "required": ["profile_sketch", "path_sketch"]},
    operation_class=OperationClass.MUTATE,
)
def sweep_sketch(sw, profile_sketch: str, path_sketch: str) -> dict:
    if (
        not isinstance(profile_sketch, str)
        or not profile_sketch.strip()
        or not isinstance(path_sketch, str)
        or not path_sketch.strip()
        or profile_sketch.strip() == path_sketch.strip()
    ):
        return sw._result(
            False,
            "profile_sketch and path_sketch must be two distinct non-empty "
            "sketch names.",
            SwErrors.swInvalidInput,
            {"code": "VALIDATION_FAILED"},
        )

    document, error = sw.get_active_doc()
    if error:
        return error
    if com(document, "GetType") != SW_DOC_PART:
        return sw._result(False, "Active document is not a part.",
                          SwErrors.swInvalidFileType)

    profile = _find_feature(document, profile_sketch)
    path = _find_feature(document, path_sketch)
    if profile is None or path is None:
        missing = profile_sketch if profile is None else path_sketch
        return sw._result(False, f"Sketch not found: {missing}",
                          SwErrors.swSelectionError)

    try:
        com(document, "ClearSelection2", True)
        if not _select_with_mark(document, profile, False, 1):
            return sw._result(False, f"Could not select profile: {profile_sketch}",
                              SwErrors.swSelectionError)
        if not _select_with_mark(document, path, True, 4):
            return sw._result(False, f"Could not select path: {path_sketch}",
                              SwErrors.swSelectionError)
        feature_manager = com(document, "FeatureManager")
        feature_data = com(feature_manager, "CreateDefinition", SW_FM_SWEEP)
        if feature_data is None:
            return sw._result(
                False, "SolidWorks could not create a sweep feature definition.",
                SwErrors.swFeatureError,
            )
        feature = com(feature_manager, "CreateFeature", feature_data)
    except Exception as create_error:
        return sw._result(False, f"Sweep creation failed: {create_error}",
                          SwErrors.swFeatureError)
    finally:
        com(document, "ClearSelection2", True)

    return _finish_feature(
        sw, document, feature,
        "Created sweep feature {name}.",
        {"profile_sketch": profile_sketch, "path_sketch": path_sketch},
    )


@tool(
    name="loft_sketches",
    description=(
        "Loft two or more ordered profile sketches on the active part. Profile "
        "order follows the list order. Use exact sketch feature names."
    ),
    schema={"type": "object", "properties": {
        "profile_sketches": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 2,
        },
    }, "required": ["profile_sketches"]},
    operation_class=OperationClass.MUTATE,
)
def loft_sketches(sw, profile_sketches) -> dict:
    names = list(profile_sketches) if isinstance(profile_sketches, list) else []
    names_valid = (
        len(names) >= 2
        and all(isinstance(name, str) and name.strip() for name in names)
        and len(names) == len({name.strip() for name in names})
    )
    if not names_valid:
        return sw._result(
            False,
            "profile_sketches must list at least two distinct non-empty sketch "
            "names.",
            SwErrors.swInvalidInput,
            {"code": "VALIDATION_FAILED"},
        )

    document, error = sw.get_active_doc()
    if error:
        return error
    if com(document, "GetType") != SW_DOC_PART:
        return sw._result(False, "Active document is not a part.",
                          SwErrors.swInvalidFileType)

    profiles = [_find_feature(document, name) for name in names]
    missing = [name for name, profile in zip(names, profiles) if profile is None]
    if missing:
        return sw._result(False, f"Sketch not found: {', '.join(missing)}",
                          SwErrors.swSelectionError)

    try:
        com(document, "ClearSelection2", True)
        for position, profile in enumerate(profiles):
            if not _select_with_mark(document, profile, position > 0, 1):
                return sw._result(
                    False, f"Could not select profile: {names[position]}",
                    SwErrors.swSelectionError,
                )
        feature = com(
            document.FeatureManager, "InsertProtrusionBlend2",
            False, True, True, 0, 0, 0, 0, 0, True, True, False,
            0.0, 0.0, 0, True, True, True, SW_LOFT_GUIDE_INFLUENCE_GLOBAL,
        )
    except Exception as create_error:
        return sw._result(False, f"Loft creation failed: {create_error}",
                          SwErrors.swFeatureError)
    finally:
        com(document, "ClearSelection2", True)

    return _finish_feature(
        sw, document, feature,
        "Created loft feature {name}.",
        {"profile_sketches": names},
    )
