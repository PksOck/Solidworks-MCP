"""
SolidWorks MCP Server
---------------------
Main MCP server entry point with all tools.

Version: 4.0.0 (Fixed for SolidWorks 2025)
Author: Samsaam Ali Baig

Fixes v4.0.0:
- execute_python now captures stdout/stderr
- FeatureExtrusion2 with correct 23 params for SW 2025
- list_features: property access instead of method calls
- extrude_sketch: proper sketch close + select before extrude
- cut_extrude: proper sketch handling
- NEW: close_sketch tool
- NEW: get_sketch_status tool for diagnostics
"""

import io
import sys
import json
import base64
import hashlib
import logging
import traceback
from typing import Dict
from pathlib import Path
from uuid import uuid4

# MCP imports
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import ImageContent, Tool, TextContent, Resource
from mcp.server.lowlevel.helper_types import ReadResourceContents

# Local imports
from .automation import SolidWorksAutomation
from .constants import SwErrors
from .config import get_config, save_config
from .core.policy import OperationClass
from .core.contracts import OperationError, OperationResult, OperationStatus
from .core.evidence import OperationJournal
from .core.session import TargetMismatchError
from . import catalog
from .registry import execute
from .knowledge import library as modeling_guidance
from .utils import get_solidworks_info, set_default_unit
from .tools.session import session_health

# Configure logging
config = get_config()
LOG_FILE = Path(__file__).parent / config.log_file

logging.basicConfig(
    level=config.get_log_level_int(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE, encoding='utf-8')]
)
logger = logging.getLogger("SolidWorksMCP")

# ============================================================================
# Global Instances
# ============================================================================

sw_automation = SolidWorksAutomation()
server = Server("solidworks-mcp-server", instructions=modeling_guidance.server_instructions())
operation_journal = OperationJournal()
_operation_payloads: Dict[str, Dict] = {}

_LEGACY_OPERATION_CLASSES = {
    "get_modeling_guide": OperationClass.READ,
    "close_document": OperationClass.MUTATE,
    "execute_python": OperationClass.RAW_EXECUTION,
}


def _execute_python_tool() -> Tool:
    return Tool(
        name="execute_python",
        description="Execute custom Python code with stdout capture. Access 'sw' (app), 'doc' (active document). Use print() for debug output.",
        inputSchema={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"}
            },
            "required": ["code"]
        }
    )


# ============================================================================
# Tool Definitions
# ============================================================================

