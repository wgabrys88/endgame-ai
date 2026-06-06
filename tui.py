from __future__ import annotations
import os
import sys
import threading
import time
from collections import deque
from typing import Any

ESC = "\033"
RST = f"{ESC}[0m"
BLD = f"{ESC}[1m"
DIM = f"{ESC}[2m"
CURLY_UL = f"{ESC}[4:3m"
NO_UL = f"{ESC}[24m"

_event_log: deque[str] = deque(maxlen=400)
_commands: deque[str] = deque(maxlen=50)
_mouse_thread: threading.Thread | None = None
_mouse_active: bool = False
_checklist_y_start: int = 0
_checklist_y_end: int = 0


def _fg(r: int, g: int, b: int) -> str:
    return f"{ESC}[38;2;{r};{g};{b}m"


def _ul_color(r: int, g: int, b: int) -> str:
    return f"{ESC}[58;2;{r};{g};{b}m"


def _size() -> tuple[int, int]:
    try:
        return os.get_terminal_size()
    except OSError:
        return 120, 40


def _plain_len(s: str) -> int:
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
            else:
                i += 1
        else:
            length += 1
            i += 1
    return length


def _pad_visible(s: str, w: int) -> str:
    visible = _plain_len(s)
    if visible >= w:
        return s
    return s + " " * (w - visible)


def _wrap_plain(text: str, width: int) -> list[str]:
    if width < 8:
        return [text[: max(1, width)]]
    cleaned = " ".join(text.replace("\r", "").split())
    if not cleaned:
        return [""]
    words = cleaned.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= width:
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _gradient(value: float) -> tuple[int, int, int]:
    if value < 0.3:
        t = value / 0.3
        return (int(50 + 170 * t), int(200 - 80 * t), int(80 - 50 * t))
    if value < 0.7:
        t = (value - 0.3) / 0.4
        return (int(220 + 35 * t), int(120 - 70 * t), int(30 - 10 * t))
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
    sys.stdout.write(f"{ESC}[?1049h{ESC}[?25l{ESC}[?1006h")
    sys.stdout.flush()
    _mouse_active = True
    _mouse_thread = threading.Thread(target=_mouse_reader, daemon=True)
    _mouse_thread.start()


def exit() -> None:
    global _mouse_active
    _mouse_active = False
    sys.stdout.write(_osc_progress_clear())
    sys.stdout.write(f"{ESC}[?1006l{ESC}[?25h{ESC}[?1049l")
    sys.stdout.flush()


def _event_style(ev: str) -> tuple[int, int, int]:
    low = ev.lower()
    if "error" in low or "fail" in low or "parse_fail" in low:
        return (220, 60, 60)
    if "goal.complete" in low or "success=true" in low or "child_done" in low:
        return (80, 220, 120)
    if "pid.reflect" in low or "pid.distill" in low or "reflector" in low:
        return (255, 80, 180)
    if "coordinate" in low or "child.spawn" in low or "decompose" in low:
        return (100, 200, 255)
    if "observe" in low or "planner" in low or "actor" in low:
        return (180, 200, 230)
    return (140, 140, 160)


