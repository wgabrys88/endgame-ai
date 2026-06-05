from __future__ import annotations
import os
import sys
import threading
import time
from collections import deque
from typing import Any

from sixel import render_lorenz, render_stagnation

ESC = "\033"
RST = f"{ESC}[0m"
BLD = f"{ESC}[1m"
DIM = f"{ESC}[2m"
ITALIC = f"{ESC}[3m"
UNDERLINE = f"{ESC}[4m"
CURLY_UL = f"{ESC}[4:3m"
NO_UL = f"{ESC}[24m"


def _ul_color(r: int, g: int, b: int) -> str:
    return f"{ESC}[58;2;{r};{g};{b}m"


def _fg(r: int, g: int, b: int) -> str:
    return f"{ESC}[38;2;{r};{g};{b}m"

_event_log: deque[str] = deque(maxlen=200)
_commands: deque[str] = deque(maxlen=50)
_mouse_thread: threading.Thread | None = None
_mouse_active: bool = False
_checklist_y_start: int = 0
_checklist_y_end: int = 0
_lorenz_history: list[tuple[float, float, float]] = []

MAX_LORENZ_HISTORY: int = 300


def _size() -> tuple[int, int]:
    try:
        return os.get_terminal_size()
    except OSError:
        return 120, 40


def _gradient(value: float) -> tuple[int, int, int]:
    if value < 0.3:
        t = value / 0.3
        return (int(50 + 170 * t), int(200 - 80 * t), int(80 - 50 * t))
    elif value < 0.7:
        t = (value - 0.3) / 0.4
        return (int(220 + 35 * t), int(120 - 70 * t), int(30 - 10 * t))
    else:
        t = (value - 0.7) / 0.3
        return (int(255 - 35 * t), int(50 - 30 * t), int(20 + 30 * t))


def _bar_gradient(value: float, w: int) -> str:
    filled = int(min(1.0, max(0.0, value)) * w)
    parts: list[str] = []
    for i in range(w):
        t = i / max(w - 1, 1)
        r, g, b = _gradient(t)
        if i < filled:
            parts.append(f"{_fg(r, g, b)}█")
        else:
            parts.append(f"{_fg(40, 40, 50)}░")
    parts.append(RST)
    return "".join(parts)


def _osc_progress(value: float, state: int = 1) -> str:
    percent = int(min(1.0, max(0.0, value)) * 100)
    return f"{ESC}]9;4;{state};{percent}\x07"


def _osc_progress_clear() -> str:
    return f"{ESC}]9;4;0;0\x07"


def _hyperlink(url: str, text: str) -> str:
    return f"{ESC}]8;;{url}\x07{text}{ESC}]8;;\x07"


def _cut(s: str, maxlen: int) -> str:
    if maxlen <= 3:
        return s[:maxlen]
    return s[:maxlen - 1] + "…" if len(s) > maxlen else s


def _visible_len(s: str) -> int:
    length = 0
    i = 0
    while i < len(s):
        if s[i] == "\033":
            if i + 1 < len(s) and s[i + 1] == "[":
                j = i + 2
                while j < len(s) and s[j] != "m":
                    j += 1
                i = j + 1
            elif i + 1 < len(s) and s[i + 1] == "]":
                j = i + 2
                while j < len(s) and s[j] != "\x07":
                    j += 1
                i = j + 1
            elif i + 1 < len(s) and s[i + 1] == "P":
                j = i + 2
                while j < len(s) - 1:
                    if s[j] == "\033" and s[j + 1] == "\\":
                        j += 2
                        break
                    j += 1
                i = j
            else:
                i += 1
        else:
            length += 1
            i += 1
    return length


def _pad(s: str, w: int) -> str:
    visible = _visible_len(s)
    if visible >= w:
        return s
    return s + " " * (w - visible)


def _role_color(role: str) -> tuple[int, int, int]:
    match role:
        case "planner":
            return (100, 180, 255)
        case "actor":
            return (255, 180, 50)
        case "reflector":
            return (255, 80, 180)
        case "verifier":
            return (80, 255, 150)
        case "distillation":
            return (180, 100, 255)
        case _:
            return (150, 150, 150)


def _mouse_reader() -> None:
    global _mouse_active
    if sys.platform != "win32":
        return
    import msvcrt
    buf = ""
    while _mouse_active:
        if msvcrt.kbhit():
            ch = msvcrt.getwch()
            buf += ch
            if buf.startswith("\x1b[<") and (buf.endswith("M") or buf.endswith("m")):
                _parse_mouse(buf)
                buf = ""
            elif len(buf) > 30:
                buf = ""
        else:
            time.sleep(0.05)


