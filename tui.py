"""TUI - single entry point for endgame-ai. Wiring-driven. Non-blocking."""
from __future__ import annotations
import argparse
import ctypes
import json
import logging
import queue
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from llm import LLMClient
from bus import Bus
from colony import Colony

BASE_DIR = Path(__file__).parent.resolve()
PROMPTS_DIR = BASE_DIR / "prompts"

_LOGS_DIR = BASE_DIR / "logs"
_LOGS_DIR.mkdir(exist_ok=True)
logging.basicConfig(filename=str(_LOGS_DIR / f"{datetime.now():%Y%m%d_%H%M%S}.txt"),
                    level=logging.DEBUG, format="%(asctime)s %(message)s")

W, H = 120, 35


def _load_wiring() -> dict[str, Any]:
    path = PROMPTS_DIR / "wiring.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _setup_console():
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    hout = k32.GetStdHandle(-11)
    hin = k32.GetStdHandle(-10)
    m = ctypes.c_ulong()
    k32.GetConsoleMode(hout, ctypes.byref(m))
    k32.SetConsoleMode(hout, m.value | 0x0004 | 0x0008)
    return k32, hout


def _write(k32, hout, text: str):
    n = ctypes.c_ulong()
    k32.WriteConsoleW(text, len(text), ctypes.byref(n), None)


