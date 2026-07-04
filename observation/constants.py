"""UIA constants — wide property/pattern cache for gather-everything probe."""
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


def _collect_ids(suffix: str, prefix: str = "UIA_") -> tuple[list[int], dict[int, str]]:
    ids: list[int] = []
    names: dict[int, str] = {}
    for attr in sorted(dir(uia)):
        if not attr.startswith(prefix) or not attr.endswith(suffix):
            continue
        val = getattr(uia, attr, None)
        if not isinstance(val, int):
            continue
        ids.append(val)
        names[val] = attr.replace(prefix, "").replace(suffix, "")
    return ids, names


# Cache all published UIA properties + patterns (gather wide, filter later)
PROPERTY_IDS, PROPERTY_NAMES = _collect_ids("PropertyId")
PATTERN_IDS, PATTERN_NAMES = _collect_ids("PatternId")

# Fallback if typelib enumeration is empty
if not PROPERTY_IDS:
    PROPERTY_IDS = [
        _const("UIA_RuntimeIdPropertyId", 30000),
        _const("UIA_BoundingRectanglePropertyId", 30001),
        _const("UIA_ProcessIdPropertyId", 30002),
        _const("UIA_ControlTypePropertyId", 30003),
        _const("UIA_LocalizedControlTypePropertyId", 30004),
        _const("UIA_NamePropertyId", 30005),
        _const("UIA_AcceleratorKeyPropertyId", 30006),
        _const("UIA_AccessKeyPropertyId", 30007),
        _const("UIA_HasKeyboardFocusPropertyId", 30008),
        _const("UIA_IsKeyboardFocusablePropertyId", 30009),
        _const("UIA_IsEnabledPropertyId", 30010),
        _const("UIA_AutomationIdPropertyId", 30011),
        _const("UIA_ClassNamePropertyId", 30012),
        _const("UIA_HelpTextPropertyId", 30013),
        _const("UIA_ItemTypePropertyId", 30014),
        _const("UIA_IsOffscreenPropertyId", 30022),
        _const("UIA_OrientationPropertyId", 30023),
        _const("UIA_FrameworkIdPropertyId", 30024),
        _const("UIA_IsRequiredForFormPropertyId", 30025),
        _const("UIA_ItemStatusPropertyId", 30026),
        _const("UIA_NativeWindowHandlePropertyId", 30020),
        _const("UIA_IsContentElementPropertyId", 30017),
        _const("UIA_IsControlElementPropertyId", 30018),
        _const("UIA_IsPasswordPropertyId", 30019),
        _const("UIA_FullDescriptionPropertyId", 30159),
    ]
    PROPERTY_NAMES = {pid: f"Property_{pid}" for pid in PROPERTY_IDS}

if not PATTERN_IDS:
    PATTERN_IDS = [
        _const("UIA_ValuePatternId", 10002),
        _const("UIA_ScrollPatternId", 10004),
        _const("UIA_TextPatternId", 10014),
        _const("UIA_LegacyIAccessiblePatternId", 10018),
        _const("UIA_WindowPatternId", 10005),
        _const("UIA_InvokePatternId", 10000),
        _const("UIA_SelectionPatternId", 10001),
        _const("UIA_GridPatternId", 10007),
        _const("UIA_TablePatternId", 10012),
    ]
    PATTERN_NAMES = {pid: f"Pattern_{pid}" for pid in PATTERN_IDS}

# Fast lookup for harvest shortcuts
PID_NAME = _const("UIA_NamePropertyId", 30005)
PID_CONTROL_TYPE = _const("UIA_ControlTypePropertyId", 30003)
PID_BOUNDING_RECT = _const("UIA_BoundingRectanglePropertyId", 30001)
PID_AUTOMATION_ID = _const("UIA_AutomationIdPropertyId", 30011)
PID_CLASS_NAME = _const("UIA_ClassNamePropertyId", 30012)
PID_HWND = _const("UIA_NativeWindowHandlePropertyId", 30020)
PID_ENABLED = _const("UIA_IsEnabledPropertyId", 30010)
PID_KEYBOARD_FOCUS = _const("UIA_HasKeyboardFocusPropertyId", 30008)
PID_OFFSCREEN = _const("UIA_IsOffscreenPropertyId", 30022)
PID_FRAMEWORK = _const("UIA_FrameworkIdPropertyId", 30024)
PID_RUNTIME_ID = _const("UIA_RuntimeIdPropertyId", 30000)

PID_TEXT = _const("UIA_TextPatternId", 10014)
PID_VALUE = _const("UIA_ValuePatternId", 10002)
PID_LEGACY = _const("UIA_LegacyIAccessiblePatternId", 10018)

CONTROL_TYPE_NAMES: dict[int, str] = {}
for attr in dir(uia):
    if attr.startswith("UIA_") and attr.endswith("ControlTypeId"):
        val = getattr(uia, attr, None)
        if isinstance(val, int):
            label = attr.replace("UIA_", "").replace("ControlTypeId", "")
            CONTROL_TYPE_NAMES[val] = label


def control_type_name(control_type_id: int) -> str:
    return CONTROL_TYPE_NAMES.get(control_type_id, f"ControlType({control_type_id})")