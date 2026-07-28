"""The desktop hand — a seated tool node. When this file is present the actor gains eyes and
hands upon the real Windows desktop; remove it and the organism simply has no hand (no flag).

It offers, by bare name in the actor namespace:
  desktop.observe(config=None) - take a fresh looking, refresh the live bare observation, and
    return {"action_index", "screen_elements", "desktop_tree_text"}
  desktop.open_url(browser='default', url='') - open a known address in the Windows default browser; any other browser value is an exact executable path
  desktop.click(x, y, hwnd) - move and press upon an owned point
  desktop.type_text(text) / desktop.paste_clipboard(text) / desktop.set_clipboard(text)
  desktop.press_key(key) / desktop.hotkey(*keys) / desktop.scroll(x, y, amount|clicks, hwnd)
  action_index - the live short-id -> element DICTIONARY map of the last looking
  read(id) - the same element DICTIONARY, bearing its WHOLE untruncated body in ["text_full"]
  screen_elements, desktop_tree_text - the raw fruit of the turn-opening scan

Each action_index value is a dictionary, and read(id) returneth that very dictionary. Select by
e["role"], e["name"], e["action"], e["window_title"], or e["value"]; take the whole body from
e["text_full"]; act with e["px"], e["py"], and e["owner_hwnd"].
The compact tree is an index: body_chars=N means read("eN")["text_full"] beareth N whole characters.
After desktop.observe(), use its returned desktop_tree_text when thou needest the new tree;
the live action_index, screen_elements, and read(id) are refreshed in place.

Bind an id, coordinate, or owner ONLY from a fresh scan; a short id dieth with the looking that
bore it. The kernel calls environment(bb, cfg) each turn to refresh the [environment] section,
and namespace(context) to inject the hand into the actor's exec namespace.
"""

import ctypes
import time
from ctypes import wintypes
from typing import Any

user32 = ole32 = oleaut32 = None
AUTOMATION = None


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


class _VARIANT_VALUE(ctypes.Union):
    _fields_ = [("llVal", ctypes.c_longlong), ("lVal", wintypes.LONG), ("dblVal", ctypes.c_double), ("boolVal", ctypes.c_short), ("bstrVal", ctypes.c_void_p), ("parray", ctypes.c_void_p), ("punkVal", ctypes.c_void_p)]


class _VARIANT(ctypes.Structure):
    _anonymous_ = ("value",)
    _fields_ = [("vt", ctypes.c_ushort), ("r1", ctypes.c_ushort), ("r2", ctypes.c_ushort), ("r3", ctypes.c_ushort), ("value", _VARIANT_VALUE)]


def _guid(a, b, c, *d):
    return _GUID(a, b, c, (ctypes.c_ubyte * 8)(*d))


def _call(ptr, slot, *types):
    address = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents[slot]
    return ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *types)(address)


def _check(hr):
    if hr < 0:
        raise OSError("UI Automation HRESULT 0x%08X" % (hr & 0xFFFFFFFF))


def _bind_windows():
    global user32, ole32, oleaut32, AUTOMATION
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    ole32, oleaut32 = ctypes.WinDLL("ole32"), ctypes.WinDLL("oleaut32")
    user32.SetCursorPos.argtypes, user32.SetCursorPos.restype = [ctypes.c_int, ctypes.c_int], wintypes.BOOL
    user32.GetCursorPos.argtypes, user32.GetCursorPos.restype = [ctypes.POINTER(wintypes.POINT)], wintypes.BOOL
    user32.WindowFromPoint.argtypes, user32.WindowFromPoint.restype = [wintypes.POINT], wintypes.HWND
    user32.GetAncestor.argtypes, user32.GetAncestor.restype = [wintypes.HWND, wintypes.UINT], wintypes.HWND
    ole32.CoInitialize.argtypes, ole32.CoInitialize.restype = [ctypes.c_void_p], ctypes.c_long
    ole32.CoCreateInstance.argtypes = [ctypes.POINTER(_GUID), ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p)]
    ole32.CoCreateInstance.restype = ctypes.c_long
    oleaut32.VariantClear.argtypes = [ctypes.POINTER(_VARIANT)]
    oleaut32.SysFreeString.argtypes = [ctypes.c_void_p]
    oleaut32.SafeArrayGetLBound.argtypes = [ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(wintypes.LONG)]
    oleaut32.SafeArrayGetUBound.argtypes = [ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(wintypes.LONG)]
    oleaut32.SafeArrayAccessData.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    oleaut32.SafeArrayUnaccessData.argtypes = [ctypes.c_void_p]
    _check(ole32.CoInitialize(None))
    user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
    user32.SendInput.restype = wintypes.UINT
    if not user32.SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2):
        raise ctypes.WinError()
    AUTOMATION = _Automation()


