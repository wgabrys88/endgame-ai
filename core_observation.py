import ctypes
import importlib
import sys
import time
from ctypes import wintypes
from typing import Any

import comtypes
import comtypes.client

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


TreeScope_Element = _const("TreeScope_Element", 1)
TreeScope_Descendants = _const("TreeScope_Descendants", 4)
TreeScope_Subtree = _const("TreeScope_Subtree", 7)

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
    PID_RUNTIME_ID, PID_BOUNDING_RECT, PID_CONTROL_TYPE, PID_NAME, PID_AUTOMATION_ID, PID_CLASS_NAME,
    PID_ENABLED, PID_OFFSCREEN, PID_HWND, PID_FRAMEWORK, PID_KEYBOARD_FOCUSABLE, PID_CONTENT_ELEMENT,
]

PID_VALUE_PATTERN = _const("UIA_ValuePatternId", 10002)
PID_TEXT_PATTERN = _const("UIA_TextPatternId", 10014)
PID_LEGACY_PATTERN = _const("UIA_LegacyIAccessiblePatternId", 10018)
PID_INVOKE_PATTERN = _const("UIA_InvokePatternId", 10000)
PID_SCROLL_PATTERN = _const("UIA_ScrollPatternId", 10004)
SCAN_PATTERN_IDS = [PID_VALUE_PATTERN, PID_TEXT_PATTERN, PID_LEGACY_PATTERN, PID_INVOKE_PATTERN, PID_SCROLL_PATTERN]

CONTROL_TYPE_NAMES = {
    getattr(uia, attr): attr.replace("UIA_", "").replace("ControlTypeId", "")
    for attr in dir(uia)
    if attr.startswith("UIA_") and attr.endswith("ControlTypeId") and isinstance(getattr(uia, attr, None), int)
}
CLICK_ROLES = {"Button", "Calendar", "CheckBox", "Hyperlink", "ListItem", "MenuItem", "RadioButton", "Tab", "TabItem", "TreeItem", "DataItem", "SplitButton"}
WRITE_ROLES = {"Edit", "ComboBox", "Spinner", "Document"}
READ_ROLES = {"Text", "ListItem"}
SCROLL_ROLES = {"List", "ScrollBar", "Slider", "Tree", "DataGrid"}
CONTAINER_ROLES = {"Pane", "Document", "Window", "Group", "List", "Tree", "DataGrid", "Tab", "Menu", "ToolBar", "Table", "MenuBar", "SplitPane", "ScrollViewer"}
JUNK_ROLES = {"TitleBar", "ScrollBar", "StatusBar", "ProgressBar", "Separator", "ToolTip", "Image", "Custom", "Header", "HeaderItem"}
DESKTOP_ICON_NAMES = {"Recycle Bin", "TeamViewer", "CherryTree", "LM Studio", "GitHub Desktop", "MPC-HC", "FileZilla", "Insomnia", "Microsoft Teams", "OneDrive", "OneNote", "Microsoft 365 Copilot", "HWMonitor", "Tiled", "Blender", "Blender 4.1", "MPC-HC x64"}


def control_type_name(control_type_id: int) -> str:
    return CONTROL_TYPE_NAMES.get(control_type_id, f"ControlType({control_type_id})")


def action_for_role(role: str, class_name: str = "") -> str:
    if role in CLICK_ROLES:
        return "click"
    if role in WRITE_ROLES or (role == "Pane" and class_name == "Scintilla"):
        return "write"
    if role in READ_ROLES:
        return "read"
    if role in SCROLL_ROLES:
        return "scroll"
    return ""


def is_desktop_leakage(node: dict[str, Any]) -> bool:
    return (
        node["role"] == "List" and node["name"] == "Desktop" and action_for_role(node["role"], node["class_name"]) == "scroll"
    ) or (node["role"] == "ListItem" and node["name"] in DESKTOP_ICON_NAMES)


