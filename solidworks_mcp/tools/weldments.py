"""
Weldment tools (part C): list library profiles, create structural members.
"""

import logging
import os

import pythoncom
import win32com.client

from ..comutil import com
from ..constants import SwErrors
from ..registry import tool

logger = logging.getLogger("SolidWorksMCP")

SW_FILE_LOCATIONS_WELDMENT_PROFILES = 29


@tool(
    name="list_weldment_profiles",
    description=(
        "List available weldment profile (.sldlfp) files under the "
        "SolidWorks weldment profiles library, grouped by folder. "
        "Use the returned path with create_structural_member. Read-only."
    ),
    schema={
        "type": "object",
        "properties": {
            "filter": {
                "type": "string",
                "description": "Case-insensitive substring to filter by filename. Optional."
            }
        },
        "required": []
    },
)
def list_weldment_profiles(sw, filter: str = "") -> dict:
    """List .sldlfp profile files under the configured weldment profiles library."""
    doc, err = sw.get_active_doc()
    if err:
        return err

    root = com(sw.app, "GetUserPreferenceStringValue",
               SW_FILE_LOCATIONS_WELDMENT_PROFILES)
    if not root or not os.path.isdir(root):
        return sw._result(False, f"Weldment profiles folder not found: {root}",
                          SwErrors.swFileNotFoundError)

    filter_lower = filter.lower()
    profiles = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if not name.lower().endswith(".sldlfp"):
                continue
            if name.startswith("~$"):
                continue
            if filter_lower and filter_lower not in name.lower():
                continue
            full_path = os.path.join(dirpath, name)
            profiles.append({
                "name": name,
                "folder": os.path.relpath(dirpath, root),
                "path": full_path
            })

    profiles.sort(key=lambda p: (p["folder"], p["name"]))

    return sw._result(
        True,
        f"Found {len(profiles)} weldment profiles under {root}.",
        data={"root": root, "profiles": profiles}
    )


def _find_feature(doc, name: str):
    feat = com(doc, "FirstFeature")
    while feat is not None:
        if com(feat, "Name") == name:
            return feat
        feat = com(feat, "GetNextFeature")
    return None


def _has_weldment_feature(doc) -> bool:
    feat = com(doc, "FirstFeature")
    while feat is not None:
        if com(feat, "GetTypeName2") == "WeldmentFeature":
            return True
        feat = com(feat, "GetNextFeature")
    return False


@tool(
    name="create_structural_member",
    description=(
        "Create a weldment structural member (WeldMemberFeat) from all "
        "connected sketch segments in a named sketch, using a library "
        "profile. Creates the Weldment folder feature if it doesn't "
        "exist yet. Modifies the active part."
    ),
    schema={
        "type": "object",
        "properties": {
            "sketch_name": {
                "type": "string",
                "description": "Name of the sketch containing the path segments (e.g. 'Sketch1')"
            },
            "profile_path": {
                "type": "string",
                "description": "Full path to a .sldlfp profile file, from list_weldment_profiles"
            },
            "connected_segments_option": {
                "type": "integer",
                "description": "0=None, 1=Apply, 2=Apply for all. Default 1.",
                "default": 1
            },
            "allow_protrusion": {
                "type": "boolean",
                "description": "Allow profile to protrude past sketch endpoints. Default true.",
                "default": True
            }
        },
        "required": ["sketch_name", "profile_path"]
    },
)
def create_structural_member(sw, sketch_name: str, profile_path: str,
                              connected_segments_option: int = 1,
                              allow_protrusion: bool = True) -> dict:
    """Create a structural member from a sketch and a library profile."""
    doc, err = sw.get_active_doc()
    if err:
        return err

    if not os.path.isfile(profile_path):
        return sw._result(False, f"Profile file not found: {profile_path}",
                          SwErrors.swFileNotFoundError)

    feat = _find_feature(doc, sketch_name)
    if feat is None:
        return sw._result(False, f"Sketch not found: {sketch_name}",
                          SwErrors.swSketchError)
    if com(feat, "GetTypeName2") != "ProfileFeature":
        return sw._result(False, f"Feature '{sketch_name}' is not a sketch.",
                          SwErrors.swSketchError)

    try:
        sk = com(feat, "GetSpecificFeature2")
        segs = com(sk, "GetSketchSegments")
    except Exception as e:
        logger.error(f"GetSketchSegments failed: {e}")
        return sw._result(False, f"Could not read sketch segments: {e}",
                          SwErrors.swSketchError)

    if not segs:
        return sw._result(False, f"Sketch '{sketch_name}' has no segments.",
                          SwErrors.swSketchError)

    fm = com(doc, "FeatureManager")

    try:
        if not _has_weldment_feature(doc):
            com(fm, "InsertWeldmentFeature")

        grp = com(fm, "CreateStructuralMemberGroup")
        seg_var = win32com.client.VARIANT(
            pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, list(segs))
        grp.Segments = seg_var

        groups_var = win32com.client.VARIANT(
            pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, [grp])

        new_feat = com(fm, "InsertStructuralWeldment5", profile_path,
                       connected_segments_option, allow_protrusion,
                       groups_var, "")
    except Exception as e:
        logger.error(f"InsertStructuralWeldment5 failed: {e}")
        return sw._result(False, f"Could not create structural member: {e}",
                          SwErrors.swFeatureError)

    if not new_feat:
        return sw._result(False, "InsertStructuralWeldment5 returned no feature.",
                          SwErrors.swFeatureError)

    return sw._result(
        True,
        f"Created structural member from sketch '{sketch_name}'.",
        data={"feature": com(new_feat, "Name")}
    )
