from __future__ import annotations
import ctypes
import json
import msvcrt
import sys
import time
from pathlib import Path
from typing import Any

from config import (
    EVENTS_PATH, SNAPSHOT_PATH, DISABLED_PATH, GUI_MODE_PATH, GOAL_PATH,
)

STD_OUTPUT_HANDLE: int = -11
TUI_ALT_SCREEN_ON: str = "\x1b[?1049h"
TUI_ALT_SCREEN_OFF: str = "\x1b[?1049l"
TUI_HIDE_CURSOR: str = "\x1b[?25l"
TUI_SHOW_CURSOR: str = "\x1b[?25h"
TUI_HOME_CLEAR: str = "\x1b[H\x1b[2J"

PANEL_FRAC: float = 0.25
PANEL_MIN_W: int = 48
PANEL_MAX_W: int = 96
INPUT_ROWS: int = 3

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_stdout_handle = _kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
_mode = ctypes.c_ulong()
_kernel32.GetConsoleMode(_stdout_handle, ctypes.byref(_mode))
_kernel32.SetConsoleMode(_stdout_handle, _mode.value | 0x0004)

MATH_CHAIN = ("stagnation", "lorenz", "pid", "scheduler")
AGENT_CHAIN = ("planner", "actor", "verifier", "fission")
SIDE_AGENTS = ("observer", "reflector")
WORK_PHASES = frozenset({
    "schedule", "plan", "actor", "action", "observe", "verify",
    "reflect", "mutation", "fission", "fission_blocked", "goal_change",
    "start", "stop",
})

RST, DIM, BOLD = "\x1b[0m", "\x1b[2m", "\x1b[1m"
SYNC_ON, SYNC_OFF = "\x1b[?2026h", "\x1b[?2026l"


def _write(text: str) -> None:
    n = ctypes.c_ulong()
    _kernel32.WriteConsoleW(_stdout_handle, text, len(text), ctypes.byref(n), None)


def _size() -> tuple[int, int]:
    import struct
    buf = ctypes.create_string_buffer(22)
    _kernel32.GetConsoleScreenBufferInfo(_stdout_handle, buf)
    _, _, _, _, _, left, top, right, bottom, _, _ = struct.unpack("hhhhHhhhhhh", buf.raw)
    return right - left + 1, bottom - top + 1


def _panel_w(total_w: int) -> int:
    return max(PANEL_MIN_W, min(PANEL_MAX_W, int(total_w * PANEL_FRAC)))


def _fg(r: int, g: int, b: int) -> str:
    return f"\x1b[38;2;{r};{g};{b}m"


def _bar(v: float, w: int, color: str) -> str:
    w = max(4, w)
    f = max(0, min(w, int(v * w)))
    return color + "█" * f + DIM + "░" * (w - f) + RST


def _wrap(text: str, width: int) -> list[str]:
    if width < 4:
        return [text[:width]]
    words = text.replace("\n", " ").split()
    if not words:
        return [""]
    lines: list[str] = []
    cur = words[0]
    for word in words[1:]:
        if len(cur) + 1 + len(word) <= width:
            cur += " " + word
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines


def _fit(lines: list[str], height: int, width: int) -> list[str]:
    out: list[str] = []
    for ln in lines:
        for part in _wrap(ln, width):
            out.append(part)
            if len(out) >= height:
                return out[:height]
    while len(out) < height:
        out.append("")
    return out[:height]


def _plain(s: str) -> str:
    out: list[str] = []
    i, n = 0, len(s)
    while i < n:
        if s[i] == "\x1b" and i + 1 < n and s[i + 1] == "[":
            j = i + 2
            while j < n and s[j] not in "ABCDEFGHJKSTfmnsulh":
                j += 1
            if j < n:
                j += 1
            i = j
            continue
        out.append(s[i])
        i += 1
    return "".join(out)


def _pad_visible(text: str, width: int) -> str:
    plain = _plain(text)
    if len(plain) >= width:
        return text
    return text + " " * (width - len(plain))


