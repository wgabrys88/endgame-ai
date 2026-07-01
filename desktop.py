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