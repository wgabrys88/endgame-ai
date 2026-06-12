"""Multi-agent reactor TUI — bars + events + spectrogram for Windows Terminal Preview."""
from __future__ import annotations

import ctypes
import glob
import json
import msvcrt
import os
import time
from pathlib import Path
from typing import Any

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║ CONFIGURATION — tune layout and behavior here only                         ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

# Paths
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
EVENTS_GLOB = "events-child-*.jsonl"
MAIN_EVENTS = "events.jsonl"

# Layout — 2x zoom-out on 1080p gives ~108×86 usable
PANEL_WIDTH = 106
PERSONALITY_WIDTH = 16
BAR_WIDTH = 4
AGENT_EVENT_ROWS = 5                       # recent work events shown (includes mutator)
HISTORY_LEN = 90                           # spectrogram samples (fills width)
SPEC_WIDTH = 14                            # spectrogram strip (narrower = more event text)
PHASE_WIDTH = 14

# Timing
REFRESH_INTERVAL = 0.12
SCAN_INTERVAL = 2.0
MAX_EVENTS_BUFFER = 600

# Reactor roster — keep in sync with reactor.py
ROSTER: dict[str, str] = {
    "n1": "git_expert",
    "n2": "implementor",
    "n3": "doc_inspector",
    "n4": "comms_operator",
    "n5": "quality_critic",
}

# Phases considered "work"
WORK_PHASES = frozenset({
    "schedule", "plan", "actor", "action", "observe", "verify", "reflect",
    "mutation", "personality.evolve", "fission", "fission_blocked", "fission_sustain", "goal_change",
    "start", "stop", "mutator", "mutator.error", "mutator.rejected",
    "planner.error", "actor.error", "verifier.error", "reflector.error",
})

# Spectrogram color ramps (5 intensity levels, low → high)
RAMP_STAG = [
    (20, 20, 30), (80, 30, 30), (160, 50, 30), (220, 70, 30), (255, 100, 60),
]
RAMP_NRG = [
    (20, 20, 30), (30, 80, 40), (40, 140, 60), (50, 200, 80), (80, 255, 120),
]
RAMP_PID = [
    (20, 20, 30), (30, 40, 100), (50, 70, 170), (70, 100, 220), (100, 140, 255),
]

SPEC_CHARS = " ·:+#"

# Normalization
STAG_MAX = 1.0
NRG_MAX = 3.0
PID_MAX = 5.0

# UI colors
CLR_ALIVE = (80, 220, 120)
CLR_DEAD = (255, 80, 80)
CLR_STAG = (255, 100, 80)
CLR_NRG = (120, 220, 140)
CLR_PID = (80, 140, 255)
CLR_FISSION = (100, 255, 180)
CLR_DIM = (80, 80, 100)
CLR_HEADER = (200, 220, 255)
CLR_BORDER = (60, 60, 80)
CLR_PHASE = (140, 170, 200)
CLR_DATA = (180, 180, 200)

# Box drawing
BOX_TL, BOX_TR = "+", "+"
BOX_BL, BOX_BR = "+", "+"
BOX_H, BOX_V = "-", "|"
BOX_ML, BOX_MR = "+", "+"
BOX_SL, BOX_SR = "+", "+"
BOX_SH = "-"

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║ END CONFIGURATION                                                          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

# Win32 console setup
_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_hout = _k32.GetStdHandle(-11)
_m = ctypes.c_ulong()
_k32.GetConsoleMode(_hout, ctypes.byref(_m))
_k32.SetConsoleMode(_hout, _m.value | 0x0004 | 0x0008)

RST = "\x1b[0m"
BOLD = "\x1b[1m"


def _w(t: str) -> None:
    n = ctypes.c_ulong()
    _k32.WriteConsoleW(_hout, t, len(t), ctypes.byref(n), None)


def _fg(r: int, g: int, b: int) -> str:
    return f"\x1b[38;2;{r};{g};{b}m"


def _vlen(s: str) -> int:
    n = 0
    i = 0
    while i < len(s):
        if s[i] == "\x1b":
            j = s.find("m", i)
            i = j + 1 if j != -1 else i + 1
        else:
            n += 1
            i += 1
    return n


