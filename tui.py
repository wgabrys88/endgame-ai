from __future__ import annotations

import ctypes
import os
import sys
from dataclasses import dataclass
from typing import Any, Protocol, cast

from config import (
    TUI_WRITE_CHUNK_SIZE, ZERO_INT, ONE_INT, TWO_INT,
    TUI_MODE_AUTO, TUI_MODE_VISUAL, TUI_MODE_JSON,
    TUI_ALT_SCREEN_ON, TUI_ALT_SCREEN_OFF, TUI_HIDE_CURSOR, TUI_SHOW_CURSOR,
    TUI_HOME_CLEAR, TUI_PORTRAIT_ASPECT_W, TUI_PORTRAIT_ASPECT_H,
    TUI_MIN_GRAPH_WIDTH, TUI_MIN_GRAPH_HEIGHT, TUI_STATUS_ROWS,
    TUI_LORENZ_TRAIL_MAX, TUI_TEXT_COLS_MIN, TUI_SIXEL_CELL_ASPECT,
    STD_OUTPUT_HANDLE, WT_SESSION_ENV, WT_PROFILE_ENV,
    SIXEL_LORENZ_WIDTH, SIXEL_LORENZ_HEIGHT, SIXEL_STAGNATION_WIDTH, SIXEL_STAGNATION_HEIGHT,
)


class _BinaryStdout(Protocol):
    def write(self, data: bytes) -> int:
        ...

    def flush(self) -> None:
        ...


class _BufferedStdout(Protocol):
    buffer: _BinaryStdout


class _Coord(ctypes.Structure):
    _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]


class _SmallRect(ctypes.Structure):
    _fields_ = [
        ("Left", ctypes.c_short),
        ("Top", ctypes.c_short),
        ("Right", ctypes.c_short),
        ("Bottom", ctypes.c_short),
    ]


class _ConsoleScreenBufferInfo(ctypes.Structure):
    _fields_ = [
        ("dwSize", _Coord),
        ("dwCursorPosition", _Coord),
        ("wAttributes", ctypes.c_uint16),
        ("srWindow", _SmallRect),
        ("dwMaximumWindowSize", _Coord),
    ]


@dataclass(slots=True)
class _Layout:
    cols: int
    rows: int
    portrait: bool
    lorenz_w: int
    lorenz_h: int
    stagnation_w: int
    stagnation_h: int
    text_cols: int


_mode: str = TUI_MODE_AUTO
_resolved_mode: str = TUI_MODE_JSON
_alt_active: bool = False
_lorenz_trail: list[tuple[float, float, float]] = []
_last_frame_key: str = ""


def set_mode(mode: str) -> None:
    global _mode
    if mode in (TUI_MODE_AUTO, TUI_MODE_VISUAL, TUI_MODE_JSON):
        _mode = mode


def resolve_mode() -> str:
    global _resolved_mode
    if _mode == TUI_MODE_JSON:
        _resolved_mode = TUI_MODE_JSON
        return _resolved_mode
    if _mode == TUI_MODE_VISUAL:
        _resolved_mode = TUI_MODE_VISUAL
        return _resolved_mode
    if os.environ.get(WT_SESSION_ENV) or os.environ.get(WT_PROFILE_ENV):
        _resolved_mode = TUI_MODE_VISUAL
        return _resolved_mode
    _resolved_mode = TUI_MODE_JSON
    return _resolved_mode


def _stdout_buffer() -> _BinaryStdout:
    return cast(_BufferedStdout, sys.stdout).buffer


def _write_bytes(data: bytes) -> None:
    stream = _stdout_buffer()
    for start in range(ZERO_INT, len(data), TUI_WRITE_CHUNK_SIZE):
        stream.write(data[start:start + TUI_WRITE_CHUNK_SIZE])
    stream.flush()


def _write_text(text: str) -> None:
    _write_bytes(text.encode("utf-8", errors="surrogatepass"))


