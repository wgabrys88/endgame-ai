from __future__ import annotations
import ctypes
import json
import msvcrt
import sys
import time
from pathlib import Path
from typing import Any, cast

from config import (
    STD_OUTPUT_HANDLE, TUI_ALT_SCREEN_ON, TUI_ALT_SCREEN_OFF,
    TUI_HIDE_CURSOR, TUI_SHOW_CURSOR, TUI_HOME_CLEAR,
    EVENTS_PATH, SNAPSHOT_PATH, DISABLED_PATH,
)

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_stdout_handle = _kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
ENABLE_VIRTUAL_TERMINAL: int = 0x0004
_mode = ctypes.c_ulong()
_kernel32.GetConsoleMode(_stdout_handle, ctypes.byref(_mode))
_kernel32.SetConsoleMode(_stdout_handle, _mode.value | ENABLE_VIRTUAL_TERMINAL)

ALL_AGENTS: list[str] = ["stagnation", "lorenz", "pid", "scheduler", "observer", "planner", "actor", "verifier", "reflector"]

RST: str = "\x1b[0m"
DIM: str = "\x1b[2m"
BOLD: str = "\x1b[1m"
BLINK: str = "\x1b[5m"


def _write(text: str) -> None:
    written = ctypes.c_ulong()
    _kernel32.WriteConsoleW(_stdout_handle, text, len(text), ctypes.byref(written), None)


def _size() -> tuple[int, int]:
    import struct
    buf = ctypes.create_string_buffer(22)
    _kernel32.GetConsoleScreenBufferInfo(_stdout_handle, buf)
    _, _, _, _, _, left, top, right, bottom, _, _ = struct.unpack("hhhhHhhhhhh", buf.raw)
    return right - left + 1, bottom - top + 1


def _fg(r: int, g: int, b: int) -> str:
    return f"\x1b[38;2;{r};{g};{b}m"


def _bg(r: int, g: int, b: int) -> str:
    return f"\x1b[48;2;{r};{g};{b}m"


def _vbar(value: float, height: int, color_fn) -> list[str]:
    filled = int(value * height)
    filled = max(0, min(height, filled))
    lines = []
    blocks = "░▒▓█"
    for row in range(height):
        level = height - 1 - row
        if level < filled:
            intensity = level / max(height - 1, 1)
            c = color_fn(intensity)
            char = blocks[min(3, int(intensity * 4))]
            lines.append(f"{c}{char}{char}{RST}")
        else:
            lines.append(f"{DIM}··{RST}")
    return lines


def _hbar(value: float, width: int, color: str) -> str:
    filled = int(value * width)
    filled = max(0, min(width, filled))
    return color + "━" * filled + DIM + "╌" * (width - filled) + RST


