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
    EVENTS_PATH, SNAPSHOT_PATH, DISABLED_PATH, PID_ROD_SCALE,
)

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_stdout_handle = _kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
ENABLE_VIRTUAL_TERMINAL: int = 0x0004
_mode = ctypes.c_ulong()
_kernel32.GetConsoleMode(_stdout_handle, ctypes.byref(_mode))
_kernel32.SetConsoleMode(_stdout_handle, _mode.value | ENABLE_VIRTUAL_TERMINAL)

ALL_AGENTS: list[str] = ["stagnation", "lorenz", "pid", "scheduler", "observer", "planner", "actor", "verifier", "reflector"]

PLOT_W: int = 36
PLOT_H: int = 12
LORENZ_HISTORY: int = 200
REACTOR_W: int = 24

_BRAILLE_MAP: list[tuple[int, int, int]] = [
    (0, 0, 0x01), (1, 0, 0x02), (2, 0, 0x04), (3, 0, 0x40),
    (0, 1, 0x08), (1, 1, 0x10), (2, 1, 0x20), (3, 1, 0x80),
]

RST: str = "\x1b[0m"
DIM: str = "\x1b[2m"
BOLD: str = "\x1b[1m"


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


def _hbar(value: float, width: int, color: str) -> str:
    filled = int(value * width)
    filled = max(0, min(width, filled))
    return color + "━" * filled + DIM + "╌" * (width - filled) + RST


def _lerp_color(t: float) -> str:
    t = max(0.0, min(1.0, t))
    return _fg(int(40 + t * 215), int(180 - t * 140), int(220 - t * 180))


def _braille_plot(xs: list[float], ys: list[float], w: int, h: int, stag: float) -> list[str]:
    if len(xs) < 2:
        return [DIM + "·" * w + RST] * h
    x_min, x_max = min(xs), max(xs)
    y_min, y_max = min(ys), max(ys)
    x_range = max(x_max - x_min, 0.1)
    y_range = max(y_max - y_min, 0.1)
    pw, ph = w * 2, h * 4
    grid: list[list[bool]] = [[False] * pw for _ in range(ph)]
    for i in range(len(xs)):
        px = int((xs[i] - x_min) / x_range * (pw - 1))
        py = int((1.0 - (ys[i] - y_min) / y_range) * (ph - 1))
        px = max(0, min(pw - 1, px))
        py = max(0, min(ph - 1, py))
        grid[py][px] = True
    color = _lerp_color(stag)
    lines: list[str] = []
    for row in range(h):
        chars: list[str] = []
        for col in range(w):
            byte = 0
            for dy, dx, bit in _BRAILLE_MAP:
                gy, gx = row * 4 + dy, col * 2 + dx
                if gy < ph and gx < pw and grid[gy][gx]:
                    byte |= bit
            chars.append(chr(0x2800 + byte))
        lines.append(color + "".join(chars) + RST)
    return lines