def _array(value, kind):
    lo, hi, data = wintypes.LONG(), wintypes.LONG(), ctypes.c_void_p()
    _check(oleaut32.SafeArrayGetLBound(value, 1, ctypes.byref(lo)))
    _check(oleaut32.SafeArrayGetUBound(value, 1, ctypes.byref(hi)))
    _check(oleaut32.SafeArrayAccessData(value, ctypes.byref(data)))
    try:
        return list(ctypes.cast(data, ctypes.POINTER(kind))[:hi.value - lo.value + 1])
    finally:
        _check(oleaut32.SafeArrayUnaccessData(value))


def _value(raw):
    try:
        base = raw.vt & 0xFFF
        if raw.vt & 0x2000:
            return _array(raw.parray, ctypes.c_double if base == 5 else wintypes.LONG)
        if base == 8:
            return ctypes.wstring_at(raw.bstrVal) if raw.bstrVal else ""
        if base == 11:
            return raw.boolVal != 0
        if base == 5:
            return raw.dblVal
        if base in (2, 3, 19):
            return raw.lVal
        return None
    finally:
        oleaut32.VariantClear(ctypes.byref(raw))


def _release(ptr):
    ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.c_void_p)(ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents[2])(ptr)


def _bstr(ptr, slot, *args):
    out = ctypes.c_void_p()
    _check(_call(ptr, slot, *(type(arg) for arg in args), ctypes.POINTER(ctypes.c_void_p))(ptr, *args, ctypes.byref(out)))
    try:
        return ctypes.wstring_at(out) if out else ""
    finally:
        oleaut32.SysFreeString(out)


class _Object:
    def __init__(self, ptr):
        self.ptr = ptr

    def __del__(self):
        if self.ptr:
            _release(self.ptr)
            self.ptr = None


class _Array(_Object):
    def __init__(self, ptr, item):
        super().__init__(ptr)
        self.item = item

    @property
    def Length(self):
        out = ctypes.c_int()
        _check(_call(self.ptr, 3, ctypes.POINTER(ctypes.c_int))(self.ptr, ctypes.byref(out)))
        return out.value

    def GetElement(self, index):
        out = ctypes.c_void_p()
        _check(_call(self.ptr, 4, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p))(self.ptr, index, ctypes.byref(out)))
        return self.item(out)


class _CacheRequest(_Object):
    def AddProperty(self, prop):
        _check(_call(self.ptr, 3, ctypes.c_int)(self.ptr, prop))

    def AddPattern(self, pattern):
        _check(_call(self.ptr, 4, ctypes.c_int)(self.ptr, pattern))

    @property
    def TreeScope(self):
        out = ctypes.c_int()
        _check(_call(self.ptr, 6, ctypes.POINTER(ctypes.c_int))(self.ptr, ctypes.byref(out)))
        return out.value

    @TreeScope.setter
    def TreeScope(self, scope):
        _check(_call(self.ptr, 7, ctypes.c_int)(self.ptr, scope))


class _ValuePattern(_Object):
    def __init__(self, ptr, cached):
        super().__init__(ptr)
        self.cached = cached

    @property
    def Value(self):
        return _bstr(self.ptr, 6 if self.cached else 4)


