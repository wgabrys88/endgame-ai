"""TUI — compact colony display. Spawns reactor, shows slot state + bus."""
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
TARGET_HEIGHT = 80
REFRESH_INTERVAL = 0.12
SCAN_INTERVAL = 2.0
MAX_EVENTS = 200

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


def _console_width() -> int:
    class _SR(ctypes.Structure):
        _fields_ = [("L", ctypes.c_short), ("T", ctypes.c_short), ("R", ctypes.c_short), ("B", ctypes.c_short)]
    class _CSBI(ctypes.Structure):
        _fields_ = [("sz", ctypes.c_short * 2), ("cp", ctypes.c_short * 2), ("a", ctypes.c_ushort), ("w", _SR), ("mx", ctypes.c_short * 2)]
    csbi = _CSBI()
    if _k32.GetConsoleScreenBufferInfo(_hout, ctypes.byref(csbi)):
        return max(80, csbi.w.R - csbi.w.L + 1)
    return 120


def _console_height() -> int:
    class _SR(ctypes.Structure):
        _fields_ = [("L", ctypes.c_short), ("T", ctypes.c_short), ("R", ctypes.c_short), ("B", ctypes.c_short)]
    class _CSBI(ctypes.Structure):
        _fields_ = [("sz", ctypes.c_short * 2), ("cp", ctypes.c_short * 2), ("a", ctypes.c_ushort), ("w", _SR), ("mx", ctypes.c_short * 2)]
    csbi = _CSBI()
    if _k32.GetConsoleScreenBufferInfo(_hout, ctypes.byref(csbi)):
        return max(20, csbi.w.B - csbi.w.T + 1)
    return 50


def _trunc(s: str, w: int) -> str:
    vis = i = 0
    while i < len(s):
        if s[i] == "\x1b":
            j = s.find("m", i)
            i = (j + 1) if j != -1 else i + 1
        else:
            vis += 1; i += 1
    if vis <= w:
        return s
    vis = 0; out = []
    i = 0
    while i < len(s):
        if s[i] == "\x1b":
            j = s.find("m", i)
            if j != -1:
                out.append(s[i:j + 1]); i = j + 1; continue
        if vis >= w - 1:
            break
        out.append(s[i]); vis += 1; i += 1
    out.append("…")
    return "".join(out)


# --- Slot tracking ---

class Slot:
    __slots__ = ("path", "slot_id", "persona", "events", "_off", "_mt",
                 "alive", "fissions", "last_phase", "stagnation")

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
        self.stagnation = 0.0

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
            self.alive = True
        elif ph == "fission":
            self.fissions += 1
        elif ph == "stop":
            self.alive = False
        elif ph == "pressure":
            self.stagnation = float(d.get("stagnation", 0))


# --- TUI ---

