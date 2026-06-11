from __future__ import annotations
import ctypes
import json
import msvcrt
import struct
import sys
import time
from pathlib import Path
from typing import Any

import log
import config

STD_OUTPUT_HANDLE: int = -11
ALT_ON = "\x1b[?1049h"
ALT_OFF = "\x1b[?1049l"
HIDE_CUR = "\x1b[?25l"
SHOW_CUR = "\x1b[?25h"

EVENT_TAIL: int = 12
LESSONS_TAIL: int = 3

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_hout = _k32.GetStdHandle(STD_OUTPUT_HANDLE)
_m = ctypes.c_ulong()
_k32.GetConsoleMode(_hout, ctypes.byref(_m))
_k32.SetConsoleMode(_hout, _m.value | 0x0004)

MATH_CHAIN = ("stagnation", "lorenz", "pid")
AGENT_CHAIN = ("planner", "actor", "verifier", "fission")
SIDE_AGENTS = ("observer", "reflector", "mutator")
MATH_PHASES = frozenset(MATH_CHAIN)
LOOP_PHASES = frozenset({
    "schedule", "plan", "actor", "action", "observe", "verify",
    "reflect", "mutation", "fission", "fission_blocked", "goal_change",
    "planner.error", "actor.error", "verifier.error", "reflector.error",
})
REFLECT_REASONS = frozenset({"pid_gate", "chaos_gate", "stag_gate"})
SCHEDULE_AGENT: dict[str, str] = {
    "execute": "actor", "advance": "actor", "need_plan": "planner",
    "wing_cross": "planner", "stuck": "planner", "plan_complete": "verifier",
}
PHASE_AGENT: dict[str, str] = {
    "plan": "planner", "planner.error": "planner",
    "actor": "actor", "action": "actor", "actor.error": "actor",
    "verify": "verifier", "verifier.error": "verifier",
    "fission": "fission", "fission_sustain": "fission", "fission_blocked": "fission",
    "reflect": "reflector", "reflector.error": "reflector",
    "mutation": "mutator", "observe": "observer",
}
WORK_PHASES = LOOP_PHASES | frozenset({"start", "stop", "fission", "token_usage", "token_warning", "mutator", "mutator.error", "mutator.rejected", "plugin.lessons_decay", "plugin.web_sentinel"})
ACTIVE_SCAN = 64
REFRESH = 0.08

RST, DIM, BOLD = "\x1b[0m", "\x1b[2m", "\x1b[1m"


def _write(t: str) -> None:
    n = ctypes.c_ulong()
    _k32.WriteConsoleW(_hout, t, len(t), ctypes.byref(n), None)


def _size() -> tuple[int, int]:
    buf = ctypes.create_string_buffer(22)
    _k32.GetConsoleScreenBufferInfo(_hout, buf)
    _, _, _, _, _, l, t, r, b, _, _ = struct.unpack("hhhhHhhhhhh", buf.raw)
    return r - l + 1, b - t + 1


def _fg(r: int, g: int, b: int) -> str:
    return f"\x1b[38;2;{r};{g};{b}m"


def _bar(v: float, w: int, color: str) -> str:
    w = max(4, w)
    f = max(0, min(w, int(v * w)))
    return color + "█" * f + DIM + "░" * (w - f) + RST


def _plain(s: str) -> str:
    out, i, n = [], 0, len(s)
    while i < n:
        if s[i] == "\x1b" and i + 1 < n and s[i + 1] == "[":
            j = i + 2
            while j < n and s[j] not in "ABCDEFGHJKSTfmnsulh":
                j += 1
            i = j + 1 if j < n else j
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def _pad(text: str, w: int) -> str:
    vl = len(_plain(text))
    return text + " " * max(0, w - vl) if vl < w else text


def _trunc(text: str, w: int) -> str:
    if len(text) <= w:
        return text
    return text[:w - 1] + "…"


def _elapsed(start: float) -> str:
    if not start:
        return "—"
    d = time.time() - start
    if d < 60:
        return f"{d:.0f}s"
    if d < 3600:
        return f"{d/60:.1f}m"
    return f"{d/3600:.1f}h"


