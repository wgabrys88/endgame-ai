from __future__ import annotations
import ctypes
from ctypes import wintypes
GWL_EXSTYLE = -20
WS_EX_LAYERED = 524288
WS_EX_TRANSPARENT = 32
WS_EX_TOOLWINDOW = 128
WS_EX_NOACTIVATE = 134217728
WM_LBUTTONDOWN = 513
WM_LBUTTONUP = 514
WM_MOUSEWHEEL = 522
WM_KEYDOWN = 256
WM_KEYUP = 257
WM_CHAR = 258
WM_SETTEXT = 12
WM_GETTEXT = 13
WM_GETTEXTLENGTH = 14
VK_SHIFT = 16
VK_CONTROL = 17
VK_MENU = 18
VK_LWIN = 91
VK_RWIN = 92
VK_RETURN = 13
VK_TAB = 9
VK_ESCAPE = 27
VK_SPACE = 32
VK_UP = 38
VK_DOWN = 40
VK_LEFT = 37
VK_RIGHT = 39
VK_HOME = 36
VK_END = 35
VK_PRIOR = 33
VK_NEXT = 34
VK_DELETE = 46
VK_BACK = 8
VK_INSERT = 45
VK_F1 = 112
VK_F12 = 123
MOUSEEVENTF_LEFTDOWN = 2
MOUSEEVENTF_LEFTUP = 4
MOUSEEVENTF_WHEEL = 2048
SM_CXSCREEN = 0
SM_CYSCREEN = 1
SW_HIDE = 0
SW_SHOW = 5
SW_MINIMIZE = 6
SW_RESTORE = 9
DWMWA_EXTENDED_FRAME_BOUNDS = 9
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
dwmapi = ctypes.windll.dwmapi
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
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
dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong]
dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long

def get_screen_size() -> tuple[int, int]:
    return (user32.GetSystemMetrics(SM_CXSCREEN), user32.GetSystemMetrics(SM_CYSCREEN))

def get_window_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ''
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value

def get_window_class(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value

def get_window_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    rect = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return (rect.left, rect.top, rect.right, rect.bottom)

def get_extended_frame_bounds(hwnd: int) -> tuple[int, int, int, int] | None:
    rect = wintypes.RECT()
    hr = dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rect), ctypes.sizeof(rect))
    if hr != 0:
        return None
    return (rect.left, rect.top, rect.right, rect.bottom)

def is_window_visible(hwnd: int) -> bool:
    return bool(user32.IsWindowVisible(hwnd)) and (not bool(user32.IsIconic(hwnd)))

def get_window_process_id(hwnd: int) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)

def get_window_ex_style(hwnd: int) -> int:
    return int(user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE))

def is_hit_test_transparent(hwnd: int) -> bool:
    if hwnd <= 0:
        return True
    ex_style = get_window_ex_style(hwnd)
    if ex_style & WS_EX_TRANSPARENT:
        return True
    if ex_style & WS_EX_LAYERED:
        if ex_style & (WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE):
            return True
    return False

def window_at_point(x: int, y: int, exclude_hwnd: int=0) -> int:
    pt = wintypes.POINT(x, y)
    hwnd = user32.WindowFromPoint(pt)
    if hwnd == 0 or hwnd == exclude_hwnd:
        return 0
    if is_hit_test_transparent(hwnd):
        return 0
    return hwnd

def enum_windows() -> list[dict]:
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
        windows.append({'hwnd': int(hwnd), 'title': title, 'class_name': get_window_class(hwnd), 'rect': {'left': rect[0], 'top': rect[1], 'right': rect[2], 'bottom': rect[3]}, 'process_id': get_window_process_id(hwnd)})
        return True
    cb = EnumWindowsProc(enum_proc)
    user32.EnumWindows(cb, 0)
    return windows

def set_foreground_window(hwnd: int) -> bool:
    return bool(user32.SetForegroundWindow(hwnd))

def click_at(x: int, y: int, hwnd: int=0) -> dict:
    if hwnd:
        lparam = y << 16 | x & 65535
        user32.PostMessageW(hwnd, WM_LBUTTONDOWN, 0, lparam)
        user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lparam)
    else:
        user32.SetCursorPos(x, y)
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    return {'ok': True, 'action': 'click', 'x': x, 'y': y, 'hwnd': hwnd}

