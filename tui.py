"""TUI — fixed 45-line display for Windows Terminal."""
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
EVENTS_GLOB = "events-child-s*.jsonl"
TARGET_HEIGHT = 45
REFRESH_INTERVAL = 0.10
SCAN_INTERVAL = 2.0
MAX_EVENTS = 300

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
    vis = 0
    i = 0
    while i < len(s):
        if s[i] == "\x1b":
            j = s.find("m", i)
            if j != -1:
                i = j + 1
                continue
        vis += 1
        if vis > w:
            break
        i += 1
    if vis <= w:
        return s
    # Truncate
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


# --- Slot view ---

class Slot:
    __slots__ = ("path", "slot_id", "persona", "events", "_off", "_mt", "alive", "fissions", "last_phase", "priority")

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
            self.priority = int(d.get("priority", 0) if "priority" in d else 0)
        elif ph == "fission":
            self.fissions += 1
        elif ph == "stop":
            self.alive = False
        elif ph == "interrupt":
            self.priority = int(d.get("pri", self.priority))

    def recent(self, n: int) -> list[dict]:
        work = [e for e in self.events if e.get("phase") not in ("start",)]
        return work[-n:]

    @property
    def active_agent(self) -> str:
        ph = self.last_phase
        if not ph or ph == "start":
            return "booting"
        if ph.startswith("planner"):
            return "planner"
        if ph in ("actor", "action"):
            return "actor"
        if ph.startswith("verif"):
            return "verifier"
        if ph.startswith("fission"):
            return "fission"
        if ph == "interrupt":
            return "INTERRUPT"
        if ph == "llm_retry":
            return "llm…"
        return ph[:10]


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

    def _scan(self) -> None:
        now = time.time()
        if now - self._last_scan < SCAN_INTERVAL:
            return
        self._last_scan = now
        for fp in glob.glob(str(BASE_DIR / EVENTS_GLOB)):
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

        def row(content: str) -> str:
            t = _trunc(content, inner)
            gap = max(0, inner - _vlen(t))
            return f"{bc}{BOX_V}{RST} {t}{' ' * gap} {bc}{BOX_V}{RST}"

        lines: list[str] = []
        lines.append(f"{bc}{BOX_TL}{BOX_H * (W - 2)}{BOX_TR}{RST}")

        # Header
        alive = sum(1 for s in slots if s.alive)
        total_f = sum(s.fissions for s in slots)
        elapsed = time.time() - self._start
        paused = (BASE_DIR / "pause").exists()
        mode = f"{_fg(*CLR_PRI)}PAUSED{RST}" if paused else f"{_fg(*CLR_ALIVE)}LIVE{RST}"
        hdr = (f"{BOLD}{_fg(*CLR_HEADER)}REACTOR{RST} {alive}/{len(slots)} slots  "
               f"[{mode}]  {_fg(*CLR_ALIVE)}F={total_f}{RST}  "
               f"{self._elapsed(elapsed)}  {time.strftime('%H:%M:%S')}")
        lines.append(row(hdr))
        lines.append(f"{bc}{BOX_ML}{BOX_H * (W - 2)}{BOX_MR}{RST}")

        # Slots: 5 slots × 4 lines = 20 lines + 4 separators = 24
        event_rows = 3
        for idx, slot in enumerate(slots):
            dot = f"{_fg(*CLR_ALIVE)}●{RST}" if slot.alive else f"{_fg(*CLR_DEAD)}○{RST}"
            persona = (slot.persona or "?")[:14].ljust(14)
            agent = slot.active_agent
            pri_tag = f" P{slot.priority}" if slot.priority > 0 else ""
            fiss = f"F={slot.fissions}" if slot.fissions else ""
            header = f"s{slot.slot_id} {persona} {dot} [{_fg(*CLR_PHASE)}{agent}{RST}]{pri_tag} {_fg(*CLR_ALIVE)}{fiss}{RST}"
            lines.append(row(_trunc(header, inner)))

            recent = slot.recent(event_rows)
            for i in range(event_rows):
                if i < len(recent):
                    ev = recent[i]
                    ph = ev.get("phase", "")[:12].ljust(12)
                    d = ev.get("d") or {}
                    brief = self._brief(ev.get("phase", ""), d, inner - 16)
                    lines.append(row(f" {_fg(*CLR_PHASE)}{ph}{RST} {_fg(*CLR_DATA)}{brief}{RST}"))
                else:
                    lines.append(row(""))
            if idx < len(slots) - 1:
                lines.append(f"{bc}{BOX_SL}{BOX_SH * (W - 2)}{BOX_SR}{RST}")

        # Bus section
        lines.append(f"{bc}{BOX_ML}{BOX_H * (W - 2)}{BOX_MR}{RST}")
        lines.append(row(f"{BOLD}{_fg(*CLR_BUS)}BUS{RST} @human · @colony"))
        bus_rows = 6
        chat = self._bus_chat[-bus_rows:]
        for i in range(bus_rows):
            if i < len(chat):
                e = chat[i]
                lines.append(row(f"{_fg(*CLR_BUS)}@{str(e.get('from', '?'))[:12]:12} {str(e.get('text', ''))[:inner-16]}{RST}"))
            else:
                lines.append(row(""))

        # Input
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
                t = f"⚡ from @{d.get('from', '?')} pri={d.get('pri', '')} {d.get('text', '')}"
            case "planner.pending":
                t = "waiting LLM..."
            case "llm_retry":
                t = f"attempt {d.get('attempt', '')} {d.get('error', '')}"
            case "fission":
                t = f"fissions={d.get('fissions', '')}"
            case "start":
                t = f"{d.get('personality', '')} [{d.get('profile', '')}]"
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