def _parse_mouse(seq: str) -> None:
    try:
        body = seq[3:-1]
        parts = body.split(";")
        button = int(parts[0])
        _col = int(parts[1])
        row = int(parts[2])
        is_press = seq.endswith("M")
        if button == 0 and is_press:
            if _checklist_y_start <= row <= _checklist_y_end:
                step = row - _checklist_y_start
                _commands.append(f"force_advance:{step}")
    except (ValueError, IndexError):
        pass


def event(msg: str) -> None:
    from datetime import datetime
    ts = datetime.now().strftime("%H:%M:%S")
    _event_log.append(f"{ts} {msg}")


def poll_commands() -> list[str]:
    result: list[str] = []
    while _commands:
        result.append(_commands.popleft())
    return result


def enter() -> None:
    global _mouse_active, _mouse_thread
    sys.stdout.write(f"{ESC}[?1049h{ESC}[?25l")
    sys.stdout.write(f"{ESC}[?1006h")
    sys.stdout.flush()
    _mouse_active = True
    _mouse_thread = threading.Thread(target=_mouse_reader, daemon=True)
    _mouse_thread.start()


def exit() -> None:
    global _mouse_active
    _mouse_active = False
    sys.stdout.write(f"{ESC}[?1006l")
    sys.stdout.write(_osc_progress_clear())
    sys.stdout.write(f"{ESC}[?25h{ESC}[?1049l")
    sys.stdout.flush()


