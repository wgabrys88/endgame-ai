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
ENABLE_MOUSE_INPUT: int = 0x0010
_mode = ctypes.c_ulong()
_kernel32.GetConsoleMode(_stdout_handle, ctypes.byref(_mode))
_kernel32.SetConsoleMode(_stdout_handle, _mode.value | ENABLE_VIRTUAL_TERMINAL)

ALL_AGENTS: list[str] = [
    "observer", "pulse",
    "planner", "actor", "verifier", "reflector",
]


def _write(text: str) -> None:
    written = ctypes.c_ulong()
    _kernel32.WriteConsoleW(_stdout_handle, text, len(text), ctypes.byref(written), None)


def _get_terminal_size() -> tuple[int, int]:
    import struct
    h = _kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
    buf = ctypes.create_string_buffer(22)
    _kernel32.GetConsoleScreenBufferInfo(h, buf)
    _, _, _, _, _, left, top, right, bottom, _, _ = struct.unpack("hhhhHhhhhhh", buf.raw)
    return right - left + 1, bottom - top + 1


class TUI:
    def __init__(self, events_path: Path, snapshot_path: Path) -> None:
        self.events_path = events_path
        self.snapshot_path = snapshot_path
        self.events: list[dict[str, Any]] = []
        self.snapshot: dict[str, Any] = {}
        self.cursor: int = -1
        self.paused: bool = False
        self.panel: str = "agents"
        self.last_file_size: int = 0
        self.running: bool = True
        self.disabled: set[str] = set()
        self.agent_cursor: int = 0
        self._load_disabled()

    def _load_disabled(self) -> None:
        if not DISABLED_PATH.exists():
            self.disabled = set()
            return
        try:
            raw: object = json.loads(DISABLED_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                self.disabled = {str(v) for v in cast(list[Any], raw)}
        except (json.JSONDecodeError, OSError):
            pass

    def _save_disabled(self) -> None:
        DISABLED_PATH.write_text(json.dumps(sorted(self.disabled)), encoding="utf-8")

    def toggle_agent(self, name: str) -> None:
        if name in self.disabled:
            self.disabled.discard(name)
        else:
            self.disabled.add(name)
        self._save_disabled()

    def load_events(self) -> bool:
        if not self.events_path.exists():
            return False
        size = self.events_path.stat().st_size
        if size == self.last_file_size:
            return False
        self.last_file_size = size
        try:
            raw = self.events_path.read_text(encoding="utf-8")
            self.events = [json.loads(line) for line in raw.splitlines() if line.strip()]
        except (json.JSONDecodeError, OSError):
            return False
        if not self.paused:
            self.cursor = len(self.events) - 1
        return True

    def load_snapshot(self) -> None:
        if not self.snapshot_path.exists():
            return
        try:
            self.snapshot = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    def handle_key(self) -> None:
        if not msvcrt.kbhit():
            return
        key = msvcrt.getch()
        if key == b"\xe0" or key == b"\x00":
            ext = msvcrt.getch()
            if ext == b"H":
                self._nav_up()
            elif ext == b"P":
                self._nav_down()
            elif ext == b"M":
                self._step_forward()
            elif ext == b"K":
                self._step_back()
            return
        if key == b" ":
            self.paused = not self.paused
        elif key == b"q":
            self.running = False
        elif key == b"\r" or key == b"\n":
            if self.panel == "agents":
                name = ALL_AGENTS[self.agent_cursor]
                self.toggle_agent(name)
            else:
                self._step_forward()
        elif key == b"1":
            self.panel = "agents"
        elif key == b"2":
            self.panel = "events"
        elif key == b"3":
            self.panel = "math"
        elif key == b"4":
            self.panel = "plan"

    def _nav_up(self) -> None:
        if self.panel == "agents":
            self.agent_cursor = max(0, self.agent_cursor - 1)
        else:
            self._step_back()

    def _nav_down(self) -> None:
        if self.panel == "agents":
            self.agent_cursor = min(len(ALL_AGENTS) - 1, self.agent_cursor + 1)
        else:
            self._step_forward()

    def _step_forward(self) -> None:
        self.paused = True
        if self.cursor < len(self.events) - 1:
            self.cursor += 1

    def _step_back(self) -> None:
        self.paused = True
        if self.cursor > 0:
            self.cursor -= 1

    def render(self) -> str:
        w, h = _get_terminal_size()
        lines: list[str] = []

        self.load_snapshot()
        self._load_disabled()

        start_evt = next((e for e in self.events if e.get("phase") == "start"), None)
        goal = start_evt["d"]["goal"] if start_evt else "(no goal)"
        budget = start_evt["d"]["budget"] if start_evt else 0
        total = len(self.events)
        status = "\x1b[33m⏸ PAUSED\x1b[0m" if self.paused else "\x1b[32m▶ LIVE\x1b[0m"
        outcome = self._outcome()

        lines.append(f"\x1b[1m{'═' * w}\x1b[0m")
        lines.append(f" \x1b[1mendgame-ai\x1b[0m │ {goal[:w-16]} │ {outcome}")
        lines.append(f" {status} │ Events: {total}/{budget} │ Cycle: {self.cursor + 1}")
        lines.append(f"\x1b[1m{'═' * w}\x1b[0m")

        panel_h = h - 8
        if self.panel == "agents":
            lines += self._render_agents(w, panel_h)
        elif self.panel == "events":
            lines += self._render_events(w, panel_h)
        elif self.panel == "math":
            lines += self._render_math(w, panel_h)
        elif self.panel == "plan":
            lines += self._render_plan(w, panel_h)

        lines.append(f"{'─' * w}")
        tab_1 = "\x1b[7m 1:Agents \x1b[0m" if self.panel == "agents" else " 1:Agents "
        tab_2 = "\x1b[7m 2:Events \x1b[0m" if self.panel == "events" else " 2:Events "
        tab_3 = "\x1b[7m 3:Math \x1b[0m" if self.panel == "math" else " 3:Math "
        tab_4 = "\x1b[7m 4:Plan \x1b[0m" if self.panel == "plan" else " 4:Plan "
        lines.append(f" {tab_1}│{tab_2}│{tab_3}│{tab_4}│ [space]=pause [q]=quit [Enter]=toggle")
        lines.append(f"\x1b[1m{'═' * w}\x1b[0m")

        return "\n".join(lines[:h])

    def _render_agents(self, w: int, max_h: int) -> list[str]:
        lines: list[str] = []
        lines.append(f" {'─' * (w-2)}")
        lines.append(f"  AGENT              │ STATUS  │ LAST EVENT")
        lines.append(f" {'─' * (w-2)}")

        last_phases: dict[str, str] = {}
        for e in self.events[-50:]:
            phase = str(e.get("phase", ""))
            if phase == "observe":
                last_phases["observer"] = phase
            elif phase == "pulse":
                last_phases["pulse"] = phase
            elif phase == "plan":
                last_phases["planner"] = phase
            elif phase in ("actor", "action"):
                last_phases["actor"] = phase
            elif phase == "verify":
                last_phases["verifier"] = phase
            elif phase == "reflect":
                last_phases["reflector"] = phase

        for i, name in enumerate(ALL_AGENTS):
            is_disabled = name in self.disabled
            cursor_mark = "►" if i == self.agent_cursor else " "

            if is_disabled:
                status_str = "\x1b[31m■ OFF \x1b[0m"
            elif name in ("observer", "pulse"):
                status_str = "\x1b[32m♥ PULSE\x1b[0m"
            else:
                status_str = "\x1b[36m◆ READY\x1b[0m"

            last_event = last_phases.get(name, "—")
            agent_type = "math" if name == "pulse" else ("sys" if name == "observer" else "llm")

            line = f" {cursor_mark} [{agent_type:4}] {name:12} │ {status_str} │ {last_event}"
            if i == self.agent_cursor:
                line = f"\x1b[44m{line}\x1b[0m"
            lines.append(line)

        lines.append(f" {'─' * (w-2)}")
        lines.append(f"  ↑↓ navigate │ Enter = toggle agent on/off")

        s = self.snapshot
        lines.append(f" {'─' * (w-2)}")
        lines.append(f"  BLACKBOARD SNAPSHOT:")
        lines.append(f"    stagnation={s.get('stagnation_score', 0):.3f} │ pid={s.get('pid_output', 0):.3f} │ lorenz_x={s.get('lorenz_x', 0):.2f}")
        lines.append(f"    failures={s.get('consecutive_failures', 0)} │ events={s.get('events', 0)}/{s.get('budget', 0)}")
        jac = s.get("jacobian", {})
        if jac:
            top = sorted(jac.items(), key=lambda x: -x[1])[:4]
            lines.append(f"    jacobian: {', '.join(f'{k}={v:.2f}' for k,v in top)}")

        remaining = max_h - len(lines)
        for _ in range(remaining):
            lines.append("")
        return lines[:max_h]

    def _render_events(self, w: int, max_h: int) -> list[str]:
        lines: list[str] = []
        if not self.events:
            lines.append("  (waiting for events...)")
            return lines

        visible_count = min(max_h - 1, len(self.events))
        start_idx = max(0, self.cursor - visible_count + 1)
        end_idx = min(len(self.events), start_idx + visible_count)
        for i in range(start_idx, end_idx):
            e = self.events[i]
            marker = "\x1b[33m►\x1b[0m" if i == self.cursor else " "
            detail = self._format_event(e, w - 25)
            ep = e.get("phase", "?")
            en = e.get("n", i + 1)
            lines.append(f" {marker} {en:3} │ {ep:18} │ {detail}")
        return lines[:max_h]

    def _render_math(self, w: int, max_h: int) -> list[str]:
        lines: list[str] = []
        s = self.snapshot
        lines.append(f"  ┌{'─' * (w-4)}┐")
        lines.append(f"  │ LORENZ ATTRACTOR                           │")
        lines.append(f"  │   x={s.get('lorenz_x', 0):8.3f}  y={s.get('lorenz_y', 0):8.3f}  z={s.get('lorenz_z', 0):8.3f}  │")
        lines.append(f"  │   energy={self.snapshot.get('energy', '?')}                      │")
        lines.append(f"  ├{'─' * (w-4)}┤")
        lines.append(f"  │ PID CONTROLLER                             │")
        lines.append(f"  │   output={s.get('pid_output', 0):.3f}  integral={s.get('pid_integral', 0):.3f}│")
        lines.append(f"  ├{'─' * (w-4)}┤")
        lines.append(f"  │ STAGNATION                                 │")
        lines.append(f"  │   score={s.get('stagnation_score', 0):.3f}  failures={s.get('consecutive_failures', 0):3}         │")
        lines.append(f"  ├{'─' * (w-4)}┤")
        lines.append(f"  │ JACOBIAN (verb effectiveness)              │")
        jac = s.get("jacobian", {})
        if jac:
            for k, v in sorted(jac.items(), key=lambda x: -x[1])[:6]:
                bar_len = int(v * 20)
                bar = "█" * bar_len + "░" * (20 - bar_len)
                lines.append(f"  │   {k:12} [{bar}] {v:.2f}    │")
        else:
            lines.append(f"  │   (no data)                                │")
        lines.append(f"  └{'─' * (w-4)}┘")
        remaining = max_h - len(lines)
        for _ in range(remaining):
            lines.append("")
        return lines[:max_h]

    def _render_plan(self, w: int, max_h: int) -> list[str]:
        lines: list[str] = []
        steps = self.snapshot.get("plan_steps", [])
        idx = self.snapshot.get("plan_index", 0)
        lines.append(f"  PLAN ({len(steps)} steps, current: {idx})")
        lines.append(f"  {'─' * (w-4)}")
        if not steps:
            lines.append("  (no active plan)")
        for i, step in enumerate(steps):
            if i == idx:
                lines.append(f"  \x1b[33m>>> {step[:w-8]}\x1b[0m")
            elif i < idx:
                lines.append(f"  \x1b[32m ✓  {step[:w-8]}\x1b[0m")
            else:
                lines.append(f"      {step[:w-8]}")
        history = self.snapshot.get("history", [])
        if history:
            lines.append(f"  {'─' * (w-4)}")
            lines.append(f"  HISTORY (last 5)")
            for h in history[-5:]:
                ok = "\x1b[32m✓\x1b[0m" if h.get("ok") else "\x1b[31m✗\x1b[0m"
                lines.append(f"    {ok} {h.get('verb', '?')}: {str(h.get('obs', ''))[:w-16]}")
        remaining = max_h - len(lines)
        for _ in range(remaining):
            lines.append("")
        return lines[:max_h]

    def _outcome(self) -> str:
        phases = [e.get("phase") for e in self.events]
        if "complete" in phases:
            return "\x1b[32m✓ COMPLETE\x1b[0m"
        if "halt" in phases:
            return "\x1b[31m✗ HALTED\x1b[0m"
        if "stop" in phases:
            return "\x1b[33m■ STOPPED\x1b[0m"
        return "\x1b[36m… RUNNING\x1b[0m"

    def _format_event(self, e: dict[str, Any], max_w: int) -> str:
        phase = e.get("phase", "?")
        d = e.get("d", {})
        match phase:
            case "start":
                return f"goal={d.get('goal', '')}"[:max_w]
            case "observe":
                return f"[{d.get('focused', '')}] {d.get('chars', 0)}ch"[:max_w]
            case "pulse":
                w_str = "⚡" if d.get("wing") else ""
                return f"s={d.get('stag', 0):.2f} x={d.get('lorenz_x', 0):.1f} p={d.get('pid', 0):.2f}{w_str} →{d.get('next', '')}"[:max_w]
            case "plan":
                return f"{d.get('mode', '')} → {d.get('action', '')}"[:max_w]
            case "actor":
                return f"{d.get('conclusion', '')} ({d.get('actions', 0)} actions)"[:max_w]
            case "action":
                ok = "✓" if d.get("ok") else "✗"
                dr = " [D]" if d.get("direct") else ""
                return f"{ok}{dr} {d.get('verb', '')} {d.get('obs', '')}"[:max_w]
            case "verify":
                v = "✓" if d.get("verdict") == "confirmed" else "✗"
                return f"{v} {d.get('evidence', '')}"[:max_w]
            case "reflect":
                return d.get("lesson", d.get("diagnosis", ""))[:max_w]
            case "lorenz.fork":
                return f"⚡ REPLAN x={d.get('x', 0):.2f}"[:max_w]
            case "complete":
                return f"\x1b[32mDONE in {d.get('events', '?')} events\x1b[0m"[:max_w]
            case "stop":
                return f"{d.get('reason', '')} ({d.get('events', '?')} events)"[:max_w]
            case "halt":
                return f"stagnation={d.get('stagnation', 0):.2f}"[:max_w]
            case _:
                raw = str(d)
                return raw[:max_w]


def run_tui(path: Path | None = None) -> None:
    events_path = path or EVENTS_PATH
    snapshot_path = SNAPSHOT_PATH
    tui = TUI(events_path, snapshot_path)

    _write(TUI_ALT_SCREEN_ON + TUI_HIDE_CURSOR)
    try:
        while tui.running:
            tui.load_events()
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
