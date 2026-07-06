from __future__ import annotations

import ctypes
import importlib
import json
import pathlib
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import Any, Iterable

import comtypes
import comtypes.client

ROOT = pathlib.Path(__file__).resolve().parent
user32 = ctypes.windll.user32

CLICK = {
    "Button", "Calendar", "CheckBox", "Hyperlink", "ListItem", "MenuItem",
    "RadioButton", "Tab", "TabItem", "TreeItem", "DataItem", "SplitButton",
}
WRITE = {"Edit", "ComboBox", "Spinner", "Document"}
READ = {"Text", "ListItem"}
SCROLL = {"List", "ScrollBar", "Slider", "Tree", "DataGrid"}
CONTAINER_ROLES = {
    "Pane", "Document", "Window", "Group", "List", "Tree", "DataGrid",
    "Tab", "Menu", "ToolBar", "Table", "MenuBar", "SplitPane", "ScrollViewer",
}

JUNK_ROLES = {
    "TitleBar", "ScrollBar", "StatusBar", "ProgressBar", "Separator",
    "ToolTip", "Image", "Custom", "Header", "HeaderItem",
}

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

PROPERTY_IDS, PROPERTY_NAMES = _collect_ids("PropertyId")
PATTERN_IDS, PATTERN_NAMES = _collect_ids("PatternId")

if not PROPERTY_IDS:
    PROPERTY_IDS = [
        _const("UIA_RuntimeIdPropertyId", 30000),
        _const("UIA_BoundingRectanglePropertyId", 30001),
        _const("UIA_ControlTypePropertyId", 30003),
        _const("UIA_NamePropertyId", 30005),
        _const("UIA_AutomationIdPropertyId", 30011),
        _const("UIA_ClassNamePropertyId", 30012),
        _const("UIA_IsEnabledPropertyId", 30010),
        _const("UIA_IsOffscreenPropertyId", 30022),
        _const("UIA_FrameworkIdPropertyId", 30024),
        _const("UIA_NativeWindowHandlePropertyId", 30020),
        _const("UIA_IsKeyboardFocusablePropertyId", 30008),
        _const("UIA_HasKeyboardFocusPropertyId", 30009),
        _const("UIA_IsContentElementPropertyId", 30015),
        _const("UIA_IsControlElementPropertyId", 30016),
        _const("UIA_ProviderDescriptionPropertyId", 30025),
    ]
    PROPERTY_NAMES = {pid: f"Property_{pid}" for pid in PROPERTY_IDS}

if not PATTERN_IDS:
    PATTERN_IDS = [
        _const("UIA_ValuePatternId", 10002),
        _const("UIA_TextPatternId", 10014),
        _const("UIA_LegacyIAccessiblePatternId", 10018),
        _const("UIA_InvokePatternId", 10000),
        _const("UIA_ScrollPatternId", 10004),
        _const("UIA_WindowPatternId", 10009),
    ]
    PATTERN_NAMES = {pid: f"Pattern_{pid}" for pid in PATTERN_IDS}

PID_NAME = _const("UIA_NamePropertyId", 30005)
PID_CONTROL_TYPE = _const("UIA_ControlTypePropertyId", 30003)
PID_BOUNDING_RECT = _const("UIA_BoundingRectanglePropertyId", 30001)
PID_AUTOMATION_ID = _const("UIA_AutomationIdPropertyId", 30011)
PID_CLASS_NAME = _const("UIA_ClassNamePropertyId", 30012)
PID_HWND = _const("UIA_NativeWindowHandlePropertyId", 30020)
PID_ENABLED = _const("UIA_IsEnabledPropertyId", 30010)
PID_OFFSCREEN = _const("UIA_IsOffscreenPropertyId", 30022)
PID_FRAMEWORK = _const("UIA_FrameworkIdPropertyId", 30024)
PID_RUNTIME_ID = _const("UIA_RuntimeIdPropertyId", 30000)
PID_KEYBOARD_FOCUSABLE = _const("UIA_IsKeyboardFocusablePropertyId", 30008)
PID_HAS_KEYBOARD_FOCUS = _const("UIA_HasKeyboardFocusPropertyId", 30009)
PID_CONTENT_ELEMENT = _const("UIA_IsContentElementPropertyId", 30015)
PID_CONTROL_ELEMENT = _const("UIA_IsControlElementPropertyId", 30016)

SCAN_DEFAULT_PROPERTY_IDS = [
    PID_RUNTIME_ID,
    PID_BOUNDING_RECT,
    PID_CONTROL_TYPE,
    PID_NAME,
    PID_AUTOMATION_ID,
    PID_CLASS_NAME,
    PID_ENABLED,
    PID_OFFSCREEN,
    PID_HWND,
    PID_FRAMEWORK,
    PID_KEYBOARD_FOCUSABLE,
    PID_HAS_KEYBOARD_FOCUS,
    PID_CONTENT_ELEMENT,
    PID_CONTROL_ELEMENT,
    _const("UIA_HelpTextPropertyId", 30013),
    _const("UIA_FullDescriptionPropertyId", 30159),
    _const("UIA_ItemStatusPropertyId", 30026),
    _const("UIA_AcceleratorKeyPropertyId", 30006),
    _const("UIA_AccessKeyPropertyId", 30007),
]
SCAN_DEFAULT_PATTERN_IDS = [
    _const("UIA_ValuePatternId", 10002),
    _const("UIA_LegacyIAccessiblePatternId", 10018),
    _const("UIA_InvokePatternId", 10000),
    _const("UIA_ScrollPatternId", 10004),
    _const("UIA_WindowPatternId", 10009),
]