class _TextRange(_Object):
    def GetText(self, length):
        return _bstr(self.ptr, 12, ctypes.c_int(length))


class _TextPattern(_Object):
    @property
    def DocumentRange(self):
        out = ctypes.c_void_p()
        _check(_call(self.ptr, 7, ctypes.POINTER(ctypes.c_void_p))(self.ptr, ctypes.byref(out)))
        return _TextRange(out)

    def GetVisibleRanges(self):
        out = ctypes.c_void_p()
        _check(_call(self.ptr, 6, ctypes.POINTER(ctypes.c_void_p))(self.ptr, ctypes.byref(out)))
        return _Array(out, _TextRange)


class _LegacyPattern(_Object):
    def __init__(self, ptr, cached):
        super().__init__(ptr)
        self.cached = cached

    @property
    def Name(self):
        return _bstr(self.ptr, 17 if self.cached else 7)

    @property
    def Value(self):
        return _bstr(self.ptr, 18 if self.cached else 8)

    @property
    def Description(self):
        return _bstr(self.ptr, 19 if self.cached else 9)


PATTERNS = {
    10002: (_ValuePattern, _guid(0xA94CD8B1, 0x0844, 0x4CD6, 0x9D, 0x2D, 0x64, 0x05, 0x37, 0xAB, 0x39, 0xE9)),
    10014: (_TextPattern, _guid(0x32EBA289, 0x3583, 0x42C9, 0x9C, 0x59, 0x3B, 0x6D, 0x9A, 0x1E, 0x9B, 0x6A)),
    10018: (_LegacyPattern, _guid(0x828055AD, 0x355B, 0x4435, 0x86, 0xD5, 0x3B, 0x51, 0xC1, 0x4A, 0x9B, 0x1B)),
}


