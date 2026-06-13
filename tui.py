"""Reactor TUI + message bus console for Windows Terminal Preview."""
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

BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
EVENTS_GLOB = "events-child-*.jsonl"
MAIN_EVENTS = "events.jsonl"

PANEL_WIDTH = 106
PERSONALITY_WIDTH = 14
BAR_WIDTH = 4
HISTORY_LEN = 90
SPEC_WIDTH = 12
PHASE_WIDTH = 12
TARGET_HEIGHT = 45  # fixed TUI height

REFRESH_INTERVAL = 0.10
SCAN_INTERVAL = 2.0
MAX_EVENTS_BUFFER = 600

ROSTER: dict[str, str] = {
    "n1": "architect",
    "n2": "implementor",
    "n3": "reviewer",
    "n4": "comms_operator",
    "n5": "devops",
    "n6": "quality_critic",
}

WORK_PHASES = frozenset({
    "schedule", "plan", "actor", "action", "observe", "verify", "fission_judge", "reflect",
    "mutation", "personality.evolve", "fission", "fission_blocked", "fission_sustain", "goal_change",
    "start", "stop", "mutator", "mutator.error", "mutator.rejected",
    "planner.error", "planner.pending", "actor.error", "verifier.error", "fission_judge.error", "reflector.error",
    "sleep", "wake",
})

RAMP_STAG = [(20, 20, 30), (80, 30, 30), (160, 50, 30), (220, 70, 30), (255, 100, 60)]
RAMP_NRG = [(20, 20, 30), (30, 80, 40), (40, 140, 60), (50, 200, 80), (80, 255, 120)]
RAMP_PID = [(20, 20, 30), (30, 40, 100), (50, 70, 170), (70, 100, 220), (100, 140, 255)]

STAG_MAX = 1.0
NRG_MAX = 3.0
PID_MAX = 5.0

CLR_ALIVE = (80, 220, 120)
CLR_DEAD = (255, 80, 80)
CLR_STAG = (255, 100, 80)
CLR_NRG = (120, 220, 140)
CLR_PID = (80, 140, 255)
CLR_FISSION = (100, 255, 180)
CLR_DIM = (80, 80, 100)
CLR_HEADER = (200, 220, 255)
CLR_BORDER = (55, 58, 78)
CLR_PHASE = (140, 170, 200)
CLR_DATA = (180, 180, 200)
CLR_BUS = (160, 190, 230)
CLR_BUS_HUMAN = (255, 200, 120)
CLR_BUS_GROK = (190, 140, 255)
CLR_BUS_EVENT = (110, 150, 190)
CLR_INPUT = (255, 240, 200)

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
SYNC_ON = "\x1b[?2026h"
SYNC_OFF = "\x1b[?2026l"


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


def _display_input(buf: str) -> str:
    """Show spaces as middle dots so typed gaps are visible in the prompt."""
    return buf.replace(" ", "\u00b7")


def _compose_lr(left: str, right: str, inner: int, right_w: int) -> str:
    """Fixed left/right columns — right strip never overlaps event text."""
    left_w = max(8, inner - right_w - 1)
    lv = _trunc(left, left_w)
    rv = _trunc(right, right_w)
    gap = max(1, left_w - _vlen(lv))
    return f"{lv}{' ' * gap}{rv}"


def _trunc(s: str, w: int, suffix: str = "…") -> str:
    if w <= 0:
        return ""
    # First pass: measure visible length
    vis_total = 0
    i = 0
    while i < len(s):
        if s[i] == "\x1b":
            j = s.find("m", i)
            if j != -1:
                i = j + 1
                continue
        vis_total += 1
        i += 1
    if vis_total <= w:
        return s
    # Needs truncation: take w-1 chars + suffix
    limit = w - 1 if suffix else w
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
        if vis >= limit:
            break
        out.append(s[i])
        vis += 1
        i += 1
    if suffix:
        out.append(suffix)
    return "".join(out)


def _console_height() -> int:
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
        return max(24, csbi.srWindow.Bottom - csbi.srWindow.Top + 1)
    return 40


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
        return max(PANEL_WIDTH, min(width, 160))
    return PANEL_WIDTH


