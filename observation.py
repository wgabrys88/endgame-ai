from __future__ import annotations

import ctypes
import importlib
import json
import math
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

from dataclasses import dataclass, field
from typing import Any


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
    keyboard_focus: bool = False
    offscreen: bool = False
    runtime_id: list[int] = field(default_factory=list)
    text_full: str | None = None
    value: str | None = None
    patterns: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    pattern_payloads: dict[str, Any] = field(default_factory=dict)
    text_sources: dict[str, str] = field(default_factory=dict)
    source_probe: tuple[int, int] | None = None

    def to_gather_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "role": self.role,
            "name": self.name,
            "hwnd": self.hwnd,
            "px": self.px,
            "py": self.py,
            "rect": self.rect,
            "enabled": self.enabled,
            "keyboard_focus": self.keyboard_focus,
            "offscreen": self.offscreen,
            "patterns": self.patterns,
        }
        if self.automation_id:
            out["automation_id"] = self.automation_id
        if self.class_name:
            out["class_name"] = self.class_name
        if self.framework_id:
            out["framework_id"] = self.framework_id
        if self.text_full:
            out["text_full"] = self.text_full
        if self.value:
            out["value"] = self.value
        if self.text_sources:
            out["text_sources"] = self.text_sources
        if self.properties:
            out["properties"] = self.properties
        if self.pattern_payloads:
            out["pattern_payloads"] = self.pattern_payloads
        if self.source_probe:
            out["source_probe"] = list(self.source_probe)
        return out

    def to_llm_dict(self) -> dict[str, Any]:
        """Minimal LLM-facing projection (filter layer preview)."""
        out: dict[str, Any] = {
            "id": self.id,
            "role": self.role,
            "name": self.name,
        }
        if self.keyboard_focus:
            out["keyboard_focus"] = True
        if not self.name and self.automation_id:
            out["automation_id"] = self.automation_id
        best = self.text_full or self.value or (self.text_sources.get("name") if self.text_sources else None)
        if best:
            n = len(best)
            out["text_hint"] = {
                "length": n,
                "prefix": best[:200] if n else "",
                "sources": list(self.text_sources.keys()) if self.text_sources else [],
            }
        return out

from typing import Any


def expand(config: dict[str, Any]) -> dict[str, Any]:
    scan = dict(config.get("scan") or {})
    scan.update(config.get("depth") or {})
    return scan

from dataclasses import dataclass, field
from typing import Any


CLICK = {
    "Button", "Calendar", "CheckBox", "Hyperlink", "ListItem", "MenuItem",
    "RadioButton", "Tab", "TabItem", "TreeItem", "DataItem", "SplitButton",
}
WRITE = {"Edit", "ComboBox", "Spinner", "Document"}
SCROLL = {"List", "ScrollBar", "Slider", "Tree", "DataGrid"}


def classify_role(role: str, class_name: str = "") -> str:
    if role in CLICK:
        return "click"
    if role in WRITE:
        return "write"
    if role == "Pane" and class_name == "Scintilla":
        return "write"
    if role in SCROLL:
        return "scroll"
    return ""


def display_name(node: CachedNode, text_max: int) -> str:
    base = (node.name or "").strip()
    text = (node.text_full or node.value or "").strip()
    if text and len(text) > len(base):
        return text[:text_max]
    return base


@dataclass
class FilteredObservation:
    action_elements: dict[str, dict[str, Any]] = field(default_factory=dict)
    llm_nodes: list[dict[str, Any]] = field(default_factory=list)
    gather_nodes: list[dict[str, Any]] = field(default_factory=list)


