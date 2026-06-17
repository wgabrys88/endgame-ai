"""TUI - single entry point for endgame-ai."""
from __future__ import annotations
import argparse
import ctypes
import json
import sys
import time
from pathlib import Path
from typing import Any

from llm import LLMClient
from bus import Bus
from colony import Colony

BASE_DIR = Path(__file__).parent.resolve()
PROMPTS_DIR = BASE_DIR / "prompts"
REFRESH_INTERVAL = 0.15


def _setup_console():
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    hout = k32.GetStdHandle(-11)
    m = ctypes.c_ulong()
    k32.GetConsoleMode(hout, ctypes.byref(m))
    k32.SetConsoleMode(hout, m.value | 0x0004 | 0x0008)
    return k32, hout


def _write_console(k32, hout, text: str):
    n = ctypes.c_ulong()
    k32.WriteConsoleW(hout, text, len(text), ctypes.byref(n), None)


def _console_size(k32, hout) -> tuple[int, int]:
    class _SR(ctypes.Structure):
        _fields_ = [("L", ctypes.c_short), ("T", ctypes.c_short), ("R", ctypes.c_short), ("B", ctypes.c_short)]

    class _CSBI(ctypes.Structure):
        _fields_ = [("sz", ctypes.c_short * 2), ("cp", ctypes.c_short * 2),
                    ("a", ctypes.c_ushort), ("w", _SR), ("mx", ctypes.c_short * 2)]

    csbi = _CSBI()
    if k32.GetConsoleScreenBufferInfo(hout, ctypes.byref(csbi)):
        return max(80, csbi.w.R - csbi.w.L + 1), max(20, csbi.w.B - csbi.w.T + 1)
    return 120, 40


