from __future__ import annotations
import hashlib, math, re, time
from dataclasses import dataclass
from typing import Any

from config import (
    TREE_WALK_TIMEOUT, PROBE_STEP_PX, PROBE_FOREGROUND_DELAY, PROBE_SAMPLE_DELAY,
    PROBE_SINE_AMPLITUDE_RATIO, PROBE_SINE_PERIOD_STEPS,
    READ_TEXT_MAX_LENGTH, SCREEN_ELEMENT_VALUE_LIMIT,
    TERMINAL_CONTEXT_TAIL_LINES,
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
import ctypes
import ctypes.wintypes as W

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
POPUP_CLASSES = frozenset({
    "TaskListThumbnailWnd", "#32768", "ToolTipClass",
    "Windows.UI.Core.CoreWindow",
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
    content_hash: str
    semantic_hash: str


def observe() -> ObserveResult:
    set_dpi_aware()
    init()
    screen_w = user32.GetSystemMetrics(0)
    screen_h = user32.GetSystemMetrics(1)
    focused_hwnd = int(user32.GetForegroundWindow())
    focused_title = get_window_title(focused_hwnd)

    windows = _enumerate_windows()
    z_order = _get_z_order()

    probe_nodes: list[dict[str, Any]] = []
    regions = _probe_regions(windows, z_order, focused_hwnd, screen_w, screen_h)
    target_wnd = _target_windows(focused_title, regions)
    saved = W.POINT()
    user32.GetCursorPos(ctypes.byref(saved))
    for x0, y0, x1, y1, wname, whwnd in regions:
        if whwnd:
            user32.SetForegroundWindow(W.HWND(whwnd))
            time.sleep(PROBE_FOREGROUND_DELAY)
        _probe_region(probe_nodes, PROBE_STEP_PX, x0, y0, x1, y1, wname, whwnd)
    user32.SetCursorPos(saved.x, saved.y)

    probe_decision = {"enabled": True, "reason": "primary_probe", "probe_actionable": _target_action_count(_classify(_clone_nodes(probe_nodes)), target_wnd)}
    tree_decision = _tree_decision(probe_decision)

    tree_nodes: list[dict[str, Any]] = []
    tree_windows = _tree_windows(windows, target_wnd, regions)
    if tree_decision["enabled"]:
        for wnd in tree_windows:
            _tree_walk(tree_nodes, wnd["element"], str(wnd["name"]), int(wnd["hwnd"]),
                       TREE_WALK_TIMEOUT)
    else:
        for wnd in tree_windows:
            if str(wnd["name"]) == "Taskbar":
                _tree_walk(tree_nodes, wnd["element"], "Taskbar", int(wnd["hwnd"]),
                           TREE_WALK_TIMEOUT)

    merged = _merge(tree_nodes, probe_nodes)
    classified = _classify(merged)

    z_titles = [str(e["title"]) for e in z_order]
    wnd_rank = {t: i for i, t in enumerate(z_titles)}
    classified.sort(key=lambda n: (wnd_rank.get(n["wnd"], 999), n["depth"], n["y"], n["x"]))

    text, book = _render(classified, target_wnd, focused_title)
    semantic_text = _semantic_render(classified, target_wnd, focused_title)
    content_hash = hashlib.md5(text.encode("utf-8", errors="surrogatepass")).hexdigest()
    semantic_hash = hashlib.md5(semantic_text.encode("utf-8", errors="surrogatepass")).hexdigest()

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
        content_hash=content_hash, semantic_hash=semantic_hash,
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
            if not value and role in ("Text", "Document", "Edit", "Pane"):
                tc = get_text_content(raw_el, READ_TEXT_MAX_LENGTH)
                if tc:
                    value = _filter_terminal_text(tc)
                    has_text_pattern = True
                else:
                    has_text_pattern = False
            else:
                has_text_pattern = False
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


def _probe_regions(windows: list[dict[str, Any]], z_order: list[dict[str, Any]], focused_hwnd: int, sw: int, sh: int) -> list[tuple[int, int, int, int, str, int]]:
    return [(0, 0, sw, sh, "Desktop", 0)]


def _window_region(wnd: dict[str, Any]) -> tuple[int, int, int, int, str, int]:
    x = int(wnd["x"])
    y = int(wnd["y"])
    return (x, y, x + int(wnd["w"]), y + int(wnd["h"]), str(wnd["name"]), int(wnd["hwnd"]))


def _top_window_region(windows: list[dict[str, Any]], z_order: list[dict[str, Any]]) -> tuple[int, int, int, int, str, int] | None:
    by_hwnd = {int(wnd["hwnd"]): wnd for wnd in windows}
    for entry in z_order:
        wnd = by_hwnd.get(int(entry["hwnd"]))
        if wnd is None:
            continue
        region = _window_region(wnd)
        if not _is_desktop_window(region):
            return region
    return None


def _is_desktop_window(region: tuple[int, int, int, int, str, int]) -> bool:
    return _region_name(region) in ("Desktop", "Program Manager")


def _target_windows(focused_title: str, regions: list[tuple[int, int, int, int, str, int]]) -> set[str]:
    if any(_is_desktop_window(r) for r in regions):
        return set()
    region_titles = {_region_name(r) for r in regions if _region_name(r) and not _is_desktop_window(r)}
    if focused_title and (not region_titles or focused_title in region_titles):
        return {focused_title}
    return region_titles


def _tree_windows(windows: list[dict[str, Any]], target_wnd: set[str], regions: list[tuple[int, int, int, int, str, int]]) -> list[dict[str, Any]]:
    if not target_wnd or any(_is_desktop_window(region) for region in regions):
        return windows
    selected = [wnd for wnd in windows if str(wnd["name"]) in target_wnd or str(wnd["name"]) == "Taskbar"]
    if selected:
        return selected
    return windows


def _region_name(region: tuple[int, int, int, int, str, int]) -> str:
    return str(region[4])


def _tree_decision(probe_decision: dict[str, Any]) -> dict[str, Any]:
    action_count = int(probe_decision.get("probe_actionable", 0))
    enabled = action_count < 1
    reason = "probe_actionable_empty" if enabled else "probe_actionable_sufficient"
    return {"enabled": enabled, "reason": reason, "probe_actionable": action_count}


def _topmost_popup(z_order: list[dict[str, Any]]) -> bool:
    if not z_order:
        return False
    return get_window_class(int(z_order[0]["hwnd"])) in POPUP_CLASSES


def _target_action_count(nodes: list[dict[str, Any]], target_wnd: set[str]) -> int:
    count = 0
    for n in nodes:
        wnd = str(n.get("wnd", ""))
        if target_wnd and wnd not in target_wnd and wnd != "Taskbar":
            continue
        if n.get("action") != "none":
            count += 1
    return count


def _probe_region(out: list[dict[str, Any]], step: int, x0: int, y0: int, x1: int, y1: int, wname: str, whwnd: int) -> None:
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
                if not value:
                    text_content = get_text_content(el, READ_TEXT_MAX_LENGTH)
                    if text_content:
                        value = _filter_terminal_text(text_content)
                r = get_rect(el)
                if not name and not value:
                    continue
                rx, ry, rw, rh = r
                out.append({
                    "wnd": wname, "hwnd": whwnd, "depth": 0,
                    "role": role, "name": name,
                    "x": rx, "y": ry, "w": rw, "h": rh,
                    "enabled": get_bool(el, UIA_IS_ENABLED),
                    "value": value,
                    "readonly": get_legacy_readonly(el),
                    "offscreen": get_bool(el, UIA_IS_OFFSCREEN),
                })
            except OSError:
                continue


def _filter_terminal_text(raw: str) -> str:
    lines = raw.splitlines()
    stripped = [l.rstrip() for l in lines if l.rstrip()]
    if not stripped:
        return ""
    kept: list[str] = []
    for line in stripped:
        if _is_runtime_log_line(line) or _is_tui_dashboard_line(line):
            continue
        kept.append(line)
    if not kept:
        kept = stripped
    last_sep = -1
    for i in range(len(kept) - 1, -1, -1):
        if " - Completed in " in kept[i]:
            last_sep = i
            break
    if last_sep >= 0 and last_sep < len(kept) - 1:
        tail = kept[last_sep + 1:]
    else:
        tail = kept
    if len(tail) > TERMINAL_CONTEXT_TAIL_LINES:
        tail = tail[-TERMINAL_CONTEXT_TAIL_LINES:]
    return "\n".join(tail)


def _is_runtime_log_line(line: str) -> bool:
    compact = line.strip()
    if not compact.startswith("{"):
        return False
    markers = ('"version":', '"phase":', '"agent_id":', '"timestamp_utc":')
    return all(marker in compact for marker in markers[:2])


def _is_tui_dashboard_line(line: str) -> bool:
    compact = line.strip()
    if not compact:
        return False
    if "\x1bP" in compact:
        return True
    if compact.startswith("endgame-ai |"):
        return True
    if compact in ("LORENZ", "STAGNATION"):
        return True
    prefixes = ("mode=", "goal:", "focus:", "plan[", "plan:", "action:", "result:", "children:", "lorenz:")
    return any(compact.startswith(prefix) for prefix in prefixes)


def _compact_display_value(value: str) -> str:
    if len(value) <= SCREEN_ELEMENT_VALUE_LIMIT:
        return value
    digest = hashlib.sha256(value.encode("utf-8", errors="surrogatepass")).hexdigest()
    return f"[chars={len(value)} sha256={digest[:16]}]"


def _merge(tree_nodes: list[dict[str, Any]], probe_nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys: set[tuple[Any, ...]] = set()
    merged: list[dict[str, Any]] = []
    for n in tree_nodes:
        k = (n["role"], n["name"], n["x"], n["y"], n["w"], n["h"])
        keys.add(k)
        merged.append(n)
    for p in probe_nodes:
        k = (p["role"], p["name"], p["x"], p["y"], p["w"], p["h"])
        if k not in keys:
            merged.append(p)
            keys.add(k)
    return merged


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


def _render(nodes: list[dict[str, Any]], target_wnd: set[str], focused_title: str) -> tuple[str, dict[str, BookEntry]]:
    book: dict[str, BookEntry] = {}
    wnd_groups: dict[str, list[dict[str, Any]]] = {}
    for n in nodes:
        wnd = n["wnd"]
        if target_wnd and wnd not in target_wnd and wnd != "Taskbar":
            continue
        if n["action"] == "none":
            continue
        wnd_groups.setdefault(wnd, []).append(n)

    lines: list[str] = []
    seq = 0
    wnd_list = sorted(wnd_groups.keys(), key=lambda w: (w != focused_title, w))
    for i, wnd in enumerate(wnd_list):
        is_last_wnd = i == len(wnd_list) - 1
        prefix = "└── " if is_last_wnd else "├── "
        focused = " (focused)" if wnd == focused_title else ""
        lines.append(f"{prefix}{wnd}{focused}")
        elements = wnd_groups[wnd]
        child_prefix = "    " if is_last_wnd else "│   "
        for j, n in enumerate(elements):
            seq += 1
            nid = str(seq)
            is_last_el = j == len(elements) - 1
            connector = "└── " if is_last_el else "├── "
            label = n.get("name", "")
            if n.get("value") and n["action"] == "write":
                val = _compact_display_value(str(n["value"]))
                desc = f'[{nid}] "{label}" = "{val}"' if label else f'[{nid}] "{val}"'
            elif label:
                desc = f'[{nid}] "{label}"'
            else:
                desc = f'[{nid}] {n["role"]}'
            if not n.get("enabled"):
                desc += " (disabled)"
            lines.append(f"{child_prefix}{connector}{desc}")
            book[nid] = BookEntry(
                id=nid, role=n["role"], name=label,
                value=n.get("value", ""), hwnd=n["hwnd"], wnd=wnd,
                px=n["x"], py=n["y"], pw=n["w"], ph=n["h"],
                enabled=n.get("enabled", True), readonly=n.get("readonly", False),
                action=n["action"],
            )
    return "\n".join(lines), book


_DYNAMIC_TEXT_PATTERNS = (
    r"\b\d+:\d+(?::\d+)?\s*(?:am|pm)?\b",
    r"\b\d+(?:\.\d+)?\s*(?:%|bps|kbps|mbps|gbps|hz|khz|mhz|ghz|kb|mb|gb|tb|ms|sec|s)\b",
    r"\b[\da-f]+(?::[\da-f]*)+%?\w*\b",
    r"\b\d+(?:\.\d+)?\b",
)


def _semantic_render(nodes: list[dict[str, Any]], target_wnd: set[str], focused_title: str) -> str:
    lines: list[str] = []
    for n in nodes:
        wnd = str(n["wnd"])
        if target_wnd and wnd not in target_wnd and wnd != "Taskbar":
            continue
        parts = [
            _normalize_dynamic_text(wnd),
            "focused" if wnd == focused_title else "",
            str(n["role"]),
            str(n["action"]),
            _normalize_dynamic_text(str(n.get("name", ""))),
            _normalize_dynamic_text(str(n.get("value", ""))),
            "enabled" if n.get("enabled", True) else "disabled",
            "readonly" if n.get("readonly", False) else "editable",
        ]
        lines.append("|".join(parts))
    return "\n".join(lines)


def _normalize_dynamic_text(text: str) -> str:
    normalized = " ".join(text.casefold().split())
    for pattern in _DYNAMIC_TEXT_PATTERNS:
        normalized = re.sub(pattern, "<dynamic>", normalized, flags=re.IGNORECASE)
    return normalized


def _clone_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(n) for n in nodes]




