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
BROWSER_WINDOW_CLASSES = frozenset({'Chrome_WidgetWin_1', 'MozillaWindowClass', 'ApplicationFrameWindow', 'OperaWindowClass'})
SEMANTIC_ZONE_ORDER = ('chrome', 'toolbar', 'tabs', 'navigation', 'search', 'form', 'content', 'status', 'chrome_misc')
ROLE_LABELS = {
    'url_field': 'url_field (address bar)',
    'search_field': 'search_field',
    'text_editor': 'text_editor (compose/article body)',
    'text_field': 'text_field',
    'toolbar_button': 'toolbar_button',
    'button': 'button',
    'link': 'link',
    'tab': 'tab',
    'resize_handle': 'resize_handle',
    'clickable': 'clickable',
}

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

def _window_rect_map(scan: dict[str, Any]) -> dict[int, dict[str, int]]:
    out: dict[int, dict[str, int]] = {}
    for win in scan.get('windows') or []:
        hwnd = int(win.get('hwnd', 0) or 0)
        rect = win.get('rect') or {}
        if hwnd > 0 and rect:
            out[hwnd] = {k: int(rect.get(k, 0)) for k in ('left', 'top', 'right', 'bottom')}
    return out

def _is_browser_window(window_class: str, title: str) -> bool:
    cls = str(window_class or '')
    if cls in BROWSER_WINDOW_CLASSES:
        return True
    low = f'{cls} {title}'.lower()
    return any(token in low for token in ('opera', 'chrome', 'firefox', 'edge', 'brave', 'vivaldi'))

def _cluster_elements(elements: list[Element], *, x_gap: int=56, y_gap: int=28) -> list[dict[str, Any]]:
    if not elements:
        return []
    sorted_elems = sorted(elements, key=lambda e: (e.y, e.x))
    clusters: list[dict[str, Any]] = []
    for elem in sorted_elems:
        placed = False
        for cluster in clusters:
            if abs(elem.x - cluster['x']) <= x_gap and abs(elem.y - cluster['y']) <= y_gap:
                cluster['elements'].append(elem)
                n = len(cluster['elements'])
                cluster['x'] = (cluster['x'] * (n - 1) + elem.x) // n
                cluster['y'] = (cluster['y'] * (n - 1) + elem.y) // n
                cluster['x_min'] = min(cluster['x_min'], elem.x)
                cluster['x_max'] = max(cluster['x_max'], elem.x)
                cluster['y_min'] = min(cluster['y_min'], elem.y)
                cluster['y_max'] = max(cluster['y_max'], elem.y)
                if CURSOR_PRIORITY.get(elem.cursor_name, 9) < CURSOR_PRIORITY.get(cluster['cursor_name'], 9):
                    cluster['cursor_name'] = elem.cursor_name
                placed = True
                break
        if not placed:
            clusters.append({'elements': [elem], 'x': elem.x, 'y': elem.y, 'x_min': elem.x, 'x_max': elem.x, 'y_min': elem.y, 'y_max': elem.y, 'cursor_name': elem.cursor_name})
    return clusters