class TUI:
    def __init__(self):
        self.slots: dict[str, Slot] = {}
        self.running = True
        self._last_scan = 0.0
        self._start = time.time()
        self._input_buf = ""
        self._session_dir = ""
        self._reactor_proc = None
        self._model_profile = os.environ.get("_ENDGAME_MODEL_PROFILE", "") or "auto"

    def _scan(self) -> None:
        now = time.time()
        if self._session_dir and now - self._last_scan < SCAN_INTERVAL:
            return
        self._last_scan = now
        sessions = sorted(glob.glob(str(BASE_DIR / "sessions" / "*")))
        if not sessions:
            return
        sd = sessions[-1]
        if sd != self._session_dir:
            self._session_dir = sd
            self.slots.clear()
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
        for s in self.slots.values():
            s.poll()

    def render(self) -> str:
        W = _console_width()
        H = _console_height()
        inner = W - 4
        CLR_A = _fg(80, 220, 120)
        CLR_D = _fg(255, 80, 80)
        CLR_H = _fg(200, 220, 255)
        CLR_B = _fg(55, 58, 78)
        CLR_DIM = _fg(80, 80, 100)
        CLR_F = _fg(100, 255, 180)
        CLR_GOAL = _fg(255, 200, 100)

        def row(c: str) -> str:
            return f"{CLR_B}│{RST} {_trunc(c, inner)}"

        lines: list[str] = []
        alive = sum(1 for s in self.slots.values() if s.alive)
        total_f = sum(s.fissions for s in self.slots.values())
        elapsed = time.time() - self._start
        hdr = f"{BOLD}{CLR_H}REACTOR{RST} {alive}/5  {CLR_F}F={total_f}{RST}  {CLR_DIM}{self._model_profile}{RST}  {elapsed:.0f}s"
        lines.append(f"{CLR_B}┌{'─' * (W - 2)}┐{RST}")
        lines.append(row(hdr))
        lines.append(f"{CLR_B}├{'─' * (W - 2)}┤{RST}")

        # Slots — each gets header + up to 4 recent event lines
        for s in sorted(self.slots.values(), key=lambda x: x.slot_id):
            dot = f"{CLR_A}●{RST}" if s.alive else f"{CLR_D}○{RST}"
            persona = (s.persona or "?")[:16].ljust(16)
            stag = f"stag={s.stagnation:.2f}"
            ph = s.last_phase[:20] if s.last_phase else "idle"
            fiss = f"{CLR_F}F={s.fissions}{RST}" if s.fissions else ""
            lines.append(row(f"s{s.slot_id} {dot} {persona} {ph:20} {stag}  {fiss}"))
            # Recent events — full width, truncated at terminal edge
            skip = {"start", "pressure", "plugin.web_sentinel", "prompt_signature", "schedule"}
            recent = [e for e in s.events if e.get("phase") not in skip][-4:]
            for ev in recent:
                ph_e = str(ev.get("phase", ""))[:14]
                d = ev.get("d") or {}
                brief = comms.format_phase_brief(ph_e, d, max_w=inner - 18)
                lines.append(row(f"    {CLR_DIM}{ph_e:14} {brief}{RST}"))
            lines.append(row(""))

        lines.append(f"{CLR_B}├{'─' * (W - 2)}┤{RST}")

        # Bus chat — use remaining space, at least 6 lines
        bus_rows = max(6, H - len(lines) - 6)
        chat = comms.read_chat(bus_rows)
        for entry in chat:
            fid = str(entry.get("from", "?"))[:12]
            kind = str(entry.get("kind", ""))[:6]
            text = str(entry.get("text", "")).replace("\n", " ")
            pri = int(entry.get("pri", 0) or 0)
            color = CLR_GOAL if pri >= 3 else CLR_DIM if pri == 0 else RST
            lines.append(row(f"  {color}@{fid:12} [{kind:6}] {text}{RST}"))
        if not chat:
            lines.append(row(f"  {CLR_DIM}(bus empty){RST}"))

        lines.append(f"{CLR_B}├{'─' * (W - 2)}┤{RST}")
        cursor = "▌" if int(time.time() * 2) % 2 else " "
        lines.append(row(f"{_fg(255, 240, 200)}@human> {self._input_buf}{cursor}{RST}"))
        lines.append(row(f"{CLR_DIM}Enter=send  Space=pause  q=quit{RST}"))
        lines.append(f"{CLR_B}└{'─' * (W - 2)}┘{RST}")

        # Fill to terminal height
        while len(lines) < H:
            lines.append(row(""))
        return "\x1b[H" + "\r\n".join(ln + "\x1b[K" for ln in lines[:H]) + "\x1b[J"

    def _handle_key(self, ch: str) -> None:
        if ch in ("\r", "\n"):
            text = self._input_buf.strip()
            if text:
                comms.post("human", "human", text, kind="message", priority=config.PRI_HUMAN)
            self._input_buf = ""
        elif ch == "\x08":
            self._input_buf = self._input_buf[:-1]
        elif ch in ("q", "Q", "\x03"):
            self.running = False
        elif ch == " " and not self._input_buf:
            p = BASE_DIR / "pause"
            if p.exists():
                p.unlink(missing_ok=True)
            else:
                p.write_text("", encoding="utf-8")
        elif len(ch) == 1 and ch.isprintable():
            self._input_buf += ch

    def run(self, *, colony_goal: str = "") -> None:
        import log
        import subprocess as sp
        log.cleanup_runtime()
        if colony_goal.strip():
            comms.set_colony_goal(colony_goal.strip(), source="human")
        _w("\x1b[?1049h\x1b[?25l\x1b]0;endgame-ai\x07")
        comms.post("tui", "tui", "TUI online.", kind="beacon")

        env = os.environ.copy()
        env["ENDGAME_BOOTSTRAPPED"] = "1"
        if colony_goal.strip():
            env["ENDGAME_COLONY_GOAL"] = colony_goal.strip()
        reactor_cmd = [sys.executable, "reactor.py"]
        if os.environ.get("_ENDGAME_MODEL_PROFILE"):
            reactor_cmd += ["--model-profile", os.environ["_ENDGAME_MODEL_PROFILE"]]
        if colony_goal.strip():
            reactor_cmd += ["--goal", colony_goal.strip()]
        self._reactor_proc = sp.Popen(reactor_cmd, cwd=str(BASE_DIR), env=env, creationflags=0x08000000)

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
    import sys
    parser = argparse.ArgumentParser()
    parser.add_argument("goal", nargs="*")
    parser.add_argument("--backend", choices=["lmstudio", "acp"], default="lmstudio")
    parser.add_argument("--model-profile", type=str, default=config.DEFAULT_MODEL_PROFILE)
    args = parser.parse_args()
    os.environ["ENDGAME_BACKEND"] = args.backend
    os.environ["_ENDGAME_MODEL_PROFILE"] = args.model_profile
    TUI().run(colony_goal=" ".join(args.goal).strip())
