"""Desktop observation for Windows 11 using UIA COM via comtypes.gen.UIAutomationClient.

Real Windows desktop observation with Element/Observation types, hover probing,
window tokens, bounded tree, and configurable observation.
"""
from __future__ import annotations

import ctypes
import json
import platform
import time
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import Any, Literal
from enum import IntEnum

import comtypes
import comtypes.client
import comtypes.gen.UIAutomationClient as uia

# Initialize COM
comtypes.CoInitialize()


# =============================================================================
# Control type name mapping (from UIAutomationClient)
# =============================================================================

CONTROL_TYPE_NAMES: dict[int, str] = {
    50032: "Window",        # UIA_WindowControlTypeId
    50033: "Pane",          # UIA_PaneControlTypeId
    50000: "Button",        # UIA_ButtonControlTypeId
    50020: "Text",          # UIA_TextControlTypeId
    50004: "Edit",          # UIA_EditControlTypeId
    50008: "List",          # UIA_ListControlTypeId
    50009: "ListItem",      # UIA_ListItemControlTypeId
    50010: "Tree",          # UIA_TreeControlTypeId
    50011: "TreeItem",      # UIA_TreeItemControlTypeId
    50017: "Tab",           # UIA_TabControlTypeId
    50018: "TabItem",       # UIA_TabItemControlTypeId
    50012: "Menu",          # UIA_MenuControlTypeId
    50013: "MenuItem",      # UIA_MenuItemControlTypeId
    50015: "ToolBar",       # UIA_ToolBarControlTypeId
    50023: "StatusBar",     # UIA_StatusBarControlTypeId
    50003: "ScrollBar",     # UIA_ScrollBarControlTypeId
    50014: "Slider",        # UIA_SliderControlTypeId
    50019: "ProgressBar",   # UIA_ProgressBarControlTypeId
    50006: "Image",         # UIA_ImageControlTypeId
    50016: "Hyperlink",     # UIA_HyperlinkControlTypeId
    50001: "CheckBox",      # UIA_CheckBoxControlTypeId
    50017: "RadioButton",   # UIA_RadioButtonControlTypeId
    50002: "ComboBox",      # UIA_ComboBoxControlTypeId
    50021: "Spinner",       # UIA_SpinnerControlTypeId
    50022: "ToolTip",       # UIA_ToolTipControlTypeId
    50026: "Group",         # UIA_GroupControlTypeId
    50028: "Separator",     # UIA_SeparatorControlTypeId
    50027: "Thumb",         # UIA_ThumbControlTypeId
}


def control_type_name(control_type_id: int) -> str:
    return CONTROL_TYPE_NAMES.get(control_type_id, f"Unknown({control_type_id})")


# =============================================================================
# Property IDs (from UIAutomationClient)
# =============================================================================

UIA_NamePropertyId = 30005
UIA_ControlTypePropertyId = 30003
UIA_LocalizedControlTypePropertyId = 30013
UIA_BoundingRectanglePropertyId = 30001
UIA_ClassNamePropertyId = 30018
UIA_ProcessIdPropertyId = 30016
UIA_RuntimeIdPropertyId = 30019
UIA_IsEnabledPropertyId = 30010
UIA_IsOffscreenPropertyId = 30011
UIA_HasKeyboardFocusPropertyId = 30014
UIA_IsKeyboardFocusablePropertyId = 30015
UIA_AutomationIdPropertyId = 30011
UIA_FrameworkIdPropertyId = 30020
UIA_NativeWindowHandlePropertyId = 30020
UIA_WindowVisualStatePropertyId = 30027
UIA_WindowWindowInteractionStatePropertyId = 30028
UIA_IsWindowPatternAvailablePropertyId = 30029


# =============================================================================
# Data classes for observation
# =============================================================================


@dataclass
class Rect:
    """Bounding rectangle."""
    left: int = 0
    top: int = 0
    right: int = 0
    bottom: int = 0
    
    @property
    def width(self) -> int:
        return self.right - self.left
    
    @property
    def height(self) -> int:
        return self.bottom - self.top
    
    def to_dict(self) -> dict[str, int]:
        return {"left": self.left, "top": self.top, "right": self.right, "bottom": self.bottom}


