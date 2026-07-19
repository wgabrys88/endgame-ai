"""obs_build — observation phase 3: build the window/element tree, index, and text.

A wired, swappable observation phase. Input contract (from obs_scan + obs_filter):
action_elements, text_hints, raw_nodes, hwnd_to_z, screen, config. Output: the
rendered tree, node_index, action_index, desktop_tree_text, and counts that the
observation artifact and downstream LLM nodes consume.
"""
import time
import ctypes
from ctypes import wintypes
from typing import Any

user32 = ctypes.windll.user32
_GA_ROOT = 2  # GetAncestor: the top-level owning window of any element handle

# UIA WindowInteractionState: surface only states an actor must heed; a window
# ready for interaction (2) needs no tag. Running(0) = still initializing/busy.
_WINDOW_STATE_LABELS = {0: "busy", 1: "closing", 3: "modal-blocked", 4: "not-responding"}


def _root_hwnd(hwnd: int) -> int:
    """The top-level owning window of an element's handle, by IDENTITY — so an element
    is attributed to the window that truly owns it, never to whatever rectangle covers
    its pixel (which lets a maximized window swallow the whole screen)."""
    if not hwnd:
        return 0
    try:
        root = int(user32.GetAncestor(wintypes.HWND(hwnd), _GA_ROOT) or 0)
        return root or hwnd
    except Exception:
        return hwnd


def _window_text(hwnd: int) -> str:
    try:
        length = int(user32.GetWindowTextLengthW(wintypes.HWND(hwnd)))
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(wintypes.HWND(hwnd), buf, length + 1)
        return buf.value or ""
    except Exception:
        return ""


def _class_name(hwnd: int) -> str:
    try:
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(wintypes.HWND(hwnd), buf, 256)
        return buf.value or ""
    except Exception:
        return ""


def _window_rect(hwnd: int) -> dict[str, int]:
    try:
        r = wintypes.RECT()
        if user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(r)):
            return {"left": int(r.left), "top": int(r.top), "right": int(r.right), "bottom": int(r.bottom)}
    except Exception:
        pass
    return {"left": 0, "top": 0, "right": 0, "bottom": 0}


def run(action_elements: dict[str, dict[str, Any]], text_hints: dict[str, str], raw_nodes: list[dict[str, Any]], hwnd_to_z: dict[int, int], screen: dict[str, int], config: dict[str, Any]) -> dict[str, Any]:
    filt = config["filter"]
    budget = config["budget"]
    line_preview_chars = int(budget["line_preview_chars"])
    max_depth = int(filt.get("max_depth", 10))
    max_children_per_window = int(filt.get("max_children_per_window", 120))
    max_llm_nodes = int(filt.get("max_llm_nodes", int(filt["max_elements"]) * 2))
    # Windows derived from each element's TRUE OS top-level owner (GetAncestor root) — one
    # identity space for windows and elements, never rectangle-overlap.
    owner_hwnds: dict[int, dict[str, Any]] = {}

    def _register_window(owner: int, seed: dict[str, Any] | None = None) -> None:
        if not owner or owner in owner_hwnds:
            return
        title = _window_text(owner) or (seed.get("name") if seed else "") or (seed.get("text_full") if seed else "") or f"Window_{owner}"
        z_order = hwnd_to_z.get(owner, len(hwnd_to_z))
        owner_hwnds[owner] = {
            "hwnd": owner, "role": "Window", "name": title, "title": title,
            "class_name": _class_name(owner) or (seed.get("class_name", "") if seed else ""),
            "framework_id": seed.get("framework_id", "") if seed else "", "rect": _window_rect(owner),
            "z_order": z_order, "active": z_order == 0, "children": [],
            "interaction_state": seed.get("interaction_state") if seed else None,
            "item_status": seed.get("item_status", "") if seed else "",
        }

    for node in raw_nodes:
        if node["role"] == "Window" and node["hwnd"]:
            _register_window(_root_hwnd(node["hwnd"]), node)
    for elem in action_elements.values():
        _register_window(int(elem.get("owner_hwnd", 0) or 0))
    windows = owner_hwnds
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

    # An element nests under the nearest filter-surviving ancestor via its true
    # parent_runtime_id chain, or else its owning window — never geometry.
    win_id_by_hwnd = {w["hwnd"]: w["id"] for w in sorted_windows}
    raw_by_rid: dict[tuple, dict[str, Any]] = {tuple(n["runtime_id"]): n for n in raw_nodes if n.get("runtime_id")}
    action_by_rid: dict[tuple, dict[str, Any]] = {}
    for elem in action_elements.values():
        rid = tuple(elem.get("runtime_id") or [])
        if rid:
            action_by_rid[rid] = elem

    def _owning_window(elem: dict[str, Any]) -> tuple[str, int | None]:
        owner = int(elem.get("owner_hwnd", 0) or 0)
        if owner in win_id_by_hwnd:
            return win_id_by_hwnd[owner], owner
        return "W0", None

    def _rendered_parent(elem: dict[str, Any]) -> dict[str, Any] | None:
        rid = tuple(elem.get("runtime_id") or [])
        seen: set[tuple] = set()
        cur = raw_by_rid.get(rid)
        while cur is not None:
            prid = tuple(cur.get("parent_runtime_id") or [])
            if not prid or prid in seen:
                break
            seen.add(prid)
            anc = action_by_rid.get(prid)
            if anc is not None and anc is not elem:
                return anc
            cur = raw_by_rid.get(prid)
        return None

    for elem in action_elements.values():
        parent_id, parent_hwnd = _owning_window(elem)
        # Cap elements per window (both nesting branches) so a huge list cannot bloat the tree.
        if parent_hwnd is not None and counts.get(parent_hwnd, 0) >= max_children_per_window:
            continue
        anc = _rendered_parent(elem)
        if anc is not None and anc.get("id") is not None:
            elem["parent_id"] = anc["id"]
            anc.setdefault("children", []).append(elem)
        else:
            elem["parent_id"] = parent_id
            (windows[parent_hwnd]["children"] if parent_hwnd in windows else root["children"]).append(elem)
        if parent_hwnd is not None:
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
        # No pixel point in the text: the actor targeteth by short_id and readeth px,py from
        # the action_index — a coordinate on the line is a dead token that only tempteth the
        # actor to nail a stale pixel into click(), against the law to reacquire each turn.
        is_disabled = node.get("enabled") is False
        parts = [p for p in (sid, role, name_prev, "[active]" if node.get("active") else "", "[focused]" if node.get("focused") else "", f"[{action}]" if action and not is_disabled else "", "[disabled]" if is_disabled else "") if p]
        state_label = _WINDOW_STATE_LABELS.get(node.get("interaction_state"))
        if state_label:
            parts.append(f"[{state_label}]")
        item_status = str(node.get("item_status") or "").strip()
        if item_status:
            parts.append(f"[status:{clean(item_status)}]")
        occluded = str(node.get("occluded_by") or "").strip()
        if occluded:
            parts.append(f"[occluded-by:{clean(occluded)}]")
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