CONTROL_TYPE_NAMES: dict[int, str] = {}
for attr in dir(uia):
    if attr.startswith("UIA_") and attr.endswith("ControlTypeId"):
        val = getattr(uia, attr, None)
        if isinstance(val, int):
            CONTROL_TYPE_NAMES[val] = attr.replace("UIA_", "").replace("ControlTypeId", "")

def control_type_name(control_type_id: int) -> str:
    return CONTROL_TYPE_NAMES.get(control_type_id, f"ControlType({control_type_id})")

def _scan_settings(config: dict[str, Any]) -> dict[str, Any]:
    out = dict(config.get("scan") or {})
    out.update(config.get("depth") or {})
    return out

def _action_for_role(role: str, class_name: str = "") -> str:
    if role in CLICK:
        return "click"
    if role in WRITE:
        return "write"
    if role in READ:
        return "read"
    if role == "Pane" and class_name == "Scintilla":
        return "write"
    if role in SCROLL:
        return "scroll"
    return ""

@dataclass
class CachedNode:
    id: str
    role: str
    name: str
    automation_id: str = ""
    class_name: str = ""
    hwnd: int = 0
    framework_id: str = ""
    px: int = 0
    py: int = 0
    rect: dict[str, int] = field(default_factory=dict)
    enabled: bool = True
    offscreen: bool = False
    runtime_id: list[int] = field(default_factory=list)
    text_full: str | None = None
    value: str | None = None
    patterns: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    pattern_payloads: dict[str, Any] = field(default_factory=dict)
    text_sources: dict[str, str] = field(default_factory=dict)
    source_probe: tuple[int, int] | None = None
    z_order: int = 0
    depth: int = 0
    parent_id: str = ""
    has_focus: bool = False
    is_keyboard_focusable: bool = False
    is_content_element: bool = False
    is_control_element: bool = False

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "role": self.role,
            "name": self.name,
            "hwnd": self.hwnd,
            "px": self.px,
            "py": self.py,
            "rect": self.rect,
            "enabled": self.enabled,
            "offscreen": self.offscreen,
            "patterns": self.patterns,
            "runtime_id": self.runtime_id,
            "z_order": self.z_order,
            "depth": self.depth,
            "parent_id": self.parent_id,
            "has_focus": self.has_focus,
            "is_keyboard_focusable": self.is_keyboard_focusable,
            "is_content_element": self.is_content_element,
            "is_control_element": self.is_control_element,
        }
        for key, val in (
            ("automation_id", self.automation_id),
            ("class_name", self.class_name),
            ("framework_id", self.framework_id),
            ("text_full", self.text_full),
            ("value", self.value),
            ("text_sources", self.text_sources),
            ("properties", self.properties),
            ("pattern_payloads", self.pattern_payloads),
            ("source_probe", list(self.source_probe) if self.source_probe else None),
        ):
            if val:
                out[key] = val
        return out


class UiaVariant:

    @staticmethod
    def to_int(v: Any) -> int:
        if v is None:
            return 0
        if hasattr(v, "value"):
            v = v.value
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def to_str(v: Any) -> str:
        if v is None:
            return ""
        if hasattr(v, "value"):
            v = v.value
        return "" if v is None else str(v)

    @staticmethod
    def to_bool(v: Any) -> bool:
        if v is None:
            return False
        if hasattr(v, "value"):
            v = v.value
        return bool(v)

    @staticmethod
    def to_rect(v: Any) -> dict[str, int]:
        if v is None:
            return {"left": 0, "top": 0, "right": 0, "bottom": 0}
        try:
            val = v.value if hasattr(v, "value") else v
            if isinstance(val, (tuple, list)) and len(val) >= 4:
                left, top, third, fourth = (float(x) for x in val[:4])
                left_i, top_i = int(left), int(top)
                if third > left or fourth > top:
                    right_i, bottom_i = int(third), int(fourth)
                else:
                    right_i, bottom_i = left_i + int(third), top_i + int(fourth)
                return {"left": left_i, "top": top_i, "right": right_i, "bottom": bottom_i}
            if hasattr(val, "left"):
                return {
                    "left": int(val.left),
                    "top": int(val.top),
                    "right": int(val.right),
                    "bottom": int(val.bottom),
                }
        except Exception:
            pass
        return {"left": 0, "top": 0, "right": 0, "bottom": 0}

    @staticmethod
    def to_runtime_id(v: Any) -> list[int]:
        if v is None:
            return []
        try:
            val = v.value if hasattr(v, "value") else v
            if val is None:
                return []
            return [int(x) for x in list(val)]
        except Exception:
            return []

    @staticmethod
    def serialize(v: Any) -> Any:
        if v is None:
            return None
        if hasattr(v, "value"):
            v = v.value
        if isinstance(v, (str, int, float, bool)):
            return v
        if isinstance(v, (tuple, list)):
            return [UiaVariant.serialize(x) for x in v]
        if isinstance(v, dict):
            return {str(k): UiaVariant.serialize(val) for k, val in v.items()}
        rect = UiaVariant.to_rect(v)
        if rect["right"] > rect["left"] and rect["bottom"] > rect["top"]:
            return rect
        try:
            if hasattr(v, "__iter__") and not isinstance(v, (str, bytes)):
                return [UiaVariant.serialize(x) for x in list(v)]
        except Exception:
            pass
        s = str(v).strip()
        return s if s else None


def _node_id(runtime_id: list[int], hwnd: int, rect: dict[str, int]) -> str:
    if runtime_id:
        return "e_" + "_".join(map(str, runtime_id))
    return f"e_{hwnd}_{rect['left']}_{rect['top']}"