def _trunc(s: str, w: int, suffix: str = "…") -> str:
    if w <= 0:
        return ""
    vis = 0
    out: list[str] = []
    i = 0
    while i < len(s):
        if s[i] == "\x1b":
            j = s.find("m", i)
            if j != -1:
                out.append(s[i:j + 1])
                i = j + 1
                continue
        if vis >= w:
            if suffix and vis >= w:
                out.append(suffix)
            break
        out.append(s[i])
        vis += 1
        i += 1
    return "".join(out)


def _console_width() -> int:
    class _COORD(ctypes.Structure):
        _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

    class _SMALL_RECT(ctypes.Structure):
        _fields_ = [
            ("Left", ctypes.c_short), ("Top", ctypes.c_short),
            ("Right", ctypes.c_short), ("Bottom", ctypes.c_short),
        ]

    class _CSBI(ctypes.Structure):
        _fields_ = [
            ("dwSize", _COORD), ("dwCursorPosition", _COORD),
            ("wAttributes", ctypes.c_ushort), ("srWindow", _SMALL_RECT),
            ("dwMaximumWindowSize", _COORD),
        ]

    csbi = _CSBI()
    if _k32.GetConsoleScreenBufferInfo(_hout, ctypes.byref(csbi)):
        width = csbi.srWindow.Right - csbi.srWindow.Left + 1
        return max(PANEL_WIDTH, min(width, 140))
    return PANEL_WIDTH


def _bar(v: float, w: int, color: tuple[int, int, int]) -> str:
    w = max(2, w)
    f = max(0, min(w, int(v * w)))
    return _fg(*color) + "=" * f + _fg(*CLR_DIM) + "-" * (w - f) + RST


def _spec_cell(value: float, ramp: list[tuple[int, int, int]]) -> str:
    idx = min(4, max(0, int(value * 4.999)))
    r, g, b = ramp[idx]
    return f"\x1b[48;2;{r};{g};{b}m "


def _spec_row(history: list[float], width: int, ramp: list[tuple[int, int, int]]) -> str:
    if len(history) >= width:
        data = history[-width:]
    else:
        data = [0.0] * (width - len(history)) + history
    return "".join(_spec_cell(v, ramp) for v in data) + RST


# ─── Agent tracking ──────────────────────────────────────────────────────────

