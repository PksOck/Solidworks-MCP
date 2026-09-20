"""
Sheet metal tools (part D): read parameters, export flat pattern.
"""

import logging
import os

import pythoncom
import win32com.client

from ..comutil import com
from ..constants import SwErrors
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

    alignment = win32com.client.VARIANT(
        pythoncom.VT_ARRAY | pythoncom.VT_R8, [0.0] * 12)
    views = win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)

    try:
        ok = com(doc, "ExportToDWG2", output_path, com(doc, "GetPathName"),
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
