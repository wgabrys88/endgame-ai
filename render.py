from __future__ import annotations
import json

CLICKABLE_ROLES = frozenset({
    "Button", "MenuItem", "ListItem", "Hyperlink", "TabItem", "TreeItem",
    "SplitButton", "CheckBox", "RadioButton", "Slider", "ScrollBar",
    "Spinner", "DataItem", "Document",
})
WRITABLE_ROLES = frozenset({"Edit", "ComboBox"})
SKIP_NAMELESS = frozenset({
    "Pane", "Group", "Custom", "Image", "Separator", "Thumb",
    "ProgressBar", "Header", "HeaderItem",
})


def parse_raw(lines: list[str]) -> tuple[dict, list[dict], dict, list[dict], list[dict], dict, list[dict]]:
    pos = 0
    screen = json.loads(lines[pos]); pos += 1
    hwnds: list[dict] = []
    while pos < len(lines) and "hwnd" in (obj := json.loads(lines[pos])):
        hwnds.append(obj); pos += 1
    focused = json.loads(lines[pos]); pos += 1
    probes: list[dict] = []
    while pos < len(lines) and "probe_px" in (obj := json.loads(lines[pos])):
        probes.append(obj); pos += 1
    windows: list[dict] = []
    while pos < len(lines) and "wnd_role" in (obj := json.loads(lines[pos])):
        windows.append(obj); pos += 1
    z_order = json.loads(lines[pos]); pos += 1
    tree_nodes: list[dict] = []
    while pos < len(lines) and "t_depth" in (obj := json.loads(lines[pos])):
        tree_nodes.append(obj); pos += 1
    return screen, hwnds, focused, probes, windows, z_order, tree_nodes


def classify_element(role: str, enabled: bool, readonly: bool) -> str:
    if not enabled:
        return "none"
    if role in WRITABLE_ROLES and not readonly:
        return "type"
    if role in CLICKABLE_ROLES:
        return "click"
    return "none"


def _assign_probe_to_window(px: int, py: int, windows: list[dict], z_order: dict) -> tuple[str, int]:
    """Assign a probe hit to a window based on Z-order and bounding rects."""
    # Build z-ordered window list (front to back)
    z_list = z_order.get("z_order", [])
    z_hwnds = [e["hwnd"] for e in z_list]

    # Build rect lookup from windows data
    wnd_rects: dict[int, tuple[str, int, int, int, int]] = {}
    for w in windows:
        wnd_rects[w["wnd_hwnd"]] = (w["wnd_name"], w["wnd_x"], w["wnd_y"],
                                     w["wnd_x"] + w["wnd_w"], w["wnd_y"] + w["wnd_h"])

    # Check z-order front to back: first window whose rect contains the point wins
    for hwnd in z_hwnds:
        if hwnd in wnd_rects:
            name, x0, y0, x1, y1 = wnd_rects[hwnd]
            if x0 <= px <= x1 and y0 <= py <= y1:
                return name, hwnd

    # Fallback: check all windows
    for hwnd, (name, x0, y0, x1, y1) in wnd_rects.items():
        if x0 <= px <= x1 and y0 <= py <= y1:
            return name, hwnd

    return "", 0


def merge_probe_into_tree(tree_nodes: list[dict], probes: list[dict],
                          windows: list[dict], z_order: dict) -> list[dict]:
    tree_keys = {
        (n["t_role"], n["t_name"], n["t_x"], n["t_y"], n["t_w"], n["t_h"])
        for n in tree_nodes
    }
    merged = list(tree_nodes)
    for p in probes:
        if not p.get("p_role"):
            continue
        key = (p["p_role"], p.get("p_name", ""), p["p_x"], p["p_y"], p["p_w"], p["p_h"])
        if key not in tree_keys:
            # Use parent-chain-derived window and depth if available
            wnd_name = p.get("p_wnd", "")
            wnd_hwnd = p.get("p_hwnd", 0)
            depth = p.get("p_depth", 0)

            # Fallback: assign by bounding rect if probe didn't find window
            if not wnd_name:
                cx = p["p_x"] + p["p_w"] // 2
                cy = p["p_y"] + p["p_h"] // 2
                wnd_name, wnd_hwnd = _assign_probe_to_window(cx, cy, windows, z_order)

            merged.append({
                "t_wnd": wnd_name, "t_hwnd": wnd_hwnd, "t_depth": depth,
                "t_role": p["p_role"], "t_name": p.get("p_name", ""),
                "t_aid": p.get("p_aid", ""), "t_desc": p.get("p_desc", ""),
                "t_x": p["p_x"], "t_y": p["p_y"], "t_w": p["p_w"], "t_h": p["p_h"],
                "t_enabled": p.get("p_enabled", True), "t_focus": p.get("p_focus", False),
                "t_value": p.get("p_value", ""), "t_readonly": p.get("p_readonly", False),
                "t_offscreen": p.get("p_offscreen", False),
            })
            tree_keys.add(key)
    return merged


