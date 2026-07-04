"""Harvest cached UIA subtree — wide properties, all pattern payloads, multi-path text."""
from __future__ import annotations

from typing import Any

from . import constants as C
from .models import CachedNode


def _variant_int(v: Any) -> int:
    if v is None:
        return 0
    if hasattr(v, "value"):
        v = v.value
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _variant_str(v: Any) -> str:
    if v is None:
        return ""
    if hasattr(v, "value"):
        v = v.value
    return "" if v is None else str(v)


def _variant_bool(v: Any) -> bool:
    if v is None:
        return False
    if hasattr(v, "value"):
        v = v.value
    return bool(v)


def _variant_rect(v: Any) -> dict[str, int]:
    if v is None:
        return {"left": 0, "top": 0, "right": 0, "bottom": 0}
    try:
        val = v.value if hasattr(v, "value") else v
        if isinstance(val, (tuple, list)) and len(val) >= 4:
            left, top, third, fourth = (float(x) for x in val[:4])
            left_i, top_i = int(left), int(top)
            if third > left or fourth > top:
                right_i, bottom_i = int(third), int(fourth)
            else:
                right_i, bottom_i = left_i + int(third), top_i + int(fourth)
            return {"left": left_i, "top": top_i, "right": right_i, "bottom": bottom_i}
        if hasattr(val, "left"):
            return {
                "left": int(val.left),
                "top": int(val.top),
                "right": int(val.right),
                "bottom": int(val.bottom),
            }
    except Exception:
        pass
    return {"left": 0, "top": 0, "right": 0, "bottom": 0}


def _variant_runtime_id(v: Any) -> list[int]:
    if v is None:
        return []
    try:
        val = v.value if hasattr(v, "value") else v
        if val is None:
            return []
        return [int(x) for x in list(val)]
    except Exception:
        return []


