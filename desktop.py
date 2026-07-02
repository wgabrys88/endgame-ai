"""Desktop observation for Windows 11 using UIA COM via comtypes.gen.UIAutomationClient.

Real Windows desktop observation with Element types, hover probing,
window tokens, a screen-rooted tree, and configurable observation.
"""
from __future__ import annotations

import ctypes
import importlib
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import Any

import comtypes
import comtypes.client


def _load_uia_module() -> Any:
    """Load/regenerate the UIAutomation comtypes wrapper when the typelib changes."""
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

# Initialize COM
comtypes.CoInitialize()


# =============================================================================
# Control type name mapping (from UIAutomationClient)
# =============================================================================

def _uia_const(name: str, default: int) -> int:
    try:
        return int(getattr(uia, name))
    except Exception:
        return default


UIA_ButtonControlTypeId = _uia_const("UIA_ButtonControlTypeId", 50000)
UIA_CalendarControlTypeId = _uia_const("UIA_CalendarControlTypeId", 50001)
UIA_CheckBoxControlTypeId = _uia_const("UIA_CheckBoxControlTypeId", 50002)
UIA_ComboBoxControlTypeId = _uia_const("UIA_ComboBoxControlTypeId", 50003)
UIA_EditControlTypeId = _uia_const("UIA_EditControlTypeId", 50004)
UIA_HyperlinkControlTypeId = _uia_const("UIA_HyperlinkControlTypeId", 50005)
UIA_ImageControlTypeId = _uia_const("UIA_ImageControlTypeId", 50006)
UIA_ListItemControlTypeId = _uia_const("UIA_ListItemControlTypeId", 50007)
UIA_ListControlTypeId = _uia_const("UIA_ListControlTypeId", 50008)
UIA_MenuControlTypeId = _uia_const("UIA_MenuControlTypeId", 50009)
UIA_MenuBarControlTypeId = _uia_const("UIA_MenuBarControlTypeId", 50010)
UIA_MenuItemControlTypeId = _uia_const("UIA_MenuItemControlTypeId", 50011)
UIA_ProgressBarControlTypeId = _uia_const("UIA_ProgressBarControlTypeId", 50012)
UIA_RadioButtonControlTypeId = _uia_const("UIA_RadioButtonControlTypeId", 50013)
UIA_ScrollBarControlTypeId = _uia_const("UIA_ScrollBarControlTypeId", 50014)
UIA_SliderControlTypeId = _uia_const("UIA_SliderControlTypeId", 50015)
UIA_SpinnerControlTypeId = _uia_const("UIA_SpinnerControlTypeId", 50016)
UIA_StatusBarControlTypeId = _uia_const("UIA_StatusBarControlTypeId", 50017)
UIA_TabControlTypeId = _uia_const("UIA_TabControlTypeId", 50018)
UIA_TabItemControlTypeId = _uia_const("UIA_TabItemControlTypeId", 50019)
UIA_TextControlTypeId = _uia_const("UIA_TextControlTypeId", 50020)
UIA_ToolBarControlTypeId = _uia_const("UIA_ToolBarControlTypeId", 50021)
UIA_ToolTipControlTypeId = _uia_const("UIA_ToolTipControlTypeId", 50022)
UIA_TreeControlTypeId = _uia_const("UIA_TreeControlTypeId", 50023)
UIA_TreeItemControlTypeId = _uia_const("UIA_TreeItemControlTypeId", 50024)
UIA_CustomControlTypeId = _uia_const("UIA_CustomControlTypeId", 50025)
UIA_GroupControlTypeId = _uia_const("UIA_GroupControlTypeId", 50026)
UIA_ThumbControlTypeId = _uia_const("UIA_ThumbControlTypeId", 50027)
UIA_DataGridControlTypeId = _uia_const("UIA_DataGridControlTypeId", 50028)
UIA_DataItemControlTypeId = _uia_const("UIA_DataItemControlTypeId", 50029)
UIA_DocumentControlTypeId = _uia_const("UIA_DocumentControlTypeId", 50030)
UIA_SplitButtonControlTypeId = _uia_const("UIA_SplitButtonControlTypeId", 50031)
UIA_WindowControlTypeId = _uia_const("UIA_WindowControlTypeId", 50032)
UIA_PaneControlTypeId = _uia_const("UIA_PaneControlTypeId", 50033)
UIA_HeaderControlTypeId = _uia_const("UIA_HeaderControlTypeId", 50034)
UIA_HeaderItemControlTypeId = _uia_const("UIA_HeaderItemControlTypeId", 50035)
UIA_TableControlTypeId = _uia_const("UIA_TableControlTypeId", 50036)
UIA_TitleBarControlTypeId = _uia_const("UIA_TitleBarControlTypeId", 50037)
UIA_SeparatorControlTypeId = _uia_const("UIA_SeparatorControlTypeId", 50038)

