from __future__ import annotations
import atexit
import collections
import json
import queue
import subprocess
import sys
import threading
import time

MODEL: str = "claude-opus-4.7"
DISTRO: str = "Ubuntu-24.04"
KIRO_CLI: str = "/usr/bin/kiro-cli"
WORKSPACE: str = "/tmp/poke-acp"

PROTOCOL_VERSION = 1
DEFAULT_PROMPT_TIMEOUT = 300.0
DEFAULT_REQUEST_TIMEOUT = 300.0
WSL_COMMAND_TIMEOUT = 15
CLOSE_JOIN_TIMEOUT = 3.0
PIN_RETRIES = 2
PIN_BACKOFF = 1
READ_CHUNK = 65536
POLL_SLEEP = 0.02
STDERR_RING_BYTES = 4096
PROTOCOL_ERROR_NOT_IMPLEMENTED = -32601
_ACP_ARGV_PREFIX = (KIRO_CLI, "acp")
PIDFILE_NAME = "acp.pid"


class ACPError(RuntimeError):
    pass


def _wsl_run(*args: str, timeout: float = WSL_COMMAND_TIMEOUT) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["wsl.exe", "-d", DISTRO, *args],
        capture_output=True,
        timeout=timeout,
    )


def _wsl_ps_argv(pid: int) -> list[str]:
    r = _wsl_run(
        "--exec", "/bin/bash", "-lc",
        f"cat /proc/{int(pid)}/cmdline 2>/dev/null | tr '\\0' '\\n'",
    )
    if r.returncode != 0:
        return []
    return [s for s in r.stdout.decode("utf-8", "replace").split("\n") if s]


def _wsl_pid_alive(pid: int) -> bool:
    r = _wsl_run("--exec", "/bin/bash", "-lc", f"kill -0 {int(pid)} 2>/dev/null && echo y || echo n")
    return r.stdout.strip() == b"y"


def _wsl_pgid(pid: int) -> int | None:
    r = _wsl_run(
        "--exec", "/bin/bash", "-lc",
        f"ps -o pgid= -p {int(pid)} 2>/dev/null | tr -d ' \\t'",
    )
    raw = r.stdout.decode("utf-8", "replace").strip()
    return int(raw) if raw.isdigit() else None


def _wsl_kill_group(pgid: int, sig: str = "TERM") -> None:
    if pgid <= 1:
        return
    _wsl_run("--exec", "/bin/bash", "-lc", f"kill -{sig} -- -{int(pgid)} 2>/dev/null || true")


