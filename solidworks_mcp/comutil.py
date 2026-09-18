"""
COM member access helpers for SolidWorks automation.

SolidWorks exposes some members as properties and others as methods, and the
distinction is not predictable from the type library. See docs/api-findings.md.
"""

import inspect
from typing import Any


def com(obj: Any, name: str, *args) -> Any:
    """
    Access a COM member regardless of whether it is a property or a method.

    win32com returns a bound method only when DISPATCH_PROPERTYGET failed;
    otherwise attribute access has already returned the value. Testing with
    callable() does not work, because CDispatch is always callable.

    Args:
        obj: COM object
        name: Member name
        *args: Arguments, if the member takes any

    Returns:
        The member value
    """
    value = getattr(obj, name)
    return value(*args) if inspect.ismethod(value) else value
