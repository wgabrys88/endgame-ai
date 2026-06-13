"""TUI — fixed 45-line display. Shows personas with their internal agents."""
from __future__ import annotations
import ctypes
import glob
import json
import msvcrt
import os
import time
from pathlib import Path
from typing import Any

import comms
import config

BASE_DIR = config.BASE_DIR
TARGET_HEIGHT = 45
REFRESH_INTERVAL = 0.10
SCAN_INTERVAL = 2.0
MAX_EVENTS = 300

# Internal agents each persona contains
INTERNAL_AGENTS = ["scheduler", "planner", "actor", "verifier", "fission_judge"]

CLR_ALIVE = (80, 220, 120)
CLR_DEAD = (255, 80, 80)
CLR_HEADER = (200, 220, 255)
CLR_BORDER = (55, 58, 78)
CLR_PHASE = (140, 170, 200)
CLR_DATA = (180, 180, 200)
CLR_BUS = (160, 190, 230)
CLR_DIM = (80, 80, 100)
CLR_INPUT = (255, 240, 200)
CLR_PRI = (255, 180, 80)
CLR_STAG = (255, 100, 80)
CLR_FISSION = (100, 255, 180)

BOX_TL, BOX_TR, BOX_BL, BOX_BR = "╔", "╗", "╚", "╝"
BOX_H, BOX_V = "═", "║"
BOX_ML, BOX_MR, BOX_SL, BOX_SR, BOX_SH = "╠", "╣", "╟", "╢", "─"

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
    n = i = 0
    while i < len(s):
        if s[i] == "\x1b":
            j = s.find("m", i)
            i = (j + 1) if j != -1 else i + 1
        else:
            n += 1
            i += 1
    return n


def _trunc(s: str, w: int) -> str:
    if w <= 0:
        return ""
    vis = i = 0
    while i < len(s):
        if s[i] == "\x1b":
            j = s.find("m", i)
            if j != -1:
                i = j + 1
                continue
        vis += 1
        i += 1
    if vis <= w:
        return s
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
        if vis >= w - 1:
            break
        out.append(s[i])
        vis += 1
        i += 1
    out.append("…")
    return "".join(out)


def _console_width() -> int:
    class _COORD(ctypes.Structure):
        _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

    class _SR(ctypes.Structure):
        _fields_ = [("L", ctypes.c_short), ("T", ctypes.c_short), ("R", ctypes.c_short), ("B", ctypes.c_short)]

    class _CSBI(ctypes.Structure):
        _fields_ = [("sz", _COORD), ("cp", _COORD), ("a", ctypes.c_ushort), ("w", _SR), ("mx", _COORD)]

    csbi = _CSBI()
    if _k32.GetConsoleScreenBufferInfo(_hout, ctypes.byref(csbi)):
        return max(80, min(csbi.w.R - csbi.w.L + 1, 160))
    return 120


def _bar(v: float, w: int, clr: tuple) -> str:
    w = max(2, w)
    f = max(0, min(w, int(v * w)))
    return _fg(*clr) + "█" * f + _fg(*CLR_DIM) + "░" * (w - f) + RST


# --- Slot view ---

