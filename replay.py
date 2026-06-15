"""replay.py - Interactive session replay: browse LLM requests, re-fire to compare models/params."""
from __future__ import annotations
import argparse
import ctypes
import json
import msvcrt
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent.resolve()

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_hout = _k32.GetStdHandle(-11)
_m = ctypes.c_ulong()
_k32.GetConsoleMode(_hout, ctypes.byref(_m))
_k32.SetConsoleMode(_hout, _m.value | 0x0004 | 0x0008)

RST = "\x1b[0m"; BOLD = "\x1b[1m"; DIM = "\x1b[2m"; INV = "\x1b[7m"
GREEN = "\x1b[32m"; CYAN = "\x1b[36m"; YELLOW = "\x1b[33m"


def _w(t: str) -> None:
    n = ctypes.c_ulong()
    _k32.WriteConsoleW(_hout, t, len(t), ctypes.byref(n), None)


def _console_dims() -> tuple[int, int]:
    class _SR(ctypes.Structure):
        _fields_ = [("L", ctypes.c_short), ("T", ctypes.c_short), ("R", ctypes.c_short), ("B", ctypes.c_short)]
    class _CSBI(ctypes.Structure):
        _fields_ = [("sz", ctypes.c_short * 2), ("cp", ctypes.c_short * 2), ("a", ctypes.c_ushort), ("w", _SR), ("mx", ctypes.c_short * 2)]
    csbi = _CSBI()
    if _k32.GetConsoleScreenBufferInfo(_hout, ctypes.byref(csbi)):
        return max(80, csbi.w.R - csbi.w.L + 1), max(20, csbi.w.B - csbi.w.T + 1)
    return 120, 40