class _Element(_Object):
    def _property(self, slot, prop):
        raw = _VARIANT()
        _check(_call(self.ptr, slot, ctypes.c_int, ctypes.POINTER(_VARIANT))(self.ptr, prop, ctypes.byref(raw)))
        return _value(raw)

    def GetCurrentPropertyValue(self, prop):
        return self._property(10, prop)

    def GetCachedPropertyValue(self, prop):
        return self._property(12, prop)

    def _pattern(self, slot, pattern):
        wrapper, iid = PATTERNS[pattern]
        out = ctypes.c_void_p()
        _check(_call(self.ptr, slot, ctypes.c_int, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p))(self.ptr, pattern, ctypes.byref(iid), ctypes.byref(out)))
        return wrapper(out, slot == 15) if wrapper is not _TextPattern else wrapper(out)

    def GetCurrentPattern(self, pattern):
        return self._pattern(14, pattern)

    def GetCachedPattern(self, pattern):
        return self._pattern(15, pattern)

    def BuildUpdatedCache(self, request):
        out = ctypes.c_void_p()
        _check(_call(self.ptr, 9, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(self.ptr, request.ptr, ctypes.byref(out)))
        return _Element(out)

    def GetCachedChildren(self):
        out = ctypes.c_void_p()
        _check(_call(self.ptr, 19, ctypes.POINTER(ctypes.c_void_p))(self.ptr, ctypes.byref(out)))
        return _Array(out, _Element) if out else None


class _Automation(_Object):
    def __init__(self):
        ptr = ctypes.c_void_p()
        clsid = _guid(0xFF48DBA4, 0x60EF, 0x4201, 0xAA, 0x87, 0x54, 0x10, 0x3E, 0xEF, 0x59, 0x4E)
        iid = _guid(0x30CBE57D, 0xD9D0, 0x452A, 0xAB, 0x13, 0x7A, 0xC5, 0xAC, 0x48, 0x25, 0xEE)
        _check(ole32.CoCreateInstance(ctypes.byref(clsid), None, 1, ctypes.byref(iid), ctypes.byref(ptr)))
        super().__init__(ptr)

    def CreateCacheRequest(self):
        out = ctypes.c_void_p()
        _check(_call(self.ptr, 20, ctypes.POINTER(ctypes.c_void_p))(self.ptr, ctypes.byref(out)))
        return _CacheRequest(out)

    def ElementFromPointBuildCache(self, point, request):
        out = ctypes.c_void_p()
        _check(_call(self.ptr, 11, wintypes.POINT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(self.ptr, point, request.ptr, ctypes.byref(out)))
        return _Element(out) if out else None


PID_RUNTIME_ID, PID_BOUNDING_RECT, PID_CONTROL_TYPE, PID_NAME = 30000, 30001, 30003, 30005
PID_ENABLED, PID_AUTOMATION_ID, PID_CLASS_NAME, PID_CONTENT_ELEMENT = 30010, 30011, 30012, 30017
PID_HWND, PID_OFFSCREEN, PID_FRAMEWORK, PID_ITEM_STATUS = 30020, 30022, 30024, 30026
PID_WINDOW_INTERACTION_STATE = 30076
SCAN_PROPERTY_IDS = [PID_RUNTIME_ID, PID_BOUNDING_RECT, PID_CONTROL_TYPE, PID_NAME, PID_AUTOMATION_ID, PID_CLASS_NAME, PID_ENABLED, PID_OFFSCREEN, PID_HWND, PID_FRAMEWORK, PID_CONTENT_ELEMENT, PID_WINDOW_INTERACTION_STATE, PID_ITEM_STATUS]
PID_VALUE_PATTERN, PID_TEXT_PATTERN, PID_LEGACY_PATTERN = PATTERNS
SCAN_PATTERN_IDS = list(PATTERNS)
TreeScope_Element, TreeScope_Subtree = 1, 7
CONTROL_TYPE_NAMES = dict(enumerate("Button Calendar CheckBox ComboBox Edit Hyperlink Image ListItem List Menu MenuBar MenuItem ProgressBar RadioButton ScrollBar Slider Spinner StatusBar Tab TabItem Text ToolBar ToolTip Tree TreeItem Custom Group Thumb DataGrid DataItem Document SplitButton Window Pane Header HeaderItem Table TitleBar Separator SemanticZoom AppBar".split(), 50000))
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
            return {"left": left, "top": top, "right": left + int(val[2]), "bottom": top + int(val[3])}
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
        self.automation = desktop_instance.automation if desktop_instance and hasattr(desktop_instance, "automation") else AUTOMATION

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
            for pid, label in ((PID_VALUE_PATTERN, "Value"), (PID_LEGACY_PATTERN, "LegacyIAccessible")):
                pattern_values.update(self._pattern_text(_pattern(element, pid), label))
            name = name or pattern_values.get("legacy_name") or ""
            if role in WRITE_ROLES | READ_ROLES and not (pattern_values.get("value") or pattern_values.get("legacy_value")):
                pattern_values.update(self._pattern_text(_pattern(element, PID_TEXT_PATTERN), "Text"))
            value = pattern_values.get("value") or pattern_values.get("legacy_value") or pattern_values.get("text") or ""
            text_full = value or name or pattern_values.get("legacy_description") or ""
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
                "value": value,
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
        depth_ceiling = int(self.cfg.get("depth_ceiling", 45))
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


def _move_cursor(x: int, y: int) -> None:
    user32.SetCursorPos(x, y)


def observe(desktop: Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(config) if isinstance(config, dict) else {}
    step_px = int(cfg.get("step_px", 64))
    max_subtree = int(cfg.get("max_subtree_nodes_per_point", 2000))
    sw, sh = int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))
    screen = {"width": sw, "height": sh}

    windows = enum_windows(int(cfg.get("min_window_area", 2500)))

    scanner = UiaScanner(cfg, desktop)
    saved = wintypes.POINT()
    had_cursor = bool(user32.GetCursorPos(ctypes.byref(saved)))
    windows_out: list[dict[str, Any]] = []
    try:
        for win in windows:
            hwnd, rect = win["hwnd"], win["rect"]
            kept: dict[str, dict[str, Any]] = {}
            for x, y in _probe_points(rect, step_px):
                if not (0 <= x < sw and 0 <= y < sh):
                    continue
                _move_cursor(x, y)
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
    finally:
        if had_cursor:
            try:
                _move_cursor(saved.x, saved.y)
            except Exception:
                pass

    result = _render(windows_out, screen)
    observed_at = time.time()
    return {
        "observed_at": observed_at,
        "desktop_tree_text": result["desktop_tree_text"],
        "action_index": result["action_index"],
        "screen_elements": result["screen_elements"],
        "observation_artifact": {"screen": screen},
    }


def _render(windows: list[dict[str, Any]], screen: dict[str, int]) -> dict[str, Any]:
    def clean(v: Any) -> str:
        return " ".join(str(v or "").replace("\r", " ").replace("\n", " ").split())

    action_index: dict[str, dict[str, Any]] = {}
    screen_elements: list[dict[str, Any]] = []
    counter = {"n": 0}
    observation_id = f"s{time.time_ns():x}"
    lines = ["W0 Screen Desktop"]

    for wi, win in enumerate(windows, start=1):
        wid = f"W{wi}"
        title = win["title"] or f"Window_{win['hwnd']}"
        window_title = clean(title)
        window_rect = win["rect"]
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

        screen_elements.append({
            "id": wid, "observation_id": observation_id, "role": "Window",
            "name": window_title, "title": window_title, "text": window_title,
            "rect": window_rect,
            "px": (window_rect["left"] + window_rect["right"]) // 2,
            "py": (window_rect["top"] + window_rect["bottom"]) // 2,
            "hwnd": win["hwnd"], "owner_hwnd": win["hwnd"], "visible": True,
        })
        actionable = [e for e in elements if e.get("action")]
        for e in actionable:
            anc = nearest_action_ancestor(e)
            if anc is not None:
                action_children.setdefault(id(anc), []).append(e)
            else:
                roots.append(e)

        lines.append(f"{wid} Window {window_title} rect=({window_rect['left']},{window_rect['top']},{window_rect['right']},{window_rect['bottom']})")
        def emit(e: dict[str, Any], indent: int) -> None:
            # Reachability at the source: an element is offered as clickable ONLY where its
            # rect truly meets the screen AND its owner window. Intersect the three; if the
            # meeting is empty the element is unreachable (below the fold, scrolled out of a
            # virtual container) and is dropped, so promise equals provision - every entry in
            # action_index bears a click-point the hand will not refuse. The click guard stays.
            er = e.get("rect") or {}
            ix_l = max(int(er.get("left", 0)), int(window_rect["left"]), 0)
            ix_t = max(int(er.get("top", 0)), int(window_rect["top"]), 0)
            ix_r = min(int(er.get("right", 0)), int(window_rect["right"]), int(screen["width"]))
            ix_b = min(int(er.get("bottom", 0)), int(window_rect["bottom"]), int(screen["height"]))
            if ix_r <= ix_l or ix_b <= ix_t:
                return
            e["px"], e["py"] = (ix_l + ix_r) // 2, (ix_t + ix_b) // 2
            counter["n"] += 1
            sid = f"e{counter['n']}"
            e["short_id"] = sid
            action = str(e.get("action", "")) if e.get("enabled") is not False else ""
            raw_name = str(e.get("name", "") or "")
            name = clean(raw_name)
            body = str(e.get("text_full") or e.get("value") or raw_name)
            body_marker = f"body_chars={len(body)}" if body and body != raw_name else ""
            parts = [p for p in (
                sid, str(e.get("role", "")), name,
                f"[{action}]" if action else "", body_marker,
            ) if p]
            lines.append("  " * indent + " ".join(parts))
            public = {**{k: v for k, v in e.items() if k != "children"},
                      "short_id": sid, "action_key": sid, "observation_id": observation_id,
                      "window_id": wid, "window_title": window_title,
                      "body_chars": len(body)}
            action_index[sid] = public
            screen_elements.append({k: v for k, v in public.items() if k not in ("short_id", "action_key")})
            for child in action_children.get(id(e), []):
                emit(child, indent + 1)

        for e in roots:
            emit(e, 1)

    return {
        "action_index": action_index,
        "screen_elements": screen_elements,
        "desktop_tree_text": "\n".join(lines),
    }


import ctypes
import os
import subprocess
from ctypes import wintypes
from typing import Any

ROOT = __import__("pathlib").Path(__file__).resolve().parent
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
_ULONG_PTR = ctypes.c_size_t


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", _ULONG_PTR)]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", _ULONG_PTR)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