@dataclass
class Element:
    """UIA element with key properties for decision making."""
    name: str = ""
    control_type: str = ""
    control_type_id: int = 0
    automation_id: str = ""
    class_name: str = ""
    process_id: int = 0
    rect: Rect = field(default_factory=Rect)
    is_enabled: bool = True
    is_offscreen: bool = False
    has_focus: bool = False
    framework_id: str = ""
    runtime_id: list[int] = field(default_factory=list)
    window_handle: int = 0
    children: list["Element"] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "control_type": self.control_type,
            "control_type_id": self.control_type_id,
            "automation_id": self.automation_id,
            "class_name": self.class_name,
            "process_id": self.process_id,
            "rect": self.rect.to_dict(),
            "is_enabled": self.is_enabled,
            "is_offscreen": self.is_offscreen,
            "has_focus": self.has_focus,
            "framework_id": self.framework_id,
            "runtime_id": self.runtime_id,
            "window_handle": self.window_handle,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class Observation:
    """Full desktop observation snapshot."""
    timestamp: float = field(default_factory=time.time)
    screen_width: int = 0
    screen_height: int = 0
    focused_element: Element | None = None
    root_elements: list[Element] = field(default_factory=list)
    active_window: Element | None = None
    focused_title: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "screen_width": self.screen_width,
            "screen_height": self.screen_height,
            "focused_element": self.focused_element.to_dict() if self.focused_element else None,
            "root_elements": [e.to_dict() for e in self.root_elements],
            "active_window": self.active_window.to_dict() if self.active_window else None,
            "focused_title": self.focused_title,
        }


# =============================================================================
# Variant helpers
# =============================================================================


def variant_to_str(variant: Any) -> str:
    if variant is None:
        return ""
    if hasattr(variant, 'value'):
        val = variant.value
        if val is None:
            return ""
        return str(val)
    return str(variant)


def variant_to_int(variant: Any) -> int:
    if variant is None:
        return 0
    if hasattr(variant, 'value'):
        val = variant.value
        if val is None:
            return 0
        try:
            return int(val)
        except (ValueError, TypeError):
            return 0
    try:
        return int(variant)
    except (ValueError, TypeError):
        return 0


def variant_to_bool(variant: Any) -> bool:
    if variant is None:
        return False
    if hasattr(variant, 'value'):
        val = variant.value
        if val is None:
            return False
        return bool(val)
    return bool(variant)


def variant_to_runtime_id(variant: Any) -> list[int]:
    if variant is None:
        return []
    try:
        if hasattr(variant, 'value'):
            val = variant.value
            if val is None:
                return []
            if hasattr(val, '__iter__'):
                return list(val)
        return []
    except Exception:
        return []


def variant_to_rect(variant: Any) -> Rect:
    rect = Rect()
    if variant is None:
        return rect
    try:
        if hasattr(variant, 'value'):
            val = variant.value
            if val is None:
                return rect
            if hasattr(val, '__iter__'):
                arr = list(val)
                if len(arr) >= 4:
                    rect = Rect(
                        left=int(arr[0]),
                        top=int(arr[1]),
                        right=int(arr[0] + arr[2]),
                        bottom=int(arr[1] + arr[3]),
                    )
    except Exception:
        pass
    return rect


# =============================================================================
# Desktop class - main observation interface
# =============================================================================


