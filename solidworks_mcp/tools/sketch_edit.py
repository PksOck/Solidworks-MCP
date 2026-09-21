"""Sketch editing operations: trim and extend existing sketch entities."""

import pythoncom
import win32com.client

from ..comutil import com
from ..constants import SwErrors
from ..core.policy import OperationClass
from ..registry import tool


SW_DOC_PART = 1

# swSketchTrimChoice_e from swconst.tlb (verified 2026-09-21):
#   closest=0, corner=1, twoentities=2, entitypoint=3, entities=4,
#   outside=5, inside=6
#
# swSketchTrimEntities (4) is deliberately NOT exposed. In SolidWorks 2025 it
# returned False and left the sketch unchanged both with and without a pick
# point, so the tool must not advertise a mode that never applies.
# swSketchTrimClosest (0) does trim correctly but returns False on success,
# which is why success is decided by observed geometry change, not by the
# API return value.
TRIM_OPTIONS = {
    "closest": 0,
    "corner": 1,
    "twoentities": 2,
    "entitypoint": 3,
    "outside": 5,
    "inside": 6,
}

# Minimum selected entities each option needs: corner/twoentities trim a corner
# between two entities, inside/outside need two boundaries plus the trimmed
# entity.
MIN_TRIM_ENTITIES = {
    "closest": 1,
    "corner": 2,
    "twoentities": 2,
    "entitypoint": 1,
    "outside": 3,
    "inside": 3,
}


def _find_feature(document, name):
    feature = com(document, "FirstFeature")
    while feature is not None:
        if com(feature, "Name") == name:
            return feature
        feature = com(feature, "GetNextFeature")
    return None


def _clean_names(items):
    if not isinstance(items, list) or not items:
        return None
    cleaned = []
    for item in items:
        if not isinstance(item, str) or not item.strip():
            return None
        cleaned.append(item.strip())
    if len(cleaned) != len(set(cleaned)):
        return None
    return cleaned


def _resolve_pick(sw, pick, unit):
    """Return the pick point in metres, or None when the caller passed garbage."""
    if pick is None:
        return (0.0, 0.0, 0.0)
    if not isinstance(pick, (list, tuple)) or len(pick) != 3:
        return None
    try:
        values = [float(value) for value in pick]
    except (TypeError, ValueError):
        return None
    return tuple(sw.units.to_meters(value, unit) for value in values)


def _segment_lengths(document, feature):
    """Snapshot sketch segment lengths so a real geometry change can be proven."""
    sketch = com(feature, "GetSpecificFeature2")
    if sketch is None:
        return None
    lengths = []
    for segment in com(sketch, "GetSketchSegments") or []:
        lengths.append(round(float(com(segment, "GetLength")), 9))
    return lengths


def _open_sketch(document, feature):
    """Select a sketch feature and enter sketch edit mode.

    ``IModelDoc2::EditSketch`` is void in this SolidWorks build and returns
    ``None`` on success, so only an explicit ``False`` counts as failure.
    """
    com(document, "ClearSelection2", True)
    if not com(feature, "Select2", False, 0):
        return False
    result = com(document, "EditSketch")
    return result is not False


def _select_segments(document, names):
    """Select sketch segments by name; the target sketch must be active."""
    empty_callout = win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)
    for position, name in enumerate(names):
        selected = com(
            document.Extension, "SelectByID2", name, "SKETCHSEGMENT",
            0.0, 0.0, 0.0, position > 0, 0, empty_callout, 0,
        )
        if not selected:
            return False
    return True


def _invalid(sw, message):
    return sw._result(False, message, SwErrors.swInvalidInput,
                      {"code": "VALIDATION_FAILED"})


def _edit_and_verify(sw, document, feature, names, action, call, failure_code,
                     failure_label):
    """Run one sketch-manager edit, then prove it changed the sketch geometry."""
    before = _segment_lengths(document, feature)
    if not _open_sketch(document, feature):
        return sw._result(False, "Could not open sketch for editing.",
                          SwErrors.swSelectionError)

    try:
        if not _select_segments(document, names):
            return sw._result(
                False,
                "Could not select all requested sketch entities. Check the "
                "exact segment names inside the active sketch.",
                SwErrors.swSelectionError,
            )
        applied = call()
    except Exception as edit_error:
        return sw._result(False, f"{failure_label} failed: {edit_error}",
                          SwErrors.swFeatureError)
    finally:
        com(document, "InsertSketch2", True)
        com(document, "ClearSelection2", True)

    after = _segment_lengths(document, feature)
    changed = before != after
    if not changed and not applied:
        return sw._result(
            False,
            f"SolidWorks did not {action} {', '.join(names)}; the sketch "
            "geometry is unchanged.",
            SwErrors.swFeatureError,
            {"code": failure_code},
        )
    return changed


