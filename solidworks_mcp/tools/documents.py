"""Document lifecycle tools: new, open, close, inspect open documents."""

from ..core.policy import OperationClass
from ..registry import tool


@tool(
    name="create_new_part",
    description="Create a new part document.",
    schema={"type": "object", "properties": {}, "required": []},
    operation_class=OperationClass.SESSION,
    postflight="bind",
)
def create_new_part(sw):
    return sw.create_new_part()


@tool(
    name="create_new_assembly",
    description="Create a new assembly document.",
    schema={"type": "object", "properties": {}, "required": []},
    operation_class=OperationClass.SESSION,
    postflight="bind",
)
def create_new_assembly(sw):
    return sw.create_new_assembly()


@tool(
    name="open_document",
    description="Open an existing SolidWorks document.",
    schema={
        "type": "object",
        "properties": {
            "filepath": {"type": "string", "description": "Path to file"}
        },
        "required": ["filepath"]
    },
    operation_class=OperationClass.SESSION,
    postflight="bind",
)
def open_document(sw, filepath=""):
    return sw.open_document(filepath)


@tool(
    name="close_document",
    description="Close the active document.",
    schema={
        "type": "object",
        "properties": {
            "save": {"type": "boolean", "default": False, "description": "Save before closing"}
        },
        "required": []
    },
    operation_class=OperationClass.MUTATE,
    postflight="none",
)
def close_document(sw, save=False):
    return sw.close_document(save)


@tool(
    name="get_document_info",
    description="Get information about the active document.",
    schema={"type": "object", "properties": {}, "required": []},
    operation_class=OperationClass.READ,
)
def get_document_info(sw):
    return sw.get_document_info()


@tool(
    name="list_open_documents",
    description="List all open documents.",
    schema={"type": "object", "properties": {}, "required": []},
    operation_class=OperationClass.READ,
)
def list_open_documents(sw):
    return sw.list_open_documents()
