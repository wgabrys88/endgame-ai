# winapi.py — Franz / windows-ai-agent-toolset-v2.5-modular
# Przywołane tutaj i rozszerzone: kursor ZAWSZE rysowany na zrzucie.
from __future__ import annotations

import os
import struct
import time
import zlib
from typing import Tuple

if os.name != "nt":
    raise OSError("Windows required — ten plik to prawdziwy Win32. Na Linuxie użyj coords.py / agent_status.py / stateless_prompt.py")

import ctypes
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

if not hasattr(wintypes, "HCURSOR"):
    wintypes.HCURSOR = wintypes.HANDLE
if not hasattr(wintypes, "HBITMAP"):
    wintypes.HBITMAP = wintypes.HANDLE
if not hasattr(wintypes, "HICON"):
    wintypes.HICON = wintypes.HANDLE

try:
    ULONG_PTR = wintypes.ULONG_PTR
except AttributeError:
    ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
SM_CXSCREEN = 0
SM_CYSCREEN = 1
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
CURSOR_SHOWING = 0x00000001
DI_NORMAL = 0x0003
BI_RGB = 0
DIB_RGB_COLORS = 0
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_WHEEL = 0x0800
HALFTONE = 4
SRCCOPY = 0x00CC0020
IDC_ARROW = 32512


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class CURSORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hCursor", wintypes.HCURSOR),
        ("ptScreenPos", POINT),
    ]


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL),
        ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD),
        ("hbmMask", wintypes.HBITMAP),
        ("hbmColor", wintypes.HBITMAP),
    ]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class INPUT_I(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("ii", INPUT_I)]


_user32_sigs = [
    ("GetSystemMetrics", [wintypes.INT], wintypes.INT),
    ("GetDC", [wintypes.HWND], wintypes.HDC),
    ("ReleaseDC", [wintypes.HWND, wintypes.HDC], wintypes.INT),
    ("GetCursorPos", [ctypes.POINTER(POINT)], wintypes.BOOL),
    ("GetCursorInfo", [ctypes.POINTER(CURSORINFO)], wintypes.BOOL),
    ("GetIconInfo", [wintypes.HICON, ctypes.POINTER(ICONINFO)], wintypes.BOOL),
    (
        "DrawIconEx",
        [
            wintypes.HDC,
            wintypes.INT,
            wintypes.INT,
            wintypes.HICON,
            wintypes.INT,
            wintypes.INT,
            wintypes.UINT,
            wintypes.HBRUSH,
            wintypes.UINT,
        ],
        wintypes.BOOL,
    ),
    ("SetCursorPos", [wintypes.INT, wintypes.INT], wintypes.BOOL),
    ("SendInput", [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int], wintypes.UINT),
    ("SetProcessDpiAwarenessContext", [wintypes.HANDLE], wintypes.BOOL),
    ("LoadCursorW", [wintypes.HINSTANCE, wintypes.LPCWSTR], wintypes.HCURSOR),
]
for _name, _args, _ret in _user32_sigs:
    _fn = getattr(user32, _name)
    _fn.argtypes = _args
    _fn.restype = _ret

user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
user32.LoadCursorW.restype = wintypes.HCURSOR
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int

