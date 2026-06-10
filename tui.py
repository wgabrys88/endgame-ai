from __future__ import annotations
import ctypes
import json
import msvcrt
import sys
import time
from pathlib import Path
from typing import Any

import log
from config import (
    EVENTS_PATH, SNAPSHOT_PATH, DISABLED_PATH, GUI_MODE_PATH, GOAL_PATH, PAUSE_PATH,
    PID_ROD_SCALE,
)

STD_OUTPUT_HANDLE: int = -11
TUI_ALT_SCREEN_ON: str = "\x1b[?1049h"
TUI_ALT_SCREEN_OFF: str = "\x1b[?1049l"
TUI_HIDE_CURSOR: str = "\x1b[?25l"
TUI_SHOW_CURSOR: str = "\x1b[?25h"

INPUT_ROWS: int = 4
EVENT_TAIL: int = 10

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_stdout_handle = _kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
_mode = ctypes.c_ulong()
_kernel32.GetConsoleMode(_stdout_handle, ctypes.byref(_mode))
_kernel32.SetConsoleMode(_stdout_handle, _mode.value | 0x0004)

MATH_CHAIN = ("stagnation", "lorenz", "pid", "scheduler")
AGENT_CHAIN = ("planner", "actor", "verifier", "fission")
SIDE_AGENTS = ("observer", "reflector")
LOOP_PHASES = frozenset({
    "schedule", "plan", "actor", "action", "observe", "verify",
    "reflect", "mutation", "fission", "fission_blocked", "goal_change",
    "planner.error", "actor.error", "verifier.error", "reflector.error",
})
WORK_PHASES = LOOP_PHASES | frozenset({"start", "stop"})

RST, DIM, BOLD = "\x1b[0m", "\x1b[2m", "\x1b[1m"


def _write(text: str) -> None:
    n = ctypes.c_ulong()
    _kernel32.WriteConsoleW(_stdout_handle, text, len(text), ctypes.byref(n), None)


