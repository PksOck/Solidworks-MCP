"""Read-only structural inspection tools."""

from ..comutil import com
from ..constants import SwErrors, SwPlanes
from ..registry import tool


@tool(
    name="list_planes",
    description="List standard and reference planes in the active document without changing selection.",
    schema={"type": "object", "properties": {}, "required": []},
)
def list_planes(sw) -> dict:
    """Return usable standard plane names and explicit RefPlane features."""
    doc, err = sw.get_active_doc()
    if err:
        return err

    planes = [
        {"name": SwPlanes.FRONT, "kind": "standard"},
        {"name": SwPlanes.TOP, "kind": "standard"},
        {"name": SwPlanes.RIGHT, "kind": "standard"},
    ]
    try:
        feature = com(doc, "FirstFeature")
        while feature is not None:
            if com(feature, "GetTypeName2") == "RefPlane":
                planes.append({"name": com(feature, "Name"), "kind": "reference"})
            feature = com(feature, "GetNextFeature")
    except Exception as error:
        return sw._result(False, f"Could not inspect reference planes: {error}",
                          SwErrors.swUnknownError)

    return sw._result(True, f"{len(planes)} planes found.", data={"planes": planes})
