"""Optional local workbench for endgame-ai.

The workbench is not required for organism operation. It serves readable HTML,
status JSON, and centralized run/pause/step control. Browser disconnects are
expected and are suppressed at the socket-write boundary.
"""
from __future__ import annotations

import json
import pathlib
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
            if self.path in {"/", "/workbench.html"}:
                html = (ROOT / "workbench.html").read_bytes()
                self._send_bytes(200, "text/html; charset=utf-8", html)
                return
            if self.path == "/api/status":
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
            if self.path == "/api/control":
                self._send_json(organism.read_control(_load_wiring()))
                return
            if self.path == "/api/wiring":
                self._send_json(_load_wiring())
                return
            if self.path == "/api/state/raw":
                wiring = _load_wiring()
                self._send_json(_safe_json(organism.state_path(wiring), {}))
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
