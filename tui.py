from __future__ import annotations
import ctypes
import json
import msvcrt
import sys
import time
from pathlib import Path
from typing import Any

from config import (
    STD_OUTPUT_HANDLE, TUI_ALT_SCREEN_ON, TUI_ALT_SCREEN_OFF,
    TUI_HIDE_CURSOR, TUI_SHOW_CURSOR, TUI_HOME_CLEAR,
    EVENTS_PATH, SNAPSHOT_PATH,
)

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_stdout_handle = _kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
ENABLE_VIRTUAL_TERMINAL: int = 0x0004
_mode = ctypes.c_ulong()
_kernel32.GetConsoleMode(_stdout_handle, ctypes.byref(_mode))
_kernel32.SetConsoleMode(_stdout_handle, _mode.value | ENABLE_VIRTUAL_TERMINAL)


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
        self.expanded: str = ""
        self.last_file_size: int = 0
        self.running: bool = True

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
            if ext == b"M":
                self._step_forward()
            elif ext == b"K":
                self._step_back()
            return
        if key == b" ":
            self.paused = not self.paused
        elif key == b"q":
            self.running = False
        elif key == b"s":
            self.expanded = "screen" if self.expanded != "screen" else ""
        elif key == b"m":
            self.expanded = "math" if self.expanded != "math" else ""
        elif key == b"p":
            self.expanded = "plan" if self.expanded != "plan" else ""
        elif key == b"e":
            self.expanded = "event" if self.expanded != "event" else ""
        elif key == b"h":
            self.expanded = "history" if self.expanded != "history" else ""
        elif key in (b"\r", b"\n"):
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

        if not self.events:
            lines.append(f"{'═' * w}")
            lines.append(" endgame-ai │ waiting for events...")
            lines.append(f" watching: {self.events_path}")
            lines.append(f"{'═' * w}")
            lines.append(" [space]=pause [q]=quit [→]=step [←]=back")
            lines.append(" [s]=screen [m]=math [p]=plan [e]=event [h]=history")
            return "\n".join(lines)

        evt = self.events[self.cursor] if 0 <= self.cursor < len(self.events) else self.events[-1]
        start_evt = next((e for e in self.events if e.get("phase") == "start"), None)
        budget = start_evt["d"]["budget"] if start_evt else 100
        goal = start_evt["d"]["goal"] if start_evt else "?"
        total = len(self.events)
        current_n = self.cursor + 1

        bar_len = w - 30
        filled = int(bar_len * min(current_n / max(total, 1), 1.0))
        bar = "█" * filled + "░" * (bar_len - filled)

        status = "⏸ PAUSED" if self.paused else "▶ LIVE"
        phase = evt.get("phase", "?")
        outcome = self._outcome()

        lines.append(f"{'═' * w}")
        lines.append(f" endgame-ai │ {goal[:w-16]}")
        lines.append(f"{'─' * w}")
        lines.append(f" {status} │ Event {current_n}/{total} (budget {budget}) │ {outcome}")
        lines.append(f" [{bar}]")
        lines.append(f"{'─' * w}")
        lines.append(f" ◄◄  ◄  {'❚❚' if not self.paused else '▶ '}  ►  ►►  │ Phase: {phase}")
        lines.append(f"{'─' * w}")

        if self.expanded:
            lines += self._render_expanded(w, h - 12)
        else:
            visible_count = min(h - 12, 15)
            start_idx = max(0, self.cursor - visible_count + 1)
            end_idx = min(len(self.events), start_idx + visible_count)
            for i in range(start_idx, end_idx):
                e = self.events[i]
                marker = "►" if i == self.cursor else " "
                detail = self._format_event(e, w - 25)
                ep = e.get("phase", "?")
                en = e.get("n", i + 1)
                lines.append(f" {marker} {en:3} │ {ep:12} │ {detail}")

        lines.append(f"{'─' * w}")
        lines.append(f" [space]=pause [q]=quit [→/Enter]=step [←]=back │ [s]creen [m]ath [p]lan [e]vent [h]istory")
        lines.append(f"{'═' * w}")
        return "\n".join(lines[:h])

    def _outcome(self) -> str:
        phases = [e.get("phase") for e in self.events]
        if "complete" in phases:
            return "✓ COMPLETE"
        if "halt" in phases:
            return "✗ HALTED"
        if "stop" in phases:
            reason = next((e["d"].get("reason", "") for e in self.events if e.get("phase") == "stop"), "")
            return f"■ STOPPED ({reason})"
        return "… RUNNING"

    def _render_expanded(self, w: int, max_lines: int) -> list[str]:
        lines: list[str] = []
        if self.expanded == "screen":
            lines.append(f" ┌{'─' * (w-2)}┐")
            lines.append(f" │ SCREEN (what LLM sees){'':>{w-25}}│")
            lines.append(f" ├{'─' * (w-2)}┤")
            screen = self.snapshot.get("screen", "(no snapshot)")
            if not screen and self.events:
                obs = next((e for e in reversed(self.events[:self.cursor+1]) if e.get("phase") == "observe"), None)
                screen = str(obs.get("d", {}).get("chars", "?")) + " chars" if obs else "(no observe)"
            for line in str(screen).split("\n")[:max_lines-4]:
                lines.append(f" │ {line[:w-4]}")
            lines.append(f" └{'─' * (w-2)}┘")
        elif self.expanded == "math":
            lines.append(f" ┌{'─' * (w-2)}┐")
            lines.append(f" │ MATH STATE{'':>{w-14}}│")
            lines.append(f" ├{'─' * (w-2)}┤")
            self.load_snapshot()
            s = self.snapshot
            lines.append(f" │ Stagnation: {s.get('stagnation_score', 0):.3f}")
            lines.append(f" │ Lorenz:     x={s.get('lorenz_x', 0):.2f} y={s.get('lorenz_y', 0):.2f} z={s.get('lorenz_z', 0):.2f}")
            lines.append(f" │ PID:        output={s.get('pid_output', 0):.3f} integral={s.get('pid_integral', 0):.3f}")
            jac = s.get("jacobian", {})
            if jac:
                top = sorted(jac.items(), key=lambda x: -x[1])[:5]
                lines.append(f" │ Jacobian:   {', '.join(f'{k}={v:.2f}' for k,v in top)}")
            lines.append(f" │ Events:     {s.get('events', '?')}/{s.get('budget', '?')}")
            lines.append(f" └{'─' * (w-2)}┘")
        elif self.expanded == "plan":
            lines.append(f" ┌{'─' * (w-2)}┐")
            lines.append(f" │ PLAN{'':>{w-8}}│")
            lines.append(f" ├{'─' * (w-2)}┤")
            self.load_snapshot()
            steps = self.snapshot.get("plan_steps", [])
            idx = self.snapshot.get("plan_index", 0)
            if not steps:
                lines.append(f" │ (no plan)")
            for i, step in enumerate(steps):
                marker = ">>>" if i == idx else ("✓" if i < idx else " ")
                lines.append(f" │ {marker} {step[:w-8]}")
            lines.append(f" └{'─' * (w-2)}┘")
        elif self.expanded == "event":
            lines.append(f" ┌{'─' * (w-2)}┐")
            lines.append(f" │ EVENT DETAIL{'':>{w-16}}│")
            lines.append(f" ├{'─' * (w-2)}┤")
            if 0 <= self.cursor < len(self.events):
                evt = self.events[self.cursor]
                formatted = json.dumps(evt, indent=2, ensure_ascii=False)
                for line in formatted.split("\n")[:max_lines-4]:
                    lines.append(f" │ {line[:w-4]}")
            lines.append(f" └{'─' * (w-2)}┘")
        elif self.expanded == "history":
            lines.append(f" ┌{'─' * (w-2)}┐")
            lines.append(f" │ ACTION HISTORY{'':>{w-18}}│")
            lines.append(f" ├{'─' * (w-2)}┤")
            self.load_snapshot()
            history = self.snapshot.get("history", [])
            for h in history[-max_lines+4:]:
                ok = "✓" if h.get("ok") else "✗"
                lines.append(f" │ {ok} {h.get('verb', '?')}: {str(h.get('obs', ''))[:w-12]}")
            if not history:
                lines.append(f" │ (no history)")
            lines.append(f" └{'─' * (w-2)}┘")
        return lines

    def _format_event(self, e: dict[str, Any], max_w: int) -> str:
        phase = e.get("phase", "?")
        d = e.get("d", {})
        match phase:
            case "start":
                return f"goal={d.get('goal', '')}"[:max_w]
            case "observe":
                return f"[{d.get('focused', '')}] {d.get('chars', 0)} chars"[:max_w]
            case "plan":
                return f"{d.get('mode', '')} → {d.get('action', '')}"[:max_w]
            case "actor":
                return f"{d.get('conclusion', '')} ({d.get('actions', 0)} actions)"[:max_w]
            case "action":
                ok = "✓" if d.get("ok") else "✗"
                return f"{ok} {d.get('verb', '')} {d.get('obs', '')}"[:max_w]
            case "verify":
                v = "✓" if d.get("verdict") == "confirmed" else "✗"
                return f"{v} {d.get('evidence', '')}"[:max_w]
            case "reflect":
                return d.get("diagnosis", "")[:max_w]
            case "lorenz.fork":
                return f"⚡ x={d.get('x', 0):.2f} stag={d.get('stagnation', 0):.2f}"[:max_w]
            case "complete":
                return f"DONE in {d.get('events', '?')} events"[:max_w]
            case "stop":
                return f"{d.get('reason', '')} ({d.get('events', '?')} events)"[:max_w]
            case "halt":
                return f"stagnation={d.get('stagnation', 0):.2f}"[:max_w]
            case "mutation":
                return f"→ {d.get('target', '')} +'{d.get('appended', '')[:30]}'"[:max_w]
            case _:
                return str(d)[:max_w]


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