def _size() -> tuple[int, int]:
    import struct
    buf = ctypes.create_string_buffer(22)
    _kernel32.GetConsoleScreenBufferInfo(_stdout_handle, buf)
    _, _, _, _, _, left, top, right, bottom, _, _ = struct.unpack("hhhhHhhhhhh", buf.raw)
    return right - left + 1, bottom - top + 1


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
    def __init__(self, events_path: Path, snapshot_path: Path, goal: str = "", backend: str = "lmstudio", budget: int = 20, autostart: bool = True) -> None:
        self.events_path = events_path
        self.snapshot_path = snapshot_path
        self.events: list[dict[str, Any]] = []
        self.snapshot: dict[str, Any] = {}
        self._events_sig: tuple[str, int, float] = ("", 0, 0.0)
        self._snapshot_mtime: float = 0.0
        self.running = True
        self.goal = goal
        self.backend = backend
        self.budget = budget
        self.proc: Any = None
        self._in_alt = False
        self.last_reason = ""
        self._loop_active = "—"
        self._math_active = "—"
        self._input_active = False
        self._input_buf = goal
        self._input_cursor = len(goal)
        self._autostart = autostart
        if goal:
            self._write_goal_file(goal)

    def _write_goal_file(self, text: str) -> None:
        GOAL_PATH.write_text(text, encoding="utf-8")

    def _read_goal_file(self) -> str:
        if GOAL_PATH.exists():
            try:
                return GOAL_PATH.read_text(encoding="utf-8").strip()
            except OSError:
                pass
        return self.goal

    def _reactor_live(self) -> bool:
        return self.proc is not None or log.reactor_running()

    def load(self) -> None:
        path = log.active_events_path()
        try:
            st = path.stat()
            sig = (str(path), st.st_size, st.st_mtime)
        except OSError:
            sig = ("", 0, 0.0)
        if sig != self._events_sig:
            self._events_sig = sig
            self.events_path = path
            try:
                self.events = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
                self._refresh_active()
            except (json.JSONDecodeError, OSError):
                pass
        if self.snapshot_path.exists():
            try:
                mt = self.snapshot_path.stat().st_mtime
                if mt != self._snapshot_mtime:
                    self._snapshot_mtime = mt
                    self.snapshot = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        if not self._input_active:
            file_goal = self._read_goal_file()
            if file_goal:
                self.goal = file_goal

    def _refresh_active(self) -> None:
        self._math_active = "—"
        self._loop_active = "—"
        self.last_reason = ""
        for e in reversed(self.events):
            p = str(e.get("phase", ""))
            d = e.get("d", {})
            if self._loop_active == "—" and p in LOOP_PHASES:
                self._loop_active = "actor" if p == "action" else p
                if p == "schedule":
                    self.last_reason = str(d.get("reason", ""))
            if self._math_active == "—" and p in MATH_CHAIN:
                self._math_active = p
            if self._math_active != "—" and self._loop_active != "—":
                break

    def _submit_goal(self) -> None:
        text = self._input_buf.strip()
        if not text:
            self._input_active = False
            return
        self.goal = text
        self._write_goal_file(text)
        self._input_active = False
        log.set_paused(False)
        if not self._reactor_live():
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
            log.set_paused(not log.paused())

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
        if self._reactor_live() or not goal:
            return
        self.goal = goal
        self._write_goal_file(goal)
        log.clean_stale_lock()
        for p in (EVENTS_PATH, self.snapshot_path, DISABLED_PATH, GUI_MODE_PATH, PAUSE_PATH):
            if p.exists():
                p.unlink()
        self.events, self._events_sig = [], ("", 0, 0.0)
        log.set_paused(False)
        self.proc = subprocess.Popen(
            [sys.executable, "main.py", goal, "--backend", self.backend, "--event-budget", str(self.budget)],
            cwd=str(BASE_DIR), creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def check_proc(self) -> None:
        if self.proc and self.proc.poll() is not None:
            self.proc = None

    def _work_events(self) -> list[dict[str, Any]]:
        return [e for e in self.events if e.get("phase") in WORK_PHASES]

    def _vchain(self, title: str, chain: tuple[str, ...], active: str, width: int) -> list[str]:
        lines = [f"{BOLD}{title}{RST}"]
        for name in chain:
            on = name == active or (name == "fission" and active == "fission_sustain")
            col = _fg(255, 220, 80) if on else DIM
            mark = "●" if on else "○"
            lines.append(f"  {col}{mark} {name}{RST}")
        return lines

    def _brief(self, phase: str, d: dict[str, Any]) -> str:
        match phase:
            case "schedule":
                s = d.get("step", "")
                base = f"reason={d.get('reason', '')}"
                return f"{base} step={s}" if s else base
            case "action" | "actor":
                if d.get("verb") or d.get("obs"):
                    return f"{'ok' if d.get('ok') else 'FAIL'} verb={d.get('verb', '')} obs={d.get('obs', '')}"
                return str(d)
            case "plan":
                return f"mode={d.get('mode', '')} steps={d.get('steps', '')} done_when={d.get('done_when', '')}"
            case "verify":
                return f"verdict={d.get('verdict', '')} evidence={d.get('evidence', '')}"
            case "goal_change":
                return f"to={d.get('to', '')}"
            case "stop":
                return f"reason={d.get('reason', '')} work={d.get('work', '')}"
            case _ if phase.endswith(".error"):
                return str(d.get("error", d))
            case _:
                return str(d) if d else ""

    def _render_input(self, w: int) -> list[str]:
        hint = f"{DIM}Enter submit  Esc cancel  Space pause  q quit{RST}"
        field_w = w - 6
        if self._input_active:
            border_col = _fg(100, 180, 255)
            field = self._input_buf
        else:
            border_col = DIM
            field = self.goal or "(press Enter to type a goal)"
        shown = _fit(_wrap(field, field_w - 1), INPUT_ROWS - 2, field_w - 1)
        lines = [f"{BOLD}{_fg(180, 210, 255)}GOAL INPUT{RST}  {hint}"]
        lines.append(f"{border_col}┌{'─' * field_w}┐{RST}")
        for row in shown:
            lines.append(f"{border_col}│{RST} {_pad_visible(row, field_w - 1)}{border_col}│{RST}")
        while len(lines) < INPUT_ROWS:
            lines.append(f"{border_col}│{RST}{' ' * field_w}{border_col}│{RST}")
        lines.append(f"{border_col}└{'─' * field_w}┘{RST}")
        return _fit(lines, INPUT_ROWS + 1, w)

    def render(self) -> list[str]:
        w, h = _size()
        w, h = max(80, w), max(28, h)
        body_h = h - INPUT_ROWS - 2

        s = self.snapshot
        stag = float(s.get("stagnation", 0))
        pid = float(s.get("pid_output", 0))
        energy = float(s.get("energy", 1))
        lx = float(s.get("lorenz_x", 0))
        ly = float(s.get("lorenz_y", 0))
        lz = float(s.get("lorenz_z", 0))
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
        trigger = s.get("reflect_trigger", {})

        if log.paused():
            status, status_col = "PAUSED", _fg(255, 180, 60)
        elif self._reactor_live():
            status, status_col = "RUN", _fg(80, 220, 120)
        elif not self.events:
            status, status_col = "READY", _fg(140, 180, 255)
        else:
            status, status_col = "LIVE", _fg(255, 220, 80)

        bar_w = w - 18
        lines: list[str] = []

        lines.append(f"{BOLD}{_fg(180, 210, 255)}GOAL{RST}")
        lines.extend(_fit(_wrap(goal or "—", w - 2), 4, w - 2))
        lines.append(DIM + "─" * (w - 1) + RST)

        clock = time.strftime("%H:%M:%S")
        log_name = Path(self._events_sig[0]).name if self._events_sig[0] else "—"
        lines.append(
            f"{status_col}{status}{RST} {DIM}{clock}{RST}  "
            f"work {work}/{budget}  events {events_n}  fail {failures}  power {power:.4f}"
            + (f"  {_fg(255, 200, 0)}WING{RST}" if wing else "")
        )
        lines.append(
            f"{DIM}log{RST} {log_name}  {DIM}loop{RST} {self._loop_active}  "
            f"{DIM}math{RST} {self._math_active}"
            + (f"  {DIM}sched{RST} {self.last_reason}" if self.last_reason else "")
        )
        if focused:
            lines.extend(_fit(_wrap(f"focus: {focused}", w - 2), 1, w - 2))

        lines.append(DIM + "─" * (w - 1) + RST)
        lines.append(f"{DIM}stagnation{RST} {_bar(stag, bar_w, _fg(255, 100, 80))}")
        lines.append(f"{DIM}pid_output{RST} {_bar(min(pid / PID_ROD_SCALE, 1), bar_w, _fg(80, 140, 255))}")
        lines.append(f"{DIM}energy{RST}    {_bar(min(energy / 3, 1), bar_w, _fg(120, 220, 140))}")
        lines.append(
            f"{DIM}lorenz{RST}   x={lx:.2f} y={ly:.2f} z={lz:.2f}  "
            f"{DIM}stag{RST}={stag:.3f} {DIM}pid{RST}={pid:.3f} {DIM}energy{RST}={energy:.3f}"
        )
        if trigger:
            lines.extend(_fit(_wrap(f"reflect_trigger: {trigger}", w - 2), 2, w - 2))

        lines.append(DIM + "─" * (w - 1) + RST)
        flow_w = max(20, w // 3 - 2)
        math = self._vchain("MATH", MATH_CHAIN, self._math_active, flow_w)
        loop = self._vchain("LOOP", AGENT_CHAIN, self._loop_active, flow_w)
        side = self._vchain("SIDE", SIDE_AGENTS, self._loop_active, flow_w)
        flow_row = max(len(math), len(loop), len(side))
        for i in range(flow_row):
            a = _pad_visible(math[i] if i < len(math) else "", flow_w)
            b = _pad_visible(loop[i] if i < len(loop) else "", flow_w)
            c = _pad_visible(side[i] if i < len(side) else "", w - 2 * flow_w - 4)
            lines.append(f"{a}  {b}  {c}")

        if done_when:
            lines.append(DIM + "─" * (w - 1) + RST)
            lines.append(f"{BOLD}{_fg(200, 180, 255)}DONE WHEN{RST}")
            lines.extend(_fit(_wrap(done_when, w - 2), 2, w - 2))

        lines.append(DIM + "─" * (w - 1) + RST)
        if plan:
            done_n = sum(1 for p in plan if p.get("status") == "done")
            lines.append(f"{BOLD}{_fg(200, 230, 255)}PLAN{RST} [{done_n}/{len(plan)}]")
            for step in plan:
                st = step.get("status", "pending")
                txt = str(step.get("text", ""))
                mark = "✓" if st == "done" else ("►" if st == "active" else "·")
                col = _fg(80, 220, 120) if st == "done" else (_fg(255, 220, 80) if st == "active" else DIM)
                parts = _wrap(txt, w - 4)
                for i, part in enumerate(parts):
                    prefix = f"{col}{mark}{RST} " if i == 0 else "  "
                    lines.append(f"{prefix}{part}")
        elif completed:
            lines.append(f"{_fg(80, 255, 180)}COMPLETED{RST}")
            lines.extend(_wrap(completed[-1], w - 2))
        else:
            lines.append(f"{DIM}no plan{RST}")

        lines.append(DIM + "─" * (w - 1) + RST)
        lines.append(f"{BOLD}{_fg(180, 210, 255)}RECENT EVENTS{RST}")
        tail = self._work_events()[-EVENT_TAIL:]
        for e in tail:
            n, ph = e.get("n", 0), str(e.get("phase", ""))
            brief = self._brief(ph, e.get("d", {}))
            for i, part in enumerate(_wrap(f"{n} {ph} {brief}", w - 2)):
                lines.append(f"{'  ' if i else ''}{part}")

        panel = _fit(lines, body_h, w)
        panel.extend(self._render_input(w))
        return _fit(panel, h, w)

    def _paint(self, lines: list[str]) -> None:
        w, h = _size()
        padded = [_pad_visible(ln, w) for ln in lines[:h]]
        while len(padded) < h:
            padded.append(" " * w)
        if not self._in_alt:
            _write(TUI_ALT_SCREEN_ON + (TUI_SHOW_CURSOR if self._input_active else TUI_HIDE_CURSOR))
            self._in_alt = True
        _write("\x1b[H" + "\n".join(padded))

    def run_loop(self) -> None:
        try:
            if self._autostart and self.goal.strip() and not self._reactor_live():
                self._launch()
            while self.running:
                self.load()
                self.handle_key()
                self.check_proc()
                self._paint(self.render())
                time.sleep(0.12)
        except KeyboardInterrupt:
            pass
        finally:
            if self.proc:
                self.proc.terminate()
            if self._in_alt:
                _write(TUI_ALT_SCREEN_OFF + TUI_SHOW_CURSOR)


def run_tui(path: Path | None = None, goal: str = "", backend: str = "lmstudio", budget: int = 20, autostart: bool = True) -> None:
    if goal:
        GOAL_PATH.write_text(goal, encoding="utf-8")
    TUI(path or EVENTS_PATH, SNAPSHOT_PATH, goal=goal, backend=backend, budget=budget, autostart=autostart).run_loop()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(prog="endgame-ai-tui")
    p.add_argument("goal", nargs="?", default="")
    p.add_argument("--backend", choices=["lmstudio", "acp"], default="lmstudio")
    p.add_argument("--event-budget", type=int, default=20)
    p.add_argument("--events", type=str, default="")
    p.add_argument("--no-autostart", action="store_true")
    a = p.parse_args()
    run_tui(
        path=Path(a.events) if a.events else None,
        goal=a.goal, backend=a.backend, budget=a.event_budget,
        autostart=not a.no_autostart,
    )