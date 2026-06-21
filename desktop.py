"""Desktop observer - hover probe primary plus bounded UIA desktop tree."""
from __future__ import annotations
import ctypes
import ctypes.wintypes as W
import math
import time
from dataclasses import dataclass
from typing import Any

PROBE_STEP_PX = 90
PROBE_DELAY = 0.001
SCROLL_ENRICH_MIN = 3
SCROLL_ENRICH_PASSES = (-3, -2, 2, 3)
SCROLL_ENRICH_DELAY = 0.08
SINE_AMP_RATIO = 0.4
SINE_PERIOD = 6.0
READ_TEXT_MAX = 200
FOCUS_DELAY = 0.3

OBSERVE_DEFAULTS = {
    "probe_step_px": PROBE_STEP_PX,
    "probe_delay_ms": int(PROBE_DELAY * 1000),
    "dense_probe_min_px": 45,
    "scroll_enrich_min": SCROLL_ENRICH_MIN,
    "scroll_enrich_passes": list(SCROLL_ENRICH_PASSES),
    "scroll_enrich_delay_ms": int(SCROLL_ENRICH_DELAY * 1000),
    "read_text_max": READ_TEXT_MAX,
    "node_value_max_chars": 1000,
    "render_value_max_chars": 80,
    "window_limit": 8,
    "desktop_tree_enabled": True,
    "desktop_tree_max_depth": 5,
    "desktop_tree_max_nodes": 220,
    "desktop_tree_child_limit": 80,
    "tree_value_max_chars": 600,
    "render_tree_value_max_chars": 160,
    "overlay_window_limit": 32,
}
OBSERVE_CONFIG = dict(OBSERVE_DEFAULTS)


def configure_observation(config: dict[str, Any] | None = None) -> None:
    """Update observer detail from wiring.json without coupling desktop.py to it."""
    global OBSERVE_CONFIG
    merged = dict(OBSERVE_DEFAULTS)
    if isinstance(config, dict):
        for key in OBSERVE_DEFAULTS:
            if key in config:
                merged[key] = config[key]
    OBSERVE_CONFIG = merged


def _obs_int(key: str, default: int) -> int:
    try:
        return int(OBSERVE_CONFIG.get(key, default))
    except (TypeError, ValueError):
        return default


def _obs_float_ms(key: str, default_seconds: float) -> float:
    try:
        return max(0.0, float(OBSERVE_CONFIG.get(key, default_seconds * 1000.0)) / 1000.0)
    except (TypeError, ValueError):
        return default_seconds


def _obs_clip(text: str, limit_key: str, default: int) -> str:
    limit = _obs_int(limit_key, default)
    if limit <= 0:
        return text
    return text[:limit]

UIA_CONTROL_TYPE_MAP: dict[int, str] = {
    50000: "Button", 50001: "Calendar", 50002: "CheckBox", 50003: "ComboBox",
    50004: "Edit", 50005: "Hyperlink", 50006: "Image", 50007: "ListItem",
    50008: "List", 50009: "Menu", 50010: "MenuBar", 50011: "MenuItem",
    50012: "ProgressBar", 50013: "RadioButton", 50014: "ScrollBar", 50015: "Slider",
    50016: "Spinner", 50017: "StatusBar", 50018: "Tab", 50019: "TabItem",
    50020: "Text", 50021: "ToolBar", 50022: "ToolTip", 50023: "Tree",
    50024: "TreeItem", 50025: "Custom", 50026: "Group", 50027: "Thumb",
    50028: "DataGrid", 50029: "DataItem", 50030: "Document", 50031: "SplitButton",
    50032: "Window", 50033: "Pane", 50034: "Header", 50035: "HeaderItem",
    50036: "Table", 50037: "TitleBar", 50038: "Separator",
}

VK_MAP: dict[str, int] = {
    "enter": 0x0D, "return": 0x0D, "tab": 0x09, "escape": 0x1B, "esc": 0x1B,
    "backspace": 0x08, "delete": 0x2E, "del": 0x2E, "insert": 0x2D,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "ctrl": 0x11, "control": 0x11, "alt": 0x12, "shift": 0x10,
    "win": 0x5B, "space": 0x20,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74,
    "f6": 0x75, "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79,
    "f11": 0x7A, "f12": 0x7B,
    "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD,
    "\\": 0xDC, ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF,
} | {chr(ord("a") + i): ord("A") + i for i in range(26)} | {chr(ord("0") + i): ord("0") + i for i in range(10)}

EXTENDED_VKS: frozenset[int] = frozenset({0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E})

ACTIONABLE_ROLES = frozenset({
    "Button", "Edit", "ComboBox", "ListItem", "Hyperlink", "MenuItem",
    "TabItem", "SplitButton", "CheckBox", "RadioButton", "Slider",
    "Document", "Text", "ScrollBar", "TreeItem", "DataItem", "Custom",
})
CLICKABLE_ROLES = frozenset({
    "Button", "MenuItem", "ListItem", "Hyperlink", "TabItem", "TreeItem",
    "SplitButton", "CheckBox", "RadioButton", "Slider", "ScrollBar", "DataItem",
})
WRITABLE_ROLES = frozenset({"Edit", "ComboBox", "Document"})