def _filter_node(node: dict) -> bool:
    """Return True if node should be included in output."""
    role = node["t_role"]
    w, h = node["t_w"], node["t_h"]
    if w <= 0 or h <= 0:
        return False
    if node.get("t_offscreen", False):
        return False
    name, value = node["t_name"], node["t_value"]
    enabled = node.get("t_enabled", True)
    readonly = node.get("t_readonly", False)
    if role in SKIP_NAMELESS and not name and not value:
        return False
    action_tag = classify_element(role, enabled, readonly)
    if action_tag == "none" and not name and not value:
        return False
    return True


def _render_node(node: dict, node_id: str) -> str:
    """Render a single node as a text line."""
    role = node["t_role"]
    name, value = node["t_name"], node["t_value"]
    enabled = node.get("t_enabled", True)
    readonly = node.get("t_readonly", False)
    depth = node.get("t_depth", 0)
    action_tag = classify_element(role, enabled, readonly)

    tag_str = f"[{action_tag.upper()}]" if action_tag != "none" else ""
    line = f"{'  ' * (depth + 1)}{node_id}. {tag_str} {role}"
    line += f" '{name}'" * bool(name)
    if value:
        vis = value[:80] + "\u2026" if len(value) > 80 else value
        line += f" val='{vis}'"
    line += " disabled" * (not enabled)
    line += " *" * node["t_focus"]
    return line


def build_context(screen: dict, focused: dict, windows: list[dict],
                  z_order: dict, tree_nodes: list[dict], probes: list[dict]) -> tuple[str, list[dict]]:
    book_entries: list[dict] = []
    output_lines: list[str] = []
    focused_hwnd = focused.get("focused_hwnd", 0)
    focused_title = focused.get("focused_title", "")

    # Merge probe data into tree with proper window assignment
    merged_nodes = merge_probe_into_tree(tree_nodes, probes, windows, z_order)

    # Assign unassigned nodes to focused window
    for node in merged_nodes:
        if not node.get("t_hwnd"):
            node["t_hwnd"] = focused_hwnd
        if not node.get("t_wnd"):
            node["t_wnd"] = focused_title

    # Determine which windows to show (focused + any target windows)
    target_wnd_names: list[str] = []
    for win in windows:
        if win["wnd_target"]:
            target_wnd_names.append(win["wnd_name"])
    if focused_title and focused_title not in target_wnd_names:
        target_wnd_names.insert(0, focused_title)

    # Group nodes by window name
    wnd_groups: dict[str, list[dict]] = {}
    for node in merged_nodes:
        wnd = node.get("t_wnd") or ""
        wnd_groups.setdefault(wnd, []).append(node)

    # Render target windows in order, then other windows with elements
    seq = 0
    rendered_wnds: set[str] = set()

    for wnd_name in target_wnd_names:
        nodes = wnd_groups.get(wnd_name, [])
        if not nodes:
            continue
        output_lines.append(f"[{wnd_name}]")
        rendered_wnds.add(wnd_name)
        for node in nodes:
            if not _filter_node(node):
                continue
            seq += 1
            node_id = str(seq)
            role = node["t_role"]
            name, value = node["t_name"], node["t_value"]
            enabled = node.get("t_enabled", True)
            readonly = node.get("t_readonly", False)
            action_tag = classify_element(role, enabled, readonly)
            book_entries.append({
                "id": node_id, "role": role, "name": name, "value": value,
                "hwnd": node["t_hwnd"], "wnd": node["t_wnd"],
                "px": node["t_x"], "py": node["t_y"],
                "pw": node["t_w"], "ph": node["t_h"],
                "enabled": enabled, "readonly": readonly, "action": action_tag,
            })
            output_lines.append(_render_node(node, node_id))

    # Show other windows that have elements (non-target) as collapsed list
    other_windows: list[str] = []
    for wnd_name, nodes in wnd_groups.items():
        if wnd_name in rendered_wnds or not wnd_name:
            continue
        visible_count = sum(1 for n in nodes if _filter_node(n))
        if visible_count > 0:
            other_windows.append(f"  [{wnd_name}] ({visible_count} elements)")

    if other_windows:
        output_lines.append("")
        output_lines.append("OTHER WINDOWS:")
        output_lines.extend(other_windows)

    # Z-order section
    z_list = z_order.get("z_order", [])
    if z_list:
        output_lines.append("")
        output_lines.append("Z-ORDER (front to back):")
        for entry in z_list[:8]:
            marker = " [FOCUSED]" if entry["z"] == 0 else ""
            output_lines.append(f"  z={entry['z']} \"{entry['title']}\"{marker}")

    return "\n".join(output_lines), book_entries


def pipeline(raw_lines: list[str]) -> tuple[str, list[dict]]:
    screen, hwnds, focused, probes, windows, z_order, tree_nodes = parse_raw(raw_lines)
    return build_context(screen, focused, windows, z_order, tree_nodes, probes)
