from __future__ import annotations
import os
import sys
from collections import deque
from typing import Any

ESC = "\033"
RST = f"{ESC}[0m"
BLD = f"{ESC}[1m"
DIM = f"{ESC}[2m"
GRN = f"{ESC}[32m"
RED = f"{ESC}[31m"
YLW = f"{ESC}[33m"
CYN = f"{ESC}[36m"
MGN = f"{ESC}[35m"

_event_log: deque[str] = deque(maxlen=200)


def _size() -> tuple[int, int]:
    try:
        return os.get_terminal_size()
    except OSError:
        return 50, 40


def _bar(value: float, w: int) -> str:
    filled = int(min(1.0, max(0.0, value)) * w)
    return "█" * filled + "░" * (w - filled)


def _spark(values: list[float], w: int) -> str:
    if not values:
        return ""
    chars = "▁▂▃▄▅▆▇█"
    recent = values[-w:]
    lo, hi = min(recent), max(recent)
    span = hi - lo if hi > lo else 1.0
    return "".join(chars[min(7, int((v - lo) / span * 7.99))] for v in recent)


def _cut(s: str, maxlen: int) -> str:
    if maxlen <= 3:
        return s[:maxlen]
    return s[:maxlen - 1] + "…" if len(s) > maxlen else s


def _pad(s: str, w: int) -> str:
    visible = _visible_len(s)
    if visible >= w:
        return s
    return s + " " * (w - visible)


def _visible_len(s: str) -> int:
    length = 0
    i = 0
    while i < len(s):
        if s[i] == "\033" and i + 1 < len(s) and s[i + 1] == "[":
            j = i + 2
            while j < len(s) and s[j] != "m":
                j += 1
            i = j + 1
        else:
            length += 1
            i += 1
    return length


def event(msg: str) -> None:
    from datetime import datetime
    ts = datetime.now().strftime("%H:%M:%S")
    _event_log.append(f"{ts} {msg}")


def enter() -> None:
    sys.stdout.write(f"{ESC}[?1049h{ESC}[?25l")
    sys.stdout.flush()


def exit() -> None:
    sys.stdout.write(f"{ESC}[?25h{ESC}[?1049l")
    sys.stdout.flush()


def render(board: Any, stagnation_history: list[float], last_event: str = "") -> None:
    cols, rows = _size()
    w = cols - 1
    inner = w - 4
    out: list[str] = []

    def hline() -> None:
        out.append(f"{CYN}├{'─' * (w - 2)}┤{RST}")

    def row(content: str) -> None:
        cut_content = _cut(content, inner)
        out.append(f"{CYN}│{RST} {_pad(cut_content, inner)} {CYN}│{RST}")

    out.append(f"{CYN}┌─ ENDGAME-AI {'─' * max(0, w - 16)}┐{RST}")

    slope_ch = "►" if board.pid_slope > 0.02 else ("◄" if board.pid_slope < -0.02 else "─")
    slope_c = RED if board.pid_slope > 0.02 else (GRN if board.pid_slope < -0.02 else DIM)

    bar_w = max(6, (inner - 30) // 2)
    row(f"{BLD}IT:{board.iteration:03d}{RST}  stag:{board.stagnation_score:.2f} {_bar(board.stagnation_score, bar_w)}  pid:{board.pid_output:.2f} {_bar(min(1.0, board.pid_output / 3.0), bar_w)}")
    row(f"{slope_c}slope:{board.pid_slope:+.3f} {slope_ch}{RST}  int:{board.pid_integral:.2f}  screen:{board.screen_stagnation}  fails:{board.consecutive_failures}")
    row(f"{DIM}{_spark(stagnation_history, inner)}{RST}")

    hline()

    if board.plan_steps:
        max_steps = min(len(board.plan_steps), max(3, (rows - 20) // 2))
        for i in range(max_steps):
            step = board.plan_steps[i]
            if i < board.plan_step_index:
                mark = f"{GRN}✓{RST}"
            elif i == board.plan_step_index:
                mark = f"{YLW}►{RST}"
            else:
                mark = f"{DIM}○{RST}"
            row(f"{mark} {_cut(step, inner - 4)}")
        if len(board.plan_steps) > max_steps:
            row(f"{DIM}  ... +{len(board.plan_steps) - max_steps} more{RST}")
    else:
        row(f"{DIM}(awaiting checklist){RST}")

    hline()

    if board.actor_observe:
        obs_lines: list[str] = []
        remaining: str = board.actor_observe
        while remaining and len(obs_lines) < 2:
            obs_lines.append(remaining[:inner - 6])
            remaining = remaining[inner - 6:]
        row(f"{BLD}SEES:{RST} {obs_lines[0]}")
        for ol in obs_lines[1:]:
            row(f"      {ol}")

    if board.last_verb:
        ok = f"{GRN}✓{RST}" if board.last_success else f"{RED}✗{RST}"
        row(f"{ok} {board.last_verb}: {_cut(board.last_observation, inner - len(board.last_verb) - 5)}")

    if board.actor_conclusion:
        cc = GRN if board.actor_conclusion == "EXPECTED" else RED
        row(f"  {cc}{board.actor_conclusion}{RST}")

    hline()

    if board.last_plan_because:
        plan_text = board.last_plan_because[:inner * 2]
        row(f"{BLD}PLAN:{RST} {_cut(plan_text, inner - 6)}")

    hline()

    goal_text = board.goal[:inner * 2]
    row(f"{MGN}GOAL:{RST} {_cut(goal_text, inner - 6)}")

    hline()

    used_lines = len(out) + 2
    log_space = max(3, rows - used_lines - 1)
    row(f"{BLD}LOG{RST}")
    recent_events = list(_event_log)[-log_space:]
    for ev in recent_events:
        row(f"{DIM}{_cut(ev, inner - 2)}{RST}")
    for _ in range(log_space - len(recent_events)):
        row("")

    status_parts = [f"rep:{board.repetition_score:.2f}"]
    if last_event:
        status_parts.append(last_event)
    status = "  ".join(status_parts)
    out.append(f"{CYN}└─ {DIM}{_cut(status, w - 5)}{RST}{CYN} {'─' * max(0, w - _visible_len(status) - 6)}┘{RST}")

    sys.stdout.write(f"{ESC}[H{ESC}[J")
    sys.stdout.write("\n".join(out))
    sys.stdout.flush()
