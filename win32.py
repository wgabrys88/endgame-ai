from __future__ import annotations


import ctypes
import ctypes.wintypes as W
import uuid
from collections.abc import Generator
from contextlib import contextmanager

from config import (
    GUID_DATA1_END, GUID_DATA2_END, GUID_DATA3_END, GUID_DATA4_START,
    GUID_DATA4_END, GUID_DATA4_LENGTH, RECT_COORDINATE_COUNT, INPUT_UNION_PAD_SIZE,
    CLSCTX_INPROC_SERVER, IUNKNOWN_RELEASE_INDEX, VT_I4, VT_BSTR, VT_BOOL,
    VT_R8_ARRAY, VARIANT_TRUE_MASK, DWORD_MASK, UIA_BOUNDING_RECTANGLE,
    UIA_CONTROL_TYPE, UIA_NAME, UIA_IS_ENABLED, UIA_IS_OFFSCREEN,
    UIA_NATIVE_WINDOW_HANDLE, UIA_LEGACY_IACCESSIBLE_PATTERN, UIA_TEXT_PATTERN,
    UIA_GET_ROOT_ELEMENT_INDEX, UIA_FIND_ALL_INDEX, UIA_ELEMENT_FROM_POINT_INDEX,
    UIA_GET_CURRENT_PROPERTY_VALUE_INDEX, UIA_GET_CURRENT_PATTERN_AS_INDEX,
    UIA_CREATE_TRUE_CONDITION_INDEX, UIA_ELEMENT_ARRAY_LENGTH_INDEX, UIA_ELEMENT_ARRAY_GET_INDEX,
    UIA_GET_RUNTIME_ID_INDEX, TREE_SCOPE_CHILDREN, LEGACY_GET_CURRENT_VALUE_INDEX,
    LEGACY_GET_CURRENT_STATE_INDEX, TEXT_PATTERN_DOCUMENT_RANGE_INDEX,
    TEXT_RANGE_GET_TEXT_INDEX, WIN_CLASS_NAME_BUFFER, WIN_WINDOW_TEXT_BUFFER,
    POINT_PACK_SHIFT_BITS, UIA_CONTROL_TYPE_MAP, VIRTUAL_KEY_MAP,
    EXTENDED_VK_CODES, PROCESS_DPI_AWARENESS_CONTEXT, READ_TEXT_MAX_LENGTH,
    
)

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