def _legacy_tools() -> list[Tool]:
    """Tools still defined inline in this module (moved to tools/ by plan B)."""
    return [
        Tool(
            name="get_modeling_guide",
            description=(
                "Read SolidWorks expert guidance and ordered modeling workflows. "
                "Use topic='index' to choose a topic before modeling; returns relevant "
                "currently advertised tools and recorded evidence. Read-only, no CAD connection needed."
            ),
            inputSchema={"type": "object", "properties": {
                "topic": {"type": "string", "default": "index",
                          "description": "Exact topic ID from index, e.g. workflow/part, workflow/weldment, expert."}
            }, "additionalProperties": False},
        ),
        # Connection Tools
        Tool(
            name="connect_solidworks",
            description="Connect to SolidWorks. Launches if not running.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="get_solidworks_info",
            description=(
                "Get SolidWorks installation information and, when connected, session health: "
                "process id, dedicated GPU memory, open document count and a restart hint."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="get_capabilities",
            description="Report the currently advertised tools, guarded-mode state, and known blocked capabilities.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="bind_active_document",
            description=(
                "Explicitly bind the current SolidWorks ActiveDoc and configuration "
                "as the target for subsequent mutating operations."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        
        # Document Tools
        Tool(
            name="create_new_part",
            description="Create a new part document.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="create_new_assembly",
            description="Create a new assembly document.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="open_document",
            description="Open an existing SolidWorks document.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "Path to file"}
                },
                "required": ["filepath"]
            }
        ),
        Tool(
            name="close_document",
            description="Close the active document.",
            inputSchema={
                "type": "object",
                "properties": {
                    "save": {"type": "boolean", "default": False, "description": "Save before closing"}
                },
                "required": []
            }
        ),
        Tool(
            name="get_document_info",
            description="Get information about the active document.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="list_open_documents",
            description="List all open documents.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        
        # Utility Tools
        Tool(
            name="set_units",
            description="Set default unit for dimensions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "unit": {
                        "type": "string",
                        "enum": ["mm", "inch", "m", "cm"],
                        "description": "Default unit"
                    }
                },
                "required": ["unit"]
            }
        ),
    ] + [_execute_python_tool()]


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List advertised SolidWorks tools"""
    return catalog.advertised_tools(_legacy_tools())


# ============================================================================
# Result Formatter
# ============================================================================

@server.list_resources()
async def list_modeling_resources() -> list[Resource]:
    entries = [{"id": "index", "title": "SolidWorks modeling guide index",
                "uri": modeling_guidance.URI_PREFIX + "index"}] + modeling_guidance.catalog()
    return [Resource(uri=entry["uri"], name=entry["id"],
                     description=entry["title"], mimeType="application/json")
            for entry in entries]


def _modeling_guide_payload(topic: str) -> dict:
    advertised = {tool.name for tool in catalog.advertised_tools(_legacy_tools())}
    return modeling_guidance.read_topic(topic, advertised)


@server.read_resource()
async def read_modeling_resource(uri) -> list[ReadResourceContents]:
    topic = modeling_guidance.topic_for_uri(str(uri))
    payload = _modeling_guide_payload(topic)
    return [ReadResourceContents(content=json.dumps(payload, ensure_ascii=False),
                                 mime_type="application/json")]


def format_result(r: Dict) -> str:
    """Format a result as compact text: status line, Details JSON, Operation JSON."""
    status = "SUCCESS" if r["success"] else "ERROR"
    lines = [f"[{status}] {r['message']}"]

    if not r["success"]:
        lines.append(f"Error Code: {r['error_code']} ({r['error_name']})")

    if r.get("data"):
        lines.append("Details: " + json.dumps(r["data"], ensure_ascii=False))

    if r.get("schema_version"):
        operation = {"operation_id": r["operation_id"], "status": r["status"]}
        if r.get("target_before") is not None:
            operation["target_before"] = r["target_before"]
        if r.get("target_after") is not None and r.get("target_after") != r.get("target_before"):
            operation["target_after"] = r["target_after"]
        for key in ("warnings", "errors"):
            if r.get(key):
                operation[key] = r[key]
        lines.append("Operation: " + json.dumps(operation, ensure_ascii=False))

    return "\n".join(lines)


def _content_for_result(result: Dict) -> list[TextContent | ImageContent]:
    """Attach a capture's bytes so MCP clients receive an image, not only a path."""
    content: list[TextContent | ImageContent] = [
        TextContent(type="text", text=format_result(result))
    ]
    artifact = result.get("data", {}).get("artifact", {})
    if artifact.get("mime_type") == "image/png" and artifact.get("path"):
        image_path = Path(artifact["path"])
        if image_path.is_file():
            image_bytes = image_path.read_bytes()
            expected_hash = artifact.get("sha256")
            actual_hash = hashlib.sha256(image_bytes).hexdigest()
            if expected_hash and expected_hash != actual_hash:
                content[0].text += "\n[WARNING] Image bytes were not attached because the artifact hash changed."
            else:
                content.append(ImageContent(
                    type="image",
                    data=base64.b64encode(image_bytes).decode("ascii"),
                    mimeType="image/png",
                ))
    return content


