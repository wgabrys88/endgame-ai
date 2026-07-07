from __future__ import annotations

import ctypes
import importlib
import json
import pathlib
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import Any

import comtypes
import comtypes.client
import core_desktop as desktop

ROOT = pathlib.Path(__file__).resolve().parent
user32 = ctypes.windll.user32

# ============================================================================
# UIA CONSTANTS - minimal, deterministic
# ============================================================================

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

# Property IDs we actually use (13 total)
PID_RUNTIME_ID = _const("UIA_RuntimeIdPropertyId", 30000)
PID_BOUNDING_RECT = _const("UIA_BoundingRectanglePropertyId", 30001)
PID_CONTROL_TYPE = _const("UIA_ControlTypePropertyId", 30003)
PID_NAME = _const("UIA_NamePropertyId", 30005)
PID_AUTOMATION_ID = _const("UIA_AutomationIdPropertyId", 30011)
PID_CLASS_NAME = _const("UIA_ClassNamePropertyId", 30012)
PID_ENABLED = _const("UIA_IsEnabledPropertyId", 30010)
PID_OFFSCREEN = _const("UIA_IsOffscreenPropertyId", 30022)
PID_HWND = _const("UIA_NativeWindowHandlePropertyId", 30020)
PID_FRAMEWORK = _const("UIA_FrameworkIdPropertyId", 30024)
PID_KEYBOARD_FOCUSABLE = _const("UIA_IsKeyboardFocusablePropertyId", 30008)
PID_CONTENT_ELEMENT = _const("UIA_IsContentElementPropertyId", 30015)

SCAN_PROPERTY_IDS = [
    PID_RUNTIME_ID, PID_BOUNDING_RECT, PID_CONTROL_TYPE, PID_NAME,
    PID_AUTOMATION_ID, PID_CLASS_NAME, PID_ENABLED, PID_OFFSCREEN,
    PID_HWND, PID_FRAMEWORK, PID_KEYBOARD_FOCUSABLE, PID_CONTENT_ELEMENT,
]

# Pattern IDs we actually use (5 total)
PID_VALUE_PATTERN = _const("UIA_ValuePatternId", 10002)
PID_TEXT_PATTERN = _const("UIA_TextPatternId", 10014)
PID_LEGACY_PATTERN = _const("UIA_LegacyIAccessiblePatternId", 10018)
PID_INVOKE_PATTERN = _const("UIA_InvokePatternId", 10000)
PID_SCROLL_PATTERN = _const("UIA_ScrollPatternId", 10004)

SCAN_PATTERN_IDS = [
    PID_VALUE_PATTERN, PID_TEXT_PATTERN, PID_LEGACY_PATTERN,
    PID_INVOKE_PATTERN, PID_SCROLL_PATTERN,
]

CONTROL_TYPE_NAMES: dict[int, str] = {}
for attr in dir(uia):
    if attr.startswith("UIA_") and attr.endswith("ControlTypeId"):
        val = getattr(uia, attr, None)
        if isinstance(val, int):
            CONTROL_TYPE_NAMES[val] = attr.replace("UIA_", "").replace("ControlTypeId", "")

def control_type_name(control_type_id: int) -> str:
    return CONTROL_TYPE_NAMES.get(control_type_id, f"ControlType({control_type_id})")

# Action role mapping - single source of truth
CLICK_ROLES = {"Button", "Calendar", "CheckBox", "Hyperlink", "ListItem", "MenuItem", "RadioButton", "Tab", "TabItem", "TreeItem", "DataItem", "SplitButton"}
WRITE_ROLES = {"Edit", "ComboBox", "Spinner", "Document"}
READ_ROLES = {"Text", "ListItem"}
SCROLL_ROLES = {"List", "ScrollBar", "Slider", "Tree", "DataGrid"}
CONTAINER_ROLES = {"Pane", "Document", "Window", "Group", "List", "Tree", "DataGrid", "Tab", "Menu", "ToolBar", "Table", "MenuBar", "SplitPane", "ScrollViewer"}
JUNK_ROLES = {"TitleBar", "ScrollBar", "StatusBar", "ProgressBar", "Separator", "ToolTip", "Image", "Custom", "Header", "HeaderItem"}

