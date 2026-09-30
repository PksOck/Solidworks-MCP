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

import json
import base64
import hashlib
import logging
import traceback
from collections import OrderedDict
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
from .config import get_config
from .core.contracts import OperationError, OperationResult, OperationStatus
from .core.evidence import OperationJournal
from . import catalog
from .com_worker import run_com
from .registry import execute
from .knowledge import library as modeling_guidance

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
_MAX_REMEMBERED = 1000
_operation_payloads: "OrderedDict[str, Dict]" = OrderedDict()


def _remember_payload(operation_id: str, payload: Dict) -> None:
    _operation_payloads[operation_id] = payload
    while len(_operation_payloads) > _MAX_REMEMBERED:
        _operation_payloads.popitem(last=False)


# ============================================================================
# Tool Definitions
# ============================================================================

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List advertised SolidWorks tools"""
    return catalog.advertised_tools()


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


@server.read_resource()
async def read_modeling_resource(uri) -> list[ReadResourceContents]:
    topic = modeling_guidance.topic_for_uri(str(uri))
    payload = modeling_guidance.read_topic(topic, catalog.advertised_tool_names())
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

def _replay_payload(operation_id: str, replay: OperationResult) -> Dict:
    payload = _operation_payloads.get(operation_id)
    if payload is not None:
        return payload
    return replay.to_dict(legacy={
        "success": replay.status is OperationStatus.COMPLETED,
        "message": "Operation outcome is already recorded.",
        "error_code": 0 if replay.status is OperationStatus.COMPLETED else 1,
        "error_name": replay.status.value,
        "data": dict(replay.data),
    })


def _record(operation_id: str, execution) -> Dict:
    """Journal one execution and return the payload sent to the client."""
    result = execution.result
    detail = dict(result.get("data", {}))
    if result.get("success"):
        operation_result = OperationResult(
            operation_id=operation_id,
            status=OperationStatus.COMPLETED,
            target_before=execution.target_before,
            target_after=execution.target_after,
            data=detail,
        )
    else:
        operation_result = OperationResult(
            operation_id=operation_id,
            status=OperationStatus.FAILED,
            target_before=execution.target_before,
            target_after=execution.target_after,
            data=detail,
            errors=(OperationError(
                code=detail.get("code", result.get("error_name", "COM_ERROR")),
                message=result.get("message", "Operation failed."),
                retryable=bool(detail.get("retryable", False)),
            ),),
        )
    operation_journal.record(operation_result)
    payload = operation_result.to_dict(legacy=result)
    _remember_payload(operation_id, payload)
    return payload


def _record_exception(operation_id: str, error: Exception) -> Dict:
    failed = OperationResult.failed(operation_id, None, str(error))
    operation_journal.record(failed)
    payload = failed.to_dict(legacy={
        "success": False,
        "message": str(error),
        "error_code": int(SwErrors.swUnknownError),
        "error_name": SwErrors.swUnknownError.name,
        "data": {},
    })
    _remember_payload(operation_id, payload)
    return payload


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent | ImageContent]:
    """Handle MCP tool calls: replay, execute once, record."""
    arguments = dict(arguments or {})
    operation_id = arguments.pop("operation_id", None) or str(uuid4())
    replay = operation_journal.reserve(operation_id)
    if replay is not None:
        return _content_for_result(_replay_payload(operation_id, replay))
    operation_journal.mark_running(operation_id)
    logger.info(f"Tool: {name}, Args: {arguments}")
    try:
        execution = await run_com(execute, name, sw_automation, arguments)
        payload = _record(operation_id, execution)
    except Exception as error:
        logger.error(f"Tool error: {error}\n{traceback.format_exc()}")
        payload = _record_exception(operation_id, error)
        return [TextContent(type="text", text=format_result(payload))]
    logger.info(f"Result: success={payload['success']}")
    return _content_for_result(payload)


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