class TUI:
    def __init__(self, colony: Colony, wiring: dict[str, Any], desktop_enabled: bool = True):
        self.colony = colony
        self._wiring = wiring
        self.desktop_enabled = desktop_enabled
        self._desktop = None
        self._actions = None
        self._running = True
        self._input_buf = ""
        self._log: list[str] = []
        self._start = time.time()
        self._slot_keys = {str(i+1): name for i, name in enumerate(wiring.get("slots", {}).keys())}
        self._result_q: queue.Queue = queue.Queue()
        self._thinking = False
        self._think_start: float = 0
        self._last_llm_summary = ""
        self._last_request = ""
        self._last_response = ""
        self._worker_thread: threading.Thread | None = None

    def _init_desktop(self):
        if self.desktop_enabled and self._desktop is None:
            try:
                from desktop import Desktop
                from actions import ActionExecutor
                self._desktop = Desktop()
                self._actions = ActionExecutor(self._desktop, self._wiring)
            except (ImportError, OSError) as e:
                self._log.append(f"[!] Desktop unavailable: {e}")
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
            self._log.append(f"[!] Observe: {e}")

    def _execute_actions(self, slot_name: str, actions: list[dict[str, Any]], reasoning_entry: dict | None = None):
        if not self._actions:
            return
        slot = self.colony.all_slots.get(slot_name)
        elements = slot.state.screen_elements if slot else {}
        outcomes: list[str] = []
        for action in actions:
            verb = str(action.get("verb", ""))
            result = self._actions.execute(verb, action, elements)
            self._log.append(f"  {verb}: {result.observation}")
            outcomes.append(f"{verb}: {'OK' if result.success else result.observation}")
            if slot:
                if not result.success:
                    slot.state.last_action_error = f"{verb}: {result.observation}"
                self.colony.bus.publish("evidence", "tool", slot.state.active_task_id or "",
                                        {"verb": verb, "success": result.success, "obs": result.observation})
        if slot and reasoning_entry is not None:
            reasoning_entry["outcome"] = "; ".join(outcomes)
            slot.state.reasoning_history.append(reasoning_entry)
            depth = self._wiring["limits"]["reasoning_history_depth"]
            if len(slot.state.reasoning_history) > depth:
                slot.state.reasoning_history = slot.state.reasoning_history[-depth:]

    def _worker(self):
        """Background: observe → step → queue results. Never blocks TUI."""
        while self._running:
            has_work = (any(s.state.goal for s in self.colony.active_slots.values())
                        or self.colony.bus.has_pending_routes())
            if not has_work:
                time.sleep(0.5)
                continue
            if self.desktop_enabled:
                self._observe()
            self._thinking = True
            self._think_start = time.time()
            results = self.colony.step()
            self._thinking = False
            for name, result in results:
                if result:
                    self._result_q.put((name, result))
            time.sleep(1.0)

    def _drain_results(self):
        while not self._result_q.empty():
            try:
                name, result = self._result_q.get_nowait()
            except queue.Empty:
                break
            phase = result.get("phase", "?")
            ts = datetime.now().strftime("%H:%M:%S")
            # Build log line — NO truncation
            event = result.get("event", "")
            conclusion = result.get("conclusion", "")
            actions = result.get("actions", [])
            self._log.append(f"[{ts}] {name}:{phase} {event} {conclusion}".rstrip())
            if actions:
                for a in actions:
                    self._log.append(f"  → {a.get('verb','')} {a.get('target','')} {a.get('value','')}")
                self._execute_actions(name, actions, result.get("reasoning_entry"))
            # LLM summary for status bar
            if event:
                self._last_llm_summary = f"{name}:{phase} → {event}"

    def _render(self) -> str:
        RST, BOLD, DIM, GREEN, RED, CYAN, YEL = (
            "\x1b[0m", "\x1b[1m", "\x1b[2m", "\x1b[32m", "\x1b[31m", "\x1b[36m", "\x1b[33m")
        lines: list[str] = []
        elapsed = time.time() - self._start
        total_f = sum(s.state.fissions for s in self.colony.all_slots.values())
        total_c = sum(s.state.cycles for s in self.colony.all_slots.values())
        # Thinking indicator
        think_str = ""
        if self._thinking:
            think_str = f"  {YEL}[THINKING {time.time() - self._think_start:.0f}s...]{RST}"
        lines.append(f"{BOLD}{CYAN}ENDGAME-AI{RST}  slots={len(self.colony.active_slots)}/{len(self.colony.all_slots)}  F={total_f}  cycles={total_c}  {elapsed:.0f}s{think_str}")
        lines.append(f"{DIM}{'═' * (W - 1)}{RST}")
        # Slot status
        for key, name in self._slot_keys.items():
            slot = self.colony.all_slots[name]
            active = self.colony.is_active(name)
            dot = f"{GREEN}●{RST}" if active else f"{DIM}○{RST}"
            phase = slot.state.phase
            goal = slot.state.goal if slot.state.goal else f"{DIM}(idle){RST}"
            lines.append(f"  {key}) {dot} {name:13} F={slot.state.fissions} {phase:12} {goal}")
        lines.append(f"{DIM}{'─' * (W - 1)}{RST}")
        # Log area — fill available space
        header_lines = len(lines)  # lines used so far
        footer_lines = 4  # summary + separator + input + help
        log_space = H - header_lines - footer_lines
        visible_log = self._log[-log_space:] if log_space > 0 else []
        for entry in visible_log:
            lines.append(f"  {entry[:W - 4]}")
        while len(lines) < H - footer_lines:
            lines.append("")
        # LLM summary bar
        lines.append(f"{DIM}{'─' * (W - 1)}{RST}")
        lines.append(f"  {DIM}LLM: {self._last_llm_summary}{RST}")
        # Input
        cursor = "│" if int(time.time() * 2) % 2 else " "
        lines.append(f"@human> {self._input_buf}{cursor}")
        lines.append(f"{DIM}Enter=send  1-{len(self._slot_keys)}=toggle  q=quit  r=last req  R=last resp{RST}")
        return "\x1b[H" + "\r\n".join(ln + "\x1b[K" for ln in lines[:H]) + "\x1b[J"

    def _handle_key(self, ch: str):
        if ch in ("\r", "\n"):
            text = self._input_buf.strip()
            if text:
                self.colony.set_goal(text)
                self._log.append(f"GOAL: {text}")
            self._input_buf = ""
        elif ch == "\x08":
            self._input_buf = self._input_buf[:-1]
        elif ch in self._slot_keys and not self._input_buf:
            name = self._slot_keys[ch]
            self.colony.toggle_slot(name)
            status = "ON" if self.colony.is_active(name) else "OFF"
            self._log.append(f"SLOT {name}: {status}")
        elif ch == "r" and not self._input_buf:
            if self._last_request:
                for line in self._last_request.split("\n"):
                    self._log.append(f"  REQ| {line}")
            else:
                self._log.append("  (no request yet)")
        elif ch == "R" and not self._input_buf:
            if self._last_response:
                for line in self._last_response.split("\n"):
                    self._log.append(f"  RSP| {line}")
            else:
                self._log.append("  (no response yet)")
        elif ch in ("q", "Q", "\x03") and not self._input_buf:
            self._running = False
        elif len(ch) == 1 and ch.isprintable():
            self._input_buf += ch

    def run(self, goal: str = ""):
        import msvcrt
        k32, hout = _setup_console()
        self._init_desktop()
        # Hook LLM client to capture last request/response for 'r'/'R' keys
        orig_call = self.colony.llm.call
        def _hooked_call(system, user, **kw):
            self._last_request = f"SYSTEM: {system}\n\nUSER: {user}"
            r = orig_call(system, user, **kw)
            self._last_response = f"TEXT: {r.text}\n\nREASONING: {r.reasoning}"
            return r
        self.colony.llm.call = _hooked_call

        if goal:
            self.colony.set_goal(goal)
            self._log.append(f"GOAL: {goal}")
        # Start worker thread
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()
        n = ctypes.c_ulong()
        def _w(t):
            k32.WriteConsoleW(hout, t, len(t), ctypes.byref(n), None)
        _w("\x1b[?1049h\x1b[?25l\x1b]0;endgame-ai\x07")
        try:
            while self._running:
                if msvcrt.kbhit():
                    self._handle_key(msvcrt.getwch())
                self._drain_results()
                _w(self._render())
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            self._running = False
            _w("\x1b[?1049l\x1b[?25h")


def main():
    parser = argparse.ArgumentParser(prog="endgame-ai")
    parser.add_argument("goal", nargs="*", help="Goal")
    parser.add_argument("--no-desktop", action="store_true")
    args = parser.parse_args()
    wiring = _load_wiring()
    bus = Bus()
    llm = LLMClient(prompts_dir=PROMPTS_DIR)
    colony = Colony(llm=llm, bus=bus, prompts_dir=PROMPTS_DIR, workspace=BASE_DIR, wiring=wiring)
    # Start with NO active slots — they activate when routes arrive
    colony.active_slots.clear()
    tui = TUI(colony=colony, wiring=wiring, desktop_enabled=not args.no_desktop)
    tui.run(goal=" ".join(args.goal).strip())


if __name__ == "__main__":
    main()
