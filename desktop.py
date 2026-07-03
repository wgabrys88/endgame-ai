"""Simplified desktop observation - pure Win32 hover scan with cursor shape detection.

Single unified method: grid scan over entire screen, detect cursor changes,
group nearby hits, present as Excel-style grid to LLM.
No UIA, no comtypes, no complex filtering - fail hard only.
"""

from __future__ import annotations

import ctypes
import time
import pathlib
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any

from win32_api import (
    user32, get_screen_size, get_window_title, get_window_class,
    enum_windows, set_foreground_window, click_at, type_text,
    press_key, hotkey, scroll_at, open_url, window_at_point,
)

ROOT = pathlib.Path(__file__).parent.resolve()


# =============================================================================
# Cursor Shape Detection
# =============================================================================

# System cursor IDs (from WinUser.h)
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

INTERACTIVE_CURSORS = {
    IDC_IBEAM,      # Text input
    IDC_HAND,       # Clickable link/button
    IDC_SIZEALL,    # Moveable
    IDC_SIZENWSE,   # Resize
    IDC_SIZENESW,   # Resize
    IDC_SIZEWE,     # Resize
    IDC_SIZENS,     # Resize
    IDC_UPARROW,    # Text select
    IDC_CROSS,      # Precision select
}

CURSOR_NAMES = {
    IDC_ARROW: "arrow",
    IDC_IBEAM: "ibeam",
    IDC_WAIT: "wait",
    IDC_CROSS: "cross",
    IDC_UPARROW: "uparrow",
    IDC_SIZE: "size",
    IDC_ICON: "icon",
    IDC_SIZENWSE: "sizenwse",
    IDC_SIZENESW: "sizenesw",
    IDC_SIZEWE: "sizewe",
    IDC_SIZENS: "sizens",
    IDC_SIZEALL: "sizeall",
    IDC_NO: "no",
    IDC_HAND: "hand",
    IDC_APPSTARTING: "appstarting",
    IDC_HELP: "help",
}

# GetCursorInfo structure
class CURSORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("flags", ctypes.c_uint),
        ("hCursor", wintypes.HANDLE),
        ("ptScreenPos", wintypes.POINT),
    ]

user32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
user32.GetCursorInfo.restype = ctypes.c_bool

# Load cursor to get system cursor handles
user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
user32.LoadCursorW.restype = wintypes.HANDLE

# System cursor resource names (MAKEINTRESOURCE macro expands to these)
SYSTEM_CURSOR_RESOURCES = {
    IDC_ARROW: "#32512",
    IDC_IBEAM: "#32513",
    IDC_WAIT: "#32514",
    IDC_CROSS: "#32515",
    IDC_UPARROW: "#32516",
    IDC_SIZE: "#32640",
    IDC_ICON: "#32641",
    IDC_SIZENWSE: "#32642",
    IDC_SIZENESW: "#32643",
    IDC_SIZEWE: "#32644",
    IDC_SIZENS: "#32645",
    IDC_SIZEALL: "#32646",
    IDC_NO: "#32648",
    IDC_HAND: "#32649",
    IDC_APPSTARTING: "#32650",
    IDC_HELP: "#32651",
}

_SYSTEM_CURSOR_HANDLES: dict[int, wintypes.HANDLE] = {}

def _get_system_cursor_handle(cursor_id: int) -> wintypes.HANDLE:
    """Get handle for a system cursor."""
    if cursor_id not in _SYSTEM_CURSOR_HANDLES:
        resource = SYSTEM_CURSOR_RESOURCES.get(cursor_id)
        if resource:
            _SYSTEM_CURSOR_HANDLES[cursor_id] = user32.LoadCursorW(0, resource)
        else:
            _SYSTEM_CURSOR_HANDLES[cursor_id] = 0
    return _SYSTEM_CURSOR_HANDLES[cursor_id]

def get_current_cursor_type() -> tuple[int, str]:
    """Get current cursor type ID and name."""
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(CURSORINFO)
    if not user32.GetCursorInfo(ctypes.byref(ci)):
        return IDC_ARROW, "arrow"
    
    # Compare with known system cursors
    for cursor_id in CURSOR_NAMES:
        if ci.hCursor == _get_system_cursor_handle(cursor_id):
            return cursor_id, CURSOR_NAMES[cursor_id]
    
    # Custom cursor - check if it's interactive by flags
    return ci.hCursor, "custom"


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class Element:
    """Detected interactive element from hover scan."""
    x: int
    y: int
    cursor_type: int
    cursor_name: str
    hwnd: int
    window_title: str
    window_class: str
    cell_id: str = ""  # Excel-style: A1, B2, etc.
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "cursor_type": self.cursor_type,
            "cursor_name": self.cursor_name,
            "hwnd": self.hwnd,
            "window_title": self.window_title,
            "window_class": self.window_class,
            "cell_id": self.cell_id,
        }


# =============================================================================
# Excel-Style Grid Mapping
# =============================================================================