def _read_pidfile(path: str) -> list[dict]:
    r = _wsl_run("--exec", "/bin/bash", "-lc", f"cat {path} 2>/dev/null || true")
    raw = r.stdout.decode("utf-8", "replace").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [e for e in data if isinstance(e, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def _write_pidfile(path: str, entries: list[dict]) -> None:
    blob = json.dumps(entries, separators=(",", ":")).replace("'", "'\\''")
    tmp = path + ".tmp"
    _wsl_run("--exec", "/bin/bash", "-lc",
             f"printf '%s' '{blob}' > {tmp} && mv {tmp} {path}")


def _delete_pidfile(path: str) -> None:
    _wsl_run("--exec", "/bin/bash", "-lc", f"rm -f {path}")


def _find_all_acp_pids() -> list[int]:
    script = (
        "for p in $(ls /proc 2>/dev/null | grep -E '^[0-9]+$'); do "
        f"  cmdline=$(tr '\\0' '|' < /proc/$p/cmdline 2>/dev/null); "
        f"  if [ \"$cmdline\" = \"{KIRO_CLI}|acp|\" ]; then "
        "    stat=$(stat -c '%Y' /proc/$p 2>/dev/null || echo 0); "
        "    printf '%s %s\\n' \"$stat\" \"$p\"; "
        "  fi; "
        "done | sort -n"
    )
    r = _wsl_run("--exec", "/bin/bash", "-lc", script)
    pids: list[tuple[int, int]] = []
    for line in r.stdout.decode("utf-8", "replace").splitlines():
        parts = line.strip().split()
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            pids.append((int(parts[0]), int(parts[1])))
    pids.sort()
    return [p for _mt, p in pids]


def _discover_child_pid(exclude: set[int] | None = None, retries: int = 20) -> int | None:
    exclude = exclude or set()
    for _ in range(retries):
        all_pids = _find_all_acp_pids()
        fresh = [p for p in all_pids if p not in exclude]
        if fresh:
            return fresh[-1]
        time.sleep(0.1)
    return None


class Client:
    def __init__(
        self,
        distro: str | None = None,
        kiro_cli: str | None = None,
        model: str | None = None,
        workspace: str | None = None,
    ) -> None:
        self._distro = distro or DISTRO
        self._kiro = kiro_cli or KIRO_CLI
        self._model = model or MODEL
        self._ws = workspace or WORKSPACE
        self._proc: subprocess.Popen | None = None
        self._reader_t: threading.Thread | None = None
        self._stderr_t: threading.Thread | None = None
        self._stderr_ring: collections.deque = collections.deque(maxlen=STDERR_RING_BYTES)
        self._next_id = 0
        self._lock = threading.Lock()
        self._pending: dict[int, queue.Queue] = {}
        self._chunks: list[str] = []
        self._prompt_done = threading.Event()
        self._prompt_id: int | None = None
        self._session_id: str | None = None
        self._initialized = False
        self._wsl_child_pid: int | None = None
        self._pidfile_path = f"{self._ws}/{PIDFILE_NAME}"
        atexit.register(self.close)

    @property
    def child_pid(self) -> int | None:
        return self._proc.pid if self._proc else None

    @property
    def wsl_child_pid(self) -> int | None:
        return self._wsl_child_pid

    def stderr_tail(self) -> str:
        return bytes(self._stderr_ring).decode("utf-8", "replace")

    def _cleanup_stragglers(self) -> list[int]:
        killed: list[int] = []
        entries = _read_pidfile(self._pidfile_path)
        tracked_live = set()
        remaining_entries: list[dict] = []
        for e in entries:
            pid = e.get("wsl_pid")
            if not isinstance(pid, int):
                continue
            if _wsl_pid_alive(pid):
                argv = _wsl_ps_argv(pid)
                if tuple(argv[:2]) == _ACP_ARGV_PREFIX:
                    tracked_live.add(pid)
                    remaining_entries.append(e)
        pids = _find_all_acp_pids()
        for pid in pids:
            if pid in tracked_live:
                continue
            argv = _wsl_ps_argv(pid)
            if tuple(argv[:2]) != _ACP_ARGV_PREFIX:
                continue
            pgid = _wsl_pgid(pid)
            if isinstance(pgid, int) and pgid > 1:
                _wsl_kill_group(pgid, "TERM")
                for _ in range(15):
                    if not _wsl_pid_alive(pid):
                        break
                    time.sleep(0.2)
                if _wsl_pid_alive(pid):
                    _wsl_kill_group(pgid, "KILL")
                    time.sleep(0.3)
            killed.append(pid)
        if remaining_entries:
            _write_pidfile(self._pidfile_path, remaining_entries)
        else:
            _delete_pidfile(self._pidfile_path)
        return killed

    def _register_in_pidfile(self) -> None:
        if self._wsl_child_pid is None:
            return
        pgid = _wsl_pgid(self._wsl_child_pid)
        entries = _read_pidfile(self._pidfile_path)
        entries = [e for e in entries if e.get("wsl_pid") != self._wsl_child_pid]
        entries.append({
            "wsl_pid": self._wsl_child_pid,
            "pgid": pgid,
            "bridge_pid": self._proc.pid if self._proc else None,
            "started_at": time.time(),
        })
        _write_pidfile(self._pidfile_path, entries)

    def _deregister_from_pidfile(self) -> None:
        entries = _read_pidfile(self._pidfile_path)
        if not entries:
            return
        remaining = [e for e in entries if e.get("wsl_pid") != self._wsl_child_pid]
        if remaining:
            _write_pidfile(self._pidfile_path, remaining)
        else:
            _delete_pidfile(self._pidfile_path)

    def _ensure_started(self) -> None:
        if self._initialized:
            return
        mk = _wsl_run("--exec", "mkdir", "-p", self._ws)
        if mk.returncode != 0:
            raise ACPError(f"mkdir workspace failed: {mk.stderr.decode('utf-8', 'replace')[:300]}")
        self._cleanup_stragglers()
        pre_pids = set(_find_all_acp_pids())
        self._pin_model()
        self._proc = subprocess.Popen(
            ["wsl.exe", "-d", self._distro, "--cd", self._ws, "--exec", self._kiro, "acp"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self._reader_t = threading.Thread(target=self._reader, daemon=True, name="acp-reader")
        self._reader_t.start()
        self._stderr_t = threading.Thread(target=self._stderr_reader, daemon=True, name="acp-stderr")
        self._stderr_t.start()
        self._wsl_child_pid = _discover_child_pid(exclude=pre_pids)
        self._register_in_pidfile()
        resp = self._request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "clientCapabilities": {
                "fs": {"readTextFile": True, "writeTextFile": True},
                "terminal": True,
            },
        })
        if resp.get("protocolVersion") != PROTOCOL_VERSION:
            raise ACPError("protocol version mismatch: " + json.dumps(resp))
        self._initialized = True

    def _pin_model(self) -> None:
        argv = ("--cd", self._ws, "--exec", self._kiro,
                "settings", "chat.defaultModel", self._model, "--workspace")
        last: subprocess.CompletedProcess | None = None
        for attempt in range(1, PIN_RETRIES + 1):
            last = _wsl_run(*argv)
            if last.returncode == 0:
                return
            if attempt < PIN_RETRIES:
                time.sleep(PIN_BACKOFF)
        err = (last.stderr or b"").decode("utf-8", "replace")[:300] if last else ""
        raise ACPError(f"pin model failed rc={last.returncode if last else '?'}: {err}")

    def close(self) -> None:
        p = self._proc
        if p is None:
            return
        self._proc = None
        try:
            if p.stdin:
                try:
                    p.stdin.close()
                except Exception:
                    pass
            if p.poll() is None:
                try:
                    p.terminate()
                except Exception:
                    pass
            try:
                p.wait(timeout=CLOSE_JOIN_TIMEOUT)
            except Exception:
                pass
            for pipe in (p.stdout, p.stderr):
                if pipe is not None:
                    try:
                        pipe.close()
                    except Exception:
                        pass
        finally:
            if self._reader_t:
                self._reader_t.join(timeout=CLOSE_JOIN_TIMEOUT)
            if self._stderr_t:
                self._stderr_t.join(timeout=CLOSE_JOIN_TIMEOUT)
            if self._wsl_child_pid is not None:
                for _ in range(10):
                    if not _wsl_pid_alive(self._wsl_child_pid):
                        break
                    time.sleep(0.2)
                if _wsl_pid_alive(self._wsl_child_pid):
                    argv = _wsl_ps_argv(self._wsl_child_pid)
                    if tuple(argv[:2]) == _ACP_ARGV_PREFIX:
                        pgid = _wsl_pgid(self._wsl_child_pid)
                        if isinstance(pgid, int) and pgid > 1:
                            _wsl_kill_group(pgid, "TERM")
                            time.sleep(0.3)
                            if _wsl_pid_alive(self._wsl_child_pid):
                                _wsl_kill_group(pgid, "KILL")
            self._deregister_from_pidfile()
            self._initialized = False
            self._wsl_child_pid = None

    def _wait_msg(self, q: queue.Queue, timeout: float, method_for_error: str) -> dict:
        deadline = time.monotonic() + timeout
        while True:
            if not q.empty():
                return q.get_nowait()
            if time.monotonic() >= deadline:
                raise ACPError("request " + method_for_error + " timed out")
            if self._proc is not None and self._proc.poll() is not None:
                raise ACPError(f"kiro-cli process exited unexpectedly; stderr tail: {self.stderr_tail()[:300]!r}")
            time.sleep(POLL_SLEEP)

    def prompt(self, text: str, timeout: float = DEFAULT_PROMPT_TIMEOUT) -> str:
        self._ensure_started()
        self._new_session()
        return self._prompt(text, timeout=timeout)

    def _prompt(self, text: str, timeout: float = DEFAULT_PROMPT_TIMEOUT) -> str:
        with self._lock:
            self._chunks.clear()
            self._prompt_done.clear()
            rid = self._send("session/prompt",
                             {"sessionId": self._session_id,
                              "prompt": [{"type": "text", "text": text}]})
            self._prompt_id = rid
        deadline = time.monotonic() + timeout
        while not self._prompt_done.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ACPError("prompt timed out after " + str(timeout) + "s")
            if self._proc is not None and self._proc.poll() is not None:
                raise ACPError(f"kiro-cli process exited unexpectedly; stderr tail: {self.stderr_tail()[:300]!r}")
            self._prompt_done.wait(timeout=min(1.0, remaining))
        q = self._pending.pop(rid, None)
        if q is not None and not q.empty():
            resp = q.get_nowait()
            if "error" in resp:
                raise ACPError(json.dumps(resp["error"]))
        return "".join(self._chunks)

    def _new_session(self) -> str:
        resp = self._request("session/new", {"cwd": self._ws, "mcpServers": []})
        sid = resp.get("sessionId")
        if not isinstance(sid, str):
            raise ACPError("session_new: no sessionId in " + json.dumps(resp))
        self._session_id = sid
        return sid

    def _send(self, method: str, params: dict) -> int:
        self._next_id += 1
        rid = self._next_id
        self._pending[rid] = queue.Queue()
        self._write({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        return rid

    def _request(self, method: str, params: dict, timeout: float = DEFAULT_REQUEST_TIMEOUT) -> dict:
        with self._lock:
            rid = self._send(method, params)
        q = self._pending[rid]
        msg = self._wait_msg(q, timeout, method)
        self._pending.pop(rid, None)
        if "error" in msg:
            raise ACPError(json.dumps(msg["error"]))
        return msg.get("result") or {}

    def _write(self, msg: dict) -> None:
        p = self._proc
        if p is None or p.stdin is None:
            raise ACPError("process not started")
        p.stdin.write(json.dumps(msg, separators=(",", ":")).encode() + b"\n")
        p.stdin.flush()

    def _reader(self) -> None:
        assert self._proc and self._proc.stdout
        buf = b""
        while self._proc and self._proc.poll() is None:
            chunk = self._proc.stdout.read1(READ_CHUNK)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                self._dispatch(msg)
        self._prompt_done.set()

    def _stderr_reader(self) -> None:
        assert self._proc and self._proc.stderr
        while self._proc and self._proc.poll() is None:
            chunk = self._proc.stderr.read1(READ_CHUNK)
            if not chunk:
                break
            self._stderr_ring.extend(chunk)

    def _dispatch(self, msg: dict) -> None:
        method, mid = msg.get("method"), msg.get("id")
        if method == "session/update" and mid is None:
            up = (msg.get("params") or {}).get("update") or {}
            if up.get("sessionUpdate") == "agent_message_chunk":
                c = up.get("content") or {}
                if c.get("type") == "text":
                    self._chunks.append(c.get("text", ""))
            return
        if mid is not None and method is None:
            result = msg.get("result") or {}
            if mid == self._prompt_id and result.get("stopReason"):
                self._prompt_id = None
                self._prompt_done.set()
            q = self._pending.get(mid)
            if q is not None:
                q.put(msg)
            return
        if method == "session/request_permission" and mid is not None:
            opts = (msg.get("params") or {}).get("options") or []
            chosen = next(
                (o.get("optionId") for o in opts if o.get("kind") == "allow_always"),
                (opts[0].get("optionId") if opts else None),
            )
            self._write({"jsonrpc": "2.0", "id": mid,
                          "result": {"outcome": {"outcome": "selected", "optionId": chosen}}})
            return
        if mid is not None and method is not None:
            self._write({"jsonrpc": "2.0", "id": mid,
                          "error": {"code": PROTOCOL_ERROR_NOT_IMPLEMENTED,
                                    "message": "not implemented"}})


_shared: Client | None = None
_shared_lock = threading.Lock()


def get_client() -> Client:
    global _shared
    with _shared_lock:
        if _shared is None:
            _shared = Client()
            atexit.register(_close_shared)
        return _shared


def _close_shared() -> None:
    global _shared
    if _shared is not None:
        _shared.close()
        _shared = None


def prompt_once(text: str, timeout: float = DEFAULT_PROMPT_TIMEOUT) -> str:
    return get_client().prompt(text, timeout=timeout)


if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]) or "Reply with exactly the single word: pong"
    t0 = time.time()
    try:
        reply = prompt_once(prompt, timeout=60.0)
        c = get_client()
        print(json.dumps({
            "ok": True,
            "elapsed_s": round(time.time() - t0, 2),
            "bridge_pid": c.child_pid,
            "wsl_pid": c.wsl_child_pid,
            "reply_len": len(reply),
            "reply": reply[:500],
        }, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({
            "ok": False,
            "elapsed_s": round(time.time() - t0, 2),
            "error_type": type(e).__name__,
            "error": str(e)[:800],
            "stderr_tail": get_client().stderr_tail()[:400] if _shared else "",
        }, ensure_ascii=False, indent=2))
        sys.exit(1)
