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
    
    # =============================================================================
    # Hover probing / mouse scanning
    # =============================================================================
    
    def _probe_point(self, x: int, y: int) -> uia.IUIAutomationElement | None:
        """Get element at screen coordinates via ElementFromPoint."""
        try:
            # ElementFromPoint takes a POINT struct (x, y as longlong)
            pt = (y << 32) | (x & 0xFFFFFFFF)
            return self.automation.ElementFromPoint(pt)
        except Exception:
            return None
    
    def hover_scan(self, config: dict[str, Any] | None = None) -> list[Element]:
        """Perform hover scan across screen to discover interactive elements.
        
        Args:
            config: {
                "step_px": 40,           # grid step in pixels
                "delay_ms": 1,           # delay between probes
                "target_window_only": True,  # only scan foreground window
                "min_size_px": 10,       # minimum element size
                "max_elements": 100,     # max elements to return
            }
        """
        if config is None:
            config = {}
        
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
        
        for y in y_range:
            for x in x_range:
                if len(elements_found) >= max_elements:
                    break
                
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
                if delay_ms > 0:
                    time.sleep(delay_ms / 1000.0)
            if len(elements_found) >= max_elements:
                break
        
        return list(elements_found.values())
    
    def dense_probe(self, region: Rect, config: dict[str, Any] | None = None) -> list[Element]:
        """Dense probe a specific region (smaller step)."""
        if config is None:
            config = {}
        config = dict(config)
        config["step_px"] = config.get("step_px", 24)
        config["target_window_only"] = False
        return self.hover_scan(config)
    
    def scroll_enrich(self, config: dict[str, Any] | None = None) -> list[Element]:
        """Scroll and re-probe to discover more elements."""
        if config is None:
            config = {}
        
        passes = config.get("passes", [-3, -2, 2, 3])  # scroll amounts
        all_elements: dict[str, Element] = {}
        
        for amount in passes:
            elements = self.hover_scan(config)
            for elem in elements:
                rid_key = ",".join(map(str, elem.runtime_id)) if elem.runtime_id else f"{elem.window_handle}:{elem.rect.left}:{elem.rect.top}"
                if rid_key not in all_elements:
                    all_elements[rid_key] = elem
            
            # Scroll
            user32 = ctypes.windll.user32
            user32.mouse_event(0x0800, 0, 0, amount * 120, 0)
            time.sleep(0.1)
        
        return list(all_elements.values())
    
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
        """Perform a full desktop observation using hover_scan as primary method.
        
        Args:
            config: Optional observation configuration with keys:
                - max_depth: Maximum tree depth (default: 3)
                - include_offscreen: Include offscreen elements (default: False)
                - max_elements: Maximum elements to return (default: 500)
                - hover_scan: dict with hover_scan config (step_px, delay_ms, target_window_only, min_size_px, max_elements)
        
        Returns:
            Observation dict with screen, elements (filtered dict), screen_text, focused_title, windows, snapshot
        """
        if config is None:
            config = {}
        
        max_depth = config.get("max_depth", self.config.get("max_depth", 3))
        include_offscreen = config.get("include_offscreen", self.config.get("include_offscreen", False))
        max_elements = config.get("max_elements", self.config.get("max_elements", 500))
        hover_config = config.get("hover_scan", self.config.get("hover_scan", {}))
        
        # Get screen size
        user32 = ctypes.windll.user32
        screen_width = user32.GetSystemMetrics(0)
        screen_height = user32.GetSystemMetrics(1)
        
        # Get root element for tree walk (for window enumeration)
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
        
        # Get root elements (top-level windows) for window tokens
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
        
        # PRIMARY: Hover scan on foreground window
        hover_elements = self.hover_scan(hover_config)
        
        # SECONDARY: Tree walk for window hierarchy (limited depth)
        tree_elements = []
        if hover_config.get("target_window_only", True) and active_window_uia:
            # Tree walk only the active window
            try:
                walker = self.automation.ControlViewWalker
                child = walker.GetFirstChildElement(active_window_uia)
                tree_count = 0
                while child and tree_count < 200:
                    elem = self._element_to_element(child, 2)
                    if include_offscreen or not elem.is_offscreen:
                        tree_elements.append(elem)
                        tree_count += 1
                    child = walker.GetNextSiblingElement(child)
            except Exception:
                pass
        else:
            # Full tree walk (fallback)
            tree_elements = root_elements
        
        # Merge: hover for positions, tree for hierarchy
        merged_elements = self._merge_elements(tree_elements, hover_elements)
        
        # Filter to actionable elements, keyed by stable ID
        filtered_elements = self.filter_elements(merged_elements)
        
        # Get window tokens
        windows = self.get_window_tokens(root_elements)
        
        # Format SCREEN text for LLM
        screen_text = self.format_screen_text(
            {"width": screen_width, "height": screen_height},
            filtered_elements,
            windows,
            focused_title
        )
        
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
            "elements": filtered_elements,  # dict keyed by element_id
            "screen_text": screen_text,
            "windows": windows,
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
    # Observation filtering and formatting
    # =============================================================================
    
    def _merge_elements(self, tree_elements: list[Element], hover_elements: list[Element]) -> list[Element]:
        """Merge tree elements (hierarchy) with hover elements (accurate positions)."""
        merged = []
        hover_by_rid = {}
        
        # Index hover elements by runtime_id
        for h in hover_elements:
            rid_key = ",".join(map(str, h.runtime_id)) if h.runtime_id else f"{h.window_handle}:{h.rect.left}:{h.rect.top}"
            hover_by_rid[rid_key] = h
        
        # Merge: use tree element but update position from hover if match
        for t in tree_elements:
            rid_key = ",".join(map(str, t.runtime_id)) if t.runtime_id else f"{t.window_handle}:{t.rect.left}:{t.rect.top}"
            if rid_key in hover_by_rid:
                h = hover_by_rid[rid_key]
                # Create merged element with tree hierarchy but hover position
                merged_elem = Element(
                    name=t.name,
                    control_type=t.control_type,
                    control_type_id=t.control_type_id,
                    automation_id=t.automation_id,
                    class_name=t.class_name,
                    process_id=t.process_id,
                    rect=h.rect,  # Use hover position (accurate)
                    is_enabled=t.is_enabled,
                    is_offscreen=h.is_offscreen,
                    has_focus=t.has_focus,
                    framework_id=t.framework_id,
                    runtime_id=t.runtime_id,
                    window_handle=t.window_handle,
                    children=t.children,
                )
                merged.append(merged_elem)
                del hover_by_rid[rid_key]
            else:
                merged.append(t)
        
        # Add remaining hover elements not in tree
        merged.extend(hover_by_rid.values())
        
        return merged
    
    def _stable_id(self, element: Element) -> str:
        """Generate stable element ID from runtime_id or position."""
        if element.runtime_id:
            return "e_" + "_".join(map(str, element.runtime_id))
        return f"e_{element.window_handle}_{element.rect.left}_{element.rect.top}"
    
    def classify_action(self, control_type_id: int) -> str:
        """Map control type to default action."""
        if control_type_id == 50000:  # Button
            return "click"
        if control_type_id in (50004, 50002):  # Edit, ComboBox
            return "write"
        if control_type_id in (50008, 50009, 50010, 50011, 50003):  # List, ListItem, Tree, TreeItem, ScrollBar
            return "scroll"
        if control_type_id in (50001, 50017):  # CheckBox, RadioButton
            return "click"
        if control_type_id == 50014:  # Slider
            return "scroll"
        if control_type_id == 50016:  # Hyperlink
            return "click"
        if control_type_id == 50018:  # TabItem
            return "click"
        if control_type_id == 50013:  # MenuItem
            return "click"
        if control_type_id == 50021:  # Spinner
            return "write"
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
            if el.control_type_id not in self.INTERACTIVE_CONTROL_TYPES:
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
    
    def get_window_tokens(self, root_elements: list[Element]) -> list[dict[str, Any]]:
        """Get window tokens W1..Wn for visible top-level windows.
        
        Screen is Window 0 (the entire desktop), then W1..Wn are top-level windows.
        """
        windows = []
        # Screen as Window 0
        user32 = ctypes.windll.user32
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        windows.append({
            "token": "W0",
            "name": "Screen",
            "title": "Desktop",
            "hwnd": 0,
            "rect": {"left": 0, "top": 0, "right": screen_w, "bottom": screen_h},
            "children": []
        })
        
        # Top-level windows as W1, W2...
        for i, el in enumerate(root_elements, 1):
            if el.rect.width > 0 and el.rect.height > 0 and not el.is_offscreen:
                windows.append({
                    "token": f"W{i}",
                    "name": el.control_type,
                    "title": el.name,
                    "hwnd": el.window_handle,
                    "rect": el.rect.to_dict(),
                    "process_id": el.process_id,
                    "class_name": el.class_name,
                })
        return windows
    
    def format_screen_text(self, screen: dict, elements: dict, windows: list, focused_title: str) -> str:
        """Format SCREEN text for LLM context with hierarchy."""
        lines = []
        
        # Window hierarchy
        lines.append("WINDOWS:")
        for w in windows:
            if w["token"] == "W0":
                lines.append(f"  * [W0] Screen ({screen['width']}x{screen['height']})")
            else:
                rect = w["rect"]
                lines.append(f"  * [{w['token']}] {w['title']} @({rect['left']},{rect['top']},{rect['right']},{rect['bottom']}) hwnd={w['hwnd']} pid={w.get('process_id',0)}")
        
        lines.append(f"\nFOCUSED WINDOW: {focused_title or 'none'}")
        
        # Key actionable elements
        lines.append(f"\nELEMENTS ({len(elements)} actionable):")
        for eid, el in list(elements.items())[:80]:
            lines.append(f"  {eid}: {el['role']} '{el['name'][:60]}' @({el['px']},{el['py']}) hwnd={el['hwnd']} action={el['action']} enabled={el['enabled']} focused={el['focused']}")
        
        if len(elements) > 80:
            lines.append(f"  ... and {len(elements) - 80} more elements")
        
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