KEY_MAP: dict[str, int] = {
    "ctrl": 0x11, "control": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B, "windows": 0x5B,
    "enter": 0x0D, "return": 0x0D, "tab": 0x09, "escape": 0x1B, "esc": 0x1B, "space": 0x20,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "delete": 0x2E, "del": 0x2E, "backspace": 0x08, "insert": 0x2D,
    **{chr(ord("a") + i): 0x41 + i for i in range(26)},
    **{str(d): 0x30 + d for d in range(10)},
    **{f"f{n}": 0x6F + n for n in range(1, 13)},
}


class Desktop:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._automation: Any = None

    @property
    def automation(self) -> Any:
        if self._automation is None:
            self._automation = AUTOMATION
        return self._automation

    def observe(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        if config is None:
            cfg = self.config
        elif isinstance(config, dict):
            cfg = config
        else:
            cfg = self.config
        return observe(self, cfg)

    def click(self, x: int, y: int, hwnd: int) -> dict[str, Any]:
        width, height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        if not 0 <= x < width or not 0 <= y < height:
            raise RuntimeError(f"click coordinates ({x}, {y}) outside physical screen {width}x{height}")
        expected = int(user32.GetAncestor(wintypes.HWND(int(hwnd)), 2) or 0)
        if not expected:
            raise RuntimeError(f"click target hwnd {hwnd} is no longer valid")
        if not user32.SetCursorPos(x, y):
            raise ctypes.WinError()
        actual = int(user32.GetAncestor(user32.WindowFromPoint(wintypes.POINT(int(x), int(y))), 2) or 0)
        if actual != expected:
            raise RuntimeError(f"click point ({x}, {y}) belongs to hwnd {actual}, expected {expected}")
        user32.mouse_event(0x0002, 0, 0, 0, 0)
        user32.mouse_event(0x0004, 0, 0, 0, 0)
        return {"ok": True, "action": "click", "x": x, "y": y, "hwnd": hwnd, "screen": {"width": width, "height": height}}

    def set_clipboard(self, text: str) -> dict[str, Any]:
        command = ["powershell.exe", "-NoProfile", "-Command", "$in=[Console]::In.ReadToEnd(); Set-Clipboard -Value $in"]
        completed = subprocess.run(command, input=str(text).encode("utf-8"), capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if completed.returncode != 0:
            raise RuntimeError(f"clipboard write failed: {(completed.stderr or completed.stdout).decode('utf-8', 'replace').strip()}")
        return {"ok": True, "action": "set_clipboard", "chars": len(str(text))}

    def type_text(self, text: str) -> dict[str, Any]:
        s = str(text)
        code_units = list(s.encode("utf-16-le"))
        events = []
        for i in range(0, len(code_units), 2):
            unit = code_units[i] | (code_units[i + 1] << 8)
            for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
                events.append(_INPUT(type=1, u=_INPUTUNION(ki=_KEYBDINPUT(wVk=0, wScan=unit, dwFlags=flags, time=0, dwExtraInfo=0))))
        if not events:
            return {"ok": True, "action": "type_text", "chars": 0}
        arr = (_INPUT * len(events))(*events)
        sent = user32.SendInput(len(events), arr, ctypes.sizeof(_INPUT))
        if sent != len(events):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"ok": True, "action": "type_text", "chars": len(s)}

    def paste_clipboard(self, text: str) -> dict[str, Any]:
        self.set_clipboard(text)
        pasted = self.hotkey("ctrl", "v")
        if pasted.get("ok") is not True:
            raise RuntimeError(f"paste failed: {pasted}")
        return {"ok": True, "action": "paste_clipboard", "chars": len(str(text))}

    def press_key(self, key: str) -> dict[str, Any]:
        vk = KEY_MAP.get(str(key).strip().lower())
        if vk is None:
            raise RuntimeError(f"unknown key: {key}; known: {', '.join(sorted(KEY_MAP))}")
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, 2, 0)
        return {"ok": True, "action": "press_key", "key": key}

    def hotkey(self, *keys: Any) -> dict[str, Any]:
        if len(keys) == 1 and isinstance(keys[0], (list, tuple)):
            raw_parts = list(keys[0])
        elif len(keys) == 1:
            raw_parts = str(keys[0]).split("+")
        else:
            raw_parts = list(keys)
        parts = [str(k).strip().lower() for k in raw_parts if str(k).strip()]
        if not parts:
            raise RuntimeError("hotkey requires at least one key")
        vks = []
        for k in parts:
            vk = KEY_MAP.get(k)
            if vk is None:
                raise RuntimeError(f"unknown key in combination: {k}; known: {', '.join(sorted(KEY_MAP))}")
            vks.append(vk)
        for vk in vks[:-1]:
            user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vks[-1], 0, 0, 0)
        user32.keybd_event(vks[-1], 0, 2, 0)
        for vk in reversed(vks[:-1]):
            user32.keybd_event(vk, 0, 2, 0)
        return {"ok": True, "action": "hotkey", "keys": parts}

    def scroll(self, x: int, y: int, amount: int | None = None, hwnd: int = 0, *, clicks: int | None = None) -> dict[str, Any]:
        if (amount is None) == (clicks is None):
            raise TypeError("scroll requires exactly one of amount or clicks")
        amount = clicks if amount is None else amount
        width, height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        if not 0 <= x < width or not 0 <= y < height:
            raise RuntimeError(f"scroll coordinates ({x}, {y}) outside physical screen {width}x{height}")
        if not user32.SetCursorPos(x, y):
            raise ctypes.WinError()
        user32.mouse_event(0x0800, 0, 0, amount * 120, 0)
        return {"ok": True, "action": "scroll", "x": x, "y": y, "amount": amount, "hwnd": hwnd, "screen": {"width": width, "height": height}}

    def open_url(self, browser: str = "default", url: str = "") -> dict[str, Any]:
        if not str(url or "").strip():
            raise RuntimeError("open_url requires a non-empty url")
        browser_key = str(browser or "").strip().lower()
        if browser_key == "default":
            os.startfile(str(url))
            return {"ok": True, "action": "open_url", "browser": "default", "url": url}
        subprocess.Popen([str(browser), str(url)])
        return {"ok": True, "action": "open_url", "browser": browser_key, "url": url}


