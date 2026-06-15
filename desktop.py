from __future__ import annotations


import ctypes
import ctypes.wintypes as W
import uuid
from collections.abc import Generator
from contextlib import contextmanager

from config import PROCESS_DPI_AWARENESS_CONTEXT, READ_TEXT_MAX_LENGTH

# --- GUI/UIA constants (moved from config.py) ---
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

GUID_DATA1_END: int = 4
GUID_DATA2_END: int = 6
GUID_DATA3_END: int = 8
GUID_DATA4_START: int = 8
GUID_DATA4_END: int = 16
GUID_DATA4_LENGTH: int = 8
RECT_COORDINATE_COUNT: int = 4
INPUT_UNION_PAD_SIZE: int = 32
CLSCTX_INPROC_SERVER: int = 1
IUNKNOWN_RELEASE_INDEX: int = 2
VT_I4: int = 3
VT_BSTR: int = 8
VT_BOOL: int = 11
VT_R8_ARRAY: int = 8197
VARIANT_TRUE_MASK: int = 0xFFFF
DWORD_MASK: int = 0xFFFFFFFF
UIA_BOUNDING_RECTANGLE: int = 30001
UIA_CONTROL_TYPE: int = 30003
UIA_NAME: int = 30005
UIA_IS_ENABLED: int = 30010
UIA_IS_OFFSCREEN: int = 30022
UIA_NATIVE_WINDOW_HANDLE: int = 30020
UIA_LEGACY_IACCESSIBLE_PATTERN: int = 10018
UIA_TEXT_PATTERN: int = 10014
UIA_GET_ROOT_ELEMENT_INDEX: int = 5
UIA_FIND_ALL_INDEX: int = 6
UIA_ELEMENT_FROM_POINT_INDEX: int = 7
UIA_GET_CURRENT_PROPERTY_VALUE_INDEX: int = 10
UIA_GET_CURRENT_PATTERN_AS_INDEX: int = 14
UIA_CREATE_TRUE_CONDITION_INDEX: int = 21
UIA_ELEMENT_ARRAY_LENGTH_INDEX: int = 3
UIA_ELEMENT_ARRAY_GET_INDEX: int = 4
UIA_GET_RUNTIME_ID_INDEX: int = 4
TREE_SCOPE_CHILDREN: int = 0x2
LEGACY_GET_CURRENT_VALUE_INDEX: int = 8
LEGACY_GET_CURRENT_STATE_INDEX: int = 11
TEXT_PATTERN_DOCUMENT_RANGE_INDEX: int = 7
TEXT_RANGE_GET_TEXT_INDEX: int = 12
WIN_CLASS_NAME_BUFFER: int = 256
WIN_WINDOW_TEXT_BUFFER: int = 512
POINT_PACK_SHIFT_BITS: int = 32

VIRTUAL_KEY_MAP: dict[str, int] = {
    "enter": 0x0D, "return": 0x0D, "tab": 0x09, "escape": 0x1B, "esc": 0x1B,
    "backspace": 0x08, "delete": 0x2E, "del": 0x2E, "insert": 0x2D,
    "home": 0x24, "end": 0x23,
    "pageup": 0x21, "page_up": 0x21, "pagedown": 0x22, "page_down": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "ctrl": 0x11, "control": 0x11, "alt": 0x12, "shift": 0x10,
    "win": 0x5B, "windows": 0x5B, "space": 0x20,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74,
    "f6": 0x75, "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79,
    "f11": 0x7A, "f12": 0x7B,
    "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD,
    "\\": 0xDC, ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF,
} | {chr(ord("a") + i): ord("A") + i for i in range(26)} | {chr(ord("0") + i): ord("0") + i for i in range(10)}
EXTENDED_VK_CODES: frozenset[int] = frozenset({0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E})

__all__ = [
    "user32",
    "UIA_CONTROL_TYPE", "UIA_NAME", "UIA_IS_ENABLED", "UIA_IS_OFFSCREEN",
    "CONTROL_TYPE_MAP", "VK_MAP", "EXTENDED_VKS", "INPUT",
    "init", "set_dpi_aware", "get_str", "get_int", "get_bool", "get_rect",
    "get_legacy_value", "get_legacy_readonly", "get_text_content", "element_from_point",
    "get_children", "get_hwnd", "get_runtime_id", "get_root",
    "get_window_class", "get_window_title",
]

