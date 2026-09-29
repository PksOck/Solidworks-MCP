"""
Assembly tools (part E): insert components, mate them, and pack and go.
"""

import logging
import math
import os

import pythoncom
import win32com.client

from ..comutil import com, set_com
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


def _component_bodies(component):
    """
    All solid bodies of a component, in a stable order.

    api-findings.md 21.5: IComponent2.GetBody returns only the FIRST body, so
    a multi-body part (e.g. a bearing modelled as two separate rings) exposed
    none of the faces on its other bodies and every mate against it failed.
    GetBodies2 is preferred, with GetBody as a fallback for mocks/older builds.
    """
    try:
        bodies = com(component, "GetBodies2", 0, True) or []
    except Exception:
        bodies = []
    if not bodies:
        body = com(component, "GetBody")
        bodies = [body] if body is not None else []
    return bodies


def _component_faces(component):
    """
    Enumerates a component's faces in a stable order (planar and
    cylindrical only -- the two types mate_* tools support). Returns a
    list of (face, kind) where kind is "planar" or "cylindrical". Index
    into this list is the face_index used by list_component_faces and
    the mate_* tools.
    """
    result = []
    for body in _component_bodies(component):
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
    - cylindrical: the axis is advanced to the axial middle of the face's
      own bounding box (not a fixed 5 mm from the axis origin, which can
      fall past the end cap and off the face), then stepped out radially,
      so it sits mid-height on the cylindrical wall.
    """
    surface = com(face, "GetSurface")
    if kind == "planar":
        fbox = list(com(face, "GetBox", True))
        return [(fbox[0] + fbox[3]) / 2, (fbox[1] + fbox[4]) / 2,
                (fbox[2] + fbox[5]) / 2]
    else:
        ax, ay, az, dx, dy, dz, radius = com(surface, "CylinderParams")[:7]
        fbox = list(com(face, "GetBox", True))
        cx = (fbox[0] + fbox[3]) / 2
        cy = (fbox[1] + fbox[4]) / 2
        cz = (fbox[2] + fbox[5]) / 2
        # axial coordinate of the face's own box centre, applied to the axis
        t = (cx - ax) * dx + (cy - ay) * dy + (cz - az) * dz
        bx, by, bz = ax + dx * t, ay + dy * t, az + dz * t
        # perpendicular-to-axis direction for the radial offset
        px, py, pz = (1.0, 0.0, 0.0) if abs(dx) < 0.9 else (0.0, 1.0, 0.0)
        # project out the axis component, normalize
        dot = px * dx + py * dy + pz * dz
        px, py, pz = px - dot * dx, py - dot * dy, pz - dot * dz
        n = (px ** 2 + py ** 2 + pz ** 2) ** 0.5
        px, py, pz = px / n, py / n, pz / n
        return [bx + radius * px, by + radius * py, bz + radius * pz]


def _select_component_face(asm, component, face_index, append, mark):
    """Selects a component's face by index (see _component_faces) for a
    mate. Returns True/False from SelectByID2.

    api-findings.md 21.3: a retry loop with nudged points was tried and made
    things worse -- a nudge can land on a neighbouring face, SelectByID2
    returns True for the wrong entity, and AddMate5 then fails. Do not add
    one; keep the single, geometrically-derived point.
    """
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


def _open_part_box(sw, filepath):
    """
    Union bounding box (metres) of an already-open part document, or None.

    api-findings.md 21.2: AddComponent5 places the component's BOUNDING-BOX
    CENTRE at the given point, so placing by the part's own origin needs the
    box centre subtracted first.
    """
    app = getattr(sw, "app", None)
    if app is None:
        return None
    try:
        doc = com(app, "GetOpenDocumentByName", filepath)
    except Exception:
        return None
    if doc is None:
        return None
    boxes = []
    try:
        for body in com(doc, "GetBodies2", 0, True) or []:
            box = com(body, "GetBodyBox")
            if box:
                boxes.append(list(box))
    except Exception:
        return None
    if not boxes:
        return None
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            min(b[2] for b in boxes), max(b[3] for b in boxes),
            max(b[4] for b in boxes), max(b[5] for b in boxes))


def _open_part_for_insert(sw, filepath):
    """Preload a native part or assembly, silent and read-only, for insertion."""
    document_type = {".sldprt": SwDocumentTypes.swDocPART,
                     ".sldasm": SwDocumentTypes.swDocASSEMBLY}.get(
                         os.path.splitext(filepath)[1].lower())
    if document_type is None:
        return None
    app = getattr(sw, "app", None)
    if app is None:
        return None
    if hasattr(app, "_oleobj_"):  # typed wrapper rejects VARIANT byref
        import win32com.client
        app = win32com.client.dynamic.Dispatch(app)
    import pythoncom
    import win32com.client as wc
    errors = wc.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = wc.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    try:
        # swOpenDocOptions_Silent | swOpenDocOptions_ReadOnly
        return com(app, "OpenDoc6", filepath, int(document_type), 1 | 2, "", errors, warnings)
    except Exception as e:
        logger.warning("could not open %s for insert: %s", filepath, e)
        return None


@tool(
    name="insert_component",
    description=(
        "Insert a Part or sub-assembly into the active assembly at a "
        "given position. Position is in meters, assembly space. By default "
        "the component's bounding-box centre lands on the point (SolidWorks "
        "AddComponent5 behaviour); place='origin' instead puts the part's "
        "own origin on the point, which needs the part already open."
    ),
    schema={
        "type": "object",
        "properties": {
            "filepath": {"type": "string", "description": "Full path to the .SLDPRT/.SLDASM to insert"},
            "x": {"type": "number", "description": "X position in meters. Default 0."},
            "y": {"type": "number", "description": "Y position in meters. Default 0."},
            "z": {"type": "number", "description": "Z position in meters. Default 0."},
            "place": {
                "type": "string",
                "enum": ["center", "origin"],
                "description": (
                    "'center' (default) = AddComponent5 legacy behaviour, the "
                    "part's bounding-box centre lands on x,y,z. 'origin' = the "
                    "part's own origin lands on x,y,z."
                ),
            },
            "configuration": {
                "type": "string",
                "description": (
                    "Optional configuration name to insert, e.g. a Toolbox size "
                    "like 'ISO 4762 M10 x 16 - 16N'. Default: the part's "
                    "default configuration."
                ),
            },
        },
        "required": ["filepath"]
    },
    operation_class=OperationClass.MUTATE,
)
def insert_component(sw, filepath: str, x: float = 0.0, y: float = 0.0, z: float = 0.0,
                     place: str = "center", configuration: str = "") -> dict:
    """Insert a component into the active assembly"""
    asm, err = _require_assembly(sw)
    if err:
        return err

    if not os.path.exists(filepath):
        return sw._result(False, f"File not found: {filepath}",
                          SwErrors.swFileNotFoundError)

    place = (place or "center").lower()
    if place not in ("center", "origin"):
        return sw._result(False, "place must be 'center' or 'origin'.",
                          SwErrors.swInvalidInput)

    if place == "origin":
        box = _open_part_box(sw, filepath)
        if box is None:
            return sw._result(
                False,
                f"place='origin' needs the part already open and non-empty: {filepath}",
                SwErrors.swInvalidInput)
        x -= (box[0] + box[3]) / 2.0
        y -= (box[1] + box[4]) / 2.0
        z -= (box[2] + box[5]) / 2.0

    try:
        comp = com(asm, "AddComponent5", filepath, SW_ADD_COMPONENT_DEFAULT_CONFIG,
                   configuration, bool(configuration), "", x, y, z)
    except Exception as e:
        logger.error(f"AddComponent5 failed: {e}")
        return sw._result(False, f"Could not insert component: {e}",
                          SwErrors.swUnknownError)

    if comp is None:
        # Toolbox browser parts (and some library parts) are rejected by a
        # closed-document AddComponent5 -- it returns None with no error.
        # Opening the part first makes the insert work (verified live).
        opened = _open_part_for_insert(sw, filepath)
        if opened is None:
            detail = f" (configuration '{configuration}')" if configuration else ""
            return sw._result(False, f"Could not insert {filepath}{detail}.",
                              SwErrors.swFeatureError)
        try:
            try:
                comp = com(asm, "AddComponent5", filepath,
                           SW_ADD_COMPONENT_DEFAULT_CONFIG,
                           configuration, bool(configuration), "", x, y, z)
            except Exception as e:
                logger.error(f"AddComponent5 (retry, part open) failed: {e}")
                return sw._result(False, f"Could not insert component: {e}",
                                  SwErrors.swUnknownError)
            if comp is None:
                detail = f" (configuration '{configuration}')" if configuration else ""
                return sw._result(False, f"Could not insert {filepath}{detail}.",
                                  SwErrors.swFeatureError)
        finally:
            sw_app = getattr(sw, "app", None)
            if sw_app is not None:
                try:
                    com(sw_app, "CloseDoc", com(opened, "GetTitle"))
                except Exception:
                    pass

    return sw._result(
        True,
        f"Inserted {com(comp, 'Name2')}.",
        data={"name": com(comp, "Name2"), "path": filepath,
              "configuration": configuration or None}
    )


@tool(name="set_component_translation", description=(
    "Set one floating top-level component's absolute translation in millimetres, "
    "preserving rotation and scale. Requires expected current translation; reads "
    "native transform back. Does not save or repair mates."),
    schema={"type": "object", "properties": {
        "component_name": {"type": "string"},
        "translation_mm": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
        "expected_translation_mm": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3}},
        "required": ["component_name", "translation_mm", "expected_translation_mm"]},
    operation_class=OperationClass.MUTATE)
def set_component_translation(sw, component_name, translation_mm, expected_translation_mm):
    asm, error = _require_assembly(sw)
    if error:
        return error
    changed = False
    try:
        for values in (translation_mm, expected_translation_mm):
            if (not isinstance(values, (list, tuple)) or len(values) != 3 or
                    any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values)):
                raise ValueError("Translations must contain three finite numeric millimetre values.")
        if not isinstance(component_name, str) or not component_name or '/' in component_name:
            raise ValueError("Exact top-level component Name2 required.")
        component = _find_component(asm, component_name)
        if component is None:
            raise ValueError("Component not found.")
        if com(component, "Name2") != component_name:
            raise ValueError("Exact top-level component required; nested suffix matching is not allowed.")
        if com(component, "IsFixed"):
            raise ValueError("Fixed component must not be moved by this tool.")
        before = list(com(com(component, "Transform2"), "ArrayData"))
        if len(before) != 16 or not all(math.isfinite(v) for v in before) or before[12] <= 0:
            raise ValueError("Invalid native component transform.")
        if any(abs(before[9+i] * 1000 - expected_translation_mm[i]) > .001 for i in range(3)):
            raise ValueError("Component translation changed; refresh expected position.")
        desired = list(before)
        desired[9:12] = [v / 1000 for v in translation_mm]
        variant = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, desired)
        transform = com(com(sw.app, "GetMathUtility"), "CreateTransform", variant)
        set_com(transform, "ArrayData", variant)
        prepared = list(com(transform, "ArrayData"))
        if len(prepared) != 16 or any(abs(a-b) > 1e-10 for a,b in zip(prepared, desired)):
            raise ValueError("Math transform did not retain requested placement.")
        changed = True
        set_com(component, "Transform2", transform)
        actual = list(com(com(component, "Transform2"), "ArrayData"))
        if len(actual) != 16 or any(abs(a-b) > 1e-8 for a,b in zip(actual, desired)):
            raise ValueError("Native component placement readback differs; inspect constraints.")
        return sw._result(True, "Component translation verified; no save performed.", data={
            "component_name": component_name, "before_transform": before, "transform": actual,
            "translation_mm": [v * 1000 for v in actual[9:12]], "saved": False})
    except Exception as exc:
        return sw._result(False, str(exc), SwErrors.swInvalidInput,
                          data={"document_may_be_modified": changed, "saved": False})


@tool(name="set_component_fixed", description="Fix or float an exact top-level component and verify native state. No save performed.",
      schema={"type":"object","properties":{"component_name":{"type":"string","minLength":1},"fixed":{"type":"boolean"}},
              "required":["component_name","fixed"]}, operation_class=OperationClass.MUTATE)
def set_component_fixed(sw, component_name, fixed):
    asm,error=_require_assembly(sw)
    if error:return error
    changed=False
    try:
        if type(fixed) is not bool or not isinstance(component_name,str) or not component_name or '/' in component_name:
            raise ValueError("Exact top-level component Name2 and boolean fixed state required.")
        component=_find_component(asm,component_name)
        if component is None or com(component,"Name2")!=component_name:
            raise ValueError("Exact top-level component not found.")
        before=bool(com(component,"IsFixed"))
        if before!=fixed:
            com(asm,"ClearSelection2",True)
            data=com(com(asm,"SelectionManager"),"CreateSelectData")
            if not com(component,"Select4",False,data,False):raise ValueError("Component selection failed.")
            changed=True
            com(asm,"FixComponent" if fixed else "UnfixComponent")
        actual=bool(com(component,"IsFixed"))
        if actual!=fixed:raise ValueError("Native fixed state did not change; inspect constraints.")
        return sw._result(True,"Component fixed state verified; no save performed.",data={
            "component_name":component_name,"before_fixed":before,"fixed":actual,"saved":False})
    except Exception as exc:
        return sw._result(False,str(exc),SwErrors.swInvalidInput,data={"document_may_be_modified":changed,"saved":False})
    finally:
        com(asm,"ClearSelection2",True)


@tool(
    name="list_components",
    description=(
        "List the components of the active assembly. mode 'fast' reads only "
        "name and path and never queries leaf parts, which keeps large "
        "assemblies quick; mode 'detailed' also reads transforms, suppression "
        "state, configuration and fixed/virtual flags."
    ),
    schema={"type": "object", "properties": {
        "depth": {"type": "integer", "minimum": 1, "maximum": 32, "default": 32},
        "mode": {
            "type": "string", "enum": ["fast", "detailed"], "default": "detailed",
            "description": ("fast: name + path only, leaves are not queried. "
                            "detailed: every member, needed for transforms, "
                            "suppression, configurations.")},
    }, "required": []},
    operation_class=OperationClass.READ,
)
def list_components(sw, depth: int = 32, mode: str = "detailed") -> dict:
    """
    List all component instances of the active assembly recursively.

    ``fast`` mode exists because every COM member access on an instance inside
    a sub-assembly costs about 0.08 s in SolidWorks (a transform ~0.35 s), so
    the cost is the number of calls, not the data. A part instance is a leaf:
    fast mode recognises it by the ``.SLDPRT`` suffix of its referenced
    document and performs no further calls on it at all.
    """
    if not isinstance(depth, int) or isinstance(depth, bool) or not 1 <= depth <= 32:
        return sw._result(False, "depth must be an integer from 1 to 32.", SwErrors.swInvalidInput)
    if mode not in ("fast", "detailed"):
        return sw._result(False, "mode must be 'fast' or 'detailed'.",
                          SwErrors.swInvalidInput, {"code": "VALIDATION_FAILED"})
    asm, err = _require_assembly(sw)
    if err:
        return err

    comps = []
    unresolved = []
    truncated = False
    fast = mode == "fast"

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

    suppression_names = {
        0: "suppressed",
        1: "lightweight",
        2: "resolved",
        3: "fully_lightweight",
        4: "internal_id_mismatch",
    }

    def children_of(comp, instance_path):
        try:
            return com(comp, "GetChildren") or []
        except Exception as error:
            unresolved.append(f"{instance_path}: children unavailable ({error})")
            return None

    def visit(comp, parent_path=None, level=1):
        nonlocal truncated
        name = com(comp, "Name2")
        instance_path = f"{parent_path}/{name}" if parent_path else name
        path = optional_component_value(comp, "GetPathName", instance_path)
        # An unresolved path may hide a sub-assembly, so only a path that names
        # a part is a leaf; unknown paths are still descended into.
        if not path:
            is_subassembly = None
        else:
            is_subassembly = str(path).casefold().endswith(".sldasm")

        if fast:
            comps.append({
                "name": name,
                "instance_path": instance_path,
                "parent_path": parent_path,
                "path": path or None,
                "is_subassembly": is_subassembly,
            })
        else:
            suppression = optional_component_value(comp, "GetSuppression", instance_path)
            virtual = optional_component_value(comp, "IsVirtual", instance_path)
            comps.append({
                "name": name,
                "instance_path": instance_path,
                "parent_path": parent_path,
                "path": path or None,
                "is_subassembly": is_subassembly,
                "configuration": optional_component_value(
                    comp, "ReferencedConfiguration", instance_path),
                "transform": transform_data(comp, instance_path),
                "is_fixed": bool(optional_component_value(comp, "IsFixed", instance_path)),
                "suppressed": suppression == 0 if suppression is not None else None,
                "suppression_state": suppression_names.get(suppression, "unknown"),
                "lightweight": suppression in {1, 3} if suppression is not None else None,
                "virtual": bool(virtual) if virtual is not None else None,
            })

        if fast and is_subassembly is False:
            return
        if level >= depth:
            children = children_of(comp, instance_path)
            if children:
                truncated = True
            return
        for child in children_of(comp, instance_path) or []:
            visit(child, instance_path, level + 1)

    for component in com(asm, "GetComponents", True) or []:
        visit(component)

    return sw._result(
        True, f"Found {len(comps)} component instances ({mode}).",
        data={
            "mode": mode,
            "components": comps,
            "coverage": {
                "complete": not unresolved and not truncated,
                "visited_count": len(comps),
                "unresolved": unresolved,
                "truncated": truncated,
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
    unresolved = []
    for index, (face, kind) in enumerate(_component_faces(comp)):
        surface = com(face, "GetSurface")
        entry = {"index": index, "kind": kind}
        if kind == "planar":
            entry["area_mm2"] = round(com(face, "GetArea") * 1_000_000, 2)
            try:
                tf = list(com(com(comp, "Transform2"), "ArrayData"))
                plane = list(com(surface, "PlaneParams"))
                normal = list(com(face, "Normal"))
                if len(tf) != 16 or len(plane) != 6 or len(normal) != 3:
                    raise ValueError("Unexpected planar face or transform array length.")
                if not all(math.isfinite(v) for v in tf + plane + normal) or tf[12] <= 0:
                    raise ValueError("Non-finite geometry or unsupported component scale.")
                point = _local_to_global(plane[3:6], tf)
                center = _local_to_global(_face_local_point(face, kind), tf)
                rotation = list(tf)
                rotation[9:13] = [0, 0, 0, 1]
                direction = _local_to_global(normal, rotation)
                length = math.sqrt(sum(v*v for v in direction))
                if length <= 1e-12:
                    raise ValueError("Planar face has no usable oriented normal.")
                entry.update(
                    plane_point_assembly_mm=[v*1000 for v in point],
                    box_center_assembly_mm=[v*1000 for v in center],
                    normal_assembly=[v/length for v in direction],
                    geometry_note="Oriented face normal; box centre is not an area centroid or guaranteed interior point.",
                )
            except Exception as exc:
                unresolved.append(f"face[{index}]: assembly geometry unavailable: {exc}")
        else:
            radius = com(surface, "CylinderParams")[6]
            entry["radius_mm"] = round(radius * 1000, 3)
        faces.append(entry)

    return sw._result(True, f"Found {len(faces)} faces on {component_name}.",
                      data={"faces": faces, "complete": not unresolved,
                            "unresolved": unresolved, "coordinate_frame": "active assembly"})


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
            "this mate type). If the two faces are exactly coincident (same "
            "radius or same plane on two components), SelectByID2 cannot "
            "resolve the probe point; pick a different face of the pair, "
            "e.g. a free bore instead of the seat it duplicates "
            "(api-findings.md 21.3).",
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
    """List mate definitions, entities, values, and rebuild status."""
    asm, err = _require_assembly(sw)
    if err:
        return err

    unresolved = []

    def optional(obj, member, context, *args):
        try:
            return com(obj, member, *args)
        except Exception as error:
            unresolved.append(f"{context}: {member} unavailable ({error})")
            return None

    def mate_type_name(value):
        try:
            return SwMateTypes(value).name.removeprefix("swMate").lower()
        except (ValueError, TypeError):
            return "unknown"

    def solver_status(feature, context, definition_available):
        warning = win32com.client.VARIANT(
            pythoncom.VT_BYREF | pythoncom.VT_BOOL, False
        )
        try:
            error_code = com(feature, "GetErrorCode2", warning)
            is_warning = bool(warning.value) if error_code else False
        except Exception as error:
            unresolved.append(f"{context}: GetErrorCode2 unavailable ({error})")
            error_code = None
            is_warning = None
        if not definition_available:
            state = "unavailable"
        elif error_code is None:
            state = "unknown"
        elif error_code == 0:
            state = "solved"
        elif is_warning:
            state = "warning"
        else:
            state = "error"
        return {"state": state, "error_code": error_code, "is_warning": is_warning}

    def inspect_entity(entity, context):
        component = optional(entity, "ReferenceComponent", context)
        component_name = (
            optional(component, "Name2", context) if component is not None else None
        )
        params = optional(entity, "EntityParams", context)
        values = list(params) if params is not None else []
        if len(values) < 8:
            unresolved.append(
                f"{context}: EntityParams returned {len(values)} of 8 values"
            )
            values.extend([None] * (8 - len(values)))
        return {
            "component": component_name,
            "reference_type": optional(entity, "ReferenceType2", context),
            "point_m": values[0:3],
            "vector": values[3:6],
            "radius_1_m": values[6],
            "radius_2_m": values[7],
        }

    def inspect_mate(feature):
        name = optional(feature, "Name", "mate") or "<unknown>"
        context = f"mate {name}"
        definition = optional(feature, "GetSpecificFeature2", context)
        feature_type = optional(feature, "GetTypeName2", context) or "<unknown>"
        mate_type = optional(definition, "Type", context) if definition is not None else None
        entities = []
        value = None
        if definition is not None:
            count = optional(definition, "GetMateEntityCount", context)
            if isinstance(count, int):
                for index in range(count):
                    entity = optional(definition, "MateEntity", f"{context}/entity[{index}]", index)
                    if entity is not None:
                        entities.append(inspect_entity(entity, f"{context}/entity[{index}]"))
            if mate_type in {
                int(SwMateTypes.swMateDISTANCE), int(SwMateTypes.swMateANGLE)
            }:
                display = optional(definition, "DisplayDimension2", context, 0)
                dimension = (
                    optional(display, "GetDimension2", context, 0)
                    if display is not None else None
                )
                system_value = (
                    optional(dimension, "SystemValue", context)
                    if dimension is not None else None
                )
                value = {
                    "system_value": system_value,
                    "unit": (
                        "m" if mate_type == int(SwMateTypes.swMateDISTANCE) else "rad"
                    ),
                }
        else:
            unresolved.append(f"{context}: mate definition unavailable")

        is_flippable_type = mate_type in {
            int(SwMateTypes.swMateDISTANCE), int(SwMateTypes.swMateANGLE)
        }

        return {
            "name": name,
            "feature_id": optional(feature, "GetID", context),
            "feature_type": feature_type,
            "mate_type": mate_type,
            "mate_type_name": mate_type_name(mate_type),
            "alignment": (
                optional(definition, "Alignment", context)
                if definition is not None else None
            ),
            "can_flip": (
                optional(definition, "CanBeFlipped", context)
                if definition is not None and is_flippable_type else None
            ),
            "flipped": (
                optional(definition, "Flipped", context)
                if definition is not None and is_flippable_type else None
            ),
            "suppressed": optional(feature, "IsSuppressed", context),
            "value": value,
            "entities": entities,
            "solver_status": solver_status(feature, context, definition is not None),
        }

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
            mates.append(inspect_mate(sub))
            sub = com(sub, "GetNextSubFeature")

    return sw._result(True, f"Found {len(mates)} mates.", data={
        "mates": mates,
        "coverage": {
            "complete": not unresolved,
            "visited_count": len(mates),
            "unresolved": unresolved,
            "truncated": False,
            "next_cursor": None,
        },
    })


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
