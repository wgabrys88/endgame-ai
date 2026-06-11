"""Endgame-AI HUD — overlay reading snapshot.json + hot-swappable hud_design.json."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as w
import json
import os
import signal
import sys
import time
from collections import deque
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent.resolve()
SNAPSHOT_PATH = BASE_DIR / "snapshot.json"
HUD_DESIGN_PATH = BASE_DIR / "hud_design.json"
HUD_DESIGN_CHOSEN_PATH = BASE_DIR / "hud_design_chosen.json"
HUD_CALIBRATE_LOG_PATH = BASE_DIR / "hud_calibrate_log.jsonl"
PID_ROD_SCALE = 4.0

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from win32 import set_dpi_aware
import log

WS_EX_LAYERED = 0x80000
WS_EX_TOPMOST = 0x8
WS_EX_TRANSPARENT = 0x20
WS_EX_TOOLWINDOW = 0x80
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
ULW_ALPHA = 0x02
BI_RGB = 0
HWND_TOPMOST = w.HWND(-1)
SWP_NOMOVE = 0x2
SWP_NOSIZE = 0x1
SWP_NOACTIVATE = 0x10
CS_HREDRAW = 0x2
CS_VREDRAW = 0x1
IDC_ARROW = 32512
WM_DESTROY = 0x2
WM_PAINT = 0xF
WM_TIMER = 0x113
DT_LEFT = 0
DT_END_ELLIPSIS = 0x8000
PS_SOLID = 0
NULL_BRUSH = 5
TRANSPARENT_BK = 1
OPAQUE_BK = 2
FONT_QUALITY_NONANTIALIASED = 3
CURVE_SEGMENTS = 6

u32 = ctypes.windll.user32
g32 = ctypes.windll.gdi32
k32 = ctypes.windll.kernel32

g32.BitBlt.argtypes = [
    w.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    w.HDC, ctypes.c_int, ctypes.c_int, w.DWORD,
]
g32.BitBlt.restype = w.BOOL

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", w.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
        ("biPlanes", w.WORD), ("biBitCount", w.WORD), ("biCompression", w.DWORD),
        ("biSizeImage", w.DWORD), ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", w.DWORD),
        ("biClrImportant", w.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", w.DWORD * 3)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
        ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long), ("top", ctypes.c_long),
        ("right", ctypes.c_long), ("bottom", ctypes.c_long),
    ]


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ("hdc", w.HDC), ("fErase", w.BOOL), ("rcPaint", w.RECT),
        ("fRestore", w.BOOL), ("fIncUpdate", w.BOOL), ("rgbReserved", w.BYTE * 32),
    ]


g32.CreateCompatibleDC.argtypes = [w.HDC]
g32.CreateCompatibleDC.restype = w.HDC
g32.CreateCompatibleBitmap.argtypes = [w.HDC, ctypes.c_int, ctypes.c_int]
g32.CreateCompatibleBitmap.restype = w.HBITMAP
g32.SelectObject.argtypes = [w.HDC, w.HGDIOBJ]
g32.SelectObject.restype = w.HGDIOBJ
g32.DeleteObject.argtypes = [w.HGDIOBJ]
g32.DeleteObject.restype = w.BOOL
g32.DeleteDC.argtypes = [w.HDC]
g32.DeleteDC.restype = w.BOOL
g32.CreateDIBSection.argtypes = [
    w.HDC, ctypes.POINTER(BITMAPINFO), w.UINT,
    ctypes.POINTER(ctypes.c_void_p), w.HANDLE, w.DWORD,
]
g32.CreateDIBSection.restype = w.HBITMAP
g32.CreateSolidBrush.argtypes = [w.COLORREF]
g32.CreateSolidBrush.restype = w.HBRUSH
g32.CreatePen.argtypes = [ctypes.c_int, ctypes.c_int, w.COLORREF]
g32.CreatePen.restype = w.HPEN
g32.CreateFontW.argtypes = [
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.LPCWSTR,
]
g32.CreateFontW.restype = w.HFONT
g32.GetStockObject.argtypes = [ctypes.c_int]
g32.GetStockObject.restype = w.HGDIOBJ
g32.SetPixel.argtypes = [w.HDC, ctypes.c_int, ctypes.c_int, w.COLORREF]
g32.SetPixel.restype = w.COLORREF
g32.SetBkMode.argtypes = [w.HDC, ctypes.c_int]
g32.SetBkMode.restype = ctypes.c_int
g32.SetBkColor.argtypes = [w.HDC, w.COLORREF]
g32.SetBkColor.restype = w.COLORREF
g32.SetTextColor.argtypes = [w.HDC, w.COLORREF]
g32.SetTextColor.restype = w.COLORREF
g32.MoveToEx.argtypes = [w.HDC, ctypes.c_int, ctypes.c_int, ctypes.POINTER(w.POINT)]
g32.MoveToEx.restype = w.BOOL
g32.LineTo.argtypes = [w.HDC, ctypes.c_int, ctypes.c_int]
g32.LineTo.restype = w.BOOL
g32.RoundRect.argtypes = [
    w.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
]
g32.RoundRect.restype = w.BOOL
g32.Ellipse.argtypes = [w.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
g32.Ellipse.restype = w.BOOL
g32.Polyline.argtypes = [w.HDC, ctypes.POINTER(w.POINT), ctypes.c_int]
g32.Polyline.restype = w.BOOL
g32.Polygon.argtypes = [w.HDC, ctypes.POINTER(w.POINT), ctypes.c_int]
g32.Polygon.restype = w.BOOL
u32.FillRect.argtypes = [w.HDC, ctypes.POINTER(RECT), w.HBRUSH]
u32.FillRect.restype = ctypes.c_int
u32.DrawTextW.argtypes = [w.HDC, w.LPCWSTR, ctypes.c_int, ctypes.POINTER(RECT), w.UINT]
u32.DrawTextW.restype = ctypes.c_int
u32.GetDC.argtypes = [w.HWND]
u32.GetDC.restype = w.HDC
u32.ReleaseDC.argtypes = [w.HWND, w.HDC]
u32.ReleaseDC.restype = ctypes.c_int
u32.BeginPaint.argtypes = [w.HWND, ctypes.POINTER(PAINTSTRUCT)]
u32.BeginPaint.restype = w.HDC
u32.EndPaint.argtypes = [w.HWND, ctypes.POINTER(PAINTSTRUCT)]
u32.EndPaint.restype = w.BOOL
u32.UpdateLayeredWindow.argtypes = [
    w.HWND, w.HDC, ctypes.POINTER(POINT), ctypes.POINTER(SIZE),
    w.HDC, ctypes.POINTER(POINT), w.COLORREF, ctypes.POINTER(BLENDFUNCTION), w.DWORD,
]
u32.UpdateLayeredWindow.restype = w.BOOL

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_long, w.HWND, w.UINT, ctypes.c_uint64, ctypes.c_int64)
u32.DefWindowProcW.argtypes = [w.HWND, w.UINT, ctypes.c_uint64, ctypes.c_int64]
u32.DefWindowProcW.restype = ctypes.c_long


class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ("style", w.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int), ("hInstance", w.HINSTANCE), ("hIcon", w.HANDLE),
        ("hCursor", w.HANDLE), ("hbrBackground", w.HANDLE), ("lpszMenuName", w.LPCWSTR),
        ("lpszClassName", w.LPCWSTR),
    ]


def rgb(r: int, g: int, b: int) -> int:
    return r | (g << 8) | (b << 16)


# =============================================================================
# HUD CONFIG — defaults; hot-swapped at runtime via hud_design.json
# =============================================================================

REFRESH_MS_DEFAULT = 500
EVENTS_ACTIVE_SCAN = 64

_DESIGN_DEFAULTS: dict[str, Any] = {
    "layout": "dashboard",
    "scale_w_pct": 100,
    "scale_h_pct": 100,
    "align": "center",
    "font_name": "Segoe UI",
    "font_size": 30,
    "font_weight": 500,
    "backdrop_r": 8,
    "backdrop_g": 8,
    "backdrop_b": 12,
    "backdrop_alpha": 255,
    "panel_r": 12,
    "panel_g": 12,
    "panel_b": 16,
    "plot_inner_r": 6,
    "plot_inner_g": 6,
    "plot_inner_b": 10,
    "right_panel_w_ratio": 0.28,
    "plot_history_len": 60,
    "plot_grid_cols_trace": 8,
    "plot_grid_rows_trace": 5,
    "plot_grid_cols_lorenz": 6,
    "plot_grid_rows_lorenz": 6,
    "plot_lorenz_range_pad": 0.08,
    "c_edge_r": 100, "c_edge_g": 160, "c_edge_b": 235,
    "c_text_r": 235, "c_text_g": 242, "c_text_b": 255,
    "c_dim_r": 145, "c_dim_g": 155, "c_dim_b": 180,
    "c_accent_r": 100, "c_accent_g": 170, "c_accent_b": 255,
    "c_run_r": 72, "c_run_g": 210, "c_run_b": 120,
    "c_pause_r": 255, "c_pause_g": 175, "c_pause_b": 55,
    "c_ready_r": 130, "c_ready_g": 170, "c_ready_b": 255,
    "c_stag_r": 255, "c_stag_g": 95, "c_stag_b": 80,
    "c_pid_r": 80, "c_pid_g": 145, "c_pid_b": 255,
    "c_energy_r": 115, "c_energy_g": 220, "c_energy_b": 140,
    "c_wing_r": 255, "c_wing_g": 200, "c_wing_b": 50,
    "c_done_r": 70, "c_done_g": 210, "c_done_b": 110,
    "c_active_r": 255, "c_active_g": 210, "c_active_b": 70,
    "c_grid_r": 80, "c_grid_g": 100, "c_grid_b": 135,
}

FONT_NAME = "Segoe UI"
FONT_SIZE = 30
FONT_WEIGHT = 500
BACKDROP_R, BACKDROP_G, BACKDROP_B = 18, 18, 28
BACKDROP_ALPHA = 90
RIGHT_PANEL_W_RATIO = 0.28
PLOT_HISTORY_LEN = 60
PLOT_GRID_COLS_TRACE = 8
PLOT_GRID_ROWS_TRACE = 5
PLOT_GRID_COLS_LORENZ = 6
PLOT_GRID_ROWS_LORENZ = 6
PLOT_LORENZ_RANGE_PAD = 0.08

LINE_H = 38
MARGIN = 15
GAP_SECTION = 7
GAP_PANEL = 10
GAP_COLUMN = 10
PAD_PANEL = 15
PAD_PLOT = 15
PAD_PLOT_INNER = 7
PAD_INSET = 2
HEADER_H = 0
METRICS_H = 0
LEFT_PANEL_W = 270
RIGHT_PANEL_W_MIN = 300
RIGHT_PANEL_W_MAX = 420
RADIUS_HEADER = 15
RADIUS_PANEL = 15
RADIUS_CARD = 10
RADIUS_PLOT = 10
RADIUS_PLOT_INNER = 4
RADIUS_BADGE = 7
RADIUS_LEGEND = 2
RADIUS_EMPTY = 15
HEADER_BADGE_W = 150
HEADER_BADGE_H = 38
HEADER_LOGO_X = 15
HEADER_TEXT_X = 45
HEADER_CLOCK_W = 150
LOGO_SIZE = 30
METRIC_PROGRESS_H = 10
METRIC_BAR_PAD = 30
AGENT_CHAIN_GAP = 7
AGENT_DOT_R = 5
AGENT_DOT_X = 4
AGENT_NAME_X = 18
DONE_WHEN_BOX_H = 0
PLAN_MARK_X = 15
PLAN_TEXT_X = 45
PLAN_MIN_WRAP = 8
PLOT_BODY_Y = 0
PLOT_AREA_PAD = 30
PLOT_FRAME_EXTRA_H = 0
LEGEND_SIZE = 10
LEGEND_GAP = 60
LEGEND_LABEL_OFF = 12
EMPTY_BOX_W = 360
EMPTY_BOX_H = 0
EMPTY_PAD = 15
EDGE_THICK = 2
OUTLINE_PAD = 2
PLOT_LINE_THICK = 2
LOGO_POLYGON_THICK = 2
PROGRESS_FILL_THICK = 1
LEGEND_FILL_THICK = 1

C_EDGE = rgb(100, 160, 235)
C_OUTLINE = rgb(0, 0, 0)
C_TEXT = rgb(235, 242, 255)
C_DIM = rgb(145, 155, 180)
C_ACCENT = rgb(100, 170, 255)
C_RUN = rgb(72, 210, 120)
C_PAUSE = rgb(255, 175, 55)
C_READY = rgb(130, 170, 255)
C_STAG = rgb(255, 95, 80)
C_PID = rgb(80, 145, 255)
C_ENERGY = rgb(115, 220, 140)
C_WING = rgb(255, 200, 50)
C_DONE = rgb(70, 210, 110)
C_ACTIVE = rgb(255, 210, 70)
C_GRID = rgb(80, 100, 135)
C_BACKDROP = rgb(18, 18, 28)
C_PANEL = rgb(20, 22, 34)
C_PLOT_INNER = rgb(12, 14, 24)

_TEXT_OUTLINE = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))

MATH_CHAIN = ("stagnation", "lorenz", "pid")
AGENT_CHAIN = ("planner", "actor", "verifier", "fission")
SIDE_AGENTS = ("observer", "reflector")
MATH_PHASES = frozenset(MATH_CHAIN)
LOOP_PHASES = frozenset({
    "schedule", "plan", "actor", "action", "observe", "verify",
    "reflect", "mutation", "fission", "fission_blocked", "goal_change",
    "planner.error", "actor.error", "verifier.error", "reflector.error",
})
REFLECT_SCHEDULE_REASONS = frozenset({"pid_gate", "chaos_gate", "stag_gate"})
SCHEDULE_LOOP_AGENT = {
    "execute": "actor", "advance": "actor", "need_plan": "planner",
    "wing_cross": "planner", "stuck": "planner", "plan_complete": "verifier",
}
LOOP_PHASE_AGENT = {
    "plan": "planner", "planner.error": "planner",
    "actor": "actor", "action": "actor", "actor.error": "actor",
    "verify": "verifier", "verifier.error": "verifier",
    "fission": "fission", "fission_sustain": "fission", "fission_blocked": "fission",
}

SW = 0
SH = 0
VX = 0
VY = 0
VW = 0
VH = 0
LAYOUT_MODE = "dashboard"

snapshot: dict[str, Any] = {}
last_mtime = 0.0
_design: dict[str, Any] = dict(_DESIGN_DEFAULTS)
_design_mtime = 0.0
math_hist: deque[dict[str, float]] = deque(maxlen=60)
lorenz_hist: deque[tuple[float, float]] = deque(maxlen=60)
math_active = "—"
loop_active = "—"
side_active = "—"
_hwnd: int | None = None
_layer: dict[str, Any] = {}
_font_handle: int | None = None
_font_key: tuple[Any, ...] = ()
_last_clock = ""
_last_agents: tuple[str, str, str] = ("—", "—", "—")


def _sync_layout() -> None:
    global LINE_H, MARGIN, GAP_SECTION, GAP_PANEL, GAP_COLUMN, PAD_PANEL, PAD_PLOT
    global PAD_PLOT_INNER, PAD_INSET, HEADER_H, METRICS_H, LEFT_PANEL_W
    global RIGHT_PANEL_W_MIN, RIGHT_PANEL_W_MAX, RADIUS_HEADER, RADIUS_PANEL, RADIUS_CARD
    global RADIUS_PLOT, RADIUS_PLOT_INNER, RADIUS_BADGE, RADIUS_LEGEND, RADIUS_EMPTY
    global HEADER_BADGE_W, HEADER_BADGE_H, HEADER_LOGO_X, HEADER_TEXT_X, HEADER_CLOCK_W
    global LOGO_SIZE, METRIC_PROGRESS_H, METRIC_BAR_PAD, AGENT_CHAIN_GAP, AGENT_DOT_R
    global AGENT_DOT_X, AGENT_NAME_X, DONE_WHEN_BOX_H, PLAN_MARK_X, PLAN_TEXT_X
    global PLOT_BODY_Y, PLOT_AREA_PAD, PLOT_FRAME_EXTRA_H, LEGEND_SIZE, LEGEND_GAP
    global LEGEND_LABEL_OFF, EMPTY_BOX_W, EMPTY_BOX_H, EMPTY_PAD, EDGE_THICK, OUTLINE_PAD
    global PLOT_LINE_THICK, LOGO_POLYGON_THICK
    LINE_H = FONT_SIZE + 8
    MARGIN = FONT_SIZE // 2
    GAP_SECTION = FONT_SIZE // 4
    GAP_PANEL = FONT_SIZE // 3
    GAP_COLUMN = GAP_PANEL
    PAD_PANEL = FONT_SIZE // 2
    PAD_PLOT = PAD_PANEL
    PAD_PLOT_INNER = FONT_SIZE // 4
    PAD_INSET = max(2, FONT_SIZE // 12)
    HEADER_H = PAD_PANEL + LINE_H * 4 + PAD_PANEL
    METRICS_H = PAD_PANEL + LINE_H * 2 + max(8, FONT_SIZE // 3) + PAD_PANEL * 2
    LEFT_PANEL_W = FONT_SIZE * 9
    RIGHT_PANEL_W_MIN = FONT_SIZE * 10
    RIGHT_PANEL_W_MAX = FONT_SIZE * 14
    RADIUS_HEADER = FONT_SIZE // 2
    RADIUS_PANEL = RADIUS_HEADER
    RADIUS_CARD = FONT_SIZE // 3
    RADIUS_PLOT = RADIUS_CARD
    RADIUS_PLOT_INNER = FONT_SIZE // 7
    RADIUS_BADGE = FONT_SIZE // 4
    RADIUS_LEGEND = max(2, FONT_SIZE // 12)
    RADIUS_EMPTY = FONT_SIZE // 2
    HEADER_BADGE_W = FONT_SIZE * 5
    HEADER_BADGE_H = LINE_H
    HEADER_LOGO_X = PAD_PANEL
    HEADER_TEXT_X = PAD_PANEL + FONT_SIZE
    HEADER_CLOCK_W = FONT_SIZE * 5
    LOGO_SIZE = FONT_SIZE
    METRIC_PROGRESS_H = max(8, FONT_SIZE // 3)
    METRIC_BAR_PAD = PAD_PANEL * 2
    AGENT_CHAIN_GAP = GAP_SECTION
    AGENT_DOT_R = FONT_SIZE // 6
    AGENT_DOT_X = PAD_INSET * 2
    AGENT_NAME_X = AGENT_DOT_X + AGENT_DOT_R * 2 + PAD_INSET
    DONE_WHEN_BOX_H = LINE_H * 2 + PAD_PANEL
    PLAN_MARK_X = PAD_PANEL
    PLAN_TEXT_X = PAD_PANEL + FONT_SIZE
    PLOT_BODY_Y = PAD_PANEL + LINE_H + PAD_INSET
    PLOT_AREA_PAD = PAD_PLOT * 2
    PLOT_FRAME_EXTRA_H = PLOT_BODY_Y + PAD_PLOT
    LEGEND_SIZE = FONT_SIZE // 3
    LEGEND_GAP = FONT_SIZE * 2
    LEGEND_LABEL_OFF = LEGEND_SIZE + PAD_INSET
    EMPTY_BOX_W = FONT_SIZE * 12
    EMPTY_BOX_H = LINE_H * 4
    EMPTY_PAD = PAD_PANEL
    EDGE_THICK = max(2, FONT_SIZE // 12)
    OUTLINE_PAD = EDGE_THICK
    PLOT_LINE_THICK = EDGE_THICK
    LOGO_POLYGON_THICK = EDGE_THICK


def _update_viewport(d: dict[str, Any]) -> None:
    global VX, VY, VW, VH
    sw_pct = max(20, min(100, int(d.get("scale_w_pct", 100))))
    sh_pct = max(20, min(100, int(d.get("scale_h_pct", 100))))
    if SW > 0 and SH > 0:
        VW = max(200, int(SW * sw_pct / 100))
        VH = max(200, int(SH * sh_pct / 100))
    else:
        VW, VH = 1920, 1080
    align = str(d.get("align", "center")).lower()
    if align == "topleft":
        VX, VY = 0, 0
    else:
        VX = max(0, (SW - VW) // 2) if SW > 0 else 0
        VY = max(0, (SH - VH) // 2) if SH > 0 else 0


def _clamp_byte(v: Any) -> int:
    return max(0, min(255, int(v)))


def _color_from(d: dict[str, Any], prefix: str) -> int:
    return rgb(
        _clamp_byte(d[f"{prefix}_r"]),
        _clamp_byte(d[f"{prefix}_g"]),
        _clamp_byte(d[f"{prefix}_b"]),
    )


def _apply_design(d: dict[str, Any]) -> None:
    global FONT_NAME, FONT_SIZE, FONT_WEIGHT, BACKDROP_R, BACKDROP_G, BACKDROP_B
    global BACKDROP_ALPHA, RIGHT_PANEL_W_RATIO, PLOT_HISTORY_LEN
    global PLOT_GRID_COLS_TRACE, PLOT_GRID_ROWS_TRACE, PLOT_GRID_COLS_LORENZ
    global PLOT_GRID_ROWS_LORENZ, PLOT_LORENZ_RANGE_PAD, C_BACKDROP, C_PANEL, C_PLOT_INNER, _design
    global C_EDGE, C_TEXT, C_DIM, C_ACCENT, C_RUN, C_PAUSE, C_READY, C_STAG, C_PID
    global C_ENERGY, C_WING, C_DONE, C_ACTIVE, C_GRID, LAYOUT_MODE
    global math_hist, lorenz_hist
    merged = {**_DESIGN_DEFAULTS, **{k: v for k, v in d.items() if k in _DESIGN_DEFAULTS}}
    _design = merged
    LAYOUT_MODE = str(merged.get("layout", "dashboard")).lower()
    FONT_NAME = str(merged["font_name"])
    FONT_SIZE = max(10, min(72, int(merged["font_size"])))
    FONT_WEIGHT = max(100, min(900, int(merged["font_weight"])))
    BACKDROP_R = _clamp_byte(merged["backdrop_r"])
    BACKDROP_G = _clamp_byte(merged["backdrop_g"])
    BACKDROP_B = _clamp_byte(merged["backdrop_b"])
    BACKDROP_ALPHA = _clamp_byte(merged["backdrop_alpha"])
    RIGHT_PANEL_W_RATIO = max(0.15, min(0.45, float(merged["right_panel_w_ratio"])))
    PLOT_HISTORY_LEN = max(10, min(200, int(merged["plot_history_len"])))
    PLOT_GRID_COLS_TRACE = max(2, int(merged["plot_grid_cols_trace"]))
    PLOT_GRID_ROWS_TRACE = max(2, int(merged["plot_grid_rows_trace"]))
    PLOT_GRID_COLS_LORENZ = max(2, int(merged["plot_grid_cols_lorenz"]))
    PLOT_GRID_ROWS_LORENZ = max(2, int(merged["plot_grid_rows_lorenz"]))
    PLOT_LORENZ_RANGE_PAD = max(0.0, min(0.5, float(merged["plot_lorenz_range_pad"])))
    C_BACKDROP = rgb(BACKDROP_R, BACKDROP_G, BACKDROP_B)
    C_PANEL = _color_from(merged, "panel")
    C_PLOT_INNER = _color_from(merged, "plot_inner")
    C_EDGE = _color_from(merged, "c_edge")
    C_TEXT = _color_from(merged, "c_text")
    C_DIM = _color_from(merged, "c_dim")
    C_ACCENT = _color_from(merged, "c_accent")
    C_RUN = _color_from(merged, "c_run")
    C_PAUSE = _color_from(merged, "c_pause")
    C_READY = _color_from(merged, "c_ready")
    C_STAG = _color_from(merged, "c_stag")
    C_PID = _color_from(merged, "c_pid")
    C_ENERGY = _color_from(merged, "c_energy")
    C_WING = _color_from(merged, "c_wing")
    C_DONE = _color_from(merged, "c_done")
    C_ACTIVE = _color_from(merged, "c_active")
    C_GRID = _color_from(merged, "c_grid")
    _sync_layout()
    _update_viewport(merged)
    _invalidate_font()
    _release_layer()
    math_hist = deque(math_hist, maxlen=PLOT_HISTORY_LEN)
    lorenz_hist = deque(lorenz_hist, maxlen=PLOT_HISTORY_LEN)


def read_design() -> bool:
    global _design_mtime
    path = str(HUD_DESIGN_PATH)
    try:
        mt = os.path.getmtime(path)
    except OSError:
        if _design_mtime == 0:
            _apply_design(_DESIGN_DEFAULTS)
            _design_mtime = -1.0
        return False
    if mt == _design_mtime:
        return False
    _design_mtime = mt
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError, TypeError):
        return False
    if not isinstance(data, dict):
        return False
    _apply_design(data)
    return True


def _init_screen() -> None:
    global SW, SH
    set_dpi_aware()
    SW = u32.GetSystemMetrics(0)
    SH = u32.GetSystemMetrics(1)
    _update_viewport(_design)


def _layer_size() -> tuple[int, int]:
    if LAYOUT_MODE == "column" and VW > 0 and VH > 0:
        return VW, VH
    return SW, SH


def _invalidate_font() -> None:
    global _font_handle, _font_key
    if _font_handle:
        g32.DeleteObject(_font_handle)
    _font_handle = None
    _font_key = ()


def _get_font() -> int:
    global _font_handle, _font_key
    key = (FONT_NAME, FONT_SIZE, FONT_WEIGHT, LAYOUT_MODE)
    if _font_handle and key == _font_key:
        return _font_handle
    _invalidate_font()
    _font_handle = _make_font()
    _font_key = key
    return _font_handle


def _ensure_layer(screen_dc: int) -> tuple[int, ctypes.c_void_p]:
    lw, lh = _layer_size()
    if _layer and (_layer.get("lw") != lw or _layer.get("lh") != lh):
        _release_layer()
    if _layer:
        return _layer["mem_dc"], _layer["bits"]
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = lw
    bmi.bmiHeader.biHeight = -lh
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = BI_RGB
    bits = ctypes.c_void_p()
    dib = g32.CreateDIBSection(screen_dc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
    if not dib:
        raise OSError("CreateDIBSection failed")
    mem_dc = g32.CreateCompatibleDC(screen_dc)
    if not mem_dc:
        g32.DeleteObject(dib)
        raise OSError("CreateCompatibleDC failed")
    g32.SelectObject(mem_dc, dib)
    _layer.update(mem_dc=mem_dc, dib=dib, bits=bits, lw=lw, lh=lh)
    return mem_dc, bits


def _release_layer() -> None:
    if not _layer:
        return
    if _layer.get("mem_dc"):
        g32.DeleteDC(_layer["mem_dc"])
    if _layer.get("dib"):
        g32.DeleteObject(_layer["dib"])
    _layer.clear()


def _clear_layer(bits: ctypes.c_void_p) -> None:
    lw, lh = _layer_size()
    ctypes.memset(bits, 0, lw * lh * 4)


def _draw_backdrop(bits: ctypes.c_void_p) -> None:
    if not bits.value:
        return
    lw, lh = _layer_size()
    if lw <= 0 or lh <= 0:
        return
    b, g, r, a = BACKDROP_B & 0xFF, BACKDROP_G & 0xFF, BACKDROP_R & 0xFF, BACKDROP_ALPHA
    n = lw * lh * 4
    buf = (ctypes.c_ubyte * n).from_address(bits.value)
    if LAYOUT_MODE == "column":
        i = 0
        while i < n:
            buf[i] = b
            buf[i + 1] = g
            buf[i + 2] = r
            buf[i + 3] = a
            i += 4
        return
    row_stride = lw * 4
    y_end = min(VY + VH, lh)
    x_end = min(VX + VW, lw)
    for y in range(VY, y_end):
        row = y * row_stride + VX * 4
        for x in range(VX, x_end):
            i = row + (x - VX) * 4
            buf[i] = b
            buf[i + 1] = g
            buf[i + 2] = r
            buf[i + 3] = a


def _fix_layer_alpha(bits: ctypes.c_void_p) -> None:
    if not bits.value:
        return
    lw, lh = _layer_size()
    n = lw * lh * 4
    buf = (ctypes.c_ubyte * n).from_address(bits.value)
    i = 3
    while i < n:
        if buf[i] == 0 and (buf[i - 3] or buf[i - 2] or buf[i - 1]):
            buf[i] = 255
        elif 0 < buf[i] < 255 and (buf[i - 3] or buf[i - 2] or buf[i - 1]):
            buf[i] = 255
        i += 4


def _needs_redraw(design_changed: bool, snapshot_changed: bool) -> bool:
    global _last_clock, _last_agents
    if design_changed or snapshot_changed:
        return True
    clk = time.strftime("%H:%M:%S")
    if clk != _last_clock:
        _last_clock = clk
        return True
    agents = (math_active, loop_active, side_active)
    if agents != _last_agents:
        _last_agents = agents
        return True
    return False


def _present(hwnd: int, screen_dc: int) -> None:
    global VX, VY
    dst_x, dst_y = VX, VY
    saved_vx, saved_vy = VX, VY
    if LAYOUT_MODE == "column":
        VX, VY = 0, 0
    lw, lh = _layer_size()
    try:
        mem_dc, bits = _ensure_layer(screen_dc)
        _clear_layer(bits)
        _draw_backdrop(bits)
        g32.SetBkMode(mem_dc, 1)
        if not snapshot:
            _draw_empty(mem_dc)
        elif LAYOUT_MODE == "column":
            _draw_column_hud(mem_dc)
        else:
            lay = _layout()
            _draw_header(mem_dc)
            _draw_metrics(mem_dc)
            _draw_agents(mem_dc, lay["left_x"], lay["body_y"], lay["left_w"], lay["body_h"])
            _draw_plan(mem_dc, lay["center_x"], lay["body_y"], lay["center_w"], lay["body_h"])
            _draw_plots(mem_dc, lay["right_x"], lay["body_y"], lay["right_w"], lay["body_h"])
        _fix_layer_alpha(bits)
        pt_dst = POINT(dst_x, dst_y)
        sz = SIZE(lw, lh)
        pt_src = POINT(0, 0)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        u32.UpdateLayeredWindow(
            hwnd, None, ctypes.byref(pt_dst), ctypes.byref(sz),
            mem_dc, ctypes.byref(pt_src), 0, ctypes.byref(blend), ULW_ALPHA,
        )
    finally:
        if LAYOUT_MODE == "column":
            VX, VY = saved_vx, saved_vy


def _fill(hdc: int, x: int, y: int, wd: int, h: int, color: int) -> None:
    brush = g32.CreateSolidBrush(color)
    u32.FillRect(hdc, ctypes.byref(RECT(x, y, x + wd, y + h)), brush)
    g32.DeleteObject(brush)


def _line_raw(hdc: int, x1: int, y1: int, x2: int, y2: int, color: int, thick: int) -> None:
    pen = g32.CreatePen(PS_SOLID, thick, color)
    old = g32.SelectObject(hdc, pen)
    g32.MoveToEx(hdc, x1, y1, None)
    g32.LineTo(hdc, x2, y2)
    g32.SelectObject(hdc, old)
    g32.DeleteObject(pen)


def _line(hdc: int, x1: int, y1: int, x2: int, y2: int, color: int, thick: int = EDGE_THICK) -> None:
    ot = thick + OUTLINE_PAD
    _line_raw(hdc, x1, y1, x2, y2, C_OUTLINE, ot)
    _line_raw(hdc, x1, y1, x2, y2, color, thick)


def _roundrect_raw(hdc: int, x: int, y: int, wd: int, h: int, radius: int,
                   fill: int | None, border: int, thick: int) -> None:
    pen = g32.CreatePen(PS_SOLID, thick, border)
    old_pen = g32.SelectObject(hdc, pen)
    if fill is not None:
        brush = g32.CreateSolidBrush(fill)
        old_brush = g32.SelectObject(hdc, brush)
    else:
        old_brush = g32.SelectObject(hdc, g32.GetStockObject(NULL_BRUSH))
    g32.RoundRect(hdc, x, y, x + wd, y + h, radius, radius)
    g32.SelectObject(hdc, old_pen)
    g32.SelectObject(hdc, old_brush)
    g32.DeleteObject(pen)
    if fill is not None:
        g32.DeleteObject(brush)


def _roundbox(hdc: int, x: int, y: int, wd: int, h: int, radius: int,
              fill: int | None, border: int | None = None, thick: int = EDGE_THICK) -> None:
    edge = C_EDGE if border is None else border
    _roundrect_raw(hdc, x, y, wd, h, radius, fill, C_OUTLINE, thick + OUTLINE_PAD)
    _roundrect_raw(hdc, x, y, wd, h, radius, fill, edge, thick)


def _text_raw(hdc: int, x: int, y: int, text: str, right: int, bottom: int, color: int) -> None:
    g32.SetTextColor(hdc, color)
    r = RECT(x, y, right, bottom)
    u32.DrawTextW(hdc, text, -1, ctypes.byref(r), DT_LEFT | DT_END_ELLIPSIS)


def _make_font(weight: int | None = None) -> int:
    w = FONT_WEIGHT if weight is None else weight
    q = FONT_QUALITY_NONANTIALIASED if LAYOUT_MODE == "column" else 0
    return g32.CreateFontW(
        FONT_SIZE, 0, 0, 0, w, 0, 0, 0, 0, 0, 0, q, 0, FONT_NAME,
    )


def _text_solid(hdc: int, x: int, y: int, text: str, color: int = C_TEXT,
                max_w: int | None = None, bg: int | None = None) -> None:
    if not text:
        return
    old = g32.SelectObject(hdc, _get_font())
    g32.SetBkMode(hdc, OPAQUE_BK)
    g32.SetBkColor(hdc, C_BACKDROP if bg is None else bg)
    right = max_w if max_w is not None else VX + VW - PAD_PANEL
    bottom = y + LINE_H
    _text_raw(hdc, x, y, text, right, bottom, color)
    g32.SetBkMode(hdc, TRANSPARENT_BK)
    g32.SelectObject(hdc, old)


def _text(hdc: int, x: int, y: int, text: str, color: int = C_TEXT, max_w: int | None = None,
          bg: int | None = None) -> None:
    if not text:
        return
    if LAYOUT_MODE == "column":
        _text_solid(hdc, x, y, text, color, max_w, bg)
        return
    old = g32.SelectObject(hdc, _get_font())
    g32.SetBkMode(hdc, TRANSPARENT_BK)
    right = max_w if max_w is not None else VX + VW - MARGIN
    bottom = y + LINE_H
    for ox, oy in _TEXT_OUTLINE:
        _text_raw(hdc, x + ox, y + oy, text, right + ox, bottom + oy, C_OUTLINE)
    _text_raw(hdc, x, y, text, right, bottom, color)
    g32.SelectObject(hdc, old)


def _metric_card_h() -> int:
    return PAD_PANEL + LINE_H * 2 + METRIC_PROGRESS_H + PAD_PANEL


def _agents_block_h() -> int:
    n = len(MATH_CHAIN) + len(AGENT_CHAIN) + len(SIDE_AGENTS)
    return (
        PAD_PANEL + LINE_H + PAD_INSET + LINE_H * 3 + LINE_H * n
        + AGENT_CHAIN_GAP * 2 + PAD_PANEL
    )


def _layout_column() -> dict[str, int]:
    x = VX
    wd = VW
    y = VY
    floor = VY + VH
    pad = PAD_PANEL
    header_h = LINE_H * 3 + pad
    agents_h = LINE_H + pad
    plan_h = LINE_H * 3 + pad
    plots_y = y + header_h + agents_h + plan_h
    plots_h = max(220, floor - plots_y - pad)
    return {
        "x": x, "w": wd, "pad": pad,
        "header_y": y, "header_h": header_h,
        "agents_y": y + header_h, "agents_h": agents_h,
        "plan_y": y + header_h + agents_h, "plan_h": plan_h,
        "plots_y": plots_y, "plots_h": plots_h,
    }


def _col_divider(hdc: int, x: int, y: int, wd: int) -> None:
    _line_raw(hdc, x + PAD_PANEL, y, x + wd - PAD_PANEL, y, C_EDGE, 1)


def _draw_header_column(hdc: int, x: int, y: int, wd: int, h: int) -> None:
    pad = PAD_PANEL
    ty = y + pad // 2
    lx = x + pad
    _polygon(
        hdc,
        [(lx, ty), (lx + LOGO_SIZE, ty), (lx + LOGO_SIZE // 2, ty + LOGO_SIZE)],
        C_ACCENT, LOGO_POLYGON_THICK, C_ACCENT,
    )
    _text(hdc, x + pad + LOGO_SIZE + PAD_INSET, ty, "ENDGAME-AI", C_TEXT)
    status, sc = _status()
    _text(hdc, x + wd - pad - FONT_SIZE * 4, ty, status, sc)
    _text(hdc, x + pad, ty + LINE_H, "reactor monitor", C_DIM)
    _text(hdc, x + wd - pad - FONT_SIZE * 5, ty + LINE_H, time.strftime("%H:%M:%S"), C_DIM)
    work = int(snapshot.get("work_events", 0))
    budget = int(snapshot.get("budget", 20))
    events_n = int(snapshot.get("events", 0))
    failures = int(snapshot.get("consecutive_failures", 0))
    stats = f"ev {events_n}  fail {failures}  {work}/{budget}"
    if snapshot.get("wing_crossed"):
        stats += "  WING"
    _text(hdc, x + pad, ty + LINE_H * 2, stats, C_DIM, max_w=x + wd - pad)
    goal = str(snapshot.get("goal", "") or "—")
    if len(goal) > 48:
        goal = goal[:45] + "…"
    _text(hdc, x + pad, y + h - LINE_H - pad // 2, goal, C_TEXT, max_w=x + wd - pad)


def _draw_agents_column(hdc: int, x: int, y: int, wd: int, h: int) -> None:
    pad = PAD_PANEL
    cy = y + pad // 2
    line = (
        f"MATH {math_active}   LOOP {loop_active}   SIDE {side_active}"
    )
    _text(hdc, x + pad, cy, line, C_DIM, max_w=x + wd - pad)


def _draw_plan_column(hdc: int, x: int, y: int, wd: int, h: int) -> None:
    pad = PAD_PANEL
    ty = y + pad // 2
    plan: list[dict[str, Any]] = snapshot.get("plan", [])
    done_n = sum(1 for p in plan if p.get("status") == "done")
    title = f"PLAN {done_n}/{len(plan)}" if plan else "PLAN"
    _text(hdc, x + pad, ty, title, C_ACCENT)
    cy = ty + LINE_H
    max_lines = 2
    if not plan:
        completed = snapshot.get("completed", [])
        msg = str(completed[-1]) if completed else "no plan"
        if len(msg) > 56:
            msg = msg[:53] + "…"
        _text(hdc, x + pad, cy, msg, C_DIM if not completed else C_DONE, max_w=x + wd - pad)
        return
    shown = 0
    for step in plan:
        if shown >= max_lines:
            break
        st = step.get("status", "pending")
        txt = str(step.get("text", ""))
        if len(txt) > 52:
            txt = txt[:49] + "…"
        if st == "done":
            mark, col = "✓", C_DONE
        elif st == "active":
            mark, col = ">", C_ACTIVE
        else:
            mark, col = "·", C_DIM
        _text(hdc, x + pad, cy, f"{mark} {txt}", col, max_w=x + wd - pad)
        cy += LINE_H
        shown += 1


def _catmull(v0: float, v1: float, v2: float, v3: float, t: float) -> float:
    t2 = t * t
    t3 = t2 * t
    return 0.5 * (
        (2 * v1) + (-v0 + v2) * t + (2 * v0 - 5 * v1 + 4 * v2 - v3) * t2
        + (-v0 + 3 * v1 - 3 * v2 + v3) * t3
    )


def _smooth_curve(pts: list[tuple[int, int]], segs: int = CURVE_SEGMENTS) -> list[tuple[int, int]]:
    if len(pts) < 2:
        return pts
    out: list[tuple[int, int]] = []
    for i in range(len(pts) - 1):
        p0 = pts[max(0, i - 1)]
        p1 = pts[i]
        p2 = pts[i + 1]
        p3 = pts[min(len(pts) - 1, i + 2)]
        for s in range(segs):
            t = s / segs
            sx = int(_catmull(p0[0], p1[0], p2[0], p3[0], t))
            sy = int(_catmull(p0[1], p1[1], p2[1], p3[1], t))
            out.append((sx, sy))
    out.append(pts[-1])
    return out


def _draw_curve_series(
    hdc: int, values: list[float], px: int, py: int, pw: int, ph: int,
    lo: float, hi: float, color: int, label: str,
) -> None:
    if len(values) < 2:
        return
    pts = _series_points(values, px, py, pw, ph, lo, hi)
    curve = _smooth_curve(pts)
    _polyline_raw(hdc, curve, color, PLOT_LINE_THICK + 1)
    tip = curve[-1]
    val = values[-1]
    _circle(hdc, tip[0], tip[1], AGENT_DOT_R + 1, color, 1, color)
    lx = min(tip[0] + 6, px + pw - FONT_SIZE * 5)
    ly = max(py + 2, tip[1] - LINE_H // 2)
    _text_solid(hdc, lx, ly, f"{label} {val:.2f}", color, bg=C_PLOT_INNER, max_w=px + pw)


def _plot_area(hdc: int, x: int, y: int, wd: int, h: int, title: str) -> tuple[int, int, int, int]:
    pad = PAD_PANEL
    _text(hdc, x + pad, y + PAD_INSET, title, C_ACCENT)
    py = y + LINE_H + PAD_INSET
    ph = h - LINE_H - PAD_INSET * 2
    px, pw = x + pad, wd - pad * 2
    _fill(hdc, px, py, pw, ph, C_PLOT_INNER)
    return px, py, pw, ph


def _draw_trace_curves(hdc: int, x: int, y: int, wd: int, h: int) -> None:
    px, py, pw, ph = _plot_area(hdc, x, y, wd, h, "TRACE")
    _grid(hdc, px, py, pw, ph, PLOT_GRID_COLS_TRACE, PLOT_GRID_ROWS_TRACE)
    data = list(math_hist)
    if len(data) < 2:
        _text(hdc, px + PAD_INSET, py + ph // 2, "collecting…", C_DIM, bg=C_PLOT_INNER)
        return
    stags = [d["stag"] for d in data]
    pids = [d["pid"] / PID_ROD_SCALE for d in data]
    energies = [d["energy"] / 3.0 for d in data]
    lo = min(min(stags), min(pids), min(energies), 0.0)
    hi = max(max(stags), max(pids), max(energies), 1.0)
    series = [(stags, C_STAG, "stag"), (pids, C_PID, "pid"), (energies, C_ENERGY, "nrg")]
    for vals, col, lbl in series:
        _draw_curve_series(hdc, vals, px, py, pw, ph, lo, hi, col, lbl)


def _draw_lorenz_curve(hdc: int, x: int, y: int, wd: int, h: int) -> None:
    px, py, pw, ph = _plot_area(hdc, x, y, wd, h, "LORENZ")
    _grid(hdc, px, py, pw, ph, PLOT_GRID_COLS_LORENZ, PLOT_GRID_ROWS_LORENZ)
    pts_data = list(lorenz_hist)
    if len(pts_data) < 2:
        lx = float(snapshot.get("lorenz_x", 0))
        ly = float(snapshot.get("lorenz_y", 0))
        _text(hdc, px + PAD_INSET, py + ph // 2, f"x={lx:.2f} y={ly:.2f}", C_DIM, bg=C_PLOT_INNER)
        return
    xs = [p[0] for p in pts_data]
    ys = [p[1] for p in pts_data]
    xlo, xhi = min(xs), max(xs)
    ylo, yhi = min(ys), max(ys)
    xspan = xhi - xlo or 1.0
    yspan = yhi - ylo or 1.0
    xlo -= xspan * PLOT_LORENZ_RANGE_PAD
    xhi += xspan * PLOT_LORENZ_RANGE_PAD
    ylo -= yspan * PLOT_LORENZ_RANGE_PAD
    yhi += yspan * PLOT_LORENZ_RANGE_PAD
    raw: list[tuple[int, int]] = []
    for xv, yv in pts_data:
        sx = px + int((xv - xlo) / (xhi - xlo) * pw)
        sy = py + ph - int((yv - ylo) / (yhi - ylo) * ph)
        raw.append((sx, sy))
    curve = _smooth_curve(raw)
    _polyline_raw(hdc, curve, C_ACCENT, PLOT_LINE_THICK + 1)
    tip = curve[-1]
    lx, ly = pts_data[-1]
    _circle(hdc, tip[0], tip[1], AGENT_DOT_R + 1, C_WING, 1, C_WING)
    _text_solid(
        hdc, min(tip[0] + 6, px + pw - FONT_SIZE * 6), max(py + 2, tip[1] - LINE_H // 2),
        f"x={lx:.1f} y={ly:.1f}", C_WING, bg=C_PLOT_INNER, max_w=px + pw,
    )


def _draw_column_plots(hdc: int, x: int, y: int, wd: int, h: int) -> None:
    trace_h = int(h * 0.58)
    _draw_trace_curves(hdc, x, y, wd, trace_h)
    _draw_lorenz_curve(hdc, x, y + trace_h, wd, h - trace_h)


def _draw_column_edge(hdc: int) -> None:
    _line_raw(hdc, VW - 1, 0, VW - 1, VH, C_EDGE, 2)
    _line_raw(hdc, 0, 0, VW - 1, 0, C_EDGE, 1)
    _line_raw(hdc, 0, VH - 1, VW - 1, VH - 1, C_EDGE, 1)


def _draw_column_hud(hdc: int) -> None:
    lay = _layout_column()
    x, wd, pad = lay["x"], lay["w"], lay["pad"]
    _draw_column_edge(hdc)
    _draw_header_column(hdc, x, lay["header_y"], wd, lay["header_h"])
    _col_divider(hdc, x, lay["header_y"] + lay["header_h"], wd)
    _draw_agents_column(hdc, x, lay["agents_y"], wd, lay["agents_h"])
    _col_divider(hdc, x, lay["agents_y"] + lay["agents_h"], wd)
    _draw_plan_column(hdc, x, lay["plan_y"], wd, lay["plan_h"])
    _col_divider(hdc, x, lay["plan_y"] + lay["plan_h"], wd)
    _draw_column_plots(hdc, x, lay["plots_y"], wd, lay["plots_h"])


def _layout() -> dict[str, int]:
    body_y = VY + MARGIN + HEADER_H + GAP_SECTION + METRICS_H + GAP_SECTION
    total_w = VW - 2 * MARGIN
    right_w = min(RIGHT_PANEL_W_MAX, max(RIGHT_PANEL_W_MIN, int(total_w * RIGHT_PANEL_W_RATIO)))
    center_w = total_w - LEFT_PANEL_W - right_w - 2 * GAP_COLUMN
    return {
        "body_y": body_y,
        "body_h": VY + VH - body_y - MARGIN,
        "left_w": LEFT_PANEL_W,
        "center_w": center_w,
        "right_w": right_w,
        "left_x": VX + MARGIN,
        "center_x": VX + MARGIN + LEFT_PANEL_W + GAP_COLUMN,
        "right_x": VX + MARGIN + LEFT_PANEL_W + GAP_COLUMN + center_w + GAP_COLUMN,
    }


def _ellipse_raw(hdc: int, cx: int, cy: int, r: int, color: int, thick: int, fill: int | None) -> None:
    pen = g32.CreatePen(PS_SOLID, thick, color)
    old_pen = g32.SelectObject(hdc, pen)
    if fill is not None:
        brush = g32.CreateSolidBrush(fill)
        old_brush = g32.SelectObject(hdc, brush)
    else:
        old_brush = g32.SelectObject(hdc, g32.GetStockObject(NULL_BRUSH))
    g32.Ellipse(hdc, cx - r, cy - r, cx + r, cy + r)
    g32.SelectObject(hdc, old_pen)
    g32.SelectObject(hdc, old_brush)
    g32.DeleteObject(pen)
    if fill is not None:
        g32.DeleteObject(brush)


def _circle(hdc: int, cx: int, cy: int, r: int, color: int, thick: int = EDGE_THICK, fill: int | None = None) -> None:
    _ellipse_raw(hdc, cx, cy, r, C_OUTLINE, thick + OUTLINE_PAD, None)
    _ellipse_raw(hdc, cx, cy, r, color, thick, fill)


def _polyline_raw(hdc: int, pts: list[tuple[int, int]], color: int, thick: int) -> None:
    pen = g32.CreatePen(PS_SOLID, thick, color)
    old = g32.SelectObject(hdc, pen)
    arr = (w.POINT * len(pts))(*[w.POINT(p[0], p[1]) for p in pts])
    g32.Polyline(hdc, arr, len(pts))
    g32.SelectObject(hdc, old)
    g32.DeleteObject(pen)


def _polyline(hdc: int, pts: list[tuple[int, int]], color: int, thick: int = EDGE_THICK) -> None:
    if len(pts) < 2:
        return
    _polyline_raw(hdc, pts, C_OUTLINE, thick + OUTLINE_PAD)
    _polyline_raw(hdc, pts, color, thick)


def _polygon(hdc: int, pts: list[tuple[int, int]], color: int, thick: int = EDGE_THICK, fill: int | None = None) -> None:
    if len(pts) < 3:
        return
    _polyline_raw(hdc, pts + [pts[0]], C_OUTLINE, thick + OUTLINE_PAD)
    pen = g32.CreatePen(PS_SOLID, thick, color)
    old_pen = g32.SelectObject(hdc, pen)
    if fill is not None:
        brush = g32.CreateSolidBrush(fill)
        old_brush = g32.SelectObject(hdc, brush)
    else:
        old_brush = g32.SelectObject(hdc, g32.GetStockObject(NULL_BRUSH))
    arr = (w.POINT * len(pts))(*[w.POINT(p[0], p[1]) for p in pts])
    g32.Polygon(hdc, arr, len(pts))
    g32.SelectObject(hdc, old_pen)
    g32.SelectObject(hdc, old_brush)
    g32.DeleteObject(pen)
    if fill is not None:
        g32.DeleteObject(brush)


def _grid(hdc: int, x: int, y: int, wd: int, h: int, cols: int = 6, rows: int = 4) -> None:
    draw = _line_raw if LAYOUT_MODE == "column" else _line
    thick = 1 if LAYOUT_MODE == "column" else EDGE_THICK
    for i in range(cols + 1):
        gx = x + i * wd // cols
        draw(hdc, gx, y, gx, y + h, C_GRID, thick)
    for i in range(rows + 1):
        gy = y + i * h // rows
        draw(hdc, x, gy, x + wd, gy, C_GRID, thick)


def _progress(hdc: int, x: int, y: int, wd: int, h: int, frac: float, color: int) -> None:
    frac = max(0.0, min(1.0, frac))
    _roundbox(hdc, x, y, wd, h, h // 2, None)
    inner_w = max(0, int((wd - 2 * PAD_INSET) * frac))
    if inner_w > PAD_INSET:
        _roundbox(hdc, x + PAD_INSET, y + PAD_INSET, inner_w, h - 2 * PAD_INSET,
                  max(RADIUS_LEGEND, (h - 2 * PAD_INSET) // 2), color, color, PROGRESS_FILL_THICK)


def _parse_events() -> None:
    global math_active, loop_active, side_active
    math_active = "—"
    loop_active = "—"
    side_active = "—"
    path = log.active_events_path()
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    events: list[dict[str, Any]] = []
    for line in lines[-EVENTS_ACTIVE_SCAN:]:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    for e in reversed(events):
        p = str(e.get("phase", ""))
        d = e.get("d", {})
        if loop_active == "—":
            if p in LOOP_PHASE_AGENT:
                loop_active = LOOP_PHASE_AGENT[p]
            elif p == "schedule":
                reason = str(d.get("reason", ""))
                if reason in SCHEDULE_LOOP_AGENT:
                    loop_active = SCHEDULE_LOOP_AGENT[reason]
            elif p in LOOP_PHASES:
                loop_active = "actor" if p == "action" else p
        if side_active == "—":
            if p in ("reflect", "reflector.error", "mutation"):
                side_active = "reflector"
            elif p == "observe":
                side_active = "observer"
            elif p == "schedule" and str(d.get("reason", "")) in REFLECT_SCHEDULE_REASONS:
                side_active = "reflector"
        if math_active == "—" and p in MATH_PHASES:
            math_active = p
        if math_active != "—" and loop_active != "—":
            break


def _update_history(data: dict[str, Any]) -> None:
    trace: list[dict[str, Any]] = data.get("math_trace", [])
    if not math_hist and trace:
        for pt in trace:
            math_hist.append({
                "stag": float(pt.get("stag", 0)),
                "pid": float(pt.get("pid", 0)),
                "energy": float(pt.get("energy", 1)),
            })
    latest = trace[-1] if trace else {}
    stag = float(latest.get("stag", data.get("stagnation", 0)))
    pid = float(latest.get("pid", data.get("pid_output", 0)))
    energy = float(latest.get("energy", data.get("energy", 1)))
    cur = {"stag": stag, "pid": pid, "energy": energy}
    if not math_hist or math_hist[-1] != cur:
        math_hist.append(cur)
    lx = float(data.get("lorenz_x", latest.get("x", 0)))
    ly = float(data.get("lorenz_y", 0))
    if not lorenz_hist or lorenz_hist[-1] != (lx, ly):
        lorenz_hist.append((lx, ly))


def read_snapshot() -> bool:
    global snapshot, last_mtime
    path = str(SNAPSHOT_PATH)
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return False
    if mt == last_mtime:
        return False
    last_mtime = mt
    try:
        with open(path, "r", encoding="utf-8") as f:
            snapshot = json.load(f)
    except (json.JSONDecodeError, OSError):
        return False
    _update_history(snapshot)
    _parse_events()
    return True


def _status() -> tuple[str, int]:
    if log.paused():
        return "PAUSED", C_PAUSE
    if log.reactor_running():
        return "RUN", C_RUN
    if snapshot:
        return "LIVE", C_ACTIVE
    return "READY", C_READY


def _metric_values() -> tuple[float, float, float]:
    trace = list(math_hist)
    latest = trace[-1] if trace else {}
    stag = float(latest.get("stag", snapshot.get("stagnation", 0)))
    pid = float(latest.get("pid", snapshot.get("pid_output", 0)))
    energy = float(latest.get("energy", snapshot.get("energy", 1)))
    return stag, pid, energy


def _draw_header(hdc: int, x: int | None = None, y: int | None = None, wd: int | None = None) -> None:
    if x is None:
        x, y, wd = VX + MARGIN, VY + MARGIN, VW - 2 * MARGIN
    else:
        y = y or VY + MARGIN
        wd = wd or VW - 2 * MARGIN
    ty = y + PAD_PANEL
    _roundbox(hdc, x, y, wd, HEADER_H, RADIUS_HEADER, C_PANEL)
    lx = x + HEADER_LOGO_X
    _polygon(
        hdc,
        [(lx, ty), (lx + LOGO_SIZE, ty), (lx + LOGO_SIZE // 2, ty + LOGO_SIZE)],
        C_ACCENT, LOGO_POLYGON_THICK, None,
    )
    _text(hdc, x + HEADER_TEXT_X, ty, "ENDGAME-AI")
    _text(hdc, x + HEADER_TEXT_X, ty + LINE_H, "reactor monitor", C_DIM)

    status, sc = _status()
    bx = x + wd - HEADER_BADGE_W - PAD_PANEL
    _roundbox(hdc, bx, ty, HEADER_BADGE_W, HEADER_BADGE_H, RADIUS_BADGE, C_PANEL)
    _text(hdc, bx + PAD_INSET, ty + (LINE_H - FONT_SIZE) // 2, status, sc)

    work = int(snapshot.get("work_events", 0))
    budget = int(snapshot.get("budget", 20))
    events_n = int(snapshot.get("events", 0))
    failures = int(snapshot.get("consecutive_failures", 0))
    power = float(snapshot.get("power", 0))
    stats = f"work {work}/{budget}   events {events_n}   fail {failures}   power {power:.4f}"
    if snapshot.get("wing_crossed"):
        stats += "   WING"
    sy = ty + LINE_H * 2
    _text(hdc, x + PAD_PANEL, sy, stats, C_DIM, max_w=x + wd - HEADER_CLOCK_W - PAD_PANEL)
    _text(hdc, x + wd - HEADER_CLOCK_W, sy, time.strftime("%H:%M:%S"), C_DIM)
    _text(hdc, x + PAD_PANEL, y + HEADER_H - LINE_H - PAD_INSET,
          str(snapshot.get("goal", "") or "—"), max_w=x + wd - PAD_PANEL)


def _draw_metric_card(hdc: int, x: int, y: int, wd: int, h: int,
                      label: str, value: str, frac: float, color: int) -> None:
    ty = y + PAD_PANEL
    _roundbox(hdc, x, y, wd, h, RADIUS_CARD, C_PANEL)
    _text(hdc, x + PAD_PANEL, ty, label.upper(), C_DIM)
    _text(hdc, x + PAD_PANEL, ty + LINE_H, value, color)
    _progress(hdc, x + PAD_PANEL, y + h - METRIC_PROGRESS_H - PAD_PANEL, wd - METRIC_BAR_PAD,
              METRIC_PROGRESS_H, frac, color)


def _metric_cards() -> list[tuple[str, str, float, int]]:
    stag, pid, energy = _metric_values()
    return [
        ("Stagnation", f"{stag:.3f}", stag, C_STAG),
        ("PID Output", f"{pid:.3f}", min(pid / PID_ROD_SCALE, 1.0), C_PID),
        ("Energy", f"{energy:.3f}", min(energy / 3.0, 1.0), C_ENERGY),
    ]


def _draw_metrics(hdc: int) -> None:
    y = VY + MARGIN + HEADER_H + GAP_SECTION
    wd = VW - 2 * MARGIN
    card_w = (wd - 2 * GAP_PANEL) // 3
    for i, (label, val, frac, col) in enumerate(_metric_cards()):
        cx = VX + MARGIN + i * (card_w + GAP_PANEL)
        _draw_metric_card(hdc, cx, y, card_w, METRICS_H, label, val, frac, col)


def _draw_metrics_stacked(hdc: int, x: int, y: int, wd: int, card_h: int) -> None:
    for i, (label, val, frac, col) in enumerate(_metric_cards()):
        cy = y + i * (card_h + GAP_PANEL)
        _draw_metric_card(hdc, x, cy, wd, card_h, label, val, frac, col)


def _draw_agent_row(hdc: int, x: int, y: int, name: str, active: str, current: str) -> None:
    on = name == current or (name == "fission" and current == "fission_sustain")
    col = C_ACTIVE if on else C_DIM
    fill = C_ACTIVE if on else None
    mid = y + LINE_H // 2
    _circle(hdc, x + AGENT_DOT_X, mid, AGENT_DOT_R, col, EDGE_THICK, fill)
    _text(hdc, x + AGENT_NAME_X, y + (LINE_H - FONT_SIZE) // 2, name, col if on else C_TEXT)


def _draw_agent_chain(hdc: int, x: int, y: int, title: str,
                      chain: tuple[str, ...], active: str) -> int:
    _text(hdc, x, y, title, C_ACCENT)
    cy = y + LINE_H
    for name in chain:
        _draw_agent_row(hdc, x, cy, name, active, active)
        cy += LINE_H
    return cy


def _draw_agents(hdc: int, x: int, y: int, wd: int, h: int) -> None:
    ty = y + PAD_PANEL
    _roundbox(hdc, x, y, wd, h, RADIUS_PANEL, C_PANEL)
    _text(hdc, x + PAD_PANEL, ty, "AGENT STATE")
    cy = ty + LINE_H + PAD_INSET
    cy = _draw_agent_chain(hdc, x + PAD_PANEL, cy, "MATH", MATH_CHAIN, math_active)
    cy += AGENT_CHAIN_GAP
    cy = _draw_agent_chain(hdc, x + PAD_PANEL, cy, "LOOP", AGENT_CHAIN, loop_active)
    cy += AGENT_CHAIN_GAP
    _draw_agent_chain(hdc, x + PAD_PANEL, cy, "SIDE", SIDE_AGENTS, side_active)

    done_when = str(snapshot.get("done_when", ""))
    if done_when:
        dy = y + h - DONE_WHEN_BOX_H
        _line(hdc, x + PAD_PLOT, dy, x + wd - PAD_PLOT, dy, C_EDGE)
        _text(hdc, x + PAD_PANEL, dy + PAD_INSET, "DONE WHEN", C_DIM)
        _text(hdc, x + PAD_PANEL, dy + LINE_H, done_when, max_w=x + wd - PAD_PANEL)


def _draw_plan(hdc: int, x: int, y: int, wd: int, h: int) -> None:
    _roundbox(hdc, x, y, wd, h, RADIUS_PANEL, C_PANEL)
    plan: list[dict[str, Any]] = snapshot.get("plan", [])
    done_n = sum(1 for p in plan if p.get("status") == "done")
    title = f"PLAN  [{done_n}/{len(plan)}]" if plan else "PLAN"
    ty = y + PAD_PANEL
    _text(hdc, x + PAD_PANEL, ty, title)

    if not plan:
        completed = snapshot.get("completed", [])
        if completed:
            _text(hdc, x + PAD_PANEL, ty + LINE_H + PAD_INSET, "COMPLETED", C_DONE)
            _text(hdc, x + PAD_PANEL, ty + 2 * LINE_H, str(completed[-1]), max_w=x + wd - PAD_PANEL)
        else:
            _text(hdc, x + PAD_PANEL, ty + LINE_H + PAD_INSET, "no plan", C_DIM)
        return

    cy = ty + LINE_H + PAD_INSET
    max_lines = (h - cy - PAD_PANEL) // LINE_H
    shown = 0
    wrap = max(PLAN_MIN_WRAP, (wd - PLAN_TEXT_X - PAD_PANEL) // max(1, FONT_SIZE // 2))
    for step in plan:
        if shown >= max_lines:
            _text(hdc, x + PLAN_MARK_X, cy, "…", C_DIM)
            break
        st = step.get("status", "pending")
        txt = str(step.get("text", ""))
        if st == "done":
            mark, mc = "\u2713", C_DONE
        elif st == "active":
            mark, mc = "\u25b6", C_ACTIVE
        else:
            mark, mc = "\u00b7", C_DIM
        _text(hdc, x + PLAN_MARK_X, cy, mark, mc)
        words = txt.split()
        line = ""
        for word in words:
            trial = f"{line} {word}".strip()
            if len(trial) > wrap and line:
                _text(hdc, x + PLAN_TEXT_X, cy, line, C_TEXT if st != "pending" else C_DIM,
                      max_w=x + wd - PAD_PANEL)
                cy += LINE_H
                shown += 1
                line = word
                if shown >= max_lines:
                    break
            else:
                line = trial
        if shown < max_lines and line:
            col = C_TEXT if st == "active" else (C_DONE if st == "done" else C_DIM)
            _text(hdc, x + PLAN_TEXT_X, cy, line, col, max_w=x + wd - PAD_PANEL)
            cy += LINE_H
            shown += 1


def _series_points(values: list[float], px: int, py: int, pw: int, ph: int,
                   lo: float | None = None, hi: float | None = None) -> list[tuple[int, int]]:
    if not values:
        return []
    if lo is None:
        lo = min(values)
    if hi is None:
        hi = max(values)
    span = hi - lo
    if span < 1e-9:
        lo -= 0.5
        hi += 0.5
        span = 1.0
    pts: list[tuple[int, int]] = []
    n = len(values)
    for i, v in enumerate(values):
        tx = px + int(i * pw / max(n - 1, 1))
        ty = py + ph - int((v - lo) / span * ph)
        pts.append((tx, ty))
    return pts


def _draw_plot_frame(hdc: int, x: int, y: int, wd: int, h: int, title: str) -> tuple[int, int, int, int]:
    _roundbox(hdc, x, y, wd, h, RADIUS_PLOT, C_PANEL)
    _text(hdc, x + PAD_PLOT, y + PAD_PANEL, title)
    px, py = x + PAD_PLOT, y + PLOT_BODY_Y
    pw, ph = wd - PLOT_AREA_PAD, h - PLOT_FRAME_EXTRA_H
    _roundbox(hdc, px, py, pw, ph, RADIUS_PLOT_INNER, C_PLOT_INNER)
    return px, py, pw, ph


def _draw_math_trace(hdc: int, x: int, y: int, wd: int, h: int) -> None:
    px, py, pw, ph = _draw_plot_frame(hdc, x, y, wd, h, "MATH TRACE")
    _grid(hdc, px, py, pw, ph, PLOT_GRID_COLS_TRACE, PLOT_GRID_ROWS_TRACE)
    data = list(math_hist)
    if len(data) < 2:
        _text(hdc, px + PAD_PLOT_INNER, py + ph // 2 - 6, "collecting…", C_DIM)
        return
    stags = [d["stag"] for d in data]
    pids = [d["pid"] / PID_ROD_SCALE for d in data]
    energies = [d["energy"] / 3.0 for d in data]
    lo = min(min(stags), min(pids), min(energies), 0.0)
    hi = max(max(stags), max(pids), max(energies), 1.0)
    series = [
        (stags, C_STAG, "stag"),
        (pids, C_PID, "pid"),
        (energies, C_ENERGY, "nrg"),
    ]
    for vals, col, _ in series:
        pts = _series_points(vals, px, py, pw, ph, lo, hi)
        _polyline(hdc, pts, col, PLOT_LINE_THICK)
    leg_x = px + PAD_PLOT_INNER
    for vals, col, lbl in series:
        _roundbox(hdc, leg_x, py + 6, LEGEND_SIZE, LEGEND_SIZE, RADIUS_LEGEND,
                  col, col, LEGEND_FILL_THICK)
        _text(hdc, leg_x + LEGEND_LABEL_OFF, py + 4, lbl, C_DIM)
        leg_x += LEGEND_GAP


def _draw_lorenz(hdc: int, x: int, y: int, wd: int, h: int) -> None:
    px, py, pw, ph = _draw_plot_frame(hdc, x, y, wd, h, "LORENZ ATTRACTOR")
    _grid(hdc, px, py, pw, ph, PLOT_GRID_COLS_LORENZ, PLOT_GRID_ROWS_LORENZ)
    pts_data = list(lorenz_hist)
    if len(pts_data) < 2:
        lx = float(snapshot.get("lorenz_x", 0))
        ly = float(snapshot.get("lorenz_y", 0))
        _text(hdc, px + PAD_PLOT_INNER, py + ph // 2 - 6, f"x={lx:.2f}  y={ly:.2f}", C_DIM)
        if pts_data:
            _circle(hdc, px + pw // 2, py + ph // 2, AGENT_DOT_R - 1, C_ACCENT, EDGE_THICK, C_ACCENT)
        return
    xs = [p[0] for p in pts_data]
    ys = [p[1] for p in pts_data]
    xlo, xhi = min(xs), max(xs)
    ylo, yhi = min(ys), max(ys)
    xspan = xhi - xlo or 1.0
    yspan = yhi - ylo or 1.0
    xlo -= xspan * PLOT_LORENZ_RANGE_PAD
    xhi += xspan * PLOT_LORENZ_RANGE_PAD
    ylo -= yspan * PLOT_LORENZ_RANGE_PAD
    yhi += yspan * PLOT_LORENZ_RANGE_PAD
    screen_pts: list[tuple[int, int]] = []
    for xv, yv in pts_data:
        sx = px + int((xv - xlo) / (xhi - xlo) * pw)
        sy = py + ph - int((yv - ylo) / (yhi - ylo) * ph)
        screen_pts.append((sx, sy))
    _polyline(hdc, screen_pts, C_ACCENT, PLOT_LINE_THICK)
    lx, ly = pts_data[-1]
    _circle(hdc, screen_pts[-1][0], screen_pts[-1][1], AGENT_DOT_R, C_WING, EDGE_THICK, C_WING)
    _text(hdc, px + PAD_PLOT_INNER, py + ph - LINE_H, f"x={lx:.1f}  y={ly:.1f}", C_DIM)


def _draw_plots(hdc: int, x: int, y: int, wd: int, h: int) -> None:
    plot_h = (h - GAP_PANEL) // 2
    _draw_math_trace(hdc, x, y, wd, plot_h)
    _draw_lorenz(hdc, x, y + plot_h + GAP_PANEL, wd, h - plot_h - GAP_PANEL)


def _draw_empty(hdc: int) -> None:
    if LAYOUT_MODE == "column":
        cx, cy = VX + MARGIN, VY + MARGIN
        box_w, box_h = VW - 2 * MARGIN, VH - 2 * MARGIN
        _roundbox(hdc, cx, cy, box_w, box_h, RADIUS_PANEL, C_PANEL)
        _text(hdc, cx + EMPTY_PAD, cy + PAD_PANEL, "ENDGAME-AI HUD")
        _text(hdc, cx + EMPTY_PAD, cy + PAD_PANEL + LINE_H, "Waiting for snapshot.json…", C_DIM)
        _text(hdc, cx + EMPTY_PAD, cy + PAD_PANEL + 2 * LINE_H, str(SNAPSHOT_PATH), C_DIM,
              max_w=cx + box_w - EMPTY_PAD)
        return
    cx = VX + VW // 2 - EMPTY_BOX_W // 2
    cy = VY + VH // 2 - EMPTY_BOX_H // 2
    _roundbox(hdc, cx, cy, EMPTY_BOX_W, EMPTY_BOX_H, RADIUS_EMPTY, C_PANEL)
    _text(hdc, cx + EMPTY_PAD, cy + PAD_PANEL, "ENDGAME-AI HUD")
    _text(hdc, cx + EMPTY_PAD, cy + PAD_PANEL + LINE_H, "Waiting for snapshot.json…", C_DIM)
    _text(hdc, cx + EMPTY_PAD, cy + PAD_PANEL + 2 * LINE_H, str(SNAPSHOT_PATH), C_DIM,
          max_w=cx + EMPTY_BOX_W - EMPTY_PAD)


def _wndproc(hwnd: int, msg: int, wp: int, lp: int) -> int:
    if msg == WM_PAINT:
        ps = PAINTSTRUCT()
        hdc = u32.BeginPaint(hwnd, ctypes.byref(ps))
        try:
            _present(hwnd, 0)
        except Exception as exc:
            sys.stderr.write(f"hud paint error: {exc}\n")
        u32.EndPaint(hwnd, ctypes.byref(ps))
        return 0
    if msg == WM_TIMER:
        design_changed = read_design()
        snapshot_changed = read_snapshot()
        if not snapshot_changed:
            _parse_events()
        if _needs_redraw(design_changed, snapshot_changed):
            try:
                _present(hwnd, 0)
            except Exception as exc:
                sys.stderr.write(f"hud timer error: {exc}\n")
        return 0
    if msg == WM_DESTROY:
        u32.PostQuitMessage(0)
        return 0
    return u32.DefWindowProcW(hwnd, msg, wp, lp)


_wndproc_cb = WNDPROC(_wndproc)


def _shutdown() -> None:
    global _hwnd
    if _hwnd:
        u32.KillTimer(_hwnd, 1)
        u32.DestroyWindow(_hwnd)
        _hwnd = None
    _release_layer()
    _invalidate_font()


def _on_sigint(*_args: object) -> None:
    u32.PostQuitMessage(0)


def main() -> None:
    global _hwnd
    _init_screen()
    signal.signal(signal.SIGINT, _on_sigint)
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else REFRESH_MS_DEFAULT
    read_design()
    read_snapshot()
    hinst = k32.GetModuleHandleW(None)
    wc = WNDCLASS()
    wc.style = CS_HREDRAW | CS_VREDRAW
    wc.lpfnWndProc = _wndproc_cb
    wc.hInstance = hinst
    wc.hCursor = u32.LoadCursorW(None, IDC_ARROW)
    wc.hbrBackground = g32.GetStockObject(NULL_BRUSH)
    wc.lpszClassName = "EndgameHUD"
    u32.RegisterClassW(ctypes.byref(wc))
    hwnd = u32.CreateWindowExW(
        WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW,
        "EndgameHUD", "EndgameHUD", WS_POPUP | WS_VISIBLE,
        0, 0, SW, SH, None, None, hinst, None,
    )
    u32.SetTimer(hwnd, 1, interval, None)
    u32.SetWindowPos(
        hwnd, HWND_TOPMOST, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
    )
    _hwnd = hwnd
    try:
        _present(hwnd, 0)
    except Exception:
        pass
    msg = w.MSG()
    try:
        while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            u32.TranslateMessage(ctypes.byref(msg))
            u32.DispatchMessageW(ctypes.byref(msg))
    except KeyboardInterrupt:
        pass
    finally:
        _shutdown()


if __name__ == "__main__":
    main()