ole32: ctypes.OleDLL = ctypes.OleDLL("ole32")
oleaut32: ctypes.WinDLL = ctypes.WinDLL("oleaut32")
oleaut32.SysFreeString.argtypes = [ctypes.c_void_p]
oleaut32.SysFreeString.restype = None
oleaut32.SafeArrayDestroy.argtypes = [ctypes.c_void_p]
oleaut32.SafeArrayDestroy.restype = ctypes.HRESULT
user32: ctypes.WinDLL = ctypes.WinDLL("user32", use_last_error=True)

user32.GetClassNameW.argtypes = [W.HWND, W.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.IsWindowVisible.argtypes = [W.HWND]
user32.IsWindowVisible.restype = W.BOOL
user32.GetWindow.argtypes = [W.HWND, W.UINT]
user32.GetWindow.restype = W.HWND
user32.GetWindowRect.argtypes = [W.HWND, ctypes.POINTER(W.RECT)]
user32.GetWindowRect.restype = W.BOOL
kernel32: ctypes.WinDLL = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
kernel32.OpenProcess.restype = W.HANDLE
kernel32.TerminateProcess.argtypes = [W.HANDLE, W.UINT]
kernel32.TerminateProcess.restype = W.BOOL
kernel32.CloseHandle.argtypes = [W.HANDLE]
kernel32.CloseHandle.restype = W.BOOL

CONTROL_TYPE_MAP: dict[int, str] = UIA_CONTROL_TYPE_MAP


class GUID(ctypes.Structure):
    _fields_ = [("Data1", W.DWORD), ("Data2", W.WORD), ("Data3", W.WORD), ("Data4", W.BYTE * GUID_DATA4_LENGTH)]


class VARIANT(ctypes.Structure):
    _fields_ = [("vt", W.WORD), ("r1", W.WORD), ("r2", W.WORD), ("r3", W.WORD), ("val", ctypes.c_ulonglong)]


class SAFEARRAY_BOUND(ctypes.Structure):
    _fields_ = [("cElements", W.DWORD), ("lLbound", W.LONG)]


class SAFEARRAY(ctypes.Structure):
    _fields_ = [("cDims", W.USHORT), ("fFeatures", W.USHORT), ("cbElements", W.DWORD),
                ("cLocks", W.DWORD), ("pvData", ctypes.c_void_p), ("rgsabound", SAFEARRAY_BOUND * 1)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", W.WORD), ("wScan", W.WORD), ("dwFlags", W.DWORD),
                ("time", W.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("_pad", ctypes.c_ubyte * INPUT_UNION_PAD_SIZE)]
    _fields_ = [("type", W.DWORD), ("u", _U)]


def make_guid(s: str) -> GUID:
    b: bytes = uuid.UUID(s).bytes
    return GUID(int.from_bytes(b[0:GUID_DATA1_END], "big"), int.from_bytes(b[GUID_DATA1_END:GUID_DATA2_END], "big"),
                int.from_bytes(b[GUID_DATA2_END:GUID_DATA3_END], "big"), (ctypes.c_ubyte * GUID_DATA4_LENGTH)(*b[GUID_DATA4_START:GUID_DATA4_END]))


CLSID_CUIAutomation = make_guid("ff48dba4-60ef-4201-aa87-54103eef594e")
IID_IUIAutomation = make_guid("30cbe57d-d9d0-452a-ab13-7ac5ac4825ee")
IID_LegacyIAccessible = make_guid("828055ad-355b-4435-86d5-3b51c14a9b1b")
IID_TextPattern = make_guid("32eba289-3583-42c9-9c59-3b6d9a1e9b6a")

_uia: ctypes.c_void_p = ctypes.c_void_p()
_true_cond: ctypes.c_void_p = ctypes.c_void_p()


def vt(this: ctypes.c_void_p, idx: int, proto_args: tuple[type, ...], *args: object) -> int:
    vtable = ctypes.cast(this, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    proto = ctypes.WINFUNCTYPE(ctypes.HRESULT, *proto_args)
    return proto(vtable[idx])(this, *args)


def release(ptr: ctypes.c_void_p) -> None:
    ptr_value = ptr.value
    if ptr_value is None:
        return
    vt_ptr = ctypes.c_void_p(ptr_value)
    vtable = ctypes.cast(vt_ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    proto = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
    proto(vtable[IUNKNOWN_RELEASE_INDEX])(vt_ptr)


def init() -> None:
    global _uia, _true_cond
    if _uia.value:
        return
    ole32.CoInitialize(None)
    ole32.CoCreateInstance(
        ctypes.byref(CLSID_CUIAutomation), None, CLSCTX_INPROC_SERVER,
        ctypes.byref(IID_IUIAutomation), ctypes.byref(_uia))
    vt(_uia, UIA_CREATE_TRUE_CONDITION_INDEX, (ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)), ctypes.byref(_true_cond))


def set_dpi_aware() -> None:
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(PROCESS_DPI_AWARENESS_CONTEXT))


def _get_property(el: ctypes.c_void_p, prop_id: int) -> VARIANT:
    var = VARIANT()
    vt(el, UIA_GET_CURRENT_PROPERTY_VALUE_INDEX, (ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(VARIANT)),
       ctypes.c_int(prop_id), ctypes.byref(var))
    return var


def get_str(el: ctypes.c_void_p, prop_id: int) -> str:
    var = _get_property(el, prop_id)
    if var.vt == VT_BSTR:
        ptr = ctypes.c_void_p(var.val)
        s = ctypes.cast(ptr, ctypes.c_wchar_p).value or ""
        oleaut32.SysFreeString(ptr)
        return s
    return ""


def get_int(el: ctypes.c_void_p, prop_id: int) -> int:
    var = _get_property(el, prop_id)
    return int(var.val & DWORD_MASK) if var.vt == VT_I4 else 0


def get_bool(el: ctypes.c_void_p, prop_id: int) -> bool:
    var = _get_property(el, prop_id)
    return (var.val & VARIANT_TRUE_MASK) == VARIANT_TRUE_MASK if var.vt == VT_BOOL else False


def get_rect(el: ctypes.c_void_p) -> tuple[int, int, int, int]:
    var = _get_property(el, UIA_BOUNDING_RECTANGLE)
    if var.vt == VT_R8_ARRAY:
        sa_ptr = ctypes.c_void_p(var.val)
        sa = ctypes.cast(sa_ptr, ctypes.POINTER(SAFEARRAY)).contents
        d = (ctypes.c_double * RECT_COORDINATE_COUNT).from_address(sa.pvData)
        rx, ry, rw, rh = (int(d[i]) for i in range(RECT_COORDINATE_COUNT))
        result = (rx, ry, rw, rh)
        oleaut32.SafeArrayDestroy(sa_ptr)
        return result
    return (0, 0, 0, 0)


def _get_legacy_pattern(el: ctypes.c_void_p) -> ctypes.c_void_p | None:
    pattern = ctypes.c_void_p()
    hr = vt(el, UIA_GET_CURRENT_PATTERN_AS_INDEX,
            (ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)),
            ctypes.c_int(UIA_LEGACY_IACCESSIBLE_PATTERN), ctypes.byref(IID_LegacyIAccessible), ctypes.byref(pattern))
    return pattern if hr == 0 and pattern.value else None


@contextmanager
def _legacy_pattern(el: ctypes.c_void_p) -> Generator[ctypes.c_void_p | None, None, None]:
    pattern = _get_legacy_pattern(el)
    try:
        yield pattern
    finally:
        if pattern is not None:
            release(pattern)


def get_legacy_value(el: ctypes.c_void_p) -> str:
    with _legacy_pattern(el) as pattern:
        if pattern is None:
            return ""
        bstr = ctypes.c_wchar_p()
        hr = vt(pattern, LEGACY_GET_CURRENT_VALUE_INDEX, (ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)), ctypes.byref(bstr))
        return bstr.value or "" if hr == 0 else ""


