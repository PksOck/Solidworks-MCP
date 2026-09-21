"""
Assembly tools (part E): insert components, mate them, and pack and go.
"""

import logging
import os

import pythoncom
import win32com.client

from ..comutil import com
from ..constants import SwDocumentTypes, SwErrors, SwMateTypes
from ..core.policy import OperationClass
from ..registry import tool
from .guard import require_output_write

logger = logging.getLogger("SolidWorksMCP")

SW_ADD_COMPONENT_DEFAULT_CONFIG = 0


def _require_assembly(sw):
    """Returns (doc, error_dict). error_dict is None if doc is an open assembly."""
    doc, err = sw.get_active_doc()
    if err:
        return None, err
    if com(doc, "GetType") != SwDocumentTypes.swDocASSEMBLY:
        return None, sw._result(False, "Active document is not an assembly.",
                                SwErrors.swInvalidFileType)
    return doc, None


def _find_component(asm, name):
    """
    Finds a component by Name2 (e.g. "Block1-1") or by its full recursive
    path (e.g. "Sub-1/Part-2"), searched over ALL components, not just
    top-level (api-findings.md §6.2 -- recursive names are "/"-separated
    paths).
    """
    for comp in com(asm, "GetComponents", False) or []:
        comp_name = com(comp, "Name2")
        if comp_name == name or comp_name.endswith("/" + name):
            return comp
    return None


def _local_to_global(local_pt, tfdata):
    """
    Component-local point -> assembly-global point, via the component's
    Transform.ArrayData (16 floats: R00..R22, Tx,Ty,Tz, scale, 0,0,0).

    api-findings.md §6.5: IMathUtility.CreatePoint + MultiplyTransform is
    BROKEN (always returns the translation alone, ignores the input
    point) -- do not use it. This manual matrix multiply is the verified
    replacement.
    """
    lx, ly, lz = local_pt
    r = tfdata
    scale = r[12]
    gx = (lx * r[0] + ly * r[3] + lz * r[6]) * scale + r[9]
    gy = (lx * r[1] + ly * r[4] + lz * r[7]) * scale + r[10]
    gz = (lx * r[2] + ly * r[5] + lz * r[8]) * scale + r[11]
    return gx, gy, gz


def _component_faces(component):
    """
    Enumerates a component's faces in a stable order (planar and
    cylindrical only -- the two types mate_* tools support). Returns a
    list of (face, kind) where kind is "planar" or "cylindrical". Index
    into this list is the face_index used by list_component_faces and
    the mate_* tools.
    """
    body = com(component, "GetBody")
    if body is None:
        return []
    result = []
    for face in com(body, "GetFaces") or []:
        surface = com(face, "GetSurface")
        if com(surface, "IsPlane"):
            result.append((face, "planar"))
        elif com(surface, "IsCylinder"):
            result.append((face, "cylindrical"))
    return result


def _face_local_point(face, kind):
    """
    A point on the face, in the component's local part-space, chosen to
    lie safely in the face's interior -- not on an edge/corner/boundary.

    api-findings.md §6.5: PlaneParams' and CylinderParams' own point can
    land exactly on a face boundary (a rectangular face's corner, or a
    cylinder's axis endpoint at the end-cap), causing SelectByID2 to fail
    or pick the wrong adjacent face.

    - planar: centroid of the face's own local bounding box.
    - cylindrical: a point offset inward along the axis from its origin,
      plus the radius outward, so it sits mid-height on the cylindrical
      wall rather than on the end-cap seam.
    """
    surface = com(face, "GetSurface")
    if kind == "planar":
        fbox = list(com(face, "GetBox", True))
        return [(fbox[0] + fbox[3]) / 2, (fbox[1] + fbox[4]) / 2,
                (fbox[2] + fbox[5]) / 2]
    else:
        ax, ay, az, dx, dy, dz, radius = com(surface, "CylinderParams")[:7]
        # perpendicular-to-axis direction for the radial offset
        px, py, pz = (1.0, 0.0, 0.0) if abs(dx) < 0.9 else (0.0, 1.0, 0.0)
        # project out the axis component, normalize
        dot = px * dx + py * dy + pz * dz
        px, py, pz = px - dot * dx, py - dot * dy, pz - dot * dz
        n = (px ** 2 + py ** 2 + pz ** 2) ** 0.5
        px, py, pz = px / n, py / n, pz / n
        return [ax + dx * 0.005 + radius * px,
                ay + dy * 0.005 + radius * py,
                az + dz * 0.005 + radius * pz]


