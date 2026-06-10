from __future__ import annotations
import ctypes
import ctypes.wintypes as W
import math
import time
from dataclasses import dataclass
from typing import Any

from config import (
    TREE_WALK_TIMEOUT, PROBE_STEP_PX, PROBE_FOREGROUND_DELAY, PROBE_SAMPLE_DELAY,
    PROBE_SINE_AMPLITUDE_RATIO, PROBE_SINE_PERIOD_STEPS,
    READ_TEXT_MAX_LENGTH, SCREEN_ELEMENT_VALUE_LIMIT, TERMINAL_CONTEXT_TAIL_LINES,
)
from win32 import (
    user32, init, set_dpi_aware,
    get_str, get_int, get_bool, get_rect,
    get_legacy_value, get_legacy_readonly, get_text_content, element_from_point,
    get_children, get_hwnd, get_runtime_id, get_root,
    get_window_class, get_window_title,
    UIA_CONTROL_TYPE, UIA_NAME, UIA_IS_ENABLED,
    UIA_IS_OFFSCREEN, CONTROL_TYPE_MAP,
)

__all__ = ["observe", "ObserveResult", "BookEntry"]

ACTIONABLE_ROLES = frozenset({
    "Button", "Edit", "ComboBox", "ListItem", "Hyperlink", "MenuItem",
    "TabItem", "SplitButton", "CheckBox", "RadioButton", "Slider",
    "Document", "Text", "ScrollBar", "TreeItem", "DataItem", "Custom",
})
CLICKABLE_ROLES = frozenset({
    "Button", "MenuItem", "ListItem", "Hyperlink", "TabItem", "TreeItem",
    "SplitButton", "CheckBox", "RadioButton", "Slider", "ScrollBar",
    "DataItem", "Document",
})
WRITABLE_ROLES = frozenset({"Edit", "ComboBox"})
SKIP_NAMELESS = frozenset({
    "Pane", "Group", "Custom", "Image", "Separator", "Thumb",
    "ProgressBar", "Header", "HeaderItem",
})

@dataclass(slots=True)
class BookEntry:
    id: str
    role: str
    name: str
    value: str
    hwnd: int
    wnd: str
    px: int
    py: int
    pw: int
    ph: int
    enabled: bool
    readonly: bool
    action: str

@dataclass(slots=True)
class ObserveResult:
    context_text: str
    book: dict[str, BookEntry]
    focused_title: str
    windows: list[dict[str, Any]]
    desktop_summary: str

def observe() -> ObserveResult:
    set_dpi_aware()
    init()
    screen_w = user32.GetSystemMetrics(0)
    screen_h = user32.GetSystemMetrics(1)
    focused_hwnd = int(user32.GetForegroundWindow())
    focused_title = get_window_title(focused_hwnd)

    windows = _enumerate_windows()
    z_order = _get_z_order()
    regions = _probe_regions(windows, focused_title, focused_hwnd, screen_w, screen_h)

    probe_nodes: list[dict[str, Any]] = []
    saved = W.POINT()
    user32.GetCursorPos(ctypes.byref(saved))
    for x0, y0, x1, y1, wname, whwnd in regions:
        if whwnd:
            user32.SetForegroundWindow(W.HWND(whwnd))
            time.sleep(PROBE_FOREGROUND_DELAY)
        _probe_region(probe_nodes, PROBE_STEP_PX, x0, y0, x1, y1, wname, whwnd)
    user32.SetCursorPos(saved.x, saved.y)

    tree_nodes: list[dict[str, Any]] = []
    for wnd in _tree_targets(windows, focused_title):
        _tree_walk(tree_nodes, wnd["element"], str(wnd["name"]), int(wnd["hwnd"]), TREE_WALK_TIMEOUT)

    merged = _merge(probe_nodes, tree_nodes)
    z_titles = [str(e["title"]) for e in z_order]
    wnd_rank = {t: i for i, t in enumerate(z_titles)}
    classified = _classify(merged)
    classified.sort(key=lambda n: (wnd_rank.get(n["wnd"], 999), n["depth"], n["y"], n["x"]))

    text, book = _render(classified, focused_title)

    desktop_lines = [f"Desktop ({screen_w}x{screen_h})"]
    for i, entry in enumerate(z_order[:10]):
        is_last = i == min(len(z_order), 10) - 1
        connector = "└── " if is_last else "├── "
        marker = " (focused)" if entry["title"] == focused_title else ""
        desktop_lines.append(f"{connector}{entry['title']}{marker}")

    return ObserveResult(
        context_text=text, book=book, focused_title=focused_title,
        windows=[{"name": w["name"], "hwnd": w["hwnd"]} for w in windows],
        desktop_summary="\n".join(desktop_lines),
    )