_gdi32_sigs = [
    ("CreateCompatibleDC", [wintypes.HDC], wintypes.HDC),
    ("DeleteDC", [wintypes.HDC], wintypes.BOOL),
    ("SelectObject", [wintypes.HDC, wintypes.HGDIOBJ], wintypes.HGDIOBJ),
    ("DeleteObject", [wintypes.HGDIOBJ], wintypes.BOOL),
    (
        "CreateDIBSection",
        [
            wintypes.HDC,
            ctypes.POINTER(BITMAPINFO),
            wintypes.UINT,
            ctypes.POINTER(ctypes.c_void_p),
            wintypes.HANDLE,
            wintypes.DWORD,
        ],
        wintypes.HBITMAP,
    ),
    (
        "StretchBlt",
        [
            wintypes.HDC,
            wintypes.INT,
            wintypes.INT,
            wintypes.INT,
            wintypes.INT,
            wintypes.HDC,
            wintypes.INT,
            wintypes.INT,
            wintypes.INT,
            wintypes.INT,
            wintypes.DWORD,
        ],
        wintypes.BOOL,
    ),
    ("SetStretchBltMode", [wintypes.HDC, wintypes.INT], wintypes.INT),
    (
        "BitBlt",
        [
            wintypes.HDC,
            wintypes.INT,
            wintypes.INT,
            wintypes.INT,
            wintypes.INT,
            wintypes.HDC,
            wintypes.INT,
            wintypes.INT,
            wintypes.DWORD,
        ],
        wintypes.BOOL,
    ),
]
for _name, _args, _ret in _gdi32_sigs:
    _fn = getattr(gdi32, _name)
    _fn.argtypes = _args
    _fn.restype = _ret

if hasattr(gdi32, "SetBrushOrgEx"):
    gdi32.SetBrushOrgEx.argtypes = [wintypes.HDC, wintypes.INT, wintypes.INT, ctypes.POINTER(POINT)]
    gdi32.SetBrushOrgEx.restype = wintypes.BOOL


def init_dpi() -> None:
    user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)


def setup_dpi() -> None:
    init_dpi()


def get_screen_size() -> Tuple[int, int]:
    w = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN) or user32.GetSystemMetrics(SM_CXSCREEN)
    h = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN) or user32.GetSystemMetrics(SM_CYSCREEN)
    return (w if w > 0 else 1920, h if h > 0 else 1080)


def get_virtual_origin() -> Tuple[int, int]:
    return (
        int(user32.GetSystemMetrics(SM_XVIRTUALSCREEN)),
        int(user32.GetSystemMetrics(SM_YVIRTUALSCREEN)),
    )


def get_cursor_pos() -> Tuple[int, int]:
    p = POINT()
    if not user32.GetCursorPos(ctypes.byref(p)):
        return 0, 0
    return int(p.x), int(p.y)


def cursor_pos_normalized(screen_w: int, screen_h: int) -> Tuple[int, int, int, int]:
    from .coords import px_to_n

    ox, oy = get_virtual_origin()
    cx, cy = get_cursor_pos()
    lx, ly = cx - ox, cy - oy
    return cx, cy, px_to_n(lx, screen_w), px_to_n(ly, screen_h)


def norm_to_screen_px(xn: float, yn: float, screen_w: int, screen_h: int) -> Tuple[int, int]:
    from .coords import n_to_px

    ox, oy = get_virtual_origin()
    return ox + n_to_px(xn, screen_w), oy + n_to_px(yn, screen_h)


def _arrow_cursor() -> int:
    return int(user32.LoadCursorW(None, ctypes.c_void_p(IDC_ARROW)) or 0)


def draw_cursor_on_dc(hdc_mem: int, screen_w: int, screen_h: int, dst_w: int, dst_h: int) -> bool:
    """Zawsze próbuje narysować kursor. Ukryty systemowy → strzałka IDC_ARROW w GetCursorPos."""
    ox, oy = get_virtual_origin()
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(CURSORINFO)
    got = bool(user32.GetCursorInfo(ctypes.byref(ci)))
    hcursor = int(ci.hCursor) if got and ci.hCursor else 0
    showing = bool(got and (ci.flags & CURSOR_SHOWING) and hcursor)
    if not showing:
        hcursor = _arrow_cursor()
        if not hcursor:
            return False
        cx, cy = get_cursor_pos()
        pt_x, pt_y = cx, cy
        hx, hy = 0, 0
    else:
        ii = ICONINFO()
        if user32.GetIconInfo(ci.hCursor, ctypes.byref(ii)):
            try:
                hx, hy = int(ii.xHotspot), int(ii.yHotspot)
            finally:
                if ii.hbmMask:
                    gdi32.DeleteObject(ii.hbmMask)
                if ii.hbmColor:
                    gdi32.DeleteObject(ii.hbmColor)
        else:
            hx, hy = 0, 0
        pt_x, pt_y = int(ci.ptScreenPos.x), int(ci.ptScreenPos.y)

    cur_x = int(pt_x) - hx - ox
    cur_y = int(pt_y) - hy - oy
    dx = int(round(cur_x * (dst_w / float(screen_w))))
    dy = int(round(cur_y * (dst_h / float(screen_h))))
    return bool(user32.DrawIconEx(hdc_mem, dx, dy, hcursor, 0, 0, 0, None, DI_NORMAL))