def _select_component_face(asm, component, face_index, append, mark):
    """Selects a component's face by index (see _component_faces) for a
    mate. Returns True/False from SelectByID2."""
    faces = _component_faces(component)
    if face_index < 0 or face_index >= len(faces):
        return False
    face, kind = faces[face_index]
    local_pt = _face_local_point(face, kind)
    tfdata = list(com(com(component, "Transform"), "ArrayData"))
    gx, gy, gz = _local_to_global(local_pt, tfdata)
    ext = com(asm, "Extension")
    return com(ext, "SelectByID2", "", "FACE", gx, gy, gz, append, mark,
               win32com.client.VARIANT(pythoncom.VT_DISPATCH, None), 0)


@tool(
    name="insert_component",
    description=(
        "Insert a Part or sub-assembly into the active assembly at a "
        "given position. Position is in meters, assembly space."
    ),
    schema={
        "type": "object",
        "properties": {
            "filepath": {"type": "string", "description": "Full path to the .SLDPRT/.SLDASM to insert"},
            "x": {"type": "number", "description": "X position in meters. Default 0."},
            "y": {"type": "number", "description": "Y position in meters. Default 0."},
            "z": {"type": "number", "description": "Z position in meters. Default 0."},
        },
        "required": ["filepath"]
    },
    operation_class=OperationClass.MUTATE,
)
def insert_component(sw, filepath: str, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> dict:
    """Insert a component into the active assembly"""
    asm, err = _require_assembly(sw)
    if err:
        return err

    if not os.path.exists(filepath):
        return sw._result(False, f"File not found: {filepath}",
                          SwErrors.swFileNotFoundError)

    try:
        comp = com(asm, "AddComponent5", filepath, SW_ADD_COMPONENT_DEFAULT_CONFIG,
                   "", False, "", x, y, z)
    except Exception as e:
        logger.error(f"AddComponent5 failed: {e}")
        return sw._result(False, f"Could not insert component: {e}",
                          SwErrors.swUnknownError)

    if comp is None:
        return sw._result(False, f"Could not insert {filepath}.",
                          SwErrors.swFeatureError)

    return sw._result(
        True,
        f"Inserted {com(comp, 'Name2')}.",
        data={"name": com(comp, "Name2"), "path": filepath}
    )


@tool(
    name="list_components",
    description="List the components of the active assembly: name, path, fixed/floating state.",
    schema={"type": "object", "properties": {}, "required": []},
    operation_class=OperationClass.READ,
)
def list_components(sw) -> dict:
    """List all component instances of the active assembly recursively."""
    asm, err = _require_assembly(sw)
    if err:
        return err

    comps = []
    unresolved = []

    def optional_component_value(comp, member, instance_path):
        try:
            return com(comp, member)
        except Exception as error:
            unresolved.append(f"{instance_path}: {member} unavailable ({error})")
            return None

    def transform_data(comp, instance_path):
        transform = optional_component_value(comp, "Transform2", instance_path)
        if transform is None:
            return None
        try:
            values = com(transform, "ArrayData")
            return list(values) if values is not None else None
        except Exception as error:
            unresolved.append(f"{instance_path}: Transform2.ArrayData unavailable ({error})")
            return None

    def visit(comp, parent_path=None):
        name = com(comp, "Name2")
        instance_path = f"{parent_path}/{name}" if parent_path else name
        # swComponentSuppressionState_e: swComponentSuppressed = 0 (TLB-verified)
        comps.append({
            "name": name,
            "instance_path": instance_path,
            "parent_path": parent_path,
            "path": com(comp, "GetPathName"),
            "configuration": optional_component_value(
                comp, "ReferencedConfiguration", instance_path),
            "transform": transform_data(comp, instance_path),
            "is_fixed": bool(com(comp, "IsFixed")),
            "suppressed": com(comp, "GetSuppression") == 0,
        })
        try:
            children = com(comp, "GetChildren") or []
        except Exception as error:
            unresolved.append(f"{instance_path}: children unavailable ({error})")
            return
        for child in children:
            visit(child, instance_path)

    for component in com(asm, "GetComponents", True) or []:
        visit(component)

    return sw._result(
        True, f"Found {len(comps)} component instances.",
        data={
            "components": comps,
            "coverage": {
                "complete": not unresolved,
                "visited_count": len(comps),
                "unresolved": unresolved,
                "truncated": False,
                "next_cursor": None,
            },
        })


@tool(
    name="list_component_faces",
    description=(
        "List the planar and cylindrical faces of one component in the "
        "active assembly, with index, type and size. Use the index with "
        "mate_coincident/mate_concentric/mate_distance's face_index1/"
        "face_index2. Indexes are only valid for the current model state "
        "-- re-run after any mate is added, since components move."
    ),
    schema={
        "type": "object",
        "properties": {
            "component_name": {"type": "string", "description": "Name2 of the component, e.g. \"Block1-1\""},
        },
        "required": ["component_name"]
    },
    operation_class=OperationClass.READ,
)
def list_component_faces(sw, component_name: str) -> dict:
    """List planar/cylindrical faces of one assembly component"""
    asm, err = _require_assembly(sw)
    if err:
        return err

    comp = _find_component(asm, component_name)
    if comp is None:
        return sw._result(False, f"Component not found: {component_name}",
                          SwErrors.swInvalidInput)

    faces = []
    for index, (face, kind) in enumerate(_component_faces(comp)):
        surface = com(face, "GetSurface")
        entry = {"index": index, "kind": kind}
        if kind == "planar":
            entry["area_mm2"] = round(com(face, "GetArea") * 1_000_000, 2)
        else:
            radius = com(surface, "CylinderParams")[6]
            entry["radius_mm"] = round(radius * 1000, 3)
        faces.append(entry)

    return sw._result(True, f"Found {len(faces)} faces on {component_name}.",
                      data={"faces": faces})


def _add_mate(sw, asm, component1, face_index1, component2, face_index2,
              mate_type, distance_m=0.0, flip=False):
    comp1 = _find_component(asm, component1)
    if comp1 is None:
        return sw._result(False, f"Component not found: {component1}",
                          SwErrors.swInvalidInput)
    comp2 = _find_component(asm, component2)
    if comp2 is None:
        return sw._result(False, f"Component not found: {component2}",
                          SwErrors.swInvalidInput)

    com(asm, "ClearSelection2", True)
    ok1 = _select_component_face(asm, comp1, face_index1, False, 1)
    if not ok1:
        return sw._result(
            False, f"Could not select face {face_index1} on {component1}.",
            SwErrors.swSelectionError)
    ok2 = _select_component_face(asm, comp2, face_index2, True, 1)
    if not ok2:
        return sw._result(
            False, f"Could not select face {face_index2} on {component2}.",
            SwErrors.swSelectionError)

    err = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    try:
        mate = com(asm, "AddMate5", int(mate_type), 0, flip, distance_m, distance_m,
                   distance_m, 0.0, 0.0, 0.0, 0.0, 0.0, False, False, 0, err)
    except Exception as e:
        logger.error(f"AddMate5 failed: {e}")
        return sw._result(False, f"Could not create mate: {e}",
                          SwErrors.swUnknownError)
    finally:
        com(asm, "ClearSelection2", True)

    if mate is None:
        return sw._result(
            False,
            "Mate could not be created (selection may not be valid for "
            "this mate type).",
            SwErrors.swFeatureError)

    return sw._result(True, f"Mate created between {component1} and {component2}.",
                      data={"mate_type": com(mate, "GetTypeName2")})


@tool(
    name="mate_coincident",
    description=(
        "Add a Coincident mate between a face of two components in the "
        "active assembly, selected by list_component_faces indexes."
    ),
    schema={
        "type": "object",
        "properties": {
            "component1": {"type": "string", "description": "Name2 of the first component"},
            "face_index1": {"type": "integer", "description": "Face index from list_component_faces(component1)"},
            "component2": {"type": "string", "description": "Name2 of the second component"},
            "face_index2": {"type": "integer", "description": "Face index from list_component_faces(component2)"},
            "flip": {"type": "boolean", "description": "Flip mate alignment. Default false."},
        },
        "required": ["component1", "face_index1", "component2", "face_index2"]
    },
    operation_class=OperationClass.MUTATE,
)
def mate_coincident(sw, component1: str, face_index1: int, component2: str,
                     face_index2: int, flip: bool = False) -> dict:
    """Add a Coincident mate between two component faces"""
    asm, err = _require_assembly(sw)
    if err:
        return err
    return _add_mate(sw, asm, component1, face_index1, component2, face_index2,
                     SwMateTypes.swMateCOINCIDENT, flip=flip)


@tool(
    name="mate_concentric",
    description=(
        "Add a Concentric mate between a cylindrical face of two "
        "components in the active assembly, selected by "
        "list_component_faces indexes."
    ),
    schema={
        "type": "object",
        "properties": {
            "component1": {"type": "string", "description": "Name2 of the first component"},
            "face_index1": {"type": "integer", "description": "Cylindrical face index from list_component_faces(component1)"},
            "component2": {"type": "string", "description": "Name2 of the second component"},
            "face_index2": {"type": "integer", "description": "Cylindrical face index from list_component_faces(component2)"},
            "flip": {"type": "boolean", "description": "Flip mate alignment. Default false."},
        },
        "required": ["component1", "face_index1", "component2", "face_index2"]
    },
    operation_class=OperationClass.MUTATE,
)
def mate_concentric(sw, component1: str, face_index1: int, component2: str,
                     face_index2: int, flip: bool = False) -> dict:
    """Add a Concentric mate between two component cylindrical faces"""
    asm, err = _require_assembly(sw)
    if err:
        return err
    return _add_mate(sw, asm, component1, face_index1, component2, face_index2,
                     SwMateTypes.swMateCONCENTRIC, flip=flip)


@tool(
    name="mate_distance",
    description=(
        "Add a Distance mate between a face of two components in the "
        "active assembly, selected by list_component_faces indexes."
    ),
    schema={
        "type": "object",
        "properties": {
            "component1": {"type": "string", "description": "Name2 of the first component"},
            "face_index1": {"type": "integer", "description": "Face index from list_component_faces(component1)"},
            "component2": {"type": "string", "description": "Name2 of the second component"},
            "face_index2": {"type": "integer", "description": "Face index from list_component_faces(component2)"},
            "distance_mm": {"type": "number", "description": "Distance in mm"},
            "flip": {"type": "boolean", "description": "Flip mate direction. Default false."},
        },
        "required": ["component1", "face_index1", "component2", "face_index2", "distance_mm"]
    },
    operation_class=OperationClass.MUTATE,
)
def mate_distance(sw, component1: str, face_index1: int, component2: str,
                   face_index2: int, distance_mm: float, flip: bool = False) -> dict:
    """Add a Distance mate between two component faces"""
    asm, err = _require_assembly(sw)
    if err:
        return err
    return _add_mate(sw, asm, component1, face_index1, component2, face_index2,
                     SwMateTypes.swMateDISTANCE, distance_m=distance_mm / 1000.0,
                     flip=flip)


@tool(
    name="list_mates",
    description="List the mates already present in the active assembly's Mates feature group.",
    schema={"type": "object", "properties": {}, "required": []},
    operation_class=OperationClass.READ,
)
def list_mates(sw) -> dict:
    """List mates in the active assembly"""
    asm, err = _require_assembly(sw)
    if err:
        return err

    mate_group = None
    feat = com(asm, "FirstFeature")
    while feat is not None:
        if com(feat, "GetTypeName2") == "MateGroup":
            mate_group = feat
            break
        feat = com(feat, "GetNextFeature")

    mates = []
    if mate_group is not None:
        sub = com(mate_group, "GetFirstSubFeature")
        while sub is not None:
            mates.append({"name": com(sub, "Name"), "type": com(sub, "GetTypeName2")})
            sub = com(sub, "GetNextSubFeature")

    return sw._result(True, f"Found {len(mates)} mates.", data={"mates": mates})


@tool(
    name="pack_and_go",
    description=(
        "Save the active assembly and all referenced documents (parts, "
        "sub-assemblies, drawings) into a destination folder, using "
        "SolidWorks Pack and Go. Reports any referenced documents that "
        "live outside the assembly's own project folder, since those "
        "would silently break with a plain folder copy (O15)."
    ),
    schema={
        "type": "object",
        "properties": {
            "destination_folder": {"type": "string", "description": "Folder to save the packed assembly into"},
            "include_drawings": {"type": "boolean", "description": "Include referenced drawings. Default true."},
        },
        "required": ["destination_folder"]
    },
    operation_class=OperationClass.EXPORT,
)
def pack_and_go(sw, destination_folder: str, include_drawings: bool = True) -> dict:
    """Pack and Go the active assembly to a destination folder"""
    denied = require_output_write(sw, destination_folder)
    if denied:
        return denied
    asm, err = _require_assembly(sw)
    if err:
        return err

    project_folder = os.path.dirname(com(asm, "GetPathName") or "")

    try:
        ext = com(asm, "Extension")
        # GetPackAndGo's live signature (SW2025) needs one ByRef IDispatch*
        # out-argument -- calling with 0 args raises "Parameter not
        # optional" (api-findings.md §6.3). pywin32 cannot marshal a
        # BYREF VT_DISPATCH out-param back to Python (known client-side
        # limitation, not an API misuse), so pgo is always None here.
        placeholder = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_DISPATCH, None)
        ext.GetPackAndGo(placeholder)
        pgo = placeholder.value
        if pgo is None:
            return sw._result(
                False,
                "GetPackAndGo could not be retrieved (pywin32 cannot "
                "marshal this COM out-parameter back to Python; see "
                "api-findings.md §6.3). Pack and Go is not usable "
                "from this tool without a different COM binding (e.g. "
                "comtypes).",
                SwErrors.swUnknownError)

        try:
            pgo.IncludeDrawings = include_drawings
        except Exception:
            pass

        names = list(com(pgo, "GetDocumentNames"))
        outside = [n for n in names
                   if os.path.normcase(os.path.dirname(n)) != os.path.normcase(project_folder)]

        os.makedirs(destination_folder, exist_ok=True)
        save_names = win32com.client.VARIANT(
            pythoncom.VT_ARRAY | pythoncom.VT_BSTR,
            [os.path.join(destination_folder, os.path.basename(n)) for n in names])
        com(pgo, "SetDocumentSaveToNames", save_names)
        com(pgo, "SetSaveToName", True, destination_folder)

        ok = com(ext, "SavePackAndGo", pgo)
    except Exception as e:
        logger.error(f"Pack and Go failed: {e}")
        return sw._result(False, f"Pack and Go failed: {e}", SwErrors.swUnknownError)

    if not ok:
        return sw._result(False, "Pack and Go reported failure.", SwErrors.swFileSaveError)

    return sw._result(
        True,
        f"Packed {len(names)} documents to {destination_folder}."
        + (f" {len(outside)} came from outside the project folder."
           if outside else ""),
        data={"documents": list(names), "outside_project_folder": outside}
    )