class Slot:
    __slots__ = ("path", "slot_id", "persona", "events", "_off", "_mt",
                 "alive", "fissions", "last_phase", "priority", "stagnation",
                 "agent_states")

    def __init__(self, path: Path, slot_id: int):
        self.path = path
        self.slot_id = slot_id
        self.persona = ""
        self.events: list[dict] = []
        self._off = 0
        self._mt = 0.0
        self.alive = True
        self.fissions = 0
        self.last_phase = ""
        self.priority = 0
        self.stagnation = 0.0
        # Track which agents have fired
        self.agent_states: dict[str, str] = {a: "idle" for a in INTERNAL_AGENTS}

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
        if len(self.events) > MAX_EVENTS:
            self.events = self.events[-MAX_EVENTS:]

    def _ingest(self, ev: dict) -> None:
        ph = ev.get("phase", "")
        d = ev.get("d") or {}
        self.last_phase = ph
        if ph == "start":
            self.persona = str(d.get("personality", self.persona))
        elif ph == "fission":
            self.fissions += 1
            self.agent_states["fission_judge"] = "✓"
        elif ph == "stop":
            self.alive = False
        elif ph == "interrupt":
            self.priority = int(d.get("pri", self.priority))
        elif ph == "pressure":
            self.stagnation = float(d.get("stagnation", 0))
        # Update agent states
        if ph == "schedule":
            self.agent_states = {a: "idle" for a in INTERNAL_AGENTS}
            self.agent_states["scheduler"] = "✓"
        elif ph.startswith("planner"):
            self.agent_states["planner"] = "⟳" if "pending" in ph else ("✗" if "error" in ph else "✓")
        elif ph in ("actor", "action"):
            ok = (d.get("ok", True)) if d else True
            self.agent_states["actor"] = "✓" if ok else "✗"
        elif ph.startswith("verif") or ph == "verify":
            v = d.get("verdict", "")
            self.agent_states["verifier"] = "✓" if v == "confirmed" else "✗"
        elif ph.startswith("fission"):
            self.agent_states["fission_judge"] = "✓" if ph == "fission" else "–"

    @property
    def active_agent(self) -> str:
        ph = self.last_phase
        if not ph or ph == "start":
            return "booting"
        if ph.startswith("planner"):
            return "planner"
        if ph in ("actor", "action"):
            return "actor"
        if ph.startswith("verif") or ph == "verify":
            return "verifier"
        if ph.startswith("fission"):
            return "fission"
        if ph == "interrupt":
            return "INTERRUPT"
        if ph == "pressure":
            return "math"
        if ph == "llm_retry" or ph == "llm_fail":
            return "llm…"
        if ph == "schedule":
            return "scheduler"
        return ph[:10]

    def agent_bar(self) -> str:
        """Compact display of all internal agent states."""
        parts = []
        for a in INTERNAL_AGENTS:
            st = self.agent_states.get(a, "idle")
            short = a[0].upper()  # S P A V F
            if st == "✓":
                parts.append(f"{_fg(*CLR_ALIVE)}{short}{RST}")
            elif st == "⟳":
                parts.append(f"{_fg(*CLR_PRI)}{short}{RST}")
            elif st == "✗":
                parts.append(f"{_fg(*CLR_DEAD)}{short}{RST}")
            else:
                parts.append(f"{_fg(*CLR_DIM)}{short}{RST}")
        return "".join(parts)


# --- TUI ---