def get_legacy_readonly(el: ctypes.c_void_p) -> bool:
    with _legacy_pattern(el) as pattern:
        if pattern is None:
            return False
        var = VARIANT()
        hr = vt(pattern, LEGACY_GET_CURRENT_STATE_INDEX, (ctypes.c_void_p, ctypes.POINTER(VARIANT)), ctypes.byref(var))
        return (var.val & VARIANT_TRUE_MASK) == VARIANT_TRUE_MASK if hr == 0 and var.vt == VT_BOOL else False


def get_text_content(el: ctypes.c_void_p, max_len: int = READ_TEXT_MAX_LENGTH) -> str:
    pattern = ctypes.c_void_p()
    hr = vt(el, UIA_GET_CURRENT_PATTERN_AS_INDEX,
            (ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)),
            ctypes.c_int(UIA_TEXT_PATTERN), ctypes.byref(IID_TextPattern), ctypes.byref(pattern))
    if hr != 0 or not pattern.value:
        return ""
    doc_range = ctypes.c_void_p()
    hr2 = vt(pattern, TEXT_PATTERN_DOCUMENT_RANGE_INDEX, (ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)), ctypes.byref(doc_range))
    if hr2 != 0 or not doc_range.value:
        release(pattern)
        return ""
    bstr = ctypes.c_wchar_p()
    hr3 = vt(doc_range, TEXT_RANGE_GET_TEXT_INDEX, (ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_wchar_p)),
             ctypes.c_int(max_len), ctypes.byref(bstr))
    text = bstr.value or "" if hr3 == 0 else ""
    release(doc_range)
    release(pattern)
    return text