class Agent:
    __slots__ = ("path", "personality", "events", "_off", "_mt",
                 "alive", "fissions", "stag", "pid_val", "energy", "last_phase",
                 "hist_stag", "hist_nrg", "hist_pid")

    def __init__(self, path: Path, personality: str):
        self.path = path
        self.personality = personality
        self.events: list[dict] = []
        self._off = 0
        self._mt = 0.0
        self.alive = True
        self.fissions = 0
        self.stag = 0.0
        self.pid_val = 0.0
        self.energy = 1.0
        self.last_phase = ""
        self.hist_stag: list[float] = []
        self.hist_nrg: list[float] = []
        self.hist_pid: list[float] = []

    def poll(self) -> None:
        try:
            st = self.path.stat()
        except OSError:
            return
        if st.st_mtime == self._mt and st.st_size == self._off:
            return
        self._mt = st.st_mtime
        if st.st_size < self._off:
            self._off = 0
        try:
            with self.path.open("r", encoding="utf-8") as f:
                f.seek(self._off)
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    self.events.append(ev)
                    self._ingest(ev)
                self._off = f.tell()
        except OSError:
            pass
        if len(self.events) > MAX_EVENTS_BUFFER:
            self.events = self.events[-MAX_EVENTS_BUFFER:]

    def _ingest(self, ev: dict) -> None:
        ph = ev.get("phase", "")
        d = ev.get("d", {}) or {}
        self.last_phase = ph
        if ph == "stop":
            self.alive = False
        elif ph == "fission":
            self.fissions += 1
        elif ph == "stagnation":
            self.stag = float(d.get("stag", self.stag))
            self.hist_stag.append(min(1.0, self.stag / STAG_MAX))
            if len(self.hist_stag) > HISTORY_LEN * 2:
                self.hist_stag = self.hist_stag[-HISTORY_LEN:]
        elif ph == "pid":
            self.pid_val = float(d.get("pid", self.pid_val))
            self.hist_pid.append(min(1.0, self.pid_val / PID_MAX))
            if len(self.hist_pid) > HISTORY_LEN * 2:
                self.hist_pid = self.hist_pid[-HISTORY_LEN:]
        elif ph == "lorenz":
            self.energy = float(d.get("energy", self.energy))
            self.hist_nrg.append(min(1.0, self.energy / NRG_MAX))
            if len(self.hist_nrg) > HISTORY_LEN * 2:
                self.hist_nrg = self.hist_nrg[-HISTORY_LEN:]
        elif ph == "math" and isinstance(d, dict):
            stag = d.get("stagnation", {})
            lorenz = d.get("lorenz", {})
            pid = d.get("pid", {})
            if isinstance(stag, dict) and "stag" in stag:
                self.stag = float(stag.get("stag", self.stag))
                self.hist_stag.append(min(1.0, self.stag / STAG_MAX))
            if isinstance(pid, dict) and "pid" in pid:
                self.pid_val = float(pid.get("pid", self.pid_val))
                self.hist_pid.append(min(1.0, self.pid_val / PID_MAX))
            if isinstance(lorenz, dict) and "energy" in lorenz:
                self.energy = float(lorenz.get("energy", self.energy))
                self.hist_nrg.append(min(1.0, self.energy / NRG_MAX))
            if len(self.hist_stag) > HISTORY_LEN * 2:
                self.hist_stag = self.hist_stag[-HISTORY_LEN:]
            if len(self.hist_pid) > HISTORY_LEN * 2:
                self.hist_pid = self.hist_pid[-HISTORY_LEN:]
            if len(self.hist_nrg) > HISTORY_LEN * 2:
                self.hist_nrg = self.hist_nrg[-HISTORY_LEN:]

    def recent_work(self, n: int) -> list[dict]:
        return [e for e in self.events if e.get("phase") in WORK_PHASES][-n:]


# ─── TUI ─────────────────────────────────────────────────────────────────────

