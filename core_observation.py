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
PID_HAS_KEYBOARD_FOCUS = _const("UIA_HasKeyboardFocusPropertyId", 30008)
PID_KEYBOARD_FOCUSABLE = _const("UIA_IsKeyboardFocusablePropertyId", 30009)
PID_CONTENT_ELEMENT = _const("UIA_IsContentElementPropertyId", 30015)
SCAN_PROPERTY_IDS = [
    PID_RUNTIME_ID, PID_BOUNDING_RECT, PID_CONTROL_TYPE, PID_NAME, PID_AUTOMATION_ID, PID_CLASS_NAME,
    PID_ENABLED, PID_OFFSCREEN, PID_HWND, PID_FRAMEWORK, PID_HAS_KEYBOARD_FOCUS, PID_KEYBOARD_FOCUSABLE, PID_CONTENT_ELEMENT,
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
                "focused": _to_bool(_cached(element, PID_HAS_KEYBOARD_FOCUS)) or _to_bool(_current(element, PID_HAS_KEYBOARD_FOCUS)),
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


def _load_phase(module_name: str):
    import importlib
    mod = importlib.import_module(module_name)
    if not hasattr(mod, "run"):
        raise RuntimeError(f"observation phase '{module_name}' does not export run(...)")
    return mod


def expand(desktop: Any, ids_or_points: list[Any], max_text: int = 5000, max_nodes: int = 200) -> dict[str, Any]:
    """Targeted deeper look at named elements: re-acquire each at its screen point and
    harvest its full subtree, returning untruncated text, value, and every child (including
    non-interactive), which the shallow tree omitteth. This is a fresh independent look, not
    memory: it readeth the live [UIA] now. `ids_or_points` are entries of the current
    action_index (each bearing px/py) or explicit {'px':x,'py':y} points."""
    from ctypes import wintypes
    scanner = UiaScanner({}, desktop)
    results: dict[str, Any] = {}
    for i, item in enumerate(ids_or_points):
        node = item if isinstance(item, dict) else {}
        px, py = node.get("px"), node.get("py")
        key = str(node.get("short_id") or node.get("id") or i)
        if px is None or py is None:
            results[key] = {"error": "element bears no screen point to expand"}
            continue
        pt = wintypes.POINT(int(px), int(py))
        try:
            root_el = scanner.automation.ElementFromPointBuildCache(pt, scanner._cache())
        except Exception as exc:
            results[key] = {"error": f"could not acquire element: {type(exc).__name__}: {exc}"}
            continue
        if root_el is None:
            results[key] = {"error": "no element at point"}
            continue
        harvested = scanner.harvest_subtree(root_el, max_nodes)
        results[key] = {
            "text_full": (harvested[0].get("text_full", "") if harvested else "")[:max_text],
            "value": (harvested[0].get("value", "") if harvested else "")[:max_text],
            "children": [
                {"role": n["role"], "name": n["name"], "action": n["action"], "text": (n.get("text_full") or "")[:max_text]}
                for n in harvested[1:]
            ],
        }
    return results


def observe(desktop: Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(config or {})
    if not cfg["enabled"]:
        raise RuntimeError("hover_cache observation is disabled")
    phases = cfg.get("phases") or {}
    scan = _load_phase(phases.get("scan", "obs_scan"))
    filt = _load_phase(phases.get("filter", "obs_filter"))
    build = _load_phase(phases.get("build", "obs_build"))
    gathered = scan.run(cfg, desktop)
    filtered = filt.run(gathered["nodes"], cfg, gathered["screen"])
    mapped = build.run(
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
        "scan_config": cfg["scan"],
        "screen": gathered["screen"],
        "desktop_tree": {
            "id": "W0", "role": "Screen", "fresh_scan": True, "observed_at": observed_at,
            "root": mapped["root"], "node_index": mapped["node_index"], "window_count": mapped["window_count"],
            "element_count": mapped["element_count"],
            "window_z_order": mapped["window_z_order"],
        },
        "action_index": mapped["action_index"],
        "desktop_tree_text": mapped["desktop_tree_text"],
    }
    return {
        "observed_at": observed_at,
        "fresh_scan": True,
        "desktop_tree": artifact["desktop_tree"],
        "desktop_tree_text": mapped["desktop_tree_text"],
        "action_index": mapped["action_index"],
        "observation_artifact": artifact,
    }