def _terminal_size() -> tuple[int, int]:
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        info = _ConsoleScreenBufferInfo()
        if kernel32.GetConsoleScreenBufferInfo(handle, ctypes.byref(info)):
            cols = info.srWindow.Right - info.srWindow.Left + ONE_INT
            rows = info.srWindow.Bottom - info.srWindow.Top + ONE_INT
            return max(cols, TUI_TEXT_COLS_MIN), max(rows, TUI_STATUS_ROWS + TUI_MIN_GRAPH_HEIGHT)
    except (AttributeError, OSError):
        pass
    return 120, 40


def _compute_layout(cols: int, rows: int) -> _Layout:
    portrait = cols < rows
    status_rows = min(TUI_STATUS_ROWS, max(rows // 4, 6))
    graph_rows = max(rows - status_rows - ONE_INT, TUI_MIN_GRAPH_HEIGHT)
    if portrait:
        graph_cols = max(TUI_MIN_GRAPH_WIDTH, min(cols * TUI_SIXEL_CELL_ASPECT - 4, int(graph_rows * TUI_PORTRAIT_ASPECT_W / TUI_PORTRAIT_ASPECT_H * TUI_SIXEL_CELL_ASPECT)))
        lorenz_h = max(TUI_MIN_GRAPH_HEIGHT, graph_rows * 3 // 5)
        stag_h = max(TUI_MIN_GRAPH_HEIGHT // 2, graph_rows - lorenz_h)
        text_cols = cols
    else:
        text_cols = min(max(cols // 3, TUI_TEXT_COLS_MIN), 44)
        graph_cols = max(TUI_MIN_GRAPH_WIDTH, min((cols - text_cols - TWO_INT) * TUI_SIXEL_CELL_ASPECT, SIXEL_LORENZ_WIDTH))
        lorenz_h = max(TUI_MIN_GRAPH_HEIGHT, min(graph_rows * TUI_SIXEL_CELL_ASPECT, SIXEL_LORENZ_HEIGHT))
        stag_h = max(TUI_MIN_GRAPH_HEIGHT // 2, min(lorenz_h * 2 // 3, SIXEL_STAGNATION_HEIGHT))
    lorenz_w = max(TUI_MIN_GRAPH_WIDTH, min(graph_cols, SIXEL_LORENZ_WIDTH * 2))
    stag_w = max(TUI_MIN_GRAPH_WIDTH, min(graph_cols, SIXEL_STAGNATION_WIDTH * 2))
    return _Layout(cols, rows, portrait, lorenz_w, lorenz_h, stag_w, stag_h, text_cols)


def _clip(text: str, limit: int) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: max(limit - 3, ZERO_INT)] + "..."


def _child_line(children: Any) -> str:
    if not children:
        return "children: none"
    parts: list[str] = []
    if isinstance(children, dict):
        children_dict = cast(dict[Any, Any], children)
        for agent_id, handle in children_dict.items():
            if hasattr(handle, "state"):
                state = str(getattr(handle, "state"))
            elif isinstance(handle, dict):
                state = str(cast(dict[str, Any], handle).get("state", "?"))
            else:
                state = "?"
            parts.append(f"{agent_id}:{state}")
    return "children: " + ", ".join(parts) if parts else "children: none"


def _child_summary(children: Any) -> str:
    if not isinstance(children, dict) or not children:
        return "children run=0 done=0 fail=0"
    running = done = failed = ZERO_INT
    children_dict = cast(dict[Any, Any], children)
    for handle in children_dict.values():
        if hasattr(handle, "state"):
            state = str(getattr(handle, "state"))
        elif isinstance(handle, dict):
            state = str(cast(dict[str, Any], handle).get("state", ""))
        else:
            state = ""
        if state == "running":
            running += ONE_INT
        elif state == "done":
            done += ONE_INT
        elif state == "failed":
            failed += ONE_INT
    return f"children run={running} done={done} fail={failed}"


def _status_lines(board: Any, stagnation_history: list[float], last_event: str, layout: _Layout) -> list[str]:
    goal = _clip(str(getattr(board, "original_goal", "") or getattr(board, "goal", "")), layout.text_cols - 6)
    focus = _clip(str(getattr(board, "focused_window", "")), layout.text_cols - 8)
    plan_steps = cast(list[Any], getattr(board, "plan_steps", []))
    plan_index = getattr(board, "plan_step_index", ZERO_INT)
    step = ""
    if plan_steps and plan_index < len(plan_steps):
        step = _clip(str(plan_steps[plan_index]), layout.text_cols - 6)
    total_steps = len(plan_steps)
    progress = f"{min(plan_index + ONE_INT, total_steps)}/{total_steps}" if total_steps else "0/0"
    last_obs = _clip(str(getattr(board, "last_observation", "")), layout.text_cols - 7)
    actor = _clip(str(getattr(board, "actor_observe", "")), layout.text_cols - 7)
    reason = _clip(str(getattr(board, "last_plan_because", "")), layout.text_cols - 7)
    lines = [
        f"endgame-ai | {getattr(board, 'agent_id', 'main')} | iter {getattr(board, 'iteration', ZERO_INT)} | {last_event}",
        f"mode={getattr(board, 'mode', '')} step={progress} screen={getattr(board, 'screen_valid', False)}",
        f"sig stag={getattr(board, 'stagnation_score', 0.0):.3f} pid={getattr(board, 'pid_output', 0.0):.3f} slope={getattr(board, 'pid_slope', 0.0):.3f} rep={getattr(board, 'repetition_score', 0.0):.3f}",
        f"risk fail={getattr(board, 'consecutive_failures', 0)} miss={getattr(board, 'expectation_miss_streak', 0)} screen_stag={getattr(board, 'screen_stagnation', 0)} { _child_summary(getattr(board, 'children', {})) }",
        f"goal: {goal}",
        f"focus: {focus}",
        f"now: {step}" if step else "now: (none)",
        f"action: {getattr(board, 'last_verb', '')} ok={getattr(board, 'last_success', False)}",
        f"result: {last_obs}",
        f"actor: {actor}" if actor else _child_line(getattr(board, "children", {})),
        f"plan: {reason}" if reason else f"energy={getattr(board, 'attractor_energy', 0.0):.3f}",
    ]
    return lines[:TUI_STATUS_ROWS]


def _append_lorenz(board: Any) -> None:
    global _lorenz_trail
    point = (float(getattr(board, "lorenz_x", 0.0)), float(getattr(board, "lorenz_y", 0.0)), float(getattr(board, "lorenz_z", 0.0)))
    _lorenz_trail.append(point)
    if len(_lorenz_trail) > TUI_LORENZ_TRAIL_MAX:
        _lorenz_trail = _lorenz_trail[-TUI_LORENZ_TRAIL_MAX:]


def _render_visual(board: Any, stagnation_history: list[float], last_event: str) -> None:
    global _last_frame_key
    cols, rows = _terminal_size()
    layout = _compute_layout(cols, rows)
    _append_lorenz(board)
    frame_key = f"{last_event}|{getattr(board, 'iteration', ZERO_INT)}|{getattr(board, 'last_verb', '')}|{getattr(board, 'last_success', '')}"
    if frame_key == _last_frame_key and last_event.startswith("COORD:"):
        return
    _last_frame_key = frame_key
    from sixel import render_lorenz, render_stagnation

    lorenz_sixel = render_lorenz(
        float(getattr(board, "lorenz_x", 0.0)),
        float(getattr(board, "lorenz_y", 0.0)),
        float(getattr(board, "lorenz_z", 0.0)),
        _lorenz_trail,
        layout.lorenz_w,
        layout.lorenz_h,
    )
    stagnation_sixel = render_stagnation(stagnation_history, layout.stagnation_w, layout.stagnation_h)
    status = _status_lines(board, stagnation_history, last_event, layout)
    parts: list[str] = [TUI_HOME_CLEAR]
    for line in status:
        parts.append(line + "\n")
    if layout.portrait:
        parts.append("\x1b[1;36mLORENZ\x1b[0m\n")
        parts.append(lorenz_sixel)
        parts.append("\n\x1b[1;33mSTAGNATION\x1b[0m\n")
        parts.append(stagnation_sixel)
        parts.append("\n")
    else:
        parts.append("\x1b[1;36mLORENZ\x1b[0m  \x1b[1;33mSTAGNATION\x1b[0m\n")
        parts.append(lorenz_sixel)
        parts.append(stagnation_sixel)
        parts.append("\n")
    _write_text("".join(parts))


def event(record: dict[str, Any], line: str) -> None:
    if resolve_mode() == TUI_MODE_VISUAL:
        return
    data = (line + "\n").encode("utf-8", errors="surrogatepass")
    _write_bytes(data)


def poll_commands() -> list[str]:
    return []


def enter() -> None:
    global _alt_active, _lorenz_trail, _last_frame_key
    _lorenz_trail = []
    _last_frame_key = ""
    if resolve_mode() != TUI_MODE_VISUAL:
        sys.stdout.flush()
        return
    _write_text(TUI_ALT_SCREEN_ON + TUI_HIDE_CURSOR + TUI_HOME_CLEAR)
    _alt_active = True


def exit() -> None:
    global _alt_active
    if _alt_active:
        _write_text(TUI_SHOW_CURSOR + TUI_ALT_SCREEN_OFF)
        _alt_active = False
    sys.stdout.flush()


def render(board: Any, stagnation_history: list[float], last_event: str = "") -> None:
    if last_event.startswith("COORD:"):
        if resolve_mode() == TUI_MODE_VISUAL:
            _render_visual(board, stagnation_history, last_event)
        return
    if resolve_mode() == TUI_MODE_VISUAL:
        _render_visual(board, stagnation_history, last_event)
    from log import log
    log(
        board.iteration,
        "tui.render",
        "live state projection",
        {
            "last_event": last_event,
            "agent_id": board.agent_id,
            "mode": board.mode,
            "screen_valid": board.screen_valid,
            "focused_window": board.focused_window,
            "stagnation_score": board.stagnation_score,
            "pid_output": board.pid_output,
            "pid_integral": board.pid_integral,
            "pid_slope": board.pid_slope,
            "repetition_score": board.repetition_score,
            "screen_stagnation": board.screen_stagnation,
            "expectation_miss_streak": board.expectation_miss_streak,
            "consecutive_failures": board.consecutive_failures,
            "attractor_energy": board.attractor_energy,
            "plan_steps": board.plan_steps,
            "plan_step_index": board.plan_step_index,
            "plan_progress": f"{min(board.plan_step_index + ONE_INT, len(board.plan_steps))}/{len(board.plan_steps)}" if board.plan_steps else "0/0",
            "last_instruction": board.last_instruction,
            "last_verb": board.last_verb,
            "last_success": board.last_success,
            "last_observation": board.last_observation,
            "actor_observe": board.actor_observe,
            "actor_conclusion": board.actor_conclusion,
            "last_plan_because": board.last_plan_because,
            "goal": board.goal,
            "stagnation_history": stagnation_history,
            "children": board.children,
            "tui_mode": resolve_mode(),
        },
    )


def launch_windows_terminal_preview(goal: str, backend: str, base_dir: str) -> int:
    import subprocess
    import shutil
    wt = shutil.which("wt.exe")
    if not wt:
        return ONE_INT
    cmd = (
        f'cd "{base_dir}"; python main.py "{goal}" --backend {backend} --tui-mode visual'
    )
    proc = subprocess.Popen([wt, "-w", "0", "new-tab", "--title", "endgame-ai", "powershell", "-NoLogo", "-NoProfile", "-Command", cmd])
    return proc.pid