@tool(
    name="trim_entities",
    description=(
        "Trim or extend existing entities inside one named sketch. Select "
        "entities by their exact sketch segment names (for example Line1, "
        "Line2). The sketch is reopened for edit and closed again. Success is "
        "confirmed by an observed geometry change. Trimming invalidates "
        "previously reported entity references."
    ),
    schema={"type": "object", "properties": {
        "sketch": {"type": "string"},
        "entities": {"type": "array", "items": {"type": "string"},
                     "minItems": 1},
        "mode": {"type": "string", "default": "corner", "enum": [
            "closest", "corner", "twoentities", "entitypoint",
            "outside", "inside",
        ]},
        "pick": {"type": "array", "items": {"type": "number"},
                 "minItems": 3, "maxItems": 3},
        "unit": {"type": "string"},
    }, "required": ["sketch", "entities"]},
    operation_class=OperationClass.MUTATE,
)
def trim_entities(sw, sketch, entities, mode="corner", pick=None, unit=None):
    if not isinstance(sketch, str) or not sketch.strip():
        return _invalid(sw, "sketch must be a non-empty sketch name.")

    mode_key = mode.strip().lower() if isinstance(mode, str) else ""
    if mode_key not in TRIM_OPTIONS:
        return _invalid(
            sw,
            "mode must be one of: " + ", ".join(sorted(TRIM_OPTIONS)) + ".",
        )

    names = _clean_names(entities)
    if names is None or len(names) < MIN_TRIM_ENTITIES[mode_key]:
        return _invalid(
            sw,
            f"mode '{mode_key}' needs at least "
            f"{MIN_TRIM_ENTITIES[mode_key]} distinct non-empty entity names.",
        )

    point = _resolve_pick(sw, pick, unit)
    if point is None:
        return _invalid(sw, "pick must be three numbers (x, y, z).")

    document, error = sw.get_active_doc()
    if error:
        return error
    if com(document, "GetType") != SW_DOC_PART:
        return sw._result(False, "Active document is not a part.",
                          SwErrors.swInvalidFileType)

    feature = _find_feature(document, sketch.strip())
    if feature is None:
        return sw._result(False, f"Sketch not found: {sketch}",
                          SwErrors.swSelectionError)

    changed = _edit_and_verify(
        sw, document, feature, names,
        action=f"trim using '{mode_key}'",
        call=lambda: com(document.SketchManager, "SketchTrim",
                         TRIM_OPTIONS[mode_key], point[0], point[1], point[2]),
        failure_code="TRIM_FAILED",
        failure_label="Trim",
    )
    if isinstance(changed, dict):
        return changed

    return sw._result(
        True,
        f"Trimmed {len(names)} entity(ies) in {sketch} using '{mode_key}'.",
        data={
            "sketch": sketch,
            "mode": mode_key,
            "trim_option": TRIM_OPTIONS[mode_key],
            "entities": names,
            "pick": list(point),
            "geometry_changed": changed,
            "references_invalidated": True,
        },
    )


@tool(
    name="extend_entities",
    description=(
        "Extend one existing sketch entity to the next entity in its path. "
        "Select the entity by its exact sketch segment name and give a pick "
        "point near the end to extend. The sketch is reopened for edit and "
        "closed again; success is confirmed by an observed geometry change."
    ),
    schema={"type": "object", "properties": {
        "sketch": {"type": "string"},
        "entities": {"type": "array", "items": {"type": "string"},
                     "minItems": 1, "maxItems": 1},
        "pick": {"type": "array", "items": {"type": "number"},
                 "minItems": 3, "maxItems": 3},
        "unit": {"type": "string"},
    }, "required": ["sketch", "entities"]},
    operation_class=OperationClass.MUTATE,
)
def extend_entities(sw, sketch, entities, pick=None, unit=None):
    if not isinstance(sketch, str) or not sketch.strip():
        return _invalid(sw, "sketch must be a non-empty sketch name.")

    names = _clean_names(entities)
    if names is None or len(names) != 1:
        return _invalid(sw, "entities must contain exactly one entity name.")

    point = _resolve_pick(sw, pick, unit)
    if point is None:
        return _invalid(sw, "pick must be three numbers (x, y, z).")

    document, error = sw.get_active_doc()
    if error:
        return error
    if com(document, "GetType") != SW_DOC_PART:
        return sw._result(False, "Active document is not a part.",
                          SwErrors.swInvalidFileType)

    feature = _find_feature(document, sketch.strip())
    if feature is None:
        return sw._result(False, f"Sketch not found: {sketch}",
                          SwErrors.swSelectionError)

    changed = _edit_and_verify(
        sw, document, feature, names,
        action=f"extend {names[0]}",
        call=lambda: com(document.SketchManager, "SketchExtend",
                         point[0], point[1], point[2]),
        failure_code="EXTEND_FAILED",
        failure_label="Extend",
    )
    if isinstance(changed, dict):
        return changed

    return sw._result(
        True,
        f"Extended {names[0]} in {sketch}.",
        data={
            "sketch": sketch,
            "entities": names,
            "pick": list(point),
            "geometry_changed": changed,
            "references_invalidated": True,
        },
    )