def _classify_control(cluster: dict[str, Any], *, win_rect: dict[str, int] | None, window_class: str, title: str) -> tuple[str, str, str]:
    cursor = str(cluster.get('cursor_name') or 'arrow')
    x, y = int(cluster['x']), int(cluster['y'])
    spread_x = int(cluster['x_max']) - int(cluster['x_min'])
    spread_y = int(cluster['y_max']) - int(cluster['y_min'])
    rel_y = 0.5
    rel_x = 0.5
    win_h = 1
    if win_rect:
        left, top, right, bottom = (win_rect['left'], win_rect['top'], win_rect['right'], win_rect['bottom'])
        win_h = max(bottom - top, 1)
        win_w = max(right - left, 1)
        rel_y = (y - top) / win_h
        rel_x = (x - left) / win_w
    browser = _is_browser_window(window_class, title)
    if cursor == 'ibeam':
        if browser and rel_y < 0.16:
            return ('url_field', 'chrome', 'Type URL here; use click_at then type_text then press_key RETURN')
        if rel_y < 0.22 and spread_x > 80:
            return ('search_field', 'search', 'Search or omnibox text input')
        if spread_y >= 48 or spread_x >= 180:
            return ('text_editor', 'content', 'Large editable area — article/compose body')
        return ('text_field', 'form', 'Single-line or small text input')
    if cursor == 'hand':
        if browser and rel_y < 0.14:
            return ('toolbar_button', 'toolbar', 'Browser chrome control (tab/menu/extension)')
        if spread_x <= 48 and spread_y <= 48:
            return ('button', 'content', 'Compact clickable control')
        return ('link', 'content', 'Clickable link or wide button')
    if cursor in {'sizeall', 'sizenwse', 'sizenesw', 'sizewe', 'sizens'}:
        return ('resize_handle', 'chrome_misc', 'Resize/drag handle')
    return ('clickable', 'content', f'Interactive target ({cursor})')