def encode_rgb_to_png(rgb: bytes, w: int, h: int) -> bytes:
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)

    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    row = w * 3
    stride = row + 1
    raw = bytearray(stride * h)
    for y in range(h):
        base = y * stride
        raw[base] = 0
        off = y * row
        raw[base + 1 : base + 1 + row] = rgb[off : off + row]
    comp = zlib.compress(bytes(raw), 6)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", comp) + chunk(b"IEND", b"")


def bgra_to_rgb(bgra: bytes, w: int, h: int) -> bytes:
    rgb = bytearray(w * h * 3)
    j = 0
    for i in range(0, len(bgra), 4):
        rgb[j] = bgra[i + 2]
        rgb[j + 1] = bgra[i + 1]
        rgb[j + 2] = bgra[i]
        j += 3
    return bytes(rgb)


def crop_rgb(rgb: bytes, w: int, h: int, x0: int, y0: int, x1: int, y1: int) -> tuple[bytes, int, int]:
    x0 = max(0, min(x0, w))
    y0 = max(0, min(y0, h))
    x1 = max(x0 + 1, min(x1, w))
    y1 = max(y0 + 1, min(y1, h))
    cw, ch = x1 - x0, y1 - y0
    out = bytearray(cw * ch * 3)
    for y in range(ch):
        src = ((y0 + y) * w + x0) * 3
        dst = y * cw * 3
        out[dst : dst + cw * 3] = rgb[src : src + cw * 3]
    return bytes(out), cw, ch


def _capture_rgb(src_x: int, src_y: int, src_w: int, src_h: int, dst_w: int, dst_h: int) -> bytes:
    hdc_screen = user32.GetDC(None)
    if not hdc_screen:
        raise RuntimeError("GetDC failed")
    hdc_mem = None
    hbmp = None
    old = None
    bits = ctypes.c_void_p()
    try:
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        if not hdc_mem:
            raise RuntimeError("CreateCompatibleDC failed")
        bmi = BITMAPINFO()
        ctypes.memset(ctypes.byref(bmi), 0, ctypes.sizeof(bmi))
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = dst_w
        bmi.bmiHeader.biHeight = -dst_h
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB
        hbmp = gdi32.CreateDIBSection(hdc_mem, ctypes.byref(bmi), DIB_RGB_COLORS, ctypes.byref(bits), 0, 0)
        if not hbmp or not bits.value:
            raise RuntimeError("CreateDIBSection failed")
        old = gdi32.SelectObject(hdc_mem, hbmp)
        if not old:
            raise RuntimeError("SelectObject failed")
        gdi32.SetStretchBltMode(hdc_mem, HALFTONE)
        if hasattr(gdi32, "SetBrushOrgEx"):
            pt = POINT()
            gdi32.SetBrushOrgEx(hdc_mem, 0, 0, ctypes.byref(pt))
        if not gdi32.StretchBlt(
            hdc_mem, 0, 0, dst_w, dst_h, hdc_screen, src_x, src_y, src_w, src_h, SRCCOPY
        ):
            raise RuntimeError("StretchBlt failed")
        draw_cursor_on_dc(hdc_mem, src_w, src_h, dst_w, dst_h)
        bgra = ctypes.string_at(bits, dst_w * dst_h * 4)
        return bgra_to_rgb(bgra, dst_w, dst_h)
    finally:
        if hdc_mem and old:
            try:
                gdi32.SelectObject(hdc_mem, old)
            except Exception:
                pass
        if hbmp:
            try:
                gdi32.DeleteObject(hbmp)
            except Exception:
                pass
        if hdc_mem:
            try:
                gdi32.DeleteDC(hdc_mem)
            except Exception:
                pass
        try:
            user32.ReleaseDC(None, hdc_screen)
        except Exception:
            pass