def _enumerate_windows() -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    for top_el in get_children(get_root()):
        try:
            x, y, w, h = get_rect(top_el)
            ct = get_int(top_el, UIA_CONTROL_TYPE)
            role = CONTROL_TYPE_MAP.get(ct, "")
            if w <= 0 or h <= 0 or role not in ("Window", "Pane"):
                continue
            name = get_str(top_el, UIA_NAME)
            el_hwnd = get_hwnd(top_el)
            windows.append({"element": top_el, "role": role, "name": name,
                            "hwnd": el_hwnd, "x": x, "y": y, "w": w, "h": h,
                            "class": get_window_class(el_hwnd)})
        except OSError:
            continue
    return windows

def _get_z_order() -> list[dict[str, Any]]:
    hwnd = user32.GetTopWindow(None)
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    z = 0
    while hwnd:
        if user32.IsWindowVisible(hwnd):
            title = get_window_title(int(hwnd))
            if title and title not in seen:
                result.append({"z": z, "hwnd": int(hwnd), "title": title})
                seen.add(title)
                z += 1
        hwnd = user32.GetWindow(hwnd, 2)
    return result

def _probe_regions(
    windows: list[dict[str, Any]], focused_title: str, focused_hwnd: int, sw: int, sh: int,
) -> list[tuple[int, int, int, int, str, int]]:
    for wnd in windows:
        if str(wnd["name"]) == focused_title or int(wnd["hwnd"]) == focused_hwnd:
            x, y, ww, wh = int(wnd["x"]), int(wnd["y"]), int(wnd["w"]), int(wnd["h"])
            return [(x, y, x + ww, y + wh, str(wnd["name"]), int(wnd["hwnd"]))]
    return [(0, 0, sw, sh, focused_title or "Desktop", focused_hwnd)]

def _tree_targets(windows: list[dict[str, Any]], focused_title: str) -> list[dict[str, Any]]:
    if focused_title:
        matched = [w for w in windows if str(w["name"]) == focused_title]
        if matched:
            return matched
    return windows