class Desktop:
    """Main desktop observation class using UIA COM via comtypes.gen.UIAutomationClient."""
    
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._automation: uia.IUIAutomation | None = None
        self._last_observation: Observation | None = None
        self._focused_title_cache: str = ""
        self._init_automation()
    
    def _init_automation(self) -> None:
        """Initialize UIA automation."""
        try:
            self._automation = comtypes.client.CreateObject(
                uia.CUIAutomation, interface=uia.IUIAutomation
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize UIA automation: {e}")
    
    @property
    def automation(self) -> uia.IUIAutomation:
        if self._automation is None:
            self._init_automation()
        return self._automation
    
    def _get_root_element(self) -> uia.IUIAutomationElement:
        """Get the desktop root element."""
        root = self.automation.GetRootElement()
        if not root:
            raise RuntimeError("Failed to get root element")
        return root
    
    def _get_property(self, element: uia.IUIAutomationElement, property_id: int) -> Any:
        """Get a property value from an element."""
        try:
            return element.GetCurrentPropertyValue(property_id)
        except Exception:
            return None
    
    def _element_to_element(self, uia_element: uia.IUIAutomationElement, max_depth: int = 3, current_depth: int = 0) -> Element:
        """Convert UIA element to our Element dataclass."""
        if current_depth >= max_depth:
            return Element()
        
        # Get properties
        name_var = self._get_property(uia_element, UIA_NamePropertyId)
        control_type_var = self._get_property(uia_element, UIA_ControlTypePropertyId)
        rect_var = self._get_property(uia_element, UIA_BoundingRectanglePropertyId)
        class_name_var = self._get_property(uia_element, UIA_ClassNamePropertyId)
        process_id_var = self._get_property(uia_element, UIA_ProcessIdPropertyId)
        runtime_id_var = self._get_property(uia_element, UIA_RuntimeIdPropertyId)
        is_enabled_var = self._get_property(uia_element, UIA_IsEnabledPropertyId)
        is_offscreen_var = self._get_property(uia_element, UIA_IsOffscreenPropertyId)
        has_focus_var = self._get_property(uia_element, UIA_HasKeyboardFocusPropertyId)
        framework_id_var = self._get_property(uia_element, UIA_FrameworkIdPropertyId)
        automation_id_var = self._get_property(uia_element, UIA_AutomationIdPropertyId)
        window_handle_var = self._get_property(uia_element, UIA_NativeWindowHandlePropertyId)
        
        control_type_id = variant_to_int(control_type_var)
        
        element = Element(
            name=variant_to_str(name_var),
            control_type=control_type_name(control_type_id),
            control_type_id=control_type_id,
            automation_id=variant_to_str(automation_id_var),
            class_name=variant_to_str(class_name_var),
            process_id=variant_to_int(process_id_var),
            rect=variant_to_rect(rect_var),
            is_enabled=variant_to_bool(is_enabled_var),
            is_offscreen=variant_to_bool(is_offscreen_var),
            has_focus=variant_to_bool(has_focus_var),
            framework_id=variant_to_str(framework_id_var),
            runtime_id=variant_to_runtime_id(runtime_id_var),
            window_handle=variant_to_int(window_handle_var),
        )
        
        # Get children
        if current_depth < max_depth - 1:
            try:
                walker = self.automation.ControlViewWalker
                child = walker.GetFirstChildElement(uia_element)
                while child:
                    element.children.append(self._element_to_element(child, max_depth, current_depth + 1))
                    child = walker.GetNextSiblingElement(child)
            except Exception:
                pass
        
        return element
    
    def _find_focused_element(self, root: uia.IUIAutomationElement) -> uia.IUIAutomationElement | None:
        """Find the element with keyboard focus."""
        try:
            true_condition = self.automation.CreateTrueCondition()
            focused = root.FindFirst(0x4, true_condition)  # TreeScope_Descendants = 0x4
            if focused:
                focus_var = self._get_property(focused, UIA_HasKeyboardFocusPropertyId)
                if variant_to_bool(focus_var):
                    return focused
        except Exception:
            pass
        return None
    
    def _get_active_window(self) -> uia.IUIAutomationElement | None:
        """Get the active (foreground) window."""
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if hwnd:
                element = self.automation.ElementFromHandle(hwnd)
                if element:
                    return element
        except Exception:
            pass
        return None
    
    def _get_window_title(self, element: uia.IUIAutomationElement) -> str:
        """Get window title from element."""
        name_var = self._get_property(element, UIA_NamePropertyId)
        return variant_to_str(name_var)
    
    def observe(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        """Perform a full desktop observation.
        
        Args:
            config: Optional observation configuration with keys:
                - max_depth: Maximum tree depth (default: 3)
                - include_offscreen: Include offscreen elements (default: False)
                - max_elements: Maximum elements to return (default: 500)
        
        Returns:
            Observation dict with screen, elements, snapshot, focused_title
        """
        if config is None:
            config = {}
        
        max_depth = config.get("max_depth", self.config.get("max_depth", 3))
        include_offscreen = config.get("include_offscreen", self.config.get("include_offscreen", False))
        max_elements = config.get("max_elements", self.config.get("max_elements", 500))
        
        # Get screen size
        user32 = ctypes.windll.user32
        screen_width = user32.GetSystemMetrics(0)
        screen_height = user32.GetSystemMetrics(1)
        
        # Get root element
        root = self._get_root_element()
        
        # Get focused element
        focused_uia = self._find_focused_element(root)
        focused_element = None
        if focused_uia:
            focused_element = self._element_to_element(focused_uia, max_depth=1)
        
        # Get active window
        active_window_uia = self._get_active_window()
        active_window = None
        focused_title = ""
        if active_window_uia:
            active_window = self._element_to_element(active_window_uia, max_depth=2)
            focused_title = self._get_window_title(active_window_uia)
            self._focused_title_cache = focused_title
        else:
            focused_title = self._focused_title_cache
        
        # Get root elements (top-level windows)
        root_elements = []
        try:
            walker = self.automation.ControlViewWalker
            child = walker.GetFirstChildElement(root)
            count = 0
            while child and count < max_elements:
                elem = self._element_to_element(child, max_depth)
                if include_offscreen or not elem.is_offscreen:
                    root_elements.append(elem)
                    count += 1
                child = walker.GetNextSiblingElement(child)
        except Exception:
            pass
        
        # Build observation
        observation = Observation(
            screen_width=screen_width,
            screen_height=screen_height,
            focused_element=focused_element,
            root_elements=root_elements,
            active_window=active_window,
            focused_title=focused_title,
        )
        
        self._last_observation = observation
        
        return {
            "screen": {"width": screen_width, "height": screen_height},
            "elements": [e.to_dict() for e in root_elements],
            "snapshot": observation.to_dict(),
            "focused_title": focused_title,
        }
    
    def observe_screen(self) -> dict[str, int]:
        """Get just the screen dimensions."""
        user32 = ctypes.windll.user32
        return {"width": user32.GetSystemMetrics(0), "height": user32.GetSystemMetrics(1)}
    
    def last_observation_snapshot(self) -> dict[str, Any] | None:
        """Get the last full observation snapshot."""
        if self._last_observation:
            return self._last_observation.to_dict()
        return None
    
    def get_focused_title(self) -> str:
        """Get the title of the currently focused window."""
        return self._focused_title_cache
    
    def configure_observation(self, **kwargs) -> None:
        """Update observation configuration."""
        self.config.update(kwargs)
    
    # =============================================================================
    # Desktop action methods
    # =============================================================================
    
    def click(self, x: int, y: int, hwnd: int = 0) -> dict[str, Any]:
        """Click at coordinates. If hwnd provided, click in that window."""
        user32 = ctypes.windll.user32
        if hwnd:
            # Click in specific window
            lparam = (y << 16) | (x & 0xFFFF)
            user32.PostMessageW(hwnd, 0x0201, 0, lparam)  # WM_LBUTTONDOWN
            user32.PostMessageW(hwnd, 0x0202, 0, lparam)  # WM_LBUTTONUP
        else:
            # Global click
            user32.SetCursorPos(x, y)
            user32.mouse_event(0x0002, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
            user32.mouse_event(0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP
        return {"ok": True, "action": "click", "x": x, "y": y, "hwnd": hwnd}
    
    def type_text(self, text: str) -> dict[str, Any]:
        """Type text into focused element."""
        user32 = ctypes.windll.user32
        for char in text:
            vk = user32.VkKeyScanW(ord(char))
            if vk == -1:
                continue
            vk_code = vk & 0xFF
            shift = (vk >> 8) & 0xFF
            if shift:
                user32.keybd_event(0x10, 0, 0, 0)  # VK_SHIFT down
            user32.keybd_event(vk_code, 0, 0, 0)  # key down
            user32.keybd_event(vk_code, 0, 2, 0)  # key up
            if shift:
                user32.keybd_event(0x10, 0, 2, 0)  # VK_SHIFT up
            time.sleep(0.01)
        return {"ok": True, "action": "type_text", "text": text}
    
    def press_key(self, key: str) -> dict[str, Any]:
        """Press a single key (e.g., 'enter', 'tab', 'escape')."""
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
        user32 = ctypes.windll.user32
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, 2, 0)
        return {"ok": True, "action": "press_key", "key": key}
    
    def hotkey(self, keys: str) -> dict[str, Any]:
        """Press key combination (e.g., 'ctrl+c', 'alt+tab', 'ctrl+shift+esc')."""
        key_map = {
            "ctrl": 0x11, "control": 0x11,
            "alt": 0x12,
            "shift": 0x10,
            "win": 0x5B, "windows": 0x5B,
            "enter": 0x0D, "tab": 0x09, "escape": 0x1B, "space": 0x20,
            "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
            "c": 0x43, "v": 0x56, "x": 0x58, "z": 0x5A,
            "a": 0x41, "s": 0x53, "f": 0x46, "n": 0x4E,
            "o": 0x4F, "p": 0x50, "w": 0x57,
        }
        parts = [k.strip().lower() for k in keys.split("+")]
        vks = []
        for k in parts:
            vk = key_map.get(k)
            if vk is None:
                return {"ok": False, "action": "hotkey", "error": f"unknown key in combination: {k}"}
            vks.append(vk)
        
        user32 = ctypes.windll.user32
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
    
    def scroll(self, x: int, y: int, amount: int, hwnd: int = 0) -> dict[str, Any]:
        """Scroll at coordinates. amount > 0 = up, < 0 = down."""
        user32 = ctypes.windll.user32
        if hwnd:
            lparam = (y << 16) | (x & 0xFFFF)
            user32.PostMessageW(hwnd, 0x020A, amount << 16, lparam)  # WM_MOUSEWHEEL
        else:
            user32.SetCursorPos(x, y)
            user32.mouse_event(0x0800, 0, 0, amount * 120, 0)  # MOUSEEVENTF_WHEEL
        return {"ok": True, "action": "scroll", "x": x, "y": y, "amount": amount, "hwnd": hwnd}
    
    def focus_window(self, target: str) -> dict[str, Any]:
        """Focus window by token (W1), title substring, or hwnd."""
        user32 = ctypes.windll.user32
        hwnd = 0
        
        if target.startswith("hwnd:"):
            try:
                hwnd = int(target[5:])
            except ValueError:
                return {"ok": False, "action": "focus_window", "error": "invalid hwnd format"}
        elif target.startswith("W"):
            # Window token - would need window tracking
            return {"ok": False, "action": "focus_window", "error": "window tokens not yet implemented"}
        else:
            # Find by title substring
            def enum_windows(hwnd, _):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        if target.lower() in buf.value.lower():
                            enum_windows.hwnd = hwnd
                            return False
                return True
            enum_windows.hwnd = 0
            user32.EnumWindows(enum_windows, 0)
            hwnd = enum_windows.hwnd
        
        if hwnd:
            user32.SetForegroundWindow(hwnd)
            return {"ok": True, "action": "focus_window", "target": target, "hwnd": hwnd}
        return {"ok": False, "action": "focus_window", "error": f"window not found: {target}"}
    
    def open_url(self, browser: str = "chrome", url: str = "") -> dict[str, Any]:
        """Open URL in browser."""
        import subprocess
        browser_paths = {
            "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "chrome": r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
        }
        exe = browser_paths.get(browser.lower())
        if not exe:
            # Try via start
            subprocess.Popen(["start", "", url], shell=True)
            return {"ok": True, "action": "open_url", "browser": "default", "url": url}
        subprocess.Popen([exe, url])
        return {"ok": True, "action": "open_url", "browser": browser, "url": url}


# Global desktop instance
_desktop_instance: Desktop | None = None


def get_desktop(config: dict[str, Any] | None = None) -> Desktop:
    """Get or create the global desktop instance."""
    global _desktop_instance
    if _desktop_instance is None:
        _desktop_instance = Desktop(config)
    return _desktop_instance


def observe(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Convenience function for desktop observation."""
    return get_desktop(config).observe(config)


def observe_screen() -> dict[str, int]:
    """Convenience function for screen dimensions."""
    return get_desktop().observe_screen()


def last_observation_snapshot() -> dict[str, Any] | None:
    """Convenience function for last observation snapshot."""
    return get_desktop().last_observation_snapshot()


def get_focused_title() -> str:
    """Convenience function for focused window title."""
    return get_desktop().get_focused_title()


def configure_observation(**kwargs) -> None:
    """Convenience function to configure observation."""
    get_desktop().configure_observation(**kwargs)