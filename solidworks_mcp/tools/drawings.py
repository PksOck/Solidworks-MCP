"""
Drawing tools (part F2): standard views and cut-list table on the active drawing.
"""

import logging
import os

from ..comutil import com
from ..constants import SwErrors
from ..core.policy import OperationClass
from ..registry import tool

logger = logging.getLogger("SolidWorksMCP")

_DEFAULT_ANGLE_TEMPLATE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "templates",
    "weldment_cutlist_angles.sldwldtbt"
)


@tool(
    name="list_drawing_views",
    description="List the views on the active drawing sheet, by name. Read-only.",
    schema={"type": "object", "properties": {}, "required": []},
    operation_class=OperationClass.READ,
)
def list_drawing_views(sw) -> dict:
    """Enumerate views on the active drawing document."""
    doc, err = sw.get_active_doc()
    if err:
        return err
    if com(doc, "GetType") != 3:
        return sw._result(False, "Active document is not a drawing.",
                          SwErrors.swUnknownError)

    views = []
    v = com(doc, "GetFirstView")
    while v is not None:
        views.append(com(v, "GetName2"))
        v = com(v, "GetNextView")

    return sw._result(True, f"Found {len(views)} view(s).", data={"views": views})


@tool(
    name="add_standard_3_view",
    description=(
        "Add a standard 3-view (third-angle projection) of a model to the "
        "active drawing sheet. The model must already be open in SolidWorks. "
        "Modifies the active drawing."
    ),
    schema={
        "type": "object",
        "properties": {
            "model_name": {
                "type": "string",
                "description": "Title of the already-open model document (part/assembly), "
                                "e.g. as shown by list_open_documents."
            }
        },
        "required": ["model_name"]
    },
    operation_class=OperationClass.MUTATE,
)
def add_standard_3_view(sw, model_name: str) -> dict:
    """Insert front/top/right views of an open model onto the active drawing."""
    doc, err = sw.get_active_doc()
    if err:
        return err
    if com(doc, "GetType") != 3:
        return sw._result(False, "Active document is not a drawing.",
                          SwErrors.swUnknownError)

    try:
        ok = com(doc, "Create3rdAngleViews2", model_name)
    except Exception as e:
        logger.error(f"Create3rdAngleViews2 failed: {e}")
        return sw._result(False, f"Could not create standard views: {e}",
                          SwErrors.swUnknownError)

    if not ok:
        return sw._result(
            False,
            f"Create3rdAngleViews2 returned false for '{model_name}' — is it open "
            "and spelled exactly as in list_open_documents?",
            SwErrors.swUnknownError)

    return sw._result(True, f"Created standard 3-view of '{model_name}'.")


@tool(
    name="insert_cut_list_table",
    description=(
        "Insert a weldment cut-list table into a drawing view. The view must "
        "already show a weldment part with a cut list (see get_cut_list). "
        "Modifies the active drawing."
    ),
    schema={
        "type": "object",
        "properties": {
            "view_name": {
                "type": "string",
                "description": "Name of the drawing view to attach the table to, "
                                "from list_drawing_views."
            },
            "x": {"type": "number", "description": "Table anchor X position in meters.", "default": 0.05},
            "y": {"type": "number", "description": "Table anchor Y position in meters.", "default": 0.05},
            "template_path": {
                "type": "string",
                "description": "Full path to a .sldwldtbt table template. Optional; "
                                "empty uses the default template."
            }
        },
        "required": ["view_name"]
    },
    operation_class=OperationClass.MUTATE,
)
def insert_cut_list_table(sw, view_name: str, x: float = 0.05, y: float = 0.05,
                           template_path: str = "") -> dict:
    """Insert a cut-list table anchored at (x, y) into the named drawing view."""
    doc, err = sw.get_active_doc()
    if err:
        return err
    if com(doc, "GetType") != 3:
        return sw._result(False, "Active document is not a drawing.",
                          SwErrors.swUnknownError)

    view = None
    v = com(doc, "GetFirstView")
    while v is not None:
        if com(v, "GetName2") == view_name:
            view = v
            break
        v = com(v, "GetNextView")

    if view is None:
        return sw._result(False, f"View not found: {view_name}",
                          SwErrors.swUnknownError)

    effective_template = template_path or (
        _DEFAULT_ANGLE_TEMPLATE if os.path.isfile(_DEFAULT_ANGLE_TEMPLATE) else ""
    )

    try:
        table = view.InsertWeldmentTable(True, x, y, 1, "", effective_template)
    except Exception as e:
        logger.error(f"InsertWeldmentTable failed: {e}")
        return sw._result(False, f"Could not insert cut-list table: {e}",
                          SwErrors.swUnknownError)

    if table is None:
        return sw._result(
            False,
            f"InsertWeldmentTable returned nothing for view '{view_name}' — "
            "it likely has no cut list (not a weldment, or cut list not built).",
            SwErrors.swUnknownError)

    return sw._result(
        True,
        f"Inserted cut-list table on view '{view_name}' "
        f"({table.RowCount} row(s), {table.ColumnCount} column(s)).",
        data={"rows": table.RowCount, "columns": table.ColumnCount}
    )
