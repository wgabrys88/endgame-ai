from __future__ import annotations

import ctypes
import ctypes.wintypes as W
import uuid
from collections.abc import Generator
from contextlib import contextmanager

__all__ = [
    "user32",
    "UIA_CONTROL_TYPE", "UIA_NAME", "UIA_IS_ENABLED", "UIA_IS_OFFSCREEN",
    "CONTROL_TYPE_MAP", "VK_MAP", "EXTENDED_VKS", "INPUT",
    "init", "set_dpi_aware", "get_str", "get_int", "get_bool", "get_rect",
    "get_legacy_value", "get_legacy_readonly", "get_text_content", "element_from_point",
    "get_children", "get_hwnd", "get_runtime_id", "get_root",
    "get_window_class", "get_window_title", "ensure_tree_walker",
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

UIA_BOUNDING_RECTANGLE: int = 30001
UIA_CONTROL_TYPE: int = 30003
UIA_NAME: int = 30005
UIA_IS_ENABLED: int = 30010
UIA_IS_OFFSCREEN: int = 30022
UIA_LEGACY_IACCESSIBLE_PATTERN: int = 10018
UIA_TEXT_PATTERN: int = 10014

CONTROL_TYPE_MAP: dict[int, str] = {
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


class GUID(ctypes.Structure):
    _fields_ = [("Data1", W.DWORD), ("Data2", W.WORD), ("Data3", W.WORD), ("Data4", W.BYTE * 8)]


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
        _fields_ = [("ki", KEYBDINPUT), ("_pad", ctypes.c_ubyte * 32)]
    _fields_ = [("type", W.DWORD), ("u", _U)]


def make_guid(s: str) -> GUID:
    b: bytes = uuid.UUID(s).bytes
    return GUID(int.from_bytes(b[0:4], "big"), int.from_bytes(b[4:6], "big"),
                int.from_bytes(b[6:8], "big"), (ctypes.c_ubyte * 8)(*b[8:16]))


CLSID_CUIAutomation = make_guid("ff48dba4-60ef-4201-aa87-54103eef594e")
IID_IUIAutomation = make_guid("30cbe57d-d9d0-452a-ab13-7ac5ac4825ee")
IID_LegacyIAccessible = make_guid("828055ad-355b-4435-86d5-3b51c14a9b1b")
IID_TextPattern = make_guid("32eba289-3583-42c9-9c59-3b6d9a1e9b6a")

_uia: ctypes.c_void_p = ctypes.c_void_p()
_true_cond: ctypes.c_void_p = ctypes.c_void_p()
_tree_walker: ctypes.c_void_p = ctypes.c_void_p()


def vt(this: ctypes.c_void_p, idx: int, proto_args: tuple[type, ...], *args: object) -> int:
    vtable = ctypes.cast(this, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    proto = ctypes.WINFUNCTYPE(ctypes.HRESULT, *proto_args)
    return proto(vtable[idx])(this, *args)


def release(ptr: ctypes.c_void_p) -> None:
    vt_ptr = ctypes.c_void_p(int(ptr.value) if ptr.value is not None else None)  # type: ignore[arg-type]
    vtable = ctypes.cast(vt_ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    proto = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
    proto(vtable[2])(vt_ptr)


def init() -> None:
    global _uia, _true_cond
    if _uia.value:
        return
    ole32.CoInitialize(None)
    ole32.CoCreateInstance(
        ctypes.byref(CLSID_CUIAutomation), None, 1,
        ctypes.byref(IID_IUIAutomation), ctypes.byref(_uia))
    vt(_uia, 21, (ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)), ctypes.byref(_true_cond))


def set_dpi_aware() -> None:
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))


def ensure_tree_walker() -> None:
    global _tree_walker
    if _tree_walker.value:
        return
    vt(_uia, 14, (ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)),
       ctypes.byref(_tree_walker))


def _get_property(el: ctypes.c_void_p, prop_id: int) -> VARIANT:
    var = VARIANT()
    vt(el, 10, (ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(VARIANT)),
       ctypes.c_int(prop_id), ctypes.byref(var))
    return var


def get_str(el: ctypes.c_void_p, prop_id: int) -> str:
    var = _get_property(el, prop_id)
    if var.vt == 8:
        ptr = ctypes.c_void_p(var.val)
        s = ctypes.cast(ptr, ctypes.c_wchar_p).value or ""
        oleaut32.SysFreeString(ptr)
        return s
    return ""


def get_int(el: ctypes.c_void_p, prop_id: int) -> int:
    var = _get_property(el, prop_id)
    return int(var.val & 0xFFFFFFFF) if var.vt == 3 else 0


def get_bool(el: ctypes.c_void_p, prop_id: int) -> bool:
    var = _get_property(el, prop_id)
    return (var.val & 0xFFFF) == 0xFFFF if var.vt == 11 else False


def get_rect(el: ctypes.c_void_p) -> tuple[int, int, int, int]:
    var = _get_property(el, UIA_BOUNDING_RECTANGLE)
    if var.vt == 8197:
        sa_ptr = ctypes.c_void_p(var.val)
        sa = ctypes.cast(sa_ptr, ctypes.POINTER(SAFEARRAY)).contents
        d = (ctypes.c_double * 4).from_address(sa.pvData)
        result = (int(d[0]), int(d[1]), int(d[2]), int(d[3]))
        oleaut32.SafeArrayDestroy(sa_ptr)
        return result
    return (0, 0, 0, 0)