class TUI:
    def __init__(self):
        self.agents: dict[str, Agent] = {}
        self.running = True
        self._last_scan = 0.0
        self._start = time.time()

    def _scan(self) -> None:
        now = time.time()
        if now - self._last_scan < SCAN_INTERVAL:
            return
        self._last_scan = now
        for fp in glob.glob(str(BASE_DIR / EVENTS_GLOB)):
            if fp not in self.agents:
                p = Path(fp)
                slot = p.stem.replace("events-child-", "")
                pers = ROSTER.get(slot, slot)
                self.agents[fp] = Agent(p, pers)
        main = str(BASE_DIR / MAIN_EVENTS)
        if os.path.exists(main) and main not in self.agents:
            self.agents[main] = Agent(Path(main), "main")

    def _poll(self) -> None:
        for a in self.agents.values():
            a.poll()

    def _sorted(self) -> list[Agent]:
        return sorted(self.agents.values(), key=lambda a: (not a.alive, a.personality))

    def _brief(self, ph: str, d: dict, max_w: int = 0) -> str:
        if not d:
            return ""
        match ph:
            case "schedule":
                if d.get("reason") == "plan_cooldown":
                    text = f"cooldown {d.get('wait', '')}s"
                else:
                    text = f"reason={d.get('reason', '')}"
            case "action" | "actor":
                ok = "ok" if d.get("ok") else "FAIL"
                v = d.get("verb", d.get("conclusion", ""))
                o = d.get("obs", "")
                text = f"{ok} {v} {o}".strip() if v or o else str(d)
            case "plan":
                reason = d.get("reason", "")
                if d.get("mode") == "rejected" and reason:
                    text = f"rejected {reason[:72]}"
                else:
                    text = f"mode={d.get('mode', '')} steps={d.get('steps', '')} {d.get('done_when', '')}"
            case "verify":
                text = f"{d.get('verdict', '')} {d.get('evidence', '')}"
            case "fission":
                text = f"power={d.get('power', '')} completions={d.get('completions', '')}"
            case "reflect":
                text = f"{d.get('diagnosis', d.get('rule', ''))}"
            case "mutation" | "mutator" | "personality.evolve":
                text = f"{d.get('action', d.get('personality', ''))} {d.get('filename', d.get('appended', d.get('target', '')))}"
            case "mutator.rejected":
                text = f"rejected {d.get('filename', '')} {d.get('reason', '')}"
            case "mutator.error":
                text = f"error {d.get('error', '')}"
            case "stop":
                text = f"reason={d.get('reason', '')}"
            case _ if ph.endswith(".error"):
                text = str(d.get("error", d))
            case _:
                text = str(d)
        return _trunc(text, max_w) if max_w > 0 else text

    def render(self) -> str:
        W = _console_width()
        inner = W - 4
        agents = self._sorted()
        bc = _fg(*CLR_BORDER)

        def row(content: str) -> str:
            t = _trunc(content, inner)
            gap = max(0, inner - _vlen(t))
            return f"{bc}{BOX_V}{RST} {t}{' ' * gap} {bc}{BOX_V}{RST}"

        lines: list[str] = []

        # Top border
        lines.append(f"{bc}{BOX_TL}{BOX_H * (W - 2)}{BOX_TR}{RST}")

        # Header
        alive = sum(1 for a in agents if a.alive)
        total = len(agents)
        total_f = sum(a.fissions for a in agents)
        elapsed = time.time() - self._start
        fpm = total_f * 60.0 / max(elapsed, 1)
        k = total_f / max(alive, 1)
        avg_stag = sum(a.stag for a in agents) / max(total, 1)

        dot_c = _fg(*CLR_ALIVE) if alive else _fg(*CLR_DEAD)
        dot = "*" if alive else "x"
        paused = (BASE_DIR / "pause").exists()
        mode = f"{_fg(*CLR_STAG)}MATH-ONLY{RST}" if paused else f"{_fg(*CLR_ALIVE)}LIVE{RST}"
        hdr = (
            f"{BOLD}{_fg(*CLR_HEADER)}REACTOR{RST} "
            f"{dot_c}{dot} {alive}/{total}{RST}  "
            f"[{mode}]  "
            f"k={k:.1f}  "
            f"{_fg(*CLR_FISSION)}F={total_f}{RST}  "
            f"{fpm:.1f}/m  "
            f"avg_stag={avg_stag:.2f}  "
            f"{self._elapsed(elapsed)}  "
            f"{time.strftime('%H:%M:%S')}"
        )
        lines.append(row(hdr))
        lines.append(f"{bc}{BOX_ML}{BOX_H * (W - 2)}{BOX_MR}{RST}")

        # Each agent
        for idx, agent in enumerate(agents):
            # Row 1: identity + bars + fission
            adot = f"{_fg(*CLR_ALIVE)}*{RST}" if agent.alive else f"{_fg(*CLR_DEAD)}x{RST}"
            pers = agent.personality[:PERSONALITY_WIDTH].ljust(PERSONALITY_WIDTH)
            stag_b = f"s{_bar(agent.stag, BAR_WIDTH, CLR_STAG)}"
            nrg_b = f"n{_bar(min(agent.energy / NRG_MAX, 1), BAR_WIDTH, CLR_NRG)}"
            pid_b = f"p{_bar(min(abs(agent.pid_val) / PID_MAX, 1), BAR_WIDTH, CLR_PID)}"
            fiss = f"{_fg(*CLR_FISSION)}F={agent.fissions}{RST}"

            lines.append(row(f"{pers} {adot} {stag_b} {nrg_b} {pid_b} {fiss}"))

            # Rows 2+: events (left) + spectrogram (right)
            spec_w = SPEC_WIDTH
            val_w = 5
            text_w = max(24, inner - spec_w - val_w - 3 - PHASE_WIDTH)
            recent = agent.recent_work(AGENT_EVENT_ROWS)

            s_strip = _spec_row(agent.hist_stag, spec_w, RAMP_STAG)
            n_strip = _spec_row(agent.hist_nrg, spec_w, RAMP_NRG)
            p_strip = _spec_row(agent.hist_pid, spec_w, RAMP_PID)
            s_val = f"{_fg(*CLR_STAG)}{agent.stag:4.2f}{RST}"
            n_val = f"{_fg(*CLR_NRG)}{agent.energy:4.1f}{RST}"
            p_val = f"{_fg(*CLR_PID)}{agent.pid_val:4.1f}{RST}"
            specs = [f"{s_strip} {s_val}", f"{n_strip} {n_val}", f"{p_strip} {p_val}"]

            for i in range(AGENT_EVENT_ROWS):
                if i < len(recent):
                    ph = recent[i].get("phase", "")
                    brief = self._brief(ph, recent[i].get("d", {}), text_w)
                    phase = _trunc(ph, PHASE_WIDTH).ljust(PHASE_WIDTH)
                    left = f" {_fg(*CLR_PHASE)}{phase}{RST} {_fg(*CLR_DATA)}{brief}{RST}"
                else:
                    left = ""
                left_trunc = _trunc(left, text_w + PHASE_WIDTH + 2)
                pad = max(0, inner - spec_w - val_w - 2 - _vlen(left_trunc))
                right = specs[i] if i < len(specs) else ""
                lines.append(row(f"{left_trunc}{chr(32) * pad} {right}"))

            # Separator
            if idx < len(agents) - 1:
                lines.append(f"{bc}{BOX_SL}{BOX_SH * (W - 2)}{BOX_SR}{RST}")

        # Footer
        lines.append(f"{bc}{BOX_ML}{BOX_H * (W - 2)}{BOX_MR}{RST}")
        foot = (
            f"avg_stag={avg_stag:.2f}  "
            f"k={k:.2f}  "
            f"{fpm:.1f}F/m  "
            f"{alive}/{total} alive  "
            f"uptime={self._elapsed(elapsed)}"
        )
        lines.append(row(foot))
        lines.append(f"{bc}{BOX_BL}{BOX_H * (W - 2)}{BOX_BR}{RST}")

        return "\x1b[H" + "\r\n".join(ln + "\x1b[K" for ln in lines) + "\x1b[J"

    @staticmethod
    def _elapsed(s: float) -> str:
        if s < 60:
            return f"{s:.0f}s"
        if s < 3600:
            return f"{s / 60:.1f}m"
        return f"{s / 3600:.1f}h"

    def run(self) -> None:
        import log
        import subprocess, sys
        log.cleanup_runtime()
        _w("\x1b[?1049h\x1b[?25l")
        _w("\x1b]0;endgame-ai reactor\x07")
        pause_path = BASE_DIR / "pause"
        # Start in paused/math-only mode
        pause_path.write_text("", encoding="utf-8")
        # Launch reactor
        if True:  # always launch reactor
            env = os.environ.copy()
            env["ENDGAME_BOOTSTRAPPED"] = "1"
            self._reactor_proc = subprocess.Popen(
                [sys.executable, "reactor.py"],
                cwd=str(BASE_DIR),
                env=env,
                creationflags=0x08000000,
            )
        else:
            self._reactor_proc = None
        try:
            while self.running:
                self._scan()
                self._poll()
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch in ("q", "Q", "\x03"):
                        break
                    elif ch == " ":
                        if pause_path.exists():
                            pause_path.unlink(missing_ok=True)
                        else:
                            pause_path.write_text("", encoding="utf-8")
                _w(self.render())
                agents = self._sorted()
                alive = sum(1 for a in agents if a.alive)
                total = len(agents) or 1
                _w(f"\x1b]9;4;1;{alive * 100 // total}\x07")
                time.sleep(REFRESH_INTERVAL)
        except KeyboardInterrupt:
            pass
        finally:
            _w("\x1b]9;4;0;0\x07")
            _w("\x1b[?1049l\x1b[?25h")
            if self._reactor_proc and self._reactor_proc.poll() is None:
                # Kill entire process tree (reactor + its children)
                os.system(f"taskkill /F /T /PID {self._reactor_proc.pid} >nul 2>&1")


if __name__ == "__main__":
    TUI().run()
