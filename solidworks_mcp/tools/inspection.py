"""Read-only structural inspection tools."""

from pathlib import PureWindowsPath
from uuid import uuid4

from ..comutil import com
from ..constants import SwErrors, SwPlanes
from ..core.snapshot import InstanceRef, ProjectSnapshot, SnapshotCoverage
from ..core.policy import OperationClass
from ..inspection.snapshots import SnapshotCursorError, SnapshotStore
from ..inspection.documents import inspect_feature_tree
from ..registry import tool
from .assembly import list_components


_INSPECTION_SECTIONS = {
    "summary", "configurations", "features", "parameters", "assembly",
    "mates", "dependencies", "manufacturing",
}


def _component_document_type(path: str | None) -> str:
    suffix = PureWindowsPath(path).suffix.casefold() if path else ""
    return {".sldprt": "part", ".sldasm": "assembly", ".slddrw": "drawing"}.get(
        suffix, "unknown"
    )


@tool(
    name="inspect_document",
    description=(
        "Build a versioned, pageable snapshot of the active document and assembly graph. "
        "Repeated instances and incomplete references are preserved."
    ),
    schema={"type": "object", "properties": {
        "sections": {"type": "array", "items": {"type": "string", "enum": sorted(_INSPECTION_SECTIONS)}},
        "depth": {"type": "integer", "minimum": 1, "maximum": 32, "default": 4},
        "cursor": {"type": "string"},
        "page_size": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
    }, "required": []},
    operation_class=OperationClass.READ,
)
def inspect_document(
    sw,
    sections: list[str] | None = None,
    depth: int = 4,
    cursor: str | None = None,
    page_size: int = 100,
) -> dict:
    """Return a read-only project snapshot or resume a stored snapshot page."""
    requested = tuple(sections or ("summary", "assembly", "dependencies"))
    unknown = sorted(set(requested) - _INSPECTION_SECTIONS)
    if unknown:
        return sw._result(
            False, f"Unknown inspection sections: {', '.join(unknown)}",
            SwErrors.swInvalidInput, {"code": "VALIDATION_FAILED"},
        )
    if not isinstance(page_size, int) or isinstance(page_size, bool) or not 1 <= page_size <= 500:
        return sw._result(False, "page_size must be an integer from 1 to 500.",
                          SwErrors.swInvalidInput, {"code": "VALIDATION_FAILED"})

    target, error = sw.capture_active_document_ref()
    if error:
        return error
    store = getattr(sw, "_snapshot_store", None)
    if store is None:
        store = SnapshotStore()
        sw._snapshot_store = store

    try:
        if cursor:
            page = store.resume(cursor, target, page_size=page_size)
            return sw._result(True, "Inspection snapshot page resumed.", data={
                "snapshot": page.to_dict(), "sections": list(requested),
            })

        documents = {target.document_id: target}
        instances = []
        dependency_edges = []
        unresolved = []
        complete = True
        truncated = False
        observations = []

        if "summary" in requested:
            observations.append({
                "section": "summary",
                "source": "SolidWorks COM",
                "document_id": target.document_id,
                "configuration": target.configuration,
                "revision_token": target.revision_token,
                "state": "known",
            })

        if {"features", "parameters"} & set(requested):
            document, document_error = sw.get_active_doc()
            if document_error:
                return document_error
            feature_report = inspect_feature_tree(document, max_depth=depth)
            if feature_report["unresolved"]:
                complete = False
                unresolved.extend(feature_report["unresolved"])
            common = {
                "source": "SolidWorks COM",
                "document_id": target.document_id,
                "configuration": target.configuration,
                "revision_token": target.revision_token,
                "state": "known" if not feature_report["unresolved"] else "unavailable",
            }
            if "features" in requested:
                observations.append({
                    **common, "section": "features", "value": feature_report["features"],
                })
            if "parameters" in requested:
                observations.append({
                    **common,
                    "section": "parameters",
                    "value": {"equations": feature_report["equations"]},
                })

        if target.document_type == "assembly" and ({"assembly", "dependencies"} & set(requested)):
            component_result = list_components(sw, depth=depth)
            if not component_result["success"]:
                return component_result
            component_data = component_result["data"]
            coverage = component_data["coverage"]
            unresolved.extend(coverage["unresolved"])
            complete = bool(coverage["complete"])
            truncated = bool(coverage["truncated"])
            for component in component_data["components"]:
                path = component.get("path")
                component_document = sw._document_session.capture(
                    title=PureWindowsPath(path).name if path else component["name"],
                    path=path,
                    document_type=_component_document_type(path),
                    configuration=component.get("configuration"),
                )
                documents.setdefault(component_document.document_id, component_document)
                instances.append(InstanceRef(
                    instance_path=component["instance_path"],
                    parent_path=component.get("parent_path"),
                    document_id=component_document.document_id,
                    configuration=component.get("configuration"),
                    transform=tuple(component["transform"]) if component.get("transform") else None,
                    suppression_state=component.get("suppression_state"),
                ))
                dependency_edges.append({
                    "source": target.document_id,
                    "target": component_document.document_id,
                    "instance_path": component["instance_path"],
                    "kind": "assembly_component",
                    "state": "known" if path else "unresolved",
                })

        snapshot = ProjectSnapshot(
            snapshot_id=str(uuid4()),
            documents=tuple(documents.values()),
            instances=tuple(instances),
            dependency_edges=tuple(dependency_edges),
            observations=tuple(observations),
            coverage=SnapshotCoverage(
                complete=complete,
                visited_count=len(instances),
                unresolved=tuple(unresolved),
                truncated=truncated,
            ),
        )
        page = store.add(snapshot, target, page_size=page_size)
        return sw._result(True, "Inspection snapshot captured.", data={
            "snapshot": page.to_dict(), "sections": list(requested),
        })
    except SnapshotCursorError as cursor_error:
        return sw._result(False, str(cursor_error), SwErrors.swInvalidInput,
                          {"code": cursor_error.code})


@tool(
    name="list_planes",
    description="List standard and reference planes in the active document without changing selection.",
    schema={"type": "object", "properties": {}, "required": []},
    operation_class=OperationClass.READ,
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
    standard_names = {plane["name"] for plane in planes}
    try:
        feature = com(doc, "FirstFeature")
        while feature is not None:
            if com(feature, "GetTypeName2") == "RefPlane":
                name = com(feature, "Name")
                if name not in standard_names:
                    planes.append({"name": name, "kind": "reference"})
            feature = com(feature, "GetNextFeature")
    except Exception as error:
        return sw._result(False, f"Could not inspect reference planes: {error}",
                          SwErrors.swUnknownError)

    return sw._result(True, f"{len(planes)} planes found.", data={"planes": planes})