def load_traces(session_dir: Path) -> list[dict[str, Any]]:
    traces_dir = session_dir / "traces"
    if not traces_dir.exists():
        return []
    traces = []
    for f in sorted(traces_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            data["_file"] = f.name
            traces.append(data)
        except (json.JSONDecodeError, OSError):
            pass
    return traces


def _fire_request(request_body: dict[str, Any], host: str, timeout: int) -> dict[str, Any]:
    payload = json.dumps(request_body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{host}/v1/chat/completions", data=payload,
                                headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    result["_latency_ms"] = int((time.time() - t0) * 1000)
    return result


def _trunc(s: str, n: int) -> str:
    return s[:n-1] + "\u2026" if len(s) > n else s


class Replay:
    def __init__(self, session_dir: Path, host: str, timeout: int):
        self.session_dir = session_dir
        self.host = host
        self.timeout = timeout
        self.items = load_traces(session_dir)
        self.cursor = 0
        self.scroll = 0
        self.replay_result = ""
        self.status = ""

    def _label(self, i: int, item: dict) -> str:
        req = item.get("request", {})
        msgs = req.get("messages", [])
        user_msg = next((m["content"] for m in msgs if m.get("role") == "user"), "")
        role = next((m["content"][:20] for m in msgs if m.get("role") == "system"), "")
        temp = req.get("temperature", "?")
        return f"[{i+1:02d}] t={temp} | {_trunc(user_msg.split(chr(10))[0], 60)}"

    def _detail(self, item: dict) -> list[str]:
        lines = []
        req = item.get("request", {})
        resp = item.get("response", {})
        for m in req.get("messages", []):
            lines.append(f"{CYAN}{m['role']}:{RST} {_trunc(m.get('content',''), 200)}")
        lines.append("")
        choices = resp.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "")
            lines.append(f"{GREEN}{BOLD}ORIGINAL:{RST}")
            for l in content.split("\n")[:8]:
                lines.append(f"  {GREEN}{l}{RST}")
        usage = resp.get("usage", {})
        if usage:
            lines.append(f"{DIM}prompt={usage.get('prompt_tokens',0)} completion={usage.get('completion_tokens',0)}{RST}")
        return lines

    def render(self) -> str:
        w, h = _console_dims()
        out = ["\x1b[H\x1b[2J"]
        out.append(f"{BOLD}REPLAY: {self.session_dir.name}{RST}  |  {len(self.items)} traces  |  {self.host}")
        out.append(f"{DIM}\u2191\u2193=select  SPACE=re-fire  s=save  q=quit{RST}")
        out.append("\u2500" * w)

        list_h = min(h // 3, len(self.items) + 1)
        if self.cursor < self.scroll: self.scroll = self.cursor
        if self.cursor >= self.scroll + list_h: self.scroll = self.cursor - list_h + 1

        for i in range(self.scroll, min(self.scroll + list_h, len(self.items))):
            lbl = _trunc(self._label(i, self.items[i]), w)
            out.append(f"{INV}{lbl}{RST}" if i == self.cursor else lbl)

        out.append("\u2500" * w)
        if self.items:
            for l in self._detail(self.items[self.cursor])[:8]:
                out.append(_trunc(l, w))

        if self.replay_result:
            out.append(f"\n{'\u2500' * w}")
            out.append(f"{YELLOW}{BOLD}RE-FIRED:{RST}")
            for l in self.replay_result.split("\n")[:6]:
                out.append(_trunc(f"  {YELLOW}{l}{RST}", w + 20))

        if self.status:
            out.append(f"\n{DIM}{self.status}{RST}")
        return "\n".join(out)

    def _refire(self) -> None:
        if not self.items: return
        item = self.items[self.cursor]
        if "request" not in item:
            self.status = "No request data"; return
        self.status = "Firing..."
        _w(self.render())
        try:
            result = _fire_request(dict(item["request"]), self.host, self.timeout)
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "(empty)")
            lat = result.get("_latency_ms", 0)
            usage = result.get("usage", {})
            self.replay_result = f"{content}\n--- {lat}ms | prompt={usage.get('prompt_tokens',0)} completion={usage.get('completion_tokens',0)}"
            self.status = f"Done in {lat}ms"
        except Exception as e:
            self.replay_result = f"ERROR: {e}"
            self.status = "Failed"

    def _save(self) -> None:
        out = BASE_DIR / "test.txt"
        with out.open("a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n{time.strftime('%Y-%m-%d %H:%M:%S')} | {self.session_dir.name} item {self.cursor+1}\n")
            if self.items:
                f.write(f"Label: {self._label(self.cursor, self.items[self.cursor])}\n")
            f.write(f"Re-fired:\n{self.replay_result}\n")
        self.status = f"Saved to {out}"

    def run(self) -> None:
        if not self.items:
            print(f"No traces in {self.session_dir}. Run a session first (LMS_TRACE_PROMPTS=True).")
            return
        _w("\x1b[?1049h\x1b[?25l")
        try:
            while True:
                _w(self.render())
                time.sleep(0.05)
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch in ("q", "\x1b"): break
                    elif ch in ("\xe0", "\x00"):
                        ch2 = msvcrt.getwch()
                        if ch2 == "H": self.cursor = max(0, self.cursor - 1)
                        elif ch2 == "P": self.cursor = min(len(self.items) - 1, self.cursor + 1)
                    elif ch == " ": self._refire()
                    elif ch == "s": self._save()
        except KeyboardInterrupt:
            pass
        finally:
            _w("\x1b[?1049l\x1b[?25h")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay LLM session - browse and re-fire requests")
    parser.add_argument("session", nargs="?", help="Session dir (default: latest)")
    parser.add_argument("--host", default="http://localhost:1234")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    if args.session:
        sd = Path(args.session) if Path(args.session).is_absolute() else BASE_DIR / args.session
    else:
        sessions = sorted((BASE_DIR / "sessions").glob("*"))
        if not sessions: print("No sessions."); sys.exit(1)
        sd = sessions[-1]

    if not sd.exists(): print(f"Not found: {sd}"); sys.exit(1)
    Replay(sd, args.host, args.timeout).run()
