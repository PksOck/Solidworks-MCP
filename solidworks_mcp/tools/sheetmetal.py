"""
Sheet metal tools (part D): read parameters, export flat pattern.
"""

import logging
import os

import pythoncom
import win32com.client

from ..comutil import com
from ..constants import SwErrors
from ..core.policy import OperationClass
from ..registry import tool
from .guard import require_output_write, require_stateful_document_access

logger = logging.getLogger("SolidWorksMCP")


def _find_sheet_metal_feature(doc):
    feat = com(doc, "FirstFeature")
    while feat is not None:
        if com(feat, "GetTypeName2") == "SheetMetal":
            return feat
        feat = com(feat, "GetNextFeature")
    return None


def _find_flat_pattern_feature(doc):
    feat = com(doc, "FirstFeature")
    while feat is not None:
        if com(feat, "GetTypeName2") == "FlatPattern":
            return feat
        feat = com(feat, "GetNextFeature")
    return None


@tool(
    name="get_sheet_metal_info",
    description=(
        "Read sheet metal parameters (thickness, K-factor, bend radius, "
        "relief settings) from the active part's Sheet-Metal feature. "
        "Read-only."
    ),
    schema={
        "type": "object",
        "properties": {},
        "required": []
    },
    operation_class=OperationClass.READ,
)
def get_sheet_metal_info(sw) -> dict:
    """Read sheet metal parameters from the active part."""
    doc, err = sw.get_active_doc()
    if err:
        return err

    feat = _find_sheet_metal_feature(doc)
    if feat is None:
        return sw._result(False, "Part has no sheet metal feature.",
                          SwErrors.swFeatureError)

    smdata = com(feat, "GetDefinition")

    return sw._result(
        True,
        "Read sheet metal parameters.",
        data={
            "thickness_mm": com(smdata, "Thickness") * 1000,
            "k_factor": com(smdata, "KFactor"),
            "bend_radius_mm": com(smdata, "BendRadius") * 1000,
            "bend_allowance_type": com(smdata, "BendAllowanceType"),
            "bend_allowance": com(smdata, "BendAllowance"),
            "use_auto_relief": com(smdata, "UseAutoRelief"),
            "auto_relief_type": com(smdata, "AutoReliefType"),
            "relief_ratio": com(smdata, "ReliefRatio"),
            "use_material_sheet_metal_parameters": com(smdata, "UseMaterialSheetMetalParameters"),
            "bend_table_file": com(smdata, "BendTableFile"),
        }
    )


@tool(
    name="flatten_sheet_metal",
    description=(
        "Suppress or unsuppress the active part's Flat-Pattern feature, "
        "toggling the body between flattened and folded state. Modifies "
        "the active part (not saved)."
    ),
    schema={
        "type": "object",
        "properties": {
            "flatten": {
                "type": "boolean",
                "description": "True to flatten (suppress Flat-Pattern feature state 1), "
                                "false to fold back (state 0)."
            }
        },
        "required": ["flatten"]
    },
    operation_class=OperationClass.MUTATE,
)
def flatten_sheet_metal(sw, flatten: bool) -> dict:
    """Toggle the Flat-Pattern feature between flattened and folded state."""
    doc, err = sw.get_active_doc()
    if err:
        return err
    denied = require_stateful_document_access(sw, doc)
    if denied:
        return denied

    feat = _find_flat_pattern_feature(doc)
    if feat is None:
        return sw._result(False, "Part has no Flat-Pattern feature.",
                          SwErrors.swFeatureError)

    state = 1 if flatten else 0
    try:
        ok = com(feat, "SetSuppression", state)
        com(doc, "EditRebuild3")
    except Exception as e:
        logger.error(f"SetSuppression failed: {e}")
        return sw._result(False, f"Could not set flat pattern state: {e}",
                          SwErrors.swFeatureError)

    if not ok:
        return sw._result(False, "SetSuppression returned false.",
                          SwErrors.swFeatureError)

    return sw._result(
        True,
        f"Flat pattern {'flattened' if flatten else 'folded back'}.",
        data={"flattened": flatten}
    )


