"""TUI - single entry point for endgame-ai. Shows full LLM request/response."""
from __future__ import annotations
import argparse
import ctypes
import logging
import queue
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import llm
from llm import LLMClient, LLMResult, set_response_limit
from bus import Bus
from colony import Colony
from wiring import load_wiring
from topology import parse_cli_from_wiring

BASE_DIR = Path(__file__).parent.resolve()
PROMPTS_DIR = BASE_DIR / "prompts"

_LOGS_DIR = BASE_DIR / "logs"
_LOGS_DIR.mkdir(exist_ok=True)
logging.basicConfig(filename=str(_LOGS_DIR / f"{datetime.now():%Y%m%d_%H%M%S}.txt"),
                    level=logging.DEBUG, format="%(asctime)s %(message)s")


_file_log = logging.getLogger("endgame")


def _setup_console():
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    hout = k32.GetStdHandle(-11)
    m = ctypes.c_ulong()
    k32.GetConsoleMode(hout, ctypes.byref(m))
    k32.SetConsoleMode(hout, m.value | 0x0004 | 0x0008)
    return k32, hout


def _console_size(k32, hout) -> tuple[int, int]:
    class _CSBI(ctypes.Structure):
        _fields_ = [("sz", ctypes.c_short * 2), ("cp", ctypes.c_short * 2),
                    ("a", ctypes.c_ushort),
                    ("wL", ctypes.c_short), ("wT", ctypes.c_short),
                    ("wR", ctypes.c_short), ("wB", ctypes.c_short),
                    ("mx", ctypes.c_short * 2)]
    csbi = _CSBI()
    if k32.GetConsoleScreenBufferInfo(hout, ctypes.byref(csbi)):
        return max(80, csbi.wR - csbi.wL + 1), max(20, csbi.wB - csbi.wT + 1)
    return 120, 35