def _get_legacy_pattern(el: ctypes.c_void_p) -> ctypes.c_void_p | None:
    pattern = ctypes.c_void_p()
    hr = vt(el, 14,
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
        hr = vt(pattern, 8, (ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)), ctypes.byref(bstr))
        return bstr.value or "" if hr == 0 else ""


def get_legacy_readonly(el: ctypes.c_void_p) -> bool:
    with _legacy_pattern(el) as pattern:
        if pattern is None:
            return False
        var = VARIANT()
        hr = vt(pattern, 11, (ctypes.c_void_p, ctypes.POINTER(VARIANT)), ctypes.byref(var))
        return (var.val & 0xFFFF) == 0xFFFF if hr == 0 and var.vt == 11 else False


def get_text_content(el: ctypes.c_void_p, max_len: int = 65536) -> str:
    pattern = ctypes.c_void_p()
    hr = vt(el, 14,
            (ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)),
            ctypes.c_int(UIA_TEXT_PATTERN), ctypes.byref(IID_TextPattern), ctypes.byref(pattern))
    if hr != 0 or not pattern.value:
        return ""
    doc_range = ctypes.c_void_p()
    hr2 = vt(pattern, 7, (ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)), ctypes.byref(doc_range))
    if hr2 != 0 or not doc_range.value:
        release(pattern)
        return ""
    bstr = ctypes.c_wchar_p()
    hr3 = vt(doc_range, 12, (ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_wchar_p)),
             ctypes.c_int(max_len), ctypes.byref(bstr))
    text = bstr.value or "" if hr3 == 0 else ""
    release(doc_range)
    release(pattern)
    return text


def element_from_point(px: int, py: int) -> ctypes.c_void_p | None:
    point_packed = ctypes.c_int64(px | (py << 32))
    found = ctypes.c_void_p()
    hr = vt(_uia, 7,
            (ctypes.c_void_p, ctypes.c_int64, ctypes.POINTER(ctypes.c_void_p)),
            point_packed, ctypes.byref(found))
    return found if hr == 0 and found.value else None


def get_children(el: ctypes.c_void_p) -> list[ctypes.c_void_p]:
    arr = ctypes.c_void_p()
    hr = vt(el, 6,
            (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)),
            ctypes.c_int(0x2), _true_cond, ctypes.byref(arr))
    if hr != 0 or not arr.value:
        return []
    length = ctypes.c_int()
    vt(arr, 3, (ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)), ctypes.byref(length))
    children: list[ctypes.c_void_p] = []
    for i in range(length.value):
        child = ctypes.c_void_p()
        vt(arr, 4, (ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)),
           ctypes.c_int(i), ctypes.byref(child))
        if child.value:
            children.append(child)
    release(arr)
    return children


def get_hwnd(el: ctypes.c_void_p) -> int:
    var = _get_property(el, 30020)
    return int(var.val & 0xFFFFFFFF) if var.vt == 3 else 0


def get_runtime_id(el: ctypes.c_void_p) -> tuple[int, ...] | None:
    sa_ptr = ctypes.c_void_p()
    hr = vt(el, 4, (ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)),
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
    vt(_uia, 5, (ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)), ctypes.byref(root))
    return root


def get_window_class(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(W.HWND(hwnd), buf, 256)
    return buf.value


def get_window_title(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(W.HWND(hwnd), buf, 512)
    return buf.value


VK_MAP: dict[str, int] = {
    "enter": 0x0D, "return": 0x0D, "tab": 0x09, "escape": 0x1B, "esc": 0x1B,
    "backspace": 0x08, "delete": 0x2E, "del": 0x2E, "insert": 0x2D, "ins": 0x2D,
    "home": 0x24, "end": 0x23,
    "pageup": 0x21, "page_up": 0x21, "pgup": 0x21,
    "pagedown": 0x22, "page_down": 0x22, "pgdn": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "ctrl": 0x11, "control": 0x11, "alt": 0x12, "shift": 0x10,
    "win": 0x5B, "windows": 0x5B, "meta": 0x5B, "super": 0x5B, "space": 0x20,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74,
    "f6": 0x75, "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79,
    "f11": 0x7A, "f12": 0x7B,
    "`": 0xC0, "~": 0xC0,
    "-": 0xBD, "_": 0xBD,
    "=": 0xBB, "+": 0xBB,
    "[": 0xDB, "{": 0xDB,
    "]": 0xDD, "}": 0xDD,
    "\\": 0xDC, "|": 0xDC,
    ";": 0xBA, ":": 0xBA,
    "'": 0xDE, '"': 0xDE,
    ",": 0xBC, "<": 0xBC,
    ".": 0xBE, ">": 0xBE,
    "/": 0xBF, "?": 0xBF,
} | {chr(ord("a") + i): ord("A") + i for i in range(26)} | {chr(ord("0") + i): ord("0") + i for i in range(10)}

EXTENDED_VKS: frozenset[int] = frozenset({0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E})