DESKTOP_ICON_NAMES = {
    "Recycle Bin", "TeamViewer", "CherryTree", "LM Studio", "GitHub Desktop",
    "MPC-HC", "FileZilla", "Insomnia", "Microsoft Teams", "OneDrive",
    "OneNote", "Microsoft 365 Copilot", "HWMonitor", "Tiled", "Blender",
    "Blender 4.1", "MPC-HC x64",
}

def action_for_role(role: str, class_name: str = "") -> str:
    if role in CLICK_ROLES: return "click"
    if role in WRITE_ROLES: return "write"
    if role in READ_ROLES: return "read"
    if role == "Pane" and class_name == "Scintilla": return "write"
    if role in SCROLL_ROLES: return "scroll"
    return ""

def is_desktop_leakage(node: "RawNode") -> bool:
    """Generic detection: any List named 'Desktop' with scroll = SysListView32 leakage."""
    act = action_for_role(node.role, node.class_name)
    if node.role == "List" and node.name == "Desktop" and "scroll" in (act or ""):
        return True
    if node.role == "ListItem" and node.name in DESKTOP_ICON_NAMES:
        return True
    return False


def get_window_z_order() -> list[int]:
    """Get visible window hwnds ordered by z-index (bottom to top)."""
    z_list = []
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    
    def callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)) or rect.right <= rect.left or rect.bottom <= rect.top:
            return True
        z_list.append(int(hwnd))
        return True
    
    try:
        user32.EnumWindows(EnumWindowsProc(callback), 0)
    except Exception:
        pass
    return z_list


# ============================================================================
# RAW NODE - single flat structure from UIA
# ============================================================================

@dataclass
class RawNode:
    """Single raw UIA element - no hierarchy, no filtering."""
    id: str                    # runtime_id based unique key
    role: str                  # control type name
    name: str                  # UIA Name property
    automation_id: str = ""
    class_name: str = ""
    hwnd: int = 0
    framework_id: str = ""
    rect: dict[str, int] = field(default_factory=dict)
    px: int = 0
    py: int = 0
    enabled: bool = True
    offscreen: bool = False
    runtime_id: list[int] = field(default_factory=list)
    text_full: str = ""
    value: str = ""
    patterns: list[str] = field(default_factory=list)
    pattern_values: dict[str, str] = field(default_factory=dict)  # pattern_name -> extracted text
    depth: int = 0
    parent_runtime_id: list[int] = field(default_factory=list)
    is_keyboard_focusable: bool = False
    is_content_element: bool = False
    action: str = ""


class UiaVariant:
    @staticmethod
    def to_int(v: Any) -> int:
        if v is None: return 0
        if hasattr(v, "value"): v = v.value
        try: return int(v)
        except (TypeError, ValueError): return 0

    @staticmethod
    def to_str(v: Any) -> str:
        if v is None: return ""
        if hasattr(v, "value"): v = v.value
        return "" if v is None else str(v)

    @staticmethod
    def to_bool(v: Any) -> bool:
        if v is None: return False
        if hasattr(v, "value"): v = v.value
        return bool(v)

    @staticmethod
    def to_rect(v: Any) -> dict[str, int]:
        if v is None: return {"left": 0, "top": 0, "right": 0, "bottom": 0}
        try:
            val = v.value if hasattr(v, "value") else v
            if isinstance(val, (tuple, list)) and len(val) >= 4:
                left, top = int(val[0]), int(val[1])
                third, fourth = float(val[2]), float(val[3])
                if third > left or fourth > top:
                    return {"left": left, "top": top, "right": int(third), "bottom": int(fourth)}
                return {"left": left, "top": top, "right": left + int(third), "bottom": top + int(fourth)}
            left_attr = getattr(val, "left", None)
            if left_attr is not None:
                return {"left": int(left_attr), "top": int(getattr(val, "top", 0)), 
                        "right": int(getattr(val, "right", 0)), "bottom": int(getattr(val, "bottom", 0))}
        except Exception:
            pass
        return {"left": 0, "top": 0, "right": 0, "bottom": 0}

    @staticmethod
    def to_runtime_id(v: Any) -> list[int]:
        if v is None: return []
        try:
            val = v.value if hasattr(v, "value") else v
            return [int(x) for x in list(val)] if val else []
        except Exception:
            return []