class TUI:
    def __init__(self, events_path: Path, snapshot_path: Path, goal: str = "", backend: str = "lmstudio", budget: int = 20) -> None:
        self.events_path = events_path
        self.snapshot_path = snapshot_path
        self.events: list[dict[str, Any]] = []
        self.snapshot: dict[str, Any] = {}
        self.last_file_size: int = 0
        self.running: bool = True
        self.disabled: set[str] = set()
        self.agent_cursor: int = 0
        self.goal: str = goal
        self.backend: str = backend
        self.budget: int = budget
        self.proc: Any = None
        self.paused: bool = bool(goal)
        self.fission_flash: float = 0.0

    def load(self) -> None:
        if self.events_path.exists():
            size = self.events_path.stat().st_size
            if size != self.last_file_size:
                self.last_file_size = size
                try:
                    raw = self.events_path.read_text(encoding="utf-8")
                    self.events = [json.loads(line) for line in raw.splitlines() if line.strip()]
                    if self.events and self.events[-1].get("phase") == "fission":
                        self.fission_flash = time.time()
                except (json.JSONDecodeError, OSError):
                    pass
        if self.snapshot_path.exists():
            try:
                self.snapshot = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        if DISABLED_PATH.exists():
            try:
                raw_d: object = json.loads(DISABLED_PATH.read_text(encoding="utf-8"))
                if isinstance(raw_d, list):
                    self.disabled = {str(v) for v in cast(list[Any], raw_d)}
            except (json.JSONDecodeError, OSError):
                pass
        else:
            self.disabled = set()

    def handle_key(self) -> None:
        if not msvcrt.kbhit():
            return
        key = msvcrt.getch()
        if key == b"\xe0" or key == b"\x00":
            ext = msvcrt.getch()
            if ext == b"H":
                self.agent_cursor = max(0, self.agent_cursor - 1)
            elif ext == b"P":
                self.agent_cursor = min(len(ALL_AGENTS) - 1, self.agent_cursor + 1)
            return
        if key == b"q":
            self.running = False
        elif key == b" ":
            self._launch()
        elif key == b"\r" or key == b"\n":
            name = ALL_AGENTS[self.agent_cursor]
            if name in self.disabled:
                self.disabled.discard(name)
            else:
                self.disabled.add(name)
            DISABLED_PATH.write_text(json.dumps(sorted(self.disabled)), encoding="utf-8")

    def _launch(self) -> None:
        import subprocess
        if self.proc is not None:
            return
        if not self.goal:
            return
        for p in (self.events_path, self.snapshot_path, DISABLED_PATH):
            if p.exists():
                p.unlink()
        self.events = []
        self.last_file_size = 0
        self.paused = False
        from config import BASE_DIR
        self.proc = subprocess.Popen(
            [sys.executable, "main.py", self.goal, "--backend", self.backend, "--event-budget", str(self.budget)],
            cwd=str(BASE_DIR),
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def check_proc(self) -> None:
        if self.proc is not None and self.proc.poll() is not None:
            self.proc = None

    def render(self) -> str:
        w, h = _size()
        s = self.snapshot
        stag = float(s.get("stagnation", 0))
        pid = float(s.get("pid_output", 0))
        energy = float(s.get("energy", 1))
        power = float(s.get("power", 0))
        failures = int(s.get("consecutive_failures", 0))
        events_n = int(s.get("events", 0))
        budget = int(s.get("budget", 0))
        goal = str(s.get("goal", "")) or "REACTOR MODE"
        plan: list[dict[str, Any]] = s.get("plan", [])
        completed: list[str] = s.get("completed", [])
        done_when = str(s.get("done_when", ""))
        wing = bool(s.get("wing_crossed", False))

        out: list[str] = []

        # Title bar
        budget_pct = events_n / max(budget, 1)
        outcome = self._outcome()
        power_str = f"{_fg(255,180,80)}⚡{power:.3f}/s{RST}" if power > 0 else ""
        title = f" {BOLD}{goal[:w-45]}{RST} {DIM}│{RST} {_fg(180,180,220)}{events_n}/{budget}{RST} {power_str} {outcome}"
        out.append(title)
        out.append(" " + _hbar(budget_pct, w - 3, _fg(80, 180, 255) if budget_pct < 0.7 else _fg(255, 140, 60)))
        out.append("")

        # Layout: reactor (left) | events + plan (right)
        reactor_w = 22
        right_w = max(30, w - reactor_w - 4)
        body_h = max(10, h - 8)

        reactor_lines = self._render_reactor(reactor_w, body_h, stag, pid, energy, power, wing, len(completed))
        right_lines = self._render_right(right_w, body_h, plan, done_when, completed)

        for i in range(body_h):
            left = reactor_lines[i] if i < len(reactor_lines) else " " * reactor_w
            right = right_lines[i] if i < len(right_lines) else ""
            out.append(f" {left} {DIM}│{RST} {right}")

        # Bottom: agent toggles
        out.append("")
        agents_str = ""
        for i, name in enumerate(ALL_AGENTS):
            is_off = name in self.disabled
            if i == self.agent_cursor:
                if is_off:
                    agents_str += f" \x1b[7m\x1b[31m {name} \x1b[0m"
                else:
                    agents_str += f" \x1b[7m\x1b[32m {name} \x1b[0m"
            elif is_off:
                agents_str += f" {_fg(80, 80, 80)}{name}{RST}"
            else:
                agents_str += f" {_fg(100, 200, 100)}{name}{RST}"
        launch_label = "launch" if self.paused else "relaunch"
        out.append(f"{agents_str}")
        out.append(f" {DIM}↑↓ select  Enter toggle  Space {launch_label}  q quit{RST}")

        return "\n".join(out[:h])

    def _render_reactor(self, w: int, h: int, stag: float, pid: float, energy: float, power: float, wing: bool, completions: int) -> list[str]:
        lines: list[str] = []
        flashing = (time.time() - self.fission_flash) < 1.5

        # Reactor core ASCII
        core_color = _fg(255, 60, 60) if flashing else (_fg(255, 180, 50) if stag > 0.5 else _fg(60, 200, 180))
        rod_color = _fg(100, 150, 255) if pid > 1.0 else _fg(60, 80, 120)

        # Control rod depth (higher PID = rods inserted deeper)
        rod_depth = min(int(pid / 3.0 * 6), 6)

        lines.append(f"{DIM}╭{'─' * (w-2)}╮{RST}")
        lines.append(f"{DIM}│{RST}{_fg(180,180,220)} REACTOR CORE    {RST}{DIM}│{RST}")
        lines.append(f"{DIM}│{'─' * (w-2)}│{RST}")

        # Control rods (top section)
        for i in range(3):
            if i < rod_depth:
                lines.append(f"{DIM}│{RST} {rod_color}║║║║║║║║║║║║║║║║║║{RST}{DIM}│{RST}")
            else:
                lines.append(f"{DIM}│{RST}                    {DIM}│{RST}")

        # Core glow zone
        glow_h = max(4, h - 18)
        fuel_level = min(energy / 2.5, 1.0)
        fuel_filled = int(fuel_level * glow_h)

        for row in range(glow_h):
            level = glow_h - 1 - row
            if level < fuel_filled:
                t = level / max(glow_h - 1, 1)
                if flashing:
                    r, g, b = 255, 255, int(200 * (1 - t))
                elif stag > 0.7:
                    r, g, b = int(200 + 55*t), int(80 - 40*t), int(30)
                else:
                    r, g, b = int(40 + 60*t), int(180 + 75*t), int(220 - 80*t)
                bar = "█" * 18
                lines.append(f"{DIM}│{RST} {_fg(r,g,b)}{bar}{RST}{DIM}│{RST}")
            else:
                lines.append(f"{DIM}│                    │{RST}")

        lines.append(f"{DIM}│{'─' * (w-2)}│{RST}")

        # Gauges
        stag_icon = "🔥" if stag > 0.7 else ("◌" if stag < 0.1 else "●")
        pid_icon = "▼" if pid > 1.0 else "△"
        fission_icon = "★" if flashing else "☆"
        wing_icon = f"{_fg(255,255,0)}⚡{RST}" if wing else " "

        lines.append(f"{DIM}│{RST} {_fg(255,120,80)}stag{RST} {stag:.2f} {stag_icon}       {DIM}│{RST}")
        lines.append(f"{DIM}│{RST} {_fg(100,150,255)}pid {RST} {pid:.2f} {pid_icon}       {DIM}│{RST}")
        lines.append(f"{DIM}│{RST} {_fg(180,120,255)}nrg {RST} {energy:.2f}         {DIM}│{RST}")
        lines.append(f"{DIM}│{RST} {_fg(255,220,80)}pow {RST} {power:.4f} {fission_icon}   {wing_icon} {DIM}│{RST}")
        lines.append(f"{DIM}│{RST} {_fg(80,255,180)}done{RST} {completions}             {DIM}│{RST}")
        lines.append(f"{DIM}╰{'─' * (w-2)}╯{RST}")

        # Pad to height
        while len(lines) < h:
            lines.append(" " * w)

        return lines[:h]

    def _render_right(self, w: int, h: int, plan: list[dict[str, Any]], done_when: str, completed: list[str]) -> list[str]:
        lines: list[str] = []

        # Plan section
        if plan:
            done_count = sum(1 for step in plan if step.get("status") == "done")
            total = len(plan)
            pbar = _hbar(done_count / max(total, 1), min(20, w - 15), _fg(80, 200, 120))
            lines.append(f"{_fg(100,220,140)}PLAN{RST} [{done_count}/{total}] {pbar}")
            if done_when:
                lines.append(f" {DIM}done_when: {done_when[:w-12]}{RST}")
            for step in plan:
                status = step.get("status", "pending")
                text = step.get("text", "")[:w - 6]
                if status == "done":
                    lines.append(f"  {_fg(80,200,80)}✓{RST} {DIM}{text}{RST}")
                elif status == "active":
                    lines.append(f"  {_fg(255,220,80)}▶{RST} {text}")
                else:
                    lines.append(f"  {DIM}○ {text}{RST}")
        else:
            lines.append(f"{DIM}PLAN (none){RST}")

        lines.append("")

        # Completed chain
        if completed:
            lines.append(f"{_fg(255,180,80)}FISSIONS{RST} ({len(completed)})")
            for c in completed[-3:]:
                lines.append(f"  {_fg(80,255,180)}★{RST} {c[:w-5]}")
            lines.append("")

        # Event feed - fill remaining space
        lines.append(f"{_fg(180,180,220)}EVENTS{RST}")
        feed_h = h - len(lines) - 1
        feed_lines = self._render_events(w, feed_h)
        lines.extend(feed_lines)

        while len(lines) < h:
            lines.append("")

        return lines[:h]

    def _render_events(self, w: int, h: int) -> list[str]:
        lines: list[str] = []
        if not self.events:
            lines.append(f"{DIM}waiting for events...{RST}")
            return lines
        # Filter: skip math noise for readability
        interesting = [e for e in self.events if e.get("phase") not in ("stagnation", "lorenz", "pid")]
        if not interesting:
            interesting = self.events
        start = max(0, len(interesting) - max(h, 1))
        for e in interesting[start:]:
            n = e.get("n", 0)
            phase = e.get("phase", "?")
            d = e.get("d", {})
            detail = self._fmt(phase, d, w - 15)
            color = self._phase_color(phase)
            lines.append(f"{DIM}{n:3}{RST} {color}{phase:8}{RST} {detail}")
        return lines[:h]

    def _fmt(self, phase: str, d: dict[str, Any], max_w: int) -> str:
        match phase:
            case "start":
                return str(d.get("goal", "") or "REACTOR MODE")[:max_w]
            case "observe":
                return f"[{d.get('focused', '')}]"[:max_w]
            case "schedule":
                reason = d.get("reason", "")
                step = d.get("step", "")
                if step:
                    return f"→{reason} {step}"[:max_w]
                return f"→{reason}"[:max_w]
            case "plan":
                dw = d.get("done_when", "")
                return f"{d.get('mode','')} {d.get('steps','')}steps \"{dw[:max_w-20]}\""[:max_w]
            case "action":
                ok = "✓" if d.get("ok") else "✗"
                dr = "ᴰ" if d.get("direct") else ""
                return f"{ok}{dr} {d.get('verb','')} {d.get('obs','')}  "[:max_w]
            case "actor":
                return f"{d.get('conclusion','')} {d.get('verb','')}"[:max_w]
            case "verify":
                v = "✓" if d.get("verdict") == "confirmed" else "✗"
                return f"{v} {d.get('evidence', '')}"[:max_w]
            case "fission":
                return f"★ power={d.get('power',0):.4f} completions={d.get('completions','')}"[:max_w]
            case "fission_sustain":
                return f"→ chain continues (power={d.get('power',0):.4f})"[:max_w]
            case "reflect":
                return str(d.get("diagnosis", ""))[:max_w]
            case "mutation":
                return f"mutate {d.get('target','')}: {d.get('appended','')}"[:max_w]
            case "complete":
                return f"✓ GOAL ACHIEVED in {d.get('events', '?')} events"[:max_w]
            case "stop":
                return f"{d.get('reason', '')} at {d.get('events', '?')}"[:max_w]
            case _:
                return str(d)[:max_w]

    def _phase_color(self, phase: str) -> str:
        match phase:
            case "schedule":
                return _fg(140, 140, 180)
            case "observe":
                return _fg(100, 180, 220)
            case "plan":
                return _fg(100, 220, 140)
            case "actor" | "action":
                return _fg(220, 180, 80)
            case "verify":
                return _fg(80, 220, 220)
            case "fission" | "fission_sustain":
                return _fg(255, 80, 255)
            case "reflect":
                return _fg(220, 140, 180)
            case "mutation":
                return _fg(255, 220, 80)
            case "complete":
                return _fg(80, 255, 80)
            case "stop":
                return _fg(255, 80, 80)
            case _:
                return DIM

    def _outcome(self) -> str:
        if self.paused and not self.events:
            return f"{_fg(255, 180, 80)}▌▌ READY{RST}"
        phases = [e.get("phase") for e in self.events]
        if "complete" in phases:
            return f"{_fg(80, 255, 80)}✓ COMPLETE{RST}"
        if "stop" in phases:
            return f"{_fg(255, 180, 80)}■ STOPPED{RST}"
        if self.proc is not None:
            return f"{_fg(100, 200, 255)}▶ RUNNING{RST}"
        if self.events:
            return f"{_fg(100, 200, 255)}… DONE{RST}"
        return f"{DIM}waiting{RST}"


def run_tui(path: Path | None = None, goal: str = "", backend: str = "lmstudio", budget: int = 20) -> None:
    events_path = path or EVENTS_PATH
    tui = TUI(events_path, SNAPSHOT_PATH, goal=goal, backend=backend, budget=budget)
    _write(TUI_ALT_SCREEN_ON + TUI_HIDE_CURSOR)
    try:
        while tui.running:
            tui.load()
            tui.handle_key()
            tui.check_proc()
            frame = tui.render()
            _write(TUI_HOME_CLEAR + frame)
            time.sleep(0.15)
    except KeyboardInterrupt:
        pass
    finally:
        if tui.proc is not None:
            tui.proc.terminate()
        _write(TUI_ALT_SCREEN_OFF + TUI_SHOW_CURSOR)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(prog="endgame-ai-tui")
    parser.add_argument("goal", nargs="?", default="")
    parser.add_argument("--backend", choices=["lmstudio", "acp"], default="lmstudio")
    parser.add_argument("--event-budget", type=int, default=20)
    parser.add_argument("--events", type=str, default="")
    args = parser.parse_args()
    ep = Path(args.events) if args.events else None
    run_tui(path=ep, goal=args.goal, backend=args.backend, budget=args.event_budget)