def _serialize_value(v: Any) -> Any:
    if v is None:
        return None
    if hasattr(v, "value"):
        v = v.value
    if isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, (tuple, list)):
        return [_serialize_value(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _serialize_value(val) for k, val in v.items()}
    rect = _variant_rect(v)
    if rect["right"] > rect["left"] and rect["bottom"] > rect["top"]:
        return rect
    try:
        if hasattr(v, "__iter__") and not isinstance(v, (str, bytes)):
            return [_serialize_value(x) for x in list(v)]
    except Exception:
        pass
    s = str(v).strip()
    return s if s else None


def _node_id(runtime_id: list[int], hwnd: int, rect: dict[str, int]) -> str:
    if runtime_id:
        return "e_" + "_".join(map(str, runtime_id))
    return f"e_{hwnd}_{rect['left']}_{rect['top']}"


def _get_cached(element: Any, prop_id: int) -> Any:
    try:
        return element.GetCachedPropertyValue(prop_id)
    except Exception:
        return None


def _get_current(element: Any, prop_id: int) -> Any:
    try:
        return element.GetCurrentPropertyValue(prop_id)
    except Exception:
        return None


def _harvest_properties(element: Any) -> dict[str, Any]:
    props: dict[str, Any] = {}
    for pid in C.PROPERTY_IDS:
        label = C.PROPERTY_NAMES.get(pid, f"Property_{pid}")
        cached = _serialize_value(_get_cached(element, pid))
        if cached is not None and cached != "" and cached != []:
            props[label] = cached
            continue
        current = _serialize_value(_get_current(element, pid))
        if current is not None and current != "" and current != []:
            props[f"{label}_current"] = current
    return props


def _get_pattern(element: Any, pattern_id: int, label: str) -> tuple[Any | None, str]:
    try:
        return element.GetCachedPattern(pattern_id), "cached"
    except Exception:
        pass
    try:
        return element.GetCurrentPattern(pattern_id), "current"
    except Exception:
        pass
    return None, ""


def _safe_attr(obj: Any, name: str) -> Any:
    try:
        return getattr(obj, name)
    except Exception:
        return None


def _extract_pattern_payload(pattern: Any, label: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if pattern is None:
        return out

    if label == "Text":
        for src, doc in (
            ("DocumentRange", _safe_attr(pattern, "DocumentRange")),
        ):
            if doc is None:
                continue
            try:
                text = doc.GetText(-1)
                if text and str(text).strip():
                    out[src] = str(text)
            except Exception:
                pass
        try:
            ranges = pattern.GetVisibleRanges()
            if ranges is not None:
                texts = []
                try:
                    length = int(ranges.Length)
                except Exception:
                    length = 0
                for i in range(length):
                    try:
                        r = ranges.GetElement(i)
                        t = r.GetText(-1)
                        if t and str(t).strip():
                            texts.append(str(t))
                    except Exception:
                        continue
                if texts:
                    out["VisibleRanges"] = "\n".join(texts)
        except Exception:
            pass

    elif label == "Value":
        for key in ("Value", "IsReadOnly"):
            val = _safe_attr(pattern, key)
            if val is not None:
                out[key] = _serialize_value(val)

    elif label == "LegacyIAccessible":
        for key in (
            "Name", "Value", "Description", "Role", "State", "DefaultAction",
            "Help", "KeyboardShortcut", "ChildId",
        ):
            val = _safe_attr(pattern, key)
            if val is not None and str(val).strip() not in ("", "0"):
                out[key] = _serialize_value(val)

    elif label == "Scroll":
        for key in ("HorizontallyScrollable", "HorizontalScrollPercent", "HorizontalViewSize",
                    "VerticallyScrollable", "VerticalScrollPercent", "VerticalViewSize"):
            val = _safe_attr(pattern, key)
            if val is not None:
                out[key] = _serialize_value(val)

    elif label == "Window":
        for key in ("CanMaximize", "CanMinimize", "IsModal", "IsTopmost", "WindowInteractionState", "WindowVisualState"):
            val = _safe_attr(pattern, key)
            if val is not None:
                out[key] = _serialize_value(val)

    elif label == "Invoke":
        out["available"] = True

    elif label == "Selection":
        try:
            sel = pattern.GetSelection()
            if sel is not None:
                try:
                    length = int(sel.Length)
                except Exception:
                    length = 0
                out["selection_count"] = length
        except Exception:
            pass

    else:
        out["available"] = True

    return out


def _harvest_patterns(element: Any) -> tuple[list[str], dict[str, Any]]:
    names: list[str] = []
    payloads: dict[str, Any] = {}
    for pid in C.PATTERN_IDS:
        label = C.PATTERN_NAMES.get(pid, f"Pattern_{pid}")
        pattern, source = _get_pattern(element, pid, label)
        if pattern is None:
            continue
        names.append(label)
        payload = _extract_pattern_payload(pattern, label)
        if payload:
            payload["_source"] = source
            payloads[label] = payload
        else:
            payloads[label] = {"_source": source, "available": True}
    return names, payloads


def _collect_text_sources(
    name: str,
    properties: dict[str, Any],
    pattern_payloads: dict[str, Any],
) -> tuple[dict[str, str], str | None, str | None]:
    sources: dict[str, str] = {}
    if name and name.strip():
        sources["name"] = name.strip()

    for key in ("HelpText", "FullDescription", "ItemStatus", "AcceleratorKey", "AccessKey"):
        val = properties.get(key)
        if isinstance(val, str) and val.strip():
            sources[key.lower()] = val.strip()

    text_full: str | None = None
    value: str | None = None

    text_payload = pattern_payloads.get("Text", {})
    for key in ("DocumentRange", "VisibleRanges"):
        val = text_payload.get(key)
        if isinstance(val, str) and val.strip():
            sources[f"text_{key.lower()}"] = val.strip()
            if not text_full or len(val) > len(text_full):
                text_full = val.strip()

    value_payload = pattern_payloads.get("Value", {})
    val = value_payload.get("Value")
    if isinstance(val, str) and val.strip():
        sources["value_pattern"] = val.strip()
        value = val.strip()

    legacy = pattern_payloads.get("LegacyIAccessible", {})
    for key in ("Value", "Name", "Description"):
        val = legacy.get(key)
        if isinstance(val, str) and val.strip():
            sources[f"legacy_{key.lower()}"] = val.strip()
            if key == "Value" and not value:
                value = val.strip()
            if not text_full or (isinstance(val, str) and len(val) > len(text_full or "")):
                if key in ("Value", "Description") or (key == "Name" and len(val) > 20):
                    text_full = val.strip()

    if not text_full and name and len(name) > 1:
        # Scintilla/Notepad++ often surfaces first line in Name only
        text_full = name.strip()

    return sources, text_full, value


def element_to_cached_node(element: Any, *, probe_xy: tuple[int, int] | None = None) -> CachedNode | None:
    try:
        rect = _variant_rect(_get_cached(element, C.PID_BOUNDING_RECT))
        if rect["right"] <= rect["left"] or rect["bottom"] <= rect["top"]:
            rect = _variant_rect(_get_current(element, C.PID_BOUNDING_RECT))
        if rect["right"] <= rect["left"] or rect["bottom"] <= rect["top"]:
            return None

        runtime_id = _variant_runtime_id(_get_cached(element, C.PID_RUNTIME_ID))
        if not runtime_id:
            runtime_id = _variant_runtime_id(_get_current(element, C.PID_RUNTIME_ID))
        hwnd = _variant_int(_get_cached(element, C.PID_HWND))
        role_id = _variant_int(_get_cached(element, C.PID_CONTROL_TYPE))
        name = _variant_str(_get_cached(element, C.PID_NAME))
        if not name:
            name = _variant_str(_get_current(element, C.PID_NAME))

        properties = _harvest_properties(element)
        patterns, pattern_payloads = _harvest_patterns(element)
        text_sources, text_full, value = _collect_text_sources(name, properties, pattern_payloads)

        px = (rect["left"] + rect["right"]) // 2
        py = (rect["top"] + rect["bottom"]) // 2

        return CachedNode(
            id=_node_id(runtime_id, hwnd, rect),
            role=C.control_type_name(role_id),
            name=name,
            automation_id=_variant_str(_get_cached(element, C.PID_AUTOMATION_ID)),
            class_name=_variant_str(_get_cached(element, C.PID_CLASS_NAME)),
            hwnd=hwnd,
            framework_id=_variant_str(_get_cached(element, C.PID_FRAMEWORK)),
            px=px,
            py=py,
            rect=rect,
            enabled=_variant_bool(_get_cached(element, C.PID_ENABLED)),
            keyboard_focus=_variant_bool(_get_cached(element, C.PID_KEYBOARD_FOCUS)),
            offscreen=_variant_bool(_get_cached(element, C.PID_OFFSCREEN)),
            runtime_id=runtime_id,
            text_full=text_full,
            value=value,
            patterns=patterns,
            properties=properties,
            pattern_payloads=pattern_payloads,
            text_sources=text_sources,
            source_probe=probe_xy,
        )
    except Exception:
        return None


def _true_condition(automation: Any) -> Any:
    try:
        return automation.CreateTrueCondition()
    except Exception:
        return automation.TrueCondition


def harvest_cached_subtree(
    automation: Any,
    root_element: Any,
    cache_request: Any,
    *,
    probe_xy: tuple[int, int],
    max_nodes: int,
) -> list[CachedNode]:
    """Walk cached subtree under root_element using FindAllBuildCache."""
    nodes: list[CachedNode] = []
    seen: set[str] = set()

    def add_element(el: Any) -> None:
        if len(nodes) >= max_nodes:
            return
        node = element_to_cached_node(el, probe_xy=probe_xy)
        if node is None or node.id in seen:
            return
        seen.add(node.id)
        nodes.append(node)

    add_element(root_element)
    try:
        arr = root_element.FindAllBuildCache(C.TreeScope_Descendants, _true_condition(automation), cache_request)
        if arr is not None:
            try:
                length = int(arr.Length)
            except Exception:
                length = 0
            for i in range(length):
                if len(nodes) >= max_nodes:
                    break
                try:
                    add_element(arr.GetElement(i))
                except Exception:
                    continue
    except Exception:
        try:
            walker = automation.CreateTreeWalkerBuildCache(_true_condition(automation), cache_request)
            child = walker.GetFirstChildElement(root_element)
            stack = [child] if child else []
            while stack and len(nodes) < max_nodes:
                el = stack.pop()
                if el is None:
                    continue
                add_element(el)
                try:
                    sib = walker.GetNextSiblingElement(el)
                    if sib:
                        stack.append(sib)
                    first = walker.GetFirstChildElement(el)
                    if first:
                        stack.append(first)
                except Exception:
                    pass
        except Exception:
            pass

    return nodes