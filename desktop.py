from __future__ import annotations
import ctypes
import json
import time
import pathlib
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any
from win32_api import user32, get_screen_size, get_window_title, get_window_class, enum_windows, set_foreground_window, click_at, type_text, press_key, hotkey, scroll_at, open_url, window_at_point
ROOT = pathlib.Path(__file__).parent.resolve()
IDC_ARROW = 32512
IDC_IBEAM = 32513
IDC_WAIT = 32514
IDC_CROSS = 32515
IDC_UPARROW = 32516
IDC_SIZE = 32640
IDC_ICON = 32641
IDC_SIZENWSE = 32642
IDC_SIZENESW = 32643
IDC_SIZEWE = 32644
IDC_SIZENS = 32645
IDC_SIZEALL = 32646
IDC_NO = 32648
IDC_HAND = 32649
IDC_APPSTARTING = 32650
IDC_HELP = 32651
INTERACTIVE_CURSORS = {IDC_IBEAM, IDC_HAND, IDC_SIZEALL, IDC_SIZENWSE, IDC_SIZENESW, IDC_SIZEWE, IDC_SIZENS, IDC_UPARROW, IDC_CROSS}
CURSOR_NAMES = {IDC_ARROW: 'arrow', IDC_IBEAM: 'ibeam', IDC_WAIT: 'wait', IDC_CROSS: 'cross', IDC_UPARROW: 'uparrow', IDC_SIZE: 'size', IDC_ICON: 'icon', IDC_SIZENWSE: 'sizenwse', IDC_SIZENESW: 'sizenesw', IDC_SIZEWE: 'sizewe', IDC_SIZENS: 'sizens', IDC_SIZEALL: 'sizeall', IDC_NO: 'no', IDC_HAND: 'hand', IDC_APPSTARTING: 'appstarting', IDC_HELP: 'help'}
CURSOR_PRIORITY = {'ibeam': 0, 'hand': 1, 'sizeall': 2, 'sizenwse': 2, 'sizenesw': 2, 'sizewe': 2, 'sizens': 2, 'uparrow': 3, 'cross': 4, 'arrow': 5, 'wait': 6}

class CURSORINFO(ctypes.Structure):
    _fields_ = [('cbSize', ctypes.c_uint), ('flags', ctypes.c_uint), ('hCursor', wintypes.HANDLE), ('ptScreenPos', wintypes.POINT)]
user32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
user32.GetCursorInfo.restype = ctypes.c_bool
user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
user32.LoadCursorW.restype = wintypes.HANDLE
SYSTEM_CURSOR_RESOURCES = {IDC_ARROW: '#32512', IDC_IBEAM: '#32513', IDC_WAIT: '#32514', IDC_CROSS: '#32515', IDC_UPARROW: '#32516', IDC_SIZE: '#32640', IDC_ICON: '#32641', IDC_SIZENWSE: '#32642', IDC_SIZENESW: '#32643', IDC_SIZEWE: '#32644', IDC_SIZENS: '#32645', IDC_SIZEALL: '#32646', IDC_NO: '#32648', IDC_HAND: '#32649', IDC_APPSTARTING: '#32650', IDC_HELP: '#32651'}
_SYSTEM_CURSOR_HANDLES: dict[int, wintypes.HANDLE] = {}

def _get_system_cursor_handle(cursor_id: int) -> wintypes.HANDLE:
    if cursor_id not in _SYSTEM_CURSOR_HANDLES:
        resource = SYSTEM_CURSOR_RESOURCES.get(cursor_id)
        _SYSTEM_CURSOR_HANDLES[cursor_id] = user32.LoadCursorW(0, resource) if resource else 0
    return _SYSTEM_CURSOR_HANDLES[cursor_id]

