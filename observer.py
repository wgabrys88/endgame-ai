from __future__ import annotations
import hashlib, math, time
from dataclasses import dataclass
from typing import Any

from config import TREE_WALK_TIMEOUT, PROBE_STEP_PX, trace
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
    ensure_tree_walker()
    saved = W.POINT()
    user32.GetCursorPos(ctypes.byref(saved))
    for x0, y0, x1, y1, wname, whwnd in regions:
        if whwnd:
            user32.SetForegroundWindow(W.HWND(whwnd))
            time.sleep(0.3)
        _probe_region(probe_nodes, PROBE_STEP_PX, x0, y0, x1, y1, wname, whwnd)
    user32.SetCursorPos(saved.x, saved.y)

    tree_nodes: list[dict[str, Any]] = []
    for wnd in windows:
        _tree_walk(tree_nodes, wnd["element"], str(wnd["name"]), int(wnd["hwnd"]),
                   TREE_WALK_TIMEOUT)

    merged = _merge(tree_nodes, probe_nodes)
    classified = _classify(merged)

    target_wnd: set[str] = {focused_title} if focused_title else set()

    z_titles = [str(e["title"]) for e in z_order]
    wnd_rank = {t: i for i, t in enumerate(z_titles)}
    classified.sort(key=lambda n: (wnd_rank.get(n["wnd"], 999), n["depth"], n["y"], n["x"]))

    text, book = _render(classified, target_wnd, focused_title)
    content_hash = hashlib.md5(text.encode("utf-8", errors="surrogatepass")).hexdigest()

    trace("observer.book", f"elements={len(book)} focused={focused_title} hash={content_hash}")
    for eid, entry in book.items():
        if entry.action != "none":
            trace("observer.element", f"[{eid}] {entry.action} {entry.role} '{entry.name}' v='{entry.value}' pos=({entry.px},{entry.py}) sz=({entry.pw},{entry.ph}) wnd={entry.wnd}")

    return ObserveResult(
        context_text=text, book=book, focused_title=focused_title,
        windows=[{"name": w["name"], "hwnd": w["hwnd"]} for w in windows],
        content_hash=content_hash,
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
                tc = get_text_content(raw_el, -1)
                if tc:
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
                "readonly": get_legacy_readonly(raw_el) if role in ACTIONABLE_ROLES else False,
                "offscreen": get_bool(raw_el, UIA_IS_OFFSCREEN),
                "has_text_pattern": n_has_text_pattern,
            })
        except OSError:
            continue
        try:
            for c in get_children(raw_el):
                queue.append((c, depth + 1))
        except OSError:
            pass


def _probe_regions(windows: list[dict[str, Any]], z_order: list[dict[str, Any]], focused_hwnd: int, sw: int, sh: int) -> list[tuple[int, int, int, int, str, int]]:
    for z in z_order:
        if get_window_class(int(z["hwnd"])) in POPUP_CLASSES:
            return [(0, 0, sw, sh, "Desktop", 0)]
    for wnd in windows:
        if int(wnd["hwnd"]) == focused_hwnd:
            return [(int(wnd["x"]), int(wnd["y"]),
                     int(wnd["x"]) + int(wnd["w"]),
                     int(wnd["y"]) + int(wnd["h"]),
                     str(wnd["name"]), int(wnd["hwnd"]))]
    return [(0, 0, sw, sh, "Desktop", 0)]


def _probe_region(out: list[dict[str, Any]], step: int, x0: int, y0: int, x1: int, y1: int, wname: str, whwnd: int) -> None:
    seen_rids: set[Any] = set()
    amp = step * 0.4
    freq = 2 * math.pi / (step * 6)
    for y in range(y0 + step // 2, y1, step):
        for x in range(x0 + step // 2, x1, step):
            py = max(y0, min(y1 - 1, y + int(amp * math.sin(freq * x))))
            user32.SetCursorPos(x, py)
            time.sleep(0.003)
            el = element_from_point(x, py)
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
                    text_content = get_text_content(el, -1)
                    if text_content:
                        value = _filter_terminal_text(text_content)
                r = get_rect(el)
                if not name and not value:
                    continue
                out.append({
                    "wnd": wname, "hwnd": whwnd, "depth": 0,
                    "role": role, "name": name,
                    "x": r[0], "y": r[1], "w": r[2], "h": r[3],
                    "enabled": get_bool(el, UIA_IS_ENABLED),
                    "value": value,
                    "readonly": get_legacy_readonly(el),
                    "offscreen": get_bool(el, UIA_IS_OFFSCREEN),
                })
            except OSError:
                continue


def _filter_terminal_text(raw: str) -> str:
    lines = raw.split("\r\n")
    stripped = [l.rstrip() for l in lines if l.rstrip()]
    if not stripped:
        return ""
    last_sep = -1
    for i in range(len(stripped) - 1, -1, -1):
        if " - Completed in " in stripped[i]:
            last_sep = i
            break
    if last_sep >= 0 and last_sep < len(stripped) - 1:
        tail = stripped[last_sep + 1:]
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
    lines: list[str] = [LEGEND]
    current_wnd = ""
    seq = 0
    for n in nodes:
        wnd = n["wnd"]
        if target_wnd and wnd not in target_wnd and wnd != "Taskbar":
            continue
        if n["action"] == "none" and not n.get("value"):
            seq += 1
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
        seq += 1
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