class TUI:
    def __init__(self, colony: Colony, wiring: dict[str, Any], desktop_enabled: bool = True):
        self.colony = colony
        self._wiring = wiring
        self.desktop_enabled = desktop_enabled
        self._running = True
        self._input_buf = ""
        self._log: list[str] = []
        self._scroll_offset = 0
        self._start = time.time()
        enabled = [n for n, c in wiring.get("slots", {}).items() if c.get("enabled", True)]
        self._slot_keys = {str(i + 1): name for i, name in enumerate(enabled)}
        self._result_q: queue.Queue = queue.Queue()
        self._thinking = False
        self._think_start: float = 0
        self._w = 120
        self._h = 35

    def _init_desktop(self):
        desktop = None
        actions = None
        if self.desktop_enabled:
            try:
                from desktop import Desktop
                from actions import ActionExecutor
                desktop = Desktop()
                actions = ActionExecutor(desktop, self._wiring)
            except (ImportError, OSError) as e:
                self._log_line(f"[!] Desktop unavailable: {e}")
                self.desktop_enabled = False
        self.colony.set_desktop(desktop, actions, self.desktop_enabled)

    def _log_line(self, text: str):
        """Add a line to the log. No truncation."""
        self._log.append(text)
        self._scroll_offset = 0

    def _log_block(self, title: str, content: str):
        """Add a multi-line block to log with full content."""
        self._log_line(f"{'─' * 40} {title} {'─' * 40}")
        for line in content.split("\n"):
            self._log_line(f"  {line}")
        self._log_line("")
        _file_log.debug("%s\n%s", title, content)

    def _worker(self):
        """Background: graph cycle per wiring.topology."""
        interval = float(self._wiring.get("limits", {}).get("observe_interval_s", 1))
        while self._running and not llm.shutdown_requested:
            has_work = (any(s.state.goal for s in self.colony.active_slots.values())
                        or self.colony.bus.has_pending_routes())
            if not has_work:
                time.sleep(0.5)
                continue
            self._thinking = True
            self._think_start = time.time()
            results = self.colony.step()
            self._thinking = False
            for name, result in results:
                if result:
                    self._result_q.put((name, result))
            time.sleep(interval)

    def _drain_results(self):
        while not self._result_q.empty():
            try:
                name, result = self._result_q.get_nowait()
            except queue.Empty:
                break
            phase = result.get("phase", "?")
            ts = datetime.now().strftime("%H:%M:%S")
            event = result.get("event", "")
            conclusion = result.get("conclusion", "")
            actions = result.get("actions", [])
            self._log_line(f"[{ts}] {name}:{phase} → {event} {conclusion}".rstrip())
            if event == "goal_complete":
                self._log_line(f"  ✓ GOAL COMPLETE")
            for line in result.get("execution_log", []):
                self._log_line(f"  {line}")
            if actions and not result.get("execution_log"):
                for a in actions:
                    self._log_line(f"  → {a.get('verb','')} target={a.get('target','')} value={a.get('value','')}")

    def _render(self) -> str:
        RST, BOLD, DIM, GREEN, CYAN, YEL, RED = (
            "\x1b[0m", "\x1b[1m", "\x1b[2m", "\x1b[32m", "\x1b[36m", "\x1b[33m", "\x1b[31m")
        w, h = self._w, self._h
        lines: list[str] = []
        elapsed = time.time() - self._start
        total_f = sum(s.state.fissions for s in self.colony.all_slots.values())
        total_c = sum(s.state.cycles for s in self.colony.all_slots.values())
        think_str = f"  {YEL}[THINKING {time.time() - self._think_start:.0f}s...]{RST}" if self._thinking else ""
        lines.append(f"{BOLD}{CYAN}ENDGAME-AI{RST}  slots={len(self.colony.active_slots)}/{len(self.colony.all_slots)}  F={total_f}  cycles={total_c}  {elapsed:.0f}s{think_str}")
        lines.append(f"{DIM}{'═' * (w - 1)}{RST}")
        for key, name in self._slot_keys.items():
            slot = self.colony.all_slots[name]
            active = self.colony.is_active(name)
            dot = f"{GREEN}●{RST}" if active else f"{DIM}○{RST}"
            phase = slot.state.phase
            goal = slot.state.goal if slot.state.goal else f"{DIM}(idle){RST}"
            lines.append(f"  {key}) {dot} {name:13} F={slot.state.fissions} {phase:12} {goal}")
        lines.append(f"{DIM}{'─' * (w - 1)}{RST}")
        header_count = len(lines)
        log_space = h - header_count - 2
        end = len(self._log) - self._scroll_offset
        start = max(0, end - log_space)
        visible = self._log[start:end] if end > 0 else []
        for entry in visible:
            lines.append(f"  {entry}")
        while len(lines) < h - 2:
            lines.append("")
        cursor = "│" if int(time.time() * 2) % 2 else " "
        lines.append(f"@human> {self._input_buf}{cursor}")
        lines.append(f"{DIM}Enter=send  1-{len(self._slot_keys)}=toggle  PgUp/PgDn=scroll  q=quit{RST}")
        return "\x1b[H" + "\r\n".join(ln + "\x1b[K" for ln in lines[:h]) + "\x1b[J"

    def _handle_key(self, ch: str):
        if ch in ("\r", "\n"):
            text = self._input_buf.strip()
            if text:
                self.colony.set_goal(text)
                self._log_line(f"GOAL: {text}")
            self._input_buf = ""
        elif ch == "\x08":
            self._input_buf = self._input_buf[:-1]
        elif ch == "\x00" or ch == "\xe0":
            import msvcrt
            ext = msvcrt.getwch()
            if ext == "I":
                self._scroll_offset = min(self._scroll_offset + 10, max(0, len(self._log) - 5))
            elif ext == "Q":
                self._scroll_offset = max(0, self._scroll_offset - 10)
        elif ch in self._slot_keys and not self._input_buf:
            name = self._slot_keys[ch]
            self.colony.toggle_slot(name)
            status = "ON" if self.colony.is_active(name) else "OFF"
            self._log_line(f"SLOT {name}: {status}")
        elif ch in ("q", "Q", "\x03") and not self._input_buf:
            self._running = False
        elif len(ch) == 1 and ch.isprintable():
            self._input_buf += ch

    def run(self, goal: str = ""):
        import msvcrt
        k32, hout = _setup_console()
        self._w, self._h = _console_size(k32, hout)
        self._init_desktop()
        orig_call = self.colony.llm.call
        def _hooked_call(system, user, **kw):
            self._log_block("REQUEST", f"SYSTEM:\n{system}\n\nUSER:\n{user}")
            self._thinking = True
            self._think_start = time.time()
            r = orig_call(system, user, **kw)
            elapsed = time.time() - self._think_start
            resp_parts = [f"CONTENT:\n{r.text}"]
            if r.reasoning:
                resp_parts.append(f"\nREASONING:\n{r.reasoning}")
            self._log_block(f"RESPONSE [{elapsed:.1f}s]", "\n".join(resp_parts))
            return r
        self.colony.set_llm_hook(_hooked_call)

        if goal:
            self.colony.set_goal(goal)
            self._log_line(f"GOAL: {goal}")
        if llm.response_limit is not None:
            self._log_line(f"[!] Auto-exit after {llm.response_limit} response(s)")
        threading.Thread(target=self._worker, daemon=True).start()
        n = ctypes.c_ulong()
        def _w(t):
            k32.WriteConsoleW(hout, t, len(t), ctypes.byref(n), None)
        _w("\x1b[?1049h\x1b[?25l\x1b]0;endgame-ai\x07")
        try:
            while self._running:
                if msvcrt.kbhit():
                    self._handle_key(msvcrt.getwch())
                self._drain_results()
                if llm.shutdown_requested:
                    self._log_line(f"[!] Response limit reached ({llm.response_count}), exiting")
                    self._running = False
                nw, nh = _console_size(k32, hout)
                if nw != self._w or nh != self._h:
                    self._w, self._h = nw, nh
                _w(self._render())
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            self._running = False
            _w("\x1b[?1049l\x1b[?25h")


def main():
    parser = argparse.ArgumentParser(prog="endgame-ai")
    parser.add_argument("goal", nargs="*", help="Goal; optional trailing positive integer = exit after N LLM responses")
    parser.add_argument("--no-desktop", action="store_true")
    parser.parse_args()
    wiring = load_wiring(PROMPTS_DIR)
    parsed = parse_cli_from_wiring(wiring, sys.argv[1:])
    if parsed["response_limit"] is not None:
        set_response_limit(parsed["response_limit"])
    bus = Bus(max_records=int(wiring["limits"]["bus_max_records"]))
    llm_client = LLMClient(prompts_dir=PROMPTS_DIR)
    desktop = wiring.get("runtime", {}).get("desktop", {}).get("enabled", True) and not parsed["no_desktop"]
    colony = Colony(llm=llm_client, bus=bus, prompts_dir=PROMPTS_DIR, workspace=BASE_DIR,
                    wiring=wiring, desktop_enabled=desktop)
    tui = TUI(colony=colony, wiring=wiring, desktop_enabled=desktop)
    tui.run(goal=parsed["goal"])


if __name__ == "__main__":
    main()