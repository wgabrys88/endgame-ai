"""brain — stateless LLM calls with a reasoning-feedback loop.

One brain object, swappable transports. Every call is stateless: the model holds no
session memory between calls. Continuity comes from `reasoning` being re-injected into
the next prompt, so later thinking is primed by earlier thinking — this is the only
"memory" the cognition layer carries.

Transports:
  - openai : any OpenAI-compatible HTTP server (LM Studio, llama.cpp, vLLM, ...).
  - gui    : a GUI/browser-hosted agent (e.g. Grok) reached through a file handoff;
             an outside operator/agent reads request.json and writes response.json.

Both return (content, reasoning). `content` is the committed answer; `reasoning` is the
model's own prior thinking, fed back on the next call when reason_feedback is on.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import time
import urllib.request

ROOT = pathlib.Path(__file__).parent.resolve()


def _extract_json(text: str):
    """Best-effort: pull the first balanced JSON object out of model text."""
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


class Brain:
    def __init__(self, cfg: dict):
        self.cfg = dict(cfg or {})
        self.transport = self.cfg.get("transport", "openai")
        self.feedback = bool(self.cfg.get("reason_feedback", True))

    # ── public API ─────────────────────────────────────────────────────────
    def think(self, system: str, user: str, prior_reasoning: str = "") -> tuple[str, dict | None, str]:
        """One stateless decision. Returns (raw_content, parsed_json_or_None, reasoning).

        If reason_feedback is on and prior_reasoning is supplied, it is injected so the
        model continues its own train of thought instead of starting cold.
        """
        if self.feedback and prior_reasoning.strip():
            user = user + "\n\nYOUR_PRIOR_REASONING (continue from it, correct it, then commit):\n" + prior_reasoning.strip()
        content, reasoning = self._call(system, user)
        return content, _extract_json(content), (reasoning or content or "").strip()

    # ── transports ─────────────────────────────────────────────────────────
    def _call(self, system: str, user: str) -> tuple[str, str]:
        if self.transport == "gui":
            return self._gui(system, user)
        return self._openai(system, user)

    def _openai(self, system: str, user: str) -> tuple[str, str]:
        host = str(self.cfg.get("host", "http://localhost:1234")).rstrip("/")
        payload = {
            "model": self.cfg.get("model", "local-model"),
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": self.cfg.get("temperature", 0.4),
            "max_tokens": self.cfg.get("max_tokens", 2048),
            "stream": False,
        }
        req = urllib.request.Request(
            host + "/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=float(self.cfg.get("timeout", 900))) as r:
            resp = json.loads(r.read().decode("utf-8", errors="replace"))
        msg = (resp.get("choices") or [{}])[0].get("message", {})
        return msg.get("content", ""), msg.get("reasoning_content", "")

    def _gui(self, system: str, user: str) -> tuple[str, str]:
        """File handoff to a GUI/browser agent. Stateless: each call is a fresh
        request id, so the outside agent treats every turn as a new chat marking."""
        g = self.cfg.get("gui", {})
        req_path = ROOT / g.get("request_path", "comms/request.json")
        resp_path = ROOT / g.get("response_path", "comms/response.json")
        archive = ROOT / g.get("archive_dir", "comms/archive")
        for p in (req_path.parent, archive):
            p.mkdir(parents=True, exist_ok=True)
        rid = f"egai-{int(time.time()*1000)}-{os.getpid()}"
        req_path.write_text(json.dumps({
            "id": rid, "status": "pending", "created_at": time.time(),
            "session": "stateless-new-chat",
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "system": system, "user": user,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        poll = max(0.05, int(g.get("poll_ms", 800)) / 1000.0)
        deadline = time.time() + float(self.cfg.get("timeout", 900))
        while time.time() < deadline:
            if resp_path.exists():
                resp = json.loads(resp_path.read_text(encoding="utf-8") or "{}")
                if resp.get("id") in (None, "", rid):
                    msg = (resp.get("choices") or [{}])[0].get("message", {}) if resp.get("choices") else {}
                    content = msg.get("content") or resp.get("content") or resp.get("response") or ""
                    try:
                        resp_path.replace(archive / f"response.{rid}.json")
                    except OSError:
                        pass
                    return str(content), str(msg.get("reasoning_content", ""))
            time.sleep(poll)
        raise TimeoutError(f"gui brain timed out waiting for {resp_path}")