class ObservationFilter:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = dict(config or {})

    @staticmethod
    def _dedupe(nodes: list[CachedNode]) -> list[CachedNode]:
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
            if node.keyboard_focus:
                prev.keyboard_focus = True
            if node.name and (not prev.name or len(node.name) > len(prev.name)):
                prev.name = node.name
        return list(merged.values())

    def apply(self, nodes: list[CachedNode]) -> FilteredObservation:
        filt = self.config.get("filter") or {}
        max_action = int(filt.get("max_action_nodes", 240))
        max_llm = int(filt.get("max_llm_nodes", 180))
        text_max = int(filt.get("text_hint_max", 120))
        require_interactive = bool(filt.get("require_interactive", True))
        action_elements: dict[str, dict[str, Any]] = {}
        llm_nodes: list[dict[str, Any]] = []
        nodes = self._dedupe(nodes)
        gather_nodes = [n.to_gather_dict() for n in nodes]

        ranked = sorted(
            nodes,
            key=lambda n: (
                0 if n.keyboard_focus else 1,
                0 if n.name or n.text_full else 1,
                0 if not n.offscreen else 1,
            ),
        )

        for node in ranked:
            if node.offscreen or not node.enabled:
                continue
            rect = node.rect
            if rect.get("right", 0) <= rect.get("left", 0) or rect.get("bottom", 0) <= rect.get("top", 0):
                continue
            action = classify_role(node.role, node.class_name)
            label = display_name(node, text_max)
            if len(llm_nodes) < max_llm:
                if label or node.text_full or node.keyboard_focus:
                    if not require_interactive or action or node.keyboard_focus:
                        llm_nodes.append(node.to_llm_dict())
            if action and len(action_elements) < max_action:
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
                    "focused": node.keyboard_focus,
                    "automation_id": node.automation_id,
                    "class_name": node.class_name,
                    "runtime_id": node.runtime_id,
                }

        return FilteredObservation(
            action_elements=action_elements,
            llm_nodes=llm_nodes,
            gather_nodes=gather_nodes,
        )

from typing import Any


