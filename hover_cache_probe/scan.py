"""Full-screen hover scan using ElementFromPointBuildCache per grid point."""
from __future__ import annotations

import ctypes
import math
import time
from ctypes import wintypes
from typing import Any, Iterable

from . import constants as C
from .harvest import harvest_cached_subtree
from .models import CachedNode

user32 = ctypes.windll.user32


def create_cache_request(automation: Any) -> Any:
    req = automation.CreateCacheRequest()
    req.TreeScope = C.TreeScope_Subtree
    for prop_id in C.PROPERTY_IDS:
        req.AddProperty(prop_id)
    for pattern_id in C.PATTERN_IDS:
        req.AddPattern(pattern_id)
    return req


def probe_point_build_cache(
    automation: Any,
    cache_request: Any,
    x: int,
    y: int,
    *,
    delay_ms: int,
    max_subtree_nodes: int,
    move_cursor: bool = True,
) -> tuple[Any | None, list[CachedNode]]:
    """Move real cursor, ElementFromPointBuildCache, harvest cached subtree."""
    if move_cursor:
        try:
            user32.SetCursorPos(int(x), int(y))
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)
        except Exception:
            pass
    pt = wintypes.POINT(int(x), int(y))
    try:
        root = automation.ElementFromPointBuildCache(pt, cache_request)
    except Exception:
        root = automation.ElementFromPoint(pt)
    if root is None:
        return None, []
    nodes = harvest_cached_subtree(
        automation,
        root,
        cache_request,
        probe_xy=(x, y),
        max_nodes=max_subtree_nodes,
    )
    return root, nodes