class TUI:
    def __init__(self):
        self.slots: dict[str, Slot] = {}
        self.running = True
        self._last_scan = 0.0
        self._start = time.time()
        self._input_buf = ""
        self._bus_chat: list[dict] = []
        self._bus_events: list[dict] = []
        self._reactor_proc = None
        self._session_dir: str = ""

    def _scan(self) -> None:
        now = time.time()
        if now - self._last_scan < SCAN_INTERVAL:
            return
        self._last_scan = now
        # Find session dir (most recent)
        sessions = sorted(glob.glob(str(BASE_DIR / "sessions" / "*")))
        if sessions:
            sd = sessions[-1]
            self._session_dir = sd
            for fp in glob.glob(os.path.join(sd, "events-child-s*.jsonl")):
                if fp not in self.slots:
                    p = Path(fp)
                    sid = int(p.stem.replace("events-child-s", ""))
                    self.slots[fp] = Slot(p, sid)

    def _poll(self) -> None:
        try:
            comms.drain_inject()
        except Exception:
            pass
        self._bus_chat = comms.read_chat(40)
        self._bus_events = comms.read_events(20)
        for s in self.slots.values():
            s.poll()

    def _sorted(self) -> list[Slot]:
        return sorted(self.slots.values(), key=lambda s: s.slot_id)

    def render(self) -> str:
        W = _console_width()
        inner = W - 4
        slots = self._sorted()
        bc = _fg(*CLR_BORDER)

        # Ensure 5 display slots (even if empty)
        display_slots: list[Slot | None] = [None] * 5
        for s in slots:
            if 1 <= s.slot_id <= 5:
                display_slots[s.slot_id - 1] = s

        def row(content: str) -> str:
            t = _trunc(content, inner)
            gap = max(0, inner - _vlen(t))
            return f"{bc}{BOX_V}{RST} {t}{' ' * gap} {bc}{BOX_V}{RST}"

        lines: list[str] = []
        lines.append(f"{bc}{BOX_TL}{BOX_H * (W - 2)}{BOX_TR}{RST}")

        # Header (line 2)
        alive = sum(1 for s in slots if s.alive)
        total_f = sum(s.fissions for s in slots)
        elapsed = time.time() - self._start
        hdr = (f"{BOLD}{_fg(*CLR_HEADER)}REACTOR{RST} {alive}/5 slots  "
               f"{_fg(*CLR_FISSION)}F={total_f}{RST}  "
               f"{self._elapsed(elapsed)}  {time.strftime('%H:%M:%S')}")
        lines.append(row(hdr))
        lines.append(f"{bc}{BOX_ML}{BOX_H * (W - 2)}{BOX_MR}{RST}")

        # Personas: 5 slots × 5 lines each (header + 2 events + agents + separator) = 25-29
        # Actually: header + agent_bar + 2 events = 4 lines per slot, + 4 separators = 24 lines
        for idx, slot in enumerate(display_slots):
            if slot is None:
                # Empty slot
                lines.append(row(f"{_fg(*CLR_DIM)}s{idx+1} {'(empty)':14} ○{RST}"))
                lines.append(row(f" {_fg(*CLR_DIM)}S P A V F{RST}"))
                lines.append(row(""))
                lines.append(row(""))
            else:
                # Header line
                dot = f"{_fg(*CLR_ALIVE)}●{RST}" if slot.alive else f"{_fg(*CLR_DEAD)}○{RST}"
                persona = (slot.persona or "?")[:14].ljust(14)
                stag_bar = _bar(slot.stagnation, 4, CLR_STAG)
                pri = f"P{slot.priority}" if slot.priority > 0 else "  "
                active = slot.active_agent
                fiss = f"{_fg(*CLR_FISSION)}F={slot.fissions}{RST}" if slot.fissions else ""
                header = f"s{slot.slot_id} {persona} {dot} [{_fg(*CLR_PHASE)}{active:10}{RST}] {stag_bar} {pri} {fiss}"
                lines.append(row(_trunc(header, inner)))

                # Agent pipeline bar
                lines.append(row(f" {slot.agent_bar()} {_fg(*CLR_DIM)}stag={slot.stagnation:.2f}{RST}"))

                # 2 recent events
                recent = slot.recent(2)
                for i in range(2):
                    if i < len(recent):
                        ev = recent[i]
                        ph = ev.get("phase", "")[:12].ljust(12)
                        brief = self._brief(ev.get("phase", ""), ev.get("d") or {}, inner - 16)
                        lines.append(row(f" {_fg(*CLR_PHASE)}{ph}{RST} {_fg(*CLR_DATA)}{brief}{RST}"))
                    else:
                        lines.append(row(""))

            if idx < 4:
                lines.append(f"{bc}{BOX_SL}{BOX_SH * (W - 2)}{BOX_SR}{RST}")

        # Bus (6 lines: header + 5 messages)
        lines.append(f"{bc}{BOX_ML}{BOX_H * (W - 2)}{BOX_MR}{RST}")
        lines.append(row(f"{BOLD}{_fg(*CLR_BUS)}BUS{RST}"))
        chat = self._bus_chat[-5:]
        for i in range(5):
            if i < len(chat):
                e = chat[i]
                lines.append(row(f"{_fg(*CLR_BUS)}@{str(e.get('from', '?'))[:12]:12} {str(e.get('text', ''))[:inner-16]}{RST}"))
            else:
                lines.append(row(""))

        # Input (3 lines: separator + prompt + help)
        lines.append(f"{bc}{BOX_ML}{BOX_H * (W - 2)}{BOX_MR}{RST}")
        cursor = "▌" if int(time.time() * 2) % 2 else " "
        lines.append(row(f"{_fg(*CLR_INPUT)}@human> {self._input_buf}{cursor}{RST}"))
        lines.append(row(f"{_fg(*CLR_DIM)}Enter=send  Space=pause  q=quit{RST}"))
        lines.append(f"{bc}{BOX_BL}{BOX_H * (W - 2)}{BOX_BR}{RST}")

        # Enforce TARGET_HEIGHT
        while len(lines) < TARGET_HEIGHT:
            lines.append("\x1b[K")
        lines = lines[:TARGET_HEIGHT]
        return "\x1b[H" + "\r\n".join(ln + "\x1b[K" for ln in lines)

    def recent(self, slot: Slot, n: int) -> list[dict]:
        """Get last n non-trivial events."""
        return [e for e in slot.events if e.get("phase") not in ("start", "pressure")][-n:]

    def _brief(self, ph: str, d: dict, max_w: int) -> str:
        if not d:
            return ""
        match ph:
            case "plan":
                t = f"mode={d.get('mode', '')} steps={d.get('steps', '')} {d.get('done_when', '')}"
            case "actor" | "action":
                t = f"{'ok' if d.get('ok') else 'FAIL'} {d.get('obs', '')}"
            case "verify":
                t = f"{d.get('verdict', '')} {d.get('evidence', '')}"
            case "interrupt":
                t = f"⚡ @{d.get('from', '?')} pri={d.get('pri', '')} {d.get('text', '')}"
            case "planner.pending":
                t = "waiting LLM..."
            case "llm_retry":
                t = f"retry #{d.get('attempt', '')} {d.get('error', '')}"
            case "fission":
                t = f"fissions={d.get('fissions', '')} {d.get('completed', '')}"
            case "start":
                t = f"{d.get('personality', '')} [{d.get('profile', '')}]"
            case "schedule":
                t = f"→ {d.get('next', '')} ({d.get('reason', '')})"
            case _:
                t = str(d)[:max_w]
        return _trunc(t.replace("\n", " "), max_w)

    @staticmethod
    def _elapsed(s: float) -> str:
        if s < 60:
            return f"{s:.0f}s"
        if s < 3600:
            return f"{s / 60:.1f}m"
        return f"{s / 3600:.1f}h"

    def _handle_key(self, ch: str) -> bool:
        if ch in ("\r", "\n"):
            text = self._input_buf.strip()
            if text:
                comms.post("human", "human", text, kind="message", priority=config.PRI_HUMAN)
            self._input_buf = ""
            return True
        if ch == "\x08":
            self._input_buf = self._input_buf[:-1]
            return True
        if ch in ("q", "Q", "\x03"):
            self.running = False
            return True
        if ch == " " and not self._input_buf:
            p = BASE_DIR / "pause"
            if p.exists():
                p.unlink(missing_ok=True)
            else:
                p.write_text("", encoding="utf-8")
            return True
        if len(ch) == 1 and ch.isprintable():
            self._input_buf += ch
            return True
        return False

    def run(self) -> None:
        import log
        import subprocess
        import sys

        log.cleanup_runtime()
        _w("\x1b[?1049h\x1b[?25l")
        _w("\x1b]0;endgame-ai · reactor\x07")

        comms.post("tui", "tui", "TUI online. Type @persona to interact.", kind="beacon")

        env = os.environ.copy()
        env["ENDGAME_BOOTSTRAPPED"] = "1"
        reactor_cmd = [sys.executable, "reactor.py"]
        if os.environ.get("_ENDGAME_MODEL_PROFILE"):
            reactor_cmd += ["--model-profile", os.environ["_ENDGAME_MODEL_PROFILE"]]
        self._reactor_proc = subprocess.Popen(reactor_cmd, cwd=str(BASE_DIR), env=env, creationflags=0x08000000)

        try:
            while self.running:
                self._scan()
                self._poll()
                if msvcrt.kbhit():
                    self._handle_key(msvcrt.getwch())
                _w(self.render())
                time.sleep(REFRESH_INTERVAL)
        except KeyboardInterrupt:
            pass
        finally:
            _w("\x1b[?1049l\x1b[?25h")
            if self._reactor_proc and self._reactor_proc.poll() is None:
                os.system(f"taskkill /F /T /PID {self._reactor_proc.pid} >nul 2>&1")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["lmstudio", "acp"], default="lmstudio")
    parser.add_argument("--model-profile", type=str, default=None)
    args = parser.parse_args()
    os.environ["ENDGAME_BACKEND"] = args.backend
    if args.model_profile:
        os.environ["_ENDGAME_MODEL_PROFILE"] = args.model_profile
    TUI().run()