class DesktopTree:
    @staticmethod
    def _contains_point(rect: dict[str, int], x: int, y: int) -> bool:
        return int(rect.get("left", 0)) <= x <= int(rect.get("right", 0)) and int(rect.get("top", 0)) <= y <= int(rect.get("bottom", 0))

    @staticmethod
    def _rect_area(rect: dict[str, int]) -> int:
        return max(0, int(rect.get("right", 0)) - int(rect.get("left", 0))) * max(0, int(rect.get("bottom", 0)) - int(rect.get("top", 0)))

    @staticmethod
    def _sort_children(node: dict[str, Any]) -> None:
        children = node.get("children")
        if not isinstance(children, list):
            return
        children.sort(key=lambda c: (
            int((c.get("rect") or {}).get("top", 0)),
            int((c.get("rect") or {}).get("left", 0)),
            DesktopTree._rect_area(c.get("rect") or {}),
        ))
        for child in children:
            if isinstance(child, dict):
                DesktopTree._sort_children(child)

    @classmethod
    def build(
        cls,
        screen: dict[str, int],
        elements: dict[str, dict[str, Any]],
        windows: list[dict[str, Any]],
        focused_title: str,
        *,
        observed_at: float,
        scan_config: dict[str, Any],
        raw_element_count: int,
    ) -> dict[str, Any]:
        root_rect = {"left": 0, "top": 0, "right": int(screen.get("width", 0)), "bottom": int(screen.get("height", 0))}
        root = {
            "id": "W0",
            "role": "Screen",
            "name": "Screen",
            "title": "Desktop",
            "rect": root_rect,
            "focused": False,
            "fresh_scan": True,
            "observed_at": observed_at,
            "scan": {
                "method": str(scan_config.get("method", "hover_cache")),
                "pattern": str(scan_config.get("pattern", "sinusoidal")),
                "step_px": int(scan_config.get("step_px", 0) or 0),
                "raw_element_count": raw_element_count,
                "actionable_element_count": len(elements),
                "stats": scan_config.get("stats", {}),
            },
            "children": [],
        }
        node_index: dict[str, dict[str, Any]] = {"W0": {k: v for k, v in root.items() if k != "children"}}
        window_nodes: dict[str, dict[str, Any]] = {}
        hwnd_to_window_id: dict[int, str] = {}
        focused_window_id = ""

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
                "focused": bool(focused_title and title == focused_title),
                "source": "win32_enum_windows",
                "children": [],
            }
            if node["focused"]:
                focused_window_id = token
            window_nodes[token] = node
            hwnd_to_window_id[node["hwnd"]] = token
            root["children"].append(node)
            node_index[token] = {k: v for k, v in node.items() if k != "children"}

        direct_elements: list[dict[str, Any]] = []
        for element_id, element in elements.items():
            px = int(element.get("px") or 0)
            py = int(element.get("py") or 0)
            hwnd = int(element.get("hwnd") or 0)
            parent_id = hwnd_to_window_id.get(hwnd, "")
            if not parent_id:
                containing = [n for n in window_nodes.values() if cls._contains_point(n.get("rect", {}), px, py)]
                if containing:
                    containing.sort(key=lambda n: cls._rect_area(n.get("rect", {})))
                    parent_id = str(containing[0]["id"])
            if not parent_id:
                parent_id = "W0"
            node = {
                "id": element_id,
                "parent_id": parent_id,
                "role": element.get("role", ""),
                "name": element.get("name", ""),
                "action": element.get("action", ""),
                "px": px,
                "py": py,
                "hwnd": hwnd,
                "rect": element.get("rect", {}),
                "enabled": bool(element.get("enabled", False)),
                "focused": bool(element.get("focused", False)),
                "automation_id": element.get("automation_id", ""),
                "class_name": element.get("class_name", ""),
                "runtime_id": element.get("runtime_id", []),
                "source": "hover_cache",
                "confidence": "cache_hit",
                "children": [],
            }
            node_index[element_id] = {k: v for k, v in node.items() if k != "children"}
            if parent_id == "W0":
                direct_elements.append(node)
            else:
                window_nodes[parent_id]["children"].append(node)

        root["children"].extend(direct_elements)
        cls._sort_children(root)
        return {
            "id": "W0",
            "role": "Screen",
            "fresh_scan": True,
            "observed_at": observed_at,
            "focused_title": focused_title,
            "focused_window_id": focused_window_id,
            "root": root,
            "node_index": node_index,
            "window_count": len(window_nodes),
            "element_count": len(elements),
        }

    @classmethod
    def semantic(cls, full_tree: dict[str, Any]) -> dict[str, Any]:
        root = cls._semantic_node(full_tree.get("root", {}) if isinstance(full_tree.get("root"), dict) else {})
        return {"id": "W0", "role": "Screen", "focused_title": full_tree.get("focused_title", ""), "root": root}

    @classmethod
    def _semantic_node(cls, node: dict[str, Any]) -> dict[str, Any]:
        semantic: dict[str, Any] = {
            "id": node.get("id", ""),
            "role": node.get("role", ""),
            "name": node.get("name", "") or node.get("title", ""),
        }
        if "action" in node:
            semantic["action"] = node.get("action")
        if node.get("focused"):
            semantic["focused"] = True
        children = node.get("children") if isinstance(node.get("children"), list) else []
        semantic["children"] = [cls._semantic_node(child) for child in children if isinstance(child, dict)]
        return semantic

    @classmethod
    def render_text(cls, semantic_tree: dict[str, Any], text_hints: dict[str, str] | None = None) -> str:
        hints = text_hints or {}
        lines: list[str] = []

        def clean_label(value: Any) -> str:
            return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())

        def render_node(node: dict[str, Any], indent: int = 0) -> None:
            prefix = "  " * indent
            node_id = str(node.get("id", ""))
            role = str(node.get("role", ""))
            name = clean_label(node.get("name", "") or node.get("title", ""))
            action = str(node.get("action", ""))
            parts: list[str] = []
            if node_id:
                parts.append(f"({node_id})")
            if role:
                parts.append(role)
            if name:
                parts.append(name)
            if action:
                parts.append(f"[{action}]")
            if node.get("focused") and role == "Window":
                parts.append("[FOCUSED]")
            hint = hints.get(node_id, "")
            if hint and hint not in name:
                parts.append(f"~{hint}")
            lines.append(f"{prefix}{' '.join(parts)}")
            for child in node.get("children") or []:
                if isinstance(child, dict):
                    render_node(child, indent + 1)

        root = semantic_tree.get("root", {})
        if not isinstance(root, dict):
            return ""
        sid, srole, sname = root.get("id", "W0"), root.get("role", "Screen"), clean_label(root.get("name", "Desktop"))
        screen_parts: list[str] = []
        if sid:
            screen_parts.append(f"({sid})")
        if srole:
            screen_parts.append(srole)
        if sname:
            screen_parts.append(sname)
        lines.append(" ".join(screen_parts))
        for child in root.get("children") or []:
            if isinstance(child, dict):
                render_node(child, 1)
        return "\n".join(lines)

    @classmethod
    def action_index(cls, full_tree: dict[str, Any]) -> dict[str, dict[str, Any]]:
        full_index = full_tree.get("node_index") if isinstance(full_tree.get("node_index"), dict) else {}
        out: dict[str, dict[str, Any]] = {}
        for node_id, node in full_index.items():
            if not isinstance(node, dict):
                continue
            out[str(node_id)] = {
                "id": node.get("id", node_id),
                "parent_id": node.get("parent_id"),
                "role": node.get("role"),
                "name": node.get("name") or node.get("title"),
                "title": node.get("title"),
                "action": node.get("action"),
                "px": node.get("px"),
                "py": node.get("py"),
                "hwnd": node.get("hwnd"),
                "rect": node.get("rect"),
                "enabled": node.get("enabled"),
                "focused": node.get("focused"),
                "automation_id": node.get("automation_id"),
                "class_name": node.get("class_name"),
                "runtime_id": node.get("runtime_id"),
            }
        return out

