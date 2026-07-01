"""Optional local workbench for endgame-ai.

The workbench is not required for organism operation. It serves readable HTML,
status JSON, and centralized run/pause/step control. Browser disconnects are
expected and are suppressed at the socket-write boundary.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import brain
import organism

ROOT = pathlib.Path(__file__).parent.resolve()
HOST = "127.0.0.1"
PORT = 8800

CLIENT_DISCONNECTS = (BrokenPipeError, ConnectionAbortedError, ConnectionResetError)


def _load_wiring() -> dict[str, Any]:
    return organism.load_wiring()


def _safe_json(path: pathlib.Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"error": f"malformed JSON in {path}: {exc}"}


def _tail_ndjson(path: pathlib.Path, max_lines: int = 80, max_bytes: int = 250_000) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    size = path.stat().st_size
    with path.open("rb") as f:
        if size > max_bytes:
            f.seek(size - max_bytes)
            f.readline()
        raw = f.read().decode("utf-8", errors="replace")
    out: list[dict[str, Any]] = []
    for line in raw.splitlines()[-max_lines:]:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _write_control(mode: str) -> dict[str, Any]:
    wiring = _load_wiring()
    path = organism.control_path(wiring)
    current = organism.read_control(wiring)
    if mode not in {"run", "pause", "step"}:
        raise RuntimeError(f"invalid control mode: {mode!r}")
    current["mode"] = mode
    if mode == "step":
        current["step_token"] = int(current.get("step_token", 0)) + 1
    current["updated_at"] = time.time()
    brain.atomic_write_json(path, current)
    return current


def _resolve_exe(name: str) -> str | None:
    """Resolve executable: absolute path first, then PATH lookup."""
    expanded = os.path.expandvars(os.path.expanduser(str(name or ""))).strip()
    if not expanded:
        return None
    p = pathlib.Path(expanded)
    if p.is_absolute() and p.exists():
        return str(p)
    found = shutil.which(expanded)
    if found:
        return found
    if os.name == "nt" and not p.suffix:
        for ext in (".exe", ".cmd", ".bat", ".ps1"):
            found = shutil.which(expanded + ext)
            if found:
                return found
    return None


def _probe_transport(wiring: dict[str, Any]) -> dict[str, Any]:
    """Probe current transport health."""
    model = wiring.get("model", {})
    transport = model.get("transport", "")
    transport_config = model.get("transport_config", {}).get(transport, {})
    
    if transport == "openai":
        base_url = str(transport_config.get("base_url") or "http://localhost:1234").rstrip("/")
        path = str(transport_config.get("path") or "/v1/models")
        try:
            import urllib.request
            with urllib.request.urlopen(base_url + path, timeout=5) as resp:
                body = resp.read(4000).decode("utf-8", errors="replace")
            return {"ok": True, "host": base_url, "models": body[:2000]}
        except Exception as e:
            return {"ok": False, "error": f"LM Studio unreachable: {e}", "host": base_url}
    
    elif transport == "opencode":
        exe = _resolve_exe(transport_config.get("executable") or "opencode")
        if not exe:
            return {"ok": False, "error": "opencode executable not found"}
        try:
            cp = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=10)
            return {"ok": cp.returncode == 0, "stdout": cp.stdout.strip(), "stderr": cp.stderr.strip()}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    elif transport in ("xai", "grok_cli"):
        if transport == "xai" and transport_config.get("mode") == "api":
            api_key = os.environ.get("XAI_API_KEY") or transport_config.get("api_key")
            return {"ok": bool(api_key), "api_key_present": bool(api_key), "mode": "api"}
        else:
            exe = _resolve_exe(transport_config.get("executable") or "grok")
            return {"ok": exe is not None, "executable": exe, "mode": "cli"}
    
    elif transport == "file_proxy":
        req_path = brain.root_path(transport_config.get("request_path"), "comms/request.json")
        resp_path = brain.root_path(transport_config.get("response_path"), "comms/response.json")
        return {"ok": True, "request_path": str(req_path), "response_path": str(resp_path)}
    
    elif transport == "browser_ai":
        return {"ok": False, "error": "browser_ai is a documented stub"}
    
    return {"ok": False, "error": f"unknown transport: {transport}"}


def _brain_test(transport: str, wiring: dict[str, Any]) -> dict[str, Any]:
    """Run ROD falsification test (2 brain calls)."""
    # Temporarily override transport for test
    test_wiring = dict(wiring)
    test_wiring.setdefault("model", {})["transport"] = transport
    test_wiring["model"]["max_brain_calls"] = 2
    
    system = (
        "ROD test assistant. Call 1: emit brief reasoning about the user task. "
        "Call 2: commit ONLY one JSON object with no markdown fences."
    )
    user = (
        f"Workbench falsification for transport {transport}. "
        'On the final call output exactly: '
        '{"record_type":"workbench_rod_test","ok":true,"transport":"' + transport + '"}'
    )
    
    started = time.time()
    try:
        record = brain.think(system, {"goal": user, "state": {}}, test_wiring)
        elapsed = round(time.time() - started, 3)
        parsed_ok = bool(
            record
            and record.get("record_type") == "workbench_rod_test"
            and record.get("ok") is True
            and str(record.get("transport", "")) == transport
        )
        return {
            "ok": parsed_ok,
            "transport": transport,
            "parsed": parsed_ok,
            "record": record,
            "elapsed_s": elapsed,
        }
    except Exception as e:
        return {
            "ok": False,
            "transport": transport,
            "error": f"{type(e).__name__}: {e}",
            "elapsed_s": round(time.time() - started, 3),
        }


class Handler(BaseHTTPRequestHandler):
    server_version = "endgame-ai-workbench/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        # Keep routine polling quiet. Real exceptions are surfaced as 500 bodies.
        return

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")

    def _send_bytes(self, status: int, content_type: str, data: bytes) -> None:
        try:
            self.send_response(status)
            self._cors()
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except CLIENT_DISCONNECTS:
            # Expected browser refresh/abort path; not an organism or server failure.
            return

    def _send_json(self, obj: Any, status: int = 200) -> None:
        self._send_bytes(status, "application/json; charset=utf-8", json.dumps(obj, ensure_ascii=False, indent=2, default=str).encode("utf-8"))

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_bytes(HTTPStatus.NO_CONTENT, "text/plain", b"")

    def do_GET(self) -> None:  # noqa: N802
        try:
            # Parse query parameters
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            path = parsed.path
            qs = parse_qs(parsed.query)
            
            if path in {"/", "/workbench.html"}:
                html = (ROOT / "workbench.html").read_bytes()
                self._send_bytes(200, "text/html; charset=utf-8", html)
                return
            
            if path == "/api/status":
                wiring = _load_wiring()
                state = _safe_json(organism.state_path(wiring), {})
                control = organism.read_control(wiring)
                runtime_tail = _tail_ndjson(organism.runtime_log_path(wiring))
                self._send_json({
                    "ok": True,
                    "state": state,
                    "control": control,
                    "runtime_tail": runtime_tail,
                    "wiring": {
                        "transport": wiring.get("model", {}).get("transport"),
                        "topology": wiring.get("topology", {}),
                    },
                })
                return
            
            if path == "/api/control":
                self._send_json(organism.read_control(_load_wiring()))
                return
            
            if path == "/api/wiring":
                self._send_json(_load_wiring())
                return
            
            if path == "/api/state/raw":
                wiring = _load_wiring()
                self._send_json(_safe_json(organism.state_path(wiring), {}))
                return
            
            if path == "/api/logs/tail":
                lines = int(qs.get("lines", ["100"])[0])
                wiring = _load_wiring()
                runtime_tail = _tail_ndjson(organism.runtime_log_path(wiring), max_lines=lines)
                self._send_json({"ok": True, "logs": runtime_tail})
                return
            
            if path == "/api/transport/probe":
                wiring = _load_wiring()
                result = _probe_transport(wiring)
                self._send_json(result)
                return
            
            self._send_json({"ok": False, "error": "not found"}, status=404)
        except CLIENT_DISCONNECTS:
            return
        except Exception as exc:
            self._send_json({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status=500)

    def do_POST(self) -> None:  # noqa: N802
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            body = json.loads(raw.decode("utf-8") or "{}")
            
            if self.path == "/api/control":
                mode = str(body.get("mode") or "")
                self._send_json({"ok": True, "control": _write_control(mode)})
                return
            
            if self.path == "/api/wiring":
                # Hot-reload wiring.json
                wiring = _load_wiring()
                wiring.update(body)
                brain.atomic_write_json(ROOT / "wiring.json", wiring)
                self._send_json({"ok": True, "message": "wiring updated"})
                return
            
            if self.path == "/api/brain/test":
                transport = str(body.get("transport") or _load_wiring().get("model", {}).get("transport") or "openai")
                wiring = _load_wiring()
                result = _brain_test(transport, wiring)
                self._send_json(result)
                return
            
            self._send_json({"ok": False, "error": "not found"}, status=404)
        except CLIENT_DISCONNECTS:
            return
        except json.JSONDecodeError as exc:
            self._send_json({"ok": False, "error": f"malformed request JSON: {exc}"}, status=400)
        except Exception as exc:
            self._send_json({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status=500)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"workbench: http://{HOST}:{PORT}/")
    server.serve_forever()


if __name__ == "__main__":
    main()