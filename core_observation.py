import ctypes
import importlib
import time
from ctypes import wintypes
from typing import Any

import comtypes
import comtypes.client

user32 = ctypes.windll.user32


def load_uia() -> Any:
    comtypes.client.GetModule("UIAutomationCore.dll")
    return importlib.import_module("comtypes.gen.UIAutomationClient")


comtypes.CoInitialize()
uia = load_uia()


def _const(name: str) -> int:
    return int(getattr(uia, name))


TreeScope_Element = _const("TreeScope_Element")
TreeScope_Descendants = _const("TreeScope_Descendants")
TreeScope_Subtree = _const("TreeScope_Subtree")

PID_RUNTIME_ID = _const("UIA_RuntimeIdPropertyId")
PID_BOUNDING_RECT = _const("UIA_BoundingRectanglePropertyId")
PID_CONTROL_TYPE = _const("UIA_ControlTypePropertyId")
PID_NAME = _const("UIA_NamePropertyId")
PID_AUTOMATION_ID = _const("UIA_AutomationIdPropertyId")
PID_CLASS_NAME = _const("UIA_ClassNamePropertyId")
PID_ENABLED = _const("UIA_IsEnabledPropertyId")
PID_OFFSCREEN = _const("UIA_IsOffscreenPropertyId")
PID_HWND = _const("UIA_NativeWindowHandlePropertyId")
PID_FRAMEWORK = _const("UIA_FrameworkIdPropertyId")
PID_HAS_KEYBOARD_FOCUS = _const("UIA_HasKeyboardFocusPropertyId")
PID_KEYBOARD_FOCUSABLE = _const("UIA_IsKeyboardFocusablePropertyId")
PID_CONTENT_ELEMENT = _const("UIA_IsContentElementPropertyId")
PID_WINDOW_INTERACTION_STATE = _const("UIA_WindowWindowInteractionStatePropertyId")
PID_ITEM_STATUS = _const("UIA_ItemStatusPropertyId")
SCAN_PROPERTY_IDS = [
    PID_RUNTIME_ID, PID_BOUNDING_RECT, PID_CONTROL_TYPE, PID_NAME, PID_AUTOMATION_ID, PID_CLASS_NAME,
    PID_ENABLED, PID_OFFSCREEN, PID_HWND, PID_FRAMEWORK, PID_HAS_KEYBOARD_FOCUS, PID_KEYBOARD_FOCUSABLE, PID_CONTENT_ELEMENT,
    PID_WINDOW_INTERACTION_STATE, PID_ITEM_STATUS,
]

PID_VALUE_PATTERN = _const("UIA_ValuePatternId")
PID_TEXT_PATTERN = _const("UIA_TextPatternId")
PID_LEGACY_PATTERN = _const("UIA_LegacyIAccessiblePatternId")
PID_INVOKE_PATTERN = _const("UIA_InvokePatternId")
PID_SCROLL_PATTERN = _const("UIA_ScrollPatternId")
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
    return node["role"] == "List" and node["name"] == "Desktop" and action_for_role(node["role"], node["class_name"]) == "scroll"


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
                "interaction_state": (lambda v: _to_int(v) if _unwrap(v) is not None else None)(_cached(element, PID_WINDOW_INTERACTION_STATE)) if role == "Window" else None,
                "item_status": _to_str(_cached(element, PID_ITEM_STATUS)),
                "action": action_for_role(role, class_name),
            }
        except Exception:
            return None

    def harvest_subtree(self, root_element: Any, max_nodes: int | None = None, parent_runtime_id: list[int] | None = None, depth: int = 0) -> list[dict[str, Any]]:
        """Walk the cached subtree preserving TRUE parent identity and depth. The cache is
        built with Subtree scope, so GetCachedChildren recurses from that one cached read
        with no further live [UIA] calls — unlike a flat descendant list, which would tag
        every node with the subtree root and destroy the real hierarchy."""
        nodes: list[dict[str, Any]] = []
        seen: set[str] = set()
        # Bound recursion by the same wiring-owned perception depth used when the tree is
        # built (filter.max_depth), so a pathologically deep accessibility tree cannot
        # overflow the Python stack. Falls back to a generous ceiling when scanned without
        # config (e.g. the expand primitive), which real UIA trees never approach.
        try:
            depth_ceiling = int(((self.cfg or {}).get("filter") or {}).get("max_depth", 40)) + depth + 5
        except Exception:
            depth_ceiling = depth + 45
        try:
            root_element = root_element.BuildUpdatedCache(self._cache(TreeScope_Subtree))
        except Exception:
            pass

        def visit(el: Any, parent_rid: list[int], d: int) -> None:
            if (max_nodes is not None and len(nodes) >= max_nodes) or d >= depth_ceiling:
                return
            node = self.element_to_raw(el, parent_rid, d)
            child_parent_rid, child_depth = parent_rid, d
            if node is not None and node["id"] not in seen:
                seen.add(node["id"])
                nodes.append(node)
                child_parent_rid, child_depth = node["runtime_id"], d + 1
            elif node is not None:
                return
            try:
                kids = el.GetCachedChildren()
                count = int(getattr(kids, "Length", 0)) if kids is not None else 0
            except (ValueError, Exception):
                kids, count = None, 0
            for i in range(count):
                if max_nodes is not None and len(nodes) >= max_nodes:
                    break
                try:
                    visit(kids.GetElement(i), child_parent_rid, child_depth)
                except Exception:
                    continue

        visit(root_element, parent_runtime_id or [], depth)
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