# ============================================================================
# Tool Handlers
# ============================================================================

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent]:
    """Handle MCP tool calls"""
    try:
        arguments = dict(arguments or {})
        operation_id = arguments.pop("operation_id", None) or str(uuid4())
        replay = operation_journal.reserve(operation_id)
        if replay is not None:
            payload = _operation_payloads.get(operation_id)
            if payload is None:
                payload = replay.to_dict(legacy={
                    "success": replay.status is OperationStatus.COMPLETED,
                    "message": "Operation outcome is already recorded.",
                    "error_code": 0 if replay.status is OperationStatus.COMPLETED else 1,
                    "error_name": replay.status.value,
                    "data": dict(replay.data),
                })
            return _content_for_result(payload)
        operation_journal.mark_running(operation_id)
        logger.info(f"Tool: {name}, Args: {arguments}")

        operation_class = _LEGACY_OPERATION_CLASSES.get(name)
        execution = None
        target_before = None
        guard_error = None
        if operation_class in {
            OperationClass.STATEFUL_READ,
            OperationClass.MUTATE,
            OperationClass.EXPORT,
        }:
            try:
                if sw_automation.has_bound_document():
                    target_before = sw_automation.require_bound_active_document()
                else:
                    target_before = sw_automation.bind_active_document()
            except TargetMismatchError as error:
                detail = error.operation_error
                result = sw_automation._result(
                    False,
                    str(error),
                    SwErrors.swInvalidInput,
                    {"code": detail.code, "retryable": detail.retryable},
                )
                guard_error = result
        
        # Connection Tools
        if guard_error is not None:
            result = guard_error

        elif name == "get_modeling_guide":
            try:
                payload = _modeling_guide_payload(arguments.get("topic", "index"))
                result = sw_automation._result(True, "Modeling guide loaded; no CAD operations executed.",
                                               SwErrors.swSuccess, payload)
            except ValueError as error:
                result = sw_automation._result(False, str(error), SwErrors.swInvalidInput)

        elif name == "connect_solidworks":
            result = sw_automation.connect()
        
        elif name == "get_solidworks_info":
            info = get_solidworks_info()
            info["session"] = session_health(sw_automation)
            result = {
                "success": info["found"],
                "message": f"SolidWorks {'found' if info['found'] else 'not found'}",
                "error_code": 0 if info["found"] else 105,
                "error_name": "swSuccess" if info["found"] else "swSolidWorksNotFound",
                "data": info
            }

        elif name == "get_capabilities":
            advertised = [tool.name for tool in await list_tools()]
            blocked = [{
                "name": "pack_and_go",
                "status": "blocked",
                "reason": "pywin32 cannot marshal the required BYREF IDispatch Pack-and-Go out parameter."
            }]
            if config.guarded_mode:
                blocked.append({
                    "name": "execute_python",
                    "status": "blocked",
                    "reason": "Raw execution is disabled in guarded mode."
                })
            sw_build = None
            if sw_automation.is_connected:
                try:
                    revision = sw_automation.app.RevisionNumber
                    sw_build = revision() if callable(revision) else revision
                except Exception:
                    sw_build = "unavailable"
            result = {
                "success": True,
                "message": "Capability report generated.",
                "error_code": 0,
                "error_name": "swSuccess",
                "data": {
                    "guarded_mode": config.guarded_mode,
                    "solidworks_build": sw_build,
                    "advertised_tools": advertised,
                    "toolsets": {"enabled": catalog.enabled_toolsets(),
                                 "available": sorted(catalog.TOOLSETS)},
                    "blocked_capabilities": blocked,
                    "modeling_guidance": {"tool": "get_modeling_guide", "topic": "index",
                                          "resource": "solidworks://guides/index"},
                }
            }

        elif name == "bind_active_document":
            document = sw_automation.bind_active_document()
            result = sw_automation._result(
                True,
                "Active document bound to this MCP session.",
                SwErrors.swSuccess,
                document.to_dict(),
            )
        
        # Document Tools
        elif name == "create_new_part":
            result = sw_automation.create_new_part()
        
        elif name == "create_new_assembly":
            result = sw_automation.create_new_assembly()
        
        elif name == "open_document":
            result = sw_automation.open_document(arguments.get("filepath", ""))
        
        elif name == "close_document":
            result = sw_automation.close_document(arguments.get("save", False))
        
        elif name == "get_document_info":
            result = sw_automation.get_document_info()
        
        elif name == "list_open_documents":
            result = sw_automation.list_open_documents()
        
        # Utility Tools
        elif name == "set_units":
            unit = arguments.get("unit", "mm")
            set_default_unit(unit)
            sw_automation._units.default_unit = unit
            result = {
                "success": True,
                "message": f"Default unit set to: {unit}",
                "error_code": 0,
                "error_name": "swSuccess",
                "data": {"unit": unit}
            }
        
        elif name == "execute_python":
            if config.guarded_mode:
                result = sw_automation._result(
                    False, "execute_python is unavailable in guarded mode.",
                    SwErrors.swInvalidInput)
            else:
                code = arguments.get("code", "")
                if not code:
                    result = sw_automation._result(False, "Code is required", SwErrors.swInvalidInput)
                else:
                    result = _execute_python_fixed(code)
        
        else:
            execution = execute(name, sw_automation, arguments)
            result = execution.result
            target_before = execution.target_before

        if execution is not None:
            target_after = execution.target_after
        else:
            target_after = target_before
            if result.get("success"):
                if name in {"create_new_part", "create_new_assembly", "open_document"}:
                    target_after = sw_automation.bind_active_document()
                elif name == "bind_active_document":
                    target_after = document
                elif (
                    target_before is not None
                    and operation_class is OperationClass.MUTATE
                    and name != "close_document"
                    and hasattr(sw_automation, "mark_active_document_mutated")
                ):
                    target_after = sw_automation.mark_active_document_mutated(target_before)

        if result.get("success"):
            operation_result = OperationResult(
                operation_id=operation_id,
                status=OperationStatus.COMPLETED,
                target_before=target_before,
                target_after=target_after,
                data=dict(result.get("data", {})),
            )
        else:
            detail = result.get("data", {})
            operation_result = OperationResult(
                operation_id=operation_id,
                status=OperationStatus.FAILED,
                target_before=target_before,
                target_after=target_after,
                data=dict(detail),
                errors=(OperationError(
                    code=detail.get("code", result.get("error_name", "COM_ERROR")),
                    message=result.get("message", "Operation failed."),
                    retryable=bool(detail.get("retryable", False)),
                ),),
            )
        operation_journal.record(operation_result)
        result = operation_result.to_dict(legacy=result)
        _operation_payloads[operation_id] = result
        
        logger.info(f"Result: success={result['success']}")
        return _content_for_result(result)
        
    except Exception as e:
        logger.error(f"Tool error: {e}\n{traceback.format_exc()}")
        if "operation_id" in locals():
            failed = OperationResult.failed(operation_id, locals().get("target_before"), str(e))
            operation_journal.record(failed)
            payload = failed.to_dict(legacy={
                "success": False,
                "message": str(e),
                "error_code": int(SwErrors.swUnknownError),
                "error_name": SwErrors.swUnknownError.name,
                "data": {},
            })
            _operation_payloads[operation_id] = payload
            return [TextContent(type="text", text=format_result(payload))]
        return [TextContent(type="text", text=f"[ERROR] {e}")]


