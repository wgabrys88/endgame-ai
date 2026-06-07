from __future__ import annotations
from config import ZERO_INT, ONE_INT, TWO_INT
import hashlib, math, re, time
from dataclasses import dataclass
from typing import Any

from config import (
    TREE_WALK_TIMEOUT, PROBE_STEP_PX, PROBE_FOREGROUND_DELAY, PROBE_SAMPLE_DELAY,
    PROBE_SINE_AMPLITUDE_RATIO, PROBE_SINE_PERIOD_STEPS, WINDOW_SORT_FALLBACK_RANK,
    READ_TEXT_MAX_LENGTH, DURATION_MS_PER_SECOND, OBSERVER_PROBE_ACTION_MIN,
)
from win32 import (
    user32, init, set_dpi_aware, ensure_tree_walker,
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
ROLE_SHORT = {
    "Button": "Btn", "Hyperlink": "Lnk", "Edit": "Edt", "ComboBox": "Cmb",
    "Slider": "Sld", "TabItem": "Tab", "ListItem": "Lst", "MenuItem": "Itm",
    "CheckBox": "Chk", "RadioButton": "Rad", "ScrollBar": "Scr",
    "SplitButton": "Spl", "DataItem": "Dat", "Document": "Doc", "TreeItem": "Tre",
}
LEGEND = ""


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
    content_hash: str
    semantic_hash: str
    trace: dict[str, Any]


def observe() -> ObserveResult:
    timing: dict[str, dict[str, int]] = {}
    t_start = _profile_start()
    set_dpi_aware()
    init()
    screen_w = user32.GetSystemMetrics(ZERO_INT)
    screen_h = user32.GetSystemMetrics(ONE_INT)
    focused_hwnd = int(user32.GetForegroundWindow())
    focused_title = get_window_title(focused_hwnd)
    _profile_add(timing, "setup", t_start)

    t_start = _profile_start()
    windows = _enumerate_windows()
    _profile_add(timing, "enumerate_windows", t_start)
    t_start = _profile_start()
    z_order = _get_z_order()
    _profile_add(timing, "z_order", t_start)

    target_wnd: set[str] = {focused_title} if focused_title else set()

    probe_nodes: list[dict[str, Any]] = []
    probe_trace: list[dict[str, Any]] = []
    t_start = _profile_start()
    regions = _probe_regions(windows, z_order, focused_hwnd, screen_w, screen_h)
    ensure_tree_walker()
    saved = W.POINT()
    user32.GetCursorPos(ctypes.byref(saved))
    for x0, y0, x1, y1, wname, whwnd in regions:
        if whwnd:
            user32.SetForegroundWindow(W.HWND(whwnd))
            time.sleep(PROBE_FOREGROUND_DELAY)
        _probe_region(probe_nodes, probe_trace, PROBE_STEP_PX, x0, y0, x1, y1, wname, whwnd)
    user32.SetCursorPos(saved.x, saved.y)
    _profile_add(timing, "probe", t_start)

    probe_decision = {"enabled": True, "reason": "primary_probe", "probe_actionable": _target_action_count(_classify(_clone_nodes(probe_nodes)), target_wnd)}
    tree_decision = _tree_decision(probe_decision)

    tree_nodes: list[dict[str, Any]] = []
    tree_trace: list[dict[str, Any]] = []
    t_start = _profile_start()
    if tree_decision["enabled"]:
        for wnd in windows:
            _tree_walk(tree_nodes, tree_trace, wnd["element"], str(wnd["name"]), int(wnd["hwnd"]),
                       TREE_WALK_TIMEOUT)
    _profile_add(timing, "tree_walk", t_start)

    t_start = _profile_start()
    merged = _merge(tree_nodes, probe_nodes)
    merged_nodes = _clone_nodes(merged)
    classified = _classify(merged)
    _profile_add(timing, "merge_classify", t_start)

    t_start = _profile_start()
    z_titles = [str(e["title"]) for e in z_order]
    wnd_rank = {t: i for i, t in enumerate(z_titles)}
    classified.sort(key=lambda n: (wnd_rank.get(n["wnd"], WINDOW_SORT_FALLBACK_RANK), n["depth"], n["y"], n["x"]))

    text, book = _render(classified, target_wnd, focused_title)
    semantic_text = _semantic_render(classified, target_wnd, focused_title)
    content_hash = hashlib.md5(text.encode("utf-8", errors="surrogatepass")).hexdigest()
    semantic_hash = hashlib.md5(semantic_text.encode("utf-8", errors="surrogatepass")).hexdigest()
    _profile_add(timing, "render_hash", t_start)
    trace = {
        "screen": {"width": screen_w, "height": screen_h},
        "focused": {"hwnd": focused_hwnd, "title": focused_title},
        "windows": _public_windows(windows),
        "z_order": z_order,
        "probe_regions": _public_regions(regions),
        "probe_decision": probe_decision,
        "probe_samples": probe_trace,
        "probe_nodes_raw": _clone_nodes(probe_nodes),
        "tree_decision": tree_decision,
        "tree_samples": tree_trace,
        "tree_nodes_raw": _clone_nodes(tree_nodes),
        "merged_nodes": merged_nodes,
        "classified_nodes": _clone_nodes(classified),
        "rendered_text": text,
        "semantic_text": semantic_text,
        "book": _book_trace(book),
        "content_hash": content_hash,
        "semantic_hash": semantic_hash,
        "timing": timing,
    }

    return ObserveResult(
        context_text=text, book=book, focused_title=focused_title,
        windows=[{"name": w["name"], "hwnd": w["hwnd"]} for w in windows],
        content_hash=content_hash, semantic_hash=semantic_hash,
        trace=trace,
    )


def _enumerate_windows() -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    for top_el in get_children(get_root()):
        try:
            x, y, w, h = get_rect(top_el)
            ct = get_int(top_el, UIA_CONTROL_TYPE)
            role = CONTROL_TYPE_MAP.get(ct, "")
            if w <= ZERO_INT or h <= ZERO_INT or role not in ("Window", "Pane"):
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
    z = ZERO_INT
    while hwnd:
        if user32.IsWindowVisible(hwnd):
            title = get_window_title(int(hwnd))
            if title and title not in seen:
                result.append({"z": z, "hwnd": int(hwnd), "title": title})
                seen.add(title)
                z += ONE_INT
        hwnd = user32.GetWindow(hwnd, TWO_INT)
    return result


def _tree_walk(out: list[dict[str, Any]], trace: list[dict[str, Any]], el: Any, wnd_name: str, wnd_hwnd: int, timeout: float) -> None:
    from collections import deque
    start = time.perf_counter()
    queue: deque[tuple[Any, int]] = deque()
    for child in get_children(el):
        queue.append((child, ONE_INT))
    while queue:
        if time.perf_counter() - start > timeout:
            break
        raw_el, depth = queue.popleft()
        try:
            x, y, w, h = get_rect(raw_el)
            ct = get_int(raw_el, UIA_CONTROL_TYPE)
        except OSError:
            trace.append({"source": "tree", "wnd": wnd_name, "hwnd": wnd_hwnd, "depth": depth, "status": "property_error"})
            continue
        role = CONTROL_TYPE_MAP.get(ct, "")
        raw = {
            "source": "tree",
            "wnd": wnd_name,
            "hwnd": wnd_hwnd,
            "depth": depth,
            "control_type": ct,
            "role": role,
            "x": x,
            "y": y,
            "w": w,
            "h": h,
        }
        if not role:
            raw["status"] = "no_role"
            trace.append(raw)
            try:
                for c in get_children(raw_el):
                    queue.append((c, depth))
            except OSError:
                pass
            continue
        try:
            value = get_legacy_value(raw_el) if role in ACTIONABLE_ROLES else ""
            raw_value = value
            if not value and role in ("Text", "Document", "Edit", "Pane"):
                tc = get_text_content(raw_el, READ_TEXT_MAX_LENGTH)
                if tc:
                    raw_value = tc
                    value = _filter_terminal_text(tc)
                    n_has_text_pattern = True
                else:
                    n_has_text_pattern = False
            else:
                n_has_text_pattern = False
            out.append({
                "wnd": wnd_name, "hwnd": wnd_hwnd, "depth": depth,
                "role": role, "name": get_str(raw_el, UIA_NAME),
                "x": x, "y": y, "w": w, "h": h,
                "enabled": get_bool(raw_el, UIA_IS_ENABLED),
                "value": value,
                "raw_value": raw_value,
                "readonly": get_legacy_readonly(raw_el) if role in ACTIONABLE_ROLES else False,
                "offscreen": get_bool(raw_el, UIA_IS_OFFSCREEN),
                "has_text_pattern": n_has_text_pattern,
            })
            raw["name"] = out[-ONE_INT]["name"]
            raw["value"] = value
            raw["raw_value"] = raw_value
            raw["enabled"] = out[-ONE_INT]["enabled"]
            raw["readonly"] = out[-ONE_INT]["readonly"]
            raw["offscreen"] = out[-ONE_INT]["offscreen"]
            raw["has_text_pattern"] = n_has_text_pattern
            raw["status"] = "accepted"
            trace.append(raw)
        except OSError:
            raw["status"] = "value_error"
            trace.append(raw)
            continue
        try:
            for c in get_children(raw_el):
                queue.append((c, depth + ONE_INT))
        except OSError:
            pass


def _probe_regions(windows: list[dict[str, Any]], z_order: list[dict[str, Any]], focused_hwnd: int, sw: int, sh: int) -> list[tuple[int, int, int, int, str, int]]:
    if _topmost_popup(z_order):
        return [(ZERO_INT, ZERO_INT, sw, sh, "Desktop", ZERO_INT)]
    for wnd in windows:
        if int(wnd["hwnd"]) == focused_hwnd:
            return [(int(wnd["x"]), int(wnd["y"]),
                     int(wnd["x"]) + int(wnd["w"]),
                     int(wnd["y"]) + int(wnd["h"]),
                     str(wnd["name"]), int(wnd["hwnd"]))]
    return [(ZERO_INT, ZERO_INT, sw, sh, "Desktop", ZERO_INT)]


def _tree_decision(probe_decision: dict[str, Any]) -> dict[str, Any]:
    action_count = int(probe_decision.get("probe_actionable", ZERO_INT))
    enabled = action_count < OBSERVER_PROBE_ACTION_MIN
    reason = "probe_actionable_empty" if enabled else "probe_actionable_sufficient"
    return {"enabled": enabled, "reason": reason, "probe_actionable": action_count}


def _topmost_popup(z_order: list[dict[str, Any]]) -> bool:
    if not z_order:
        return False
    return get_window_class(int(z_order[ZERO_INT]["hwnd"])) in POPUP_CLASSES


def _target_action_count(nodes: list[dict[str, Any]], target_wnd: set[str]) -> int:
    count = ZERO_INT
    for n in nodes:
        wnd = str(n.get("wnd", ""))
        if target_wnd and wnd not in target_wnd and wnd != "Taskbar":
            continue
        if n.get("action") != "none":
            count += ONE_INT
    return count


def _probe_region(out: list[dict[str, Any]], trace: list[dict[str, Any]], step: int, x0: int, y0: int, x1: int, y1: int, wname: str, whwnd: int) -> None:
    seen_rids: set[Any] = set()
    amp = step * PROBE_SINE_AMPLITUDE_RATIO
    freq = TWO_INT * math.pi / (step * PROBE_SINE_PERIOD_STEPS)
    for y in range(y0 + step // TWO_INT, y1, step):
        for x in range(x0 + step // TWO_INT, x1, step):
            py = max(y0, min(y1 - ONE_INT, y + int(amp * math.sin(freq * x))))
            user32.SetCursorPos(x, py)
            time.sleep(PROBE_SAMPLE_DELAY)
            try:
                el = element_from_point(x, py)
            except OSError as e:
                trace.append({"source": "probe", "wnd": wname, "hwnd": whwnd, "x": x, "y": py, "status": "element_from_point_error", "exception_type": type(e).__name__, "exception": str(e)})
                continue
            if not el:
                trace.append({"source": "probe", "wnd": wname, "hwnd": whwnd, "x": x, "y": py, "status": "no_element"})
                continue
            try:
                rid = get_runtime_id(el)
                if rid and rid in seen_rids:
                    trace.append({"source": "probe", "wnd": wname, "hwnd": whwnd, "x": x, "y": py, "runtime_id": rid, "status": "duplicate_runtime_id"})
                    continue
                if rid:
                    seen_rids.add(rid)
                ct = get_int(el, UIA_CONTROL_TYPE)
                role = CONTROL_TYPE_MAP.get(ct, "")
                if not role:
                    trace.append({"source": "probe", "wnd": wname, "hwnd": whwnd, "x": x, "y": py, "runtime_id": rid, "control_type": ct, "status": "no_role"})
                    continue
                name = get_str(el, UIA_NAME)
                value = get_legacy_value(el)
                raw_value = value
                if not value:
                    text_content = get_text_content(el, READ_TEXT_MAX_LENGTH)
                    if text_content:
                        raw_value = text_content
                        value = _filter_terminal_text(text_content)
                r = get_rect(el)
                if not name and not value:
                    trace.append({"source": "probe", "wnd": wname, "hwnd": whwnd, "x": x, "y": py, "runtime_id": rid, "control_type": ct, "role": role, "rect": r, "status": "empty_text"})
                    continue
                rx, ry, rw, rh = r
                node = {
                    "wnd": wname, "hwnd": whwnd, "depth": ZERO_INT,
                    "role": role, "name": name,
                    "x": rx, "y": ry, "w": rw, "h": rh,
                    "enabled": get_bool(el, UIA_IS_ENABLED),
                    "value": value,
                    "raw_value": raw_value,
                    "readonly": get_legacy_readonly(el),
                    "offscreen": get_bool(el, UIA_IS_OFFSCREEN),
                    "runtime_id": rid,
                    "probe_x": x,
                    "probe_y": py,
                }
                out.append(node)
                trace.append({"source": "probe", "wnd": wname, "hwnd": whwnd, "x": x, "y": py, "runtime_id": rid, "control_type": ct, "role": role, "name": name, "value": value, "raw_value": raw_value, "rect": r, "status": "accepted"})
            except OSError:
                trace.append({"source": "probe", "wnd": wname, "hwnd": whwnd, "x": x, "y": py, "status": "property_error"})
                continue


def _filter_terminal_text(raw: str) -> str:
    lines = raw.split("\r\n")
    stripped = [l.rstrip() for l in lines if l.rstrip()]
    if not stripped:
        return ""
    last_sep = -ONE_INT
    for i in range(len(stripped) - ONE_INT, -ONE_INT, -ONE_INT):
        if " - Completed in " in stripped[i]:
            last_sep = i
            break
    if last_sep >= ZERO_INT and last_sep < len(stripped) - ONE_INT:
        tail = stripped[last_sep + ONE_INT:]
    else:
        tail = stripped
    return "\n".join(tail)


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
        if w <= ZERO_INT or h <= ZERO_INT or n.get("offscreen"):
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
    lines: list[str] = [LEGEND]
    current_wnd = ""
    seq = ZERO_INT
    for n in nodes:
        wnd = n["wnd"]
        if target_wnd and wnd not in target_wnd and wnd != "Taskbar":
            continue
        if n["action"] == "none" and not n.get("value"):
            seq += ONE_INT
            book[str(seq)] = BookEntry(
                id=str(seq), role=n["role"], name=n.get("name", ""),
                value=n.get("value", ""), hwnd=n["hwnd"], wnd=wnd,
                px=n["x"], py=n["y"], pw=n["w"], ph=n["h"],
                enabled=n.get("enabled", True), readonly=n.get("readonly", False),
                action=n["action"],
            )
            continue
        if wnd != current_wnd:
            current_wnd = wnd
            marker = "*" if wnd == focused_title else ""
            lines.append(f"[{wnd}]{marker}")
        seq += ONE_INT
        nid = str(seq)
        act = {"click": "C", "write": "W"}.get(n["action"], ".")
        typ = ROLE_SHORT.get(n["role"], n["role"])
        line = f"[{nid}] {act} {typ}"
        if n.get("name"):
            line += f" '{n['name']}'"
        if n.get("value"):
            line += f" v='{n['value']}'"
        if not n.get("enabled"):
            line += " -"
        lines.append(line)
        book[nid] = BookEntry(
            id=nid, role=n["role"], name=n.get("name", ""),
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


def _profile_start() -> tuple[float, float]:
    return time.perf_counter(), time.process_time()


def _profile_add(profile: dict[str, dict[str, int]], phase: str, start: tuple[float, float]) -> None:
    row = profile.setdefault(phase, {"wall_ms": ZERO_INT, "cpu_ms": ZERO_INT, "calls": ZERO_INT})
    row["wall_ms"] += int((time.perf_counter() - start[ZERO_INT]) * DURATION_MS_PER_SECOND)
    row["cpu_ms"] += int((time.process_time() - start[ONE_INT]) * DURATION_MS_PER_SECOND)
    row["calls"] += ONE_INT


def _clone_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(n) for n in nodes]


def _public_windows(windows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for w in windows:
        result.append({k: v for k, v in w.items() if k != "element"})
    return result


def _public_regions(regions: list[tuple[int, int, int, int, str, int]]) -> list[dict[str, Any]]:
    return [
        {"x0": x0, "y0": y0, "x1": x1, "y1": y1, "window": wname, "hwnd": whwnd}
        for x0, y0, x1, y1, wname, whwnd in regions
    ]


def _book_trace(book: dict[str, BookEntry]) -> dict[str, dict[str, Any]]:
    return {
        key: {
            "id": value.id,
            "role": value.role,
            "name": value.name,
            "value": value.value,
            "hwnd": value.hwnd,
            "wnd": value.wnd,
            "px": value.px,
            "py": value.py,
            "pw": value.pw,
            "ph": value.ph,
            "enabled": value.enabled,
            "readonly": value.readonly,
            "action": value.action,
        }
        for key, value in book.items()
    }