def get_window_z_order() -> list[int]:
    out: list[int] = []
    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _):
        rect = wintypes.RECT()
        if user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd) and user32.GetWindowTextLengthW(hwnd) > 0 and user32.GetWindowRect(hwnd, ctypes.byref(rect)) and rect.right > rect.left and rect.bottom > rect.top:
            out.append(int(hwnd))
        return True

    try:
        user32.EnumWindows(enum_proc(callback), 0)
    except Exception:
        pass
    return out


def _unwrap(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _to_int(v: Any) -> int:
    try:
        return int(_unwrap(v))
    except (TypeError, ValueError):
        return 0


def _to_str(v: Any) -> str:
    v = _unwrap(v)
    return "" if v is None else str(v)


def _to_bool(v: Any) -> bool:
    return bool(_unwrap(v)) if v is not None else False


def _to_rect(v: Any) -> dict[str, int]:
    val = _unwrap(v)
    try:
        if isinstance(val, (tuple, list)) and len(val) >= 4:
            left, top = int(val[0]), int(val[1])
            third, fourth = float(val[2]), float(val[3])
            if third > left or fourth > top:
                return {"left": left, "top": top, "right": int(third), "bottom": int(fourth)}
            return {"left": left, "top": top, "right": left + int(third), "bottom": top + int(fourth)}
        if getattr(val, "left", None) is not None:
            return {"left": int(val.left), "top": int(getattr(val, "top", 0)), "right": int(getattr(val, "right", 0)), "bottom": int(getattr(val, "bottom", 0))}
    except Exception:
        pass
    return {"left": 0, "top": 0, "right": 0, "bottom": 0}


def _to_runtime_id(v: Any) -> list[int]:
    try:
        val = _unwrap(v)
        return [int(x) for x in list(val)] if val else []
    except Exception:
        return []


def _node_id(runtime_id: list[int], hwnd: int, rect: dict[str, int]) -> str:
    # Hierarchical shortest practical ID: prefer compact runtime-derived or hwnd+rect for action_index / focused_elements.
    # No long strings; keeps uniqueness for node_by_id / click_node while reducing prompt bloat.
    if runtime_id:
        short = "_".join(map(str, runtime_id[-3:])) if len(runtime_id) > 3 else "_".join(map(str, runtime_id))
        return f"e_{short}"
    return f"e_{hwnd}_{rect.get('left',0)}_{rect.get('top',0)}"


def _cached(element: Any, prop_id: int) -> Any:
    try:
        return element.GetCachedPropertyValue(prop_id)
    except Exception:
        return None


def _current(element: Any, prop_id: int) -> Any:
    try:
        return element.GetCurrentPropertyValue(prop_id)
    except Exception:
        return None


def _pattern(element: Any, pattern_id: int) -> Any:
    try:
        return element.GetCachedPattern(pattern_id)
    except Exception:
        try:
            return element.GetCurrentPattern(pattern_id)
        except Exception:
            return None


class UiaScanner:
    def __init__(self, config: dict[str, Any], desktop_instance: Any = None):
        self.cfg = config
        self.automation = desktop_instance.automation if desktop_instance and hasattr(desktop_instance, "automation") else comtypes.client.CreateObject(uia.CUIAutomation, interface=uia.IUIAutomation)

    def _cache(self, scope: int = TreeScope_Subtree):
        req = self.automation.CreateCacheRequest()
        req.TreeScope = scope
        for pid in SCAN_PROPERTY_IDS:
            req.AddProperty(pid)
        for pid in SCAN_PATTERN_IDS:
            req.AddPattern(pid)
        return req

    def _pattern_text(self, pattern: Any, label: str) -> dict[str, str]:
        out: dict[str, str] = {}
        if pattern is None:
            return out
        try:
            if label == "Value" and getattr(pattern, "Value", None) is not None:
                out["value"] = str(pattern.Value)
            elif label == "Text":
                doc = getattr(pattern, "DocumentRange", None)
                if doc is not None:
                    text = doc.GetText(-1)
                    if text and str(text).strip():
                        out["text"] = str(text)
                ranges = pattern.GetVisibleRanges()
                texts = []
                for i in range(int(getattr(ranges, "Length", 0)) if ranges is not None else 0):
                    t = ranges.GetElement(i).GetText(-1)
                    if t and str(t).strip():
                        texts.append(str(t))
                if texts:
                    out["text_ranges"] = "\n".join(texts)
            elif label == "LegacyIAccessible":
                for key in ("Value", "Name", "Description"):
                    val = getattr(pattern, key, None)
                    if val is not None and str(val).strip() not in ("", "0"):
                        out[f"legacy_{key.lower()}"] = str(val)
        except Exception:
            pass
        return out

    def element_to_raw(self, element: Any, parent_runtime_id: list[int] | None = None, depth: int = 0) -> dict[str, Any] | None:
        try:
            rect = _to_rect(_cached(element, PID_BOUNDING_RECT))
            if rect["right"] <= rect["left"] or rect["bottom"] <= rect["top"]:
                rect = _to_rect(_current(element, PID_BOUNDING_RECT))
            if rect["right"] <= rect["left"] or rect["bottom"] <= rect["top"]:
                return None
            runtime_id = _to_runtime_id(_cached(element, PID_RUNTIME_ID)) or _to_runtime_id(_current(element, PID_RUNTIME_ID))
            hwnd = _to_int(_cached(element, PID_HWND))
            role = control_type_name(_to_int(_cached(element, PID_CONTROL_TYPE)) or _to_int(_current(element, PID_CONTROL_TYPE)))
            name = _to_str(_cached(element, PID_NAME)) or _to_str(_current(element, PID_NAME))
            class_name = _to_str(_cached(element, PID_CLASS_NAME))
            pattern_values: dict[str, str] = {}
            for pid, label in ((PID_VALUE_PATTERN, "Value"), (PID_TEXT_PATTERN, "Text"), (PID_LEGACY_PATTERN, "LegacyIAccessible")):
                pattern_values.update(self._pattern_text(_pattern(element, pid), label))
            text_full = pattern_values.get("text") or pattern_values.get("text_ranges") or pattern_values.get("value") or pattern_values.get("legacy_value") or pattern_values.get("legacy_name") or name or ""
            px, py = (rect["left"] + rect["right"]) // 2, (rect["top"] + rect["bottom"]) // 2
            return {
                "id": _node_id(runtime_id, hwnd, rect),
                "role": role,
                "name": name,
                "automation_id": _to_str(_cached(element, PID_AUTOMATION_ID)),
                "class_name": class_name,
                "hwnd": hwnd,
                "framework_id": _to_str(_cached(element, PID_FRAMEWORK)),
                "rect": rect,
                "px": px,
                "py": py,
                "enabled": _to_bool(_cached(element, PID_ENABLED)),
                "offscreen": _to_bool(_cached(element, PID_OFFSCREEN)),
                "runtime_id": runtime_id,
                "text_full": text_full,
                "value": pattern_values.get("value") or pattern_values.get("legacy_value") or "",
                "patterns": list(pattern_values.keys()),
                "pattern_values": pattern_values,
                "depth": depth,
                "parent_runtime_id": parent_runtime_id or [],
                "is_keyboard_focusable": _to_bool(_cached(element, PID_KEYBOARD_FOCUSABLE)) or _to_bool(_current(element, PID_KEYBOARD_FOCUSABLE)),
                "is_content_element": _to_bool(_cached(element, PID_CONTENT_ELEMENT)) or _to_bool(_current(element, PID_CONTENT_ELEMENT)),
                "action": action_for_role(role, class_name),
            }
        except Exception:
            return None

    def harvest_subtree(self, root_element: Any, max_nodes: int, parent_runtime_id: list[int] | None = None, depth: int = 0) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(el: Any, parent: list[int], d: int) -> dict[str, Any] | None:
            if len(nodes) >= max_nodes:
                return None
            node = self.element_to_raw(el, parent, d)
            if node is None or node["id"] in seen:
                return None
            seen.add(node["id"])
            nodes.append(node)
            return node

        root_node = add(root_element, parent_runtime_id or [], depth)
        if not root_node:
            return nodes
        try:
            arr = root_element.FindAllBuildCache(TreeScope_Descendants, self.automation.CreateTrueCondition(), self._cache())
            for i in range(int(getattr(arr, "Length", 0)) if arr is not None else 0):
                if len(nodes) >= max_nodes:
                    break
                try:
                    add(arr.GetElement(i), root_node["runtime_id"], depth + 1)
                except Exception:
                    continue
        except Exception:
            pass
        return nodes


def _hit_key_from_element(element: Any) -> tuple[str, str]:
    rect = _to_rect(_cached(element, PID_BOUNDING_RECT))
    if rect["right"] <= rect["left"] or rect["bottom"] <= rect["top"]:
        rect = _to_rect(_current(element, PID_BOUNDING_RECT))
    runtime_id = _to_runtime_id(_cached(element, PID_RUNTIME_ID)) or _to_runtime_id(_current(element, PID_RUNTIME_ID))
    hwnd = _to_int(_cached(element, PID_HWND)) or _to_int(_current(element, PID_HWND))
    role_id = _to_int(_cached(element, PID_CONTROL_TYPE)) or _to_int(_current(element, PID_CONTROL_TYPE))
    return _node_id(runtime_id, hwnd, rect), control_type_name(role_id)


def gather_raw(config: dict[str, Any], desktop: Any) -> dict[str, Any]:
    scan = config["scan"]
    step_px = int(scan["step_px"])
    delay_ms = int(scan["delay_ms"])
    max_subtree = int(scan["max_subtree_nodes_per_point"])
    max_total = int(scan["max_total_nodes"])
    sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    area = scan.get("area") or {}
    if area:
        left = max(0, min(sw - 1, int(area.get("left", 0) or 0)))
        top = max(0, min(sh - 1, int(area.get("top", 0) or 0)))
        right = max(left + 1, min(sw, int(area.get("right", sw) or sw)))
        bottom = max(top + 1, min(sh, int(area.get("bottom", sh) or sh)))
    else:
        left, top, right, bottom = 0, 0, sw, sh
    margin = max(2, min(step_px // 4, max(0, min(right - left, bottom - top) // 8)))
    usable_w, usable_h = max(1, right - left - 2 * margin), max(1, bottom - top - 2 * margin)
    cols, rows = max(1, usable_w // step_px), max(1, usable_h // step_px)
    g = 1.32471795724474602596
    ax, ay = 1.0 / g, 1.0 / (g * g)
    points: list[tuple[int, int]] = []
    cells: set[tuple[int, int]] = set()
    for i in range((cols + 1) * (rows + 1)):
        x = left + margin + int(((0.5 + ax * (i + 1)) % 1.0) * usable_w)
        y = top + margin + int(((0.5 + ay * (i + 1)) % 1.0) * usable_h)
        cell = (x // step_px, y // step_px)
        if cell not in cells:
            cells.add(cell)
            points.append((min(sw - 1, max(0, x)), min(sh - 1, max(0, y))))
    scanner = UiaScanner(config, desktop)
    index: dict[str, dict[str, Any]] = {}
    saturated: set[str] = set()
    errors: list[dict[str, Any]] = []
    saved = wintypes.POINT()
    had_cursor = bool(user32.GetCursorPos(ctypes.byref(saved)))
    t0 = time.time()
    try:
        for x, y in points:
            if len(index) >= max_total:
                break
            user32.SetCursorPos(int(x), int(y))
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)
            pt = wintypes.POINT(int(x), int(y))
            try:
                root = scanner.automation.ElementFromPointBuildCache(pt, scanner._cache(TreeScope_Element))
            except Exception as build_exc:
                try:
                    root = scanner.automation.ElementFromPoint(pt)
                except Exception as point_exc:
                    errors.append({"x": int(x), "y": int(y), "build_cache_error": f"{type(build_exc).__name__}: {build_exc}", "point_error": f"{type(point_exc).__name__}: {point_exc}"})
                    continue
            if root is None:
                continue
            hit_key, role = _hit_key_from_element(root)
            if hit_key in saturated or (hit_key in index and role not in CONTAINER_ROLES):
                continue
            nodes = scanner.harvest_subtree(root, max_subtree)
            added = 0
            for node in nodes:
                if is_desktop_leakage(node):
                    continue
                prev = index.get(node["id"])
                if prev is None:
                    index[node["id"]] = node
                    added += 1
                else:
                    for key in ("text_full", "value"):
                        if node[key] and (not prev[key] or len(node[key]) > len(prev[key])):
                            prev[key] = node[key]
                    for key, value in node["pattern_values"].items():
                        if key not in prev["pattern_values"] or len(value) > len(prev["pattern_values"].get(key, "")):
                            prev["pattern_values"][key] = value
                    prev["patterns"] = sorted(set(prev["patterns"]) | set(node["patterns"]))
            if hit_key and (added == 0 or len(nodes) >= max_subtree):
                saturated.add(hit_key)
    finally:
        if had_cursor:
            try:
                user32.SetCursorPos(saved.x, saved.y)
            except Exception:
                pass
    return {
        "nodes": list(index.values()),
        "screen": {"width": sw, "height": sh},
        "scan_stats": {
            "area": {"left": left, "top": top, "right": right, "bottom": bottom},
            "probes": len(points),
            "unique_nodes": len(index),
            "point_errors": len(errors),
            "first_point_errors": errors[:5],
            "elapsed_s": round(time.time() - t0, 3),
        },
    }


def filter_raw(raw_nodes: list[dict[str, Any]], config: dict[str, Any], screen: dict[str, int]) -> dict[str, Any]:
    filt = config["filter"]
    max_elements = int(filt["max_elements"])
    max_per_window = int(filt["max_per_window"])
    max_text = int(filt["max_text"])
    require_interactive = bool(filt["require_interactive"])
    hwnd_to_z = {hwnd: i for i, hwnd in enumerate(get_window_z_order())}
    ranked = sorted([n for n in raw_nodes if not n["offscreen"] and n["role"] not in JUNK_ROLES], key=lambda n: (0 if n["name"] or n["text_full"] else 1, 0 if not n["offscreen"] else 1))
    action_elements: dict[str, dict[str, Any]] = {}
    text_hints: dict[str, str] = {}
    hwnd_counts: dict[int, int] = {}
    for node in ranked:
        if len(action_elements) >= max_elements:
            break
        action = node["action"]
        if require_interactive and not action:
            continue
        label = (node["text_full"] or node["name"] or "")[:max_text]
        if label and label != (node["name"] or ""):
            text_hints[node["id"]] = label
        if action:
            hwnd = node["hwnd"]
            if hwnd_counts.get(hwnd, 0) >= max_per_window:
                continue
            hwnd_counts[hwnd] = hwnd_counts.get(hwnd, 0) + 1
            action_elements[node["id"]] = {
                "id": node["id"], "short_id": "", "name": label or node["name"], "role": node["role"],
                "action": action, "px": node["px"], "py": node["py"], "hwnd": hwnd, "rect": node["rect"],
                "enabled": node["enabled"], "automation_id": node["automation_id"], "class_name": node["class_name"],
                "runtime_id": node["runtime_id"], "depth": node["depth"],
            }
    return {"action_elements": action_elements, "text_hints": text_hints, "hwnd_to_z": hwnd_to_z, "hwnd_interactive_count": hwnd_counts}


def build_tree_and_map(action_elements: dict[str, dict[str, Any]], text_hints: dict[str, str], raw_nodes: list[dict[str, Any]], hwnd_to_z: dict[int, int], screen: dict[str, int], config: dict[str, Any]) -> dict[str, Any]:
    filt = config["filter"]
    max_depth = int(filt.get("max_depth", 10))
    max_children_per_window = int(filt.get("max_children_per_window", 120))
    max_llm_nodes = int(filt.get("max_llm_nodes", int(filt["max_elements"]) * 2))
    windows: dict[int, dict[str, Any]] = {}
    for node in raw_nodes:
        if node["role"] == "Window" and node["hwnd"] and node["hwnd"] not in windows:
            windows[node["hwnd"]] = {
                "hwnd": node["hwnd"], "title": node["name"] or node["text_full"] or f"Window_{node['hwnd']}",
                "class_name": node["class_name"], "framework_id": node["framework_id"], "rect": node["rect"],
                "z_order": hwnd_to_z.get(node["hwnd"], 0), "children": [],
            }
    sorted_windows = sorted(windows.values(), key=lambda w: w["z_order"])
    root = {"id": "W0", "role": "Screen", "name": "Screen", "title": "Desktop", "rect": {"left": 0, "top": 0, "right": screen["width"], "bottom": screen["height"]}, "fresh_scan": True, "observed_at": time.time(), "children": []}
    node_index: dict[str, dict[str, Any]] = {"W0": {k: v for k, v in root.items() if k != "children"}}
    counts = {w["hwnd"]: 0 for w in sorted_windows}
    for window in sorted_windows:
        token = f"W{len(root['children']) + 1}"
        window["id"] = token
        window["parent_id"] = "W0"
        root["children"].append(window)
        node_index[token] = {k: v for k, v in window.items() if k != "children"}
    for elem in action_elements.values():
        parent_hwnd = next((w["hwnd"] for w in sorted_windows if w["rect"].get("left", 0) <= elem["px"] <= w["rect"].get("right", 0) and w["rect"].get("top", 0) <= elem["py"] <= w["rect"].get("bottom", 0)), None)
        parent_id = next((w["id"] for w in sorted_windows if w["hwnd"] == parent_hwnd), "W0") if parent_hwnd is not None else "W0"
        if parent_hwnd is not None and parent_id != "W0" and counts.get(parent_hwnd, 0) >= max_children_per_window:
            continue
        elem["parent_id"] = parent_id
        (root["children"] if parent_id == "W0" or parent_hwnd is None else windows[parent_hwnd]["children"]).append(elem)
        if parent_hwnd is not None and parent_id != "W0":
            counts[parent_hwnd] = counts.get(parent_hwnd, 0) + 1
        node_index[elem["id"]] = {k: v for k, v in elem.items() if k != "children"}

    def area(r: dict[str, int]) -> int:
        return max(0, r.get("right", 0) - r.get("left", 0)) * max(0, r.get("bottom", 0) - r.get("top", 0))

    def sort_prune(node: dict[str, Any], depth: int = 0) -> None:
        kids = node.get("children", [])
        if not isinstance(kids, list):
            return
        if depth >= max_depth:
            node["children"] = []
            return
        kids.sort(key=lambda c: (c.get("z_order", 0), c.get("rect", {}).get("top", 0), c.get("rect", {}).get("left", 0), area(c.get("rect", {}))))
        for child in kids:
            if isinstance(child, dict):
                sort_prune(child, depth + 1)

    sort_prune(root)
    short: dict[str, str] = {}
    counters: dict[str, int] = {}

    def assign(node: dict[str, Any], parent: str = "") -> None:
        nid = node.get("id", "")
        if nid == "W0":
            sid = "W0"
        elif nid.startswith("W") and node.get("parent_id") == "W0":
            sid = nid
        elif parent and parent.startswith("W") and "E" in parent:
            key = f"{parent}_child"; counters[key] = counters.get(key, 0) + 1; sid = f"{parent}C{counters[key]}"
        elif parent and parent.startswith("W") and parent != "W0":
            counters[parent] = counters.get(parent, 0) + 1; sid = f"{parent}E{counters[parent]}"
        else:
            sid = nid
        short[nid] = sid
        node["short_id"] = sid
        for child in node.get("children", []):
            if isinstance(child, dict):
                assign(child, sid)

    assign(root)
    node_index_short = {short.get(oid, oid): {**ndata, "short_id": short.get(oid, oid)} for oid, ndata in node_index.items()}
    action_index_short = {short.get(oid, oid): {**edata, "short_id": short.get(oid, oid)} for oid, edata in action_elements.items()}

    def clean(v: Any) -> str:
        return " ".join(str(v or "").replace("\r", " ").replace("\n", " ").split())

    lines = ["W0 Screen Desktop"]
    rendered = 1
    limit_hit = False

    def render(node: dict[str, Any], indent: int = 1) -> None:
        nonlocal rendered, limit_hit
        if rendered >= max_llm_nodes:
            limit_hit = True
            return
        sid, role, name, action = node.get("short_id", node.get("id", "")), str(node.get("role", "")), clean(node.get("name", "") or node.get("title", "")), str(node.get("action", ""))
        parts = [p for p in (sid, role, name, f"[{action}]" if action else "") if p]
        hint = text_hints.get(node.get("id", ""), "")
        if hint and hint not in name:
            parts.append(f"~{hint}")
        lines.append("  " * indent + " ".join(parts))
        rendered += 1
        for child in node.get("children", []):
            if isinstance(child, dict):
                render(child, indent + 1)

    for child in root.get("children", []):
        if isinstance(child, dict):
            render(child, 1)
    return {
        "root": root,
        "node_index": node_index_short,
        "action_index": action_index_short,
        "desktop_tree_text": "\n".join(lines),
        "window_count": len(sorted_windows),
        "element_count": len(action_index_short),
        "rendered_node_count": rendered,
        "max_llm_nodes": max_llm_nodes,
        "llm_node_limit_hit": limit_hit,
        "window_z_order": [w["hwnd"] for w in sorted_windows],
    }


def observe(desktop: Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(config or {})
    if not cfg["enabled"]:
        raise RuntimeError("hover_cache observation is disabled")
    gathered = gather_raw(cfg, desktop)
    filtered = filter_raw(gathered["nodes"], cfg, gathered["screen"])
    mapped = build_tree_and_map(filtered["action_elements"], filtered["text_hints"], gathered["nodes"], filtered["hwnd_to_z"], gathered["screen"], cfg)
    observed_at = time.time()
    artifact = {
        "observed_at": observed_at,
        "fresh_scan": True,
        "scan_config": cfg["scan"],
        "screen": gathered["screen"],
        "scan_stats": gathered["scan_stats"],
        "desktop_tree": {
            "id": "W0", "role": "Screen", "fresh_scan": True, "observed_at": observed_at,
            "root": mapped["root"], "node_index": mapped["node_index"], "window_count": mapped["window_count"],
            "element_count": mapped["element_count"], "rendered_node_count": mapped["rendered_node_count"],
            "max_llm_nodes": mapped["max_llm_nodes"], "llm_node_limit_hit": mapped["llm_node_limit_hit"],
            "window_z_order": mapped["window_z_order"],
        },
        "action_index": mapped["action_index"],
        "desktop_tree_text": mapped["desktop_tree_text"],
    }
    desktop._last_desktop_tree = artifact["desktop_tree"]
    desktop._last_action_index = mapped["action_index"]
    return {
        "observed_at": observed_at,
        "fresh_scan": True,
        "desktop_tree": artifact["desktop_tree"],
        "desktop_tree_text": mapped["desktop_tree_text"],
        "action_index": mapped["action_index"],
        "rendered_node_count": mapped["rendered_node_count"],
        "max_llm_nodes": mapped["max_llm_nodes"],
        "llm_node_limit_hit": mapped["llm_node_limit_hit"],
        "observation_artifact": artifact,
    }