# ============================================================================
# FIXED: Execute Python with stdout capture
# ============================================================================

def _execute_python_fixed(code: str) -> Dict:
    """
    Execute custom Python code with access to SolidWorks.
    FIXED: Now captures stdout, stderr, and 'result' variable.
    """
    try:
        if not sw_automation.is_connected:
            r = sw_automation.connect()
            if not r["success"]:
                return r
        
        import win32com.client
        import pythoncom
        import math
        import os as os_module
        
        # Prepare execution context with many useful objects
        exec_globals = {
            # SolidWorks objects
            'sw': sw_automation.app,
            'doc': sw_automation.app.ActiveDoc if sw_automation.app else None,
            'automation': sw_automation,
            
            # COM libraries
            'win32com': win32com,
            'pythoncom': pythoncom,
            
            # Standard libraries
            'math': math,
            'os': os_module,
            'json': json,
            
            # Result placeholder
            'result': None,
        }
        
        # Capture stdout and stderr
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()
        
        try:
            sys.stdout = captured_stdout
            sys.stderr = captured_stderr
            
            # Execute the code
            exec(code, exec_globals)
            
        finally:
            # Always restore stdout/stderr
            sys.stdout = old_stdout
            sys.stderr = old_stderr
        
        # Get captured output
        stdout_text = captured_stdout.getvalue()
        stderr_text = captured_stderr.getvalue()
        result_val = exec_globals.get('result')
        
        # Build response message
        message_parts = []
        
        if stdout_text:
            message_parts.append(f"=== Output ===\n{stdout_text.rstrip()}")
        
        if stderr_text:
            message_parts.append(f"=== Stderr ===\n{stderr_text.rstrip()}")
        
        if result_val is not None:
            message_parts.append(f"=== Result ===\n{result_val}")
        
        if not message_parts:
            message_parts.append("Code executed successfully (no output)")
        
        return {
            "success": True,
            "message": "\n\n".join(message_parts),
            "error_code": 0,
            "error_name": "swSuccess",
            "data": {
                "stdout": stdout_text,
                "stderr": stderr_text,
                "result": str(result_val) if result_val is not None else None
            }
        }
        
    except SyntaxError as e:
        return {
            "success": False,
            "message": f"Syntax error: {e}",
            "error_code": 999,
            "error_name": "swUnknownError",
            "data": {"error_type": "SyntaxError", "details": str(e)}
        }
        
    except Exception as e:
        tb = traceback.format_exc()
        return {
            "success": False,
            "message": f"Execution error: {e}\n\nTraceback:\n{tb}",
            "error_code": 999,
            "error_name": "swUnknownError",
            "data": {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": tb
            }
        }


# ============================================================================
# Main Entry Point
# ============================================================================

async def main():
    """Main entry point for MCP server"""
    logger.info("Starting SolidWorks MCP Server v4.0.0 (Fixed)...")
    logger.info(f"Log file: {LOG_FILE}")
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def run():
    """Run the server"""
    import asyncio
    asyncio.run(main())


if __name__ == "__main__":
    run()
