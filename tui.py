from __future__ import annotations
import ctypes
import json
import sys
import time
from pathlib import Path
from typing import Any

from config import (
    STD_OUTPUT_HANDLE, TUI_ALT_SCREEN_ON, TUI_ALT_SCREEN_OFF,
    TUI_HIDE_CURSOR, TUI_SHOW_CURSOR, TUI_HOME_CLEAR,
    EVENTS_PATH,
)

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_stdout_handle = _kernel32.GetStdHandle(STD_OUTPUT_HANDLE)


def _write(text: str) -> None:
    written = ctypes.c_ulong()
    _kernel32.WriteConsoleW(_stdout_handle, text, len(text), ctypes.byref(written), None)


def _render_frame(events: list[dict[str, Any]], width: int = 80) -> str:
    if not events:
        return "waiting for events..."

    last = events[-1]
    n = last.get("n", 0)
    phase = last.get("phase", "?")

    start_evt = next((e for e in events if e.get("phase") == "start"), None)
    budget = start_evt["d"]["budget"] if start_evt else 100
    goal = start_evt["d"]["goal"] if start_evt else "?"

    bar_len = width - 20
    filled = int(bar_len * min(n / max(budget, 1), 1.0))
    bar = "█" * filled + "░" * (bar_len - filled)

    actions = [e for e in events if e.get("phase") == "action"]
    ok_count = sum(1 for a in actions if a.get("d", {}).get("ok"))
    fail_count = len(actions) - ok_count

    plans = [e for e in events if e.get("phase") == "plan"]
    verifies = [e for e in events if e.get("phase") == "verify"]
    reflects = [e for e in events if e.get("phase") == "reflect"]

    lines: list[str] = []
    lines.append(f"{'═' * width}")
    lines.append(f" endgame-ai │ {goal[:width-16]}")
    lines.append(f"{'─' * width}")
    lines.append(f" EVENT {n:3}/{budget:3} [{bar}]")
    lines.append(f" PHASE: {phase:12} │ actions: {ok_count}ok {fail_count}fail │ plans: {len(plans)} │ verifies: {len(verifies)} │ reflects: {len(reflects)}")
    lines.append(f"{'─' * width}")

    recent = events[-8:]
    for evt in recent:
        en = evt.get("n", 0)
        ep = evt.get("phase", "?")
        ed = evt.get("d", {})
        detail = _format_detail(ep, ed)
        lines.append(f" {en:3} │ {ep:12} │ {detail[:width-22]}")

    lines.append(f"{'─' * width}")

    lorenz_evt = next((e for e in reversed(events) if e.get("phase") == "lorenz.fork"), None)
    if lorenz_evt:
        lines.append(f" ⚡ LORENZ FORK at event {lorenz_evt.get('n')}: x={lorenz_evt['d'].get('x', 0):.2f}")

    reflect_evt = next((e for e in reversed(events) if e.get("phase") == "reflect"), None)
    if reflect_evt:
        lines.append(f" 🔍 {reflect_evt['d'].get('diagnosis', '')[:width-5]}")

    lines.append(f"{'═' * width}")
    return "\n".join(lines)


def _format_detail(phase: str, d: dict[str, Any]) -> str:
    match phase:
        case "start":
            return f"goal={d.get('goal', '')}"
        case "observe":
            return f"[{d.get('focused', '')}] {d.get('chars', 0)} chars"
        case "plan":
            return f"{d.get('mode', '')} → {d.get('action', '')[:40]}"
        case "actor":
            return f"{d.get('conclusion', '')} ({d.get('actions', 0)} actions)"
        case "action":
            ok = "✓" if d.get("ok") else "✗"
            return f"{ok} {d.get('verb', '')} {d.get('obs', '')[:40]}"
        case "verify":
            v = "✓" if d.get("verdict") == "confirmed" else "✗"
            return f"{v} {d.get('evidence', '')[:50]}"
        case "reflect":
            return d.get("diagnosis", "")[:50]
        case "complete":
            return f"DONE in {d.get('events', '?')} events"
        case "stop":
            return f"{d.get('reason', '')} ({d.get('events', '?')} events)"
        case _:
            return str(d)[:50]


def run_tui(path: Path | None = None) -> None:
    target = path or EVENTS_PATH
    _write(TUI_ALT_SCREEN_ON + TUI_HIDE_CURSOR)
    try:
        last_size = 0
        events: list[dict[str, Any]] = []
        while True:
            try:
                if target.exists():
                    current_size = target.stat().st_size
                    if current_size != last_size:
                        last_size = current_size
                        raw = target.read_text(encoding="utf-8")
                        events = [json.loads(line) for line in raw.splitlines() if line.strip()]
                frame = _render_frame(events)
                _write(TUI_HOME_CLEAR + frame)

                if events and events[-1].get("phase") in ("complete", "stop", "halt"):
                    time.sleep(2.0)
                    break
            except (json.JSONDecodeError, OSError):
                pass
            time.sleep(0.3)
    except KeyboardInterrupt:
        pass
    finally:
        _write(TUI_ALT_SCREEN_OFF + TUI_SHOW_CURSOR)


if __name__ == "__main__":
    p = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    run_tui(p)
