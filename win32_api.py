"""Win32 API constants and functions - pure ctypes, no UIA."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

# =============================================================================
# Win32 Constants
# =============================================================================

# Window styles
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

# Window messages
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_MOUSEWHEEL = 0x020A
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_CHAR = 0x0102
WM_SETTEXT = 0x000C
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E

# Virtual key codes
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_RETURN = 0x0D
VK_TAB = 0x09
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_UP = 0x26
VK_DOWN = 0x28
VK_LEFT = 0x25
VK_RIGHT = 0x27
VK_HOME = 0x24
VK_END = 0x23
VK_PRIOR = 0x21  # PageUp
VK_NEXT = 0x22   # PageDown
VK_DELETE = 0x2E
VK_BACK = 0x08
VK_INSERT = 0x2D
VK_F1 = 0x70
VK_F12 = 0x7B

# Mouse events
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_WHEEL = 0x0800

# System metrics
SM_CXSCREEN = 0
SM_CYSCREEN = 1

# Window states
SW_HIDE = 0
SW_SHOW = 5
SW_MINIMIZE = 6
SW_RESTORE = 9

# DWM
DWMWA_EXTENDED_FRAME_BOUNDS = 9

# =============================================================================
# Win32 Function Bindings
# =============================================================================

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
dwmapi = ctypes.windll.dwmapi

# Window enumeration
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

# Core window functions
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int

user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = ctypes.c_bool
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = ctypes.c_bool
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsIconic.restype = ctypes.c_bool
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_longlong
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = ctypes.c_bool
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = ctypes.c_bool
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = ctypes.c_bool
user32.WindowFromPoint.argtypes = [wintypes.POINT]
user32.WindowFromPoint.restype = wintypes.HWND
user32.PostMessageW.argtypes = [wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = ctypes.c_bool
user32.SendMessageW.argtypes = [wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
user32.SendMessageW.restype = ctypes.c_longlong
user32.keybd_event.argtypes = [ctypes.c_byte, ctypes.c_byte, ctypes.c_ulong, ctypes.c_ulong]
user32.mouse_event.argtypes = [ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
user32.VkKeyScanW.argtypes = [wintypes.WCHAR]
user32.VkKeyScanW.restype = ctypes.c_short

# DWM for extended frame bounds
dwmapi.DwmGetWindowAttribute.argtypes = [
    wintypes.HWND, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong
]
dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long

# =============================================================================
# Helper Functions
# =============================================================================

def get_screen_size() -> tuple[int, int]:
    """Get screen dimensions."""
    return (
        user32.GetSystemMetrics(SM_CXSCREEN),
        user32.GetSystemMetrics(SM_CYSCREEN)
    )

def get_window_title(hwnd: int) -> str:
    """Get window title."""
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value

def get_window_class(hwnd: int) -> str:
    """Get window class name."""
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value

def get_window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    """Get window rectangle (left, top, right, bottom)."""
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return (rect.left, rect.top, rect.right, rect.bottom)

def get_extended_frame_bounds(hwnd: int) -> tuple[int, int, int, int] | None:
    """Get extended frame bounds (includes shadow) via DWM."""
    rect = wintypes.RECT()
    hr = dwmapi.DwmGetWindowAttribute(
        hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rect), ctypes.sizeof(rect)
    )
    if hr != 0:
        return None
    return (rect.left, rect.top, rect.right, rect.bottom)

def is_window_visible(hwnd: int) -> bool:
    """Check if window is visible and not minimized."""
    return bool(user32.IsWindowVisible(hwnd)) and not bool(user32.IsIconic(hwnd))

def get_window_process_id(hwnd: int) -> int:
    """Get process ID owning the window."""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)

def get_window_ex_style(hwnd: int) -> int:
    """Get extended window style."""
    return int(user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE))

def is_hit_test_transparent(hwnd: int) -> bool:
    """Check if window is hit-test transparent."""
    if hwnd <= 0:
        return True
    ex_style = get_window_ex_style(hwnd)
    if ex_style & WS_EX_TRANSPARENT:
        return True
    if ex_style & WS_EX_LAYERED:
        if ex_style & (WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE):
            return True
    return False

def window_at_point(x: int, y: int, exclude_hwnd: int = 0) -> int:
    """Get window at screen point, skipping transparent windows."""
    pt = wintypes.POINT(x, y)
    hwnd = user32.WindowFromPoint(pt)
    if hwnd == 0 or hwnd == exclude_hwnd:
        return 0
    if is_hit_test_transparent(hwnd):
        return 0
    return hwnd

def enum_windows() -> list[dict]:
    """Enumerate all visible top-level windows."""
    windows = []
    
    def enum_proc(hwnd, lparam):
        if not is_window_visible(hwnd):
            return True
        rect = get_window_rect(hwnd)
        if not rect or rect[2] <= rect[0] or rect[3] <= rect[1]:
            return True
        title = get_window_title(hwnd)
        if not title:
            return True
        windows.append({
            "hwnd": int(hwnd),
            "title": title,
            "class_name": get_window_class(hwnd),
            "rect": {"left": rect[0], "top": rect[1], "right": rect[2], "bottom": rect[3]},
            "process_id": get_window_process_id(hwnd),
        })
        return True
    
    cb = EnumWindowsProc(enum_proc)
    user32.EnumWindows(cb, 0)
    return windows

def set_foreground_window(hwnd: int) -> bool:
    """Bring window to foreground."""
    return bool(user32.SetForegroundWindow(hwnd))

def click_at(x: int, y: int, hwnd: int = 0) -> dict:
    """Click at coordinates."""
    if hwnd:
        lparam = (y << 16) | (x & 0xFFFF)
        user32.PostMessageW(hwnd, WM_LBUTTONDOWN, 0, lparam)
        user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lparam)
    else:
        user32.SetCursorPos(x, y)
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    return {"ok": True, "action": "click", "x": x, "y": y, "hwnd": hwnd}

def type_text(text: str) -> dict:
    """Type text via key events."""
    for ch in text:
        vk = user32.VkKeyScanW(ord(ch))
        if vk == -1:
            continue
        vk_code = vk & 0xFF
        shift = (vk >> 8) & 0xFF
        if shift:
            user32.keybd_event(VK_SHIFT, 0, 0, 0)
        user32.keybd_event(vk_code, 0, 0, 0)
        user32.keybd_event(vk_code, 0, 2, 0)
        if shift:
            user32.keybd_event(VK_SHIFT, 0, 2, 0)
        ctypes.windll.kernel32.Sleep(10)
    return {"ok": True, "action": "type_text", "text": text}

def press_key(key: str) -> dict:
    """Press a single key."""
    key_map = {
        "enter": VK_RETURN, "tab": VK_TAB, "escape": VK_ESCAPE, "space": VK_SPACE,
        "up": VK_UP, "down": VK_DOWN, "left": VK_LEFT, "right": VK_RIGHT,
        "home": VK_HOME, "end": VK_END, "pageup": VK_PRIOR, "pagedown": VK_NEXT,
        "delete": VK_DELETE, "backspace": VK_BACK, "insert": VK_INSERT,
        "f1": VK_F1, "f2": 0x71, "f3": 0x72, "f4": 0x73,
        "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
        "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": VK_F12,
    }
    vk = key_map.get(key.lower())
    if vk is None:
        return {"ok": False, "action": "press_key", "error": f"unknown key: {key}"}
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, 2, 0)
    return {"ok": True, "action": "press_key", "key": key}

def hotkey(keys: list[str]) -> dict:
    """Press key combination."""
    key_map = {
        "ctrl": VK_CONTROL, "control": VK_CONTROL,
        "alt": VK_MENU,
        "shift": VK_SHIFT,
        "win": VK_LWIN, "windows": VK_LWIN,
        "enter": VK_RETURN, "tab": VK_TAB, "escape": VK_ESCAPE, "space": VK_SPACE,
        "up": VK_UP, "down": VK_DOWN, "left": VK_LEFT, "right": VK_RIGHT,
        "c": 0x43, "v": 0x56, "x": 0x58, "z": 0x5A,
        "a": 0x41, "s": 0x53, "f": 0x46, "n": 0x4E,
        "o": 0x4F, "p": 0x50, "w": 0x57,
        "r": 0x52, "l": 0x4C, "d": 0x44,
    }
    vks = []
    for k in keys:
        vk = key_map.get(k.lower().strip())
        if vk is None:
            return {"ok": False, "action": "hotkey", "error": f"unknown key: {k}"}
        vks.append(vk)
    
    # Press modifiers first
    for vk in vks[:-1]:
        user32.keybd_event(vk, 0, 0, 0)
    # Press main key
    user32.keybd_event(vks[-1], 0, 0, 0)
    user32.keybd_event(vks[-1], 0, 2, 0)
    # Release modifiers
    for vk in reversed(vks[:-1]):
        user32.keybd_event(vk, 0, 2, 0)
    return {"ok": True, "action": "hotkey", "keys": keys}

def scroll_at(x: int, y: int, amount: int, hwnd: int = 0) -> dict:
    """Scroll at coordinates."""
    if hwnd:
        lparam = (y << 16) | (x & 0xFFFF)
        user32.PostMessageW(hwnd, WM_MOUSEWHEEL, amount << 16, lparam)
    else:
        user32.SetCursorPos(x, y)
        user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, amount * 120, 0)
    return {"ok": True, "action": "scroll", "x": x, "y": y, "amount": amount, "hwnd": hwnd}

def open_url(browser: str = "chrome", url: str = "") -> dict:
    """Open URL in browser."""
    import subprocess
    import os
    browser_paths = {
        "chrome": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ],
        "edge": [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"],
        "firefox": [r"C:\Program Files\Mozilla Firefox\firefox.exe"],
        "opera": [
            r"C:\Program Files\Opera\launcher.exe",
            r"C:\Program Files (x86)\Opera\launcher.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera\launcher.exe"),
        ],
    }
    paths = browser_paths.get(browser.lower(), [])
    exe = None
    for p in paths:
        if os.path.exists(os.path.expandvars(p)):
            exe = os.path.expandvars(p)
            break
    if not exe:
        subprocess.Popen(["start", "", url], shell=True)
        return {"ok": True, "action": "open_url", "browser": "default", "url": url, "launched": True, "verified": False}
    subprocess.Popen([exe, url])
    return {"ok": True, "action": "open_url", "browser": browser, "url": url, "launched": True, "verified": False}