def get_current_cursor_type() -> tuple[int, str]:
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(CURSORINFO)
    if not user32.GetCursorInfo(ctypes.byref(ci)):
        return (IDC_ARROW, 'arrow')
    for cursor_id in CURSOR_NAMES:
        if ci.hCursor == _get_system_cursor_handle(cursor_id):
            return (cursor_id, CURSOR_NAMES[cursor_id])
    return (ci.hCursor, 'custom')

@dataclass
class Element:
    x: int
    y: int
    cursor_type: int
    cursor_name: str
    hwnd: int
    window_title: str
    window_class: str
    cell_id: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {'x': self.x, 'y': self.y, 'cursor_type': self.cursor_type, 'cursor_name': self.cursor_name, 'hwnd': self.hwnd, 'window_title': self.window_title, 'window_class': self.window_class, 'cell_id': self.cell_id}

def _col_to_letter(col: int) -> str:
    result = ''
    col += 1
    while col > 0:
        col -= 1
        result = chr(65 + col % 26) + result
        col //= 26
    return result

def _create_grid_mapping(elements: list[Element], cell_size: int=100) -> dict[str, list[Element]]:
    grid: dict[str, list[Element]] = {}
    for elem in elements:
        col = elem.x // cell_size
        row = elem.y // cell_size
        cell_id = f'{_col_to_letter(col)}{row + 1}'
        elem.cell_id = cell_id
        grid.setdefault(cell_id, []).append(elem)
    return grid

def _cell_sort_key(cell_id: str) -> tuple[int, int]:
    col_str = ''
    row_str = ''
    for ch in cell_id:
        if ch.isalpha():
            col_str += ch
        else:
            row_str += ch
    col = 0
    for ch in col_str:
        col = col * 26 + (ord(ch.upper()) - 64)
    return (int(row_str or '1') - 1, col - 1)

def _pick_cell_element(cells: list[Element]) -> Element:
    return min(cells, key=lambda e: (CURSOR_PRIORITY.get(e.cursor_name, 9), e.x, e.y))

def _render_compact_grid(grid: dict[str, list[Element]], config: dict[str, Any]) -> list[str]:
    interactive = {cid: _pick_cell_element(cells) for cid, cells in grid.items() if any((e.cursor_name in {'ibeam', 'hand', 'sizeall', 'sizenwse', 'sizenesw', 'sizewe', 'sizens', 'uparrow', 'cross'} for e in cells))}
    if not interactive:
        return ['GRID: (no interactive cells)']
    cols = set()
    rows = set()
    for cell_id in interactive:
        row, col = _cell_sort_key(cell_id)
        cols.add(col)
        rows.add(row)
    max_cols = int(config.get('grid_max_cols', 16))
    max_rows = int(config.get('grid_max_rows', 12))
    min_col, max_col = (min(cols), min(max(cols), min(cols) + max_cols - 1))
    min_row, max_row = (min(rows), min(max(rows), min(rows) + max_rows - 1))
    lines = ['GRID:']
    header = '    ' + ' '.join((f'{_col_to_letter(c):>3}' for c in range(min_col, max_col + 1)))
    lines.append(header)
    for r in range(min_row, max_row + 1):
        row_parts = [f'{r + 1:3} ']
        for c in range(min_col, max_col + 1):
            cell_id = f'{_col_to_letter(c)}{r + 1}'
            if cell_id in interactive:
                row_parts.append(f' {interactive[cell_id].cursor_name[:3]:>3}')
            else:
                row_parts.append('  .')
        lines.append(''.join(row_parts))
    return lines