def capture_screenshot_png(target_w: int, target_h: int) -> Tuple[bytes, int, int]:
    screen_w, screen_h = get_screen_size()
    ox, oy = get_virtual_origin()
    rgb = _capture_rgb(ox, oy, screen_w, screen_h, target_w, target_h)
    return encode_rgb_to_png(rgb, target_w, target_h), screen_w, screen_h


def capture_region_png(left: int, top: int, right: int, bottom: int) -> Tuple[bytes, int, int]:
    w, h = max(1, right - left), max(1, bottom - top)
    rgb = _capture_rgb(left, top, w, h, w, h)
    return encode_rgb_to_png(rgb, w, h), w, h


def enum_windows(min_area: int = 2500) -> list[dict]:
    out: list[dict] = []
    seen: set[int] = set()
    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _):
        h = int(hwnd)
        if h in seen or not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        rect = RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        w, ht = rect.right - rect.left, rect.bottom - rect.top
        if w <= 0 or ht <= 0 or w * ht < min_area:
            return True
        length = int(user32.GetWindowTextLengthW(hwnd))
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        seen.add(h)
        out.append(
            {
                "hwnd": h,
                "title": buf.value or "",
                "rect": {
                    "left": int(rect.left),
                    "top": int(rect.top),
                    "right": int(rect.right),
                    "bottom": int(rect.bottom),
                },
            }
        )
        return True

    user32.EnumWindows(enum_proc(callback), 0)
    return out


def find_window(title_substr: str) -> dict | None:
    needle = title_substr.lower()
    for w in enum_windows():
        if needle in (w.get("title") or "").lower():
            return w
    return None


def _send_inputs(*inps: INPUT) -> None:
    n = len(inps)
    if n <= 0:
        return
    arr = (INPUT * n)(*inps)
    user32.SendInput(n, arr, ctypes.sizeof(INPUT))


def _mi(flags: int, data: int = 0, dx: int = 0, dy: int = 0) -> INPUT:
    i = INPUT()
    i.type = INPUT_MOUSE
    i.ii.mi = MOUSEINPUT(dx, dy, data, flags, 0, 0)
    return i


def _ki(scan: int, flags: int) -> INPUT:
    i = INPUT()
    i.type = INPUT_KEYBOARD
    i.ii.ki = KEYBDINPUT(0, scan, flags, 0, 0)
    return i


def move_mouse_norm(xn: float, yn: float) -> Tuple[int, int]:
    screen_w, screen_h = get_screen_size()
    x, y = norm_to_screen_px(xn, yn, screen_w, screen_h)
    user32.SetCursorPos(x, y)
    return screen_w, screen_h


def click_mouse() -> None:
    _send_inputs(_mi(MOUSEEVENTF_LEFTDOWN), _mi(MOUSEEVENTF_LEFTUP))


def right_click_mouse() -> None:
    _send_inputs(_mi(MOUSEEVENTF_RIGHTDOWN), _mi(MOUSEEVENTF_RIGHTUP))


def scroll_down(notches: int = 1) -> None:
    for _ in range(max(1, notches)):
        _send_inputs(_mi(MOUSEEVENTF_WHEEL, (-120) & 0xFFFFFFFF))


def scroll_up(notches: int = 1) -> None:
    for _ in range(max(1, notches)):
        _send_inputs(_mi(MOUSEEVENTF_WHEEL, 120))


def type_text(text: str) -> None:
    for ch in text:
        code = ord(ch)
        _send_inputs(_ki(code, KEYEVENTF_UNICODE), _ki(code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
        time.sleep(0.005)