def element_from_point(px: int, py: int) -> ctypes.c_void_p | None:
    point_packed = ctypes.c_int64(px | (py << POINT_PACK_SHIFT_BITS))
    found = ctypes.c_void_p()
    hr = vt(_uia, UIA_ELEMENT_FROM_POINT_INDEX,
            (ctypes.c_void_p, ctypes.c_int64, ctypes.POINTER(ctypes.c_void_p)),
            point_packed, ctypes.byref(found))
    return found if hr == 0 and found.value else None


def get_children(el: ctypes.c_void_p) -> list[ctypes.c_void_p]:
    arr = ctypes.c_void_p()
    hr = vt(el, UIA_FIND_ALL_INDEX,
            (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)),
            ctypes.c_int(TREE_SCOPE_CHILDREN), _true_cond, ctypes.byref(arr))
    if hr != 0 or not arr.value:
        return []
    length = ctypes.c_int()
    vt(arr, UIA_ELEMENT_ARRAY_LENGTH_INDEX, (ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)), ctypes.byref(length))
    children: list[ctypes.c_void_p] = []
    for i in range(length.value):
        child = ctypes.c_void_p()
        vt(arr, UIA_ELEMENT_ARRAY_GET_INDEX, (ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)),
           ctypes.c_int(i), ctypes.byref(child))
        if child.value:
            children.append(child)
    release(arr)
    return children


def get_hwnd(el: ctypes.c_void_p) -> int:
    var = _get_property(el, UIA_NATIVE_WINDOW_HANDLE)
    return int(var.val & DWORD_MASK) if var.vt == VT_I4 else 0


def get_runtime_id(el: ctypes.c_void_p) -> tuple[int, ...] | None:
    sa_ptr = ctypes.c_void_p()
    hr = vt(el, UIA_GET_RUNTIME_ID_INDEX, (ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)),
            ctypes.byref(sa_ptr))
    if hr != 0 or not sa_ptr.value:
        return None
    sa = ctypes.cast(sa_ptr, ctypes.POINTER(SAFEARRAY)).contents
    count = sa.rgsabound[0].cElements
    if count == 0:
        oleaut32.SafeArrayDestroy(sa_ptr)
        return None
    data = (ctypes.c_int * count).from_address(sa.pvData)
    result = tuple(data[i] for i in range(count))
    oleaut32.SafeArrayDestroy(sa_ptr)
    return result