def _node_id(runtime_id: list[int], hwnd: int, rect: dict[str, int]) -> str:
    if runtime_id: return "e_" + "_".join(map(str, runtime_id))
    return f"e_{hwnd}_{rect['left']}_{rect['top']}"


def _get_cached(element: Any, prop_id: int) -> Any:
    try: return element.GetCachedPropertyValue(prop_id)
    except Exception: return None


def _get_current(element: Any, prop_id: int) -> Any:
    try: return element.GetCurrentPropertyValue(prop_id)
    except Exception: return None


def _get_pattern(element: Any, pattern_id: int) -> tuple[Any | None, str]:
    try: return element.GetCachedPattern(pattern_id), "cached"
    except Exception: pass
    try: return element.GetCurrentPattern(pattern_id), "current"
    except Exception: pass
    return None, ""


# ============================================================================
# PHASE 1: RAW GATHERING - mouse probe + UIA subtree harvest
# ============================================================================

class UiaScanner:
    """Phase 1: raw UIA element harvest via R2 mouse probe grid."""

    def __init__(self, config: dict[str, Any], desktop_instance: Any = None):
        self.cfg = config
        self.desktop_instance = desktop_instance
        self.automation = desktop_instance.automation if desktop_instance and hasattr(desktop_instance, 'automation') else uia.CUIAutomation()
        self._z_counter = 0

    def _next_z(self) -> int:
        self._z_counter += 1
        return self._z_counter

    def _extract_pattern_text(self, pattern: Any, label: str) -> dict[str, str]:
        """Extract text from UIA patterns - Value, Text, LegacyIAccessible."""
        out = {}
        if pattern is None:
            return out
        try:
            if label == "Value":
                val = getattr(pattern, "Value", None)
                if val is not None:
                    out["value"] = str(val)
            elif label == "Text":
                doc = getattr(pattern, "DocumentRange", None)
                if doc is not None:
                    try:
                        text = doc.GetText(-1)
                        if text and str(text).strip():
                            out["text"] = str(text)
                    except Exception:
                        pass
                try:
                    ranges = pattern.GetVisibleRanges()
                    if ranges is not None:
                        texts = []
                        length = int(getattr(ranges, "Length", 0))
                        for i in range(length):
                            try:
                                t = ranges.GetElement(i).GetText(-1)
                                if t and str(t).strip():
                                    texts.append(str(t))
                            except Exception:
                                continue
                        if texts:
                            out["text_ranges"] = "\n".join(texts)
                except Exception:
                    pass
            elif label == "LegacyIAccessible":
                for key in ("Value", "Name", "Description"):
                    val = getattr(pattern, key, None)
                    if val is not None and str(val).strip() not in ("", "0"):
                        out[f"legacy_{key.lower()}"] = str(val)
        except Exception:
            pass
        return out

    def element_to_raw(self, element: Any, parent_runtime_id: list[int] | None = None, depth: int = 0) -> RawNode | None:
        """Convert single UIA element to RawNode."""
        try:
            rect = UiaVariant.to_rect(_get_cached(element, PID_BOUNDING_RECT))
            if rect["right"] <= rect["left"] or rect["bottom"] <= rect["top"]:
                rect = UiaVariant.to_rect(_get_current(element, PID_BOUNDING_RECT))
            if rect["right"] <= rect["left"] or rect["bottom"] <= rect["top"]:
                return None

            runtime_id = UiaVariant.to_runtime_id(_get_cached(element, PID_RUNTIME_ID)) or \
                         UiaVariant.to_runtime_id(_get_current(element, PID_RUNTIME_ID))
            hwnd = UiaVariant.to_int(_get_cached(element, PID_HWND))
            role_id = UiaVariant.to_int(_get_cached(element, PID_CONTROL_TYPE)) or \
                      UiaVariant.to_int(_get_current(element, PID_CONTROL_TYPE))
            name = UiaVariant.to_str(_get_cached(element, PID_NAME)) or \
                   UiaVariant.to_str(_get_current(element, PID_NAME))

            role = control_type_name(role_id)
            automation_id = UiaVariant.to_str(_get_cached(element, PID_AUTOMATION_ID))
            class_name = UiaVariant.to_str(_get_cached(element, PID_CLASS_NAME))
            framework_id = UiaVariant.to_str(_get_cached(element, PID_FRAMEWORK))
            enabled = UiaVariant.to_bool(_get_cached(element, PID_ENABLED))
            offscreen = UiaVariant.to_bool(_get_cached(element, PID_OFFSCREEN))
            is_keyboard_focusable = UiaVariant.to_bool(_get_cached(element, PID_KEYBOARD_FOCUSABLE)) or \
                                    UiaVariant.to_bool(_get_current(element, PID_KEYBOARD_FOCUSABLE))
            is_content_element = UiaVariant.to_bool(_get_cached(element, PID_CONTENT_ELEMENT)) or \
                                 UiaVariant.to_bool(_get_current(element, PID_CONTENT_ELEMENT))

            # Extract text from patterns (Value, Text, Legacy)
            pattern_values = {}
            for pid, label in [
                (PID_VALUE_PATTERN, "Value"),
                (PID_TEXT_PATTERN, "Text"),
                (PID_LEGACY_PATTERN, "LegacyIAccessible"),
            ]:
                pattern, _ = _get_pattern(element, pid)
                if pattern:
                    extracted = self._extract_pattern_text(pattern, label)
                    pattern_values.update(extracted)

            # Determine best text representation
            text_full = (pattern_values.get("text") or pattern_values.get("text_ranges") or
                        pattern_values.get("value") or pattern_values.get("legacy_value") or
                        pattern_values.get("legacy_name") or name or "")
            value = pattern_values.get("value") or pattern_values.get("legacy_value") or ""

            action = action_for_role(role, class_name)
            px = (rect["left"] + rect["right"]) // 2
            py = (rect["top"] + rect["bottom"]) // 2

            return RawNode(
                id=_node_id(runtime_id, hwnd, rect),
                role=role,
                name=name,
                automation_id=automation_id,
                class_name=class_name,
                hwnd=hwnd,
                framework_id=framework_id,
                rect=rect,
                px=px,
                py=py,
                enabled=enabled,
                offscreen=offscreen,
                runtime_id=runtime_id,
                text_full=text_full,
                value=value,
                patterns=list(pattern_values.keys()),
                pattern_values=pattern_values,
                depth=depth,
                parent_runtime_id=parent_runtime_id or [],
                is_keyboard_focusable=is_keyboard_focusable,
                is_content_element=is_content_element,
                action=action,
            )
        except Exception:
            return None

    def harvest_subtree(self, root_element: Any, max_nodes: int, parent_runtime_id: list[int] | None = None, depth: int = 0) -> list[RawNode]:
        """Harvest entire subtree from root element via UIA cache."""
        nodes: list[RawNode] = []
        seen: set[str] = set()

        def add_element(el: Any, p_rid: list[int], d: int):
            if len(nodes) >= max_nodes:
                return
            node = self.element_to_raw(el, p_rid, d)
            if node is None or node.id in seen:
                return
            seen.add(node.id)
            nodes.append(node)
            return node

        # Add root
        root_node = add_element(root_element, parent_runtime_id or [], depth)
        if not root_node:
            return nodes

        # Harvest descendants via cached subtree
        try:
            true_cond = self.automation.CreateTrueCondition()
            arr = root_element.FindAllBuildCache(TreeScope_Descendants, true_cond, self._build_cache_request())
            if arr is not None:
                length = int(getattr(arr, "Length", 0))
                for i in range(length):
                    if len(nodes) >= max_nodes:
                        break
                    try:
                        el = arr.GetElement(i)
                        # Parent is previous element at same or lower depth (approximation)
                        add_element(el, root_node.runtime_id, depth + 1)
                    except Exception:
                        continue
        except Exception:
            pass
        return nodes

    def _build_cache_request(self):
        req = self.automation.CreateCacheRequest()
        req.TreeScope = TreeScope_Subtree
        for pid in SCAN_PROPERTY_IDS:
            req.AddProperty(pid)
        for pid in SCAN_PATTERN_IDS:
            req.AddPattern(pid)
        return req

    def _build_hit_cache_request(self):
        req = self._build_cache_request()
        req.TreeScope = TreeScope_Element
        return req


