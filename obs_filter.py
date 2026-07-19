"""obs_filter — observation phase 2: cast out what is not a target, and say WHY.

A wired, swappable observation phase. Input contract (from obs_scan): raw nodes +
config + screen. Output contract (what obs_build reads): {action_elements,
text_hints, hwnd_to_z, hwnd_interactive_count}, and beside them an [eliminated]
ledger (id -> the reason it was cast out) so no thing vanisheth silently and the
whole winnowing may be beheld in the phase log.

The winnowing is an ORDERED CHAIN of named rules, not scattered guards. First come
the rules of NATURE — what a thing IS: offscreen, junk, not interactive, or a
nameless clickable (a nameless WRITABLE is kept, for an edit field's label is oft a
sibling Text). Then, for a thing that acteth, the rules of BUDGET — bounds and the
per-window and total fills. The first rule that biteth recordeth its verdict. To
change how observation filtereth, reorder or edit this one chain.
"""
from typing import Any

import core_observation as obs


def run(raw_nodes: list[dict[str, Any]], config: dict[str, Any], screen: dict[str, int]) -> dict[str, Any]:
    filt = config["filter"]
    max_elements = int(filt["max_elements"])
    max_per_window = int(filt["max_per_window"])
    sw, sh = int(screen.get("width", 0) or 0), int(screen.get("height", 0) or 0)

    def _owner(node: dict[str, Any]) -> int:
        # The TRUE top-level owner the scan resolved by identity; most elements report
        # hwnd 0, so caps MUST key on owner_hwnd, else one busy window starveth the rest.
        return int(node.get("owner_hwnd", 0) or 0) or int(node["hwnd"] or 0)

    def _off_bounds(node: dict[str, Any]) -> bool:
        return bool(sw and sh) and not (0 <= node["px"] < sw and 0 <= node["py"] < sh)

    def _nameless_clickable(node: dict[str, Any]) -> bool:
        action = node["action"]
        return bool(action) and action != "write" and not (node["name"] or node["text_full"] or node["value"] or node["automation_id"])

    # Rules of NATURE — a thing is cast out for WHAT IT IS, before ever it is weighed for
    # budget. Ordered; the first that biteth names the verdict. Edit this list to change
    # the winnowing; the organism's body is hot-swappable.
    nature_rules: list[tuple[str, Any]] = [
        ("offscreen", lambda n: n["offscreen"]),
        ("junk_role", lambda n: n["role"] in obs.JUNK_ROLES),
        ("not_interactive", lambda n: not n["action"]),
        ("nameless_clickable", _nameless_clickable),
    ]

    hwnd_to_z = {hwnd: i for i, hwnd in enumerate(obs.get_window_z_order())}
    action_elements: dict[str, dict[str, Any]] = {}
    text_hints: dict[str, str] = {}
    hwnd_counts: dict[int, int] = {}
    eliminated: dict[str, str] = {}

    # Named things first, so the budget filleth with the legible before the anonymous.
    ranked = sorted(raw_nodes, key=lambda n: 0 if (n["name"] or n["text_full"]) else 1)
    for node in ranked:
        reason = next((name for name, hit in nature_rules if hit(node)), None)
        if reason:
            eliminated[node["id"]] = reason
            continue
        # Past the rules of nature, every thing beareth an action. A label borne in its own
        # text (differing from its name) is hung upon it as a hint whether or not it survive
        # the budget — an unnamed input is oft known only thus.
        label = node["text_full"] or node["name"] or ""
        if label and label != (node["name"] or ""):
            text_hints[node["id"]] = label
        if _off_bounds(node):
            eliminated[node["id"]] = "offscreen_bounds"
            continue
        owner = _owner(node)
        if owner and hwnd_counts.get(owner, 0) >= max_per_window:
            eliminated[node["id"]] = "owner_window_cap"
            continue
        if len(action_elements) >= max_elements:
            eliminated[node["id"]] = "element_budget"
            continue
        if owner:
            hwnd_counts[owner] = hwnd_counts.get(owner, 0) + 1
        action_elements[node["id"]] = {
            "id": node["id"], "short_id": "", "name": label or node["name"], "role": node["role"],
            "action": node["action"], "px": node["px"], "py": node["py"], "hwnd": node["hwnd"], "rect": node["rect"],
            "enabled": node["enabled"], "automation_id": node["automation_id"], "class_name": node["class_name"],
            "runtime_id": node["runtime_id"], "depth": node["depth"], "focused": node["focused"],
            "owner_hwnd": node.get("owner_hwnd", 0), "hit_point": node.get("hit_point"),
        }
    return {
        "action_elements": action_elements,
        "text_hints": text_hints,
        "hwnd_to_z": hwnd_to_z,
        "hwnd_interactive_count": hwnd_counts,
        "eliminated": eliminated,
    }