def _make_short_id(window_idx: int, elem_idx: int, child_idx: int = 0) -> str:
    if window_idx == 0:
        if child_idx > 0:
            return f"W0C{child_idx}"
        return "W0"
    if elem_idx > 0:
        if child_idx > 0:
            return f"W{window_idx}E{elem_idx}C{child_idx}"
        return f"W{window_idx}E{elem_idx}"
    return f"W{window_idx}"


def _get_cached(element: Any, prop_id: int) -> Any:
    try:
        return element.GetCachedPropertyValue(prop_id)
    except Exception:
        return None


def _get_current(element: Any, prop_id: int) -> Any:
    try:
        return element.GetCurrentPropertyValue(prop_id)
    except Exception:
        return None


def _harvest_properties(element: Any, property_ids: list[int]) -> dict[str, Any]:
    props: dict[str, Any] = {}
    for pid in property_ids:
        label = PROPERTY_NAMES.get(pid, f"Property_{pid}")
        cached = UiaVariant.serialize(_get_cached(element, pid))
        if cached is not None and cached != "" and cached != []:
            props[label] = cached
            continue
        current = UiaVariant.serialize(_get_current(element, pid))
        if current is not None and current != "" and current != []:
            props[f"{label}_current"] = current
    return props


def _get_pattern(element: Any, pattern_id: int) -> tuple[Any | None, str]:
    try:
        return element.GetCachedPattern(pattern_id), "cached"
    except Exception:
        pass
    try:
        return element.GetCurrentPattern(pattern_id), "current"
    except Exception:
        pass
    return None, ""


def _safe_attr(obj: Any, name: str) -> Any:
    try:
        return getattr(obj, name)
    except Exception:
        return None