def gather_raw(config: dict[str, Any], desktop: Any) -> dict[str, Any]:
    """Phase 1 entry point: R2 probe grid → raw UIA nodes."""
    scan_cfg = config.get("scan", {})
    step_px = int(scan_cfg.get("step_px", 96))
    delay_ms = int(scan_cfg.get("delay_ms", 0))
    max_subtree = int(scan_cfg.get("max_subtree_nodes_per_point", 5000))
    max_total = int(scan_cfg.get("max_total_nodes", 20000))

    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)

    # R2 sequence points
    margin = max(8, step_px // 4)
    usable_w = max(1, sw - 2 * margin)
    usable_h = max(1, sh - 2 * margin)
    cols = max(1, usable_w // step_px)
    rows = max(1, usable_h // step_px)
    count = (cols + 1) * (rows + 1)
    g = 1.32471795724474602596
    ax, ay = 1.0 / g, 1.0 / (g * g)

    points = []
    seen_cells = set()
    for i in range(count):
        fx = (0.5 + ax * (i + 1)) % 1.0
        fy = (0.5 + ay * (i + 1)) % 1.0
        x = margin + int(fx * usable_w)
        y = margin + int(fy * usable_h)
        cell = (x // step_px, y // step_px)
        if cell in seen_cells:
            continue
        seen_cells.add(cell)
        points.append((min(sw - 1, max(0, x)), min(sh - 1, max(0, y))))

    scanner = UiaScanner(config, desktop)
    index: dict[str, RawNode] = {}
    saturated_hits = set()
    probes = 0
    t0 = time.time()

    saved = wintypes.POINT()
    had_cursor = bool(user32.GetCursorPos(ctypes.byref(saved)))
    try:
        for x, y in points:
            if len(index) >= max_total:
                break
            user32.SetCursorPos(int(x), int(y))
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)
            pt = wintypes.POINT(int(x), int(y))
            try:
                root = scanner.automation.ElementFromPointBuildCache(pt, scanner._build_hit_cache_request())
            except Exception:
                root = scanner.automation.ElementFromPoint(pt)
            if root is None:
                continue

            hit_key, role = _hit_key_from_element(root)
            if hit_key in saturated_hits or (hit_key in index and role not in CONTAINER_ROLES):
                continue

            nodes = scanner.harvest_subtree(root, max_subtree)
            added = 0
            for node in nodes:
                if is_desktop_leakage(node):
                    continue
                prev = index.get(node.id)
                if prev is None:
                    index[node.id] = node
                    added += 1
                else:
                    # Merge: keep longer text
                    if node.text_full and (not prev.text_full or len(node.text_full) > len(prev.text_full)):
                        prev.text_full = node.text_full
                    if node.value and (not prev.value or len(node.value) > len(prev.value)):
                        prev.value = node.value
                    for k, v in node.pattern_values.items():
                        if k not in prev.pattern_values or len(v) > len(prev.pattern_values.get(k, "")):
                            prev.pattern_values[k] = v
                    prev.patterns = sorted(set(prev.patterns) | set(node.patterns))

            if hit_key and (added == 0 or len(nodes) >= max_subtree):
                saturated_hits.add(hit_key)
    finally:
        if had_cursor:
            try: user32.SetCursorPos(saved.x, saved.y)
            except Exception: pass

    return {
        "nodes": list(index.values()),
        "screen": {"width": sw, "height": sh},
        "scan_stats": {
            "probes": len(points),
            "unique_nodes": len(index),
            "elapsed_s": round(time.time() - t0, 3),
        },
    }


def _hit_key_from_element(element: Any) -> tuple[str, str]:
    runtime_id = UiaVariant.to_runtime_id(_get_cached(element, PID_RUNTIME_ID)) or \
                 UiaVariant.to_runtime_id(_get_current(element, PID_RUNTIME_ID))
    rect = UiaVariant.to_rect(_get_cached(element, PID_BOUNDING_RECT))
    if rect["right"] <= rect["left"] or rect["bottom"] <= rect["top"]:
        rect = UiaVariant.to_rect(_get_current(element, PID_BOUNDING_RECT))
    hwnd = UiaVariant.to_int(_get_cached(element, PID_HWND)) or \
           UiaVariant.to_int(_get_current(element, PID_HWND))
    role_id = UiaVariant.to_int(_get_cached(element, PID_CONTROL_TYPE)) or \
              UiaVariant.to_int(_get_current(element, PID_CONTROL_TYPE))
    return _node_id(runtime_id, hwnd, rect), control_type_name(role_id)


# ============================================================================
# PHASE 2: FILTER - reduce raw nodes to LLM-relevant actionable elements
# ============================================================================

def filter_raw(raw_nodes: list[RawNode], config: dict[str, Any], screen: dict[str, int]) -> dict[str, Any]:
    """Phase 2: filter raw nodes → actionable elements + text hints."""
    filt = config.get("filter") or {}
    max_action = int(filt.get("max_action_nodes", 5000))
    max_depth = int(filt.get("max_depth", 10))
    max_children_per_window = int(filt.get("max_children_per_window", 100))
    require_interactive = bool(filt.get("require_interactive", False))
    text_max = int(filt.get("text_hint_max", 10000))

    # Get window z-order for layering
    z_order = get_window_z_order()
    hwnd_to_z = {hwnd: i for i, hwnd in enumerate(z_order)}

    # Rank: named/textual first, on-screen first
    ranked = sorted(
        [n for n in raw_nodes if not n.offscreen and n.role not in JUNK_ROLES],
        key=lambda n: (0 if n.name or n.text_full else 1, 0 if not n.offscreen else 1)
    )

    # Select actionable elements
    action_elements: dict[str, dict[str, Any]] = {}
    text_hints: dict[str, str] = {}

    for node in ranked:
        if len(action_elements) >= max_action:
            break
        action = node.action
        if require_interactive and not action:
            continue
        if action or not require_interactive:
            label = (node.text_full or node.name or "")[:text_max]
            if label and label != (node.name or ""):
                text_hints[node.id] = label
            if action:
                action_elements[node.id] = {
                    "id": node.id,
                    "short_id": "",  # assigned in MAP phase
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
                    "depth": node.depth,
                }

    return {
        "action_elements": action_elements,
        "text_hints": text_hints,
        "hwnd_to_z": hwnd_to_z,
    }


# ============================================================================
# PHASE 3: MAP - build hierarchy + assign hierarchical short IDs (W0E1C1D0...)
# ============================================================================

def build_tree_and_map(action_elements: dict[str, dict[str, Any]], text_hints: dict[str, str],
                       raw_nodes: list[RawNode], hwnd_to_z: dict[int, int], screen: dict[str, int],
                       config: dict[str, Any]) -> dict[str, Any]:
    """Phase 3: construct window→element tree + assign hierarchical short IDs."""
    filt = config.get("filter") or {}
    max_depth = int(filt.get("max_depth", 10))
    max_children_per_window = int(filt.get("max_children_per_window", 100))

    # Build window list from raw nodes (unique hwnds with Window role)
    window_nodes: dict[int, dict[str, Any]] = {}
    for node in raw_nodes:
        if node.role == "Window" and node.hwnd and node.hwnd not in window_nodes:
            window_nodes[node.hwnd] = {
                "hwnd": node.hwnd,
                "title": node.name or node.text_full or f"Window_{node.hwnd}",
                "class_name": node.class_name,
                "framework_id": node.framework_id,
                "rect": node.rect,
                "z_order": hwnd_to_z.get(node.hwnd, 0),
                "children": [],
            }

    # Sort windows by z-order (bottom to top)
    sorted_windows = sorted(window_nodes.values(), key=lambda w: w["z_order"])

    # Build root
    root = {
        "id": "W0",
        "role": "Screen",
        "name": "Screen",
        "title": "Desktop",
        "rect": {"left": 0, "top": 0, "right": screen["width"], "bottom": screen["height"]},
        "fresh_scan": True,
        "observed_at": time.time(),
        "children": [],
    }
    node_index: dict[str, dict[str, Any]] = {"W0": {k: v for k, v in root.items() if k != "children"}}
    window_child_counts: dict[int, int] = {w["hwnd"]: 0 for w in sorted_windows}

    # Attach windows as children of root
    for w in sorted_windows:
        w_token = f"W{len(root['children']) + 1}"
        w["id"] = w_token
        w["parent_id"] = "W0"
        root["children"].append(w)
        node_index[w_token] = {k: v for k, v in w.items() if k != "children"}

    # Attach action elements to their window by hwnd containment
    for elem in action_elements.values():
        hwnd = elem["hwnd"]
        parent_hwnd = None
        for w in sorted_windows:
            r = w["rect"]
            if r.get("left", 0) <= elem["px"] <= r.get("right", 0) and \
               r.get("top", 0) <= elem["py"] <= r.get("bottom", 0):
                parent_hwnd = w["hwnd"]
                break

        parent_id = "W0"
        if parent_hwnd is not None:
            parent_id = next((w["id"] for w in sorted_windows if w["hwnd"] == parent_hwnd), "W0")
        if parent_hwnd is not None and parent_id != "W0" and window_child_counts.get(parent_hwnd, 0) >= max_children_per_window:
            continue

        elem["parent_id"] = parent_id
        if parent_id == "W0" or parent_hwnd is None:
            root["children"].append(elem)
        else:
            window_nodes[parent_hwnd]["children"].append(elem)
            window_child_counts[parent_hwnd] = window_child_counts.get(parent_hwnd, 0) + 1

        node_index[elem["id"]] = {k: v for k, v in elem.items() if k != "children"}

    # Sort children recursively by z-order, then top, then left, then area
    def rect_area(r): return max(0, r.get("right", 0) - r.get("left", 0)) * max(0, r.get("bottom", 0) - r.get("top", 0))
    def sort_recursive(node: dict[str, Any]):
        kids = node.get("children", [])
        if isinstance(kids, list):
            kids.sort(key=lambda c: (c.get("z_order", 0), c.get("rect", {}).get("top", 0),
                                      c.get("rect", {}).get("left", 0), rect_area(c.get("rect", {}))))
            for c in kids:
                if isinstance(c, dict):
                    sort_recursive(c)
    sort_recursive(root)

    # Prune by max_depth
    def prune_depth(node: dict[str, Any], d: int = 0):
        kids = node.get("children", [])
        if isinstance(kids, list):
            if d >= max_depth:
                node["children"] = []
            else:
                for c in kids:
                    if isinstance(c, dict):
                        prune_depth(c, d + 1)
    prune_depth(root)

    # Assign hierarchical short IDs: W0, W1, W1E1, W1E1C1, W1E1C1D1...
    short_id_map: dict[str, str] = {}
    elem_counters: dict[str, int] = {}

    def assign_ids(node: dict[str, Any], parent_short: str = ""):
        nid = node.get("id", "")
        if nid == "W0":
            short = "W0"
        elif nid.startswith("W") and node.get("parent_id") == "W0":
            short = nid  # W1, W2...
        elif parent_short and parent_short.startswith("W") and "E" in parent_short:
            # Parent is W1E1 → child is W1E1C1
            key = f"{parent_short}_child"
            elem_counters[key] = elem_counters.get(key, 0) + 1
            short = f"{parent_short}C{elem_counters[key]}"
        elif parent_short and parent_short.startswith("W") and parent_short != "W0":
            # Parent is W1 → child is W1E1
            elem_counters[parent_short] = elem_counters.get(parent_short, 0) + 1
            short = f"{parent_short}E{elem_counters[parent_short]}"
        else:
            short = nid

        short_id_map[nid] = short
        node["short_id"] = short

        for child in node.get("children", []):
            if isinstance(child, dict):
                assign_ids(child, short)

    assign_ids(root)

    # Rewrite node_index and action_elements with short_ids as keys
    node_index_by_short = {}
    for oid, ndata in node_index.items():
        sid = short_id_map.get(oid, oid)
        ndata["short_id"] = sid
        node_index_by_short[sid] = ndata

    action_index_by_short = {}
    for oid, edata in action_elements.items():
        sid = short_id_map.get(oid, oid)
        edata["short_id"] = sid
        action_index_by_short[sid] = edata

    # Render desktop_tree_text using short_ids
    def clean(v: Any) -> str:
        return " ".join(str(v or "").replace("\r", " ").replace("\n", " ").split())

    lines = ["W0 Screen Desktop"]
    def render(node: dict[str, Any], indent: int = 1):
        sid = node.get("short_id", node.get("id", ""))
        role = str(node.get("role", ""))
        name = clean(node.get("name", "") or node.get("title", ""))
        action = str(node.get("action", ""))
        parts = [sid] if sid else []
        if role: parts.append(role)
        if name: parts.append(name)
        if action: parts.append(f"[{action}]")
        hint = text_hints.get(node.get("id", ""), "")
        if hint and hint not in name:
            parts.append(f"~{hint}")
        lines.append("  " * indent + " ".join(parts))
        for child in node.get("children", []):
            if isinstance(child, dict):
                render(child, indent + 1)

    for child in root.get("children", []):
        if isinstance(child, dict):
            render(child, 1)

    return {
        "root": root,
        "node_index": node_index_by_short,
        "action_index": action_index_by_short,
        "desktop_tree_text": "\n".join(lines),
        "window_count": len(sorted_windows),
        "element_count": len(action_index_by_short),
        "window_z_order": [w["hwnd"] for w in sorted_windows],
    }


# ============================================================================
# PUBLIC API - observe() integrates all 3 phases
# ============================================================================

def observe(desktop: Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Main entry: RAW → FILTER → MAP → observation dict."""
    cfg = dict(config or {})
    if not cfg.get("enabled", True):
        raise RuntimeError("hover_cache observation is disabled")

    # Phase 1: RAW gathering
    gathered = gather_raw(cfg, desktop)

    # Phase 2: FILTER
    filtered = filter_raw(gathered["nodes"], cfg, gathered["screen"])

    # Phase 3: MAP
    mapped = build_tree_and_map(
        filtered["action_elements"],
        filtered["text_hints"],
        gathered["nodes"],
        filtered["hwnd_to_z"],
        gathered["screen"],
        cfg,
    )

    observed_at = time.time()
    artifact = {
        "observed_at": observed_at,
        "fresh_scan": True,
        "scan_config": cfg.get("scan", {}),
        "scan_stats": gathered["scan_stats"],
        "desktop_tree": {
            "id": "W0",
            "role": "Screen",
            "fresh_scan": True,
            "observed_at": observed_at,
            "root": mapped["root"],
            "node_index": mapped["node_index"],
            "window_count": mapped["window_count"],
            "element_count": mapped["element_count"],
            "window_z_order": mapped["window_z_order"],
        },
        "action_index": mapped["action_index"],
        "desktop_tree_text": mapped["desktop_tree_text"],
    }

    # Store for capability runtime
    desktop._last_desktop_tree = artifact["desktop_tree"]
    desktop._last_action_index = mapped["action_index"]

    return {
        "observed_at": observed_at,
        "fresh_scan": True,
        "desktop_tree": artifact["desktop_tree"],
        "desktop_tree_text": mapped["desktop_tree_text"],
        "action_index": mapped["action_index"],
        "observation_artifact": artifact,
    }