def _col_to_letter(col: int) -> str:
    """Convert 0-based column index to Excel letter (A, B, ..., Z, AA, AB...)."""
    result = ""
    col += 1  # 1-based for Excel
    while col > 0:
        col -= 1
        result = chr(65 + (col % 26)) + result
        col //= 26
    return result

def _create_grid_mapping(elements: list[Element], cell_size: int = 100) -> dict[str, list[Element]]:
    """Group elements into Excel-style grid cells."""
    grid: dict[str, list[Element]] = {}
    for elem in elements:
        col = elem.x // cell_size
        row = elem.y // cell_size
        cell_id = f"{_col_to_letter(col)}{row + 1}"
        elem.cell_id = cell_id
        grid.setdefault(cell_id, []).append(elem)
    return grid

def _render_grid_text(grid: dict[str, list[Element]], max_cols: int = 20, max_rows: int = 15) -> str:
    """Render grid as text for LLM consumption."""
    lines = ["SCREEN GRID (Excel-style cells, 100px each):"]
    
    # Find bounds
    all_cells = list(grid.keys())
    if not all_cells:
        return lines[0] + "\n  (empty)"
    
    cols = set()
    rows = set()
    for cell_id in all_cells:
        # Parse cell_id like "A1" -> col=0, row=0
        col_str = ""
        row_str = ""
        for ch in cell_id:
            if ch.isalpha():
                col_str += ch
            else:
                row_str += ch
        col = 0
        for ch in col_str:
            col = col * 26 + (ord(ch.upper()) - 64)
        col -= 1
        row = int(row_str) - 1
        cols.add(col)
        rows.add(row)
    
    min_col, max_col = min(cols), min(max(cols), max_cols - 1)
    min_row, max_row = min(rows), min(max(rows), max_rows - 1)
    
    # Header
    header = "    " + " ".join(f"{_col_to_letter(c):>3}" for c in range(min_col, max_col + 1))
    lines.append(header)
    
    for r in range(min_row, max_row + 1):
        row_parts = [f"{r+1:3} "]
        for c in range(min_col, max_col + 1):
            cell_id = f"{_col_to_letter(c)}{r+1}"
            if cell_id in grid:
                # Show cursor type of first element
                cursor = grid[cell_id][0].cursor_name[:3]
                row_parts.append(f" {cursor:>3}")
            else:
                row_parts.append("  .")
        lines.append("".join(row_parts))
    
    # Legend
    lines.append("\nLEGEND: ibe=text, han=click, siz=resize, uar=select, cro=precision, arr=default")
    lines.append(f"TOTAL ELEMENTS: {sum(len(v) for v in grid.values())} in {len(grid)} cells")
    
    return "\n".join(lines)


# =============================================================================
# Main Hover Scan
# =============================================================================