@tool(
    name="get_flat_pattern_info",
    description=(
        "Flatten the active sheet metal part, read the flat pattern's "
        "bounding box and body/face counts, then fold it back. Net effect "
        "on the model is none (not saved), but the part is flattened and "
        "refolded during the call."
    ),
    schema={
        "type": "object",
        "properties": {},
        "required": []
    },
    operation_class=OperationClass.STATEFUL_READ,
)
def get_flat_pattern_info(sw) -> dict:
    """Read flat pattern bounding-box dimensions, restoring the folded state after."""
    doc, err = sw.get_active_doc()
    if err:
        return err
    denied = require_stateful_document_access(sw, doc)
    if denied:
        return denied

    feat = _find_flat_pattern_feature(doc)
    if feat is None:
        return sw._result(False, "Part has no Flat-Pattern feature.",
                          SwErrors.swFeatureError)

    # IsSuppressed()==True is the normal/folded state (SetSuppression(0));
    # SetSuppression(1) unsuppresses the feature, which is what flattens the
    # body (live-verified: 42 -> 14 faces on a real part). Counter-intuitive
    # naming, but matches swSuppressFeature=0 / swUnSuppressFeature=1.
    was_folded = com(feat, "IsSuppressed")

    try:
        if was_folded:
            com(feat, "SetSuppression", 1)
            com(doc, "EditRebuild3")

        bodies = com(doc, "GetBodies2", 0, True)
        if not bodies:
            return sw._result(False, "No solid body found after flattening.",
                              SwErrors.swFeatureError)
        body = bodies[0]
        box = com(body, "GetBodyBox")
        faces = com(body, "GetFaceCount")
    finally:
        if was_folded:
            com(feat, "SetSuppression", 0)
            com(doc, "EditRebuild3")

    xmin, ymin, zmin, xmax, ymax, zmax = box
    return sw._result(
        True,
        "Read flat pattern info (model restored to folded state).",
        data={
            "length_mm": (xmax - xmin) * 1000,
            "width_mm": (ymax - ymin) * 1000,
            "height_mm": (zmax - zmin) * 1000,
            "face_count": faces
        }
    )


@tool(
    name="export_flat_pattern",
    description=(
        "Export the flat pattern of the active sheet metal part to a "
        "DXF or DWG file for laser cutting. Does not modify the model "
        "(works regardless of Flat-Pattern feature suppression state)."
    ),
    schema={
        "type": "object",
        "properties": {
            "output_path": {
                "type": "string",
                "description": "Full destination path, extension .dxf or .dwg"
            }
        },
        "required": ["output_path"]
    },
    operation_class=OperationClass.EXPORT,
)
def export_flat_pattern(sw, output_path: str) -> dict:
    """Export the flat pattern of the active sheet metal part."""
    denied = require_output_write(sw, output_path)
    if denied:
        return denied
    doc, err = sw.get_active_doc()
    if err:
        return err

    if _find_sheet_metal_feature(doc) is None:
        return sw._result(False, "Part has no sheet metal feature.",
                          SwErrors.swFeatureError)

    ext = os.path.splitext(output_path)[1].lower()
    if ext not in (".dxf", ".dwg"):
        return sw._result(False, f"Unsupported output extension: {ext}",
                          SwErrors.swInvalidInput)

    # ExportToDWG2 needs the model path as its base-name argument. An unsaved
    # scratch part has an empty path, which makes the export fail with no
    # explanation (live-verified: it succeeds as soon as the part is saved).
    model_path = com(doc, "GetPathName")
    if not model_path:
        return sw._result(
            False,
            "SolidWorks needs a saved model path to export a flat pattern. "
            "Save the part first (save_document) and retry.",
            SwErrors.swFileSaveError,
            {"code": "UNSAVED_DOCUMENT"},
        )

    alignment = win32com.client.VARIANT(
        pythoncom.VT_ARRAY | pythoncom.VT_R8, [0.0] * 12)
    views = win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)

    try:
        ok = com(doc, "ExportToDWG2", output_path, model_path,
                 1, True, alignment, False, False, 0, views)
    except Exception as e:
        logger.error(f"ExportToDWG2 failed: {e}")
        return sw._result(False, f"Export failed: {e}", SwErrors.swExportError)

    if not ok:
        return sw._result(False, "Export failed.", SwErrors.swExportError)

    return sw._result(
        True,
        f"Exported flat pattern to {output_path}.",
        data={"path": output_path}
    )


