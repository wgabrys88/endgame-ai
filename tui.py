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

ALL_AGENTS: list[str] = ["observer", "pulse", "planner", "actor", "verifier", "reflector"]

PLOT_W: int = 40
PLOT_H: int = 14
LORENZ_HISTORY: int = 200


def _write(text: str) -> None:
    written = ctypes.c_ulong()
    _kernel32.WriteConsoleW(_stdout_handle, text, len(text), ctypes.byref(written), None)


def _size() -> tuple[int, int]:
    import struct
    buf = ctypes.create_string_buffer(22)
    _kernel32.GetConsoleScreenBufferInfo(_stdout_handle, buf)
    _, _, _, _, _, left, top, right, bottom, _, _ = struct.unpack("hhhhHhhhhhh", buf.raw)
    return right - left + 1, bottom - top + 1


def _rgb_fg(r: int, g: int, b: int) -> str:
    return f"\x1b[38;2;{r};{g};{b}m"


def _rgb_bg(r: int, g: int, b: int) -> str:
    return f"\x1b[48;2;{r};{g};{b}m"


RST: str = "\x1b[0m"
DIM: str = "\x1b[2m"
BOLD: str = "\x1b[1m"


def _lerp_color(t: float) -> str:
    t = max(0.0, min(1.0, t))
    r = int(40 + t * 215)
    g = int(180 - t * 140)
    b = int(220 - t * 180)
    return _rgb_fg(r, g, b)


def _braille_plot(xs: list[float], ys: list[float], w: int, h: int, stag: float) -> list[str]:
    if len(xs) < 2:
        return [" " * w] * h
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    x_range = max(x_max - x_min, 0.1)
    y_range = max(y_max - y_min, 0.1)
    pw = w * 2
    ph = h * 4
    grid: list[list[bool]] = [[False] * pw for _ in range(ph)]
    for i in range(len(xs)):
        px = int((xs[i] - x_min) / x_range * (pw - 1))
        py = int((1.0 - (ys[i] - y_min) / y_range) * (ph - 1))
        px = max(0, min(pw - 1, px))
        py = max(0, min(ph - 1, py))
        if 0 <= py < ph and 0 <= px < pw:
            grid[py][px] = True
    lines: list[str] = []
    color = _lerp_color(stag)
    for row in range(h):
        chars: list[str] = []
        for col in range(w):
            byte = 0
            for dy, dx, bit in _BRAILLE_MAP:
                gy = row * 4 + dy
                gx = col * 2 + dx
                if gy < ph and gx < pw and grid[gy][gx]:
                    byte |= bit
            chars.append(chr(0x2800 + byte))
        lines.append(color + "".join(chars) + RST)
    return lines


_BRAILLE_MAP: list[tuple[int, int, int]] = [
    (0, 0, 0x01), (1, 0, 0x02), (2, 0, 0x04), (3, 0, 0x40),
    (0, 1, 0x08), (1, 1, 0x10), (2, 1, 0x20), (3, 1, 0x80),
]


def _bar(value: float, width: int, color: str) -> str:
    filled = int(value * width)
    filled = max(0, min(width, filled))
    return color + "━" * filled + DIM + "╌" * (width - filled) + RST