def type_text(text: str) -> dict:
    for ch in text:
        vk = user32.VkKeyScanW(ord(ch))
        if vk == -1:
            continue
        vk_code = vk & 255
        shift = vk >> 8 & 255
        if shift:
            user32.keybd_event(VK_SHIFT, 0, 0, 0)
        user32.keybd_event(vk_code, 0, 0, 0)
        user32.keybd_event(vk_code, 0, 2, 0)
        if shift:
            user32.keybd_event(VK_SHIFT, 0, 2, 0)
        ctypes.windll.kernel32.Sleep(10)
    return {'ok': True, 'action': 'type_text', 'text': text}

def press_key(key: str) -> dict:
    key_map = {'enter': VK_RETURN, 'tab': VK_TAB, 'escape': VK_ESCAPE, 'space': VK_SPACE, 'up': VK_UP, 'down': VK_DOWN, 'left': VK_LEFT, 'right': VK_RIGHT, 'home': VK_HOME, 'end': VK_END, 'pageup': VK_PRIOR, 'pagedown': VK_NEXT, 'delete': VK_DELETE, 'backspace': VK_BACK, 'insert': VK_INSERT, 'f1': VK_F1, 'f2': 113, 'f3': 114, 'f4': 115, 'f5': 116, 'f6': 117, 'f7': 118, 'f8': 119, 'f9': 120, 'f10': 121, 'f11': 122, 'f12': VK_F12}
    vk = key_map.get(key.lower())
    if vk is None:
        return {'ok': False, 'action': 'press_key', 'error': f'unknown key: {key}'}
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, 2, 0)
    return {'ok': True, 'action': 'press_key', 'key': key}

def hotkey(keys: list[str]) -> dict:
    key_map = {'ctrl': VK_CONTROL, 'control': VK_CONTROL, 'alt': VK_MENU, 'shift': VK_SHIFT, 'win': VK_LWIN, 'windows': VK_LWIN, 'enter': VK_RETURN, 'tab': VK_TAB, 'escape': VK_ESCAPE, 'space': VK_SPACE, 'up': VK_UP, 'down': VK_DOWN, 'left': VK_LEFT, 'right': VK_RIGHT, 'c': 67, 'v': 86, 'x': 88, 'z': 90, 'a': 65, 's': 83, 'f': 70, 'n': 78, 'o': 79, 'p': 80, 'w': 87, 'r': 82, 'l': 76, 'd': 68}
    vks = []
    for k in keys:
        vk = key_map.get(k.lower().strip())
        if vk is None:
            return {'ok': False, 'action': 'hotkey', 'error': f'unknown key: {k}'}
        vks.append(vk)
    for vk in vks[:-1]:
        user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vks[-1], 0, 0, 0)
    user32.keybd_event(vks[-1], 0, 2, 0)
    for vk in reversed(vks[:-1]):
        user32.keybd_event(vk, 0, 2, 0)
    return {'ok': True, 'action': 'hotkey', 'keys': keys}

def scroll_at(x: int, y: int, amount: int, hwnd: int=0) -> dict:
    if hwnd:
        lparam = y << 16 | x & 65535
        user32.PostMessageW(hwnd, WM_MOUSEWHEEL, amount << 16, lparam)
    else:
        user32.SetCursorPos(x, y)
        user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, amount * 120, 0)
    return {'ok': True, 'action': 'scroll', 'x': x, 'y': y, 'amount': amount, 'hwnd': hwnd}

def open_url(browser: str | None = None, url: str = '') -> dict:
    import subprocess
    import os
    if not browser:
        subprocess.Popen(['start', '', url], shell=True)
        return {'ok': True, 'action': 'open_url', 'browser': 'default', 'url': url, 'launched': True, 'verified': False}
    browser_paths = {'chrome': ['C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', 'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe'], 'edge': ['C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'], 'firefox': ['C:\\Program Files\\Mozilla Firefox\\firefox.exe'], 'opera': ['C:\\Program Files\\Opera\\launcher.exe', 'C:\\Program Files (x86)\\Opera\\launcher.exe', os.path.expandvars('%LOCALAPPDATA%\\Programs\\Opera\\launcher.exe')]}
    paths = browser_paths.get(browser.lower(), [])
    exe = None
    for p in paths:
        if os.path.exists(os.path.expandvars(p)):
            exe = os.path.expandvars(p)
            break
    if not exe:
        subprocess.Popen(['start', '', url], shell=True)
        return {'ok': True, 'action': 'open_url', 'browser': 'default', 'url': url, 'launched': True, 'verified': False}
    subprocess.Popen([exe, url])
    return {'ok': True, 'action': 'open_url', 'browser': browser, 'url': url, 'launched': True, 'verified': False}