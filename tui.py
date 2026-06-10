from __future__ import annotations
import ctypes
import json
import msvcrt
import sys
import time
from pathlib import Path
from typing import Any, cast

from config import (
    EVENTS_PATH, SNAPSHOT_PATH, DISABLED_PATH, GUI_MODE_PATH,
)

# TUI constants (moved from config.py)
STD_OUTPUT_HANDLE: int = -11
TUI_ALT_SCREEN_ON: str = "\x1b[?1049h"
TUI_ALT_SCREEN_OFF: str = "\x1b[?1049l"
TUI_HIDE_CURSOR: str = "\x1b[?25l"
TUI_SHOW_CURSOR: str = "\x1b[?25h"
TUI_HOME_CLEAR: str = "\x1b[H\x1b[2J"

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
    "reflect", "mutation", "fission", "fission_blocked", "start", "stop",
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


def _fg(r: int, g: int, b: int) -> str:
    return f"\x1b[38;2;{r};{g};{b}m"


def _bar(v: float, w: int, color: str) -> str:
    f = max(0, min(w, int(v * w)))
    return color + "█" * f + DIM + "░" * (w - f) + RST


def _clip(s: str, w: int) -> str:
    return s if len(s) <= w else s[: max(0, w - 1)] + "…"


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
        self.paused = bool(goal)
        self._lines: list[str] = []
        self._in_alt = False
        self.last_phase = ""
        self.last_reason = ""

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

    def handle_key(self) -> None:
        if not msvcrt.kbhit():
            return
        key = msvcrt.getch()
        if key == b"q":
            self.running = False
        elif key == b" ":
            self._launch()

    def _launch(self) -> None:
        import subprocess
        from config import BASE_DIR
        if self.proc or not self.goal:
            return
        for p in (self.events_path, self.snapshot_path, DISABLED_PATH, GUI_MODE_PATH):
            if p.exists():
                p.unlink()
        self.events, self.last_size, self._lines = [], 0, []
        self.paused = False
        self.proc = subprocess.Popen(
            [sys.executable, "main.py", self.goal, "--backend", self.backend, "--event-budget", str(self.budget)],
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
        return [e for e in self.events if e.get("phase") in WORK_PHASES][-12:]

    def render(self) -> list[str]:
        w, _ = _size()
        w = max(80, w)
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
        goal = _clip(str(s.get("goal", "") or self.goal or "REACTOR"), w - 4)
        plan: list[dict[str, Any]] = s.get("plan", [])
        completed: list[str] = s.get("completed", [])
        done_when = str(s.get("done_when", ""))
        wing = bool(s.get("wing_crossed", False))

        def node(name: str, chain: tuple[str, ...]) -> str:
            on = name == active or (name == "fission" and active == "fission_sustain")
            label = name.upper() if on else name
            col = _fg(255, 220, 80) if on else (_fg(120, 200, 255) if name in chain else DIM)
            mark = "●" if on else "○"
            return f"{col}{mark}{label}{RST}"

        lines: list[str] = []
        status = "RUN" if self.proc else ("READY" if self.paused and not self.events else "LIVE")
        lines.append(f"{BOLD}{goal}{RST}")
        lines.append(
            f"{_fg(100,200,255)}{status}{RST}  "
            f"work={work}/{budget}  events={events_n}  power={power:.4f}  "
            f"stag={stag:.2f}  pid={pid:.2f}  energy={energy:.2f}  fail={failures}"
            + (f"  {_fg(255,200,0)}WING{RST}" if wing else "")
        )
        lines.append(DIM + "─" * (w - 1) + RST)

        flow_w = w - 2
        math_line = "  MATH  " + " ──► ".join(node(n, MATH_CHAIN) for n in MATH_CHAIN)
        lines.append(_clip(math_line, flow_w))
        agent_line = "  LOOP  " + " ──► ".join(node(n, AGENT_CHAIN) for n in AGENT_CHAIN)
        lines.append(_clip(agent_line, flow_w))
        side_line = "  SIDE  " + "    ".join(node(n, SIDE_AGENTS) for n in SIDE_AGENTS)
        lines.append(_clip(side_line, flow_w))
        if self.last_reason:
            lines.append(f"  {DIM}schedule.reason{RST}={self.last_reason}  {DIM}active{RST}={active}")

        lines.append(DIM + "─" * (w - 1) + RST)
        lines.append(f"  {DIM}stagnation{RST} {_bar(stag, 20, _fg(255, 100, 80))}  {DIM}pid_output{RST} {_bar(min(pid / 4, 1), 20, _fg(80, 140, 255))}")
        if done_when:
            lines.append(f"  {DIM}done_when{RST} {_clip(done_when, w - 14)}")

        if plan:
            done = sum(1 for p in plan if p.get("status") == "done")
            lines.append(f"  {DIM}plan{RST} [{done}/{len(plan)}]")
            for step in plan[:6]:
                st = step.get("status", "pending")
                txt = _clip(str(step.get("text", "")), w - 8)
                mark = "✓" if st == "done" else ("►" if st == "active" else "·")
                col = _fg(80, 220, 120) if st == "done" else (_fg(255, 220, 80) if st == "active" else DIM)
                lines.append(f"    {col}{mark}{RST} {txt}")
        elif completed:
            lines.append(f"  {_fg(80,255,180)}completed{RST} {_clip(completed[-1], w - 14)}")

        lines.append(DIM + "─" * (w - 1) + RST)
        lines.append(f"  {DIM}event tape{RST}")
        for e in self._work_events()[-8:]:
            n, ph = e.get("n", 0), str(e.get("phase", ""))
            lines.append(f"    {DIM}{n:>4}{RST} {_clip(self._brief(ph, e.get('d', {})), w - 10)}")

        lines.append(DIM + "─" * (w - 1) + RST)
        lines.append(f" {DIM}Space launch/relaunch  q quit  backend={self.backend}{RST}")
        return lines

    def _brief(self, phase: str, d: dict[str, Any]) -> str:
        match phase:
            case "schedule":
                s = d.get("step", "")
                return f"schedule.{d.get('reason', '')}" + (f" → {_clip(str(s), 40)}" if s else "")
            case "action":
                return f"{'ok' if d.get('ok') else 'FAIL'} {d.get('verb', '')} {_clip(str(d.get('obs', '')), 50)}"
            case "plan":
                return f"plan {d.get('mode', '')} steps={d.get('steps', '')} {_clip(str(d.get('done_when', '')), 40)}"
            case "verify":
                return f"verdict={d.get('verdict', '')} {_clip(str(d.get('evidence', '')), 45)}"
            case "fission":
                return f"★ power={d.get('power', 0):.4f} completions={d.get('completions', '')}"
            case "reflect":
                return _clip(str(d.get("diagnosis", "")), 70)
            case "stop":
                return f"stop reason={d.get('reason', '')} work={d.get('work', '')}"
            case _:
                return _clip(str(d), 70)

    def _paint(self, lines: list[str]) -> None:
        w, h = _size()
        padded = [_clip(ln, w).ljust(w) for ln in lines[:h]]
        while len(padded) < h:
            padded.append(" " * w)
        if not self._in_alt:
            _write(TUI_ALT_SCREEN_ON + TUI_HIDE_CURSOR)
            self._in_alt = True
        buf = SYNC_ON + "\x1b[H" + "\n".join(padded) + SYNC_OFF
        _write(buf)
        self._lines = padded

    def run_loop(self) -> None:
        try:
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
                _write(SYNC_OFF + TUI_ALT_SCREEN_OFF + TUI_SHOW_CURSOR)


def run_tui(path: Path | None = None, goal: str = "", backend: str = "lmstudio", budget: int = 20) -> None:
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