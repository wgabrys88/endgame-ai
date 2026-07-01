"""Desktop observation for Windows 11 using UIA COM.

Real Windows desktop observation with Element/Observation types, hover probing,
window tokens, bounded tree, and configurable observation.
"""
from __future__ import annotations

import platform
import time
import ctypes
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import Any, Literal
from enum import IntEnum

import comtypes
import comtypes.client
from comtypes import GUID, IUnknown, COMMETHOD, HRESULT
from comtypes.automation import IDispatch, VARIANT, VT_EMPTY, VT_I4, VT_BSTR, VT_ARRAY, VT_VARIANT, VT_UI4
from comtypes.safearray import safearray_as_ndarray

# Initialize COM
comtypes.CoInitialize()

# Windows UIA constants
UIA_ElementNotFound = 0x80040201

# UIA Property IDs
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
UIA_WindowPatternId = 10009
UIA_LegacyIAccessiblePatternId = 10018
UIA_ValuePatternId = 10002
UIA_ExpandCollapsePatternId = 10005
UIA_TogglePatternId = 10006
UIA_SelectionItemPatternId = 10034
UIA_InvokePatternId = 10000
UIA_ScrollPatternId = 10004
UIA_TransformPatternId = 10025

# UIA Control Type IDs
UIA_WindowControlTypeId = 50032
UIA_PaneControlTypeId = 50033
UIA_ButtonControlTypeId = 50000
UIA_TextControlTypeId = 50020
UIA_EditControlTypeId = 50004
UIA_ListControlTypeId = 50008
UIA_ListItemControlTypeId = 50009
UIA_TreeControlTypeId = 50010
UIA_TreeItemControlTypeId = 50011
UIA_TabControlTypeId = 50017
UIA_TabItemControlTypeId = 50018
UIA_MenuControlTypeId = 50012
UIA_MenuItemControlTypeId = 50013
UIA_ToolBarControlTypeId = 50015
UIA_StatusBarControlTypeId = 50023
UIA_ScrollBarControlTypeId = 50003
UIA_SliderControlTypeId = 50014
UIA_ProgressBarControlTypeId = 50019
UIA_ImageControlTypeId = 50006
UIA_HyperlinkControlTypeId = 50016
UIA_CheckBoxControlTypeId = 50001
UIA_RadioButtonControlTypeId = 50017
UIA_ComboBoxControlTypeId = 50002
UIA_SpinnerControlTypeId = 50021
UIA_ToolTipControlTypeId = 50022
UIA_GroupControlTypeId = 50026
UIA_SeparatorControlTypeId = 50028
UIA_ThumbControlTypeId = 50027

# TreeScope
TreeScope_Element = 0x1
TreeScope_Children = 0x2
TreeScope_Descendants = 0x4
TreeScope_Parent = 0x8
TreeScope_Ancestors = 0x10
TreeScope_Subtree = 0x7

# CacheRequest flags
UiaCacheRequestOptions_None = 0

# UIA interface GUIDs
IID_IUIAutomation = GUID("{30cbe57d-d9d0-452a-ab13-7ac5ac4825ee}")
IID_IUIAutomationElement = GUID("{d22108aa-8ac5-49a5-837b-37bbb3d7591e}")
IID_IUIAutomationCondition = GUID("{352ffba8-0973-437c-a61f-f64cafd81df9}")
IID_IUIAutomationTreeWalker = GUID("{4042c624-389c-4a39-9c8d-9f1534729bc1}")
IID_IUIAutomationCacheRequest = GUID("{b32a92b5-bc25-4078-9c08-d7ee95c48e03}")

CLSID_CUIAutomation = GUID("{ff48dba4-60ef-4201-aa87-54103eef594e}")


