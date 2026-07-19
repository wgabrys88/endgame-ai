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
PID_CONTENT_ELEMENT = _const("UIA_IsContentElementPropertyId")
PID_WINDOW_INTERACTION_STATE = _const("UIA_WindowWindowInteractionStatePropertyId")
PID_ITEM_STATUS = _const("UIA_ItemStatusPropertyId")
SCAN_PROPERTY_IDS = [
    PID_RUNTIME_ID, PID_BOUNDING_RECT, PID_CONTROL_TYPE, PID_NAME, PID_AUTOMATION_ID, PID_CLASS_NAME,
    PID_ENABLED, PID_OFFSCREEN, PID_HWND, PID_FRAMEWORK, PID_CONTENT_ELEMENT,
    PID_WINDOW_INTERACTION_STATE, PID_ITEM_STATUS,
]

PID_VALUE_PATTERN = _const("UIA_ValuePatternId")
PID_TEXT_PATTERN = _const("UIA_TextPatternId")
PID_LEGACY_PATTERN = _const("UIA_LegacyIAccessiblePatternId")
SCAN_PATTERN_IDS = [PID_VALUE_PATTERN, PID_TEXT_PATTERN, PID_LEGACY_PATTERN]

CONTROL_TYPE_NAMES = {
    getattr(uia, attr): attr.replace("UIA_", "").replace("ControlTypeId", "")
    for attr in dir(uia)
    if attr.startswith("UIA_") and attr.endswith("ControlTypeId") and isinstance(getattr(uia, attr, None), int)
}
CLICK_ROLES = {"Button", "Calendar", "CheckBox", "Hyperlink", "ListItem", "MenuItem", "RadioButton", "Tab", "TabItem", "TreeItem", "DataItem", "SplitButton"}
WRITE_ROLES = {"Edit", "ComboBox", "Spinner", "Document"}
READ_ROLES = {"Text", "ListItem"}
SCROLL_ROLES = {"List", "ScrollBar", "Slider", "Tree", "DataGrid"}


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
    return node["role"] == "List" and node["name"] == "Desktop"


def enum_windows(min_area: int = 2500) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _):
        h = int(hwnd)
        if h in seen or not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        w, ht = rect.right - rect.left, rect.bottom - rect.top
        if w <= 0 or ht <= 0 or w * ht < min_area:
            return True
        length = int(user32.GetWindowTextLengthW(hwnd))
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        seen.add(h)
        out.append({
            "hwnd": h,
            "title": buf.value or "",
            "rect": {"left": int(rect.left), "top": int(rect.top), "right": int(rect.right), "bottom": int(rect.bottom)},
            "z_order": len(out),
        })
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
                "is_content_element": _to_bool(_cached(element, PID_CONTENT_ELEMENT)) or _to_bool(_current(element, PID_CONTENT_ELEMENT)),
                "interaction_state": (lambda v: _to_int(v) if _unwrap(v) is not None else None)(_cached(element, PID_WINDOW_INTERACTION_STATE)) if role == "Window" else None,
                "item_status": _to_str(_cached(element, PID_ITEM_STATUS)),
                "action": action_for_role(role, class_name),
            }
        except Exception:
            return None

    def harvest_subtree(self, root_element: Any, max_nodes: int | None = None) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        seen: set[str] = set()
        depth_ceiling = 45
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
            except Exception:
                kids, count = None, 0
            for i in range(count):
                if max_nodes is not None and len(nodes) >= max_nodes:
                    break
                try:
                    visit(kids.GetElement(i), child_parent_rid, child_depth)
                except Exception:
                    continue

        visit(root_element, [], 0)
        return nodes


def expand(desktop: Any, ids_or_points: list[Any], char_budget: int | None = None) -> dict[str, Any]:
    from ctypes import wintypes
    scanner = UiaScanner({}, desktop)
    harvested_by_key: dict[str, list[dict[str, Any]]] = {}
    for i, item in enumerate(ids_or_points):
        node = item if isinstance(item, dict) else {}
        px, py = node.get("px"), node.get("py")
        key = str(node.get("short_id") or node.get("id") or i)
        if px is None or py is None:
            raise RuntimeError(f"expand: element '{key}' bears no screen point to expand")
        px, py = int(px), int(py)
        pt = wintypes.POINT(px, py)
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
    if char_budget is not None and grand_total > char_budget:
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


