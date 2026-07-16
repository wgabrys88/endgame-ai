"""obs_scan — observation phase 1: scan the desktop via UIA point-probing.

A wired, swappable observation phase. `observe()` in core_observation loads this by
the name in wiring.observe_config.phases.scan. Input: config + desktop. Output
contract (what the next phase, obs_filter, reads): {nodes, screen}.
"""
import ctypes
from ctypes import wintypes
from typing import Any

import core_observation as obs

user32 = ctypes.windll.user32


def run(config: dict[str, Any], desktop: Any) -> dict[str, Any]:
    scan = config["scan"]
    step_px = int(scan["step_px"])
    max_subtree = int(scan["max_subtree_nodes_per_point"])
    max_total = int(scan["max_total_nodes"])
    sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    area = scan.get("area") or {}
    if area:
        left = max(0, min(sw - 1, int(area.get("left", 0) or 0)))
        top = max(0, min(sh - 1, int(area.get("top", 0) or 0)))
        right = max(left + 1, min(sw, int(area.get("right", sw) or sw)))
        bottom = max(top + 1, min(sh, int(area.get("bottom", sh) or sh)))
    else:
        left, top, right, bottom = 0, 0, sw, sh
    margin = 2
    usable_w, usable_h = max(1, right - left - 2 * margin), max(1, bottom - top - 2 * margin)
    cols, rows = max(1, usable_w // step_px), max(1, usable_h // step_px)
    g = 1.32471795724474602596
    ax, ay = 1.0 / g, 1.0 / (g * g)
    points: list[tuple[int, int]] = []
    cells: set[tuple[int, int]] = set()
    for i in range((cols + 1) * (rows + 1)):
        x = left + margin + int(((0.5 + ax * (i + 1)) % 1.0) * usable_w)
        y = top + margin + int(((0.5 + ay * (i + 1)) % 1.0) * usable_h)
        cell = (x // step_px, y // step_px)
        if cell not in cells:
            cells.add(cell)
            points.append((min(sw - 1, max(0, x)), min(sh - 1, max(0, y))))
    scanner = obs.UiaScanner(config, desktop)
    index: dict[str, dict[str, Any]] = {}
    saturated: set[str] = set()
    saved = wintypes.POINT()
    had_cursor = bool(user32.GetCursorPos(ctypes.byref(saved)))
    try:
        for x, y in points:
            if len(index) >= max_total:
                break
            user32.SetCursorPos(int(x), int(y))
            pt = wintypes.POINT(int(x), int(y))
            try:
                root = scanner.automation.ElementFromPointBuildCache(pt, scanner._cache(obs.TreeScope_Element))
            except Exception:
                try:
                    root = scanner.automation.ElementFromPoint(pt)
                except Exception:
                    continue
            if root is None:
                continue
            hit_key, role = obs._hit_key_from_element(root)
            if hit_key in saturated or (hit_key in index and role not in obs.CONTAINER_ROLES):
                continue
            nodes = scanner.harvest_subtree(root, max_subtree)
            added = 0
            for node in nodes:
                if obs.is_desktop_leakage(node):
                    continue
                prev = index.get(node["id"])
                if prev is None:
                    index[node["id"]] = node
                    added += 1
                else:
                    for key in ("text_full", "value"):
                        if node[key] and (not prev[key] or len(node[key]) > len(prev[key])):
                            prev[key] = node[key]
                    for key, value in node["pattern_values"].items():
                        if key not in prev["pattern_values"] or len(value) > len(prev["pattern_values"].get(key, "")):
                            prev["pattern_values"][key] = value
                    prev["patterns"] = sorted(set(prev["patterns"]) | set(node["patterns"]))
            if hit_key and (added == 0 or len(nodes) >= max_subtree):
                saturated.add(hit_key)
    finally:
        if had_cursor:
            try:
                user32.SetCursorPos(saved.x, saved.y)
            except Exception:
                pass
    return {
        "nodes": list(index.values()),
        "screen": {"width": sw, "height": sh},
    }