class TUI:
    def __init__(self, events_path: Path, snapshot_path: Path, goal: str = "", backend: str = "lmstudio", budget: int = 20) -> None:
        self.events_path = events_path
        self.snapshot_path = snapshot_path
        self.events: list[dict[str, Any]] = []
        self.snapshot: dict[str, Any] = {}
        self.last_size = 0
        self.running = True
        self.disabled: set[str] = set()
        self.goal = goal
        self.backend = backend
        self.budget = budget
        self.proc: Any = None
        self.paused = not bool(goal)
        self._in_alt = False
        self.last_phase = ""
        self.last_reason = ""
        self._input_active = False
        self._input_buf = goal
        self._input_cursor = len(goal)
        self._last_applied_goal = goal
        if goal:
            self._write_goal_file(goal)

    def _write_goal_file(self, text: str) -> None:
        GOAL_PATH.write_text(text, encoding="utf-8")
        self._last_applied_goal = text

    def _read_goal_file(self) -> str:
        if GOAL_PATH.exists():
            try:
                return GOAL_PATH.read_text(encoding="utf-8").strip()
            except OSError:
                pass
        return self.goal

    def load(self) -> None:
        if self.events_path.exists():
            sz = self.events_path.stat().st_size
            if sz != self.last_size:
                self.last_size = sz
                try:
                    self.events = [json.loads(ln) for ln in self.events_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
                    if self.events:
                        e = self.events[-1]
                        self.last_phase = str(e.get("phase", ""))
                        d = e.get("d", {})
                        if self.last_phase == "schedule":
                            self.last_reason = str(d.get("reason", ""))
                except (json.JSONDecodeError, OSError):
                    pass
        if self.snapshot_path.exists():
            try:
                self.snapshot = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        file_goal = self._read_goal_file()
        if file_goal and not self._input_active:
            self.goal = file_goal

    def _submit_goal(self) -> None:
        text = self._input_buf.strip()
        self.goal = text
        self._write_goal_file(text)
        self._input_active = False
        if text and not self.proc:
            self._launch()

    def handle_key(self) -> None:
        if not msvcrt.kbhit():
            return
        ch = msvcrt.getwch()
        if self._input_active:
            self._handle_input_key(ch)
            return
        if ch in ("\r", "\n"):
            self._input_active = True
            self._input_buf = self.goal
            self._input_cursor = len(self._input_buf)
        elif ch.lower() == "q":
            self.running = False
        elif ch == " ":
            self._launch()

    def _handle_input_key(self, ch: str) -> None:
        if ch in ("\r", "\n"):
            self._submit_goal()
        elif ch == "\x1b":
            self._input_active = False
            self._input_buf = self.goal
            self._input_cursor = len(self._input_buf)
        elif ch in ("\x08", "\x7f"):
            if self._input_cursor > 0:
                self._input_buf = self._input_buf[: self._input_cursor - 1] + self._input_buf[self._input_cursor :]
                self._input_cursor -= 1
        elif ch == "\x03":
            self._input_active = False
        elif len(ch) == 1 and ch >= " ":
            self._input_buf = self._input_buf[: self._input_cursor] + ch + self._input_buf[self._input_cursor :]
            self._input_cursor += 1

    def _launch(self) -> None:
        import subprocess
        from config import BASE_DIR
        goal = self.goal.strip() or self._read_goal_file()
        if self.proc or not goal:
            return
        self.goal = goal
        self._write_goal_file(goal)
        for p in (self.events_path, self.snapshot_path, DISABLED_PATH, GUI_MODE_PATH):
            if p.exists():
                p.unlink()
        self.events, self.last_size = [], 0
        self.paused = False
        self.proc = subprocess.Popen(
            [sys.executable, "main.py", goal, "--backend", self.backend, "--event-budget", str(self.budget)],
            cwd=str(BASE_DIR), creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def check_proc(self) -> None:
        if self.proc and self.proc.poll() is not None:
            self.proc = None

    def _active_phase(self) -> str:
        for e in reversed(self.events):
            p = str(e.get("phase", ""))
            if p in MATH_CHAIN or p in AGENT_CHAIN or p in SIDE_AGENTS or p == "action":
                return p
        return self.last_phase or "—"

    def _work_events(self) -> list[dict[str, Any]]:
        return [e for e in self.events if e.get("phase") in WORK_PHASES]

    def _vchain(self, title: str, chain: tuple[str, ...], active: str, width: int) -> list[str]:
        lines = [f"{BOLD}{title}{RST}"]
        for name in chain:
            on = name == active or (name == "fission" and active == "fission_sustain")
            col = _fg(255, 220, 80) if on else DIM
            mark = "●" if on else "○"
            lines.append(f"  {col}{mark} {name}{RST}")
        return _fit(lines, len(chain) + 1, width)

    def _render_status(self, pw: int, h: int) -> list[str]:
        s = self.snapshot
        active = self._active_phase()
        stag = float(s.get("stagnation", 0))
        pid = float(s.get("pid_output", 0))
        energy = float(s.get("energy", 1))
        power = float(s.get("power", 0))
        work = int(s.get("work_events", 0))
        events_n = int(s.get("events", len(self.events)))
        budget = int(s.get("budget", self.budget))
        failures = int(s.get("consecutive_failures", 0))
        goal = str(s.get("goal", "") or self.goal or "")
        plan: list[dict[str, Any]] = s.get("plan", [])
        completed: list[str] = s.get("completed", [])
        done_when = str(s.get("done_when", ""))
        wing = bool(s.get("wing_crossed", False))
        focused = str(s.get("focused_window", ""))

        body_h = h - INPUT_ROWS - 1
        goal_h = max(3, body_h // 7)
        metrics_h = 5
        flow_h = 13
        done_h = 3 if done_when else 0
        plan_h = max(4, body_h - goal_h - metrics_h - flow_h - done_h - 2)

        bar_w = pw - 16
        status = "RUN" if self.proc else ("READY" if self.paused and not self.events else "LIVE")
        status_col = _fg(80, 220, 120) if status == "RUN" else (_fg(255, 220, 80) if status == "LIVE" else _fg(140, 180, 255))

        lines: list[str] = []
        lines.append(f"{BOLD}{_fg(180, 210, 255)}GOAL{RST}")
        lines.extend(_fit(_wrap(goal or "(type a goal below)", pw - 2), goal_h, pw - 2))

        lines.append(DIM + "─" * (pw - 1) + RST)
        lines.append(
            f"{status_col}{status}{RST}  work {work}/{budget}  events {events_n}  fail {failures}"
            + (f"  {_fg(255, 200, 0)}WING{RST}" if wing else "")
        )
        lines.append(f"{DIM}active{RST} {active}  {DIM}power{RST} {power:.4f}")
        if self.last_reason:
            lines.extend(_fit(_wrap(f"schedule: {self.last_reason}", pw - 2), 1, pw - 2))
        if focused:
            lines.extend(_fit(_wrap(f"focus: {focused}", pw - 2), 1, pw - 2))

        lines.append(DIM + "─" * (pw - 1) + RST)
        lines.append(f"{DIM}stagnation{RST} {_bar(stag, bar_w, _fg(255, 100, 80))}")
        lines.append(f"{DIM}pid_output{RST} {_bar(min(pid / 4, 1), bar_w, _fg(80, 140, 255))}")
        lines.append(f"{DIM}energy{RST}    {_bar(min(energy / 2, 1), bar_w, _fg(120, 220, 140))}")
        lines.append(f"{DIM}values{RST}    stag={stag:.3f} pid={pid:.3f} energy={energy:.3f}")
        while len(lines) < goal_h + 2 + metrics_h + 2:
            lines.append("")

        lines.append(DIM + "─" * (pw - 1) + RST)
        math = self._vchain("MATH", MATH_CHAIN, active, pw - 2)
        loop = self._vchain("LOOP", AGENT_CHAIN, active, pw - 2)
        side = self._vchain("SIDE", SIDE_AGENTS, active, pw - 2)
        flow_lines = math + [""] + loop + [""] + side
        lines.extend(_fit(flow_lines, flow_h, pw - 2))

        if done_when:
            lines.append(DIM + "─" * (pw - 1) + RST)
            lines.append(f"{BOLD}{_fg(200, 180, 255)}DONE WHEN{RST}")
            lines.extend(_fit(_wrap(done_when, pw - 2), done_h, pw - 2))

        lines.append(DIM + "─" * (pw - 1) + RST)
        if plan:
            done = sum(1 for p in plan if p.get("status") == "done")
            lines.append(f"{BOLD}{_fg(200, 230, 255)}PLAN{RST} [{done}/{len(plan)}]")
            plan_lines: list[str] = []
            for step in plan:
                st = step.get("status", "pending")
                txt = str(step.get("text", ""))
                mark = "✓" if st == "done" else ("►" if st == "active" else "·")
                col = _fg(80, 220, 120) if st == "done" else (_fg(255, 220, 80) if st == "active" else DIM)
                parts = _wrap(txt, pw - 6)
                for i, part in enumerate(parts):
                    prefix = f"  {col}{mark}{RST} " if i == 0 else "    "
                    plan_lines.append(f"{prefix}{part}")
            lines.extend(_fit(plan_lines, plan_h, pw - 2))
        elif completed:
            lines.append(f"{_fg(80, 255, 180)}COMPLETED{RST}")
            lines.extend(_fit(_wrap(completed[-1], pw - 2), plan_h - 1, pw - 2))
        else:
            lines.append(f"{DIM}no active plan{RST}")
            lines.extend([""] * (plan_h - 1))

        return _fit(lines, body_h, pw)

    def _render_log(self, lw: int, h: int) -> list[str]:
        lines: list[str] = [f"{BOLD}{_fg(180, 210, 255)}EVENTS{RST}"]
        for e in self._work_events():
            n, ph = e.get("n", 0), str(e.get("phase", ""))
            brief = self._brief(ph, e.get("d", {}))
            header = f"{DIM}{n:>5}{RST} {BOLD}{ph}{RST}"
            lines.append(header)
            for part in _wrap(brief, lw - 2):
                lines.append(f"  {part}")
            lines.append("")
        return _fit(lines, h, lw)

    def _render_input(self, pw: int) -> list[str]:
        label = f"{BOLD}{_fg(180, 210, 255)}GOAL INPUT{RST}  {DIM}Enter send  Esc cancel  Space launch{RST}"
        field_w = pw - 4
        if self._input_active:
            shown = self._input_buf
            cursor = self._input_cursor
            before = shown[:cursor]
            after = shown[cursor:]
            caret = _fg(255, 255, 255) + (before[-1] if before else " ") + RST
            if before:
                field = before[:-1] + caret + after
            else:
                field = caret + after
            border_col = _fg(100, 180, 255)
        else:
            field = self.goal or self._input_buf
            border_col = DIM
            if len(_plain(field)) > field_w:
                field = field[-field_w:]
        field_plain = _plain(field)
        if len(field_plain) > field_w:
            field = field[-field_w:]
        box_top = f"{border_col}┌{'─' * field_w}┐{RST}"
        box_mid = f"{border_col}│{RST} {_pad_visible(field, field_w - 1)}{border_col}│{RST}"
        box_bot = f"{border_col}└{'─' * field_w}┘{RST}"
        return _fit([label, box_top, box_mid, box_bot], INPUT_ROWS, pw)

    def _brief(self, phase: str, d: dict[str, Any]) -> str:
        match phase:
            case "schedule":
                s = d.get("step", "")
                base = f"reason={d.get('reason', '')}"
                return f"{base} step={s}" if s else base
            case "action":
                return f"{'ok' if d.get('ok') else 'FAIL'} verb={d.get('verb', '')} obs={d.get('obs', '')}"
            case "plan":
                return f"mode={d.get('mode', '')} steps={d.get('steps', '')} done_when={d.get('done_when', '')}"
            case "verify":
                return f"verdict={d.get('verdict', '')} evidence={d.get('evidence', '')}"
            case "fission":
                return f"power={d.get('power', 0):.4f} completions={d.get('completions', '')}"
            case "reflect":
                return str(d.get("diagnosis", ""))
            case "goal_change":
                return f"from={d.get('from', '')} to={d.get('to', '')}"
            case "stop":
                return f"reason={d.get('reason', '')} work={d.get('work', '')}"
            case _:
                return str(d)

    def render(self) -> tuple[list[str], list[str]]:
        w, h = _size()
        w, h = max(100, w), max(30, h)
        pw = _panel_w(w)
        lw = w - pw - 1
        status = self._render_status(pw, h)
        log_lines = self._render_log(lw, h)
        input_lines = self._render_input(pw)
        status = status[: h - INPUT_ROWS] + input_lines
        return status, log_lines

    def _paint(self, left: list[str], right: list[str]) -> None:
        w, h = _size()
        pw = _panel_w(max(100, w))
        lw = max(20, w - pw - 1)
        sep = DIM + "│" + RST
        rows: list[str] = []
        for y in range(h):
            l = left[y] if y < len(left) else ""
            r = right[y] if y < len(right) else ""
            l = _pad_visible(l, pw)
            r = _pad_visible(r, lw)
            rows.append(l + sep + r)
        if not self._in_alt:
            _write(TUI_ALT_SCREEN_ON + (TUI_SHOW_CURSOR if self._input_active else TUI_HIDE_CURSOR))
            self._in_alt = True
        buf = SYNC_ON + "\x1b[H" + "\n".join(rows) + SYNC_OFF
        _write(buf)
        if self._input_active:
            input_row = h - INPUT_ROWS + 2
            cursor_col = 2 + min(self._input_cursor, pw - 6)
            _write(f"\x1b[{input_row};{cursor_col}H")

    def run_loop(self) -> None:
        try:
            while self.running:
                self.load()
                self.handle_key()
                self.check_proc()
                left, right = self.render()
                self._paint(left, right)
                time.sleep(0.12)
        except KeyboardInterrupt:
            pass
        finally:
            if self.proc:
                self.proc.terminate()
            if self._in_alt:
                _write(SYNC_OFF + TUI_ALT_SCREEN_OFF + TUI_SHOW_CURSOR)


def run_tui(path: Path | None = None, goal: str = "", backend: str = "lmstudio", budget: int = 20) -> None:
    if goal:
        GOAL_PATH.write_text(goal, encoding="utf-8")
    TUI(path or EVENTS_PATH, SNAPSHOT_PATH, goal=goal, backend=backend, budget=budget).run_loop()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(prog="endgame-ai-tui")
    p.add_argument("goal", nargs="?", default="")
    p.add_argument("--backend", choices=["lmstudio", "acp"], default="lmstudio")
    p.add_argument("--event-budget", type=int, default=20)
    p.add_argument("--events", type=str, default="")
    a = p.parse_args()
    run_tui(path=Path(a.events) if a.events else None, goal=a.goal, backend=a.backend, budget=a.event_budget)