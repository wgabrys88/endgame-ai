"""brain — stateless LLM calls with the ROD (Reason-Observe-Decide) two-call pattern.

One brain object, swappable transports. Every call is stateless: the model holds no
server-side session memory. Each DECISION is made with two calls:

  Call 1 — the model reasons freely about the situation.
  Call 2 — the SAME prompt, with the model's own Call-1 reasoning echoed back as
           ROD_REASONING_CONTENT, so it re-reasons from its draft and commits clean JSON.

This is intelligence amplification: the second pass critiques its own first thoughts and
is measurably sharper. The reasoning feedback lives entirely within one decision; there
is no cross-turn chat state.

Reasoning is read from the model's `reasoning_content` field when present; for models
that inline their thinking (e.g. Nemotron emits <think>...</think> in `content`), it is
extracted from the think block instead.

Transports:
  - openai : any OpenAI-compatible HTTP server (LM Studio, llama.cpp, vLLM, ...).
  - gui    : a GUI/browser-hosted agent (e.g. Grok) reached through a file handoff;
             an outside operator/agent reads request.json and writes response.json.

_call() returns (content, reasoning_content) for both transports.
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
    """Pull the model's decision JSON out of free-form text.

    Reasoning models (e.g. Nemotron) emit their thinking inline in `content`, often
    closed by </think>, then the real JSON. That thinking contains brace-laden prose,
    so we (1) drop any <think>...</think> or leading text up to the last </think>,
    then (2) scan ALL balanced top-level {...} spans and return the LAST one that
    parses — the committed decision comes after the reasoning, not before it.
    """
    if not text:
        return None
    text = text.strip()
    # Drop chain-of-thought: keep only what follows the final </think>, if present.
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    for block in reversed(fenced):
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            pass
    # Collect every balanced top-level object; prefer the last parseable one.
    candidates = []
    depth = 0
    in_str = esc = False
    start = -1
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    candidates.append(text[start:i + 1])
    for span in reversed(candidates):
        try:
            return json.loads(span)
        except json.JSONDecodeError:
            continue
    return None


def _strip_think(text: str) -> str:
    """Return the committed answer with any <think>...</think> block removed."""
    if not text:
        return ""
    if "</think>" in text:
        return text.rsplit("</think>", 1)[1].strip()
    return text.strip()


def _think_block(content: str, reasoning_content: str) -> str:
    """Extract the model's reasoning from a Call-1 response.

    Prefer the dedicated reasoning_content field. If it is empty (models like
    Nemotron inline their thinking in `content`), use the <think>...</think> block;
    failing that, fall back to the whole content.
    """
    if reasoning_content and reasoning_content.strip():
        return reasoning_content.strip()
    m = re.search(r"<think>(.*?)</think>", content, flags=re.S)
    if m:
        return m.group(1).strip()
    if "</think>" in content:  # open think with no opening tag
        return content.rsplit("</think>", 1)[0].strip()
    return (content or "").strip()


class Brain:
    def __init__(self, cfg: dict):
        self.cfg = dict(cfg or {})
        self.transport = self.cfg.get("transport", "openai")
        self.retries = int(self.cfg.get("parse_retries", 2))

    # ── public API ─────────────────────────────────────────────────────────
    def think(self, system: str, user: str) -> tuple[str, dict | None, str]:
        """One decision via the ROD two-call pattern. Returns (content, parsed, reasoning).

        Call 1: the model reasons freely. We capture its reasoning (from reasoning_content
        or the inline <think> block). Call 2: the SAME prompt with the model's own reasoning
        echoed back as ROD_REASONING_CONTENT, so it re-reasons from its draft and commits
        clean JSON. This is intelligence amplification, not just parse insurance — the
        second pass is measurably sharper because it critiques its own first thoughts.

        Each call is stateless (no chat session is carried server-side); the reasoning
        feedback is the only continuity, and it lives entirely within this one decision.
        """
        content, parsed, reasoning = "", None, ""
        for _ in range(self.retries + 1):
            # Call 1 — reason freely.
            c1, r1 = self._call(system, user)
            reasoning = _think_block(c1, r1)
            # Call 2 — echo reasoning back; commit the decision.
            rod_user = user + "\n\nROD_REASONING_CONTENT:\n" + (reasoning or "(none)")
            c2, _r2 = self._call(system, rod_user)
            content = c2
            parsed = _extract_json(c2)
            if parsed:
                break
        return content, parsed, reasoning

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
        # Pass through proven sampling + reasoning-budget knobs when present.
        for key in ("top_p", "top_k", "repeat_penalty", "presence_penalty", "frequency_penalty", "stop", "thinking"):
            if key in self.cfg:
                payload[key] = self.cfg[key]
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
