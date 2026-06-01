from __future__ import annotations

import atexit
import json
import queue
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Any

__all__ = ["ACPError", "prompt_once"]

DISTRO: str = "Ubuntu-24.04"
KIRO_CLI: str = "/usr/bin/kiro-cli"
WORKSPACE: str = "/tmp/poke-acp"
MODEL: str = "claude-opus-4.7"
PROTOCOL_VERSION: int = 1
DEFAULT_TIMEOUT: float = 300.0

type JsonMsg = dict[str, Any]


class ACPError(RuntimeError):
    pass


@dataclass
class _Flight:
    session_id: str
    request_id: int = -1
    chunks: list[str] = field(default_factory=list)
    done: threading.Event = field(default_factory=threading.Event)


class _Pool:
    def __init__(self) -> None:
        self._proc: subprocess.Popen[bytes] | None = None
        self._lock = threading.Lock()
        self._next_id: int = 0
        self._pending: dict[int, queue.Queue[JsonMsg]] = {}
        self._flights: dict[str, _Flight] = {}
        self._started: bool = False
        atexit.register(self.close)

    def _alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _start(self) -> None:
        if self._alive() and self._started:
            return
        if self._proc is not None:
            self._proc.terminate()
            self._proc.wait(timeout=5)
        self._started = False
        self._pending.clear()
        self._flights.clear()
        self._next_id = 0
        subprocess.run(
            ["wsl.exe", "-d", DISTRO, "--exec", "mkdir", "-p", WORKSPACE],
            capture_output=True, timeout=10)
        subprocess.run(
            ["wsl.exe", "-d", DISTRO, "--cd", WORKSPACE, "--exec",
             KIRO_CLI, "settings", "chat.defaultModel", MODEL, "--workspace"],
            capture_output=True, timeout=15)
        self._proc = subprocess.Popen(
            ["wsl.exe", "-d", DISTRO, "--cd", WORKSPACE, "--exec", KIRO_CLI, "acp"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        threading.Thread(target=self._reader, daemon=True).start()
        resp: JsonMsg = self._request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "clientCapabilities": {"fs": {"readTextFile": True, "writeTextFile": True}, "terminal": True}})
        if resp.get("protocolVersion") != PROTOCOL_VERSION:
            raise ACPError("protocol version mismatch")
        self._started = True

    def prompt(self, text: str, timeout: float = DEFAULT_TIMEOUT) -> str:
        self._start()
        sid_resp: JsonMsg = self._request("session/new", {"cwd": WORKSPACE, "mcpServers": []})
        sid: Any = sid_resp.get("sessionId")
        if not isinstance(sid, str):
            raise ACPError("no sessionId returned")
        flight = _Flight(session_id=sid)
        with self._lock:
            self._next_id += 1
            rid = self._next_id
            flight.request_id = rid
            self._pending[rid] = queue.Queue()
            self._flights[sid] = flight
            self._write({"jsonrpc": "2.0", "id": rid, "method": "session/prompt",
                         "params": {"sessionId": sid, "prompt": [{"type": "text", "text": text}]}})
        if not flight.done.wait(timeout):
            self._flights.pop(sid, None)
            raise ACPError(f"prompt timed out after {timeout}s")
        self._flights.pop(sid, None)
        return "".join(flight.chunks)

    def _send(self, method: str, params: JsonMsg) -> int:
        self._next_id += 1
        rid = self._next_id
        self._pending[rid] = queue.Queue()
        self._write({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        return rid

    def _request(self, method: str, params: JsonMsg, timeout: float = 60.0) -> JsonMsg:
        with self._lock:
            rid = self._send(method, params)
        try:
            msg: JsonMsg = self._pending[rid].get(timeout=timeout)
        except queue.ShutDown:
            raise ACPError("client shut down during request")
        self._pending.pop(rid, None)
        if "error" in msg:
            raise ACPError(str(msg["error"]))
        return msg.get("result") or {}

    def _write(self, msg: JsonMsg) -> None:
        if not self._alive() or self._proc is None or self._proc.stdin is None:
            raise ACPError("process not running")
        self._proc.stdin.write(json.dumps(msg, separators=(",", ":")).encode() + b"\n")
        self._proc.stdin.flush()

    def _reader(self) -> None:
        buf = b""
        while self._alive():
            if self._proc is None or self._proc.stdout is None:
                break
            chunk = self._proc.stdout.read1(65536)  # type: ignore[attr-defined]
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if line.strip():
                    try:
                        self._dispatch(json.loads(line))
                    except (json.JSONDecodeError, Exception):
                        pass
        for f in self._flights.values():
            f.done.set()

    def _dispatch(self, msg: JsonMsg) -> None:
        method: str | None = msg.get("method")
        mid: int | None = msg.get("id")
        if method == "session/update":
            params: JsonMsg = msg.get("params") or {}
            sid: str | None = params.get("sessionId")
            up: JsonMsg = params.get("update") or {}
            if up.get("sessionUpdate") == "agent_message_chunk":
                c: JsonMsg = up.get("content") or {}
                if c.get("type") == "text" and sid and sid in self._flights:
                    self._flights[sid].chunks.append(c.get("text", ""))
        elif method is None and isinstance(mid, int):
            result: JsonMsg = msg.get("result") or {}
            if result.get("stopReason"):
                for f in self._flights.values():
                    if f.request_id == mid:
                        f.done.set()
                        break
            q = self._pending.get(mid)
            if q:
                q.put(msg)
        elif method == "session/request_permission" and isinstance(mid, int):
            opts: list[JsonMsg] = (msg.get("params") or {}).get("options") or []
            chosen: str | None = next(
                (o.get("optionId") for o in opts if o.get("kind") == "allow_always"),
                (opts[0].get("optionId") if opts else None))
            self._write({"jsonrpc": "2.0", "id": mid,
                         "result": {"outcome": {"outcome": "selected", "optionId": chosen}}})
        elif isinstance(mid, int):
            self._write({"jsonrpc": "2.0", "id": mid,
                         "error": {"code": -32601, "message": "not implemented"}})

    def close(self) -> None:
        if self._proc is None:
            return
        p = self._proc
        self._proc = None
        self._started = False
        for q in self._pending.values():
            q.shutdown()
        for f in self._flights.values():
            f.done.set()
        p.terminate()
        p.wait(timeout=5)


_pool: _Pool | None = None
_pool_lock = threading.Lock()


def prompt_once(text: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = _Pool()
    return _pool.prompt(text, timeout=timeout)