_desktop_instance: Desktop | None = None


def get_desktop(config: dict[str, Any] | None = None) -> Desktop:
    global _desktop_instance
    if user32 is None:
        _bind_windows()  # lazy: bind the Windows DLLs on first real use, not at import
    if _desktop_instance is None:
        _desktop_instance = Desktop(config)
    return _desktop_instance
import types as _types

_LAST_OBS = {"action_index": {}, "screen_elements": [], "desktop_tree_text": ""}


def _remember_observation(snap):
    """Install one looking without invalidating the live containers already seated in a deed."""
    new_action_index = dict(snap.get("action_index", {}) or {})
    new_screen_elements = list(snap.get("screen_elements", []) or [])
    action_index = _LAST_OBS["action_index"]
    action_index.clear()
    action_index.update(new_action_index)
    screen_elements = _LAST_OBS["screen_elements"]
    screen_elements[:] = new_screen_elements
    _LAST_OBS["desktop_tree_text"] = str(snap.get("desktop_tree_text", "") or "")
    return {
        "action_index": action_index,
        "screen_elements": screen_elements,
        "desktop_tree_text": _LAST_OBS["desktop_tree_text"],
    }


def snapshot_observation():
    return {
        "action_index": _LAST_OBS["action_index"],
        "screen_elements": _LAST_OBS["screen_elements"],
        "desktop_tree_text": _LAST_OBS["desktop_tree_text"],
    }