def _clip(text: str, width: int) -> str:
    if width <= 0:
        return ""
    return text if len(text) <= width else text[: max(0, width - 1)] + "…"


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
        self.focused_window: str = ""

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
                    for e in reversed(self.events):
                        if e.get("phase") == "observe":
                            self.focused_window = str(e.get("d", {}).get("focused", ""))
                            break
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
        from config import BASE_DIR, GUI_MODE_PATH
        if self.proc is not None:
            return
        if not self.goal:
            return
        for p in (self.events_path, self.snapshot_path, DISABLED_PATH, GUI_MODE_PATH):
            if p.exists():
                p.unlink()
        self.events = []
        self.last_file_size = 0
        self.paused = False
        self.proc = subprocess.Popen(
            [sys.executable, "main.py", self.goal, "--backend", self.backend, "--event-budget", str(self.budget)],
            cwd=str(BASE_DIR),
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def check_proc(self) -> None:
        if self.proc is not None and self.proc.poll() is not None:
            self.proc = None

    def _math_from_events(self) -> dict[str, Any]:
        stag_hist: list[float] = []
        pid_hist: list[float] = []
        lorenz_xs: list[float] = []
        lorenz_ys: list[float] = []
        wing = False
        for e in self.events:
            phase = str(e.get("phase", ""))
            d: dict[str, Any] = e.get("d", {})
            if phase == "stagnation":
                stag_hist.append(float(d.get("stag", 0)))
            elif phase == "pid":
                pid_hist.append(float(d.get("pid", 0)))
            elif phase == "lorenz":
                lorenz_xs.append(float(d.get("x", 0)))
                lorenz_ys.append(float(d.get("y", d.get("energy", 0))))
                wing = bool(d.get("wing", False))
        if len(lorenz_xs) > LORENZ_HISTORY:
            lorenz_xs = lorenz_xs[-LORENZ_HISTORY:]
            lorenz_ys = lorenz_ys[-LORENZ_HISTORY:]
        s = self.snapshot
        return {
            "stag": stag_hist[-1] if stag_hist else float(s.get("stagnation", 0)),
            "pid": pid_hist[-1] if pid_hist else float(s.get("pid_output", 0)),
            "energy": float(s.get("energy", 1)),
            "stag_hist": stag_hist[-20:],
            "pid_hist": pid_hist[-20:],
            "lorenz_xs": lorenz_xs,
            "lorenz_ys": lorenz_ys,
            "wing": wing or bool(s.get("wing_crossed", False)),
            "lorenz_x": float(s.get("lorenz_x", 0)),
            "lorenz_y": float(s.get("lorenz_y", 0)),
            "lorenz_z": float(s.get("lorenz_z", 0)),
        }

    def render(self) -> str:
        w, h = _size()
        s = self.snapshot
        math = self._math_from_events()
        stag = float(math["stag"])
        pid = float(math["pid"])
        energy = float(math["energy"])
        power = float(s.get("power", 0))
        events_n = int(s.get("events", len(self.events)))
        work_n = int(s.get("work_events", 0))
        budget = int(s.get("budget", self.budget))
        failures = int(s.get("consecutive_failures", 0))
        pid_integral = float(s.get("pid_integral", 0))
        goal = str(s.get("goal", "")) or self.goal or "REACTOR MODE"
        plan: list[dict[str, Any]] = s.get("plan", [])
        completed: list[str] = s.get("completed", [])
        done_when = str(s.get("done_when", ""))
        wing = bool(math["wing"])
        focused = self.focused_window or str(s.get("focused_window", ""))

        out: list[str] = []
        work_pct = work_n / max(budget, 1)
        outcome = self._outcome()
        power_str = f"{_fg(255,180,80)}power={power:.4f}/s{RST}" if power > 0 else ""
        title = f" {BOLD}{_clip(goal, w - 50)}{RST} {DIM}│{RST} {_fg(180,180,220)}work {work_n}/{budget}{RST} {DIM}events {events_n}{RST} {power_str} {outcome}"
        out.append(title)
        out.append(" " + _hbar(work_pct, w - 3, _fg(80, 180, 255) if work_pct < 0.7 else _fg(255, 140, 60)))

        fields = (
            f"{DIM}stagnation{RST}={stag:.2f}  "
            f"{DIM}pid_output{RST}={pid:.2f}  "
            f"{DIM}pid_integral{RST}={pid_integral:.2f}  "
            f"{DIM}energy{RST}={energy:.2f}  "
            f"{DIM}failures{RST}={failures}"
        )
        out.append(" " + _clip(fields, w - 1))
        lorenz_line = (
            f"{DIM}lorenz_x{RST}={math['lorenz_x']:+.2f}  "
            f"{DIM}lorenz_y{RST}={math['lorenz_y']:+.2f}  "
            f"{DIM}lorenz_z{RST}={math['lorenz_z']:.2f}  "
            f"{DIM}wing_crossed{RST}={'yes' if wing else 'no'}"
        )
        out.append(" " + _clip(lorenz_line, w - 1))
        if focused:
            out.append(f" {DIM}focused_window{RST}: {_clip(focused, w - 18)}")
        if done_when:
            out.append(f" {DIM}done_when{RST}: {_clip(done_when, w - 14)}")
        out.append("")

        body_h = max(12, h - len(out) - 4)
        reactor_w = min(REACTOR_W, max(20, w // 5))
        plot_w = min(PLOT_W, max(24, w // 4))
        right_w = max(32, w - reactor_w - plot_w - 6)

        reactor_lines = self._render_reactor(reactor_w, body_h, stag, pid, energy, power, wing, len(completed))
        chaos_lines = self._render_chaos(plot_w, body_h, math["lorenz_xs"], math["lorenz_ys"], stag, math)
        right_lines = self._render_right(right_w, body_h, plan, done_when, completed)

        for i in range(body_h):
            left = reactor_lines[i] if i < len(reactor_lines) else " " * reactor_w
            mid = chaos_lines[i] if i < len(chaos_lines) else " " * plot_w
            right = right_lines[i] if i < len(right_lines) else ""
            out.append(f" {left} {DIM}│{RST} {mid} {DIM}│{RST} {right}")

        agents_str = ""
        for i, name in enumerate(ALL_AGENTS):
            is_off = name in self.disabled
            if i == self.agent_cursor:
                agents_str += f" \x1b[7m\x1b[{31 if is_off else 32}m {name} \x1b[0m"
            elif is_off:
                agents_str += f" {_fg(80, 80, 80)}{name}{RST}"
            else:
                agents_str += f" {_fg(100, 200, 100)}{name}{RST}"
        launch_label = "launch" if self.paused else "relaunch"
        out.append(f"{agents_str}")
        out.append(f" {DIM}↑↓ select  Enter toggle  Space {launch_label}  q quit  backend={self.backend}{RST}")
        return "\n".join(out[:h])

    def _render_reactor(self, w: int, h: int, stag: float, pid: float, energy: float, power: float, wing: bool, completions: int) -> list[str]:
        lines: list[str] = []
        flashing = (time.time() - self.fission_flash) < 1.5
        tick = int(time.time() * 2) % 4
        lines.append(f"{DIM}╭{'─' * (w - 2)}╮{RST}")
        lines.append(f"{DIM}│{RST}{_fg(180,180,220)} REACTOR CORE {RST}{DIM}│{RST}")
        lines.append(f"{DIM}├{'─' * (w - 2)}┤{RST}")
        core_h = max(5, h - 13)
        rod_pct = min(pid / PID_ROD_SCALE, 1.0)
        rod_rows = int(rod_pct * core_h)
        fuel_rows = max(1, core_h - rod_rows)
        inner = w - 4
        for row in range(core_h):
            if row < rod_rows:
                rod_color = _fg(80, 130, 220) if pid < 2.0 else _fg(60, 100, 255)
                rod_char = "┃" if (row + tick) % 2 == 0 else "│"
                n_rods = max(4, inner // 3)
                rods = (" " + rod_char + " ") * n_rods
                lines.append(f"{DIM}│{RST}{rod_color}{_clip(rods, inner)}{RST}{DIM}│{RST}")
            else:
                t = (row - rod_rows) / max(fuel_rows - 1, 1)
                if flashing:
                    r, g, b = 255, int(255 - 80 * t), int(100 + 100 * t)
                elif stag > 0.7:
                    r, g, b = int(220 + 35 * t), int(60 + 20 * t), 20
                elif stag > 0.3:
                    r, g, b = int(180 + 40 * t), int(140 - 40 * t), int(40 + 20 * t)
                else:
                    r, g, b = int(30 + 40 * t), int(160 + 60 * t), int(200 - 40 * t)
                chars = "░▒▓█"
                ci = min(3, int(min(energy / 2.5, 1.0) * 3 + (0.5 if (row + tick) % 3 == 0 else 0)))
                bar = chars[ci] * inner
                lines.append(f"{DIM}│{RST} {_fg(r, g, b)}{bar}{RST}{DIM}│{RST}")
        lines.append(f"{DIM}├{'─' * (w - 2)}┤{RST}")
        s_bar = "━" * int(stag * 10) + "╌" * (10 - int(stag * 10))
        p_bar = "━" * int(rod_pct * 10) + "╌" * (10 - int(rod_pct * 10))
        stag_c = _fg(255, 80, 60) if stag > 0.5 else _fg(100, 200, 150)
        pid_c = _fg(80, 130, 255) if pid < 2.0 else _fg(255, 80, 80)
        lines.append(f"{DIM}│{RST} {stag_c}stagnation{RST} {stag_c}{s_bar}{RST} {stag:.2f}{DIM}│{RST}")
        lines.append(f"{DIM}│{RST} {pid_c}pid_output{RST} {pid_c}{p_bar}{RST} {pid:.2f}{DIM}│{RST}")
        nrg_c = _fg(180, 120, 255)
        wing_icon = f" {_fg(255,200,0)}wing{RST}" if wing else ""
        lines.append(f"{DIM}│{RST} {nrg_c}energy{RST} {energy:.2f}{wing_icon}{' ' * max(0, w - 22)}{DIM}│{RST}")
        pow_c = _fg(255, 220, 80) if power > 0 else DIM
        fission_icon = f"{_fg(255,255,0)}★{RST}" if flashing else "☆"
        lines.append(f"{DIM}│{RST} {pow_c}power{RST} {power:.4f}/s {fission_icon}{DIM}│{RST}")
        done_c = _fg(80, 255, 180) if completions > 0 else DIM
        lines.append(f"{DIM}│{RST} {done_c}completed{RST} {completions}{DIM}│{RST}")
        lines.append(f"{DIM}╰{'─' * (w - 2)}╯{RST}")
        while len(lines) < h:
            lines.append(" " * w)
        return lines[:h]

    def _render_chaos(self, w: int, h: int, xs: list[float], ys: list[float], stag: float, math: dict[str, Any]) -> list[str]:
        lines: list[str] = []
        pts = len(xs)
        wing_hint = f" {_fg(255,200,0)}wing{RST}" if math.get("wing") else ""
        label = f"{_fg(180,120,255)}LORENZ x×y{RST} {DIM}n={pts}{RST}{wing_hint}"
        lines.append(_clip(label, w))
        plot_h = max(1, h - 2)
        lines.extend(_braille_plot(xs, ys, w, plot_h, stag))
        if pts >= 2:
            footer = f"{DIM}x={xs[-1]:+.1f} y={ys[-1]:+.1f} E={math['energy']:.2f}{RST}"
            lines.append(_clip(footer, w))
        while len(lines) < h:
            lines.append(" " * w)
        return lines[:h]

    def _render_right(self, w: int, h: int, plan: list[dict[str, Any]], done_when: str, completed: list[str]) -> list[str]:
        lines: list[str] = []
        if plan:
            done_count = sum(1 for step in plan if step.get("status") == "done")
            total = len(plan)
            pbar = _hbar(done_count / max(total, 1), min(24, w - 12), _fg(80, 200, 120))
            lines.append(f"{_fg(100,220,140)}plan{RST} [{done_count}/{total}] {pbar}")
            for step in plan:
                status = step.get("status", "pending")
                text = str(step.get("text", ""))
                prefix = "  "
                if status == "done":
                    line = f"{prefix}{_fg(80,200,80)}✓{RST} {DIM}{_clip(text, w - 4)}{RST}"
                elif status == "active":
                    line = f"{prefix}{_fg(255,220,80)}▶{RST} {_clip(text, w - 4)}"
                else:
                    line = f"{prefix}{DIM}○ {_clip(text, w - 6)}{RST}"
                lines.append(line)
        else:
            lines.append(f"{DIM}plan (none){RST}")
        lines.append("")
        if completed:
            lines.append(f"{_fg(255,180,80)}completed{RST} ({len(completed)})")
            for c in completed[-4:]:
                lines.append(f"  {_fg(80,255,180)}★{RST} {_clip(c, w - 4)}")
            lines.append("")
        lines.append(f"{_fg(180,180,220)}events{RST}")
        feed_h = max(1, h - len(lines))
        lines.extend(self._render_events(w, feed_h))
        while len(lines) < h:
            lines.append("")
        return lines[:h]

    def _render_events(self, w: int, h: int) -> list[str]:
        if not self.events:
            return [f"{DIM}waiting for events…{RST}"]
        math_phases = {"stagnation", "lorenz", "pid"}
        interesting = [e for e in self.events if e.get("phase") not in math_phases]
        tail = interesting[-h:] if interesting else self.events[-h:]
        lines: list[str] = []
        for e in tail:
            n = e.get("n", 0)
            phase = str(e.get("phase", "?"))
            detail = self._fmt(phase, e.get("d", {}), w - 14)
            color = self._phase_color(phase)
            lines.append(f"{DIM}{n:>4}{RST} {color}{phase:10}{RST} {detail}")
        return lines[:h]

    def _fmt(self, phase: str, d: dict[str, Any], max_w: int) -> str:
        match phase:
            case "start":
                return _clip(str(d.get("goal", "") or "REACTOR MODE"), max_w)
            case "observe":
                return _clip(f"focused={d.get('focused', '')} chars={d.get('chars', 0)}", max_w)
            case "schedule":
                step = d.get("step", "")
                return _clip(f"reason={d.get('reason', '')}" + (f" step={step}" if step else ""), max_w)
            case "plan":
                return _clip(f"mode={d.get('mode', '')} steps={d.get('steps', '')} done_when={d.get('done_when', '')}", max_w)
            case "action":
                ok = "ok" if d.get("ok") else "FAIL"
                dr = " direct" if d.get("direct") else ""
                return _clip(f"{ok}{dr} verb={d.get('verb', '')} obs={d.get('obs', '')}", max_w)
            case "actor":
                return _clip(f"conclusion={d.get('conclusion', '')} ok={d.get('ok', '')} {d.get('error', d.get('note', ''))}", max_w)
            case "verify":
                return _clip(f"verdict={d.get('verdict', '')} evidence={d.get('evidence', '')}", max_w)
            case "fission":
                return _clip(f"power={d.get('power', 0):.4f} completions={d.get('completions', '')}", max_w)
            case "fission_blocked":
                return _clip(f"reason={d.get('reason', '')} done_when={d.get('done_when', '')}", max_w)
            case "stagnation":
                return _clip(f"stag={d.get('stag', 0)} progress={d.get('progress', 0)} wait={d.get('wait', False)}", max_w)
            case "pid":
                return _clip(f"pid_output={d.get('pid', 0)}", max_w)
            case "lorenz":
                return _clip(f"x={d.get('x', 0)} y={d.get('y', d.get('energy', 0))} energy={d.get('energy', 0)} wing={d.get('wing', False)}", max_w)
            case "reflect":
                return _clip(f"diagnosis={d.get('diagnosis', '')}", max_w)
            case "mutation":
                return _clip(f"target={d.get('target', '')} appended={d.get('appended', '')}", max_w)
            case "stop":
                return _clip(f"reason={d.get('reason', '')} events={d.get('events', '')} work={d.get('work', '')}", max_w)
            case _:
                return _clip(str(d), max_w)

    def _phase_color(self, phase: str) -> str:
        match phase:
            case "schedule": return _fg(140, 140, 180)
            case "observe": return _fg(100, 180, 220)
            case "plan": return _fg(100, 220, 140)
            case "actor" | "action": return _fg(220, 180, 80)
            case "verify": return _fg(80, 220, 220)
            case "fission" | "fission_sustain": return _fg(255, 80, 255)
            case "fission_blocked": return _fg(255, 120, 60)
            case "stagnation" | "pid" | "lorenz": return _fg(100, 160, 220)
            case "reflect" | "mutation": return _fg(220, 140, 180)
            case "stop": return _fg(255, 80, 80)
            case _: return DIM

    def _outcome(self) -> str:
        if self.paused and not self.events:
            return f"{_fg(255, 180, 80)}▌▌ READY{RST}"
        if self.proc is not None:
            return f"{_fg(100, 200, 255)}▶ RUNNING{RST}"
        for e in reversed(self.events):
            if e.get("phase") == "stop":
                d = e.get("d", {})
                return f"{_fg(255, 180, 80)}■ {str(d.get('reason', 'stopped')).upper()}{RST}"
        if self.events:
            return f"{_fg(140, 180, 220)}● {self.events[-1].get('phase', '')}{RST}"
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
            _write(TUI_HOME_CLEAR + tui.render())
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
    run_tui(path=Path(args.events) if args.events else None, goal=args.goal, backend=args.backend, budget=args.event_budget)