def render(board: Any, stagnation_history: list[float], last_event: str = "") -> None:
    global _checklist_y_start, _checklist_y_end, _lorenz_history
    cols, rows = _size()
    w = cols - 1
    inner = w - 4
    out: list[str] = []
    current_row = 0

    _lorenz_history.append((board.lorenz_x, board.lorenz_y, board.lorenz_z))
    if len(_lorenz_history) > MAX_LORENZ_HISTORY:
        _lorenz_history = _lorenz_history[-MAX_LORENZ_HISTORY:]

    border_color = _fg(60, 140, 180)

    def hline() -> None:
        nonlocal current_row
        out.append(f"{border_color}├{'─' * (w - 2)}┤{RST}")
        current_row += 1

    def row(content: str) -> None:
        nonlocal current_row
        cut_content = _cut(content, inner)
        out.append(f"{border_color}│{RST} {_pad(cut_content, inner)} {border_color}│{RST}")
        current_row += 1

    title = f" ENDGAME-AI  IT:{board.iteration:03d} "
    out.append(f"{border_color}┌─{BLD}{_fg(200, 220, 255)}{title}{RST}{border_color}{'─' * max(0, w - len(title) - 4)}┐{RST}")
    current_row += 1

    stag_r, stag_g, stag_b = _gradient(board.stagnation_score)
    bar_w = max(6, (inner - 40) // 2)
    stag_bar = _bar_gradient(board.stagnation_score, bar_w)
    pid_bar = _bar_gradient(min(1.0, board.pid_output / 3.0), bar_w)
    row(f"{_fg(stag_r, stag_g, stag_b)}stag:{board.stagnation_score:.2f}{RST} {stag_bar}  {_fg(100, 150, 255)}pid:{board.pid_output:.2f}{RST} {pid_bar}")

    slope_r, slope_g, slope_b = (220, 60, 60) if board.pid_slope > 0.02 else ((60, 220, 100) if board.pid_slope < -0.02 else (100, 100, 100))
    slope_ch = "▲" if board.pid_slope > 0.02 else ("▼" if board.pid_slope < -0.02 else "─")
    row(f"{_fg(slope_r, slope_g, slope_b)}slope:{board.pid_slope:+.3f} {slope_ch}{RST}  {DIM}int:{board.pid_integral:.2f}  screen:{board.screen_stagnation}  fails:{board.consecutive_failures}  energy:{board.attractor_energy:.2f}{RST}")

    hline()

    show_sixel = rows > 35 and cols > 80
    if show_sixel and len(stagnation_history) > 2:
        sixel_w = min(200, (inner - 2) * 2)
        sixel_h = 42
        sixel_str = render_stagnation(stagnation_history, sixel_w, sixel_h)
        out.append(sixel_str)
        current_row += (sixel_h // 6) + 1

    if show_sixel and len(_lorenz_history) > 10:
        lorenz_w = min(200, (inner - 2) * 2)
        lorenz_h = 48
        lorenz_str = render_lorenz(board.lorenz_x, board.lorenz_y, board.lorenz_z, _lorenz_history, lorenz_w, lorenz_h)
        out.append(lorenz_str)
        current_row += (lorenz_h // 6) + 1

    if show_sixel:
        hline()

    _checklist_y_start = current_row + 1
    if board.plan_steps:
        max_steps = min(len(board.plan_steps), max(3, (rows - current_row - 15) // 2))
        for i in range(max_steps):
            step = board.plan_steps[i]
            if i < board.plan_step_index:
                mark = f"{_fg(80, 220, 120)}✓{RST}"
                step_text = f"{DIM}{step}{RST}"
            elif i == board.plan_step_index:
                mark = f"{_fg(255, 220, 50)}►{RST}"
                step_text = f"{BLD}{CURLY_UL}{_ul_color(255, 180, 50)}{step}{NO_UL}{RST}"
            else:
                mark = f"{_fg(80, 80, 100)}○{RST}"
                step_text = f"{_fg(120, 120, 140)}{step}{RST}"
            row(f"{mark} {_cut(step_text, inner - 4)}")
        if len(board.plan_steps) > max_steps:
            row(f"{DIM}  ... +{len(board.plan_steps) - max_steps} more{RST}")
    else:
        row(f"{DIM}(awaiting checklist){RST}")
    _checklist_y_end = current_row

    hline()

    if board.actor_observe:
        obs_text = board.actor_observe[:inner * 2]
        row(f"{_fg(200, 200, 220)}SEES:{RST} {_cut(obs_text, inner - 6)}")

    if board.last_verb:
        if board.last_success:
            ok = f"{_fg(80, 220, 120)}✓{RST}"
        else:
            ok = f"{_fg(220, 60, 60)}✗{RST}"
        row(f"{ok} {board.last_verb}: {_cut(board.last_observation, inner - len(board.last_verb) - 5)}")

    if board.actor_conclusion:
        if board.actor_conclusion == "EXPECTED":
            cc_r, cc_g, cc_b = (80, 220, 120)
        else:
            cc_r, cc_g, cc_b = (220, 60, 60)
        row(f"  {_fg(cc_r, cc_g, cc_b)}{board.actor_conclusion}{RST}")

    hline()

    if board.last_plan_because:
        plan_text = board.last_plan_because[:inner * 2]
        row(f"{_fg(100, 180, 255)}PLAN:{RST} {_cut(plan_text, inner - 6)}")

    hline()

    goal_text = board.goal[:inner * 2]
    row(f"{_fg(180, 100, 255)}{BLD}GOAL:{RST} {_cut(goal_text, inner - 6)}")

    hline()

    used_lines = current_row + 3
    log_space = max(3, rows - used_lines - 1)

    if last_event:
        lr, lg, lb = _role_color(last_event.split(":")[1] if ":" in last_event else "")
        log_label = _hyperlink("file:///log", "LOG")
        row(f"{_fg(lr, lg, lb)}{BLD}{log_label}{RST} {DIM}{last_event}{RST}")
    else:
        row(f"{BLD}{_hyperlink('file:///log', 'LOG')}{RST}")

    recent_events = list(_event_log)[-(log_space - 1):]
    for ev in recent_events:
        display = _cut(ev, inner - 2)
        if "error" in ev.lower() or "FAIL" in ev:
            row(f"{_fg(220, 60, 60)}{display}{RST}")
        elif "success=True" in ev or "goal.complete" in ev:
            row(f"{_fg(80, 220, 120)}{display}{RST}")
        elif "pid.reflect" in ev or "pid.distill" in ev:
            row(f"{_fg(255, 80, 180)}{display}{RST}")
        else:
            row(f"{DIM}{display}{RST}")
    for _ in range(log_space - 1 - len(recent_events)):
        row("")

    status_parts: list[str] = []
    status_parts.append(f"rep:{board.repetition_score:.2f}")
    if last_event:
        status_parts.append(last_event)
    status = "  ".join(status_parts)
    out.append(f"{border_color}└─ {DIM}{_cut(status, w - 5)}{RST}{border_color} {'─' * max(0, w - _visible_len(status) - 6)}┘{RST}")

    progress_state = 1
    if board.stagnation_score > 0.8:
        progress_state = 2
    elif board.stagnation_score > 0.5:
        progress_state = 3
    sys.stdout.write(_osc_progress(board.stagnation_score, progress_state))

    sys.stdout.write(f"{ESC}[H{ESC}[J")
    sys.stdout.write("\n".join(out))
    sys.stdout.flush()