def hover_scan_fullscreen(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Single unified hover scan over entire screen.
    
    Config:
        step_px: grid step in pixels (default 40)
        delay_ms: delay between probes (default 1)
        cell_size: Excel grid cell size (default 100)
        max_elements: max elements to return (default 500)
        restore_cursor: restore mouse position after (default True)
    """
    if config is None:
        config = {}
    
    step_px = config.get("step_px", 40)
    delay_ms = config.get("delay_ms", 1)
    cell_size = config.get("cell_size", 100)
    max_elements = config.get("max_elements", 500)
    restore_cursor = config.get("restore_cursor", True)
    
    screen_w, screen_h = get_screen_size()
    
    # Save cursor position
    saved_pos = wintypes.POINT()
    if restore_cursor:
        user32.GetCursorPos(ctypes.byref(saved_pos))
    
    elements: list[Element] = []
    last_cursor_type = IDC_ARROW
    
    try:
        y = 0
        while y < screen_h and len(elements) < max_elements:
            x = 0
            while x < screen_w and len(elements) < max_elements:
                user32.SetCursorPos(x, y)
                if delay_ms > 0:
                    time.sleep(delay_ms / 1000.0)
                
                cursor_type, cursor_name = get_current_cursor_type()
                hwnd = window_at_point(x, y)
                
                # Detect cursor change OR interactive cursor
                is_interactive = cursor_type in INTERACTIVE_CURSORS
                cursor_changed = cursor_type != last_cursor_type
                
                if is_interactive or cursor_changed:
                    if hwnd > 0:
                        title = get_window_title(hwnd)
                        cls = get_window_class(hwnd)
                        elements.append(Element(
                            x=x, y=y,
                            cursor_type=cursor_type,
                            cursor_name=cursor_name,
                            hwnd=hwnd,
                            window_title=title,
                            window_class=cls,
                        ))
                
                last_cursor_type = cursor_type
                x += step_px
            y += step_px
    finally:
        if restore_cursor:
            user32.SetCursorPos(saved_pos.x, saved_pos.y)
    
    # Group into grid
    grid = _create_grid_mapping(elements, cell_size)
    grid_text = _render_grid_text(grid)
    
    # Also get window list for context
    windows = enum_windows()
    focused_hwnd = user32.GetForegroundWindow()
    focused_title = get_window_title(focused_hwnd) if focused_hwnd else ""
    
    return {
        "observed_at": time.time(),
        "screen_width": screen_w,
        "screen_height": screen_h,
        "step_px": step_px,
        "cell_size": cell_size,
        "elements": [e.to_dict() for e in elements],
        "grid": {k: [e.to_dict() for e in v] for k, v in grid.items()},
        "grid_text": grid_text,
        "windows": windows,
        "focused_title": focused_title,
        "focused_hwnd": focused_hwnd,
        "element_count": len(elements),
        "cell_count": len(grid),
    }


def observe(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Main observation entry point - calls hover_scan_fullscreen."""
    result = hover_scan_fullscreen(config)
    # Write observation artifact for debugging
    artifact_dir = ROOT / "comms" / "observations"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    import json
    artifact_path = artifact_dir / f"{int(result['observed_at'] * 1000)}.json"
    artifact_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    result["observation_artifact"] = {"path": artifact_path.relative_to(ROOT).as_posix(), "size": artifact_path.stat().st_size, "kind": "hover_scan_grid"}
    return result


def observe_screen() -> dict[str, int]:
    """Get screen dimensions."""
    w, h = get_screen_size()
    return {"width": w, "height": h}


def get_focused_title() -> str:
    """Get focused window title."""
    hwnd = user32.GetForegroundWindow()
    return get_window_title(hwnd) if hwnd else ""


def last_desktop_tree() -> dict[str, Any] | None:
    """Compatibility: return last observation as tree-like structure."""
    # This would need state persistence - for now return None
    return None


def last_action_index() -> dict[str, dict[str, Any]]:
    """Compatibility: return elements keyed by cell_id for execute."""
    # This would need state persistence - for now return empty
    return {}


def configure_observation(**kwargs) -> None:
    """No-op for compatibility."""
    pass


# =============================================================================
# Action Functions (re-export from win32_api)
# =============================================================================

__all__ = [
    "hover_scan_fullscreen",
    "observe",
    "observe_screen",
    "get_focused_title",
    "last_desktop_tree",
    "last_action_index",
    "configure_observation",
    "click_at",
    "type_text",
    "press_key",
    "hotkey",
    "scroll_at",
    "open_url",
    "Element",
    "set_foreground_window",
    "enum_windows",
    "window_at_point",
    "Desktop",  # compatibility class
    "get_desktop",  # compatibility function
]

# =============================================================================
# Compatibility Layer for Existing Code
# =============================================================================

class Desktop:
    """Compatibility wrapper - old Desktop class interface."""
    
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
    
    def observe(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        """Observe - returns compatible format."""
        result = hover_scan_fullscreen(config or self.config)
        # Convert to old format for compatibility
        return {
            "observed_at": result["observed_at"],
            "fresh_scan": True,
            "desktop_tree_text": result["grid_text"],
            "focused_title": result["focused_title"],
            "observation_artifact": {"path": "", "size": 0, "kind": "hover_scan_grid"},
        }
    
    def observe_screen(self) -> dict[str, int]:
        return observe_screen()
    
    def last_desktop_tree(self) -> dict[str, Any] | None:
        return None
    
    def last_action_index(self) -> dict[str, dict[str, Any]]:
        return {}
    
    def get_focused_title(self) -> str:
        return get_focused_title()
    
    def configure_observation(self, **kwargs) -> None:
        self.config.update(kwargs)
    
    # Action methods - delegate to module functions
    def click(self, x: int, y: int, hwnd: int = 0) -> dict:
        return click_at(x, y, hwnd)
    
    def type_text(self, text: str) -> dict:
        return type_text(text)
    
    def press_key(self, key: str) -> dict:
        return press_key(key)
    
    def hotkey(self, keys) -> dict:
        if isinstance(keys, str):
            keys = [k.strip() for k in keys.split("+")]
        return hotkey(keys)
    
    def scroll(self, x: int, y: int, amount: int, hwnd: int = 0) -> dict:
        return scroll_at(x, y, amount, hwnd)
    
    def focus_window(self, target: str) -> dict:
        return set_foreground_window(int(target)) if target.isdigit() else {"ok": False, "error": "use hwnd"}
    
    def open_url(self, browser: str = "chrome", url: str = "") -> dict:
        return open_url(browser, url)

    def render_tree_text(self, tree: dict[str, Any] | None = None) -> str:
        """Compatibility: render tree as text - returns grid text."""
        # In the new system, the "tree" is the grid text
        if tree and isinstance(tree, dict) and "grid_text" in tree:
            return tree["grid_text"]
        # Fallback: do a fresh scan and return grid text
        result = hover_scan_fullscreen(self.config)
        return result.get("grid_text", "SCAN EMPTY")


_desktop_instance: Desktop | None = None

def get_desktop(config: dict[str, Any] | None = None) -> Desktop:
    """Get or create the global desktop instance (compat)."""
    global _desktop_instance
    if _desktop_instance is None:
        _desktop_instance = Desktop(config)
    return _desktop_instance