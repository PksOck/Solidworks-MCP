"""Advertised tool catalog: guarded mode and enabled toolsets applied to all tools.

Toolsets only shorten what a client loads; a call to a tool outside the
enabled toolsets still executes, so a stale client list never breaks work.
"""

import logging
import os
from typing import Iterable, List, Optional

from mcp.types import Tool

from .config import get_config
from .registry import registered_tools, tool_module_for

logger = logging.getLogger("SolidWorksMCP")

TOOLSETS = {
    "core": ("connection", "documents", "session", "saving", "history", "views",
             "inspection", "measurements", "export"),
    "sketch": ("sketch_basic", "sketch_entities", "sketch_create", "construction_geometry"),
    "sketch_edit": ("sketch_edit",),
    "features": ("features_basic", "patterns", "advanced_features", "body_features",
                 "reference_geometry", "equations", "material", "appearance",
                 "properties", "configurations"),
    "surfaces": ("surface_features",),
    "assembly": ("assembly", "standard_parts"),
    "drawing": ("drawings", "drawing_annotations"),
    "sheetmetal": ("sheetmetal",),
    "weldments": ("weldments", "cutlist"),
    "simulation": ("simulation",),
    "project": ("project_copy", "project_lifecycle", "model_edit", "parameter_workspace",
                "parameter_batch", "cad_workflows", "manufacturing_package", "imports"),
    "planners": ("engineering_planners",),
}
_MODULE_TOOLSET = {module: name for name, modules in TOOLSETS.items() for module in modules}

# Tools still defined inline in server.py; removed when they move to tools/ (plan B).
_LEGACY_TOOLSETS = {
    **dict.fromkeys(("get_modeling_guide", "connect_solidworks", "get_solidworks_info",
                     "get_capabilities", "bind_active_document", "set_units", "execute_python",
                     "create_new_part", "create_new_assembly", "open_document", "close_document",
                     "get_document_info", "list_open_documents"), "core"),
    **dict.fromkeys(("create_sketch", "create_sketch_on_face", "draw_line", "draw_circle",
                     "draw_rectangle", "draw_arc", "draw_polygon", "draw_spline",
                     "draw_arc_3point", "draw_slot", "close_sketch", "get_sketch_status"), "sketch"),
    **dict.fromkeys(("extrude_sketch", "cut_extrude", "revolve_sketch", "fillet_edges",
                     "chamfer_edges", "list_features"), "features"),
}


def toolset_of(name: str) -> Optional[str]:
    if name in _LEGACY_TOOLSETS:
        return _LEGACY_TOOLSETS[name]
    module = tool_module_for(name)
    return _MODULE_TOOLSET.get(module.rsplit(".", 1)[-1]) if module else None


def enabled_toolsets() -> List[str]:
    raw = os.environ.get("SW_MCP_TOOLSETS")
    if raw is not None:
        requested = [part.strip() for part in raw.split(",") if part.strip()]
    else:
        requested = get_config().enabled_toolsets
    if requested is None:
        return sorted(TOOLSETS)
    unknown = [name for name in requested if name not in TOOLSETS]
    if unknown:
        logger.warning("Unknown toolsets ignored: %s", ", ".join(unknown))
    return sorted({"core"} | {name for name in requested if name in TOOLSETS})


def advertised_tools(extra: Iterable[Tool] = ()) -> List[Tool]:
    """Tools a client should see; unmapped tools are never hidden."""
    enabled = set(enabled_toolsets())
    guarded = get_config().guarded_mode
    result = []
    for item in list(extra) + registered_tools():
        if guarded and item.name == "execute_python":
            continue
        toolset = toolset_of(item.name)
        if toolset is None or toolset in enabled:
            result.append(item)
    return result