def _extract_pattern_payload(pattern: Any, label: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if pattern is None:
        return out
    if label == "Text":
        doc = _safe_attr(pattern, "DocumentRange")
        if doc is not None:
            try:
                text = doc.GetText(-1)
                if text and str(text).strip():
                    out["DocumentRange"] = str(text)
            except Exception:
                pass
        try:
            ranges = pattern.GetVisibleRanges()
            if ranges is not None:
                texts = []
                try:
                    length = int(ranges.Length)
                except Exception:
                    length = 0
                for i in range(length):
                    try:
                        t = ranges.GetElement(i).GetText(-1)
                        if t and str(t).strip():
                            texts.append(str(t))
                    except Exception:
                        continue
                if texts:
                    out["VisibleRanges"] = "\n".join(texts)
        except Exception:
            pass
    elif label == "Value":
        for key in ("Value", "IsReadOnly"):
            val = _safe_attr(pattern, key)
            if val is not None:
                out[key] = UiaVariant.serialize(val)
    elif label == "LegacyIAccessible":
        for key in ("Name", "Value", "Description", "Role", "State", "DefaultAction", "Help", "KeyboardShortcut", "ChildId"):
            val = _safe_attr(pattern, key)
            if val is not None and str(val).strip() not in ("", "0"):
                out[key] = UiaVariant.serialize(val)
    elif label == "Scroll":
        for key in ("HorizontallyScrollable", "HorizontalScrollPercent", "HorizontalViewSize",
                    "VerticallyScrollable", "VerticalScrollPercent", "VerticalViewSize"):
            val = _safe_attr(pattern, key)
            if val is not None:
                out[key] = UiaVariant.serialize(val)
    elif label == "Window":
        for key in ("CanMaximize", "CanMinimize", "IsModal", "IsTopmost", "WindowInteractionState", "WindowVisualState"):
            val = _safe_attr(pattern, key)
            if val is not None:
                out[key] = UiaVariant.serialize(val)
    elif label in ("Invoke", "Selection"):
        out["available"] = True
    else:
        out["available"] = True
    return out


def _harvest_patterns(element: Any, pattern_ids: list[int]) -> tuple[list[str], dict[str, Any]]:
    names: list[str] = []
    payloads: dict[str, Any] = {}
    for pid in pattern_ids:
        label = PATTERN_NAMES.get(pid, f"Pattern_{pid}")
        pattern, source = _get_pattern(element, pid)
        if pattern is None:
            continue
        names.append(label)
        payload = _extract_pattern_payload(pattern, label)
        payload["_source"] = source
        payloads[label] = payload if payload else {"_source": source, "available": True}
    return names, payloads


def _collect_text_sources(name: str, properties: dict[str, Any], pattern_payloads: dict[str, Any]) -> tuple[dict[str, str], str | None, str | None]:
    sources: dict[str, str] = {}
    if name and name.strip():
        sources["name"] = name.strip()
    for key in ("HelpText", "FullDescription", "ItemStatus", "AcceleratorKey", "AccessKey"):
        val = properties.get(key)
        if isinstance(val, str) and val.strip():
            sources[key.lower()] = val.strip()
    text_full: str | None = None
    value: str | None = None
    text_payload = pattern_payloads.get("Text", {})
    for key in ("DocumentRange", "VisibleRanges"):
        val = text_payload.get(key)
        if isinstance(val, str) and val.strip():
            sources[f"text_{key.lower()}"] = val.strip()
            if not text_full or len(val) > len(text_full):
                text_full = val.strip()
    val = (pattern_payloads.get("Value", {}) or {}).get("Value")
    if isinstance(val, str) and val.strip():
        sources["value_pattern"] = val.strip()
        value = val.strip()
    legacy = pattern_payloads.get("LegacyIAccessible", {})
    for key in ("Value", "Name", "Description"):
        val = legacy.get(key)
        if isinstance(val, str) and val.strip():
            sources[f"legacy_{key.lower()}"] = val.strip()
            if key == "Value" and not value:
                value = val.strip()
            if not text_full or len(val) > len(text_full):
                if key in ("Value", "Description") or (key == "Name" and len(val) > 20):
                    text_full = val.strip()
    if not text_full and name and len(name) > 1:
        text_full = name.strip()
    return sources, text_full, value


def _true_condition(automation: Any) -> Any:
    try:
        return automation.CreateTrueCondition()
    except Exception:
        return automation.TrueCondition


class UiaScanner:

    def __init__(self, desktop, config):
        self.desktop = desktop
        self.scan_cfg = _scan_settings(config)
        self.automation = desktop.automation
        self.property_ids = _scan_property_ids(self.scan_cfg)
        self.pattern_ids = _scan_pattern_ids(self.scan_cfg)
        self.cache_request = self._build_cache_request()
        self.hit_cache_request = self._build_hit_cache_request()
        self._z_counter = 0

    def _build_cache_request(self):
        req = self.automation.CreateCacheRequest()
        req.TreeScope = TreeScope_Subtree
        for prop_id in self.property_ids:
            req.AddProperty(prop_id)
        for pattern_id in self.pattern_ids:
            req.AddPattern(pattern_id)
        return req

    def _build_hit_cache_request(self):
        req = self.automation.CreateCacheRequest()
        req.TreeScope = TreeScope_Element
        for prop_id in (PID_RUNTIME_ID, PID_BOUNDING_RECT, PID_CONTROL_TYPE, PID_HWND):
            req.AddProperty(prop_id)
        return req

    def _next_z(self) -> int:
        self._z_counter += 1
        return self._z_counter

    def element_to_node(self, element, probe_xy=None, parent_id="", depth=0):
        try:
            rect = UiaVariant.to_rect(_get_cached(element, PID_BOUNDING_RECT))
            if rect["right"] <= rect["left"] or rect["bottom"] <= rect["top"]:
                rect = UiaVariant.to_rect(_get_current(element, PID_BOUNDING_RECT))
            if rect["right"] <= rect["left"] or rect["bottom"] <= rect["top"]:
                return None
            runtime_id = UiaVariant.to_runtime_id(_get_cached(element, PID_RUNTIME_ID)) or UiaVariant.to_runtime_id(_get_current(element, PID_RUNTIME_ID))
            hwnd = UiaVariant.to_int(_get_cached(element, PID_HWND))
            role_id = UiaVariant.to_int(_get_cached(element, PID_CONTROL_TYPE))
            name = UiaVariant.to_str(_get_cached(element, PID_NAME)) or UiaVariant.to_str(_get_current(element, PID_NAME))
            
            properties = _harvest_properties(element, self.property_ids)
            patterns, pattern_payloads = _harvest_patterns(element, self.pattern_ids)
            text_sources, text_full, value = _collect_text_sources(name, properties, pattern_payloads)
            
            role = control_type_name(role_id)
            
            has_focus = UiaVariant.to_bool(_get_cached(element, PID_HAS_KEYBOARD_FOCUS)) or UiaVariant.to_bool(_get_current(element, PID_HAS_KEYBOARD_FOCUS))
            is_keyboard_focusable = UiaVariant.to_bool(_get_cached(element, PID_KEYBOARD_FOCUSABLE)) or UiaVariant.to_bool(_get_current(element, PID_KEYBOARD_FOCUSABLE))
            is_content_element = UiaVariant.to_bool(_get_cached(element, PID_CONTENT_ELEMENT)) or UiaVariant.to_bool(_get_current(element, PID_CONTENT_ELEMENT))
            is_control_element = UiaVariant.to_bool(_get_cached(element, PID_CONTROL_ELEMENT)) or UiaVariant.to_bool(_get_current(element, PID_CONTROL_ELEMENT))
            
            z_order = self._next_z()
            
            return CachedNode(
                id=_node_id(runtime_id, hwnd, rect),
                role=role,
                name=name,
                automation_id=UiaVariant.to_str(_get_cached(element, PID_AUTOMATION_ID)),
                class_name=UiaVariant.to_str(_get_cached(element, PID_CLASS_NAME)),
                hwnd=hwnd,
                framework_id=UiaVariant.to_str(_get_cached(element, PID_FRAMEWORK)),
                px=(rect["left"] + rect["right"]) // 2,
                py=(rect["top"] + rect["bottom"]) // 2,
                rect=rect,
                enabled=UiaVariant.to_bool(_get_cached(element, PID_ENABLED)),
                offscreen=UiaVariant.to_bool(_get_cached(element, PID_OFFSCREEN)),
                runtime_id=runtime_id,
                text_full=text_full,
                value=value,
                patterns=patterns,
                properties=properties,
                pattern_payloads=pattern_payloads,
                text_sources=text_sources,
                source_probe=probe_xy,
                z_order=z_order,
                depth=depth,
                parent_id=parent_id,
                has_focus=has_focus,
                is_keyboard_focusable=is_keyboard_focusable,
                is_content_element=is_content_element,
                is_control_element=is_control_element,
            )
        except Exception:
            return None

    def harvest_subtree(self, root_element, *, probe_xy, max_nodes, parent_id="", depth=0):
        nodes = []
        seen = set()

        def get_node_id(el):
            rid = UiaVariant.to_runtime_id(_get_cached(el, PID_RUNTIME_ID)) or UiaVariant.to_runtime_id(_get_current(el, PID_RUNTIME_ID))
            hwnd = UiaVariant.to_int(_get_cached(el, PID_HWND))
            rect = UiaVariant.to_rect(_get_cached(el, PID_BOUNDING_RECT))
            if rect["right"] <= rect["left"] or rect["bottom"] <= rect["top"]:
                rect = UiaVariant.to_rect(_get_current(el, PID_BOUNDING_RECT))
            return _node_id(rid, hwnd, rect)

        def add_element(el, pid="", d=0):
            if len(nodes) >= max_nodes:
                return
            node = self.element_to_node(el, probe_xy=probe_xy, parent_id=pid, depth=d)
            if node is None or node.id in seen:
                return
            seen.add(node.id)
            nodes.append(node)
            return node

        root_node = add_element(root_element, parent_id, depth)
        root_nid = root_node.id if root_node else ""
        
        try:
            arr = root_element.FindAllBuildCache(TreeScope_Descendants, _true_condition(self.automation), self.cache_request)
            if arr is not None:
                try:
                    length = int(arr.Length)
                except Exception:
                    length = 0
                for i in range(length):
                    if len(nodes) >= max_nodes:
                        break
                    try:
                        el = arr.GetElement(i)
                        nid = get_node_id(el)
                        pid = parent_id
                        if i > 0:
                            prev = arr.GetElement(i - 1)
                            prev_nid = get_node_id(prev)
                            pid = prev_nid
                        add_element(el, pid, depth + 1)
                    except Exception:
                        continue
        except Exception:
            pass
        return nodes

    def probe(self, x, y, *, delay_ms, max_subtree_nodes, saturated_hits, index):
        user32.SetCursorPos(int(x), int(y))
        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)
        pt = wintypes.POINT(int(x), int(y))
        try:
            root = self.automation.ElementFromPointBuildCache(pt, self.hit_cache_request)
        except Exception:
            root = self.automation.ElementFromPoint(pt)
        if root is None:
            return [], None, False
        hit_key, role = _hit_key_from_element(root)
        if hit_key in saturated_hits:
            return [], hit_key, True
        if hit_key in index and role not in CONTAINER_ROLES:
            return [], hit_key, True
        return self.harvest_subtree(root, probe_xy=(x, y), max_nodes=max_subtree_nodes), hit_key, False