def _probe_points(rect: dict[str, int], step_px: int) -> list[tuple[int, int]]:
    left, top = rect["left"], rect["top"]
    w, h = max(1, rect["right"] - left), max(1, rect["bottom"] - top)
    cols, rows = max(1, w // step_px), max(1, h // step_px)
    g = 1.32471795724474602596
    ax, ay = 1.0 / g, 1.0 / (g * g)
    points: list[tuple[int, int]] = []
    cells: set[tuple[int, int]] = set()
    for i in range((cols + 1) * (rows + 1)):
        x = left + int(((0.5 + ax * (i + 1)) % 1.0) * w)
        y = top + int(((0.5 + ay * (i + 1)) % 1.0) * h)
        cell = (x // step_px, y // step_px)
        if cell not in cells:
            cells.add(cell)
            points.append((x, y))
    return points


def observe(desktop: Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(config or {})
    if not cfg.get("enabled", True):
        raise RuntimeError("observation is disabled")
    scan = cfg.get("scan", {})
    step_px = int(scan.get("step_px", 64))
    max_subtree = int(scan.get("max_subtree_nodes_per_point", 2000))
    line_preview_chars = int(cfg.get("budget", {}).get("line_preview_chars", 120))
    sw, sh = int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))
    screen = {"width": sw, "height": sh}

    windows = enum_windows()

    scanner = UiaScanner(cfg, desktop)
    windows_out: list[dict[str, Any]] = []
    for win in windows:
        hwnd, rect = win["hwnd"], win["rect"]
        kept: dict[str, dict[str, Any]] = {}
        for x, y in _probe_points(rect, step_px):
            pt = wintypes.POINT(int(x), int(y))
            try:
                owner = int(user32.GetAncestor(user32.WindowFromPoint(pt), 2) or 0)
            except Exception:
                owner = 0
            if owner != hwnd:
                continue
            try:
                root = scanner.automation.ElementFromPointBuildCache(pt, scanner._cache(TreeScope_Element))
            except Exception:
                continue
            if root is None:
                continue
            for i, node in enumerate(scanner.harvest_subtree(root, max_subtree)):
                if is_desktop_leakage(node):
                    continue
                node["owner_hwnd"] = hwnd
                if i == 0:
                    node.setdefault("hit_point", (int(x), int(y)))
                nid = node["id"]
                prev = kept.get(nid)
                if prev is None:
                    kept[nid] = node
                else:
                    if not prev.get("hit_point") and node.get("hit_point"):
                        prev["hit_point"] = node["hit_point"]
                    for key in ("text_full", "value"):
                        if node[key] and (not prev[key] or len(node[key]) > len(prev[key])):
                            prev[key] = node[key]
        win["elements"] = list(kept.values())
        windows_out.append(win)

    result = _render(windows_out, screen, line_preview_chars)
    observed_at = time.time()
    return {
        "observed_at": observed_at,
        "desktop_tree_text": result["desktop_tree_text"],
        "action_index": result["action_index"],
        "screen_elements": result["screen_elements"],
        "observation_artifact": {"screen": screen},
    }


def _render(windows: list[dict[str, Any]], screen: dict[str, int], line_preview_chars: int) -> dict[str, Any]:
    def clean(v: Any) -> str:
        return " ".join(str(v or "").replace("\r", " ").replace("\n", " ").split())

    def preview(text: str) -> tuple[str, int]:
        c = clean(text)
        return (c[:line_preview_chars], len(c)) if len(c) > line_preview_chars else (c, 0)

    action_index: dict[str, dict[str, Any]] = {}
    screen_elements: list[dict[str, Any]] = []
    counter = {"n": 0}
    lines = ["W0 Screen Desktop"]

    for wi, win in enumerate(windows, start=1):
        wid = f"W{wi}"
        title = win["title"] or f"Window_{win['hwnd']}"
        elements = win["elements"]
        by_rid = {tuple(e.get("runtime_id") or []): e for e in elements if e.get("runtime_id")}
        action_children: dict[str, list[dict[str, Any]]] = {}
        roots: list[dict[str, Any]] = []

        def nearest_action_ancestor(e: dict[str, Any]) -> dict[str, Any] | None:
            seen: set[tuple] = set()
            prid = tuple(e.get("parent_runtime_id") or [])
            while prid and prid not in seen:
                seen.add(prid)
                anc = by_rid.get(prid)
                if anc is not None and anc is not e and anc.get("action"):
                    return anc
                cur = by_rid.get(prid)
                prid = tuple(cur.get("parent_runtime_id") or []) if cur else ()
            return None

        actionable = [e for e in elements if e.get("action")]
        for e in actionable:
            anc = nearest_action_ancestor(e)
            if anc is not None:
                action_children.setdefault(id(anc), []).append(e)
            else:
                roots.append(e)
            screen_elements.append({
                "id": e["id"], "name": e.get("name", ""), "role": e.get("role", ""),
                "text": e.get("text_full", "") or "", "value": e.get("value", "") or "",
                "px": e.get("px"), "py": e.get("py"), "rect": e.get("rect", {}), "hwnd": win["hwnd"],
                "enabled": e.get("enabled"),
            })

        active = " [active]" if wi == 1 else ""
        lines.append(f"{wid} Window {clean(title)}{active}")

        def emit(e: dict[str, Any], indent: int) -> None:
            counter["n"] += 1
            sid = f"e{counter['n']}"
            e["short_id"] = sid
            action = str(e.get("action", "")) if e.get("enabled") is not False else ""
            name_prev, name_total = preview(e.get("name", "") or "")
            parts = [p for p in (
                sid, str(e.get("role", "")), name_prev,
                f"[{action}]" if action else "",
            ) if p]
            if name_total:
                parts.append(f"({name_total} chars)")
            lines.append("  " * indent + " ".join(parts))
            action_index[sid] = {**{k: v for k, v in e.items() if k != "children"}, "short_id": sid}
            for child in action_children.get(id(e), []):
                emit(child, indent + 1)

        for e in roots:
            emit(e, 1)

    return {
        "action_index": action_index,
        "screen_elements": screen_elements,
        "desktop_tree_text": "\n".join(lines),
    }