CONTROL_TYPE_NAMES: dict[int, str] = {
    UIA_ButtonControlTypeId: "Button",
    UIA_CalendarControlTypeId: "Calendar",
    UIA_CheckBoxControlTypeId: "CheckBox",
    UIA_ComboBoxControlTypeId: "ComboBox",
    UIA_EditControlTypeId: "Edit",
    UIA_HyperlinkControlTypeId: "Hyperlink",
    UIA_ImageControlTypeId: "Image",
    UIA_ListItemControlTypeId: "ListItem",
    UIA_ListControlTypeId: "List",
    UIA_MenuControlTypeId: "Menu",
    UIA_MenuBarControlTypeId: "MenuBar",
    UIA_MenuItemControlTypeId: "MenuItem",
    UIA_ProgressBarControlTypeId: "ProgressBar",
    UIA_RadioButtonControlTypeId: "RadioButton",
    UIA_ScrollBarControlTypeId: "ScrollBar",
    UIA_SliderControlTypeId: "Slider",
    UIA_SpinnerControlTypeId: "Spinner",
    UIA_StatusBarControlTypeId: "StatusBar",
    UIA_TabControlTypeId: "Tab",
    UIA_TabItemControlTypeId: "TabItem",
    UIA_TextControlTypeId: "Text",
    UIA_ToolBarControlTypeId: "ToolBar",
    UIA_ToolTipControlTypeId: "ToolTip",
    UIA_TreeControlTypeId: "Tree",
    UIA_TreeItemControlTypeId: "TreeItem",
    UIA_CustomControlTypeId: "Custom",
    UIA_GroupControlTypeId: "Group",
    UIA_ThumbControlTypeId: "Thumb",
    UIA_DataGridControlTypeId: "DataGrid",
    UIA_DataItemControlTypeId: "DataItem",
    UIA_DocumentControlTypeId: "Document",
    UIA_SplitButtonControlTypeId: "SplitButton",
    UIA_WindowControlTypeId: "Window",
    UIA_PaneControlTypeId: "Pane",
    UIA_HeaderControlTypeId: "Header",
    UIA_HeaderItemControlTypeId: "HeaderItem",
    UIA_TableControlTypeId: "Table",
    UIA_TitleBarControlTypeId: "TitleBar",
    UIA_SeparatorControlTypeId: "Separator",
}

INTERACTIVE_CONTROL_TYPES = {
    UIA_ButtonControlTypeId,
    UIA_CalendarControlTypeId,
    UIA_CheckBoxControlTypeId,
    UIA_ComboBoxControlTypeId,
    UIA_EditControlTypeId,
    UIA_HyperlinkControlTypeId,
    UIA_ListItemControlTypeId,
    UIA_ListControlTypeId,
    UIA_MenuItemControlTypeId,
    UIA_RadioButtonControlTypeId,
    UIA_ScrollBarControlTypeId,
    UIA_SliderControlTypeId,
    UIA_SpinnerControlTypeId,
    UIA_TabControlTypeId,
    UIA_TabItemControlTypeId,
    UIA_TreeControlTypeId,
    UIA_TreeItemControlTypeId,
    UIA_DataGridControlTypeId,
    UIA_DataItemControlTypeId,
    UIA_DocumentControlTypeId,
    UIA_SplitButtonControlTypeId,
}


def control_type_name(control_type_id: int) -> str:
    return CONTROL_TYPE_NAMES.get(control_type_id, f"Unknown({control_type_id})")


# =============================================================================
# Property IDs (from UIAutomationClient)
# =============================================================================