def _merge_role_duplicates(controls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not controls:
        return controls
    merged: list[dict[str, Any]] = []
    for ctrl in controls:
        found = False
        for existing in merged:
            if existing['role'] != ctrl['role'] or existing['zone'] != ctrl['zone']:
                continue
            if abs(existing['y'] - ctrl['y']) > 24:
                continue
            if abs(existing['x'] - ctrl['x']) > 220:
                continue
            existing['x'] = (existing['x'] + ctrl['x']) // 2
            existing['y'] = (existing['y'] + ctrl['y']) // 2
            existing['action_click'] = f"click_at({existing['x']}, {existing['y']})"
            found = True
            break
        if not found:
            merged.append(dict(ctrl))
    for idx, ctrl in enumerate(merged, start=1):
        ctrl['id'] = f'ui_{idx}'
    return merged

def _build_semantic_controls(elements: list[Element], *, win_rect: dict[str, int] | None, window_class: str, title: str) -> list[dict[str, Any]]:
    clusters = _cluster_elements(elements)
    controls: list[dict[str, Any]] = []
    for idx, cluster in enumerate(clusters, start=1):
        role, zone, hint = _classify_control(cluster, win_rect=win_rect, window_class=window_class, title=title)
        controls.append({
            'id': f'ui_{idx}',
            'role': role,
            'label': ROLE_LABELS.get(role, role),
            'zone': zone,
            'x': cluster['x'],
            'y': cluster['y'],
            'cursor': cluster['cursor_name'],
            'hint': hint,
            'action_click': f'click_at({cluster["x"]}, {cluster["y"]})',
        })
    controls = _merge_role_duplicates(controls)
    zone_rank = {z: i for i, z in enumerate(SEMANTIC_ZONE_ORDER)}
    role_rank = {'url_field': 0, 'search_field': 1, 'text_editor': 2, 'text_field': 3, 'toolbar_button': 4, 'button': 5, 'link': 6}
    controls.sort(key=lambda c: (zone_rank.get(c['zone'], 99), role_rank.get(c['role'], 99), c['y'], c['x']))
    return controls

def _suggested_actions(controls: list[dict[str, Any]], *, title: str, focused: bool) -> list[str]:
    if not focused:
        return []
    actions: list[str] = []
    url_fields = [c for c in controls if c['role'] == 'url_field']
    editors = [c for c in controls if c['role'] in {'text_editor', 'text_field'}]
    if url_fields:
        c = url_fields[0]
        actions.append(f"navigate: {c['action_click']}; type_text('https://example.com'); press_key('RETURN')")
    if editors and not url_fields:
        c = editors[0]
        actions.append(f"type_into_field: {c['action_click']}; type_text('...')")
    low = title.lower()
    if 'x.com' in low or 'twitter' in low:
        actions.append('x_compose: locate text_editor in content zone; click; type_text article body')
    if 'linkedin' in low:
        actions.append('linkedin_article: locate text_editor; click; type_text article body')
    return actions[:4]

def _render_semantic_ui_tree(scan: dict[str, Any], config: dict[str, Any]) -> str:
    elements = [Element(**e) if isinstance(e, dict) else e for e in scan.get('elements', [])]
    focused_hwnd = int(scan.get('focused_hwnd') or 0)
    rects = _window_rect_map(scan)
    max_windows = int(config.get('max_windows', 14))
    max_controls = int(config.get('max_semantic_controls', 32))
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
        return (0 if hwnd == focused_hwnd else 1, -len(elems), title.lower())

    lines = [
        'SEMANTIC_UI (python-prepared; use role names and @x,y — ignore raw cursor tokens)',
        f"FOCUS: {scan.get('focused_title') or '(none)'}",
        f"SCREEN: {scan.get('screen_width')}x{scan.get('screen_height')}",
        f"SCAN: step={scan.get('step_px')}px raw_hits={scan.get('element_count', len(elements))}",
    ]
    ordered_hwnds = sorted(by_hwnd.keys(), key=window_rank)
    total_controls = 0
    for hwnd in ordered_hwnds[:max_windows]:
        elems = by_hwnd[hwnd]
        title = elems[0].window_title or '(untitled)'
        cls = elems[0].window_class or ''
        focused = hwnd == focused_hwnd
        rect = rects.get(hwnd)
        rect_s = ''
        if rect:
            w = rect['right'] - rect['left']
            h = rect['bottom'] - rect['top']
            rect_s = f' rect={w}x{h}'
        marker = '*' if focused else ' '
        lines.append(f"{marker} WINDOW [{hwnd}] \"{title}\" class={cls} focused={'yes' if focused else 'no'}{rect_s}")
        controls = _build_semantic_controls(elems, win_rect=rect, window_class=cls, title=title)
        by_zone: dict[str, list[dict[str, Any]]] = {}
        for ctrl in controls:
            by_zone.setdefault(ctrl['zone'], []).append(ctrl)
        for zone in SEMANTIC_ZONE_ORDER:
            zone_controls = by_zone.get(zone) or []
            if not zone_controls:
                continue
            lines.append(f"    ZONE {zone}:")
            for ctrl in zone_controls:
                if total_controls >= max_controls:
                    break
                lines.append(f"      - {ctrl['label']} @{ctrl['x']},{ctrl['y']} id={ctrl['id']} | {ctrl['hint']}")
                lines.append(f"        action: {ctrl['action_click']}")
                total_controls += 1
            if total_controls >= max_controls:
                break
        if not controls:
            lines.append('    ZONE content: (no interactive controls detected)')
        for action in _suggested_actions(controls, title=title, focused=focused):
            lines.append(f"    SUGGESTED: {action}")
        if total_controls >= max_controls:
            lines.append('... semantic control cap reached')
            break
    if len(ordered_hwnds) > max_windows:
        lines.append(f"... +{len(ordered_hwnds) - max_windows} windows omitted")
    if not ordered_hwnds:
        lines.append('(no interactive windows)')
    return '\n'.join(lines)

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
    max_chars = int(config.get('max_tree_chars', 8000))
    text = _render_semantic_ui_tree(scan, config)
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
    return {'observed_at': scan['observed_at'], 'fresh_scan': True, 'desktop_tree_text': tree_text, 'focused_title': scan['focused_title'], 'observation_artifact': {'path': artifact_path.relative_to(ROOT).as_posix(), 'size': artifact_path.stat().st_size, 'kind': 'semantic_ui_hover_scan'}, 'element_count': scan['element_count'], 'cell_count': scan['cell_count']}

def observe_screen() -> dict[str, int]:
    w, h = get_screen_size()
    return {'width': w, 'height': h}

def get_focused_title() -> str:
    hwnd = user32.GetForegroundWindow()
    return get_window_title(hwnd) if hwnd else ''