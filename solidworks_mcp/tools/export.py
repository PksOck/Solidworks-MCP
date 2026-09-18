"""
Export tools (part G): planar face and flat pattern export to DXF.
"""

import logging

from ..comutil import com
from ..constants import SwErrors
from ..registry import tool

logger = logging.getLogger("SolidWorksMCP")

SW_DOC_PART = 1
SW_SOLID_BODY = 0


@tool(
    name="list_planar_faces",
    description=(
        "List the planar faces of the open part, with index, area and normal. "
        "Use the index to pick a face for DXF export. Read-only."
    ),
    schema={
        "type": "object",
        "properties": {
            "min_area_mm2": {
                "type": "number",
                "description": "Skip faces smaller than this. Default 0."
            }
        },
        "required": []
    },
)
def list_planar_faces(sw, min_area_mm2: float = 0.0) -> dict:
    """List planar faces of the active part"""
    doc, err = sw.get_active_doc()
    if err:
        return err

    if com(doc, "GetType") != SW_DOC_PART:
        return sw._result(False, "Active document is not a part.",
                          SwErrors.swInvalidFileType)

    try:
        bodies = com(doc, "GetBodies2", SW_SOLID_BODY, True)
    except Exception as e:
        logger.error(f"GetBodies2 failed: {e}")
        return sw._result(False, f"Could not read bodies: {e}",
                          SwErrors.swUnknownError)

    if not bodies:
        return sw._result(False, "Part has no solid bodies.",
                          SwErrors.swExportError)

    faces = []
    index = 0
    for body_index, body in enumerate(bodies):
        body_name = com(body, "Name")
        for face in com(body, "GetFaces") or []:
            surface = com(face, "GetSurface")
            is_plane = com(surface, "IsPlane")
            area_mm2 = com(face, "GetArea") * 1_000_000
            if is_plane and area_mm2 >= min_area_mm2:
                nx, ny, nz, px, py, pz = com(surface, "PlaneParams")[:6]
                faces.append({
                    "index": index,
                    "body": body_name,
                    "body_index": body_index,
                    "area_mm2": round(area_mm2, 2),
                    "normal": [round(nx, 6), round(ny, 6), round(nz, 6)],
                    "point_mm": [round(px * 1000, 3), round(py * 1000, 3),
                                 round(pz * 1000, 3)]
                })
            index += 1

    faces.sort(key=lambda f: f["area_mm2"], reverse=True)

    return sw._result(
        True,
        f"Found {len(faces)} planar faces in {len(bodies)} bodies.",
        data={"bodies": len(bodies), "faces": faces}
    )