def sinusoidal_probe_points(
    sw: int,
    sh: int,
    *,
    step_px: int = 96,
    row_step_px: int | None = None,
) -> list[tuple[int, int]]:
    """Serpentine rows with sine wiggle — continuous path, fewer points than dense grid."""
    margin = max(8, step_px // 4)
    row_step = row_step_px or max(step_px, (sh - 2 * margin) // max(6, sh // (step_px * 2)))
    amplitude = max(4, row_step // 5)
    wavelength = max(sw // 2, step_px * 4)
    points: list[tuple[int, int]] = []
    row_idx = 0
    for y_base in range(margin, sh - margin, row_step):
        xs = list(range(margin, sw - margin, step_px))
        if row_idx % 2 == 1:
            xs.reverse()
        for x in xs:
            wiggle = int(amplitude * math.sin((2 * math.pi * x) / wavelength))
            y = min(sh - 1, max(0, y_base + wiggle))
            points.append((x, y))
        row_idx += 1
    return points


def _run_probe_path(
    automation: Any,
    cache_request: Any,
    points: Iterable[tuple[int, int]],
    *,
    delay_ms: int,
    max_subtree_nodes_per_point: int,
    max_total_nodes: int,
    max_probe_points: int | None,
    restore_cursor: bool,
    pattern: str,
    step_px: int,
) -> dict[str, Any]:
    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)
    global_index: dict[str, CachedNode] = {}
    probe_log: list[dict[str, Any]] = []
    t0 = time.time()
    probes = 0
    total_subtree = 0

    saved = wintypes.POINT()
    had_cursor = bool(user32.GetCursorPos(ctypes.byref(saved))) if restore_cursor else False

    try:
        for x, y in points:
            if max_probe_points is not None and probes >= max_probe_points:
                break
            if len(global_index) >= max_total_nodes:
                break
            probes += 1
            _, nodes = probe_point_build_cache(
                automation,
                cache_request,
                x,
                y,
                delay_ms=delay_ms,
                max_subtree_nodes=max_subtree_nodes_per_point,
                move_cursor=True,
            )
            added = merge_nodes(global_index, nodes)
            total_subtree += len(nodes)
            if nodes:
                probe_log.append({
                    "x": x,
                    "y": y,
                    "subtree_nodes": len(nodes),
                    "new_nodes": added,
                    "sample_roles": list({n.role for n in nodes[:8]}),
                })
    finally:
        if restore_cursor and had_cursor:
            try:
                user32.SetCursorPos(saved.x, saved.y)
            except Exception:
                pass

    fg_title = ""
    try:
        fg = automation.GetFocusedElement()
        if fg is not None:
            fg_title = str(fg.CurrentName or "")
    except Exception:
        pass

    nodes = list(global_index.values())
    text_blobs = [
        {
            "id": n.id,
            "role": n.role,
            "name": n.name,
            "length": len(n.text_full or ""),
            "prefix": (n.text_full or "")[:300],
            "sources": list(n.text_sources.keys()),
        }
        for n in nodes if n.text_full
    ]
    text_blobs.sort(key=lambda t: t["length"], reverse=True)

    return {
        "methodology": "SetCursorPos + ElementFromPointBuildCache(TreeScope_Subtree) + wide UIA property/pattern harvest",
        "screen": {"width": sw, "height": sh},
        "config": {
            "pattern": pattern,
            "step_px": step_px,
            "delay_ms": delay_ms,
            "max_probe_points": max_probe_points,
            "max_subtree_nodes_per_point": max_subtree_nodes_per_point,
            "max_total_nodes": max_total_nodes,
            "restore_cursor": restore_cursor,
            "cached_property_count": len(C.PROPERTY_IDS),
            "cached_pattern_count": len(C.PATTERN_IDS),
        },
        "stats": {
            "probes": probes,
            "subtree_nodes_seen": total_subtree,
            "unique_nodes": len(nodes),
            "nodes_with_text": sum(1 for n in nodes if n.text_full),
            "nodes_with_text_sources": sum(1 for n in nodes if n.text_sources),
            "nodes_with_value": sum(1 for n in nodes if n.value),
            "nodes_with_pattern_payloads": sum(1 for n in nodes if n.pattern_payloads),
            "avg_properties_per_node": round(
                sum(len(n.properties) for n in nodes) / max(len(nodes), 1), 1
            ),
            "elapsed_s": round(time.time() - t0, 3),
        },
        "focus": {"window_title": fg_title},
        "gather": {
            "nodes": [n.to_gather_dict() for n in nodes],
            "body_map": {
                n.id: {"hwnd": n.hwnd, "px": n.px, "py": n.py, "rect": n.rect}
                for n in nodes
            },
        },
        "llm_preview": {
            "nodes": [n.to_llm_dict() for n in nodes if not n.offscreen][:200],
            "text_blobs_top": text_blobs[:10],
        },
        "probe_log_sample": probe_log[:30],
    }


def merge_nodes(global_index: dict[str, CachedNode], new_nodes: list[CachedNode]) -> int:
    added = 0
    for node in new_nodes:
        prev = global_index.get(node.id)
        if prev is None:
            global_index[node.id] = node
            added += 1
            continue
        if node.text_full and (not prev.text_full or len(node.text_full) > len(prev.text_full)):
            prev.text_full = node.text_full
        if node.value and (not prev.value or len(node.value) > len(prev.value)):
            prev.value = node.value
        for k, v in node.text_sources.items():
            if k not in prev.text_sources or len(v) > len(prev.text_sources.get(k, "")):
                prev.text_sources[k] = v
        for k, v in node.properties.items():
            if k not in prev.properties:
                prev.properties[k] = v
        for k, v in node.pattern_payloads.items():
            if k not in prev.pattern_payloads:
                prev.pattern_payloads[k] = v
        if node.keyboard_focus:
            prev.keyboard_focus = True
        prev.patterns = sorted(set(prev.patterns) | set(node.patterns))
    return added


def fullscreen_hover_cache_scan(
    automation: Any,
    *,
    step_px: int = 32,
    delay_ms: int = 5,
    max_probe_points: int | None = None,
    max_subtree_nodes_per_point: int = 120,
    max_total_nodes: int = 2000,
    pattern: str = "grid",
) -> dict[str, Any]:
    """Single-pass full-screen hover + UIA cache harvest."""
    cache_request = create_cache_request(automation)
    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)

    if pattern == "sinusoidal":
        points = sinusoidal_probe_points(sw, sh, step_px=step_px)
    else:
        points = [(x, y) for y in range(0, sh, step_px) for x in range(0, sw, step_px)]

    return _run_probe_path(
        automation,
        cache_request,
        points,
        delay_ms=delay_ms,
        max_subtree_nodes_per_point=max_subtree_nodes_per_point,
        max_total_nodes=max_total_nodes,
        max_probe_points=max_probe_points,
        restore_cursor=True,
        pattern=pattern,
        step_px=step_px,
    )


def single_point_probe(
    automation: Any,
    x: int,
    y: int,
    *,
    delay_ms: int = 10,
    max_subtree_nodes: int = 500,
) -> dict[str, Any]:
    """Probe one screen coordinate (for random/manual testing)."""
    cache_request = create_cache_request(automation)
    t0 = time.time()
    root, nodes = probe_point_build_cache(
        automation,
        cache_request,
        x,
        y,
        delay_ms=delay_ms,
        max_subtree_nodes=max_subtree_nodes,
    )
    text_blobs = [
        {"id": n.id, "role": n.role, "name": n.name, "length": len(n.text_full or ""), "text_full": n.text_full}
        for n in nodes if n.text_full
    ]
    text_blobs.sort(key=lambda t: t["length"], reverse=True)
    root_brief = None
    if root is not None:
        try:
            root_brief = {"name": str(root.CurrentName or ""), "control_type": int(root.CurrentControlType)}
        except Exception:
            root_brief = {"name": ""}
    return {
        "point": {"x": x, "y": y},
        "elapsed_s": round(time.time() - t0, 3),
        "root": root_brief,
        "subtree_count": len(nodes),
        "nodes": [n.to_gather_dict() for n in nodes],
        "text_blobs": text_blobs,
        "llm_preview": [n.to_llm_dict() for n in nodes[:50]],
    }