def expand(desktop: Any, ids_or_points: list[Any], char_budget: int) -> dict[str, Any]:
    """Targeted deeper look at named elements: re-acquire each at its screen point and
    harvest its full subtree, returning the WHOLE untruncated text, value, and every child
    (including non-interactive), which the shallow tree omitteth. This is a fresh independent
    look, not memory: it readeth the live [UIA] now. `ids_or_points` are entries of the current
    action_index (each bearing px/py) or explicit {'px':x,'py':y} points.

    No text is ever cut short. The shallow tree already nameth each element's true size in
    chars, so thou knowest the cost ere thou askest. Shouldst the sum of what thou askest
    exceed [char_budget], this faileth hard and nameth each element's size—ask again for fewer
    or other elements."""
    from ctypes import wintypes
    scanner = UiaScanner({}, desktop)
    harvested_by_key: dict[str, list[dict[str, Any]]] = {}
    for i, item in enumerate(ids_or_points):
        node = item if isinstance(item, dict) else {}
        px, py = node.get("px"), node.get("py")
        key = str(node.get("short_id") or node.get("id") or i)
        if px is None or py is None:
            raise RuntimeError(f"expand: element '{key}' bears no screen point to expand")
        pt = wintypes.POINT(int(px), int(py))
        root_el = scanner.automation.ElementFromPointBuildCache(pt, scanner._cache())
        if root_el is None:
            raise RuntimeError(f"expand: no element at point ({px}, {py}) for '{key}'")
        harvested_by_key[key] = scanner.harvest_subtree(root_el)

    def _chars(harvested: list[dict[str, Any]]) -> int:
        if not harvested:
            return 0
        head = harvested[0]
        total = len(head.get("text_full", "") or "") + len(head.get("value", "") or "")
        total += sum(len(n.get("text_full", "") or "") for n in harvested[1:])
        return total

    sizes = {key: _chars(h) for key, h in harvested_by_key.items()}
    grand_total = sum(sizes.values())
    if grand_total > char_budget:
        detail = ", ".join(f"{k}={v} chars" for k, v in sizes.items())
        raise RuntimeError(f"expand: requested {grand_total} chars exceedeth budget {char_budget} ({detail}); ask for fewer or other elements")

    results: dict[str, Any] = {}
    for key, harvested in harvested_by_key.items():
        results[key] = {
            "text_full": harvested[0].get("text_full", "") if harvested else "",
            "value": harvested[0].get("value", "") if harvested else "",
            "children": [
                {"role": n["role"], "name": n["name"], "action": n["action"], "text": n.get("text_full") or ""}
                for n in harvested[1:]
            ],
        }
    return results


def observe(desktop: Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(config or {})
    if not cfg["enabled"]:
        raise RuntimeError("hover_cache observation is disabled")
    phases = cfg.get("phases") or {}
    scan = _load_phase(phases["scan"])
    filt = _load_phase(phases["filter"])
    build = _load_phase(phases["build"])
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
        "screen_elements": mapped["screen_elements"],
        "observation_artifact": artifact,
    }