def _render_visible_windows(scan: dict[str, Any], config: dict[str, Any]) -> list[str]:
    windows = scan.get('windows') or []
    if not windows:
        return []
    focused_hwnd = int(scan.get('focused_hwnd') or 0)
    max_visible = int(config.get('max_visible_windows', 18))
    ranked = sorted(windows, key=lambda w: (0 if int(w.get('hwnd', 0)) == focused_hwnd else 1, str(w.get('title', '')).lower()))
    lines = ['VISIBLE:']
    for win in ranked[:max_visible]:
        hwnd = int(win.get('hwnd', 0))
        title = str(win.get('title', '') or '(untitled)')
        cls = str(win.get('class_name', '') or '')
        rect = win.get('rect') or {}
        w = int(rect.get('right', 0)) - int(rect.get('left', 0))
        h = int(rect.get('bottom', 0)) - int(rect.get('top', 0))
        marker = '*' if hwnd == focused_hwnd else ' '
        lines.append(f"{marker} [{hwnd}] {title} ({cls}) {w}x{h}")
    if len(ranked) > max_visible:
        lines.append(f"... +{len(ranked) - max_visible} visible windows omitted")
    return lines

def _render_hierarchical_tree(scan: dict[str, Any], config: dict[str, Any]) -> str:
    elements = [Element(**e) if isinstance(e, dict) else e for e in scan.get('elements', [])]
    focused_hwnd = int(scan.get('focused_hwnd') or 0)
    max_chars = int(config.get('max_tree_chars', 8000))
    max_windows = int(config.get('max_windows', 14))
    max_cells = int(config.get('max_cells_per_window', 24))
    by_hwnd: dict[int, list[Element]] = {}
    for elem in elements:
        if elem.cursor_type not in INTERACTIVE_CURSORS and elem.cursor_name not in CURSOR_PRIORITY:
            continue
        if elem.hwnd <= 0:
            continue
        by_hwnd.setdefault(elem.hwnd, []).append(elem)
    def window_rank(hwnd: int) -> tuple[int, int, str]:
        elems = by_hwnd.get(hwnd, [])
        title = elems[0].window_title if elems else ''
        focus_rank = 0 if hwnd == focused_hwnd else 1
        return (focus_rank, -len(elems), title.lower())
    ordered_hwnds = sorted(by_hwnd.keys(), key=window_rank)
    lines = [f"FOCUS: {scan.get('focused_title') or '(none)'}", f"SCREEN: {scan.get('screen_width')}x{scan.get('screen_height')}", f"SCAN: step={scan.get('step_px')}px elements={scan.get('element_count', len(elements))}", f"INTERACTIVE: {sum((len(v) for v in by_hwnd.values()))} hits / {len(by_hwnd)} windows"]
    lines.extend(_render_visible_windows(scan, config))
    lines.append('WINDOWS:')
    omitted = 0
    for hwnd in ordered_hwnds[:max_windows]:
        elems = by_hwnd[hwnd]
        title = elems[0].window_title or '(untitled)'
        cls = elems[0].window_class or ''
        marker = '*' if hwnd == focused_hwnd else ' '
        lines.append(f"{marker} [{hwnd}] {title} ({cls})")
        cells: dict[str, Element] = {}
        for elem in elems:
            if not elem.cell_id:
                col = elem.x // int(scan.get('cell_size') or 100)
                row = elem.y // int(scan.get('cell_size') or 100)
                elem.cell_id = f'{_col_to_letter(col)}{row + 1}'
            prev = cells.get(elem.cell_id)
            if prev is None or CURSOR_PRIORITY.get(elem.cursor_name, 9) < CURSOR_PRIORITY.get(prev.cursor_name, 9):
                cells[elem.cell_id] = elem
        for cell_id in sorted(cells.keys(), key=_cell_sort_key)[:max_cells]:
            elem = cells[cell_id]
            lines.append(f"    {cell_id} {elem.cursor_name} @{elem.x},{elem.y}")
        if len(cells) > max_cells:
            lines.append(f"    ... +{len(cells) - max_cells} cells")
    if len(ordered_hwnds) > max_windows:
        omitted = len(ordered_hwnds) - max_windows
        lines.append(f"... +{omitted} windows omitted")
    grid = _create_grid_mapping(elements, int(scan.get('cell_size') or 100))
    lines.extend(_render_compact_grid(grid, config))
    text = '\n'.join(lines)
    if len(text) > max_chars:
        trimmed = text[:max_chars].rsplit('\n', 1)[0]
        text = trimmed + f'\n... truncated at {max_chars} chars'
    if not text.strip():
        raise RuntimeError('observe produced empty desktop_tree_text')
    return text