class TUI:
    def __init__(self, events_path: Path, snapshot_path: Path) -> None:
        self.events_path = events_path
        self.snapshot_path = snapshot_path
        self.events: list[dict[str, Any]] = []
        self.snapshot: dict[str, Any] = {}
        self.last_file_size: int = 0
        self.running: bool = True
        self.disabled: set[str] = set()
        self.agent_cursor: int = 0
        self.lorenz_xs: list[float] = []
        self.lorenz_ys: list[float] = []

    def load(self) -> None:
        if self.events_path.exists():
            size = self.events_path.stat().st_size
            if size != self.last_file_size:
                self.last_file_size = size
                try:
                    raw = self.events_path.read_text(encoding="utf-8")
                    self.events = [json.loads(line) for line in raw.splitlines() if line.strip()]
                    self.lorenz_xs = []
                    self.lorenz_ys = []
                    for e in self.events:
                        if e.get("phase") == "pulse":
                            d = e.get("d", {})
                            self.lorenz_xs.append(float(d.get("lorenz_x", 0)))
                            self.lorenz_ys.append(float(d.get("energy", 1)))
                    if len(self.lorenz_xs) > LORENZ_HISTORY:
                        self.lorenz_xs = self.lorenz_xs[-LORENZ_HISTORY:]
                        self.lorenz_ys = self.lorenz_ys[-LORENZ_HISTORY:]
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
        elif key == b"\r" or key == b"\n":
            name = ALL_AGENTS[self.agent_cursor]
            if name in self.disabled:
                self.disabled.discard(name)
            else:
                self.disabled.add(name)
            DISABLED_PATH.write_text(json.dumps(sorted(self.disabled)), encoding="utf-8")

    def render(self) -> str:
        w, h = _size()
        s = self.snapshot
        stag = float(s.get("stagnation_score", 0))
        pid = float(s.get("pid_output", 0))
        energy = float(s.get("attractor_energy", 1))
        rep = float(s.get("repetition_score", 0))
        failures = int(s.get("consecutive_failures", 0))
        events_n = int(s.get("events", 0))
        budget = int(s.get("budget", 0))
        goal = str(s.get("goal", "(waiting)"))
        plan_steps: list[str] = s.get("plan_steps", [])
        plan_idx = int(s.get("plan_index", 0))
        wing = bool(s.get("lorenz_wing_crossed", False))
        focused = str(s.get("focused_window", ""))

        out: list[str] = []

        budget_pct = events_n / max(budget, 1)
        budget_color = _lerp_color(budget_pct)
        outcome = self._outcome()
        title = f" {BOLD}{goal[:w-30]}{RST} {DIM}│{RST} {budget_color}{events_n}/{budget}{RST} {outcome}"
        out.append(title)
        out.append(budget_color + _bar(budget_pct, w - 2, budget_color) + RST)

        plot_w = min(PLOT_W, max(10, w // 3))
        plot_h = min(PLOT_H, max(4, h - 10))
        right_w = max(20, w - plot_w - 3)

        plot_lines = _braille_plot(self.lorenz_xs, self.lorenz_ys, plot_w, plot_h, stag)

        event_lines = self._render_events(right_w, plot_h)

        for i in range(max(len(plot_lines), len(event_lines))):
            left = plot_lines[i] if i < len(plot_lines) else " " * plot_w
            right = event_lines[i] if i < len(event_lines) else ""
            out.append(f" {left} {DIM}│{RST} {right}")

        stag_bar = _bar(stag, 20, _lerp_color(stag))
        pid_bar = _bar(min(pid / 3.0, 1.0), 20, _lerp_color(min(pid / 3.0, 1.0)))
        energy_bar = _bar(min(energy / 3.0, 1.0), 20, _rgb_fg(180, 120, 255))
        wing_str = f" {_rgb_fg(255, 255, 0)}⚡ WING CROSS{RST}" if wing else ""

        out.append(f" {DIM}stag{RST} {stag_bar} {stag:.2f}  {DIM}pid{RST} {pid_bar} {pid:.2f}  {DIM}energy{RST} {energy_bar} {energy:.2f}{wing_str}")
        out.append(f" {DIM}rep={rep:.2f} fails={failures} screen_stag={s.get('screen_stagnation', 0)} halt={s.get('halt_count', 0)}{RST}  {DIM}focus: {focused[:30]}{RST}")

        plan_line = ""
        if plan_steps:
            total = len(plan_steps)
            current = plan_steps[plan_idx] if plan_idx < total else "(done)"
            done_count = min(plan_idx, total)
            plan_line = f" {DIM}plan{RST} [{done_count}/{total}] {_rgb_fg(100, 220, 180)}{current[:w-20]}{RST}"
        else:
            plan_line = f" {DIM}plan{RST} (none)"
        out.append(plan_line)

        agents_str = ""
        for i, name in enumerate(ALL_AGENTS):
            is_off = name in self.disabled
            if i == self.agent_cursor:
                if is_off:
                    agents_str += f" \x1b[7m\x1b[31m {name} \x1b[0m"
                else:
                    agents_str += f" \x1b[7m\x1b[32m {name} \x1b[0m"
            elif is_off:
                agents_str += f" {_rgb_fg(80, 80, 80)}{name}{RST}"
            else:
                agents_str += f" {_rgb_fg(100, 200, 100)}{name}{RST}"
        out.append(f"{agents_str}  {DIM}↑↓ select  Enter toggle  q quit{RST}")

        return "\n".join(out[:h])

    def _render_events(self, w: int, h: int) -> list[str]:
        lines: list[str] = []
        if not self.events:
            lines.append(f"{DIM}waiting for events...{RST}")
            return lines
        start = max(0, len(self.events) - h)
        for e in self.events[start:]:
            n = e.get("n", 0)
            phase = e.get("phase", "?")
            d = e.get("d", {})
            detail = self._fmt(phase, d, w - 18)
            color = self._phase_color(phase)
            lines.append(f"{DIM}{n:3}{RST} {color}{phase:8}{RST} {detail}")
        return lines[:h]

    def _fmt(self, phase: str, d: dict[str, Any], max_w: int) -> str:
        match phase:
            case "start":
                return str(d.get("goal", ""))[:max_w]
            case "observe":
                stag = "≡" if d.get("stagnant") else ""
                return f"{stag}[{d.get('focused', '')}] {d.get('chars', 0)}ch"[:max_w]
            case "pulse":
                w_str = "⚡" if d.get("wing") else ""
                return f"s={d.get('stag', 0):.2f} x={d.get('lorenz_x', 0):.1f} p={d.get('pid', 0):.2f} →{d.get('next', '')}{w_str}"[:max_w]
            case "plan":
                return f"{d.get('mode', '')} {d.get('action', '')}"[:max_w]
            case "actor":
                return f"{d.get('conclusion', '')} {d.get('verb', '')} ok={d.get('ok', '')}"[:max_w]
            case "action":
                ok = "✓" if d.get("ok") else "✗"
                dr = "[D]" if d.get("direct") else ""
                return f"{ok}{dr} {d.get('verb', '')} {d.get('obs', '')}"[:max_w]
            case "verify":
                v = "✓" if d.get("verdict") == "confirmed" else "✗"
                return f"{v} {d.get('evidence', '')}"[:max_w]
            case "reflect":
                return str(d.get("lesson", d.get("diagnosis", "")))[:max_w]
            case "complete":
                return f"✓ DONE in {d.get('events', '?')} events"[:max_w]
            case "halt":
                return f"HALTED stag={d.get('stagnation', 0):.2f}"[:max_w]
            case "stop":
                return f"{d.get('reason', '')} at {d.get('events', '?')}"[:max_w]
            case _:
                return str(d)[:max_w]

    def _phase_color(self, phase: str) -> str:
        match phase:
            case "pulse":
                return _rgb_fg(180, 120, 255)
            case "observe":
                return _rgb_fg(100, 180, 220)
            case "plan":
                return _rgb_fg(100, 220, 140)
            case "actor" | "action":
                return _rgb_fg(220, 180, 80)
            case "verify":
                return _rgb_fg(80, 220, 220)
            case "reflect":
                return _rgb_fg(220, 140, 180)
            case "complete":
                return _rgb_fg(80, 255, 80)
            case "halt" | "stop":
                return _rgb_fg(255, 80, 80)
            case _:
                return DIM

    def _outcome(self) -> str:
        phases = [e.get("phase") for e in self.events]
        if "complete" in phases:
            return f"{_rgb_fg(80, 255, 80)}✓ COMPLETE{RST}"
        if "halt" in phases:
            return f"{_rgb_fg(255, 80, 80)}✗ HALTED{RST}"
        if "stop" in phases:
            return f"{_rgb_fg(255, 180, 80)}■ STOPPED{RST}"
        if self.events:
            return f"{_rgb_fg(100, 200, 255)}… LIVE{RST}"
        return f"{DIM}waiting{RST}"


def run_tui(path: Path | None = None) -> None:
    events_path = path or EVENTS_PATH
    tui = TUI(events_path, SNAPSHOT_PATH)
    _write(TUI_ALT_SCREEN_ON + TUI_HIDE_CURSOR)
    try:
        while tui.running:
            tui.load()
            tui.handle_key()
            frame = tui.render()
            _write(TUI_HOME_CLEAR + frame)
            time.sleep(0.15)
    except KeyboardInterrupt:
        pass
    finally:
        _write(TUI_ALT_SCREEN_OFF + TUI_SHOW_CURSOR)


if __name__ == "__main__":
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    run_tui(p)