def render(board: Any, stagnation_history: list[float], last_event: str = "") -> None:
    global _checklist_y_start, _checklist_y_end
    cols, rows = _size()
    w = max(40, cols - 1)
    inner = w - 4
    wrap_w = max(20, inner - 2)
    out: list[str] = []
    current_row = 0
    border = _fg(60, 140, 180)

    def hline() -> None:
        nonlocal current_row
        out.append(f"{border}├{'─' * (w - 2)}┤{RST}")
        current_row += 1

    def row_raw(content: str) -> None:
        nonlocal current_row
        out.append(f"{border}│{RST} {_pad_visible(content, inner)} {border}│{RST}")
        current_row += 1

    def rows_section(title: str, lines: list[str], title_color: tuple[int, int, int], max_lines: int) -> None:
        nonlocal current_row
        tr, tg, tb = title_color
        row_raw(f"{_fg(tr, tg, tb)}{BLD}{title}{RST}")
        shown = 0
        for line in lines:
            if shown >= max_lines:
                row_raw(f"{DIM}  ... ({len(lines) - max_lines} more lines){RST}")
                break
            row_raw(f"  {line}")
            shown += 1
        if not lines:
            row_raw(f"{DIM}  (none){RST}")

    mode_label = str(board.mode).upper()
    screen_flag = "SCREEN:ok" if board.screen_valid else "SCREEN:--"
    title = f" ENDGAME-AI  IT:{board.iteration:03d}  {board.agent_id}  {mode_label}  {screen_flag} "
    out.append(f"{border}┌─{BLD}{_fg(200, 220, 255)}{title}{RST}{border}{'─' * max(0, w - _plain_len(title) - 4)}┐{RST}")
    current_row += 1

    stag_r, stag_g, stag_b = _gradient(board.stagnation_score)
    bar_w = max(8, (inner - 52) // 2)
    row_raw(
        f"{_fg(stag_r, stag_g, stag_b)}stag {board.stagnation_score:.2f}{RST} {_bar_gradient(board.stagnation_score, bar_w)}  "
        f"{_fg(100, 150, 255)}pid {board.pid_output:.2f}{RST} {_bar_gradient(min(1.0, board.pid_output / 3.0), bar_w)}  "
        f"{DIM}rep {board.repetition_score:.2f}  fails {board.consecutive_failures}  scr-stag {board.screen_stagnation}{RST}"
    )
    slope_ch = "▲" if board.pid_slope > 0.02 else ("▼" if board.pid_slope < -0.02 else "─")
    row_raw(f"{DIM}slope {board.pid_slope:+.3f} {slope_ch}  int {board.pid_integral:.2f}  energy {board.attractor_energy:.2f}{RST}")

    hline()

    status_lines: list[str] = []
    if last_event:
        lr, lg, lb = _role_color(last_event.split(":")[1] if ":" in last_event else "")
        status_lines.append(f"{_fg(lr, lg, lb)}event {last_event}{RST}")
    if board.focused_window:
        status_lines.extend(_wrap_plain(f"focus: {board.focused_window}", wrap_w))
    if board.last_instruction:
        status_lines.extend(_wrap_plain(f"next: {board.last_instruction}", wrap_w))
    rows_section("STATUS", status_lines, (120, 180, 255), 4)

    hline()

    if board.mode == "coordinate" and board.children:
        child_lines: list[str] = []
        for aid, handle in board.children.items():
            state = handle.state
            mark = "RUN" if state == "running" else state.upper()
            err = f" err={handle.error[:40]}" if handle.error else ""
            child_lines.append(f"{aid} [{mark}]{err}")
        rows_section("CHILDREN", child_lines, (100, 200, 255), 6)

    _checklist_y_start = current_row + 1
    checklist_lines: list[str] = []
    if board.plan_steps:
        total = len(board.plan_steps)
        idx = board.plan_step_index
        start = max(0, idx - 2)
        end = min(total, start + 8)
        if end - start < 8:
            start = max(0, end - 8)
        for i in range(start, end):
            step = board.plan_steps[i]
            if i < idx:
                mark = f"{_fg(80, 220, 120)}done{RST}"
            elif i == idx:
                mark = f"{_fg(255, 220, 50)}NOW{RST}"
            else:
                mark = f"{_fg(80, 80, 100)}wait{RST}"
            for j, wl in enumerate(_wrap_plain(step, wrap_w - 8)):
                prefix = f"[{i + 1}/{total}] {mark} " if j == 0 else "         "
                checklist_lines.append(f"{prefix}{wl}")
        if start > 0 or end < total:
            checklist_lines.insert(0, f"{DIM}steps {start + 1}-{end} of {total}{RST}")
    else:
        checklist_lines.append(f"{DIM}(planner has not emitted checklist yet){RST}")
    rows_section("CHECKLIST", checklist_lines, (255, 200, 100), 10)
    _checklist_y_end = current_row

    hline()

    actor_lines: list[str] = []
    if board.actor_observe:
        actor_lines.extend(_wrap_plain(board.actor_observe, wrap_w))
    if board.last_verb:
        ok = f"{_fg(80, 220, 120)}OK{RST}" if board.last_success else f"{_fg(220, 60, 60)}FAIL{RST}"
        obs = board.last_observation.replace("\n", " ")[:500]
        actor_lines.append(f"{ok} {board.last_verb}: " + " ".join(_wrap_plain(obs, wrap_w - 10)))
    if board.actor_conclusion:
        cc = (80, 220, 120) if board.actor_conclusion == "EXPECTED" else (220, 60, 60)
        actor_lines.append(f"{_fg(*cc)}conclusion {board.actor_conclusion}{RST}")
    rows_section("ACTOR", actor_lines, (255, 180, 50), 6)

    hline()

    plan_lines = _wrap_plain(board.last_plan_because, wrap_w) if board.last_plan_because else []
    rows_section("PLANNER", plan_lines, (100, 180, 255), 4)

    hline()

    goal_plain = board.goal or ""
    goal_lines = _wrap_plain(goal_plain, wrap_w)
    if len(goal_plain) > wrap_w * 4:
        goal_lines = goal_lines[:4]
        goal_lines.append(f"{DIM}({len(goal_plain)} chars total — full text in log file){RST}")
    rows_section("GOAL", goal_lines, (180, 100, 255), 5)

    hline()

    used = current_row + 2
    log_budget = max(6, rows - used - 1)
    row_raw(f"{BLD}{_fg(200, 220, 255)}EVENT LOG{RST} {DIM}(full width; details in log-main-*.txt){RST}")

    recent = list(_event_log)[-log_budget:]
    for ev in recent:
        parts = ev.split(" ", 1)
        ts = parts[0] if parts else ""
        body = parts[1] if len(parts) > 1 else ev
        wrapped = _wrap_plain(body, wrap_w - 9)
        er, eg, eb = _event_style(body)
        for i, wl in enumerate(wrapped[:3]):
            prefix = f"{DIM}{ts}{RST} " if i == 0 else "       "
            row_raw(f"{prefix}{_fg(er, eg, eb)}{wl}{RST}")
        if len(wrapped) > 3:
            row_raw(f"       {DIM}... ({len(wrapped) - 3} more){RST}")

    for _ in range(log_budget - len(recent)):
        row_raw("")

    status_footer = f"rep {board.repetition_score:.2f}"
    if last_event:
        status_footer += f"  |  {last_event}"
    footer_plain = status_footer
    out.append(
        f"{border}└─ {DIM}{footer_plain}{RST}{border}{'─' * max(0, w - len(footer_plain) - 6)}┘{RST}"
    )

    progress_state = 2 if board.stagnation_score > 0.8 else (3 if board.stagnation_score > 0.5 else 1)
    sys.stdout.write(_osc_progress(board.stagnation_score, progress_state))
    sys.stdout.write(f"{ESC}[H{ESC}[J")
    sys.stdout.write("\n".join(out))
    sys.stdout.flush()