def _scan_property_ids(scan_cfg: dict[str, Any]) -> list[int]:
    ids = scan_cfg.get("property_ids")
    return [int(x) for x in ids] if ids else list(SCAN_DEFAULT_PROPERTY_IDS)


def _scan_pattern_ids(scan_cfg: dict[str, Any]) -> list[int]:
    ids = scan_cfg.get("pattern_ids")
    return [int(x) for x in ids] if ids else list(SCAN_DEFAULT_PATTERN_IDS)


class WindowZOrder:
    def __init__(self):
        self.windows: list[dict] = []
        self._hwnd_to_z: dict[int, int] = {}
    
    def add_window(self, hwnd: int, title: str, rect: dict, z_index: int):
        self.windows.append({
            "hwnd": hwnd,
            "title": title,
            "rect": rect,
            "z_index": z_index,
        })
        self._hwnd_to_z[hwnd] = z_index
    
    def get_z_order(self, hwnd: int) -> int:
        return self._hwnd_to_z.get(hwnd, 0)
    
    def sort_by_z(self):
        self.windows.sort(key=lambda w: w["z_index"])


def get_window_z_order() -> WindowZOrder:
    z_order = WindowZOrder()
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    
    windows = []
    
    def callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)) or rect.right <= rect.left or rect.bottom <= rect.top:
            return True
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        windows.append({
            "hwnd": int(hwnd),
            "title": title.value,
            "rect": {"left": rect.left, "top": rect.top, "right": rect.right, "bottom": rect.bottom},
        })
        return True
    
    try:
        user32.EnumWindows(EnumWindowsProc(callback), 0)
    except Exception:
        pass
    
    for i, w in enumerate(windows):
        z_order.add_window(w["hwnd"], w["title"], w["rect"], i)
    
    z_order.sort_by_z()
    return z_order


def scan(desktop, config):
    scan_cfg = _scan_settings(config)
    stale_merge_stop = int(scan_cfg.get("stale_merge_stop", 12))
    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)
    step_px = int(scan_cfg.get("step_px", 96))
    delay_ms = int(scan_cfg.get("delay_ms", 0))
    max_subtree = int(scan_cfg.get("max_subtree_nodes_per_point", 5000))
    max_total = int(scan_cfg.get("max_total_nodes", 20000))
    max_probes = scan_cfg.get("max_probe_points")
    points = _r2_points(sw, sh, step_px=step_px)

    z_order = get_window_z_order()
    index = {}
    saturated_hits = set()
    probes = 0
    probes_skipped = 0
    probes_harvested = 0
    subtree_seen = 0
    consecutive_no_add = 0
    early_stop = None
    t0 = time.time()
    saved = wintypes.POINT()
    had_cursor = bool(user32.GetCursorPos(ctypes.byref(saved)))
    try:
        for x, y in points:
            if max_probes is not None and probes >= int(max_probes):
                break
            if len(index) >= max_total:
                early_stop = "max_total"
                break
            probes += 1
            nodes, hit_key, skipped = UiaScanner(desktop, config).probe(
                x,
                y,
                delay_ms=delay_ms,
                max_subtree_nodes=max_subtree,
                saturated_hits=saturated_hits,
                index=index,
            )
            if skipped:
                probes_skipped += 1
                continue
            probes_harvested += 1
            subtree_seen += len(nodes)
            added = _merge_nodes(index, nodes)
            if hit_key and (added == 0 or len(nodes) >= max_subtree):
                saturated_hits.add(hit_key)
            if added == 0:
                consecutive_no_add += 1
                if consecutive_no_add >= stale_merge_stop and len(index) > 0:
                    early_stop = "stale_merges"
                    break
            else:
                consecutive_no_add = 0
    finally:
        if had_cursor:
            try:
                user32.SetCursorPos(saved.x, saved.y)
            except Exception:
                pass

    nodes = list(index.values())
    return {
        "nodes": nodes,
        "screen": {"width": sw, "height": sh},
        "windows": desktop.get_window_tokens(),
        "window_z_order": [w["hwnd"] for w in z_order.windows],
        "scan": {
            "method": "hover_cache",
            "pattern": "r2",
            "step_px": step_px,
            "stats": {
                "probes": probes,
                "probes_harvested": probes_harvested,
                "probes_skipped": probes_skipped,
                "saturated_hits": len(saturated_hits),
                "early_stop": early_stop,
                "subtree_nodes_seen": subtree_seen,
                "unique_nodes": len(nodes),
                "nodes_with_text": sum(1 for n in nodes if n.text_full),
                "elapsed_s": round(time.time() - t0, 3),
            },
        },
    }