@dataclass(slots=True)
class Element:
    id: str
    role: str
    name: str
    value: str
    hwnd: int
    px: int
    py: int
    pw: int
    ph: int
    action: str
    wnd: str = ""
    enabled: bool = True
    readonly: bool = False


@dataclass(slots=True)
class Observation:
    focused_title: str
    elements: dict[str, Element]
    context_text: str
    snapshot: dict[str, Any] | None = None


class _UIA:
    """Minimal COM UIA wrapper for hover probing and bounded tree walking."""

    CLSCTX_INPROC = 1
    VT_I4 = 3
    VT_BSTR = 8
    VT_BOOL = 11
    VT_R8_ARRAY = 8197
    UIA_BOUNDING_RECT = 30001
    UIA_CONTROL_TYPE = 30003
    UIA_NAME = 30005
    UIA_IS_ENABLED = 30010
    UIA_IS_OFFSCREEN = 30022
    UIA_NATIVE_WINDOW_HANDLE = 30020
    UIA_ELEMENT_FROM_POINT = 7
    UIA_GET_ROOT_ELEMENT = 5
    UIA_GET_PROPERTY = 10
    UIA_FIND_ALL = 6
    UIA_CREATE_TRUE_CONDITION = 21
    UIA_ARRAY_LENGTH = 3
    UIA_ARRAY_GET_ELEMENT = 4
    UIA_PROCESS_ID = 30002
    UIA_LEGACY_PATTERN = 10018
    LEGACY_VALUE_INDEX = 8
    UIA_TEXT_PATTERN = 10014
    TEXT_DOC_RANGE = 7
    TEXT_GET_TEXT = 12
    UIA_AUTOMATION_ID = 30011
    UIA_CLASS_NAME = 30012
    UIA_IS_CONTROL_ELEMENT = 30016

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", W.DWORD), ("Data2", W.WORD), ("Data3", W.WORD), ("Data4", ctypes.c_ubyte * 8)]

    class VARIANT(ctypes.Structure):
        _fields_ = [("vt", W.WORD), ("r1", W.WORD), ("r2", W.WORD), ("r3", W.WORD), ("val", ctypes.c_ulonglong)]

    class SAFEARRAY(ctypes.Structure):
        class BOUND(ctypes.Structure):
            _fields_ = [("cElements", W.DWORD), ("lLbound", W.LONG)]
        _fields_ = [("cDims", W.USHORT), ("fFeatures", W.USHORT), ("cbElements", W.DWORD),
                    ("cLocks", W.DWORD), ("pvData", ctypes.c_void_p), ("rgsabound", BOUND * 1)]

    def __init__(self):
        import uuid
        self.ole32 = ctypes.OleDLL("ole32")
        self.oleaut32 = ctypes.WinDLL("oleaut32")
        self.oleaut32.SysFreeString.argtypes = [ctypes.c_void_p]
        self.oleaut32.SysFreeString.restype = None
        self.oleaut32.SafeArrayDestroy.argtypes = [ctypes.c_void_p]
        self.ole32.CoInitialize(None)
        clsid = self._make_guid("ff48dba4-60ef-4201-aa87-54103eef594e")
        iid = self._make_guid("30cbe57d-d9d0-452a-ab13-7ac5ac4825ee")
        self._uia = ctypes.c_void_p()
        self.ole32.CoCreateInstance(ctypes.byref(clsid), None, self.CLSCTX_INPROC,
                                    ctypes.byref(iid), ctypes.byref(self._uia))
        self._iid_legacy = self._make_guid("828055ad-355b-4435-86d5-3b51c14a9b1b")
        self._iid_text = self._make_guid("32eba289-3583-42c9-9c59-3b6d9a1e9b6a")

    def _make_guid(self, s: str) -> "IA.GUID":
        import uuid as _uuid
        b = _uuid.UUID(s).bytes
        return self.GUID(
            int.from_bytes(b[0:4], "big"), int.from_bytes(b[4:6], "big"),
            int.from_bytes(b[6:8], "big"), (ctypes.c_ubyte * 8)(*b[8:16]))

    def _vt(self, this: ctypes.c_void_p, idx: int, proto_args: tuple, *args):
        vtable = ctypes.cast(this, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        proto = ctypes.WINFUNCTYPE(ctypes.HRESULT, *proto_args)
        return proto(vtable[idx])(this, *args)

    def _release(self, ptr: ctypes.c_void_p):
        if ptr.value:
            vtable = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
            proto = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
            proto(vtable[2])(ptr)

    def element_from_point(self, px: int, py: int) -> ctypes.c_void_p | None:
        packed = ctypes.c_int64(px | (py << 32))
        found = ctypes.c_void_p()
        hr = self._vt(self._uia, self.UIA_ELEMENT_FROM_POINT,
                      (ctypes.c_void_p, ctypes.c_int64, ctypes.POINTER(ctypes.c_void_p)),
                      packed, ctypes.byref(found))
        return found if hr == 0 and found.value else None

    def root_element(self) -> ctypes.c_void_p | None:
        root = ctypes.c_void_p()
        hr = self._vt(self._uia, self.UIA_GET_ROOT_ELEMENT,
                      (ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)),
                      ctypes.byref(root))
        return root if hr == 0 and root.value else None

    def true_condition(self) -> ctypes.c_void_p | None:
        condition = ctypes.c_void_p()
        hr = self._vt(self._uia, self.UIA_CREATE_TRUE_CONDITION,
                      (ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)),
                      ctypes.byref(condition))
        return condition if hr == 0 and condition.value else None

    def find_all_children(self, el: ctypes.c_void_p, condition: ctypes.c_void_p) -> ctypes.c_void_p | None:
        found = ctypes.c_void_p()
        hr = self._vt(el, self.UIA_FIND_ALL,
                      (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)),
                      ctypes.c_int(2), condition, ctypes.byref(found))
        return found if hr == 0 and found.value else None

    def array_length(self, arr: ctypes.c_void_p) -> int:
        length = ctypes.c_int()
        hr = self._vt(arr, self.UIA_ARRAY_LENGTH,
                      (ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)),
                      ctypes.byref(length))
        return int(length.value) if hr == 0 else 0

    def array_get(self, arr: ctypes.c_void_p, index: int) -> ctypes.c_void_p | None:
        el = ctypes.c_void_p()
        hr = self._vt(arr, self.UIA_ARRAY_GET_ELEMENT,
                      (ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)),
                      ctypes.c_int(index), ctypes.byref(el))
        return el if hr == 0 and el.value else None

    def get_property(self, el: ctypes.c_void_p, prop_id: int):
        var = self.VARIANT()
        self._vt(el, self.UIA_GET_PROPERTY,
                 (ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(self.VARIANT)),
                 ctypes.c_int(prop_id), ctypes.byref(var))
        return var

    def get_str(self, el: ctypes.c_void_p, prop_id: int) -> str:
        var = self.get_property(el, prop_id)
        if var.vt == self.VT_BSTR:
            ptr = ctypes.c_void_p(var.val)
            s = ctypes.cast(ptr, ctypes.c_wchar_p).value or ""
            self.oleaut32.SysFreeString(ptr)
            return s
        return ""

    def get_int(self, el: ctypes.c_void_p, prop_id: int) -> int:
        var = self.get_property(el, prop_id)
        return int(var.val & 0xFFFFFFFF) if var.vt == self.VT_I4 else 0

    def get_bool(self, el: ctypes.c_void_p, prop_id: int) -> bool:
        var = self.get_property(el, prop_id)
        return (var.val & 0xFFFF) == 0xFFFF if var.vt == self.VT_BOOL else False

    def get_rect(self, el: ctypes.c_void_p) -> tuple[int, int, int, int]:
        var = self.get_property(el, self.UIA_BOUNDING_RECT)
        if var.vt == self.VT_R8_ARRAY:
            sa_ptr = ctypes.c_void_p(var.val)
            sa = ctypes.cast(sa_ptr, ctypes.POINTER(self.SAFEARRAY)).contents
            d = (ctypes.c_double * 4).from_address(sa.pvData)
            result = (int(d[0]), int(d[1]), int(d[2]), int(d[3]))
            self.oleaut32.SafeArrayDestroy(sa_ptr)
            return result
        return (0, 0, 0, 0)

    def get_legacy_value(self, el: ctypes.c_void_p) -> str:
        pattern = ctypes.c_void_p()
        hr = self._vt(el, 14,
                      (ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(self.GUID), ctypes.POINTER(ctypes.c_void_p)),
                      ctypes.c_int(self.UIA_LEGACY_PATTERN), ctypes.byref(self._iid_legacy), ctypes.byref(pattern))
        if hr != 0 or not pattern.value:
            return ""
        bstr = ctypes.c_wchar_p()
        hr2 = self._vt(pattern, self.LEGACY_VALUE_INDEX,
                       (ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)), ctypes.byref(bstr))
        self._release(pattern)
        return bstr.value or "" if hr2 == 0 else ""

    def get_text_content(self, el: ctypes.c_void_p, max_len: int = READ_TEXT_MAX) -> str:
        pattern = ctypes.c_void_p()
        hr = self._vt(el, 14,
                      (ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(self.GUID), ctypes.POINTER(ctypes.c_void_p)),
                      ctypes.c_int(self.UIA_TEXT_PATTERN), ctypes.byref(self._iid_text), ctypes.byref(pattern))
        if hr != 0 or not pattern.value:
            return ""
        doc_range = ctypes.c_void_p()
        hr2 = self._vt(pattern, self.TEXT_DOC_RANGE,
                       (ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)), ctypes.byref(doc_range))
        if hr2 != 0 or not doc_range.value:
            self._release(pattern)
            return ""
        bstr = ctypes.c_wchar_p()
        hr3 = self._vt(doc_range, self.TEXT_GET_TEXT,
                       (ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_wchar_p)),
                       ctypes.c_int(max_len), ctypes.byref(bstr))
        text = bstr.value or "" if hr3 == 0 else ""
        self._release(doc_range)
        self._release(pattern)
        return text