UIA_RuntimeIdPropertyId = _uia_const("UIA_RuntimeIdPropertyId", 30000)
UIA_BoundingRectanglePropertyId = _uia_const("UIA_BoundingRectanglePropertyId", 30001)
UIA_ProcessIdPropertyId = _uia_const("UIA_ProcessIdPropertyId", 30002)
UIA_ControlTypePropertyId = _uia_const("UIA_ControlTypePropertyId", 30003)
UIA_LocalizedControlTypePropertyId = _uia_const("UIA_LocalizedControlTypePropertyId", 30004)
UIA_NamePropertyId = _uia_const("UIA_NamePropertyId", 30005)
UIA_HasKeyboardFocusPropertyId = _uia_const("UIA_HasKeyboardFocusPropertyId", 30008)
UIA_IsKeyboardFocusablePropertyId = _uia_const("UIA_IsKeyboardFocusablePropertyId", 30009)
UIA_IsEnabledPropertyId = _uia_const("UIA_IsEnabledPropertyId", 30010)
UIA_AutomationIdPropertyId = _uia_const("UIA_AutomationIdPropertyId", 30011)
UIA_ClassNamePropertyId = _uia_const("UIA_ClassNamePropertyId", 30012)
UIA_NativeWindowHandlePropertyId = _uia_const("UIA_NativeWindowHandlePropertyId", 30020)
UIA_IsOffscreenPropertyId = _uia_const("UIA_IsOffscreenPropertyId", 30022)
UIA_FrameworkIdPropertyId = _uia_const("UIA_FrameworkIdPropertyId", 30024)


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
        val = variant.value if hasattr(variant, "value") else variant
        if val is None:
            return rect
        if all(hasattr(val, attr) for attr in ("left", "top", "right", "bottom")):
            return Rect(int(val.left), int(val.top), int(val.right), int(val.bottom))
        if all(hasattr(val, attr) for attr in ("Left", "Top", "Right", "Bottom")):
            return Rect(int(val.Left), int(val.Top), int(val.Right), int(val.Bottom))
        if hasattr(val, "__iter__"):
            arr = list(val)
            if len(arr) >= 4:
                left, top, third, fourth = map(int, arr[:4])
                right = third if third > left else left + third
                bottom = fourth if fourth > top else top + fourth
                return Rect(left=left, top=top, right=right, bottom=bottom)
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
        self._last_desktop_tree: dict[str, Any] | None = None
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
    
    def _element_to_element(self, uia_element: uia.IUIAutomationElement, max_depth: int = 1, current_depth: int = 0) -> Element:
        """Convert UIA element to our Element dataclass."""
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
        
        return Element(
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
    
    # =============================================================================
    # Hover probing / mouse scanning
    # =============================================================================
    
    def _probe_point(self, x: int, y: int) -> uia.IUIAutomationElement | None:
        """Get element at screen coordinates via ElementFromPoint."""
        try:
            # ElementFromPoint takes a tagPOINT struct
            from ctypes import wintypes
            pt = wintypes.POINT(x, y)
            return self.automation.ElementFromPoint(pt)
        except Exception:
            return None
    
    def hover_scan(self, config: dict[str, Any] | None = None) -> list[Element]:
        """Perform hover scan across screen to discover interactive elements.
        
        Args:
            config: {
                "mode": "cursor_hover", # cursor_hover moves the real pointer, point_probe does not
                "step_px": 40,           # grid step in pixels
                "delay_ms": 1,           # delay between probes
                "target_window_only": True,  # only scan foreground window
                "min_size_px": 10,       # minimum element size
                "max_elements": 100,     # max elements to return
            }
        """
        if config is None:
            config = {}
        
        mode = str(config.get("mode", self.config.get("hover_scan_mode", "point_probe")) or "point_probe")
        restore_cursor = bool(config.get("restore_cursor", self.config.get("hover_scan_restore_cursor", True)))
        step_px = config.get("step_px", self.config.get("hover_scan_step_px", 40))
        delay_ms = config.get("delay_ms", self.config.get("hover_scan_delay_ms", 1))
        target_window_only = config.get("target_window_only", self.config.get("hover_scan_target_window_only", True))
        min_size = config.get("min_size_px", self.config.get("hover_scan_min_size_px", 10))
        max_elements = config.get("max_elements", self.config.get("hover_scan_max_elements", 100))
        
        user32 = ctypes.windll.user32
        screen_width = user32.GetSystemMetrics(0)
        screen_height = user32.GetSystemMetrics(1)
        
        # Get target window rect if specified
        target_rect = None
        if target_window_only:
            active_uia = self._get_active_window()
            if active_uia:
                rect_var = self._get_property(active_uia, UIA_BoundingRectanglePropertyId)
                target_rect = variant_to_rect(rect_var)
        
        elements_found: dict[str, Element] = {}  # dedup by runtime_id
        scanned = 0
        
        if target_rect and target_rect.width > 0 and target_rect.height > 0:
            x_range = range(target_rect.left, target_rect.right, step_px)
            y_range = range(target_rect.top, target_rect.bottom, step_px)
        else:
            x_range = range(0, screen_width, step_px)
            y_range = range(0, screen_height, step_px)
        
        saved_cursor = wintypes.POINT()
        cursor_saved = False
        if mode == "cursor_hover" and restore_cursor:
            try:
                cursor_saved = bool(user32.GetCursorPos(ctypes.byref(saved_cursor)))
            except Exception:
                cursor_saved = False

        try:
            for y in y_range:
                for x in x_range:
                    if len(elements_found) >= max_elements:
                        break

                    if mode == "cursor_hover":
                        try:
                            user32.SetCursorPos(int(x), int(y))
                            if delay_ms > 0:
                                time.sleep(delay_ms / 1000.0)
                        except Exception:
                            pass

                    uia_elem = self._probe_point(x, y)
                    if not uia_elem:
                        continue

                    # Get rect to filter by size
                    rect_var = self._get_property(uia_elem, UIA_BoundingRectanglePropertyId)
                    rect = variant_to_rect(rect_var)

                    if rect.width < min_size or rect.height < min_size:
                        continue

                    # Convert to our Element
                    elem = self._element_to_element(uia_elem, max_depth=1)

                    # Dedup by runtime_id
                    rid_key = ",".join(map(str, elem.runtime_id)) if elem.runtime_id else f"{elem.window_handle}:{elem.rect.left}:{elem.rect.top}"
                    if rid_key not in elements_found:
                        elements_found[rid_key] = elem

                    scanned += 1
                    if mode != "cursor_hover" and delay_ms > 0:
                        time.sleep(delay_ms / 1000.0)
                if len(elements_found) >= max_elements:
                    break
        finally:
            if mode == "cursor_hover" and restore_cursor and cursor_saved:
                try:
                    user32.SetCursorPos(saved_cursor.x, saved_cursor.y)
                except Exception:
                    pass
        
        return list(elements_found.values())
    
    def _find_focused_element(self) -> uia.IUIAutomationElement | None:
        """Find the element with keyboard focus."""
        try:
            return self.automation.GetFocusedElement()
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
        """Perform a full desktop observation using hover_scan as primary method.
        
        Args:
            config: Optional observation configuration with keys:
                - hover_scan: dict with hover_scan config (step_px, delay_ms, target_window_only, min_size_px, max_elements)
        
        Returns:
            Fresh observation dict with desktop_tree, screen_text, focused_title, and scan metadata.
        """
        if config is None:
            config = {}
        
        hover_config = config.get("hover_scan", self.config.get("hover_scan", {}))
        
        # Get screen size
        user32 = ctypes.windll.user32
        screen_width = user32.GetSystemMetrics(0)
        screen_height = user32.GetSystemMetrics(1)
        
        # Get active window
        active_window_uia = self._get_active_window()
        focused_title = ""
        if active_window_uia:
            focused_title = self._get_window_title(active_window_uia)
            self._focused_title_cache = focused_title
        else:
            focused_title = self._focused_title_cache
        
        observed_at = time.time()

        # PRIMARY: Hover scan - scan whole screen if desktop/taskbar is active, else target window only
        is_desktop = focused_title in ("Program Manager", "Desktop", "Taskbar", "") or not active_window_uia
        target_window_only = hover_config.get("target_window_only", True) and not is_desktop
        
        hover_config_adjusted = dict(hover_config)
        hover_config_adjusted["target_window_only"] = target_window_only
        # Use larger step for full-screen scan to avoid excessive probes
        if not target_window_only:
            hover_config_adjusted["step_px"] = hover_config.get("full_screen_step_px", 60)
        
        hover_elements = self.hover_scan(hover_config_adjusted)
        filtered_elements = self.filter_elements(hover_elements)
        windows = self.get_window_tokens()
        desktop_tree = self.build_desktop_tree(
            {"width": screen_width, "height": screen_height},
            filtered_elements,
            windows,
            focused_title,
            observed_at=observed_at,
            scan_config=hover_config_adjusted,
            raw_element_count=len(hover_elements),
        )
        
        # Format SCREEN text for LLM
        screen_text = self.format_screen_text(
            {"width": screen_width, "height": screen_height},
            filtered_elements,
            windows,
            focused_title,
            desktop_tree,
        )
        
        self._last_desktop_tree = desktop_tree
        
        return {
            "observed_at": observed_at,
            "fresh_scan": True,
            "desktop_tree": desktop_tree,
            "screen_text": screen_text,
            "focused_title": focused_title,
        }
    
    def observe_screen(self) -> dict[str, int]:
        """Get just the screen dimensions."""
        user32 = ctypes.windll.user32
        return {"width": user32.GetSystemMetrics(0), "height": user32.GetSystemMetrics(1)}
    
    def last_desktop_tree(self) -> dict[str, Any] | None:
        """Get the last fresh desktop tree produced by observe()."""
        return self._last_desktop_tree
    
    def get_focused_title(self) -> str:
        """Get the title of the currently focused window."""
        return self._focused_title_cache
    
    def configure_observation(self, **kwargs) -> None:
        """Update observation configuration."""
        self.config.update(kwargs)
    
    # =============================================================================
    # Observation filtering and formatting
    # =============================================================================
    
    def _stable_id(self, element: Element) -> str:
        """Generate stable element ID from runtime_id or position."""
        if element.runtime_id:
            return "e_" + "_".join(map(str, element.runtime_id))
        return f"e_{element.window_handle}_{element.rect.left}_{element.rect.top}"
    
    def classify_action(self, control_type_id: int) -> str:
        """Map control type to default action."""
        if control_type_id in {
            UIA_ButtonControlTypeId,
            UIA_CalendarControlTypeId,
            UIA_CheckBoxControlTypeId,
            UIA_HyperlinkControlTypeId,
            UIA_ListItemControlTypeId,
            UIA_MenuItemControlTypeId,
            UIA_RadioButtonControlTypeId,
            UIA_TabControlTypeId,
            UIA_TabItemControlTypeId,
            UIA_TreeItemControlTypeId,
            UIA_DataItemControlTypeId,
            UIA_SplitButtonControlTypeId,
        }:
            return "click"
        if control_type_id in {UIA_EditControlTypeId, UIA_ComboBoxControlTypeId, UIA_SpinnerControlTypeId}:
            return "write"
        if control_type_id in {
            UIA_ListControlTypeId,
            UIA_ScrollBarControlTypeId,
            UIA_SliderControlTypeId,
            UIA_TreeControlTypeId,
            UIA_DataGridControlTypeId,
            UIA_DocumentControlTypeId,
        }:
            return "scroll"
        return ""
    
    def filter_elements(self, elements: list[Element]) -> dict[str, dict[str, Any]]:
        """Filter to actionable elements, return dict keyed by stable element_id."""
        result = {}
        for el in elements:
            # Skip zero-size rects
            if el.rect.width <= 0 or el.rect.height <= 0:
                continue
            # Skip offscreen or disabled
            if el.is_offscreen or not el.is_enabled:
                continue
            # Must be interactive type
            if el.control_type_id not in INTERACTIVE_CONTROL_TYPES:
                continue
            action = self.classify_action(el.control_type_id)
            if not action:
                continue
            
            elem_id = self._stable_id(el)
            px = el.rect.left + el.rect.width // 2
            py = el.rect.top + el.rect.height // 2
            
            result[elem_id] = {
                "id": elem_id,
                "name": el.name,
                "role": el.control_type,
                "action": action,
                "px": px,
                "py": py,
                "hwnd": el.window_handle,
                "rect": el.rect.to_dict(),
                "enabled": el.is_enabled,
                "focused": el.has_focus,
                "automation_id": el.automation_id,
                "class_name": el.class_name,
                "runtime_id": el.runtime_id,
            }
        return result

    def _contains_point(self, rect: dict[str, int], x: int, y: int) -> bool:
        return int(rect.get("left", 0)) <= x <= int(rect.get("right", 0)) and int(rect.get("top", 0)) <= y <= int(rect.get("bottom", 0))

    def _rect_area(self, rect: dict[str, int]) -> int:
        return max(0, int(rect.get("right", 0)) - int(rect.get("left", 0))) * max(0, int(rect.get("bottom", 0)) - int(rect.get("top", 0)))

    def build_desktop_tree(
        self,
        screen: dict[str, int],
        elements: dict[str, dict[str, Any]],
        windows: list[dict[str, Any]],
        focused_title: str,
        *,
        observed_at: float,
        scan_config: dict[str, Any],
        raw_element_count: int,
    ) -> dict[str, Any]:
        """Build a fresh screen-rooted desktop hierarchy from window tokens and hover scan hits."""
        root_rect = {"left": 0, "top": 0, "right": int(screen.get("width", 0)), "bottom": int(screen.get("height", 0))}
        root = {
            "id": "W0",
            "role": "Screen",
            "name": "Screen",
            "title": "Desktop",
            "rect": root_rect,
            "focused": False,
            "fresh_scan": True,
            "observed_at": observed_at,
            "scan": {
                "method": "hover_scan",
                "mode": str(scan_config.get("mode", "point_probe")),
                "target_window_only": bool(scan_config.get("target_window_only", False)),
                "step_px": int(scan_config.get("step_px", 0) or 0),
                "raw_element_count": raw_element_count,
                "actionable_element_count": len(elements),
            },
            "children": [],
        }
        node_index: dict[str, dict[str, Any]] = {"W0": {k: v for k, v in root.items() if k != "children"}}
        window_nodes: dict[str, dict[str, Any]] = {}
        hwnd_to_window_id: dict[int, str] = {}
        focused_window_id = ""

        for window in windows:
            token = str(window.get("token") or "")
            if not token or token == "W0":
                continue
            title = str(window.get("title") or window.get("name") or "")
            node = {
                "id": token,
                "parent_id": "W0",
                "role": "Window",
                "name": title,
                "title": title,
                "hwnd": int(window.get("hwnd") or 0),
                "process_id": int(window.get("process_id") or 0),
                "class_name": str(window.get("class_name") or ""),
                "rect": window.get("rect", {}),
                "focused": bool(focused_title and title == focused_title),
                "source": "win32_enum_windows",
                "children": [],
            }
            if node["focused"]:
                focused_window_id = token
            window_nodes[token] = node
            hwnd_to_window_id[node["hwnd"]] = token
            root["children"].append(node)
            node_index[token] = {k: v for k, v in node.items() if k != "children"}

        direct_elements: list[dict[str, Any]] = []
        for element_id, element in elements.items():
            px = int(element.get("px") or 0)
            py = int(element.get("py") or 0)
            hwnd = int(element.get("hwnd") or 0)
            parent_id = hwnd_to_window_id.get(hwnd, "")
            if not parent_id:
                containing = [
                    node for node in window_nodes.values()
                    if self._contains_point(node.get("rect", {}), px, py)
                ]
                if containing:
                    containing.sort(key=lambda node: self._rect_area(node.get("rect", {})))
                    parent_id = str(containing[0]["id"])
            if not parent_id:
                parent_id = "W0"

            node = {
                "id": element_id,
                "parent_id": parent_id,
                "role": element.get("role", ""),
                "name": element.get("name", ""),
                "action": element.get("action", ""),
                "px": px,
                "py": py,
                "hwnd": hwnd,
                "rect": element.get("rect", {}),
                "enabled": bool(element.get("enabled", False)),
                "focused": bool(element.get("focused", False)),
                "automation_id": element.get("automation_id", ""),
                "class_name": element.get("class_name", ""),
                "runtime_id": element.get("runtime_id", []),
                "source": "hover_scan",
                "confidence": "point_hit",
                "children": [],
            }
            node_index[element_id] = {k: v for k, v in node.items() if k != "children"}
            if parent_id == "W0":
                direct_elements.append(node)
            else:
                window_nodes[parent_id]["children"].append(node)

        root["children"].extend(direct_elements)
        return {
            "id": "W0",
            "role": "Screen",
            "fresh_scan": True,
            "observed_at": observed_at,
            "focused_title": focused_title,
            "focused_window_id": focused_window_id,
            "root": root,
            "node_index": node_index,
            "window_count": len(window_nodes),
            "element_count": len(elements),
        }
    
    def get_window_tokens(self) -> list[dict[str, Any]]:
        """Get window tokens W1..Wn for visible top-level windows.
        
        Screen is Window 0 (the entire desktop), then W1..Wn are top-level windows.
        """
        user32 = ctypes.windll.user32
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        windows = [{
            "token": "W0",
            "name": "Screen",
            "title": "Desktop",
            "hwnd": 0,
            "rect": {"left": 0, "top": 0, "right": screen_w, "bottom": screen_h},
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
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return True
            if rect.right <= rect.left or rect.bottom <= rect.top:
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
    
    def format_screen_text(self, screen: dict, elements: dict, windows: list, focused_title: str, desktop_tree: dict[str, Any] | None = None) -> str:
        """Format SCREEN text for LLM context with hierarchy."""
        lines = []
        
        # Window hierarchy
        lines.append("DESKTOP TREE:")
        lines.append(f"  * [W0] Screen ({screen['width']}x{screen['height']}) fresh_scan=true")
        for w in windows:
            if w["token"] != "W0":
                rect = w["rect"]
                lines.append(f"    * [{w['token']}] Window '{w['title']}' @({rect['left']},{rect['top']},{rect['right']},{rect['bottom']}) hwnd={w['hwnd']} pid={w.get('process_id',0)}")
        
        lines.append(f"\nFOCUSED WINDOW: {focused_title or 'none'}")
        
        # Key actionable tree nodes
        lines.append(f"\nACTION NODES ({len(elements)} actionable):")
        for eid, el in elements.items():
            lines.append(f"  {eid}: {el['role']} '{el['name']}' @({el['px']},{el['py']}) hwnd={el['hwnd']} action={el['action']} enabled={el['enabled']} focused={el['focused']}")
        
        return "\n".join(lines)

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
    
    def hotkey(self, keys) -> dict[str, Any]:
        """Press key combination (e.g., 'ctrl+c', 'alt+tab', 'win+r' or ['ctrl', 'c'])."""
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
            "r": 0x52, "l": 0x4C, "d": 0x44,
        }
        # Accept both string "win+r" and list ["win", "r"]
        if isinstance(keys, list):
            parts = [k.strip().lower() for k in keys]
        else:
            parts = [k.strip().lower() for k in str(keys).split("+")]
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
            # Window token - look up in windows from last observation
            try:
                tree = self.last_desktop_tree() or {}
                node = (tree.get("node_index") or {}).get(target, {})
                hwnd = int(node.get("hwnd") or 0)
            except Exception:
                pass
            if not hwnd:
                return {"ok": False, "action": "focus_window", "error": f"window token not found: {target}"}
        else:
            # Find by title substring
            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
            found_hwnd = [0]
            
            def callback(hwnd, _):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        if target.lower() in buf.value.lower():
                            found_hwnd[0] = hwnd
                            return False
                return True
            
            cb = EnumWindowsProc(callback)
            user32.EnumWindows(cb, 0)
            hwnd = found_hwnd[0]
        
        if hwnd:
            user32.SetForegroundWindow(hwnd)
            return {"ok": True, "action": "focus_window", "target": target, "hwnd": hwnd}
        return {"ok": False, "action": "focus_window", "error": f"window not found: {target}"}
    
    def open_url(self, browser: str = "chrome", url: str = "") -> dict[str, Any]:
        """Open URL in browser."""
        import subprocess
        browser_paths = {
            "chrome": [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            ],
            "edge": [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"],
            "firefox": [r"C:\Program Files\Mozilla Firefox\firefox.exe"],
        }
        paths = browser_paths.get(browser.lower(), [])
        exe = None
        for p in paths:
            import os
            if os.path.exists(os.path.expandvars(p)):
                exe = os.path.expandvars(p)
                break
        if not exe:
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


def last_desktop_tree() -> dict[str, Any] | None:
    """Convenience function for last desktop tree."""
    return get_desktop().last_desktop_tree()


def get_focused_title() -> str:
    """Convenience function for focused window title."""
    return get_desktop().get_focused_title()


def configure_observation(**kwargs) -> None:
    """Convenience function to configure observation."""
    get_desktop().configure_observation(**kwargs)
