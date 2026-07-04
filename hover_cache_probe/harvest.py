"""Harvest cached UIA subtree nodes + TextPattern/ValuePattern payloads."""
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
            # UIA via comtypes may return (l, t, r, b) OR (l, t, width, height)
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


def _node_id(runtime_id: list[int], hwnd: int, rect: dict[str, int]) -> str:
    if runtime_id:
        return "e_" + "_".join(map(str, runtime_id))
    return f"e_{hwnd}_{rect['left']}_{rect['top']}"


def _get_cached(element: Any, prop_id: int) -> Any:
    try:
        return element.GetCachedPropertyValue(prop_id)
    except Exception:
        return None


def _pattern_names(element: Any) -> list[str]:
    names = []
    mapping = {
        C.PATTERN_IDS[0]: "Text",
        C.PATTERN_IDS[1]: "Value",
        C.PATTERN_IDS[2]: "Scroll",
        C.PATTERN_IDS[3]: "LegacyIAccessible",
    }
    for pid, label in mapping.items():
        try:
            element.GetCachedPattern(pid)
            names.append(label)
        except Exception:
            pass
    return names


def _extract_text_pattern(element: Any) -> str | None:
    try:
        pattern = element.GetCachedPattern(C.PATTERN_IDS[0])
        if pattern is None:
            return None
        doc = pattern.DocumentRange
        if doc is None:
            return None
        text = doc.GetText(-1)
        if text and str(text).strip():
            return str(text)
    except Exception:
        pass
    return None


def _extract_value_pattern(element: Any) -> str | None:
    try:
        pattern = element.GetCachedPattern(C.PATTERN_IDS[1])
        if pattern is None:
            return None
        val = pattern.Value
        if val is not None and str(val).strip():
            return str(val)
    except Exception:
        pass
    return None


def element_to_cached_node(element: Any, *, probe_xy: tuple[int, int] | None = None) -> CachedNode | None:
    try:
        rect = _variant_rect(_get_cached(element, C.PROPERTY_IDS[2]))
        if rect["right"] <= rect["left"] or rect["bottom"] <= rect["top"]:
            return None
        runtime_id = _variant_runtime_id(_get_cached(element, C.PROPERTY_IDS[11]))
        hwnd = _variant_int(_get_cached(element, C.PROPERTY_IDS[5]))
        role_id = _variant_int(_get_cached(element, C.PROPERTY_IDS[1]))
        name = _variant_str(_get_cached(element, C.PROPERTY_IDS[0]))
        px = (rect["left"] + rect["right"]) // 2
        py = (rect["top"] + rect["bottom"]) // 2
        patterns = _pattern_names(element)
        text_full = _extract_text_pattern(element) if "Text" in patterns else None
        value = _extract_value_pattern(element) if "Value" in patterns else None
        return CachedNode(
            id=_node_id(runtime_id, hwnd, rect),
            role=C.control_type_name(role_id),
            name=name,
            automation_id=_variant_str(_get_cached(element, C.PROPERTY_IDS[3])),
            class_name=_variant_str(_get_cached(element, C.PROPERTY_IDS[4])),
            hwnd=hwnd,
            framework_id=_variant_str(_get_cached(element, C.PROPERTY_IDS[9])),
            px=px,
            py=py,
            rect=rect,
            enabled=_variant_bool(_get_cached(element, C.PROPERTY_IDS[6])),
            keyboard_focus=_variant_bool(_get_cached(element, C.PROPERTY_IDS[7])),
            offscreen=_variant_bool(_get_cached(element, C.PROPERTY_IDS[8])),
            runtime_id=runtime_id,
            text_full=text_full,
            value=value,
            patterns=patterns,
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
        # fallback: TreeWalker with cache
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