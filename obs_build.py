"""obs_build — observation phase 3: build the window/element tree, index, and text.

A wired, swappable observation phase. Input contract (from obs_scan + obs_filter):
action_elements, text_hints, raw_nodes, hwnd_to_z, screen, config. Output: the
rendered tree, node_index, action_index, desktop_tree_text, and counts that the
observation artifact and downstream LLM nodes consume.
"""
import time
from typing import Any


def run(action_elements: dict[str, dict[str, Any]], text_hints: dict[str, str], raw_nodes: list[dict[str, Any]], hwnd_to_z: dict[int, int], screen: dict[str, int], config: dict[str, Any]) -> dict[str, Any]:
    filt = config["filter"]
    max_depth = int(filt.get("max_depth", 10))
    max_children_per_window = int(filt.get("max_children_per_window", 120))
    max_llm_nodes = int(filt.get("max_llm_nodes", int(filt["max_elements"]) * 2))
    windows: dict[int, dict[str, Any]] = {}
    for node in raw_nodes:
        if node["role"] == "Window" and node["hwnd"] and node["hwnd"] not in windows:
            windows[node["hwnd"]] = {
                "hwnd": node["hwnd"], "title": node["name"] or node["text_full"] or f"Window_{node['hwnd']}",
                "class_name": node["class_name"], "framework_id": node["framework_id"], "rect": node["rect"],
                "z_order": hwnd_to_z.get(node["hwnd"], 0), "children": [],
            }
    sorted_windows = sorted(windows.values(), key=lambda w: w["z_order"])
    root = {"id": "W0", "role": "Screen", "name": "Screen", "title": "Desktop", "rect": {"left": 0, "top": 0, "right": screen["width"], "bottom": screen["height"]}, "fresh_scan": True, "observed_at": time.time(), "children": []}
    node_index: dict[str, dict[str, Any]] = {"W0": {k: v for k, v in root.items() if k != "children"}}
    counts = {w["hwnd"]: 0 for w in sorted_windows}
    dropped_per_window: dict[int, int] = {}
    for window in sorted_windows:
        token = f"W{len(root['children']) + 1}"
        window["id"] = token
        window["parent_id"] = "W0"
        root["children"].append(window)
        node_index[token] = {k: v for k, v in window.items() if k != "children"}

    def _rect_gap(r: dict[str, int], px: int, py: int) -> int:
        dx = max(r.get("left", 0) - px, 0, px - r.get("right", 0))
        dy = max(r.get("top", 0) - py, 0, py - r.get("bottom", 0))
        return dx * dx + dy * dy

    for elem in action_elements.values():
        parent_hwnd = next((w["hwnd"] for w in sorted_windows if w["rect"].get("left", 0) <= elem["px"] <= w["rect"].get("right", 0) and w["rect"].get("top", 0) <= elem["py"] <= w["rect"].get("bottom", 0)), None)
        if parent_hwnd is None and sorted_windows:
            nearest = min(sorted_windows, key=lambda w: _rect_gap(w["rect"], elem["px"], elem["py"]))
            parent_hwnd = nearest["hwnd"]
        parent_id = next((w["id"] for w in sorted_windows if w["hwnd"] == parent_hwnd), "W0") if parent_hwnd is not None else "W0"
        if parent_hwnd is not None and parent_id != "W0" and counts.get(parent_hwnd, 0) >= max_children_per_window:
            dropped_per_window[parent_hwnd] = dropped_per_window.get(parent_hwnd, 0) + 1
            continue
        elem["parent_id"] = parent_id
        (root["children"] if parent_id == "W0" or parent_hwnd is None else windows[parent_hwnd]["children"]).append(elem)
        if parent_hwnd is not None and parent_id != "W0":
            counts[parent_hwnd] = counts.get(parent_hwnd, 0) + 1
        node_index[elem["id"]] = {k: v for k, v in elem.items() if k != "children"}

    def area(r: dict[str, int]) -> int:
        return max(0, r.get("right", 0) - r.get("left", 0)) * max(0, r.get("bottom", 0) - r.get("top", 0))

    def sort_prune(node: dict[str, Any], depth: int = 0) -> None:
        kids = node.get("children", [])
        if not isinstance(kids, list):
            return
        if depth >= max_depth:
            node["children"] = []
            return
        kids.sort(key=lambda c: (c.get("z_order", 0), c.get("rect", {}).get("top", 0), c.get("rect", {}).get("left", 0), area(c.get("rect", {}))))
        for child in kids:
            if isinstance(child, dict):
                sort_prune(child, depth + 1)

    sort_prune(root)

    def assign(node: dict[str, Any]) -> None:
        node["short_id"] = node.get("id", "")
        for child in node.get("children", []):
            if isinstance(child, dict):
                assign(child)

    assign(root)
    node_index_short = {oid: {**ndata, "short_id": oid} for oid, ndata in node_index.items()}
    action_index_short = {oid: {**edata, "short_id": oid} for oid, edata in action_elements.items()}

    def clean(v: Any) -> str:
        return " ".join(str(v or "").replace("\r", " ").replace("\n", " ").split())

    lines = ["W0 Screen Desktop"]
    rendered = 1
    limit_hit = False

    def render(node: dict[str, Any], indent: int = 1) -> None:
        nonlocal rendered, limit_hit
        if rendered >= max_llm_nodes:
            limit_hit = True
            return
        sid, role, name, action = node.get("short_id", node.get("id", "")), str(node.get("role", "")), clean(node.get("name", "") or node.get("title", "")), str(node.get("action", ""))
        parts = [p for p in (sid, role, name, f"[{action}]" if action else "") if p]
        hint = text_hints.get(node.get("id", ""), "")
        if hint and hint not in name:
            parts.append(f"~{hint}")
        lines.append("  " * indent + " ".join(parts))
        rendered += 1
        for child in node.get("children", []):
            if isinstance(child, dict):
                render(child, indent + 1)

    for child in root.get("children", []):
        if isinstance(child, dict):
            render(child, 1)
    return {
        "root": root,
        "node_index": node_index_short,
        "action_index": action_index_short,
        "desktop_tree_text": "\n".join(lines),
        "window_count": len(sorted_windows),
        "element_count": len(action_index_short),
        "rendered_node_count": rendered,
        "max_llm_nodes": max_llm_nodes,
        "llm_node_limit_hit": limit_hit,
        "window_z_order": [w["hwnd"] for w in sorted_windows],
        "elements_dropped_per_window": {next((w["id"] for w in sorted_windows if w["hwnd"] == h), h): n for h, n in dropped_per_window.items() if n},
        "elements_truncated": sum(dropped_per_window.values()) > 0,
    }