from typing import Any



def _variant_int(v: Any) -> int:
    if v is None:
        return 0
    if hasattr(v, "value"):
        v = v.value
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _variant_str(v: Any) -> str:
    if v is None:
        return ""
    if hasattr(v, "value"):
        v = v.value
    return "" if v is None else str(v)


def _variant_bool(v: Any) -> bool:
    if v is None:
        return False
    if hasattr(v, "value"):
        v = v.value
    return bool(v)


def _variant_rect(v: Any) -> dict[str, int]:
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


def _variant_runtime_id(v: Any) -> list[int]:
    if v is None:
        return []
    try:
        val = v.value if hasattr(v, "value") else v
        if val is None:
            return []
        return [int(x) for x in list(val)]
    except Exception:
        return []


def _serialize_value(v: Any) -> Any:
    if v is None:
        return None
    if hasattr(v, "value"):
        v = v.value
    if isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, (tuple, list)):
        return [_serialize_value(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _serialize_value(val) for k, val in v.items()}
    rect = _variant_rect(v)
    if rect["right"] > rect["left"] and rect["bottom"] > rect["top"]:
        return rect
    try:
        if hasattr(v, "__iter__") and not isinstance(v, (str, bytes)):
            return [_serialize_value(x) for x in list(v)]
    except Exception:
        pass
    s = str(v).strip()
    return s if s else None


def _node_id(runtime_id: list[int], hwnd: int, rect: dict[str, int]) -> str:
    if runtime_id:
        return "e_" + "_".join(map(str, runtime_id))
    return f"e_{hwnd}_{rect['left']}_{rect['top']}"


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


def _harvest_properties(element: Any) -> dict[str, Any]:
    props: dict[str, Any] = {}
    for pid in PROPERTY_IDS:
        label = PROPERTY_NAMES.get(pid, f"Property_{pid}")
        cached = _serialize_value(_get_cached(element, pid))
        if cached is not None and cached != "" and cached != []:
            props[label] = cached
            continue
        current = _serialize_value(_get_current(element, pid))
        if current is not None and current != "" and current != []:
            props[f"{label}_current"] = current
    return props


def _get_pattern(element: Any, pattern_id: int, label: str) -> tuple[Any | None, str]:
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
        for src, doc in (
            ("DocumentRange", _safe_attr(pattern, "DocumentRange")),
        ):
            if doc is None:
                continue
            try:
                text = doc.GetText(-1)
                if text and str(text).strip():
                    out[src] = str(text)
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
                        r = ranges.GetElement(i)
                        t = r.GetText(-1)
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
                out[key] = _serialize_value(val)

    elif label == "LegacyIAccessible":
        for key in (
            "Name", "Value", "Description", "Role", "State", "DefaultAction",
            "Help", "KeyboardShortcut", "ChildId",
        ):
            val = _safe_attr(pattern, key)
            if val is not None and str(val).strip() not in ("", "0"):
                out[key] = _serialize_value(val)

    elif label == "Scroll":
        for key in ("HorizontallyScrollable", "HorizontalScrollPercent", "HorizontalViewSize",
                    "VerticallyScrollable", "VerticalScrollPercent", "VerticalViewSize"):
            val = _safe_attr(pattern, key)
            if val is not None:
                out[key] = _serialize_value(val)

    elif label == "Window":
        for key in ("CanMaximize", "CanMinimize", "IsModal", "IsTopmost", "WindowInteractionState", "WindowVisualState"):
            val = _safe_attr(pattern, key)
            if val is not None:
                out[key] = _serialize_value(val)

    elif label == "Invoke":
        out["available"] = True

    elif label == "Selection":
        try:
            sel = pattern.GetSelection()
            if sel is not None:
                try:
                    length = int(sel.Length)
                except Exception:
                    length = 0
                out["selection_count"] = length
        except Exception:
            pass

    else:
        out["available"] = True

    return out


def _harvest_patterns(element: Any) -> tuple[list[str], dict[str, Any]]:
    names: list[str] = []
    payloads: dict[str, Any] = {}
    for pid in PATTERN_IDS:
        label = PATTERN_NAMES.get(pid, f"Pattern_{pid}")
        pattern, source = _get_pattern(element, pid, label)
        if pattern is None:
            continue
        names.append(label)
        payload = _extract_pattern_payload(pattern, label)
        if payload:
            payload["_source"] = source
            payloads[label] = payload
        else:
            payloads[label] = {"_source": source, "available": True}
    return names, payloads


def _collect_text_sources(
    name: str,
    properties: dict[str, Any],
    pattern_payloads: dict[str, Any],
) -> tuple[dict[str, str], str | None, str | None]:
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

    value_payload = pattern_payloads.get("Value", {})
    val = value_payload.get("Value")
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
            if not text_full or (isinstance(val, str) and len(val) > len(text_full or "")):
                if key in ("Value", "Description") or (key == "Name" and len(val) > 20):
                    text_full = val.strip()

    if not text_full and name and len(name) > 1:
        # Scintilla/Notepad++ often surfaces first line in Name only
        text_full = name.strip()

    return sources, text_full, value


def element_to_cached_node(element: Any, *, probe_xy: tuple[int, int] | None = None) -> CachedNode | None:
    try:
        rect = _variant_rect(_get_cached(element, PID_BOUNDING_RECT))
        if rect["right"] <= rect["left"] or rect["bottom"] <= rect["top"]:
            rect = _variant_rect(_get_current(element, PID_BOUNDING_RECT))
        if rect["right"] <= rect["left"] or rect["bottom"] <= rect["top"]:
            return None

        runtime_id = _variant_runtime_id(_get_cached(element, PID_RUNTIME_ID))
        if not runtime_id:
            runtime_id = _variant_runtime_id(_get_current(element, PID_RUNTIME_ID))
        hwnd = _variant_int(_get_cached(element, PID_HWND))
        role_id = _variant_int(_get_cached(element, PID_CONTROL_TYPE))
        name = _variant_str(_get_cached(element, PID_NAME))
        if not name:
            name = _variant_str(_get_current(element, PID_NAME))

        properties = _harvest_properties(element)
        patterns, pattern_payloads = _harvest_patterns(element)
        text_sources, text_full, value = _collect_text_sources(name, properties, pattern_payloads)

        px = (rect["left"] + rect["right"]) // 2
        py = (rect["top"] + rect["bottom"]) // 2

        return CachedNode(
            id=_node_id(runtime_id, hwnd, rect),
            role=control_type_name(role_id),
            name=name,
            automation_id=_variant_str(_get_cached(element, PID_AUTOMATION_ID)),
            class_name=_variant_str(_get_cached(element, PID_CLASS_NAME)),
            hwnd=hwnd,
            framework_id=_variant_str(_get_cached(element, PID_FRAMEWORK)),
            px=px,
            py=py,
            rect=rect,
            enabled=_variant_bool(_get_cached(element, PID_ENABLED)),
            keyboard_focus=_variant_bool(_get_cached(element, PID_KEYBOARD_FOCUS)),
            offscreen=_variant_bool(_get_cached(element, PID_OFFSCREEN)),
            runtime_id=runtime_id,
            text_full=text_full,
            value=value,
            patterns=patterns,
            properties=properties,
            pattern_payloads=pattern_payloads,
            text_sources=text_sources,
            source_probe=probe_xy,
        )
    except Exception:
        return None


def _true_condition(automation: Any) -> Any:
    try:
        return automation.CreateTrueCondition()
    except Exception:
        return automation.TrueCondition


def harvest_cached_subtree(
    automation: Any,
    root_element: Any,
    cache_request: Any,
    *,
    probe_xy: tuple[int, int],
    max_nodes: int,
) -> list[CachedNode]:
    """Walk cached subtree under root_element using FindAllBuildCache."""
    nodes: list[CachedNode] = []
    seen: set[str] = set()

    def add_element(el: Any) -> None:
        if len(nodes) >= max_nodes:
            return
        node = element_to_cached_node(el, probe_xy=probe_xy)
        if node is None or node.id in seen:
            return
        seen.add(node.id)
        nodes.append(node)

    add_element(root_element)
    try:
        arr = root_element.FindAllBuildCache(TreeScope_Descendants, _true_condition(automation), cache_request)
        if arr is not None:
            try:
                length = int(arr.Length)
            except Exception:
                length = 0
            for i in range(length):
                if len(nodes) >= max_nodes:
                    break
                try:
                    add_element(arr.GetElement(i))
                except Exception:
                    continue
    except Exception:
        try:
            walker = automation.CreateTreeWalkerBuildCache(_true_condition(automation), cache_request)
            child = walker.GetFirstChildElement(root_element)
            stack = [child] if child else []
            while stack and len(nodes) < max_nodes:
                el = stack.pop()
                if el is None:
                    continue
                add_element(el)
                try:
                    sib = walker.GetNextSiblingElement(el)
                    if sib:
                        stack.append(sib)
                    first = walker.GetFirstChildElement(el)
                    if first:
                        stack.append(first)
                except Exception:
                    pass
        except Exception:
            pass

    return nodes

def create_cache_request(automation: Any, scan_cfg: dict[str, Any] | None = None) -> Any:
    scan_cfg = scan_cfg or {}
    req = automation.CreateCacheRequest()
    req.TreeScope = TreeScope_Subtree
    prop_ids = scan_cfg.get("property_ids") or PROPERTY_IDS
    pat_ids = scan_cfg.get("pattern_ids") or PATTERN_IDS
    for prop_id in prop_ids:
        req.AddProperty(prop_id)
    for pattern_id in pat_ids:
        req.AddPattern(pattern_id)
    return req


def probe_point_build_cache(
    automation: Any,
    cache_request: Any,
    x: int,
    y: int,
    *,
    delay_ms: int,
    max_subtree_nodes: int,
    move_cursor: bool = True,
) -> tuple[Any | None, list[CachedNode]]:
    """Move real cursor, ElementFromPointBuildCache, harvest cached subtree."""
    if move_cursor:
        try:
            user32.SetCursorPos(int(x), int(y))
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)
        except Exception:
            pass
    pt = wintypes.POINT(int(x), int(y))
    try:
        root = automation.ElementFromPointBuildCache(pt, cache_request)
    except Exception:
        root = automation.ElementFromPoint(pt)
    if root is None:
        return None, []
    nodes = harvest_cached_subtree(
        automation,
        root,
        cache_request,
        probe_xy=(x, y),
        max_nodes=max_subtree_nodes,
    )
    return root, nodes


