"""obs_filter — observation phase 2: rank and select actionable elements.

A wired, swappable observation phase. Input contract (from obs_scan): raw nodes +
config + screen. Output contract (what obs_build reads): {action_elements,
text_hints, hwnd_to_z, hwnd_interactive_count}. Change this file to change how
observation filters — e.g. route some elements one way and some another — without
touching scan or build.
"""
from typing import Any

import core_observation as obs


def run(raw_nodes: list[dict[str, Any]], config: dict[str, Any], screen: dict[str, int]) -> dict[str, Any]:
    filt = config["filter"]
    max_elements = int(filt["max_elements"])
    max_per_window = int(filt["max_per_window"])
    require_interactive = bool(filt["require_interactive"])
    sw, sh = int(screen.get("width", 0) or 0), int(screen.get("height", 0) or 0)

    def _on_screen(node: dict[str, Any]) -> bool:
        if not sw or not sh:
            return True
        return 0 <= node["px"] < sw and 0 <= node["py"] < sh

    hwnd_to_z = {hwnd: i for i, hwnd in enumerate(obs.get_window_z_order())}
    ranked = sorted([n for n in raw_nodes if not n["offscreen"] and n["role"] not in obs.JUNK_ROLES], key=lambda n: (0 if n["name"] or n["text_full"] else 1, 0 if not n["offscreen"] else 1))
    action_elements: dict[str, dict[str, Any]] = {}
    text_hints: dict[str, str] = {}
    hwnd_counts: dict[int, int] = {}
    for node in ranked:
        action = node["action"]
        if require_interactive and not action:
            continue
        label = node["text_full"] or node["name"] or ""
        # Drop nameless NON-write clickables as noise; keep nameless writables (an edit
        # field's label is oft a sibling Text, e.g. "Headline*" beside an unnamed input).
        if action and action != "write" and not (node["name"] or node["text_full"] or node["value"] or node["automation_id"]):
            continue
        if label and label != (node["name"] or ""):
            text_hints[node["id"]] = label
        if action:
            if not _on_screen(node):
                continue
            hwnd = node["hwnd"]
            if hwnd_counts.get(hwnd, 0) >= max_per_window:
                continue
            if len(action_elements) >= max_elements:
                continue
            hwnd_counts[hwnd] = hwnd_counts.get(hwnd, 0) + 1
            action_elements[node["id"]] = {
                "id": node["id"], "short_id": "", "name": label or node["name"], "role": node["role"],
                "action": action, "px": node["px"], "py": node["py"], "hwnd": hwnd, "rect": node["rect"],
                "enabled": node["enabled"], "automation_id": node["automation_id"], "class_name": node["class_name"],
                "runtime_id": node["runtime_id"], "depth": node["depth"], "focused": node["focused"],
                "owner_hwnd": node.get("owner_hwnd", 0), "hit_point": node.get("hit_point"),
            }
    return {
        "action_elements": action_elements,
        "text_hints": text_hints,
        "hwnd_to_z": hwnd_to_z,
        "hwnd_interactive_count": hwnd_counts,
    }