def hover_scan_fullscreen(config: dict[str, Any] | None=None) -> dict[str, Any]:
    config = config or {}
    step_px = int(config.get('step_px', 40))
    delay_ms = int(config.get('delay_ms', 1))
    cell_size = int(config.get('cell_size', 100))
    max_elements = int(config.get('max_elements', 500))
    restore_cursor = bool(config.get('restore_cursor', True))
    screen_w, screen_h = get_screen_size()
    saved_pos = wintypes.POINT()
    if restore_cursor:
        user32.GetCursorPos(ctypes.byref(saved_pos))
    elements: list[Element] = []
    last_cursor_type = IDC_ARROW
    row_report = max(step_px * 8, 1)
    try:
        y = 0
        while y < screen_h and len(elements) < max_elements:
            if y % row_report == 0:
                pct = int(y * 100 / max(screen_h, 1))
                print(f'[observe] scan {pct}% row {y}/{screen_h} elements={len(elements)}', flush=True)
            x = 0
            while x < screen_w and len(elements) < max_elements:
                user32.SetCursorPos(x, y)
                if delay_ms > 0:
                    time.sleep(delay_ms / 1000.0)
                cursor_type, cursor_name = get_current_cursor_type()
                hwnd = window_at_point(x, y)
                is_interactive = cursor_type in INTERACTIVE_CURSORS
                cursor_changed = cursor_type != last_cursor_type
                if is_interactive or cursor_changed:
                    if hwnd > 0:
                        elements.append(Element(x=x, y=y, cursor_type=cursor_type, cursor_name=cursor_name, hwnd=hwnd, window_title=get_window_title(hwnd), window_class=get_window_class(hwnd)))
                last_cursor_type = cursor_type
                x += step_px
            y += step_px
    finally:
        if restore_cursor:
            user32.SetCursorPos(saved_pos.x, saved_pos.y)
    grid = _create_grid_mapping(elements, cell_size)
    focused_hwnd = user32.GetForegroundWindow()
    focused_title = get_window_title(focused_hwnd) if focused_hwnd else ''
    return {'observed_at': time.time(), 'screen_width': screen_w, 'screen_height': screen_h, 'step_px': step_px, 'cell_size': cell_size, 'elements': [e.to_dict() for e in elements], 'grid': {k: [e.to_dict() for e in v] for k, v in grid.items()}, 'windows': enum_windows(), 'focused_title': focused_title, 'focused_hwnd': focused_hwnd, 'element_count': len(elements), 'cell_count': len(grid)}

def observe(config: dict[str, Any] | None=None) -> dict[str, Any]:
    config = dict(config or {})
    scan = hover_scan_fullscreen(config)
    print(f'[observe] rendering tree from {scan.get("element_count", 0)} elements', flush=True)
    tree_text = _render_hierarchical_tree(scan, config)
    print(f'[observe] desktop_tree_text {len(tree_text)} chars', flush=True)
    artifact_dir = ROOT / 'comms' / 'observations'
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{int(scan['observed_at'] * 1000)}.json"
    artifact_path.write_text(json.dumps({**scan, 'desktop_tree_text': tree_text}, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    return {'observed_at': scan['observed_at'], 'fresh_scan': True, 'desktop_tree_text': tree_text, 'focused_title': scan['focused_title'], 'observation_artifact': {'path': artifact_path.relative_to(ROOT).as_posix(), 'size': artifact_path.stat().st_size, 'kind': 'hover_scan_grid'}, 'element_count': scan['element_count'], 'cell_count': scan['cell_count']}

def observe_screen() -> dict[str, int]:
    w, h = get_screen_size()
    return {'width': w, 'height': h}

def get_focused_title() -> str:
    hwnd = user32.GetForegroundWindow()
    return get_window_title(hwnd) if hwnd else ''