class TUI:
    SLOT_KEYS = {"1": "architect", "2": "implementor", "3": "reviewer", "4": "devops"}

    def __init__(self, colony: Colony, desktop_enabled: bool = True):
        self.colony = colony
        self.desktop_enabled = desktop_enabled
        self._desktop = None
        self._actions = None
        self._running = True
        self._input_buf = ""
        self._log: list[str] = []
        self._start = time.time()

    def _init_desktop(self):
        if self.desktop_enabled and self._desktop is None:
            try:
                from desktop import Desktop
                from actions import ActionExecutor
                self._desktop = Desktop()
                self._actions = ActionExecutor(self._desktop)
            except (ImportError, OSError) as e:
                self._log.append(f"Desktop unavailable: {e}")
                self.desktop_enabled = False

    def _observe(self):
        if not self._desktop:
            return
        try:
            obs = self._desktop.observe()
            for slot in self.colony.active_slots.values():
                if slot.can_act_desktop:
                    slot.observe(obs.context_text, obs.elements)
        except Exception as e:
            self._log.append(f"Observe error: {e}")

    def _execute_actions(self, slot_name: str, actions: list[dict[str, Any]]):
        if not self._actions:
            return
        slot = self.colony.all_slots.get(slot_name)
        elements = slot.state.screen_elements if slot else {}
        for action in actions:
            verb = str(action.get("verb", ""))
            result = self._actions.execute(verb, action, elements)
            self._log.append(f"  [{slot_name}] {verb}: {result.observation[:60]}")
            if slot:
                self.colony.bus.publish("evidence", "tool", slot.state.active_task_id or "",
                                        {"verb": verb, "success": result.success, "obs": result.observation[:200]})

    def render(self, w: int, h: int) -> str:
        RST = "\x1b[0m"
        BOLD = "\x1b[1m"
        DIM = "\x1b[2m"
        GREEN = "\x1b[32m"
        RED = "\x1b[31m"
        CYAN = "\x1b[36m"

        lines: list[str] = []
        elapsed = time.time() - self._start
        total_f = sum(s.state.fissions for s in self.colony.all_slots.values())
        total_c = sum(s.state.cycles for s in self.colony.all_slots.values())
        active_count = len(self.colony.active_slots)
        lines.append(f"{BOLD}{CYAN}ENDGAME-AI{RST}  slots={active_count}/4  F={total_f}  cycles={total_c}  {elapsed:.0f}s")
        lines.append(f"{DIM}{'=' * (w - 1)}{RST}")

        for key, name in self.SLOT_KEYS.items():
            slot = self.colony.all_slots[name]
            active = self.colony.is_active(name)
            dot = f"{GREEN}*{RST}" if active else f"{RED}x{RST}"
            phase = slot.state.last_phase[:12] if slot.state.last_phase else "idle"
            goal = slot.state.goal[:w-40] if slot.state.goal else "(no goal)"
            lock = " [ACT]" if self.colony._actor_lock == name else ""
            lines.append(f"  {key}) {dot} {name:13} F={slot.state.fissions} {phase:12} {goal}{lock}")

        lines.append(f"{DIM}{'-' * (w - 1)}{RST}")
        log_space = max(4, h - len(lines) - 4)
        for entry in self._log[-log_space:]:
            lines.append(f"  {DIM}{entry[:w-4]}{RST}")

        while len(lines) < h - 3:
            lines.append("")

        lines.append(f"{DIM}{'-' * (w - 1)}{RST}")
        cursor = "|" if int(time.time() * 2) % 2 else " "
        lines.append(f"@human> {self._input_buf}{cursor}")
        lines.append(f"{DIM}Enter=send  1-4=toggle slot  q=quit{RST}")

        return "\x1b[H" + "\r\n".join(ln + "\x1b[K" for ln in lines[:h]) + "\x1b[J"

    def _handle_key(self, ch: str):
        if ch in ("\r", "\n"):
            text = self._input_buf.strip()
            if text:
                self.colony.set_goal(text)
                self._log.append(f"GOAL: {text}")
            self._input_buf = ""
        elif ch == "\x08":
            self._input_buf = self._input_buf[:-1]
        elif ch in self.SLOT_KEYS and not self._input_buf:
            name = self.SLOT_KEYS[ch]
            self.colony.toggle_slot(name)
            status = "ON" if self.colony.is_active(name) else "OFF"
            self._log.append(f"SLOT {name}: {status}")
        elif ch in ("q", "Q", "\x03") and not self._input_buf:
            self._running = False
        elif len(ch) == 1 and ch.isprintable():
            self._input_buf += ch

    def run(self, goal: str = ""):
        import msvcrt
        k32, hout = _setup_console()
        self._init_desktop()
        if goal:
            self.colony.set_goal(goal)
            self._log.append(f"GOAL: {goal}")

        _write_console(k32, hout, "\x1b[?1049h\x1b[?25l\x1b]0;endgame-ai\x07")
        try:
            while self._running:
                if msvcrt.kbhit():
                    self._handle_key(msvcrt.getwch())

                w, h = _console_size(k32, hout)
                _write_console(k32, hout, self.render(w, h))

                has_work = (any(s.state.goal for s in self.colony.active_slots.values())
                            or self.colony.bus.has_pending_routes())
                if not has_work:
                    time.sleep(REFRESH_INTERVAL)
                    continue

                if self.desktop_enabled:
                    self._observe()

                results = self.colony.step()
                for name, result in results:
                    if result:
                        phase = result.get("phase", "?")
                        self.colony.all_slots[name].state.last_phase = phase
                        brief = json.dumps({k: v for k, v in result.items() if k != "phase"}, ensure_ascii=False)[:80]
                        self._log.append(f"  [{name}:{phase}] {brief}")
                        if result.get("actions"):
                            self._execute_actions(name, result["actions"])

                time.sleep(2.0)
        except KeyboardInterrupt:
            pass
        finally:
            _write_console(k32, hout, "\x1b[?1049l\x1b[?25h")


def main():
    parser = argparse.ArgumentParser(prog="endgame-ai")
    parser.add_argument("goal", nargs="*", help="Goal")
    parser.add_argument("--no-desktop", action="store_true", help="Skip screen observation")
    args = parser.parse_args()

    workspace = BASE_DIR
    bus = Bus()
    llm = LLMClient(prompts_dir=PROMPTS_DIR)
    colony = Colony(llm=llm, bus=bus, prompts_dir=PROMPTS_DIR, workspace=workspace)
    tui = TUI(colony=colony, desktop_enabled=not args.no_desktop)
    tui.run(goal=" ".join(args.goal).strip())


if __name__ == "__main__":
    main()