class Desktop:
    """Desktop observer using mouse hover probing only."""

    def __init__(self):
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        self.user32.GetForegroundWindow.restype = W.HWND
        self.user32.GetTopWindow.restype = W.HWND
        self.user32.GetWindow.restype = W.HWND
        self.user32.GetAncestor.restype = W.HWND
        self._uia = _UIA()

    def observe(self) -> Observation:
        screen_w = self.user32.GetSystemMetrics(0)
        screen_h = self.user32.GetSystemMetrics(1)
        focused_hwnd = int(self.user32.GetForegroundWindow())
        focused_title = self._get_window_title(focused_hwnd) or "Desktop"
        if focused_title.strip().lower() in {"desktop", "program manager"}:
            fallback = self._top_application_window()
            if fallback:
                focused_hwnd, focused_title = fallback

        rect = self._get_window_rect(focused_hwnd)
        if rect:
            x0, y0, x1, y1 = rect
        else:
            x0, y0, x1, y1 = 0, 0, screen_w, screen_h

        saved = W.POINT()
        self.user32.GetCursorPos(ctypes.byref(saved))
        probe_step = max(10, _obs_int("probe_step_px", PROBE_STEP_PX))
        enrich_min = max(0, _obs_int("scroll_enrich_min", SCROLL_ENRICH_MIN))
        window_infos = self._window_infos(
            focused_hwnd,
            limit=max(1, _obs_int("overlay_window_limit", 32)),
            include_untitled=True,
        )
        z_index = {int(w["hwnd"]): int(w["z"]) for w in window_infos}
        overlay_hwnds = self._overlay_hwnds(focused_hwnd, rect, window_infos)

        nodes = self._probe(x0, y0, x1, y1, focused_hwnd, step=probe_step)
        if len(nodes) < enrich_min:
            dense_step = max(_obs_int("dense_probe_min_px", 45), probe_step // 2)
            extra = self._probe(0, 0, screen_w, screen_h, focused_hwnd, step=dense_step)
            seen = {(n["role"], n.get("name", ""), n["x"], n["y"], n["w"], n["h"]) for n in nodes}
            for n in extra:
                key = (n["role"], n.get("name", ""), n["x"], n["y"], n["w"], n["h"])
                if key not in seen:
                    seen.add(key)
                    nodes.append(n)
        classified = self._classify(nodes, z_index)
        if len(classified) < enrich_min:
            cx = max(x0 + 40, min(x1 - 40, (x0 + x1) // 2))
            cy = max(y0 + 40, min(y1 - 40, (y0 + y1) // 2))
            seen = {(n["role"], n.get("name", ""), n["x"], n["y"], n["w"], n["h"]) for n in nodes}
            passes = OBSERVE_CONFIG.get("scroll_enrich_passes", SCROLL_ENRICH_PASSES)
            if not isinstance(passes, (list, tuple)):
                passes = SCROLL_ENRICH_PASSES
            for amount in passes:
                self.scroll(cx, cy, amount)
                time.sleep(_obs_float_ms("scroll_enrich_delay_ms", SCROLL_ENRICH_DELAY))
                for n in self._probe(x0, y0, x1, y1, focused_hwnd, step=probe_step):
                    key = (n["role"], n.get("name", ""), n["x"], n["y"], n["w"], n["h"])
                    if key not in seen:
                        seen.add(key)
                        nodes.append(n)
            classified = self._classify(nodes, z_index)
        self.user32.SetCursorPos(saved.x, saved.y)
        elements, context_text = self._render(classified, focused_title, focused_hwnd, overlay_hwnds)
        tree_snapshot = None
        tree_error = ""
        if OBSERVE_CONFIG.get("desktop_tree_enabled", True):
            try:
                tree_snapshot = self._desktop_tree_snapshot(window_infos)
                tree_lines = self._desktop_tree_lines(tree_snapshot)
            except Exception as e:
                tree_error = f"{type(e).__name__}: {e}"
                tree_lines = [f"TREE_ERROR: {type(e).__name__}: {e}"]
            if tree_lines:
                context_text += "\nDESKTOP_TREE:\n" + "\n".join(tree_lines)
        windows = self._window_titles(focused_hwnd, limit=max(1, _obs_int("window_limit", 8)))
        if windows:
            context_text += "\nWINDOWS:\n" + "\n".join(f"  {w}" for w in windows)
        if not elements:
            context_text += (
                "\n  (no interactive elements — use hotkey win+r for Run dialog, "
                "or focus with window title substring)"
            )
        snapshot = self._observation_snapshot(focused_title, focused_hwnd, elements, window_infos, tree_snapshot, tree_error)
        return Observation(focused_title=focused_title, elements=elements, context_text=context_text, snapshot=snapshot)

    def click(self, px: int, py: int, hwnd: int = 0):
        if hwnd:
            self.user32.SetForegroundWindow(hwnd)
            time.sleep(0.05)
        self.user32.SetCursorPos(px, py)
        time.sleep(0.02)
        self.user32.mouse_event(0x0002, 0, 0, 0, 0)
        time.sleep(0.05)
        self.user32.mouse_event(0x0004, 0, 0, 0, 0)

    def type_text(self, text: str):
        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", W.WORD), ("wScan", W.WORD), ("dwFlags", W.DWORD),
                        ("time", W.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

        class INPUT(ctypes.Structure):
            class _U(ctypes.Union):
                _fields_ = [("ki", KEYBDINPUT), ("_pad", ctypes.c_ubyte * 32)]
            _fields_ = [("type", W.DWORD), ("u", _U)]

        for char in text:
            inputs = (INPUT * 2)()
            inputs[0].type = 1
            inputs[0].u.ki.wScan = ord(char)
            inputs[0].u.ki.dwFlags = 0x0004
            inputs[1].type = 1
            inputs[1].u.ki.wScan = ord(char)
            inputs[1].u.ki.dwFlags = 0x0006
            self.user32.SendInput(2, ctypes.byref(inputs), ctypes.sizeof(INPUT))
            time.sleep(0.03)

    def press_key(self, key: str):
        vk = VK_MAP.get(key.lower())
        if not vk:
            return
        flags = 0x0001 if vk in EXTENDED_VKS else 0
        self.user32.keybd_event(vk, 0, flags, None)
        time.sleep(0.03)
        self.user32.keybd_event(vk, 0, 0x0002 | flags, None)

    def hotkey(self, keys: list[str]):
        vks = [VK_MAP[k.lower()] for k in keys if k.lower() in VK_MAP]
        for vk in vks:
            self.user32.keybd_event(vk, 0, 0x0001 if vk in EXTENDED_VKS else 0, None)
            time.sleep(0.03)
        for vk in reversed(vks):
            self.user32.keybd_event(vk, 0, 0x0002 | (0x0001 if vk in EXTENDED_VKS else 0), None)
            time.sleep(0.03)

    def scroll(self, px: int, py: int, amount: int = 3, hwnd: int = 0):
        if hwnd:
            self.user32.SetForegroundWindow(hwnd)
            time.sleep(0.05)
        self.user32.SetCursorPos(px, py)
        time.sleep(0.02)
        self.user32.mouse_event(0x0800, 0, 0, amount * 120, 0)

    def focus_window(self, title: str) -> bool:
        import re
        title_l = title.lower().strip()
        keywords = [w for w in re.split(r"[\s\-]+", title_l) if len(w) > 3]
        best_hwnd = None
        best_score = 99
        hwnd = self.user32.GetTopWindow(None)
        while hwnd:
            if self.user32.IsWindowVisible(hwnd):
                wt = self._get_window_title(int(hwnd))
                wt_l = wt.lower()
                if title_l in wt_l or wt_l in title_l:
                    return self._set_foreground_verified(int(hwnd), title_l, keywords)
                overlap = sum(1 for w in keywords if w in wt_l)
                if overlap and overlap < best_score:
                    best_score = overlap
                    best_hwnd = hwnd
            hwnd = self.user32.GetWindow(hwnd, 2)
        if best_hwnd:
            return self._set_foreground_verified(int(best_hwnd), title_l, keywords)
        return False

    def _set_foreground_verified(self, hwnd: int, title_l: str, keywords: list[str]) -> bool:
        self.user32.SetForegroundWindow(W.HWND(hwnd))
        time.sleep(FOCUS_DELAY)
        active = int(self.user32.GetForegroundWindow() or 0)
        if not active:
            return False
        active_root = self._root_hwnd(active)
        target_root = self._root_hwnd(hwnd)
        if active == hwnd or (active_root and active_root == target_root):
            return True
        active_title = self._get_window_title(active).lower()
        if title_l and (title_l in active_title or active_title in title_l):
            return True
        return bool(keywords and any(w in active_title for w in keywords))

    def _window_titles(self, focused_hwnd: int, limit: int = 8) -> list[str]:
        return [
            f"{'*' if w['focused'] else '-'} {w['title']}"
            for w in self._window_infos(focused_hwnd, limit=limit, include_untitled=False)
        ]

    def _window_infos(self, focused_hwnd: int, limit: int = 8, include_untitled: bool = False) -> list[dict[str, Any]]:
        infos: list[dict[str, Any]] = []
        seen: set[int] = set()
        hwnd = self.user32.GetTopWindow(None)
        z = 0
        while hwnd and len(infos) < limit:
            ihwnd = int(hwnd)
            if ihwnd not in seen and self.user32.IsWindowVisible(hwnd):
                seen.add(ihwnd)
                title = self._get_window_title(ihwnd).strip()
                if title or include_untitled:
                    infos.append({
                        "hwnd": ihwnd,
                        "title": title or "(untitled)",
                        "rect": self._get_window_rect(ihwnd),
                        "focused": ihwnd == focused_hwnd,
                        "z": z,
                    })
                    z += 1
            hwnd = self.user32.GetWindow(hwnd, 2)
        return infos

    def _overlay_hwnds(
        self,
        focused_hwnd: int,
        focused_rect: tuple[int, int, int, int] | None,
        window_infos: list[dict[str, Any]],
    ) -> set[int]:
        if not focused_hwnd or not focused_rect:
            return set()
        overlays: set[int] = set()
        for info in window_infos:
            hwnd = int(info.get("hwnd", 0) or 0)
            if hwnd == focused_hwnd:
                break
            rect = info.get("rect")
            if rect and self._rects_intersect(focused_rect, rect):
                overlays.add(hwnd)
        return overlays

    @staticmethod
    def _rects_intersect(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
        return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])

    def _root_hwnd(self, hwnd: int) -> int:
        if not hwnd:
            return 0
        root = self.user32.GetAncestor(W.HWND(hwnd), 2)
        return int(root) if root else int(hwnd)

    def _top_application_window(self) -> tuple[int, str] | None:
        hwnd = self.user32.GetTopWindow(None)
        while hwnd:
            if self.user32.IsWindowVisible(hwnd):
                title = self._get_window_title(int(hwnd)).strip()
                if title and title.lower() not in {"desktop", "program manager"}:
                    return int(hwnd), title
            hwnd = self.user32.GetWindow(hwnd, 2)
        return None

    def _get_window_title(self, hwnd: int) -> str:
        buf = ctypes.create_unicode_buffer(512)
        self.user32.GetWindowTextW(W.HWND(hwnd), buf, 512)
        return buf.value

    def _get_window_rect(self, hwnd: int) -> tuple[int, int, int, int] | None:
        rect = W.RECT()
        if self.user32.GetWindowRect(W.HWND(hwnd), ctypes.byref(rect)):
            return (rect.left, rect.top, rect.right, rect.bottom)
        return None

    def _desktop_tree_snapshot(self, window_infos: list[dict[str, Any]]) -> dict[str, Any]:
        max_depth = max(1, _obs_int("desktop_tree_max_depth", 5))
        max_nodes = max(1, _obs_int("desktop_tree_max_nodes", 220))
        child_limit = max(1, _obs_int("desktop_tree_child_limit", 80))
        root = self._uia.root_element()
        if not root:
            raise RuntimeError("UIA root element unavailable")
        condition = self._uia.true_condition()
        if not condition:
            self._uia._release(root)
            raise RuntimeError("UIA true condition unavailable")
        counter = {"count": 0, "truncated": False}
        try:
            root_node = self._collect_tree_node(root, condition, 0, max_depth, max_nodes, child_limit, counter)
        finally:
            self._uia._release(condition)
            self._uia._release(root)
        if not root_node:
            return {}
        z_index = {int(w["hwnd"]): int(w["z"]) for w in window_infos}
        self._order_root_tree(root_node, z_index)
        return {
            "order": "top-level windows are rendered top-to-bottom by Win32 z-order; [ID] targets are the actionable scope",
            "root": root_node,
            "node_count": counter["count"],
            "truncated": bool(counter.get("truncated")),
            "max_depth": max_depth,
            "max_nodes": max_nodes,
            "child_limit": child_limit,
        }

    def _desktop_tree_lines(self, snapshot: dict[str, Any]) -> list[str]:
        root_node = snapshot.get("root")
        if not root_node:
            return []
        lines = [
            f"  ORDER: {snapshot.get('order', '')}.",
            f"  TREE_NODES: {snapshot.get('node_count', 0)}",
        ]
        self._render_tree_node(root_node, lines, 1)
        if snapshot.get("truncated"):
            lines.append(f"  ... tree truncated at {snapshot.get('max_nodes', '?')} UIA nodes")
        return lines

    def _observation_snapshot(
        self,
        focused_title: str,
        focused_hwnd: int,
        elements: dict[str, Element],
        window_infos: list[dict[str, Any]],
        tree_snapshot: dict[str, Any] | None,
        tree_error: str,
    ) -> dict[str, Any]:
        return {
            "focused_title": focused_title,
            "focused_hwnd": int(focused_hwnd or 0),
            "action_scope": "focused_window_or_top_overlay",
            "elements": [
                {
                    "id": e.id,
                    "role": e.role,
                    "name": e.name,
                    "value": e.value,
                    "hwnd": e.hwnd,
                    "x": e.px,
                    "y": e.py,
                    "w": e.pw,
                    "h": e.ph,
                    "action": e.action,
                    "window": e.wnd,
                    "enabled": e.enabled,
                    "readonly": e.readonly,
                }
                for e in elements.values()
            ],
            "windows": [
                {
                    "hwnd": int(w.get("hwnd", 0) or 0),
                    "title": w.get("title", ""),
                    "rect": list(w["rect"]) if w.get("rect") else None,
                    "focused": bool(w.get("focused")),
                    "z": int(w.get("z", 0) or 0),
                }
                for w in window_infos
            ],
            "desktop_tree": tree_snapshot,
            "desktop_tree_error": tree_error,
        }

    def _collect_tree_node(
        self,
        el: ctypes.c_void_p,
        condition: ctypes.c_void_p,
        depth: int,
        max_depth: int,
        max_nodes: int,
        child_limit: int,
        counter: dict[str, Any],
    ) -> dict[str, Any] | None:
        if counter["count"] >= max_nodes:
            counter["truncated"] = True
            return None
        counter["count"] += 1
        node = self._tree_snapshot(el)
        node["children"] = []
        if depth >= max_depth:
            return node
        arr = self._uia.find_all_children(el, condition)
        if not arr:
            return node
        try:
            total = self._uia.array_length(arr)
            limit = min(total, child_limit)
            for i in range(limit):
                if counter["count"] >= max_nodes:
                    counter["truncated"] = True
                    break
                child = self._uia.array_get(arr, i)
                if not child:
                    continue
                try:
                    child_node = self._collect_tree_node(child, condition, depth + 1, max_depth, max_nodes, child_limit, counter)
                    if child_node and self._tree_node_visible(child_node):
                        node["children"].append(child_node)
                finally:
                    self._uia._release(child)
            if total > limit:
                node["children_truncated"] = total - limit
        finally:
            self._uia._release(arr)
        return node

    def _tree_snapshot(self, el: ctypes.c_void_p) -> dict[str, Any]:
        ct = self._uia.get_int(el, _UIA.UIA_CONTROL_TYPE)
        role = UIA_CONTROL_TYPE_MAP.get(ct, f"ControlType{ct}" if ct else "Element")
        hwnd = self._uia.get_int(el, _UIA.UIA_NATIVE_WINDOW_HANDLE)
        x, y, w, h = self._uia.get_rect(el)
        value = self._uia.get_legacy_value(el)
        return {
            "role": role,
            "name": _obs_clip(self._uia.get_str(el, _UIA.UIA_NAME), "tree_value_max_chars", 600),
            "value": _obs_clip(value, "tree_value_max_chars", 600),
            "automation_id": self._uia.get_str(el, _UIA.UIA_AUTOMATION_ID),
            "class_name": self._uia.get_str(el, _UIA.UIA_CLASS_NAME),
            "hwnd": hwnd,
            "root_hwnd": self._root_hwnd(hwnd),
            "x": x,
            "y": y,
            "w": w,
            "h": h,
            "enabled": self._uia.get_bool(el, _UIA.UIA_IS_ENABLED),
            "offscreen": self._uia.get_bool(el, _UIA.UIA_IS_OFFSCREEN),
            "control": self._uia.get_bool(el, _UIA.UIA_IS_CONTROL_ELEMENT),
        }

    def _tree_node_visible(self, node: dict[str, Any]) -> bool:
        if node.get("children"):
            return True
        if node.get("offscreen"):
            return False
        return bool(node.get("name") or node.get("value") or (node.get("w", 0) > 0 and node.get("h", 0) > 0))

    def _order_root_tree(self, root_node: dict[str, Any], z_index: dict[int, int]) -> None:
        children = root_node.get("children") or []
        children.sort(key=lambda n: (
            z_index.get(int(n.get("root_hwnd") or n.get("hwnd") or 0), 9999),
            int(n.get("y", 0)),
            int(n.get("x", 0)),
        ))

    def _render_tree_node(self, node: dict[str, Any], lines: list[str], depth: int) -> None:
        indent = "  " * depth
        role = node.get("role") or "Element"
        name = _obs_clip(node.get("name", ""), "render_tree_value_max_chars", 160)
        value = _obs_clip(node.get("value", ""), "render_tree_value_max_chars", 160)
        bits = [role]
        if name:
            bits.append(f'"{name}"')
        if value and value != name:
            bits.append(f'= "{value}"')
        if node.get("class_name"):
            bits.append(f"class={node['class_name']}")
        hwnd = int(node.get("root_hwnd") or node.get("hwnd") or 0)
        if hwnd:
            bits.append(f"hwnd={hwnd}")
        if node.get("w", 0) > 0 and node.get("h", 0) > 0:
            bits.append(f"@ {node['x']},{node['y']} {node['w']}x{node['h']}")
        if node.get("offscreen"):
            bits.append("offscreen")
        lines.append(indent + " ".join(bits))
        for child in node.get("children", []):
            self._render_tree_node(child, lines, depth + 1)
        if node.get("children_truncated"):
            lines.append(f"{indent}  ... {node['children_truncated']} more children")

    def _probe(self, x0: int, y0: int, x1: int, y1: int, hwnd: int, step: int | None = None) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        seen_keys: set[tuple] = set()
        step = step or max(10, _obs_int("probe_step_px", PROBE_STEP_PX))
        amp = step * SINE_AMP_RATIO
        freq = 2 * math.pi / (step * SINE_PERIOD)
        probe_delay = _obs_float_ms("probe_delay_ms", PROBE_DELAY)
        read_text_max = max(0, _obs_int("read_text_max", READ_TEXT_MAX))

        for y in range(y0 + step // 2, y1, step):
            for x in range(x0 + step // 2, x1, step):
                py = max(y0, min(y1 - 1, y + int(amp * math.sin(freq * x))))
                self.user32.SetCursorPos(x, py)
                if probe_delay:
                    time.sleep(probe_delay)
                try:
                    el = self._uia.element_from_point(x, py)
                except OSError:
                    continue
                if not el:
                    continue
                try:
                    ct = self._uia.get_int(el, _UIA.UIA_CONTROL_TYPE)
                    role = UIA_CONTROL_TYPE_MAP.get(ct, "")
                    if not role:
                        continue
                    name = self._uia.get_str(el, _UIA.UIA_NAME)
                    value = self._uia.get_legacy_value(el)
                    if not value:
                        value = self._uia.get_text_content(el, read_text_max)
                    rx, ry, rw, rh = self._uia.get_rect(el)
                    if rw <= 0 or rh <= 0:
                        continue
                    key = (role, name, rx, ry, rw, rh)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    if not name and not value:
                        continue
                    el_hwnd = self._uia.get_int(el, _UIA.UIA_NATIVE_WINDOW_HANDLE) or hwnd
                    root_hwnd = self._root_hwnd(el_hwnd)
                    nodes.append({
                        "role": role, "name": name, "value": _obs_clip(value, "node_value_max_chars", 1000),
                        "x": rx, "y": ry, "w": rw, "h": rh,
                        "hwnd": el_hwnd,
                        "root_hwnd": root_hwnd,
                        "enabled": self._uia.get_bool(el, _UIA.UIA_IS_ENABLED),
                        "offscreen": self._uia.get_bool(el, _UIA.UIA_IS_OFFSCREEN),
                    })
                except OSError:
                    continue
                finally:
                    self._uia._release(el)
        return nodes

    def _classify(self, nodes: list[dict[str, Any]], z_index: dict[int, int] | None = None) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for n in nodes:
            if n.get("offscreen") or n["w"] <= 0 or n["h"] <= 0:
                continue
            role = n["role"]
            enabled = n.get("enabled", True)
            if enabled and role in WRITABLE_ROLES:
                action = "write"
            elif enabled and role in CLICKABLE_ROLES:
                action = "click"
            elif role in ACTIONABLE_ROLES:
                action = "read"
            else:
                continue
            n["action"] = action
            result.append(n)
        z_index = z_index or {}
        result.sort(key=lambda n: (z_index.get(int(n.get("root_hwnd") or n.get("hwnd") or 0), 9999), n["y"], n["x"]))
        return result

    def _render(
        self,
        nodes: list[dict[str, Any]],
        focused_title: str,
        focused_hwnd: int = 0,
        overlay_hwnds: set[int] | None = None,
    ) -> tuple[dict[str, Element], str]:
        elements: dict[str, Element] = {}
        overlay_hwnds = overlay_hwnds or set()
        lines: list[str] = [
            f"FOCUSED: {focused_title}",
            "SCOPE: [ID] targets are actionable in the focused window or top overlay; DESKTOP_TREE/WINDOWS are awareness only.",
        ]
        seq = 0
        rendered = 0
        for n in nodes:
            role, name, value = n["role"], n.get("name", ""), n.get("value", "")
            rendered += 1
            preview = _obs_clip(value, "render_value_max_chars", 80)
            root_hwnd = int(n.get("root_hwnd") or n.get("hwnd", 0) or 0)
            owns_scope = (
                not focused_hwnd
                or n.get("hwnd", 0) == focused_hwnd
                or root_hwnd == focused_hwnd
                or n.get("hwnd", 0) in overlay_hwnds
                or root_hwnd in overlay_hwnds
            )
            if n["action"] != "read" and owns_scope:
                seq += 1
                eid = str(seq)
                if value and n["action"] == "write":
                    desc = f'[{eid}] {role} "{name}" = "{preview}"' if name else f'[{eid}] {role} "{preview}"'
                elif name:
                    desc = f'[{eid}] {role} "{name}"'
                else:
                    desc = f'[{eid}] {role}'
                elements[eid] = Element(
                    id=eid, role=role, name=name, value=value,
                    hwnd=root_hwnd or n["hwnd"], px=n["x"], py=n["y"], pw=n["w"], ph=n["h"],
                    action=n["action"], wnd=focused_title,
                    enabled=n.get("enabled", True), readonly=False,
                )
            else:
                if name and value:
                    desc = f'{role} "{name}" = "{preview}"'
                elif name:
                    desc = f'{role} "{name}"'
                else:
                    desc = f'{role} "{preview}"'
            lines.append(f"  {desc}")
        lines.insert(1, f"ELEMENTS: {seq}")
        lines.insert(2, f"OBSERVED: {rendered}")
        return elements, "\n".join(lines)


def observe() -> Observation:
    """Module-level observe - hover probe primary plus bounded desktop tree."""
    return Desktop().observe()