def sinusoidal_probe_points(
    sw: int,
    sh: int,
    *,
    step_px: int = 96,
    row_step_px: int | None = None,
) -> list[tuple[int, int]]:
    """Serpentine rows with sine wiggle — continuous path, fewer points than dense grid."""
    margin = max(8, step_px // 4)
    row_step = row_step_px or max(step_px, (sh - 2 * margin) // max(6, sh // (step_px * 2)))
    amplitude = max(4, row_step // 5)
    wavelength = max(sw // 2, step_px * 4)
    points: list[tuple[int, int]] = []
    row_idx = 0
    for y_base in range(margin, sh - margin, row_step):
        xs = list(range(margin, sw - margin, step_px))
        if row_idx % 2 == 1:
            xs.reverse()
        for x in xs:
            wiggle = int(amplitude * math.sin((2 * math.pi * x) / wavelength))
            y = min(sh - 1, max(0, y_base + wiggle))
            points.append((x, y))
        row_idx += 1
    return points


def _run_probe_path(
    automation: Any,
    cache_request: Any,
    points: Iterable[tuple[int, int]],
    *,
    delay_ms: int,
    max_subtree_nodes_per_point: int,
    max_total_nodes: int,
    max_probe_points: int | None,
    restore_cursor: bool,
    pattern: str,
    step_px: int,
    include_nodes: bool = False,
) -> dict[str, Any]:
    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)
    global_index: dict[str, CachedNode] = {}
    probe_log: list[dict[str, Any]] = []
    t0 = time.time()
    probes = 0
    total_subtree = 0

    saved = wintypes.POINT()
    had_cursor = bool(user32.GetCursorPos(ctypes.byref(saved))) if restore_cursor else False

    try:
        for x, y in points:
            if max_probe_points is not None and probes >= max_probe_points:
                break
            if len(global_index) >= max_total_nodes:
                break
            probes += 1
            _, nodes = probe_point_build_cache(
                automation,
                cache_request,
                x,
                y,
                delay_ms=delay_ms,
                max_subtree_nodes=max_subtree_nodes_per_point,
                move_cursor=True,
            )
            added = merge_nodes(global_index, nodes)
            total_subtree += len(nodes)
            if nodes:
                probe_log.append({
                    "x": x,
                    "y": y,
                    "subtree_nodes": len(nodes),
                    "new_nodes": added,
                    "sample_roles": list({n.role for n in nodes[:8]}),
                })
    finally:
        if restore_cursor and had_cursor:
            try:
                user32.SetCursorPos(saved.x, saved.y)
            except Exception:
                pass

    fg_title = ""
    try:
        fg = automation.GetFocusedElement()
        if fg is not None:
            fg_title = str(fg.CurrentName or "")
    except Exception:
        pass

    nodes = list(global_index.values())
    text_blobs = [
        {
            "id": n.id,
            "role": n.role,
            "name": n.name,
            "length": len(n.text_full or ""),
            "prefix": (n.text_full or "")[:300],
            "sources": list(n.text_sources.keys()),
        }
        for n in nodes if n.text_full
    ]
    text_blobs.sort(key=lambda t: t["length"], reverse=True)

    result = {
        "methodology": "SetCursorPos + ElementFromPointBuildCache(TreeScope_Subtree) + wide UIA property/pattern harvest",
        "screen": {"width": sw, "height": sh},
        "config": {
            "pattern": pattern,
            "step_px": step_px,
            "delay_ms": delay_ms,
            "max_probe_points": max_probe_points,
            "max_subtree_nodes_per_point": max_subtree_nodes_per_point,
            "max_total_nodes": max_total_nodes,
            "restore_cursor": restore_cursor,
            "cached_property_count": len(PROPERTY_IDS),
            "cached_pattern_count": len(PATTERN_IDS),
        },
        "stats": {
            "probes": probes,
            "subtree_nodes_seen": total_subtree,
            "unique_nodes": len(nodes),
            "nodes_with_text": sum(1 for n in nodes if n.text_full),
            "nodes_with_text_sources": sum(1 for n in nodes if n.text_sources),
            "nodes_with_value": sum(1 for n in nodes if n.value),
            "nodes_with_pattern_payloads": sum(1 for n in nodes if n.pattern_payloads),
            "avg_properties_per_node": round(
                sum(len(n.properties) for n in nodes) / max(len(nodes), 1), 1
            ),
            "elapsed_s": round(time.time() - t0, 3),
        },
        "focus": {"window_title": fg_title},
        "gather": {
            "nodes": [n.to_gather_dict() for n in nodes],
            "body_map": {
                n.id: {"hwnd": n.hwnd, "px": n.px, "py": n.py, "rect": n.rect}
                for n in nodes
            },
        },
        "llm_preview": {
            "nodes": [n.to_llm_dict() for n in nodes if not n.offscreen][:200],
            "text_blobs_top": text_blobs[:10],
        },
        "probe_log_sample": probe_log[:30],
    }
    if include_nodes:
        result["_nodes"] = nodes
    return result


def merge_nodes(global_index: dict[str, CachedNode], new_nodes: list[CachedNode]) -> int:
    added = 0
    for node in new_nodes:
        prev = global_index.get(node.id)
        if prev is None:
            global_index[node.id] = node
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
        if node.keyboard_focus:
            prev.keyboard_focus = True
        prev.patterns = sorted(set(prev.patterns) | set(node.patterns))
    return added


def fullscreen_hover_cache_scan(
    automation: Any,
    *,
    step_px: int = 32,
    delay_ms: int = 5,
    max_probe_points: int | None = None,
    max_subtree_nodes_per_point: int = 120,
    max_total_nodes: int = 2000,
    pattern: str = "grid",
    include_nodes: bool = False,
    scan_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scan_cfg = scan_cfg or {}
    cache_request = create_cache_request(automation, scan_cfg)
    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)

    if pattern == "sinusoidal":
        points = sinusoidal_probe_points(sw, sh, step_px=step_px)
    else:
        points = [(x, y) for y in range(0, sh, step_px) for x in range(0, sw, step_px)]

    return _run_probe_path(
        automation,
        cache_request,
        points,
        delay_ms=delay_ms,
        max_subtree_nodes_per_point=max_subtree_nodes_per_point,
        max_total_nodes=max_total_nodes,
        max_probe_points=max_probe_points,
        restore_cursor=True,
        pattern=pattern,
        step_px=step_px,
        include_nodes=include_nodes,
    )


def single_point_probe(
    automation: Any,
    x: int,
    y: int,
    *,
    delay_ms: int = 10,
    max_subtree_nodes: int = 500,
) -> dict[str, Any]:
    """Probe one screen coordinate (for random/manual testing)."""
    cache_request = create_cache_request(automation)
    t0 = time.time()
    root, nodes = probe_point_build_cache(
        automation,
        cache_request,
        x,
        y,
        delay_ms=delay_ms,
        max_subtree_nodes=max_subtree_nodes,
    )
    text_blobs = [
        {"id": n.id, "role": n.role, "name": n.name, "length": len(n.text_full or ""), "text_full": n.text_full}
        for n in nodes if n.text_full
    ]
    text_blobs.sort(key=lambda t: t["length"], reverse=True)
    root_brief = None
    if root is not None:
        try:
            root_brief = {"name": str(root.CurrentName or ""), "control_type": int(root.CurrentControlType)}
        except Exception:
            root_brief = {"name": ""}
    return {
        "point": {"x": x, "y": y},
        "elapsed_s": round(time.time() - t0, 3),
        "root": root_brief,
        "subtree_count": len(nodes),
        "nodes": [n.to_gather_dict() for n in nodes],
        "text_blobs": text_blobs,
        "llm_preview": [n.to_llm_dict() for n in nodes[:50]],
    }

import json
import pathlib
import time
from typing import Any




class Observer:
    def __init__(self, desktop: Any):
        self._d = desktop

    def observe(self, config: dict[str, Any]) -> dict[str, Any]:
        scan_cfg = expand(config)
        run = fullscreen_hover_cache_scan(
            self._d.automation,
            pattern=str(scan_cfg.get("pattern", "sinusoidal")),
            step_px=int(scan_cfg.get("step_px", 96)),
            delay_ms=int(scan_cfg.get("delay_ms", 5)),
            max_probe_points=scan_cfg.get("max_probe_points"),
            max_subtree_nodes_per_point=int(scan_cfg.get("max_subtree_nodes_per_point", 250)),
            max_total_nodes=int(scan_cfg.get("max_total_nodes", 2000)),
            include_nodes=True,
            scan_cfg=scan_cfg,
        )
        nodes: list[CachedNode] = run.pop("_nodes", [])
        filtered = ObservationFilter(config).apply(nodes)
        return self._package(run, filtered, scan_cfg, config)

    def _package(
        self,
        run: dict[str, Any],
        filtered: Any,
        scan_cfg: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any]:
        import ctypes
        user32 = ctypes.windll.user32
        screen = {"width": user32.GetSystemMetrics(0), "height": user32.GetSystemMetrics(1)}
        focused_title = str(run.get("focus", {}).get("window_title") or "") or self._d.get_focused_title()
        self._d._focused_title_cache = focused_title
        observed_at = time.time()
        scan_meta = {**scan_cfg, "method": "hover_cache", "stats": run.get("stats", {})}
        full_tree = DesktopTree.build(
            screen,
            dict(filtered.action_elements),
            self._d.get_window_tokens(),
            focused_title,
            observed_at=observed_at,
            scan_config=scan_meta,
            raw_element_count=len(filtered.gather_nodes),
        )
        desktop_tree = DesktopTree.semantic(full_tree)
        action_index = DesktopTree.action_index(full_tree)
        text_max = int((config.get("filter") or {}).get("text_hint_max", 120))
        hints = {
            n["id"]: str((n.get("text_hint") or {}).get("prefix", ""))[:text_max]
            for n in filtered.llm_nodes
            if isinstance(n, dict) and n.get("text_hint")
        }
        artifact = self._write_artifact(
            {
                "observed_at": observed_at,
                "fresh_scan": True,
                "focused_title": focused_title,
                "scan_config": scan_cfg,
                "hover_cache_config": config,
                "gather": filtered.gather_nodes,
                "llm_nodes": filtered.llm_nodes,
                "scan_stats": run.get("stats", {}),
                "full_desktop_tree": full_tree,
                "semantic_desktop_tree": desktop_tree,
                "action_index": action_index,
            },
            observed_at,
        )
        self._d._last_desktop_tree = desktop_tree
        self._d._last_action_index = action_index
        return {
            "observed_at": observed_at,
            "fresh_scan": True,
            "desktop_tree": desktop_tree,
            "desktop_tree_text": DesktopTree.render_text(desktop_tree, hints),
            "action_index": action_index,
            "observation_artifact": artifact,
            "focused_title": focused_title,
        }

    @staticmethod
    def _write_artifact(payload: dict[str, Any], observed_at: float) -> dict[str, Any]:
        artifact_dir = ROOT / "comms" / "observations"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        path = artifact_dir / f"{int(observed_at * 1000)}.json"
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        tmp.replace(path)
        return {"path": path.relative_to(ROOT).as_posix(), "size": path.stat().st_size, "kind": "raw_full_observation"}