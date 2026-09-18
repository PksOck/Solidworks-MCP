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

logger = logging.getLogger("SolidWorksMCP")


def _find_sheet_metal_feature(doc):
    feat = com(doc, "FirstFeature")
    while feat is not None:
        if com(feat, "GetTypeName2") == "SheetMetal":
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
