from __future__ import annotations

import ctypes
import importlib
import os
import subprocess
import sys
import time
from ctypes import wintypes
from typing import Any

import comtypes
import comtypes.client

ROOT = __import__("pathlib").Path(__file__).parent.resolve()
user32 = ctypes.windll.user32


def _load_uia_module() -> Any:
    try:
        comtypes.client.GetModule("UIAutomationCore.dll")
        return importlib.import_module("comtypes.gen.UIAutomationClient")
    except ImportError as exc:
        if "Typelib different than module" not in str(exc):
            raise
        for name in list(sys.modules):
            if name.startswith("comtypes.gen.UIAutomation"):
                sys.modules.pop(name, None)
        comtypes.client.GetModule("UIAutomationCore.dll")
        return importlib.import_module("comtypes.gen.UIAutomationClient")


uia = _load_uia_module()
comtypes.CoInitialize()


class Desktop:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._automation: Any = None
        self._last_desktop_tree: dict[str, Any] | None = None
        self._last_action_index: dict[str, dict[str, Any]] = {}

    def _init_automation(self) -> None:
        self._automation = comtypes.client.CreateObject(uia.CUIAutomation, interface=uia.IUIAutomation)

    @property
    def automation(self) -> Any:
        if self._automation is None:
            self._init_automation()
        return self._automation

    def observe(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        from core_observation import observe as observe_desktop
        cfg = config or {}
        hc = cfg.get("hover_cache", self.config.get("hover_cache", {}))
        return observe_desktop(self, hc)

    def observe_screen(self) -> dict[str, int]:
        return {"width": user32.GetSystemMetrics(0), "height": user32.GetSystemMetrics(1)}

    def last_desktop_tree(self) -> dict[str, Any] | None:
        return self._last_desktop_tree

    def last_action_index(self) -> dict[str, dict[str, Any]]:
        return self._last_action_index

    def get_window_tokens(self) -> list[dict[str, Any]]:
        sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        windows = [{
            "token": "W0",
            "name": "Screen",
            "title": "Desktop",
            "hwnd": 0,
            "rect": {"left": 0, "top": 0, "right": sw, "bottom": sh},
            "children": [],
        }]
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

        def callback(hwnd, _):
            if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            rect = wintypes.RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)) or rect.right <= rect.left or rect.bottom <= rect.top:
                return True
            title = ctypes.create_unicode_buffer(length + 1)
            class_name = ctypes.create_unicode_buffer(256)
            pid = wintypes.DWORD()
            user32.GetWindowTextW(hwnd, title, length + 1)
            user32.GetClassNameW(hwnd, class_name, 256)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            windows.append({
                "token": f"W{len(windows)}",
                "name": "Window",
                "title": title.value,
                "hwnd": int(hwnd),
                "rect": {"left": rect.left, "top": rect.top, "right": rect.right, "bottom": rect.bottom},
                "process_id": int(pid.value),
                "class_name": class_name.value,
            })
            return True

        try:
            user32.EnumWindows(EnumWindowsProc(callback), 0)
        except Exception:
            pass
        return windows

    def click(self, x: int, y: int, hwnd: int = 0) -> dict[str, Any]:
        if hwnd:
            lparam = (y << 16) | (x & 0xFFFF)
            user32.PostMessageW(hwnd, 0x0201, 0, lparam)
            user32.PostMessageW(hwnd, 0x0202, 0, lparam)
        else:
            user32.SetCursorPos(x, y)
            user32.mouse_event(0x0002, 0, 0, 0, 0)
            user32.mouse_event(0x0004, 0, 0, 0, 0)
        return {"ok": True, "action": "click", "x": x, "y": y, "hwnd": hwnd}

    def type_text(self, text: str) -> dict[str, Any]:
        for char in text:
            vk = user32.VkKeyScanW(ord(char))
            if vk == -1:
                continue
            vk_code = vk & 0xFF
            shift = (vk >> 8) & 0xFF
            if shift:
                user32.keybd_event(0x10, 0, 0, 0)
            user32.keybd_event(vk_code, 0, 0, 0)
            user32.keybd_event(vk_code, 0, 2, 0)
            if shift:
                user32.keybd_event(0x10, 0, 2, 0)
            time.sleep(0.01)
        return {"ok": True, "action": "type_text", "text": text}

    def press_key(self, key: str) -> dict[str, Any]:
        key_map = {
            "enter": 0x0D, "tab": 0x09, "escape": 0x1B, "space": 0x20,
            "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
            "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
            "delete": 0x2E, "backspace": 0x08, "insert": 0x2D,
            "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
            "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
            "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
        }
        vk = key_map.get(key.lower())
        if vk is None:
            return {"ok": False, "action": "press_key", "error": f"unknown key: {key}"}
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, 2, 0)
        return {"ok": True, "action": "press_key", "key": key}

    def hotkey(self, *keys: Any) -> dict[str, Any]:
        key_map = {
            "ctrl": 0x11, "control": 0x11, "alt": 0x12, "shift": 0x10,
            "win": 0x5B, "windows": 0x5B,
            "enter": 0x0D, "tab": 0x09, "escape": 0x1B, "space": 0x20,
            "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
            "c": 0x43, "v": 0x56, "x": 0x58, "z": 0x5A,
            "a": 0x41, "s": 0x53, "f": 0x46, "n": 0x4E,
            "o": 0x4F, "p": 0x50, "w": 0x57, "r": 0x52, "l": 0x4C, "d": 0x44,
        }
        if len(keys) == 1 and isinstance(keys[0], (list, tuple)):
            raw_parts = list(keys[0])
        elif len(keys) == 1:
            raw_parts = str(keys[0]).split("+")
        else:
            raw_parts = list(keys)
        parts = [str(k).strip().lower() for k in raw_parts if str(k).strip()]
        if not parts:
            return {"ok": False, "action": "hotkey", "error": "no keys provided"}
        vks = []
        for k in parts:
            vk = key_map.get(k)
            if vk is None:
                return {"ok": False, "action": "hotkey", "error": f"unknown key in combination: {k}"}
            vks.append(vk)
        for vk in vks[:-1]:
            user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vks[-1], 0, 0, 0)
        user32.keybd_event(vks[-1], 0, 2, 0)
        for vk in reversed(vks[:-1]):
            user32.keybd_event(vk, 0, 2, 0)
        return {"ok": True, "action": "hotkey", "keys": parts}

    def scroll(self, x: int, y: int, amount: int, hwnd: int = 0) -> dict[str, Any]:
        if hwnd:
            lparam = (y << 16) | (x & 0xFFFF)
            user32.PostMessageW(hwnd, 0x020A, amount << 16, lparam)
        else:
            user32.SetCursorPos(x, y)
            user32.mouse_event(0x0800, 0, 0, amount * 120, 0)
        return {"ok": True, "action": "scroll", "x": x, "y": y, "amount": amount, "hwnd": hwnd}

    def open_url(self, browser: str = "chrome", url: str = "") -> dict[str, Any]:
        if not str(url or "").strip():
            raise RuntimeError("open_url requires a non-empty url")
        browser_paths = {
            "chrome": [r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"],
            "edge": [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"],
            "firefox": [r"C:\Program Files\Mozilla Firefox\firefox.exe"],
            "opera": [
                r"%LOCALAPPDATA%\Programs\Opera\opera.exe",
                r"%LOCALAPPDATA%\Programs\Opera\launcher.exe",
                r"C:\Program Files\Opera\opera.exe",
                r"C:\Program Files\Opera\launcher.exe",
                r"C:\Program Files (x86)\Opera\opera.exe",
                r"C:\Program Files (x86)\Opera\launcher.exe",
            ],
        }
        browser_key = str(browser or "").strip().lower()
        if browser_key == "default":
            os.startfile(str(url))
            return {"ok": True, "action": "open_url", "browser": "default", "url": url}
        if browser_key not in browser_paths:
            raise RuntimeError(f"open_url unsupported browser '{browser}'; choose one of {sorted(browser_paths)} or 'default'")
        exe = next((os.path.expandvars(p) for p in browser_paths[browser_key] if os.path.exists(os.path.expandvars(p))), None)
        if not exe:
            raise RuntimeError(f"open_url browser '{browser_key}' is not installed in known paths")
        subprocess.Popen([exe, url])
        return {"ok": True, "action": "open_url", "browser": browser_key, "url": url, "exe": exe}


_desktop_instance: Desktop | None = None


def get_desktop(config: dict[str, Any] | None = None) -> Desktop:
    global _desktop_instance
    if _desktop_instance is None:
        _desktop_instance = Desktop(config)
    return _desktop_instance


def observe(config: dict[str, Any] | None = None) -> dict[str, Any]:
    return get_desktop(config).observe(config)


def observe_screen() -> dict[str, int]:
    return get_desktop().observe_screen()


def last_desktop_tree() -> dict[str, Any] | None:
    return get_desktop().last_desktop_tree()


def last_action_index() -> dict[str, dict[str, Any]]:
    return get_desktop().last_action_index()