def restore_observation(snap):
    _remember_observation(snap)


# Windows DLLs are bound LAZILY on first get_desktop() — so this node imports on any OS and
# binds only when the hand is actually used (on the real Windows target). No import-time POST.


def _read_element(sid):
    """Reveal one element's WHOLE record from the current looking - the SAME dict shape as
    action_index[sid], its full untruncated body in ["text_full"]. One shape everywhere:
    read(id)["value"], read(id)["name"], read(id)["text_full"] all hold, as doth
    action_index[id]. Fail hard on a stale/unknown id."""
    idx = _LAST_OBS.get("action_index") or {}
    e = idx.get(sid)
    if e is None:
        raise KeyError("read: no element %r in the fresh scan; a short id dieth with the looking that bore it" % (sid,))
    return e


def _host_facts():
    import getpass, platform, shutil, sys as _s
    try:
        user = getpass.getuser()
    except Exception:
        user = "(unknown)"
    tools = [t for t in ("git", "python", "powershell.exe", "pwsh", "cmd", "bash", "node", "curl", "pip") if shutil.which(t)]
    return "\n".join([
        "HOST",
        "platform: %s (%s)" % (platform.platform(), _s.platform),
        "machine: %s" % platform.node(),
        "user: %s" % user,
        "cwd: %s" % os.getcwd(),
        "repo_root: %s" % ROOT,
        "python: %s" % _s.executable,
        "shell_tools: %s" % (", ".join(tools) or "(none found)"),
    ])