class IUIAutomationElement(IUnknown):
    _iid_ = IID_IUIAutomationElement
    _methods_ = [
        COMMETHOD([], HRESULT, "GetCurrentPropertyValue",
                  (['in'], ctypes.c_int, 'propertyId'),
                  (['out', 'retval'], ctypes.POINTER(VARIANT), 'retVal')),
        COMMETHOD([], HRESULT, "GetCachedPropertyValue",
                  (['in'], ctypes.c_int, 'propertyId'),
                  (['out', 'retval'], ctypes.POINTER(VARIANT), 'retVal')),
        COMMETHOD([], HRESULT, "GetCurrentPatternAs",
                  (['in'], GUID, 'patternId'),
                  (['in'], GUIDispatch'], ctypes.POINTER(ctypes.c_void_p), 'retVal')),
        COMMETHOD([], HRESULT, "FindFirst",
                  (['in'], ctypes.c_int, 'scope'),
                  (['in'], ctypes.POINTER(IUnknown), 'condition'),
                  (['out', 'retval'], ctypes.POINTER(ctypes.POINTER(IUIAutomationElement)), 'retVal')),
        COMMETHOD([], HRESULT, "FindAll",
                  (['in'], ctypes.c_int, 'scope'),
                  (['in'], ctypes.POINTER(IUnknown), 'condition'),
                  (['out', 'retval'], ctypes.POINTER(ctypes.c_void_p), 'retVal')),
    ]


class IUIAutomationCondition(IUnknown):
    _iid_ = IID_IUIAutomationCondition
    _methods_ = []


class IUIAutomationTreeWalker(IUnknown):
    _iid_ = IID_IUIAutomationTreeWalker
    _methods_ = [
        COMMETHOD([], HRESULT, "GetParentElement",
                  (['in'], ctypes.POINTER(IUIAutomationElement), 'element'),
                  (['out', 'retval'], ctypes.POINTER(ctypes.POINTER(IUIAutomationElement)), 'retVal')),
        COMMETHOD([], HRESULT, "GetFirstChildElement",
                  (['in'], ctypes.POINTER(IUIAutomationElement), 'element'),
                  (['out', 'retval'], ctypes.POINTER(ctypes.POINTER(IUIAutomationElement)), 'retVal')),
        COMMETHOD([], HRESULT, "GetLastChildElement",
                  (['in'], ctypes.POINTER(IUIAutomationElement), 'element'),
                  (['out', 'retval'], ctypes.POINTER(ctypes.POINTER(IUIAutomationElement)), 'retVal')),
        COMMETHOD([], HRESULT, "GetNextSiblingElement",
                  (['in'], ctypes.POINTER(IUIAutomationElement), 'element'),
                  (['out', 'retval'], ctypes.POINTER(ctypes.POINTER(IUIAutomationElement)), 'retVal')),
        COMMETHOD([], HRESULT, "GetPreviousSiblingElement",
                  (['in'], ctypes.POINTER(IUIAutomationElement), 'element'),
                  (['out', 'retval'], ctypes.POINTER(ctypes.POINTER(IUIAutomationElement)), 'retVal')),
    ]


class IUIAutomationCacheRequest(IUnknown):
    _iid_ = IID_IUIAutomationCacheRequest
    _methods_ = [
        COMMETHOD([], HRESULT, "AddProperty",
                  (['in'], ctypes.c_int, 'propertyId')),
        COMMETHOD([], HRESULT, "AddPattern",
                  (['in'], ctypes.c_int, 'patternId')),
    ]


class IUIAutomation(IUnknown):
    _iid_ = IID_IUIAutomation
    _methods_ = [
        COMMETHOD([], HRESULT, "GetRootElement",
                  (['out', 'retval'], ctypes.POINTER(ctypes.POINTER(IUIAutomationElement)), 'retVal')),
        COMMETHOD([], HRESULT, "ElementFromHandle",
                  (['in'], wintypes.HWND, 'hwnd'),
                  (['out', 'retval'], ctypes.POINTER(ctypes.POINTER(IUIAutomationElement)), 'retVal')),
        COMMETHOD([], HRESULT, "ElementFromPoint",
                  (['in'], ctypes.c_longlong, 'pt'),
                  (['out', 'retval'], ctypes.POINTER(ctypes.POINTER(IUIAutomationElement)), 'retVal')),
        COMMETHOD([], HRESULT, "CreateCacheRequest",
                  (['out', 'retval'], ctypes.POINTER(ctypes.POINTER(IUIAutomationCacheRequest)), 'retVal')),
        COMMETHOD([], HRESULT, "CreateTrueCondition",
                  (['out', 'retval'], ctypes.POINTER(ctypes.POINTER(IUIAutomationCondition)), 'retVal')),
        COMMETHOD([], HRESULT, "CreatePropertyCondition",
                  (['in'], ctypes.c_int, 'propertyId'),
                  (['in'], VARIANT, 'value'),
                  (['out', 'retval'], ctypes.POINTER(ctypes.POINTER(IUIAutomationCondition)), 'retVal')),
        COMMETHOD([], HRESULT, "ControlViewWalker",
                  (['out', 'retval'], ctypes.POINTER(ctypes.POINTER(IUIAutomationTreeWalker)), 'retVal')),
        COMMETHOD([], HRESULT, "ContentViewWalker",
                  (['out', 'retval'], ctypes.POINTER(ctypes.POINTER(IUIAutomationTreeWalker)), 'retVal')),
    ]


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
# Control type name mapping
# =============================================================================


CONTROL_TYPE_NAMES: dict[int, str] = {
    UIA_WindowControlTypeId: "Window",
    UIA_PaneControlTypeId: "Pane",
    UIA_ButtonControlTypeId: "Button",
    UIA_TextControlTypeId: "Text",
    UIA_EditControlTypeId: "Edit",
    UIA_ListControlTypeId: "List",
    UIA_ListItemControlTypeId: "ListItem",
    UIA_TreeControlTypeId: "Tree",
    UIA_TreeItemControlTypeId: "TreeItem",
    UIA_TabControlTypeId: "Tab",
    UIA_TabItemControlTypeId: "TabItem",
    UIA_MenuControlTypeId: "Menu",
    UIA_MenuItemControlTypeId: "MenuItem",
    UIA_ToolBarControlTypeId: "ToolBar",
    UIA_StatusBarControlTypeId: "StatusBar",
    UIA_ScrollBarControlTypeId: "ScrollBar",
    UIA_SliderControlTypeId: "Slider",
    UIA_ProgressBarControlTypeId: "ProgressBar",
    UIA_ImageControlTypeId: "Image",
    UIA_HyperlinkControlTypeId: "Hyperlink",
    UIA_CheckBoxControlTypeId: "CheckBox",
    UIA_RadioButtonControlTypeId: "RadioButton",
    UIA_ComboBoxControlTypeId: "ComboBox",
    UIA_SpinnerControlTypeId: "Spinner",
    UIA_ToolTipControlTypeId: "ToolTip",
    UIA_GroupControlTypeId: "Group",
    UIA_SeparatorControlTypeId: "Separator",
    UIA_ThumbControlTypeId: "Thumb",
}


def control_type_name(control_type_id: int) -> str:
    return CONTROL_TYPE_NAMES.get(control_type_id, f"Unknown({control_type_id})")


# =============================================================================
# Variant helpers
# =============================================================================


def variant_to_str(variant: VARIANT) -> str:
    if variant.vt == VT_BSTR:
        return variant.value or ""
    if variant.vt == VT_I4:
        return str(variant.value)
    if variant.vt == VT_UI4:
        return str(variant.value)
    if variant.vt == VT_EMPTY:
        return ""
    return str(variant.value) if variant.value is not None else ""


def variant_to_int(variant: VARIANT) -> int:
    if variant.vt in (VT_I4, VT_UI4):
        return int(variant.value or 0)
    return 0


def variant_to_bool(variant: VARIANT) -> bool:
    if variant.vt == VT_I4:
        return bool(variant.value)
    return False


def variant_to_runtime_id(variant: VARIANT) -> list[int]:
    if variant.vt == (VT_ARRAY | VT_I4):
        try:
            arr = safearray_as_ndarray(variant)
            return arr.tolist()
        except Exception:
            pass
    return []


# =============================================================================
# Desktop class - main observation interface
# =============================================================================


class Desktop:
    """Main desktop observation class using UIA COM."""
    
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._automation: IUIAutomation | None = None
        self._last_observation: Observation | None = None
        self._focused_title_cache: str = ""
        self._init_automation()
    
    def _init_automation(self) -> None:
        """Initialize UIA automation."""
        try:
            self._automation = comtypes.client.CreateObject(
                CLSID_CUIAutomation, interface=IUIAutomation
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize UIA automation: {e}")
    
    @property
    def automation(self) -> IUIAutomation:
        if self._automation is None:
            self._init_automation()
        return self._automation
    
    def _get_root_element(self) -> IUIAutomationElement:
        """Get the desktop root element."""
        root = ctypes.POINTER(IUIAutomationElement)()
        hr = self.automation.GetRootElement(ctypes.byref(root))
        if hr != 0 or not root:
            raise RuntimeError(f"Failed to get root element: HRESULT={hr:#x}")
        return root
    
    def _get_property(self, element: IUIAutomationElement, property_id: int) -> VARIANT:
        """Get a property value from an element."""
        variant = VARIANT()
        variant.vt = VT_EMPTY
        hr = element.GetCurrentPropertyValue(property_id, ctypes.byref(variant))
        if hr != 0:
            variant.vt = VT_EMPTY
        return variant
    
    def _element_to_element(self, uia_element: IUIAutomationElement, max_depth: int = 3, current_depth: int = 0) -> Element:
        """Convert UIA element to our Element dataclass."""
        if current_depth >= max_depth:
            return Element()
        
        # Get properties
        name_var = self._get_property(uia_element, UIA_NamePropertyId)
        control_type_var = self._get_property(uia_element, UIA_ControlTypePropertyId)
        localized_type_var = self._get_property(uia_element, UIA_LocalizedControlTypePropertyId)
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
        
        # Build rect
        rect = Rect()
        if rect_var.vt == (VT_ARRAY | VT_I4):
            try:
                arr = safearray_as_ndarray(rect_var)
                if len(arr) >= 4:
                    rect = Rect(
                        left=int(arr[0]),
                        top=int(arr[1]),
                        right=int(arr[0] + arr[2]),
                        bottom=int(arr[1] + arr[3]),
                    )
            except Exception:
                pass
        
        element = Element(
            name=variant_to_str(name_var),
            control_type=control_type_name(control_type_id),
            control_type_id=control_type_id,
            automation_id=variant_to_str(automation_id_var),
            class_name=variant_to_str(class_name_var),
            process_id=variant_to_int(process_id_var),
            rect=rect,
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
                walker = ctypes.POINTER(IUIAutomationTreeWalker)()
                hr = self.automation.ControlViewWalker(ctypes.byref(walker))
                if hr == 0 and walker:
                    child = ctypes.POINTER(IUIAutomationElement)()
                    hr = walker.GetFirstChildElement(uia_element, ctypes.byref(child))
                    while hr == 0 and child:
                        element.children.append(self._element_to_element(child, max_depth, current_depth + 1))
                        next_sibling = ctypes.POINTER(IUIAutomationElement)()
                        hr = walker.GetNextSiblingElement(child, ctypes.byref(next_sibling))
                        child = next_sibling
            except Exception:
                pass
        
        return element
    
    def _find_focused_element(self, root: IUIAutomationElement) -> IUIAutomationElement | None:
        """Find the element with keyboard focus."""
        try:
            true_condition = ctypes.POINTER(IUIAutomationCondition)()
            hr = self.automation.CreateTrueCondition(ctypes.byref(true_condition))
            if hr != 0 or not true_condition:
                return None
            
            focused = ctypes.POINTER(IUIAutomationElement)()
            hr = root.FindFirst(TreeScope_Descendants, true_condition, ctypes.byref(focused))
            if hr == 0 and focused:
                # Check if this element has focus
                focus_var = self._get_property(focused, UIA_HasKeyboardFocusPropertyId)
                if variant_to_bool(focus_var):
                    return focused
        except Exception:
            pass
        return None
    
    def _get_active_window(self) -> IUIAutomationElement | None:
        """Get the active (foreground) window."""
        try:
            # Get foreground window handle
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if hwnd:
                element = ctypes.POINTER(IUIAutomationElement)()
                hr = self.automation.ElementFromHandle(hwnd, ctypes.byref(element))
                if hr == 0 and element:
                    return element
        except Exception:
            pass
        return None
    
    def _get_window_title(self, element: IUIAutomationElement) -> str:
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
            walker = ctypes.POINTER(IUIAutomationTreeWalker)()
            hr = self.automation.ControlViewWalker(ctypes.byref(walker))
            if hr == 0 and walker:
                child = ctypes.POINTER(IUIAutomationElement)()
                hr = walker.GetFirstChildElement(root, ctypes.byref(child))
                count = 0
                while hr == 0 and child and count < max_elements:
                    elem = self._element_to_element(child, max_depth)
                    if include_offscreen or not elem.is_offscreen:
                        root_elements.append(elem)
                        count += 1
                    next_sibling = ctypes.POINTER(IUIAutomationElement)()
                    hr = walker.GetNextSiblingElement(child, ctypes.byref(next_sibling))
                    child = next_sibling
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