class TUI:
    def __init__(self, goal: str = "", backend: str = "lmstudio", budget: int = 20, autostart: bool = True):
        self.events: list[dict] = []
        self.snapshot: dict[str, Any] = {}
        self._ev_sig: tuple[str, int, float] = ("", 0, 0.0)
        self._ev_offset: int = 0
        self._snap_mt: float = 0.0
        self.running = True
        self.goal = goal
        self.backend = backend
        self.budget = budget
        self.proc: Any = None
        self._in_alt = False
        self._input_active = False
        self._input_buf = goal
        self._input_cur = len(goal)
        self._autostart = autostart
        self._loop = "—"
        self._side = "—"
        self._math = "—"
        self._reason = ""
        self._start_time: float = 0.0
        if goal:
            config.GOAL_PATH.write_text(goal, encoding="utf-8")

    def _reactor_live(self) -> bool:
        return self.proc is not None or log.reactor_running()

    def _load_events(self) -> bool:
        path = log.active_events_path()
        try:
            st = path.stat()
        except OSError:
            return False
        sig = (str(path), st.st_size, st.st_mtime)
        if sig[0] != self._ev_sig[0] or st.st_size < self._ev_offset:
            self.events, self._ev_offset = [], 0
        if sig == self._ev_sig and st.st_size == self._ev_offset:
            return False
        self._ev_sig = sig
        try:
            with path.open("r", encoding="utf-8") as f:
                f.seek(self._ev_offset)
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            self.events.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
                self._ev_offset = f.tell()
        except OSError:
            return False
        self._refresh_active()
        return True

    def _load_snapshot(self) -> None:
        p = config.SNAPSHOT_PATH
        if not p.exists():
            return
        try:
            mt = p.stat().st_mtime
            if mt == self._snap_mt:
                return
            self._snap_mt = mt
            self.snapshot = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    def load(self) -> None:
        changed = self._load_events()
        if changed or self._reactor_live():
            self._load_snapshot()
        if not self._input_active:
            if config.GOAL_PATH.exists():
                try:
                    g = config.GOAL_PATH.read_text(encoding="utf-8").strip()
                    if g:
                        self.goal = g
                except OSError:
                    pass
        if self.events and not self._start_time:
            first = self.events[0]
            self._start_time = first.get("t", 0)

    def _refresh_active(self) -> None:
        self._math = self._loop = self._side = "—"
        self._reason = ""
        for e in reversed(self.events[-ACTIVE_SCAN:]):
            p = str(e.get("phase", ""))
            d = e.get("d", {})
            if p in PHASE_AGENT:
                agent = PHASE_AGENT[p]
                if agent in ("observer", "reflector", "mutator"):
                    if self._side == "—":
                        self._side = agent
                elif self._loop == "—":
                    self._loop = agent
            elif p == "schedule" and self._loop == "—":
                r = str(d.get("reason", ""))
                self._reason = r
                if r in SCHEDULE_AGENT:
                    self._loop = SCHEDULE_AGENT[r]
                if r in REFLECT_REASONS and self._side == "—":
                    self._side = "reflector"
            if p in MATH_PHASES and self._math == "—":
                self._math = p
            if self._math != "—" and self._loop != "—" and self._side != "—":
                break

    def handle_key(self) -> None:
        if not msvcrt.kbhit():
            return
        ch = msvcrt.getwch()
        if self._input_active:
            if ch in ("\r", "\n"):
                self._submit()
            elif ch == "\x1b":
                self._input_active = False
            elif ch in ("\x08", "\x7f"):
                if self._input_cur > 0:
                    self._input_buf = self._input_buf[:self._input_cur - 1] + self._input_buf[self._input_cur:]
                    self._input_cur -= 1
            elif ch == "\x03":
                self._input_active = False
            elif len(ch) == 1 and ch >= " ":
                self._input_buf = self._input_buf[:self._input_cur] + ch + self._input_buf[self._input_cur:]
                self._input_cur += 1
            return
        if ch in ("\r", "\n"):
            self._input_active = True
            self._input_buf = self.goal
            self._input_cur = len(self.goal)
        elif ch.lower() == "q":
            self.running = False
        elif ch == " ":
            log.set_paused(not log.paused())
        elif ch.lower() == "r" and not self._reactor_live():
            self._launch()

    def _submit(self) -> None:
        text = self._input_buf.strip()
        self._input_active = False
        if not text:
            return
        self.goal = text
        config.GOAL_PATH.write_text(text, encoding="utf-8")
        log.set_paused(False)
        if not self._reactor_live():
            self._launch()

    def _launch(self) -> None:
        import subprocess
        goal = self.goal.strip()
        if self._reactor_live() or not goal:
            return
        config.GOAL_PATH.write_text(goal, encoding="utf-8")
        log.clean_stale_lock()
        for p in (config.EVENTS_PATH, config.SNAPSHOT_PATH, config.DISABLED_PATH, config.GUI_MODE_PATH, config.PAUSE_PATH):
            if p.exists():
                p.unlink()
        self.events, self._ev_sig, self._ev_offset = [], ("", 0, 0.0), 0
        self._snap_mt, self.snapshot, self._start_time = 0.0, {}, 0.0
        log.set_paused(False)
        self.proc = subprocess.Popen(
            [sys.executable, "main.py", goal, "--backend", self.backend, "--event-budget", str(self.budget)],
            cwd=str(config.BASE_DIR), creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def check_proc(self) -> None:
        if self.proc and self.proc.poll() is not None:
            self.proc = None

    def _lessons(self) -> list[str]:
        import lessons
        items = lessons.recent(LESSONS_TAIL)
        return [f"[{e.get('score',5)}/10] {e.get('result','')}" for e in items]

    def _brief(self, phase: str, d: dict) -> str:
        match phase:
            case "schedule":
                s = d.get("step", "")
                return f"reason={d.get('reason','')}" + (f" step={s}" if s else "")
            case "action" | "actor":
                return f"{'ok' if d.get('ok') else 'FAIL'} {d.get('verb','')} {d.get('obs','')}" if d.get("verb") or d.get("obs") else str(d)[:80]
            case "plan":
                return f"mode={d.get('mode','')} steps={d.get('steps','')} done={d.get('done_when','')[:40]}"
            case "reflect":
                esc = f" →{d.get('escalate','')}" if d.get("escalate") else ""
                return f"lesson={str(d.get('lesson',''))[:80]}{esc}"
            case "observe":
                return f"focused={d.get('focused','')} chars={d.get('chars','')}"
            case "verify":
                return f"{d.get('verdict','')} {d.get('evidence','')[:60]}"
            case "fission":
                return f"power={d.get('power','')} completions={d.get('completions','')}"
            case "mutator" | "mutator.rejected":
                return f"action={d.get('action','')} file={d.get('filename','')} {d.get('reason','')}"
            case "stop":
                return f"reason={d.get('reason','')} work={d.get('work','')}"
            case "token_usage":
                return f"{d.get('role','')} total≈{d.get('total_est','')}"
            case "token_warning":
                return f"{d.get('role','')} {d.get('warning','')}"
            case _ if phase.startswith("plugin."):
                return f"decayed={d.get('decayed','')}" if "decay" in phase else f"ok={d.get('ok','')}"
            case _ if phase.endswith(".error"):
                return str(d.get("error", d))[:80]
            case _:
                return str(d)[:80] if d else ""

    def render(self) -> str:
        w, h = _size()
        w, h = max(80, w), max(24, h)
        s = self.snapshot
        out: list[str] = []

        # --- Header ---
        if log.paused():
            st, sc = "▐▐ PAUSED", _fg(255, 180, 60)
        elif self._reactor_live():
            st, sc = "● RUNNING", _fg(80, 220, 120)
        elif self.events:
            st, sc = "■ STOPPED", _fg(255, 90, 90)
        else:
            st, sc = "○ READY", _fg(140, 180, 255)

        trace = s.get("math_trace", [])
        latest = trace[-1] if trace else {}
        stag = float(latest.get("stag", s.get("stagnation", 0)))
        pid = float(latest.get("pid", s.get("pid_output", 0)))
        energy = float(latest.get("energy", s.get("energy", 1)))
        lx = float(latest.get("x", s.get("lorenz_x", 0)))
        ly = float(s.get("lorenz_y", 0))
        lz = float(s.get("lorenz_z", 0))
        power = float(s.get("power", 0))
        work = int(s.get("work_events", 0))
        ev_n = max(int(s.get("events", 0)), len(self.events))
        budget = int(s.get("budget", self.budget))
        failures = int(s.get("consecutive_failures", 0))
        completed = s.get("completed", [])
        fissions = len(completed)
        plan = s.get("plan", [])
        done_when = str(s.get("done_when", ""))
        wing = bool(latest.get("wing", s.get("wing_crossed", False)))
        focused = str(s.get("focused_window", ""))
        ts = s.get("token_state", {}) if isinstance(s.get("token_state"), dict) else {}
        tok_total = int(ts.get("cumulative_total_est", 0) or 0)
        tok_burn = float(ts.get("burn_rate_tpm", 0) or 0)
        tok_calls = int(ts.get("calls", 0) or 0)

        elapsed = _elapsed(self._start_time)
        goal = str(s.get("goal", "") or self.goal or "—")

        # Title + status
        title = f"{BOLD}{_fg(180, 210, 255)}ENDGAME-AI{RST}  {sc}{st}{RST}  {DIM}{time.strftime('%H:%M:%S')}{RST}  elapsed {elapsed}"
        out.append(_trunc(title, w + 40))  # extra for ANSI
        out.append(f"{DIM}{'─' * (w - 1)}{RST}")

        # Goal
        out.append(f"{BOLD}{_fg(200, 230, 255)}GOAL{RST} {_trunc(goal, w - 6)}")

        # Metrics row
        wing_s = f"  {_fg(255, 200, 0)}WING✦{RST}" if wing else ""
        metrics = (
            f"fissions {_fg(80,255,180)}{fissions}{RST}  "
            f"power {power:.4f}  work {work}/{budget}  "
            f"fails {failures}  events {ev_n}"
            f"{wing_s}"
        )
        out.append(metrics)

        # Token row
        tok = f"{DIM}tokens{RST} calls={tok_calls} total≈{tok_total} burn≈{tok_burn:.1f}/min"
        if focused:
            tok += f"  {DIM}focus{RST}={_trunc(focused, 30)}"
        out.append(tok)
        out.append(f"{DIM}{'─' * (w - 1)}{RST}")

        # Math gauges
        bar_w = w - 14
        out.append(f"{DIM}stag {RST}{_bar(stag, bar_w, _fg(255, 100, 80))} {stag:.3f}")
        out.append(f"{DIM}pid  {RST}{_bar(min(pid / config.PID_ROD_SCALE, 1), bar_w, _fg(80, 140, 255))} {pid:.3f}")
        out.append(f"{DIM}nrg  {RST}{_bar(min(energy / 3, 1), bar_w, _fg(120, 220, 140))} {energy:.3f}")
        lorenz_s = f"{DIM}lorenz{RST} x={lx:+.2f} y={ly:+.2f} z={lz:+.2f}"
        out.append(lorenz_s)
        out.append(f"{DIM}{'─' * (w - 1)}{RST}")

        # Agent chains (horizontal)
        def _chain_row(label: str, chain: tuple[str, ...], active: str) -> str:
            parts = [f"{DIM}{label}{RST} "]
            for name in chain:
                on = name == active
                if on:
                    parts.append(f"{_fg(255, 220, 80)}●{name}{RST} ")
                else:
                    parts.append(f"{DIM}○{name}{RST} ")
            return "".join(parts)

        out.append(_chain_row("math", MATH_CHAIN, self._math))
        out.append(_chain_row("loop", AGENT_CHAIN, self._loop))
        out.append(_chain_row("side", SIDE_AGENTS, self._side))
        if self._reason:
            out.append(f"{DIM}  sched_reason={RST}{self._reason}")
        out.append(f"{DIM}{'─' * (w - 1)}{RST}")

        # Plan
        if plan:
            done_n = sum(1 for p in plan if p.get("status") == "done")
            out.append(f"{BOLD}{_fg(200, 230, 255)}PLAN{RST} [{done_n}/{len(plan)}]  {DIM}done_when={RST}{_trunc(done_when, w - 30)}")
            max_steps = min(len(plan), max(3, (h - len(out) - EVENT_TAIL - 8)))
            for step in plan[:max_steps]:
                st_s = step.get("status", "pending")
                txt = str(step.get("text", ""))
                if st_s == "done":
                    mark, col = "✓", _fg(80, 220, 120)
                elif st_s == "active":
                    mark, col = "►", _fg(255, 220, 80)
                else:
                    mark, col = "·", DIM
                out.append(f" {col}{mark}{RST} {_trunc(txt, w - 5)}")
            if len(plan) > max_steps:
                out.append(f"   {DIM}…+{len(plan) - max_steps} more{RST}")
        else:
            out.append(f"{DIM}no plan{RST}")

        if completed:
            out.append(f"{DIM}last fission:{RST} {_trunc(completed[-1], w - 15)}")
        out.append(f"{DIM}{'─' * (w - 1)}{RST}")

        # Events
        out.append(f"{BOLD}{_fg(180, 210, 255)}EVENTS{RST} (last {EVENT_TAIL})")
        tail = [e for e in self.events if e.get("phase") in WORK_PHASES][-EVENT_TAIL:]
        for e in tail:
            n, ph = e.get("n", 0), str(e.get("phase", ""))
            brief = self._brief(ph, e.get("d", {}))
            line = f" {DIM}{n:>4}{RST} {ph:<18} {brief}"
            out.append(_trunc(line, w))
        out.append(f"{DIM}{'─' * (w - 1)}{RST}")

        # Lessons
        lessons = self._lessons()
        if lessons:
            out.append(f"{BOLD}{_fg(180, 200, 160)}LESSONS{RST} (last {len(lessons)})")
            for ln in lessons:
                out.append(f" {DIM}{_trunc(ln, w - 3)}{RST}")
            out.append(f"{DIM}{'─' * (w - 1)}{RST}")

        # Input field
        if self._input_active:
            bc = _fg(100, 180, 255)
            field = self._input_buf + "▌"
        else:
            bc = DIM
            field = self.goal or "(press Enter to set goal)"
        out.append(f"{bc}┌{'─' * (w - 3)}┐{RST}")
        out.append(f"{bc}│{RST} {_trunc(field, w - 5)} {bc}│{RST}")
        out.append(f"{bc}└{'─' * (w - 3)}┘{RST}")

        # Keybind bar
        keys = f"{DIM}Enter{RST}=goal  {DIM}Space{RST}=pause  {DIM}r{RST}=restart  {DIM}q{RST}=quit"
        out.append(keys)

        # Pad to height
        while len(out) < h:
            out.append("")
        return "\n".join(_pad(line, w) for line in out[:h])

    def _paint(self, frame: str) -> None:
        if not self._in_alt:
            _write(ALT_ON + (SHOW_CUR if self._input_active else HIDE_CUR))
            self._in_alt = True
        _write(f"\x1b[H{frame}")

    def run_loop(self) -> None:
        try:
            if self._autostart and self.goal.strip() and not self._reactor_live():
                self._launch()
            while self.running:
                self.load()
                self.handle_key()
                self.check_proc()
                self._paint(self.render())
                time.sleep(REFRESH)
        except KeyboardInterrupt:
            pass
        finally:
            if self.proc:
                self.proc.terminate()
            if self._in_alt:
                _write(ALT_OFF + SHOW_CUR)


def run_tui(goal: str = "", backend: str = "lmstudio", budget: int = 20, autostart: bool = True) -> None:
    TUI(goal=goal, backend=backend, budget=budget, autostart=autostart).run_loop()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(prog="endgame-ai")
    p.add_argument("goal", nargs="?", default="")
    p.add_argument("--backend", choices=["lmstudio", "acp"], default="lmstudio")
    p.add_argument("--event-budget", type=int, default=20)
    p.add_argument("--no-autostart", action="store_true")
    a = p.parse_args()
    run_tui(goal=a.goal, backend=a.backend, budget=a.event_budget, autostart=not a.no_autostart)