def _positive(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


@tool(
    name="create_sheet_metal_base_flange",
    description=(
        "Create the first sheet-metal feature (base flange) from the last "
        "sketch of the active part, which becomes the Sheet-Metal feature. "
        "The sketch geometry is the flange outline and 'width_mm' is the "
        "flange width across the sketch. Modifies the active part."
    ),
    schema={
        "type": "object",
        "properties": {
            "thickness_mm": {"type": "number",
                             "description": "Sheet thickness in mm."},
            "bend_radius_mm": {"type": "number",
                               "description": "Default bend radius in mm. Defaults to the thickness."},
            "width_mm": {"type": "number", "default": 50.0,
                         "description": "Flange width in mm, split evenly on both sides of the sketch plane."}
        },
        "required": ["thickness_mm"]
    },
    operation_class=OperationClass.MUTATE,
)
def create_sheet_metal_base_flange(sw, thickness_mm: float,
                                   bend_radius_mm: float = None,
                                   width_mm: float = 50.0) -> dict:
    """Create a base flange from the last sketch using InsertSheetMetalBaseFlange."""
    if not _positive(thickness_mm):
        return sw._result(False, "thickness_mm must be a positive number.",
                          SwErrors.swInvalidInput, {"code": "VALIDATION_FAILED"})
    if bend_radius_mm is not None and (
            not isinstance(bend_radius_mm, (int, float))
            or isinstance(bend_radius_mm, bool) or bend_radius_mm < 0):
        return sw._result(False, "bend_radius_mm must be a non-negative number.",
                          SwErrors.swInvalidInput, {"code": "VALIDATION_FAILED"})
    if not _positive(width_mm):
        return sw._result(False, "width_mm must be a positive number.",
                          SwErrors.swInvalidInput, {"code": "VALIDATION_FAILED"})

    doc, err = sw.get_active_doc()
    if err:
        return err
    if _find_sheet_metal_feature(doc) is not None:
        return sw._result(
            False, "The active part already has a sheet-metal feature.",
            SwErrors.swFeatureError, {"code": "ALREADY_SHEET_METAL"},
        )

    selected, sketch_name, message = sw._close_and_select_sketch(doc)
    if not selected:
        return sw._result(False, f"Could not select a sketch: {message}",
                          SwErrors.swSketchError)

    radius_mm = thickness_mm if bend_radius_mm is None else bend_radius_mm
    half_width_m = width_mm / 2000.0
    empty_callout = win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)

    # InsertSheetMetalBaseFlange2 returns None in SW 2025 rev 33.1.1 even when
    # its arguments are the v2 equivalents; the 16-argument
    # InsertSheetMetalBaseFlange creates the Sheet-Metal feature reliably
    # (live-verified).
    try:
        feature = com(
            com(doc, "FeatureManager"), "InsertSheetMetalBaseFlange",
            thickness_mm / 1000.0,   # Thickness (m)
            False,                    # ThickenDir
            radius_mm / 1000.0,       # Radius (m)
            half_width_m,             # ExtrudeDist1 (m)
            half_width_m,             # ExtrudeDist2 (m)
            False,                    # FlipExtruDir
            0,                        # EndCondition1 (blind)
            0,                        # EndCondition2 (blind)
            0,                        # DirToUse
            empty_callout,            # PCBA
            False,                    # UseDefaultRelief
            0,                        # ReliefType
            0.0, 0.0, 0.0,            # ReliefWidth, ReliefDepth, ReliefRatio
            False,                    # UseReliefRatio
        )
    except Exception as create_error:
        logger.error(f"InsertSheetMetalBaseFlange failed: {create_error}")
        return sw._result(False, f"Could not create the base flange: {create_error}",
                          SwErrors.swFeatureError)

    sheet_metal = _find_sheet_metal_feature(doc)
    if sheet_metal is None:
        # The API returns a feature even when nothing usable was built, so
        # success is only reported when the Sheet-Metal feature is observed.
        return sw._result(
            False,
            "No sheet-metal feature appeared after the base flange call.",
            SwErrors.swFeatureError, {"code": "FEATURE_CREATE_FAILED"},
        )

    return sw._result(
        True,
        f"Created base flange '{com(feature, 'Name')}' from sketch '{sketch_name}'.",
        data={
            "feature": com(feature, "Name") if feature is not None else None,
            "sheet_metal_feature": com(sheet_metal, "Name"),
            "sketch": sketch_name,
            "thickness_mm": thickness_mm,
            "bend_radius_mm": radius_mm,
            "width_mm": width_mm,
        },
    )