def _bar(v: float, w: int, color: tuple[int, int, int]) -> str:
    w = max(2, w)
    f = max(0, min(w, int(v * w)))
    return _fg(*color) + "█" * f + _fg(*CLR_DIM) + "░" * (w - f) + RST


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

    @property
    def active_agent(self) -> str:
        """Which internal agent is currently active in this persona."""
        ph = self.last_phase
        if not ph or ph == "start":
            return "booting"
        if ph == "sleep":
            return "sleeping"
        if ph == "wake":
            return "waking"
        if ph == "math":
            return "math"
        if ph.startswith("planner"):
            return "planner"
        if ph in ("actor", "action", "observe") or ph.startswith("actor"):
            return "actor"
        if ph in ("verify",) or ph.startswith("verifier"):
            return "verifier"
        if ph in ("fission_judge", "fission", "fission_blocked", "fission_sustain") or ph.startswith("fission"):
            return "fission_judge"
        if ph in ("reflect",) or ph.startswith("reflector"):
            return "reflector"
        if ph in ("mutation",) or ph.startswith("mutator") or ph == "personality.evolve":
            return "mutator"
        if ph == "schedule":
            return "scheduler"
        return ph[:12]

    @staticmethod
    def _is_cooldown(ev: dict) -> bool:
        return ev.get("phase") == "schedule" and (ev.get("d") or {}).get("reason") == "plan_cooldown"

    def _should_append(self, ev: dict) -> bool:
        if self._is_cooldown(ev) and self.events and self._is_cooldown(self.events[-1]):
            self.events[-1] = ev
            return False
        return True

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
                    if self._should_append(ev):
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
        work = [e for e in self.events if e.get("phase") in WORK_PHASES and not self._is_cooldown(e)]
        return work[-n:]


