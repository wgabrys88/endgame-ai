"""Minimal UIA constants loader — cache API only, no desktop.py coupling."""
from __future__ import annotations

import importlib
import sys
from typing import Any

import comtypes
import comtypes.client


def load_uia() -> Any:
    try:
        comtypes.client.GetModule("UIAutomationCore.dll")
        return importlib.import_module("comtypes.gen.UIAutomationClient")
    except ImportError as exc:
        if "Typelib different than module" not in str(exc):
            raise
        for name in list(sys.modules):
            if name.startswith("comtypes.gen.UIAutomation"):
                sys.modules.pop(name, None)
        comtypes.client.GetModule("UIAutomationCore.dll")
        return importlib.import_module("comtypes.gen.UIAutomationClient")


comtypes.CoInitialize()

uia = load_uia()


def _const(name: str, default: int) -> int:
    try:
        return int(getattr(uia, name))
    except Exception:
        return default


# TreeScope
TreeScope_Element = _const("TreeScope_Element", 1)
TreeScope_Children = _const("TreeScope_Children", 2)
TreeScope_Descendants = _const("TreeScope_Descendants", 4)
TreeScope_Subtree = _const("TreeScope_Subtree", 7)

# Properties to cache (small intentional set — gather wide, filter later)
PROPERTY_IDS = [
    _const("UIA_NamePropertyId", 30005),
    _const("UIA_ControlTypePropertyId", 30003),
    _const("UIA_BoundingRectanglePropertyId", 30001),
    _const("UIA_AutomationIdPropertyId", 30011),
    _const("UIA_ClassNamePropertyId", 30012),
    _const("UIA_NativeWindowHandlePropertyId", 30020),
    _const("UIA_IsEnabledPropertyId", 30010),
    _const("UIA_HasKeyboardFocusPropertyId", 30008),
    _const("UIA_IsOffscreenPropertyId", 30022),
    _const("UIA_FrameworkIdPropertyId", 30024),
    _const("UIA_ProcessIdPropertyId", 30002),
    _const("UIA_RuntimeIdPropertyId", 30000),
]

# Patterns to cache
PATTERN_IDS = [
    _const("UIA_TextPatternId", 10014),
    _const("UIA_ValuePatternId", 10002),
    _const("UIA_ScrollPatternId", 10004),
    _const("UIA_LegacyIAccessiblePatternId", 10018),
]

CONTROL_TYPE_NAMES: dict[int, str] = {}
for attr in dir(uia):
    if attr.startswith("UIA_") and attr.endswith("ControlTypeId"):
        val = getattr(uia, attr, None)
        if isinstance(val, int):
            label = attr.replace("UIA_", "").replace("ControlTypeId", "")
            CONTROL_TYPE_NAMES[val] = label


def control_type_name(control_type_id: int) -> str:
    return CONTROL_TYPE_NAMES.get(control_type_id, f"ControlType({control_type_id})")