def gather(desktop, config):
    return scan(desktop, config)


def _hit_key_from_element(element: Any) -> tuple[str, str]:
    runtime_id = UiaVariant.to_runtime_id(_get_cached(element, PID_RUNTIME_ID)) or UiaVariant.to_runtime_id(_get_current(element, PID_RUNTIME_ID))
    rect = UiaVariant.to_rect(_get_cached(element, PID_BOUNDING_RECT))
    if rect["right"] <= rect["left"] or rect["bottom"] <= rect["top"]:
        rect = UiaVariant.to_rect(_get_current(element, PID_BOUNDING_RECT))
    hwnd = UiaVariant.to_int(_get_cached(element, PID_HWND)) or UiaVariant.to_int(_get_current(element, PID_HWND))
    role_id = UiaVariant.to_int(_get_cached(element, PID_CONTROL_TYPE)) or UiaVariant.to_int(_get_current(element, PID_CONTROL_TYPE))
    return _node_id(runtime_id, hwnd, rect), control_type_name(role_id)


def _r2_points(sw: int, sh: int, *, step_px: int) -> list[tuple[int, int]]:
    margin = max(8, step_px // 4)
    usable_w = max(1, sw - 2 * margin)
    usable_h = max(1, sh - 2 * margin)
    cols = max(1, usable_w // step_px)
    rows = max(1, usable_h // step_px)
    count = (cols + 1) * (rows + 1)
    g = 1.32471795724474602596
    ax, ay = 1.0 / g, 1.0 / (g * g)
    seen: set[tuple[int, int]] = set()
    points: list[tuple[int, int]] = []
    for i in range(count):
        fx = (0.5 + ax * (i + 1)) % 1.0
        fy = (0.5 + ay * (i + 1)) % 1.0
        x = margin + int(fx * usable_w)
        y = margin + int(fy * usable_h)
        cell = (x // step_px, y // step_px)
        if cell in seen:
            continue
        seen.add(cell)
        points.append((min(sw - 1, max(0, x)), min(sh - 1, max(0, y))))
    return points


def _merge_nodes(index: dict[str, CachedNode], new_nodes: list[CachedNode]) -> int:
    added = 0
    for node in new_nodes:
        prev = index.get(node.id)
        if prev is None:
            index[node.id] = node
            added += 1
            continue
        if node.text_full and (not prev.text_full or len(node.text_full) > len(prev.text_full)):
            prev.text_full = node.text_full
        if node.value and (not prev.value or len(node.value) > len(prev.value)):
            prev.value = node.value
        for k, v in node.text_sources.items():
            if k not in prev.text_sources or len(v) > len(prev.text_sources.get(k, "")):
                prev.text_sources[k] = v
        for k, v in node.properties.items():
            if k not in prev.properties:
                prev.properties[k] = v
        for k, v in node.pattern_payloads.items():
            if k not in prev.pattern_payloads:
                prev.pattern_payloads[k] = v
        prev.patterns = sorted(set(prev.patterns) | set(node.patterns))
    return added


def filter_gather(gathered: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    filt = config.get("filter") or {}
    text_max = int(filt.get("text_hint_max", 10000))
    max_action = int(filt.get("max_action_nodes", 5000))
    require_interactive = bool(filt.get("require_interactive", False))
    nodes: list[CachedNode] = list(gathered.get("nodes") or [])
    screen = gathered.get("screen") or {}
    windows = gathered.get("windows") or []
    window_z_order = gathered.get("window_z_order") or []
    scan = gathered.get("scan") or {}

    merged: dict[str, CachedNode] = {}
    for node in nodes:
        key = ",".join(map(str, node.runtime_id)) if node.runtime_id else node.id
        prev = merged.get(key)
        if prev is None:
            merged[key] = node
            continue
        if node.text_full and (not prev.text_full or len(node.text_full) > len(prev.text_full)):
            prev.text_full = node.text_full
        if node.value and (not prev.value or len(node.value) > len(prev.value)):
            prev.value = node.value
        if node.name and (not prev.name or len(node.name) > len(prev.name)):
            prev.name = node.name
    nodes = list(merged.values())

    def label_for(node: CachedNode) -> str:
        base = (node.name or "").strip()
        text = (node.text_full or node.value or "").strip()
        if text and len(text) > len(base):
            return text[:text_max]
        return base[:text_max] if base else ""

    def rect_area(rect: dict[str, int]) -> int:
        return max(0, int(rect.get("right", 0)) - int(rect.get("left", 0))) * max(0, int(rect.get("bottom", 0)) - int(rect.get("top", 0)))

    def contains(rect: dict[str, int], x: int, y: int) -> bool:
        return int(rect.get("left", 0)) <= x <= int(rect.get("right", 0)) and int(rect.get("top", 0)) <= y <= int(rect.get("bottom", 0))

    action_elements: dict[str, dict[str, Any]] = {}
    text_hints: dict[str, str] = {}
    ranked = sorted(nodes, key=lambda n: (0 if n.name or n.text_full else 1, 0 if not n.offscreen else 1))
    for node in ranked:
        if node.offscreen:
            continue
        if node.role in JUNK_ROLES:
            continue
        rect = node.rect
        if rect.get("right", 0) <= rect.get("left", 0) or rect.get("bottom", 0) <= rect.get("top", 0):
            continue
        action = _action_for_role(node.role, node.class_name)
        label = label_for(node)
        if label and label not in (node.name or ""):
            text_hints[node.id] = label
        if action and len(action_elements) < max_action:
            if require_interactive:
                action_elements[node.id] = {
                    "id": node.id,
                    "name": label or node.name,
                    "role": node.role,
                    "action": action,
                    "px": node.px,
                    "py": node.py,
                    "hwnd": node.hwnd,
                    "rect": node.rect,
                    "enabled": node.enabled,
                    "automation_id": node.automation_id,
                    "class_name": node.class_name,
                    "runtime_id": node.runtime_id,
                    "z_order": node.z_order,
                    "depth": node.depth,
                    "has_focus": node.has_focus,
                }

    observed_at = time.time()
    hwnd_to_z = {hwnd: i for i, hwnd in enumerate(window_z_order)}
    
    root = {
        "id": "W0",
        "role": "Screen",
        "name": "Screen",
        "title": "Desktop",
        "rect": {"left": 0, "top": 0, "right": int(screen.get("width", 0)), "bottom": int(screen.get("height", 0))},
        "fresh_scan": True,
        "observed_at": observed_at,
        "scan": {**scan, "raw_element_count": len(nodes), "actionable_element_count": len(action_elements)},
        "children": [],
    }
    node_index: dict[str, dict[str, Any]] = {"W0": {k: v for k, v in root.items() if k != "children"}}
    window_nodes: dict[str, dict[str, Any]] = {}
    hwnd_to_window: dict[int, str] = {}

    for window in windows:
        token = str(window.get("token") or "")
        if not token or token == "W0":
            continue
        title = str(window.get("title") or window.get("name") or "")
        node = {
            "id": token,
            "parent_id": "W0",
            "role": "Window",
            "name": title,
            "title": title,
            "hwnd": int(window.get("hwnd") or 0),
            "process_id": int(window.get("process_id") or 0),
            "class_name": str(window.get("class_name") or ""),
            "rect": window.get("rect", {}),
            "z_order": hwnd_to_z.get(int(window.get("hwnd") or 0), 0),
            "children": [],
        }
        window_nodes[token] = node
        hwnd_to_window[node["hwnd"]] = token
        root["children"].append(node)
        node_index[token] = {k: v for k, v in node.items() if k != "children"}

    root["children"].sort(key=lambda w: w.get("z_order", 0))

    direct: list[dict[str, Any]] = []
    for element in action_elements.values():
        px, py = int(element.get("px") or 0), int(element.get("py") or 0)
        hwnd = int(element.get("hwnd") or 0)
        parent_id = hwnd_to_window.get(hwnd, "")
        if not parent_id:
            containing = [n for n in window_nodes.values() if contains(n.get("rect", {}), px, py)]
            if containing:
                containing.sort(key=lambda n: rect_area(n.get("rect", {})))
                parent_id = str(containing[0]["id"])
        if not parent_id:
            parent_id = "W0"
        node = {
            "id": element["id"],
            "parent_id": parent_id,
            "role": element.get("role", ""),
            "name": element.get("name", ""),
            "action": element.get("action", ""),
            "px": px,
            "py": py,
            "hwnd": hwnd,
            "rect": element.get("rect", {}),
            "enabled": bool(element.get("enabled", False)),
            "automation_id": element.get("automation_id", ""),
            "class_name": element.get("class_name", ""),
            "runtime_id": element.get("runtime_id", []),
            "z_order": element.get("z_order", 0),
            "depth": element.get("depth", 0),
            "has_focus": element.get("has_focus", False),
            "children": [],
        }
        node_index[node["id"]] = {k: v for k, v in node.items() if k != "children"}
        if parent_id == "W0":
            direct.append(node)
        else:
            window_nodes[parent_id]["children"].append(node)

    for node in merged.values():
        if node.id in action_elements:
            continue
        px, py = int(node.px or 0), int(node.py or 0)
        hwnd = int(node.hwnd or 0)
        parent_id = hwnd_to_window.get(hwnd, "")
        if not parent_id:
            containing = [n for n in window_nodes.values() if contains(n.get("rect", {}), px, py)]
            if containing:
                containing.sort(key=lambda n: rect_area(n.get("rect", {})))
                parent_id = str(containing[0]["id"])
        if not parent_id:
            parent_id = "W0"
        action = _action_for_role(node.role, node.class_name) or ""
        n = {
            "id": node.id,
            "parent_id": parent_id,
            "role": node.role,
            "name": node.name or "",
            "action": action,
            "px": px,
            "py": py,
            "hwnd": hwnd,
            "rect": node.rect,
            "enabled": node.enabled,
            "automation_id": node.automation_id,
            "class_name": node.class_name,
            "runtime_id": node.runtime_id,
            "z_order": node.z_order,
            "depth": node.depth,
            "has_focus": node.has_focus,
            "children": [],
        }
        node_index[n["id"]] = {k: v for k, v in n.items() if k != "children"}
        if action and len(action_elements) < max_action:
            action_elements[n["id"]] = n
        if parent_id == "W0":
            direct.append(n)
        else:
            window_nodes[parent_id]["children"].append(n)
    root["children"].extend(direct)

    def sort_children(node: dict[str, Any]) -> None:
        children = node.get("children")
        if not isinstance(children, list):
            return
        children.sort(key=lambda c: (c.get("z_order", 0), int((c.get("rect") or {}).get("top", 0)), int((c.get("rect") or {}).get("left", 0)), rect_area(c.get("rect") or {})))
        for child in children:
            if isinstance(child, dict):
                sort_children(child)

    sort_children(root)

    def assign_short_ids(node: dict[str, Any], window_prefix: str = "", elem_counter: dict[str, int] | None = None) -> None:
        if elem_counter is None:
            elem_counter = {}
        node_id = node.get("id", "")
        parent_id = node.get("parent_id", "")
        
        if node_id == "W0":
            short_id = "W0"
        elif node_id.startswith("W") and parent_id == "W0":
            short_id = node_id
        elif parent_id.startswith("W") and parent_id != "W0":
            win_key = parent_id
            if win_key not in elem_counter:
                elem_counter[win_key] = 0
            elem_counter[win_key] += 1
            short_id = f"{win_key}E{elem_counter[win_key]}"
        else:
            parent_short = parent_id
            if parent_short in short_id_map:
                parent_short = short_id_map[parent_short]
            child_key = f"{parent_short}_child"
            if child_key not in elem_counter:
                elem_counter[child_key] = 0
            elem_counter[child_key] += 1
            short_id = f"{parent_short}C{elem_counter[child_key]}"
        
        short_id_map[node_id] = short_id
        node["short_id"] = short_id
        
        for child in node.get("children") or []:
            if isinstance(child, dict):
                assign_short_ids(child, window_prefix, elem_counter)

    short_id_map: dict[str, str] = {}
    assign_short_ids(root)

    for node_id, node_data in node_index.items():
        if node_id in short_id_map:
            node_data["short_id"] = short_id_map[node_id]
    
    for elem_id, elem_data in action_elements.items():
        if elem_id in short_id_map:
            elem_data["short_id"] = short_id_map[elem_id]

    def clean(value: Any) -> str:
        return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())

    lines: list[str] = []
    lines.append("W0 Screen Desktop")

    def render(node: dict[str, Any], indent: int = 1) -> None:
        prefix = "  " * indent
        short_id = node.get("short_id", node.get("id", ""))
        role = str(node.get("role", ""))
        name = clean(node.get("name", "") or node.get("title", ""))
        action = str(node.get("action", ""))
        parts = []
        if short_id:
            parts.append(short_id)
        if role:
            parts.append(role)
        if name:
            parts.append(name)
        if action:
            parts.append(f"[{action}]")
        hint = text_hints.get(node.get("id", ""), "")
        if hint and hint not in name:
            parts.append(f"~{hint}")
        lines.append(f"{prefix}{' '.join(parts)}")
        for child in node.get("children") or []:
            if isinstance(child, dict):
                render(child, indent + 1)

    for child in root.get("children") or []:
        if isinstance(child, dict):
            render(child, 1)

    desktop_tree = {
        "id": "W0",
        "role": "Screen",
        "fresh_scan": True,
        "observed_at": observed_at,
        "root": root,
        "node_index": node_index,
        "window_count": len(window_nodes),
        "element_count": len(action_elements),
        "window_z_order": window_z_order,
    }
    return {
        "gather_nodes": [n.to_dict() for n in nodes],
        "action_index": action_elements,
        "desktop_tree": desktop_tree,
        "desktop_tree_text": "\n".join(lines),
        "text_hints": text_hints,
    }


def _write_artifact(payload: dict[str, Any], observed_at: float) -> dict[str, Any]:
    path = ROOT / f"runtime_observation_{int(observed_at * 1000)}.json"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)
    return {"path": path.relative_to(ROOT).as_posix(), "size": path.stat().st_size, "kind": "raw_full_observation"}


def observe(desktop: Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(config or {})
    if not cfg.get("enabled", True):
        raise RuntimeError("hover_cache observation is disabled")
    gathered = gather(desktop, cfg)
    filtered = filter_gather(gathered, cfg)
    observed_at = time.time()
    desktop._last_desktop_tree = filtered["desktop_tree"]
    desktop._last_action_index = filtered["action_index"]
    artifact = _write_artifact(
        {
            "observed_at": observed_at,
            "fresh_scan": True,
            "scan_config": _scan_settings(cfg),
            "gather": filtered["gather_nodes"],
            "scan_stats": (gathered.get("scan") or {}).get("stats", {}),
            "desktop_tree": filtered["desktop_tree"],
            "action_index": filtered["action_index"],
            "desktop_tree_text": filtered["desktop_tree_text"],
        },
        observed_at,
    )
    return {
        "observed_at": observed_at,
        "fresh_scan": True,
        "desktop_tree": filtered["desktop_tree"],
        "desktop_tree_text": filtered["desktop_tree_text"],
        "action_index": filtered["action_index"],
        "observation_artifact": artifact,
    }