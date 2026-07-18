"""obs_build — observation phase 3: build the window/element tree, index, and text.

A wired, swappable observation phase. Input contract (from obs_scan + obs_filter):
action_elements, text_hints, raw_nodes, hwnd_to_z, screen, config. Output: the
rendered tree, node_index, action_index, desktop_tree_text, and counts that the
observation artifact and downstream LLM nodes consume.
"""
import time
from typing import Any

# UIA WindowInteractionState: surface only states an actor must heed; a window
# ready for interaction (2) needs no tag. Running(0) = still initializing/busy.
_WINDOW_STATE_LABELS = {0: "busy", 1: "closing", 3: "modal-blocked", 4: "not-responding"}


def run(action_elements: dict[str, dict[str, Any]], text_hints: dict[str, str], raw_nodes: list[dict[str, Any]], hwnd_to_z: dict[int, int], screen: dict[str, int], config: dict[str, Any]) -> dict[str, Any]:
    filt = config["filter"]
    budget = config["budget"]
    line_preview_chars = int(budget["line_preview_chars"])
    max_depth = int(filt.get("max_depth", 10))
    max_children_per_window = int(filt.get("max_children_per_window", 120))
    max_llm_nodes = int(filt.get("max_llm_nodes", int(filt["max_elements"]) * 2))
    windows: dict[int, dict[str, Any]] = {}
    for node in raw_nodes:
        if node["role"] == "Window" and node["hwnd"] and node["hwnd"] not in windows:
            title = node["name"] or node["text_full"] or f"Window_{node['hwnd']}"
            z_order = hwnd_to_z.get(node["hwnd"], len(hwnd_to_z))
            windows[node["hwnd"]] = {
                "hwnd": node["hwnd"], "role": "Window", "name": title, "title": title,
                "class_name": node["class_name"], "framework_id": node["framework_id"], "rect": node["rect"],
                "z_order": z_order, "active": z_order == 0, "children": [],
                "interaction_state": node.get("interaction_state"), "item_status": node.get("item_status", ""),
            }
    sorted_windows = sorted(windows.values(), key=lambda w: w["z_order"])
    root = {"id": "W0", "role": "Screen", "name": "Screen", "title": "Desktop", "rect": {"left": 0, "top": 0, "right": screen["width"], "bottom": screen["height"]}, "fresh_scan": True, "observed_at": time.time(), "children": []}
    node_index: dict[str, dict[str, Any]] = {"W0": {k: v for k, v in root.items() if k != "children"}}
    counts = {w["hwnd"]: 0 for w in sorted_windows}
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

    short_by_id: dict[str, str] = {"W0": "W0"}
    counter = {"n": 0}

    def assign(node: dict[str, Any]) -> None:
        internal = node.get("id", "")
        if str(internal).startswith("W"):
            short = str(internal)
        else:
            counter["n"] += 1
            short = f"e{counter['n']}"
        short_by_id[internal] = short
        node["short_id"] = short
        for child in node.get("children", []):
            if isinstance(child, dict):
                assign(child)

    assign(root)
    node_index_short = {short_by_id.get(oid, oid): {**ndata, "short_id": short_by_id.get(oid, oid)} for oid, ndata in node_index.items()}
    action_index_short = {short_by_id[oid]: {**edata, "short_id": short_by_id[oid]} for oid, edata in action_elements.items() if oid in short_by_id}

    def clean(v: Any) -> str:
        return " ".join(str(v or "").replace("\r", " ").replace("\n", " ").split())

    def preview(text: str) -> tuple[str, int]:
        cleaned = clean(text)
        n = len(cleaned)
        if n > line_preview_chars:
            return cleaned[:line_preview_chars], n
        return cleaned, 0

    lines = ["W0 Screen Desktop"]
    rendered = 1

    def render(node: dict[str, Any], indent: int = 1) -> None:
        nonlocal rendered
        if rendered >= max_llm_nodes:
            return
        sid, role, action = node.get("short_id", node.get("id", "")), str(node.get("role", "")), str(node.get("action", ""))
        name_prev, name_total = preview(node.get("name", "") or node.get("title", ""))
        point = f"@{node['px']},{node['py']}" if node.get("px") is not None and node.get("py") is not None else ""
        is_disabled = node.get("enabled") is False
        parts = [p for p in (sid, role, name_prev, point, "[active]" if node.get("active") else "", "[focused]" if node.get("focused") else "", f"[{action}]" if action and not is_disabled else "", "[disabled]" if is_disabled else "") if p]
        state_label = _WINDOW_STATE_LABELS.get(node.get("interaction_state"))
        if state_label:
            parts.append(f"[{state_label}]")
        item_status = str(node.get("item_status") or "").strip()
        if item_status:
            parts.append(f"[status:{clean(item_status)}]")
        hint = text_hints.get(node.get("id", ""), "")
        hint_total = 0
        if hint and clean(hint) not in name_prev:
            hint_prev, hint_total = preview(hint)
            parts.append(f"~{hint_prev}")
        held = max(name_total, hint_total)
        if held:
            parts.append(f"({held} chars)")
        lines.append("  " * indent + " ".join(parts))
        rendered += 1
        for child in node.get("children", []):
            if isinstance(child, dict):
                render(child, indent + 1)

    for child in root.get("children", []):
        if isinstance(child, dict):
            render(child, 1)

    screen_elements = [
        {
            "id": short_by_id.get(n["id"], ""),
            "name": n.get("name", ""),
            "role": n.get("role", ""),
            "text": n.get("text_full", "") or "",
            "value": n.get("value", "") or "",
            "px": n.get("px"),
            "py": n.get("py"),
            "rect": n.get("rect", {}),
            "hwnd": n.get("hwnd", 0),
            "enabled": n.get("enabled"),
        }
        for n in raw_nodes
        if not n.get("offscreen")
    ]
    return {
        "root": root,
        "node_index": node_index_short,
        "action_index": action_index_short,
        "screen_elements": screen_elements,
        "desktop_tree_text": "\n".join(lines),
        "window_count": len(sorted_windows),
        "element_count": len(action_index_short),
        "window_z_order": [w["hwnd"] for w in sorted_windows],
    }
