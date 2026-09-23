"""Advanced part features that do not belong to the sketch workflow."""

import math

from ..comutil import com
from ..constants import SwErrors
from ..core.policy import OperationClass
from ..registry import tool
from .export import _get_planar_face_by_index


SW_DOC_PART = 1
SW_FM_SWEEP = 17
SW_FM_SWEEP_CUT = 18
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
    return _sweep(sw, profile_sketch, path_sketch, SW_FM_SWEEP, "sweep")


def _sweep(sw, profile_sketch, path_sketch, definition, label):
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
        feature_data = com(feature_manager, "CreateDefinition", definition)
        if feature_data is None:
            return sw._result(
                False, f"SolidWorks could not create a {label} feature definition.",
                SwErrors.swFeatureError,
            )
        feature = com(feature_manager, "CreateFeature", feature_data)
    except Exception as create_error:
        return sw._result(False, f"{label.capitalize()} creation failed: "
                          f"{create_error}", SwErrors.swFeatureError)
    finally:
        com(document, "ClearSelection2", True)

    return _finish_feature(
        sw, document, feature,
        f"Created {label} feature {{name}}.",
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
    return _loft(sw, profile_sketches, False)


def _loft(sw, profile_sketches, cut):
    label = "loft cut" if cut else "loft"
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
        if cut:
            # Live-verified in api-findings §31; the tlb has no InsertCutBlend2.
            feature = com(
                document.FeatureManager, "InsertCutBlend",
                False, True, False, 1.0, 0, 0, False, 0.0, 0.0, 0, True, True,
            )
        else:
            feature = com(
                document.FeatureManager, "InsertProtrusionBlend2",
                False, True, True, 0, 0, 0, 0, 0, True, True, False,
                0.0, 0.0, 0, True, True, True, SW_LOFT_GUIDE_INFLUENCE_GLOBAL,
            )
    except Exception as create_error:
        return sw._result(False, f"{label.capitalize()} creation failed: "
                          f"{create_error}", SwErrors.swFeatureError)
    finally:
        com(document, "ClearSelection2", True)

    return _finish_feature(
        sw, document, feature,
        f"Created {label} feature {{name}}.",
        {"profile_sketches": names},
    )


@tool(
    name="revolve_cut",
    description=(
        "Revolve one closed sketch as a cut through the active part. The "
        "sketch must hold exactly one centerline as the axis, so draw the "
        "profile with draw_rectangle rather than draw_center_rectangle, whose "
        "construction diagonals make the axis ambiguous. angle is in degrees."
    ),
    schema={"type": "object", "properties": {
        "sketch": {"type": "string"},
        "angle": {"type": "number", "default": 360},
    }, "required": ["sketch"]},
    operation_class=OperationClass.MUTATE,
)
def revolve_cut(sw, sketch: str, angle: float = 360) -> dict:
    if (
        not isinstance(sketch, str) or not sketch.strip()
        or isinstance(angle, bool) or not isinstance(angle, (int, float))
        or not 0 < angle <= 360
    ):
        return sw._result(
            False, "sketch must be a non-empty name and angle in (0, 360].",
            SwErrors.swInvalidInput, {"code": "VALIDATION_FAILED"},
        )

    document, error = sw.get_active_doc()
    if error:
        return error
    if com(document, "GetType") != SW_DOC_PART:
        return sw._result(False, "Active document is not a part.",
                          SwErrors.swInvalidFileType)

    profile = _find_feature(document, sketch)
    if profile is None:
        return sw._result(False, f"Sketch not found: {sketch}",
                          SwErrors.swSelectionError)

    try:
        com(document, "ClearSelection2", True)
        if not _select_with_mark(document, profile, False, 0):
            return sw._result(False, f"Could not select sketch: {sketch}",
                              SwErrors.swSelectionError)
        # FeatureRevolve2 with IsCut=True (4th argument); live-verified §31.
        feature = com(
            document.FeatureManager, "FeatureRevolve2",
            True, True, False, True, False, False, 0, 0,
            math.radians(angle), 0.0, False, False, 0.0, 0.0, 0, 0.0, 0.0,
            True, True, True,
        )
    except Exception as create_error:
        return sw._result(False, f"Revolve cut creation failed: {create_error}",
                          SwErrors.swFeatureError)
    finally:
        com(document, "ClearSelection2", True)

    return _finish_feature(
        sw, document, feature,
        "Created revolve cut feature {name}.",
        {"sketch": sketch, "angle": angle},
    )


@tool(
    name="sweep_cut",
    description=(
        "Sweep one closed profile sketch along one path sketch as a cut "
        "through the active part. Use exact sketch feature names."
    ),
    schema={"type": "object", "properties": {
        "profile_sketch": {"type": "string"},
        "path_sketch": {"type": "string"},
    }, "required": ["profile_sketch", "path_sketch"]},
    operation_class=OperationClass.MUTATE,
)
def sweep_cut(sw, profile_sketch: str, path_sketch: str) -> dict:
    return _sweep(sw, profile_sketch, path_sketch, SW_FM_SWEEP_CUT, "sweep cut")


@tool(
    name="loft_cut",
    description=(
        "Loft two or more ordered profile sketches as a cut through the "
        "active part. Profile order follows the list order."
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
def loft_cut(sw, profile_sketches) -> dict:
    return _loft(sw, profile_sketches, True)


SW_NET_BLEND_BOSS = 1
SW_NET_BLEND_CUT = 3


def _boundary(sw, profile_sketches, cut):
    label = "boundary cut" if cut else "boundary"
    names = list(profile_sketches) if isinstance(profile_sketches, list) else []
    names_valid = (
        2 <= len(names) <= 3
        and all(isinstance(name, str) and name.strip() for name in names)
        and len(names) == len({name.strip() for name in names})
    )
    if not names_valid:
        return sw._result(
            False,
            "profile_sketches must list two or three distinct non-empty sketch "
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
        # Direction 1 curve marks are 8193, 16385, 24577 (InsertNetBlend help).
        for position, profile in enumerate(profiles):
            if not _select_with_mark(document, profile, position > 0,
                                     8192 * (position + 1) + 1):
                return sw._result(
                    False, f"Could not select profile: {names[position]}",
                    SwErrors.swSelectionError,
                )
        feature_manager = com(document, "FeatureManager")
        for position in range(len(names)):
            com(feature_manager, "SetNetBlendCurveData",
                0, position, 0, 0.0, 1.0, True)
        for direction in (0, 1):
            com(feature_manager, "SetNetBlendDirectionData",
                direction, 0, 0, False, False)
        before = com(com(document, "FeatureByPositionReverse", 0), "Name")
        # InsertNetBlend returns None even when it succeeds (api-findings §32),
        # so the new feature is read back from the end of the tree.
        com(feature_manager, "InsertNetBlend",
            SW_NET_BLEND_CUT if cut else SW_NET_BLEND_BOSS, len(names), 0,
            False, 1.0, True, True, True, True, False, 0.0, 0.0, False, 0,
            False, False, 0.0, False, 0.0, False)
        feature = com(document, "FeatureByPositionReverse", 0)
        expected_type = "NetBlendCut" if cut else "NetBlend"
        if (
            com(feature, "Name") == before
            or com(feature, "GetTypeName2") != expected_type
        ):
            feature = None
    except Exception as create_error:
        return sw._result(False, f"{label.capitalize()} creation failed: "
                          f"{create_error}", SwErrors.swFeatureError)
    finally:
        com(document, "ClearSelection2", True)

    return _finish_feature(
        sw, document, feature,
        f"Created {label} feature {{name}}.",
        {"profile_sketches": names},
    )


_BOUNDARY_SCHEMA = {"type": "object", "properties": {
    "profile_sketches": {
        "type": "array",
        "items": {"type": "string"},
        "minItems": 2,
        "maxItems": 3,
    },
}, "required": ["profile_sketches"]}


@tool(
    name="boundary_boss",
    description=(
        "Create a boundary boss through two or three ordered profile sketches "
        "on the active part (one direction, no tangency conditions). Use exact "
        "sketch feature names."
    ),
    schema=_BOUNDARY_SCHEMA,
    operation_class=OperationClass.MUTATE,
)
def boundary_boss(sw, profile_sketches) -> dict:
    return _boundary(sw, profile_sketches, False)


@tool(
    name="boundary_cut",
    description=(
        "Cut a boundary shape through two or three ordered profile sketches "
        "from the active part (one direction, no tangency conditions)."
    ),
    schema=_BOUNDARY_SCHEMA,
    operation_class=OperationClass.MUTATE,
)
def boundary_cut(sw, profile_sketches) -> dict:
    return _boundary(sw, profile_sketches, True)


@tool(
    name="draft_faces",
    description=(
        "Draft planar faces of the active part about a planar neutral face. "
        "Face indices come from list_planar_faces on the current model state "
        "(identify faces by area and point, not only by normal). angle is in "
        "degrees; flip reverses the draft direction."
    ),
    schema={"type": "object", "properties": {
        "angle": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 90},
        "neutral_face_index": {"type": "integer", "minimum": 0},
        "draft_face_indices": {
            "type": "array",
            "items": {"type": "integer", "minimum": 0},
            "minItems": 1,
            "uniqueItems": True,
        },
        "flip": {"type": "boolean", "default": False},
    }, "required": ["angle", "neutral_face_index", "draft_face_indices"]},
    operation_class=OperationClass.MUTATE,
)
def draft_faces(sw, angle: float, neutral_face_index: int,
                draft_face_indices, flip: bool = False) -> dict:
    def is_index(value):
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0

    faces = draft_face_indices if isinstance(draft_face_indices, list) else []
    if (
        isinstance(angle, bool) or not isinstance(angle, (int, float))
        or not 0 < angle < 90
        or not is_index(neutral_face_index)
        or not faces or not all(is_index(index) for index in faces)
        or len(faces) != len(set(faces)) or neutral_face_index in faces
        or not isinstance(flip, bool)
    ):
        return sw._result(
            False,
            "angle must be in (0, 90); neutral_face_index and draft_face_indices "
            "must be distinct non-negative integers with at least one drafted "
            "face; flip must be boolean.",
            SwErrors.swInvalidInput,
            {"code": "VALIDATION_FAILED"},
        )

    document, error = sw.get_active_doc()
    if error:
        return error
    if com(document, "GetType") != SW_DOC_PART:
        return sw._result(False, "Active document is not a part.",
                          SwErrors.swInvalidFileType)

    try:
        com(document, "ClearSelection2", True)
        # Neutral plane mark 1, faces to draft mark 2 (InsertMultiFaceDraft help).
        for position, (face_index, mark) in enumerate(
            [(neutral_face_index, 1)] + [(index, 2) for index in faces]
        ):
            face = _get_planar_face_by_index(document, face_index)
            if face is None:
                return sw._result(
                    False,
                    f"No current planar face at index {face_index}; re-run "
                    "list_planar_faces.",
                    SwErrors.swSelectionError,
                )
            if not _select_with_mark(document, face, position > 0, mark):
                return sw._result(False, f"Could not select face {face_index}.",
                                  SwErrors.swSelectionError)
        feature = com(document.FeatureManager, "InsertMultiFaceDraft",
                      math.radians(angle), flip, False, 0, False, False)
    except Exception as create_error:
        return sw._result(False, f"Draft creation failed: {create_error}",
                          SwErrors.swFeatureError)
    finally:
        com(document, "ClearSelection2", True)

    return _finish_feature(
        sw, document, feature,
        "Created draft feature {name}.",
        {"angle": angle, "neutral_face_index": neutral_face_index,
         "draft_face_indices": faces, "flip": flip},
    )
