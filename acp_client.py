from __future__ import annotations

from config import ZERO_INT, ONE_INT
import atexit
import io
import json
import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any, cast

from config import (
    ACP_PROTOCOL_VERSION, ACP_DEFAULT_TIMEOUT, ACP_REQUEST_TIMEOUT,
    ACP_WSL_MKDIR_TIMEOUT, ACP_SETTINGS_TIMEOUT, ACP_CLOSE_TIMEOUT,
    ACP_READ_CHUNK_SIZE, JSONRPC_METHOD_NOT_FOUND, ACP_WORKSPACE_BASE,
    ACP_STOP_POLL_SECONDS,
)
from stop_signal import stop_requested

__all__ = ["ACPError", "prompt_once"]

DISTRO: str = "Ubuntu-24.04"
KIRO_CLI: str = "/usr/bin/kiro-cli"
WORKSPACE: str = f"{ACP_WORKSPACE_BASE}-{os.getpid()}"
MODEL: str = "claude-opus-4.7"
PROTOCOL_VERSION: int = ACP_PROTOCOL_VERSION
DEFAULT_TIMEOUT: float = ACP_DEFAULT_TIMEOUT

type JsonMsg = dict[str, Any]


class ACPError(RuntimeError):
    pass


@dataclass
class _Flight:
    session_id: str
    request_id: int = -ONE_INT
    chunks: list[str] = field(default_factory=lambda: list[str]())
    done: threading.Event = field(default_factory=threading.Event)


class _Pool:
    def __init__(self) -> None:
        self._proc: subprocess.Popen[bytes] | None = None
        self._lock = threading.Lock()
        self._next_id: int = ZERO_INT
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
            self._proc.wait(timeout=ACP_CLOSE_TIMEOUT)
        self._started = False
        self._pending.clear()
        self._flights.clear()
        self._next_id = ZERO_INT
        _run_setup_command(
            ["wsl.exe", "-d", DISTRO, "--exec", "mkdir", "-p", WORKSPACE],
            ACP_WSL_MKDIR_TIMEOUT)
        _run_setup_command(
            ["wsl.exe", "-d", DISTRO, "--cd", WORKSPACE, "--exec",
             KIRO_CLI, "settings", "chat.defaultModel", MODEL, "--workspace"],
            ACP_SETTINGS_TIMEOUT)
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
            self._next_id += ONE_INT
            rid = self._next_id
            flight.request_id = rid
            self._pending[rid] = queue.Queue()
            self._flights[sid] = flight
            self._write({"jsonrpc": "2.0", "id": rid, "method": "session/prompt",
                         "params": {"sessionId": sid, "prompt": [{"type": "text", "text": text}]}})
        deadline = time.monotonic() + timeout
        while not flight.done.wait(ACP_STOP_POLL_SECONDS):
            if stop_requested():
                self._flights.pop(sid, None)
                raise ACPError("stop signal requested")
            if time.monotonic() >= deadline:
                self._flights.pop(sid, None)
                raise ACPError(f"prompt timed out after {timeout}s")
        self._flights.pop(sid, None)
        return "".join(flight.chunks)

    def _send(self, method: str, params: JsonMsg) -> int:
        self._next_id += ONE_INT
        rid = self._next_id
        self._pending[rid] = queue.Queue()
        self._write({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        return rid

    def _request(self, method: str, params: JsonMsg, timeout: float = ACP_REQUEST_TIMEOUT) -> JsonMsg:
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
        buf: bytes = b""
        while self._alive():
            if self._proc is None or self._proc.stdout is None:
                break
            reader = cast(io.BufferedReader, self._proc.stdout)
            chunk: bytes = reader.read1(ACP_READ_CHUNK_SIZE)
            if not chunk:
                break
            buf = buf + chunk
            while b"\n" in buf:
                parts: list[bytes] = buf.split(b"\n", ONE_INT)
                line: bytes = parts[ZERO_INT]
                buf = parts[ONE_INT]
                if line.strip():
                    try:
                        self._dispatch(json.loads(line.decode("utf-8")))
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
            params_data: JsonMsg = msg.get("params") or {}
            raw_opts: object = params_data.get("options") or []
            opts: list[JsonMsg] = cast(list[JsonMsg], raw_opts) if isinstance(raw_opts, list) else []
            chosen: str | None = next(
                (str(o.get("optionId")) for o in opts if o.get("kind") == "allow_always"),
                (str(opts[ZERO_INT].get("optionId")) if opts else None))
            self._write({"jsonrpc": "2.0", "id": mid,
                         "result": {"outcome": {"outcome": "selected", "optionId": chosen}}})
        elif isinstance(mid, int):
            self._write({"jsonrpc": "2.0", "id": mid,
                         "error": {"code": JSONRPC_METHOD_NOT_FOUND, "message": "not implemented"}})

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
        try:
            p.wait(timeout=ACP_CLOSE_TIMEOUT)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(timeout=ACP_CLOSE_TIMEOUT)


_pool: _Pool | None = None
_pool_lock = threading.Lock()


def _run_setup_command(cmd: list[str], timeout: float) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != ZERO_INT:
        output = (proc.stdout + proc.stderr).strip()
        raise ACPError(f"setup command failed: {cmd} exit={proc.returncode} output={output}")


def prompt_once(text: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = _Pool()
    return _pool.prompt(text, timeout=timeout)


def close_pool() -> None:
    global _pool
    with _pool_lock:
        if _pool is None:
            return
        _pool.close()
        _pool = None