def get_root() -> ctypes.c_void_p:
    root = ctypes.c_void_p()
    vt(_uia, UIA_GET_ROOT_ELEMENT_INDEX, (ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)), ctypes.byref(root))
    return root


def get_window_class(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(WIN_CLASS_NAME_BUFFER)
    user32.GetClassNameW(W.HWND(hwnd), buf, WIN_CLASS_NAME_BUFFER)
    return buf.value


def get_window_title(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(WIN_WINDOW_TEXT_BUFFER)
    user32.GetWindowTextW(W.HWND(hwnd), buf, WIN_WINDOW_TEXT_BUFFER)
    return buf.value



VK_MAP: dict[str, int] = VIRTUAL_KEY_MAP
EXTENDED_VKS: frozenset[int] = EXTENDED_VK_CODES


# --- Observer (merged from observer.py) ---

__all__ = ["observe", "ObserveResult", "BookEntry"]

ACTIONABLE_ROLES = frozenset({
    "Button", "Edit", "ComboBox", "ListItem", "Hyperlink", "MenuItem",
    "TabItem", "SplitButton", "CheckBox", "RadioButton", "Slider",
    "Document", "Text", "ScrollBar", "TreeItem", "DataItem", "Custom",
})
CLICKABLE_ROLES = frozenset({
    "Button", "MenuItem", "ListItem", "Hyperlink", "TabItem", "TreeItem",
    "SplitButton", "CheckBox", "RadioButton", "Slider", "ScrollBar",
    "DataItem", "Document",
})
WRITABLE_ROLES = frozenset({"Edit", "ComboBox"})
SKIP_NAMELESS = frozenset({
    "Pane", "Group", "Custom", "Image", "Separator", "Thumb",
    "ProgressBar", "Header", "HeaderItem",
})

@dataclass(slots=True)
class BookEntry:
    id: str
    role: str
    name: str
    value: str
    hwnd: int
    wnd: str
    px: int
    py: int
    pw: int
    ph: int
    enabled: bool
    readonly: bool
    action: str

@dataclass(slots=True)
class ObserveResult:
    context_text: str
    book: dict[str, BookEntry]
    focused_title: str
    windows: list[dict[str, Any]]
    desktop_summary: str

def observe() -> ObserveResult:
    set_dpi_aware()
    init()
    screen_w = user32.GetSystemMetrics(0)
    screen_h = user32.GetSystemMetrics(1)
    focused_hwnd = int(user32.GetForegroundWindow())
    focused_title = get_window_title(focused_hwnd)

    windows = _enumerate_windows()
    z_order = _get_z_order()
    regions = _probe_regions(windows, focused_title, focused_hwnd, screen_w, screen_h)

    probe_nodes: list[dict[str, Any]] = []
    saved = W.POINT()
    user32.GetCursorPos(ctypes.byref(saved))
    for x0, y0, x1, y1, wname, whwnd in regions:
        if whwnd:
            user32.SetForegroundWindow(W.HWND(whwnd))
            time.sleep(config.PROBE_FOREGROUND_DELAY)
        _probe_region(probe_nodes, config.PROBE_STEP_PX, x0, y0, x1, y1, wname, whwnd)
    user32.SetCursorPos(saved.x, saved.y)

    tree_nodes: list[dict[str, Any]] = []
    for wnd in _tree_targets(windows, focused_title):
        _tree_walk(tree_nodes, wnd["element"], str(wnd["name"]), int(wnd["hwnd"]), config.TREE_WALK_TIMEOUT)

    merged = _merge(probe_nodes, tree_nodes)
    z_titles = [str(e["title"]) for e in z_order]
    wnd_rank = {t: i for i, t in enumerate(z_titles)}
    classified = _classify(merged)
    classified.sort(key=lambda n: (wnd_rank.get(n["wnd"], 999), n["depth"], n["y"], n["x"]))

    text, book = _render(classified, focused_title)

    desktop_lines = [f"Desktop ({screen_w}x{screen_h})"]
    for i, entry in enumerate(z_order[:10]):
        is_last = i == min(len(z_order), 10) - 1
        connector = "â””â”€â”€ " if is_last else "â”œâ”€â”€ "
        marker = " (focused)" if entry["title"] == focused_title else ""
        desktop_lines.append(f"{connector}{entry['title']}{marker}")

    return ObserveResult(
        context_text=text, book=book, focused_title=focused_title,
        windows=[{"name": w["name"], "hwnd": w["hwnd"]} for w in windows],
        desktop_summary="\n".join(desktop_lines),
    )

def _enumerate_windows() -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    for top_el in get_children(get_root()):
        try:
            x, y, w, h = get_rect(top_el)
            ct = get_int(top_el, UIA_CONTROL_TYPE)
            role = CONTROL_TYPE_MAP.get(ct, "")
            if w <= 0 or h <= 0 or role not in ("Window", "Pane"):
                continue
            name = get_str(top_el, UIA_NAME)
            el_hwnd = get_hwnd(top_el)
            windows.append({"element": top_el, "role": role, "name": name,
                            "hwnd": el_hwnd, "x": x, "y": y, "w": w, "h": h,
                            "class": get_window_class(el_hwnd)})
        except OSError:
            continue
    return windows

def _get_z_order() -> list[dict[str, Any]]:
    hwnd = user32.GetTopWindow(None)
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    z = 0
    while hwnd:
        if user32.IsWindowVisible(hwnd):
            title = get_window_title(int(hwnd))
            if title and title not in seen:
                result.append({"z": z, "hwnd": int(hwnd), "title": title})
                seen.add(title)
                z += 1
        hwnd = user32.GetWindow(hwnd, 2)
    return result

def _probe_regions(
    windows: list[dict[str, Any]], focused_title: str, focused_hwnd: int, sw: int, sh: int,
) -> list[tuple[int, int, int, int, str, int]]:
    for wnd in windows:
        if str(wnd["name"]) == focused_title or int(wnd["hwnd"]) == focused_hwnd:
            x, y, ww, wh = int(wnd["x"]), int(wnd["y"]), int(wnd["w"]), int(wnd["h"])
            return [(x, y, x + ww, y + wh, str(wnd["name"]), int(wnd["hwnd"]))]
    return [(0, 0, sw, sh, focused_title or "Desktop", focused_hwnd)]

def _tree_targets(windows: list[dict[str, Any]], focused_title: str) -> list[dict[str, Any]]:
    if focused_title:
        matched = [w for w in windows if str(w["name"]) == focused_title]
        if matched:
            return matched
    return windows

def _probe_region(
    out: list[dict[str, Any]], step: int,
    x0: int, y0: int, x1: int, y1: int, wname: str, whwnd: int,
) -> None:
    seen_rids: set[Any] = set()
    amp = step * config.PROBE_SINE_AMPLITUDE_RATIO
    freq = 2 * math.pi / (step * config.PROBE_SINE_PERIOD_STEPS)
    for y in range(y0 + step // 2, y1, step):
        for x in range(x0 + step // 2, x1, step):
            py = max(y0, min(y1 - 1, y + int(amp * math.sin(freq * x))))
            user32.SetCursorPos(x, py)
            time.sleep(config.PROBE_SAMPLE_DELAY)
            try:
                el = element_from_point(x, py)
            except OSError:
                continue
            if not el:
                continue
            try:
                rid = get_runtime_id(el)
                if rid and rid in seen_rids:
                    continue
                if rid:
                    seen_rids.add(rid)
                ct = get_int(el, UIA_CONTROL_TYPE)
                role = CONTROL_TYPE_MAP.get(ct, "")
                if not role:
                    continue
                name = get_str(el, UIA_NAME)
                value = get_legacy_value(el)
                has_text_pattern = False
                if not value:
                    text_content = get_text_content(el, config.READ_TEXT_MAX_LENGTH)
                    if text_content:
                        value = _filter_terminal_text(text_content)
                        has_text_pattern = True
                rx, ry, rw, rh = get_rect(el)
                if not name and not value:
                    continue
                out.append({
                    "wnd": wname, "hwnd": whwnd, "depth": 0,
                    "role": role, "name": name,
                    "x": rx, "y": ry, "w": rw, "h": rh,
                    "enabled": get_bool(el, UIA_IS_ENABLED),
                    "value": value,
                    "readonly": get_legacy_readonly(el),
                    "offscreen": get_bool(el, UIA_IS_OFFSCREEN),
                    "has_text_pattern": has_text_pattern,
                })
            except OSError:
                continue

def _tree_walk(out: list[dict[str, Any]], el: Any, wnd_name: str, wnd_hwnd: int, timeout: float) -> None:
    from collections import deque
    start = time.perf_counter()
    queue: deque[tuple[Any, int]] = deque()
    for child in get_children(el):
        queue.append((child, 1))
    while queue:
        if time.perf_counter() - start > timeout:
            break
        raw_el, depth = queue.popleft()
        try:
            x, y, w, h = get_rect(raw_el)
            ct = get_int(raw_el, UIA_CONTROL_TYPE)
        except OSError:
            continue
        role = CONTROL_TYPE_MAP.get(ct, "")
        if not role:
            try:
                for c in get_children(raw_el):
                    queue.append((c, depth))
            except OSError:
                pass
            continue
        try:
            value = get_legacy_value(raw_el) if role in ACTIONABLE_ROLES else ""
            has_text_pattern = False
            if not value and role in ("Text", "Document", "Edit", "Pane"):
                tc = get_text_content(raw_el, config.READ_TEXT_MAX_LENGTH)
                if tc:
                    value = _filter_terminal_text(tc)
                    has_text_pattern = True
            out.append({
                "wnd": wnd_name, "hwnd": wnd_hwnd, "depth": depth,
                "role": role, "name": get_str(raw_el, UIA_NAME),
                "x": x, "y": y, "w": w, "h": h,
                "enabled": get_bool(raw_el, UIA_IS_ENABLED),
                "value": value,
                "readonly": get_legacy_readonly(raw_el) if role in ACTIONABLE_ROLES else False,
                "offscreen": get_bool(raw_el, UIA_IS_OFFSCREEN),
                "has_text_pattern": has_text_pattern,
            })
        except OSError:
            continue
        try:
            for c in get_children(raw_el):
                queue.append((c, depth + 1))
        except OSError:
            pass

def _node_key(n: dict[str, Any]) -> tuple[Any, ...]:
    return (n["role"], n.get("name", ""), n["x"], n["y"], n["w"], n["h"])

def _merge(probe_nodes: list[dict[str, Any]], tree_nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Probe is primary â€” hover discoveries land first; tree adds depth and gaps."""
    index: dict[tuple[Any, ...], int] = {}
    merged: list[dict[str, Any]] = []
    for node in probe_nodes:
        key = _node_key(node)
        index[key] = len(merged)
        merged.append(node)
    for node in tree_nodes:
        key = _node_key(node)
        if key in index:
            hit = merged[index[key]]
            hit["depth"] = max(int(hit.get("depth", 0)), int(node.get("depth", 0)))
            hit["has_text_pattern"] = hit.get("has_text_pattern") or node.get("has_text_pattern")
        else:
            merged.append(node)
    return merged

def _filter_terminal_text(raw: str) -> str:
    lines = raw.splitlines()
    stripped = [l.rstrip() for l in lines if l.rstrip()]
    if not stripped:
        return ""
    kept = [l for l in stripped if not _is_runtime_log_line(l) and not _is_tui_dashboard_line(l)]
    if not kept:
        kept = stripped
    last_sep = -1
    for i in range(len(kept) - 1, -1, -1):
        if " - Completed in " in kept[i]:
            last_sep = i
            break
    tail = kept[last_sep + 1:] if last_sep >= 0 and last_sep < len(kept) - 1 else kept
    limit = int(config.TERMINAL_CONTEXT_TAIL_LINES)
    if limit > 0 and len(tail) > limit:
        tail = tail[-limit:]
    return "\n".join(tail)

def _is_runtime_log_line(line: str) -> bool:
    compact = line.strip()
    return compact.startswith("{") and '"phase":' in compact

def _is_tui_dashboard_line(line: str) -> bool:
    compact = line.strip()
    return bool(compact) and ("\x1bP" in compact or compact.startswith("endgame-ai |"))

def _classify(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tab_rects: list[tuple[int, int, int, int]] = []
    for n in nodes:
        if n["role"] == "TabItem":
            tab_rects.append((n["x"], n["y"], n["x"] + n["w"], n["y"] + n["h"]))

    result: list[dict[str, Any]] = []
    for n in nodes:
        role = n["role"]
        w, h = n["w"], n["h"]
        if w <= 0 or h <= 0 or n.get("offscreen"):
            continue
        name = n.get("name", "")
        value = n.get("value", "")
        enabled = n.get("enabled", True)
        readonly = n.get("readonly", False)
        if role in SKIP_NAMELESS and not name and not value:
            continue
        inside_tab = False
        if role != "TabItem":
            nx, ny = n["x"], n["y"]
            for tx, ty, tx2, ty2 in tab_rects:
                if tx <= nx and ny >= ty and nx + w <= tx2 and ny + h <= ty2:
                    inside_tab = True
                    break
        if enabled and role in WRITABLE_ROLES and not readonly and not inside_tab:
            action = "write"
        elif enabled and n.get("has_text_pattern") and not inside_tab:
            action = "write"
        elif enabled and role in CLICKABLE_ROLES:
            action = "click"
        else:
            action = "none"
        if action == "none" and not name and not value:
            continue
        n["action"] = action
        result.append(n)
    return result

def _clip_value(value: str) -> str:
    limit = int(config.SCREEN_ELEMENT_VALUE_LIMIT)
    if limit <= 0:
        return value
    return value if len(value) <= limit else value[:limit] + "â€¦"

def _render(nodes: list[dict[str, Any]], focused_title: str) -> tuple[str, dict[str, BookEntry]]:
    book: dict[str, BookEntry] = {}
    wnd_groups: dict[str, list[dict[str, Any]]] = {}
    for n in nodes:
        wnd_groups.setdefault(n["wnd"], []).append(n)

    lines: list[str] = []
    seq = 0
    wnd_list = sorted(wnd_groups.keys(), key=lambda w: (w != focused_title, w))
    for i, wnd in enumerate(wnd_list):
        is_last_wnd = i == len(wnd_list) - 1
        branch = "    " if is_last_wnd else "â”‚   "
        focused = " (focused)" if wnd == focused_title else ""
        lines.append(f"{'â””â”€â”€ ' if is_last_wnd else 'â”œâ”€â”€ '}{wnd}{focused}")
        for n in wnd_groups[wnd]:
            depth = max(1, int(n.get("depth", 1)))
            indent = branch + ("â”‚   " * (depth - 1))
            label = str(n.get("name", ""))
            role = str(n.get("role", ""))
            if n.get("action") != "none":
                seq += 1
                nid = str(seq)
                if n.get("value") and n["action"] == "write":
                    val = _clip_value(str(n["value"]))
                    desc = f'[{nid}] {role} "{label}" = "{val}"' if label else f'[{nid}] {role} "{val}"'
                elif label:
                    desc = f'[{nid}] {role} "{label}"'
                else:
                    desc = f'[{nid}] {role}'
                if not n.get("enabled"):
                    desc += " (disabled)"
                book[nid] = BookEntry(
                    id=nid, role=role, name=label,
                    value=str(n.get("value", "")), hwnd=n["hwnd"], wnd=wnd,
                    px=n["x"], py=n["y"], pw=n["w"], ph=n["h"],
                    enabled=n.get("enabled", True), readonly=n.get("readonly", False),
                    action=n["action"],
                )
            else:
                val = _clip_value(str(n.get("value", ""))) if n.get("value") else ""
                if label and val:
                    desc = f'{role} "{label}" = "{val}"'
                elif label:
                    desc = f'{role} "{label}"'
                elif val:
                    desc = f'{role} "{val}"'
                else:
                    desc = role
            lines.append(f"{indent}â”œâ”€â”€ {desc}")
    return "\n".join(lines), book