class TUI:
    def __init__(self):
        self.agents: dict[str, Agent] = {}
        self.running = True
        self._last_scan = 0.0
        self._start = time.time()
        self._input_buf = ""
        self._input_from = "human"
        self._bus_chat: list[dict[str, Any]] = []
        self._bus_events: list[dict[str, Any]] = []
        self._bus_alert_id = 0
        self._reactor_proc = None

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

    def _mention_alert(self) -> None:
        for entry in self._bus_chat:
            eid = int(entry.get("id", 0) or 0)
            if eid <= self._bus_alert_id:
                continue
            self._bus_alert_id = max(self._bus_alert_id, eid)
            if str(entry.get("from", "")) == "human":
                continue
            mentions = entry.get("mentions") if isinstance(entry.get("mentions"), list) else []
            if not comms.ping_for("human", mentions):
                continue
            try:
                ctypes.windll.user32.MessageBeep(0xFFFFFFFF)
            except (AttributeError, OSError):
                _w("\x07\x07")

    def _poll(self) -> None:
        comms.drain_inject()
        self._bus_chat = comms.read_chat(40)
        self._bus_events = comms.read_events(20)
        self._mention_alert()
        for a in self.agents.values():
            a.poll()

    def _sorted(self) -> list[Agent]:
        return sorted(self.agents.values(), key=lambda a: (not a.alive, a.personality))

    def _brief(self, ph: str, d: dict, max_w: int = 0) -> str:
        if not d:
            return ""
        match ph:
            case "schedule":
                text = f"cooldown {d.get('wait', '')}s" if d.get("reason") == "plan_cooldown" else f"reason={d.get('reason', '')}"
            case "action" | "actor":
                ok = "ok" if d.get("ok") else "FAIL"
                v = d.get("verb", d.get("conclusion", ""))
                o = d.get("obs", "")
                text = f"{ok} {v} {o}".strip() if v or o else str(d)
            case "planner.pending":
                text = "waiting LLM..."
            case "wake":
                text = f"⚡ woken by @{d.get('from', '?')}: {d.get('text', '')}"
            case "plan":
                reason = d.get("reason", "")
                text = f"rejected {reason[:72]}" if d.get("mode") == "rejected" and reason else f"mode={d.get('mode', '')} steps={d.get('steps', '')} {d.get('done_when', '')}"
            case "verify":
                text = f"{d.get('verdict', '')} {d.get('evidence', '')}"
            case "fission_judge":
                text = f"{d.get('verdict', '')} {d.get('diagnosis', '')}"
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
        return _trunc(text.replace("\n", " ").replace("\r", ""), max_w) if max_w > 0 else text.replace("\n", " ").replace("\r", "")

    def _bus_color(self, from_id: str, kind: str) -> tuple[int, int, int]:
        if from_id == "human":
            return CLR_BUS_HUMAN
        if kind == "event":
            return CLR_BUS_EVENT
        return CLR_BUS

    def _bus_line(self, entry: dict[str, Any], width: int) -> str:
        fid = str(entry.get("from", "?"))
        kind = str(entry.get("kind", "message"))[:5]
        text = str(entry.get("text", "")).replace("\n", " ")
        mentions = entry.get("mentions") if isinstance(entry.get("mentions"), list) else []
        if comms.ping_for("human", mentions):
            color = CLR_BUS_HUMAN
            kind = "ping!"
        else:
            color = self._bus_color(fid, kind)
        body = f"@{fid:<14} [{kind}] {text}"
        return f"{_fg(*color)}{_trunc(body, width)}{RST}"

    def _post_input(self) -> None:
        text = self._input_buf.strip()
        if not text:
            return
        role = comms.ROLES.get(self._input_from, "colony")
        comms.post(self._input_from, role, text, kind="message")
        self._input_buf = ""
        self._bus_chat = comms.read_chat(40)
        self._bus_events = comms.read_events(20)

    def _handle_key(self, ch: str) -> bool:
        if ch in ("\r", "\n"):
            self._post_input()
            return True
        if ch == "\x08":
            self._input_buf = self._input_buf[:-1]
            return True
        if ch == "\x1b":
            return True
        if ch == "\t":
            return True
        if ch in ("q", "Q", "\x03"):
            self.running = False
            return True
        if ch == " ":
            if self._input_buf:
                self._input_buf += " "
                return True
            pause_path = BASE_DIR / "pause"
            if pause_path.exists():
                pause_path.unlink(missing_ok=True)
            else:
                pause_path.write_text("", encoding="utf-8")
            return True
        if len(ch) == 1 and ch.isprintable():
            self._input_buf += ch
            return True
        return False

    def _layout(self, agent_count: int) -> tuple[int, int, int, int]:
        """Fixed 45-line layout. Returns event_rows, bus_chat_rows, bus_event_rows, spec_width."""
        w = _console_width()
        spec_w = 10 if w < 100 else SPEC_WIDTH
        # Fixed: 3 chrome + personas section + bus section + 4 footer
        # personas: agent_count * (1 header + event_rows) + (agent_count-1) separators
        # bus: 1 header + chat + 1 header + events
        # footer: separator + prompt + help + bottom = 4
        # Target: 45 = 3 + personas + bus + 4
        # Available for personas+bus = 38
        # Bus gets 1+chat+1+events = min 6 lines
        # Personas get rest
        available = TARGET_HEIGHT - 7  # 3 top chrome + 4 bottom = 38
        n = max(agent_count, 1)
        separators = max(0, n - 1)
        # Give bus 8 lines (1 header + 4 chat + 1 header + 2 events)
        bus_total = 8
        persona_budget = available - bus_total  # 30 lines for personas
        # Each persona: 1 header + event_rows; plus separators between
        per_persona = max(2, (persona_budget - separators) // n)
        event_rows = per_persona - 1  # subtract header line
        bus_chat = 4
        bus_event = 2
        return event_rows, bus_chat, bus_event, spec_w

    def render(self) -> str:
        W = _console_width()
        inner = W - 4
        agents = self._sorted()
        event_rows, bus_chat_n, bus_event_n, spec_w = self._layout(len(agents))
        bc = _fg(*CLR_BORDER)

        def row(content: str) -> str:
            t = _trunc(content, inner)
            gap = max(0, inner - _vlen(t))
            return f"{bc}{BOX_V}{RST} {t}{' ' * gap} {bc}{BOX_V}{RST}"

        lines: list[str] = []
        lines.append(f"{bc}{BOX_TL}{BOX_H * (W - 2)}{BOX_TR}{RST}")

        alive = sum(1 for a in agents if a.alive)
        total = len(agents)
        total_f = sum(a.fissions for a in agents)
        elapsed = time.time() - self._start
        fpm = total_f * 60.0 / max(elapsed, 1)
        k = total_f / max(alive, 1)
        avg_stag = sum(a.stag for a in agents) / max(total, 1)
        paused = (BASE_DIR / "pause").exists()
        mode = f"{_fg(*CLR_STAG)}MATH-ONLY{RST}" if paused else f"{_fg(*CLR_ALIVE)}LIVE{RST}"
        dot_c = _fg(*CLR_ALIVE) if alive else _fg(*CLR_DEAD)
        dot = "●" if alive else "○"
        hdr = (
            f"{BOLD}{_fg(*CLR_HEADER)}REACTOR{RST} {dot_c}{dot}{RST} {alive}/{total} personas  "
            f"[{mode}]  k={k:.1f}  {_fg(*CLR_FISSION)}F={total_f}{RST}  {fpm:.1f}/m  "
            f"stag={avg_stag:.2f}  {self._elapsed(elapsed)}  {time.strftime('%H:%M:%S')}"
        )
        lines.append(row(hdr))
        lines.append(f"{bc}{BOX_ML}{BOX_H * (W - 2)}{BOX_MR}{RST}")

        val_w = 5
        right_col_w = spec_w + val_w + 1
        bar_w = 3 if W < 110 else BAR_WIDTH
        brief_w = max(12, inner - right_col_w - PHASE_WIDTH - 4)

        for idx, agent in enumerate(agents):
            adot = f"{_fg(*CLR_ALIVE)}●{RST}" if agent.alive else f"{_fg(*CLR_DEAD)}○{RST}"
            pers = agent.personality[:PERSONALITY_WIDTH].ljust(PERSONALITY_WIDTH)
            aa = agent.active_agent
            aa_clr = CLR_STAG if aa == "sleeping" else CLR_PHASE
            aa_tag = f"{_fg(*aa_clr)}{aa}{RST}"
            stag_b = f"s{_bar(agent.stag, bar_w, CLR_STAG)}"
            nrg_b = f"n{_bar(min(agent.energy / NRG_MAX, 1), bar_w, CLR_NRG)}"
            pid_b = f"p{_bar(min(abs(agent.pid_val) / PID_MAX, 1), bar_w, CLR_PID)}"
            fiss = f"{_fg(*CLR_FISSION)}F={agent.fissions}{RST}"
            lines.append(row(_trunc(f"{pers} {adot} [{aa_tag}] {stag_b} {nrg_b} {pid_b} {fiss}", inner)))

            recent = agent.recent_work(event_rows)
            s_strip = _spec_row(agent.hist_stag, spec_w, RAMP_STAG)
            n_strip = _spec_row(agent.hist_nrg, spec_w, RAMP_NRG)
            p_strip = _spec_row(agent.hist_pid, spec_w, RAMP_PID)
            specs = [
                f"{s_strip}{_fg(*CLR_STAG)}{agent.stag:4.2f}{RST}",
                f"{n_strip}{_fg(*CLR_NRG)}{agent.energy:4.1f}{RST}",
                f"{p_strip}{_fg(*CLR_PID)}{agent.pid_val:4.1f}{RST}",
            ]
            for i in range(event_rows):
                if i < len(recent):
                    ph = recent[i].get("phase", "")
                    brief = self._brief(ph, recent[i].get("d", {}), brief_w)
                    phase = _trunc(ph, PHASE_WIDTH).ljust(PHASE_WIDTH)
                    left = f" {_fg(*CLR_PHASE)}{phase}{RST} {_fg(*CLR_DATA)}{brief}{RST}"
                else:
                    left = ""
                right = specs[i] if i < len(specs) else ""
                lines.append(row(_compose_lr(left, right, inner, right_col_w)))
            if idx < len(agents) - 1:
                lines.append(f"{bc}{BOX_SL}{BOX_SH * (W - 2)}{BOX_SR}{RST}")

        lines.append(f"{bc}{BOX_ML}{BOX_H * (W - 2)}{BOX_MR}{RST}")
        lines.append(row(f"{BOLD}{_fg(*CLR_BUS)}CHAT{RST} @Human · colony — @mention pings"))
        chat_entries = self._bus_chat[-bus_chat_n:]
        for i in range(bus_chat_n):
            if i < len(chat_entries):
                lines.append(row(self._bus_line(chat_entries[i], inner)))
            else:
                lines.append(row(""))
        lines.append(row(f"{BOLD}{_fg(*CLR_BUS)}EVENTS{RST}"))
        ev_entries = self._bus_events[-bus_event_n:]
        for i in range(bus_event_n):
            if i < len(ev_entries):
                lines.append(row(self._bus_line(ev_entries[i], inner)))
            else:
                lines.append(row(""))

        lines.append(f"{bc}{BOX_ML}{BOX_H * (W - 2)}{BOX_MR}{RST}")
        role = comms.ROLES.get(self._input_from, "colony")
        shown = _display_input(self._input_buf)
        prompt = f"@{self._input_from} ({role})> {shown}"
        cursor = "\u258c" if int(time.time() * 2) % 2 else " "
        lines.append(row(f"{_fg(*CLR_INPUT)}{_trunc(prompt, inner - 1)}{cursor}{RST}"))
        lines.append(row(f"{_fg(*CLR_DIM)}Enter send · Space empty=LIVE · q quit{RST}"))

        lines.append(f"{bc}{BOX_BL}{BOX_H * (W - 2)}{BOX_BR}{RST}")
        # Enforce exactly TARGET_HEIGHT lines
        while len(lines) < TARGET_HEIGHT:
            lines.append("\x1b[K")
        lines = lines[:TARGET_HEIGHT]
        return "\x1b[H" + "\r\n".join(ln + "\x1b[K" for ln in lines)

    @staticmethod
    def _elapsed(s: float) -> str:
        if s < 60:
            return f"{s:.0f}s"
        if s < 3600:
            return f"{s / 60:.1f}m"
        return f"{s / 3600:.1f}h"

    def run(self) -> None:
        import log
        import subprocess
        import sys

        log.cleanup_runtime()
        _w("\x1b[?1049h\x1b[?25l\x1b[?2004h\x1b[5 q")
        _w("\x1b]0;endgame-ai · reactor + bus\x07")
        pause_path = BASE_DIR / "pause"
        pause_path.write_text("", encoding="utf-8")
        comms.post("tui", "console", "TUI online. @Human @colony — @mention plays alert sound.", kind="beacon")

        env = os.environ.copy()
        env["ENDGAME_BOOTSTRAPPED"] = "1"
        reactor_cmd = [sys.executable, "reactor.py"]
        if os.environ.get("_ENDGAME_MODEL_PROFILE"):
            reactor_cmd += ["--model-profile", os.environ["_ENDGAME_MODEL_PROFILE"]]
        self._reactor_proc = subprocess.Popen(
            reactor_cmd,
            cwd=str(BASE_DIR),
            env=env,
            creationflags=0x08000000,
        )
        try:
            while self.running:
                self._scan()
                self._poll()
                if msvcrt.kbhit():
                    self._handle_key(msvcrt.getwch())
                _w(SYNC_ON + self.render() + SYNC_OFF)
                agents = self._sorted()
                alive = sum(1 for a in agents if a.alive)
                total = len(agents) or 1
                _w(f"\x1b]9;4;1;{alive * 100 // total}\x07")
                time.sleep(REFRESH_INTERVAL)
        except KeyboardInterrupt:
            pass
        finally:
            _w("\x1b]9;4;0;0\x07\x1b[?2004l\x1b[?1049l\x1b[?25h")
            if self._reactor_proc and self._reactor_proc.poll() is None:
                os.system(f"taskkill /F /T /PID {self._reactor_proc.pid} >nul 2>&1")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["lmstudio", "acp"], default="lmstudio")
    parser.add_argument("--model-profile", type=str, default=None,
                        help="Model profile (e.g. nemotron, gemma)")
    args = parser.parse_args()
    os.environ["ENDGAME_BACKEND"] = args.backend
    if args.model_profile:
        os.environ["_ENDGAME_MODEL_PROFILE"] = args.model_profile
    TUI().run()