# ──────────────────────────────────────────────────────────────────────────────────────
#  NODE HOOKS — how the kernel seats this card (the OSI payload: what it MEANS + what it DOES)
# ──────────────────────────────────────────────────────────────────────────────────────
def environment(bb, cfg=None):
    """Kernel perception hook: refresh the [environment] blackboard section from a fresh scan."""
    facts = _host_facts()
    d = get_desktop()
    obs_cfg = (cfg or {}).get("observation", {})
    obs_result = _remember_observation(d.observe(obs_cfg))
    _LAST_OBS["desktop_tree_text"] = _LAST_OBS["desktop_tree_text"].strip()
    tree = _LAST_OBS["desktop_tree_text"] or "(no interactable elements observed)"
    bb.set("environment", facts + "\n\nSCREEN\n" + tree)


def namespace(context=None):
    """Kernel namespace hook: the eyes and hand injected into the exec namespace. The WITNESS
    receives eyes-only reads of the screen it did not itself paint - it may weigh screen state as
    one surface among many, but it holds no hand and so cannot fake the effect it judges. The
    ACTOR receives the full desktop hand. This is the separated-powers spine, not a toggle."""
    ctx = context or {}
    kind = ctx.get("kind", "actor")
    ns = {
        "screen_elements": _LAST_OBS["screen_elements"],
        "desktop_tree_text": _LAST_OBS["desktop_tree_text"],
        "action_index": _LAST_OBS["action_index"],
        "read": _read_element,
    }
    if kind == "witness":
        return ns
    d = get_desktop()

    def observe_live(config=None):
        return _remember_observation(d.observe(config))

    ns["desktop"] = _types.SimpleNamespace(
        click=d.click, type_text=d.type_text, paste_clipboard=d.paste_clipboard,
        set_clipboard=d.set_clipboard, press_key=d.press_key, hotkey=d.hotkey,
        scroll=d.scroll, open_url=d.open_url, observe=observe_live,
    )
    return ns
