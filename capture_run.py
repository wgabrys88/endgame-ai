"""[capture_run] — external, non-invasive run harness (gitignored instrument, NOT body).

The organism's transport POSTs and returns; NOTHING in the body writes the brain
request-log the parser consumes (historically an xAI server-side export). This harness
reconstructs that log locally by teeing the ONE POST path (urllib.request.urlopen inside
transport_xai) into a request-logs-<date>.jsonl in the exact shape tools_parse_requests
autodetects: {timestamp, request:<payload>, response:<raw xai obj>}. It then runs the
wheel on the supplied goal and dumps the final state beside the log. It patches only the
stdlib call, never the organism, so it changes no behaviour and adds no machinery.

USAGE (through powershell.exe on Windows, where the desktop + XAI_API_KEY live):
  python capture_run.py "the root goal"
"""
from __future__ import annotations

import datetime as _dt
import io
import json
import pathlib
import sys
import urllib.request

_HERE = pathlib.Path(__file__).parent.resolve()
_STAMP = _dt.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
_LOG = _HERE / f"request-logs-{_STAMP}.jsonl"
_STATE = _HERE / f"run-state-{_STAMP}.json"

_real_urlopen = urllib.request.urlopen


class _Replay(io.BytesIO):
    """A response stand-in: caches the real bytes so transport can read() them once more."""

    def __init__(self, data: bytes, headers, status):
        super().__init__(data)
        self.headers = headers
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _tee_urlopen(req, *args, **kwargs):
    url = req.full_url if hasattr(req, "full_url") else str(req)
    is_model = isinstance(url, str) and "/v1/responses" in url
    with _real_urlopen(req, *args, **kwargs) as resp:
        body = resp.read()
        headers, status = resp.headers, getattr(resp, "status", 200)
    if is_model:
        try:
            payload = json.loads(req.data.decode("utf-8")) if getattr(req, "data", None) else {}
        except Exception:
            payload = {"_unparsed_request": True}
        try:
            raw = json.loads(body.decode("utf-8"))
        except Exception:
            raw = {"_unparsed_response": body.decode("utf-8", "replace")}
        rec = {"timestamp": _dt.datetime.now().isoformat(), "request": payload, "response": raw}
        with _LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return _Replay(body, headers, status)


def main(argv: list[str]) -> int:
    goal = argv[1] if len(argv) > 1 else ""
    if not goal.strip():
        raise SystemExit("capture_run: supply a non-empty root goal as the sole argument")
    urllib.request.urlopen = _tee_urlopen  # tee only; behaviour unchanged
    import core_organism  # imported AFTER patch so transport binds the patched stdlib
    print(f"[capture] log -> {_LOG.name}   state -> {_STATE.name}", flush=True)
    print(f"[capture] goal: {goal}", flush=True)
    state = None
    try:
        state = core_organism.run(goal)
        return 0
    finally:
        try:
            snapshot = {k: v for k, v in (state or {}).items()}
            _STATE.write_text(json.dumps(snapshot, ensure_ascii=False, default=str, indent=2), encoding="utf-8")
            print(f"[capture] final phase: {(state or {}).get('_phase')}  tick: {(state or {}).get('tick')}  last_signal: {(state or {}).get('last_signal')}", flush=True)
        except Exception as exc:
            print(f"[capture] state dump failed: {exc}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