def _probe_region(
    out: list[dict[str, Any]], step: int,
    x0: int, y0: int, x1: int, y1: int, wname: str, whwnd: int,
) -> None:
    seen_rids: set[Any] = set()
    amp = step * PROBE_SINE_AMPLITUDE_RATIO
    freq = 2 * math.pi / (step * PROBE_SINE_PERIOD_STEPS)
    for y in range(y0 + step // 2, y1, step):
        for x in range(x0 + step // 2, x1, step):
            py = max(y0, min(y1 - 1, y + int(amp * math.sin(freq * x))))
            user32.SetCursorPos(x, py)
            time.sleep(PROBE_SAMPLE_DELAY)
            try:
                el = element_from_point(x, py)
            except OSError:
                continue
            if not el:
                continue
            try:
                rid = get_runtime_id(el)
                if rid and rid in seen_rids:
                    continue
                if rid:
                    seen_rids.add(rid)
                ct = get_int(el, UIA_CONTROL_TYPE)
                role = CONTROL_TYPE_MAP.get(ct, "")
                if not role:
                    continue
                name = get_str(el, UIA_NAME)
                value = get_legacy_value(el)
                has_text_pattern = False
                if not value:
                    text_content = get_text_content(el, READ_TEXT_MAX_LENGTH)
                    if text_content:
                        value = _filter_terminal_text(text_content)
                        has_text_pattern = True
                rx, ry, rw, rh = get_rect(el)
                if not name and not value:
                    continue
                out.append({
                    "wnd": wname, "hwnd": whwnd, "depth": 0,
                    "role": role, "name": name,
                    "x": rx, "y": ry, "w": rw, "h": rh,
                    "enabled": get_bool(el, UIA_IS_ENABLED),
                    "value": value,
                    "readonly": get_legacy_readonly(el),
                    "offscreen": get_bool(el, UIA_IS_OFFSCREEN),
                    "has_text_pattern": has_text_pattern,
                })
            except OSError:
                continue

def _tree_walk(out: list[dict[str, Any]], el: Any, wnd_name: str, wnd_hwnd: int, timeout: float) -> None:
    from collections import deque
    start = time.perf_counter()
    queue: deque[tuple[Any, int]] = deque()
    for child in get_children(el):
        queue.append((child, 1))
    while queue:
        if time.perf_counter() - start > timeout:
            break
        raw_el, depth = queue.popleft()
        try:
            x, y, w, h = get_rect(raw_el)
            ct = get_int(raw_el, UIA_CONTROL_TYPE)
        except OSError:
            continue
        role = CONTROL_TYPE_MAP.get(ct, "")
        if not role:
            try:
                for c in get_children(raw_el):
                    queue.append((c, depth))
            except OSError:
                pass
            continue
        try:
            value = get_legacy_value(raw_el) if role in ACTIONABLE_ROLES else ""
            has_text_pattern = False
            if not value and role in ("Text", "Document", "Edit", "Pane"):
                tc = get_text_content(raw_el, READ_TEXT_MAX_LENGTH)
                if tc:
                    value = _filter_terminal_text(tc)
                    has_text_pattern = True
            out.append({
                "wnd": wnd_name, "hwnd": wnd_hwnd, "depth": depth,
                "role": role, "name": get_str(raw_el, UIA_NAME),
                "x": x, "y": y, "w": w, "h": h,
                "enabled": get_bool(raw_el, UIA_IS_ENABLED),
                "value": value,
                "readonly": get_legacy_readonly(raw_el) if role in ACTIONABLE_ROLES else False,
                "offscreen": get_bool(raw_el, UIA_IS_OFFSCREEN),
                "has_text_pattern": has_text_pattern,
            })
        except OSError:
            continue
        try:
            for c in get_children(raw_el):
                queue.append((c, depth + 1))
        except OSError:
            pass

def _node_key(n: dict[str, Any]) -> tuple[Any, ...]:
    return (n["role"], n.get("name", ""), n["x"], n["y"], n["w"], n["h"])

def _merge(probe_nodes: list[dict[str, Any]], tree_nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Probe is primary — hover discoveries land first; tree adds depth and gaps."""
    index: dict[tuple[Any, ...], int] = {}
    merged: list[dict[str, Any]] = []
    for node in probe_nodes:
        key = _node_key(node)
        index[key] = len(merged)
        merged.append(node)
    for node in tree_nodes:
        key = _node_key(node)
        if key in index:
            hit = merged[index[key]]
            hit["depth"] = max(int(hit.get("depth", 0)), int(node.get("depth", 0)))
            hit["has_text_pattern"] = hit.get("has_text_pattern") or node.get("has_text_pattern")
        else:
            merged.append(node)
    return merged

def _filter_terminal_text(raw: str) -> str:
    lines = raw.splitlines()
    stripped = [l.rstrip() for l in lines if l.rstrip()]
    if not stripped:
        return ""
    kept = [l for l in stripped if not _is_runtime_log_line(l) and not _is_tui_dashboard_line(l)]
    if not kept:
        kept = stripped
    last_sep = -1
    for i in range(len(kept) - 1, -1, -1):
        if " - Completed in " in kept[i]:
            last_sep = i
            break
    tail = kept[last_sep + 1:] if last_sep >= 0 and last_sep < len(kept) - 1 else kept
    if len(tail) > TERMINAL_CONTEXT_TAIL_LINES:
        tail = tail[-TERMINAL_CONTEXT_TAIL_LINES:]
    return "\n".join(tail)

def _is_runtime_log_line(line: str) -> bool:
    compact = line.strip()
    return compact.startswith("{") and '"phase":' in compact

def _is_tui_dashboard_line(line: str) -> bool:
    compact = line.strip()
    return bool(compact) and ("\x1bP" in compact or compact.startswith("endgame-ai |"))

def _classify(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tab_rects: list[tuple[int, int, int, int]] = []
    for n in nodes:
        if n["role"] == "TabItem":
            tab_rects.append((n["x"], n["y"], n["x"] + n["w"], n["y"] + n["h"]))

    result: list[dict[str, Any]] = []
    for n in nodes:
        role = n["role"]
        w, h = n["w"], n["h"]
        if w <= 0 or h <= 0 or n.get("offscreen"):
            continue
        name = n.get("name", "")
        value = n.get("value", "")
        enabled = n.get("enabled", True)
        readonly = n.get("readonly", False)
        if role in SKIP_NAMELESS and not name and not value:
            continue
        inside_tab = False
        if role != "TabItem":
            nx, ny = n["x"], n["y"]
            for tx, ty, tx2, ty2 in tab_rects:
                if tx <= nx and ny >= ty and nx + w <= tx2 and ny + h <= ty2:
                    inside_tab = True
                    break
        if enabled and role in WRITABLE_ROLES and not readonly and not inside_tab:
            action = "write"
        elif enabled and n.get("has_text_pattern") and not inside_tab:
            action = "write"
        elif enabled and role in CLICKABLE_ROLES:
            action = "click"
        else:
            action = "none"
        if action == "none" and not name and not value:
            continue
        n["action"] = action
        result.append(n)
    return result

def _clip_value(value: str) -> str:
    limit = SCREEN_ELEMENT_VALUE_LIMIT
    return value if len(value) <= limit else value[:limit] + "…"

def _render(nodes: list[dict[str, Any]], focused_title: str) -> tuple[str, dict[str, BookEntry]]:
    book: dict[str, BookEntry] = {}
    wnd_groups: dict[str, list[dict[str, Any]]] = {}
    for n in nodes:
        wnd_groups.setdefault(n["wnd"], []).append(n)

    lines: list[str] = []
    seq = 0
    wnd_list = sorted(wnd_groups.keys(), key=lambda w: (w != focused_title, w))
    for i, wnd in enumerate(wnd_list):
        is_last_wnd = i == len(wnd_list) - 1
        branch = "    " if is_last_wnd else "│   "
        focused = " (focused)" if wnd == focused_title else ""
        lines.append(f"{'└── ' if is_last_wnd else '├── '}{wnd}{focused}")
        for n in wnd_groups[wnd]:
            depth = max(1, int(n.get("depth", 1)))
            indent = branch + ("│   " * (depth - 1))
            label = str(n.get("name", ""))
            role = str(n.get("role", ""))
            if n.get("action") != "none":
                seq += 1
                nid = str(seq)
                if n.get("value") and n["action"] == "write":
                    val = _clip_value(str(n["value"]))
                    desc = f'[{nid}] {role} "{label}" = "{val}"' if label else f'[{nid}] {role} "{val}"'
                elif label:
                    desc = f'[{nid}] {role} "{label}"'
                else:
                    desc = f'[{nid}] {role}'
                if not n.get("enabled"):
                    desc += " (disabled)"
                book[nid] = BookEntry(
                    id=nid, role=role, name=label,
                    value=str(n.get("value", "")), hwnd=n["hwnd"], wnd=wnd,
                    px=n["x"], py=n["y"], pw=n["w"], ph=n["h"],
                    enabled=n.get("enabled", True), readonly=n.get("readonly", False),
                    action=n["action"],
                )
            else:
                val = _clip_value(str(n.get("value", ""))) if n.get("value") else ""
                if label and val:
                    desc = f'{role} "{label}" = "{val}"'
                elif label:
                    desc = f'{role} "{label}"'
                elif val:
                    desc = f'{role} "{val}"'
                else:
                    desc = role
            lines.append(f"{indent}├── {desc}")
    return "\n".join(lines), book