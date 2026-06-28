"""brain — the cognition backend. Stateless LLM calls with the ROD two-call pattern.

One brain, swappable transports selected by wiring model.transport:
  - openai     : OpenAI-compatible HTTP server (LM Studio, llama.cpp, vLLM, ...). The CORE.
  - file_proxy : file handoff to any outside agent. The engine writes an OpenAI-shaped
                 request.json and waits for response.json. This is how cognition can be
                 routed through a browser-hosted AI (e.g. Grok in Opera) driven by a
                 human or a watcher process.
  - browser_ai : the engine itself drives a browser AI via desktop verbs (open/focus,
                 type the prompt, read the answer). Implemented in actions.py.

ROD (Reason-Observe-Decide): every decision is TWO calls. Call 1 the model reasons; Call 2
re-sends the same prompt with the model's own Call-1 reasoning echoed back as
ROD_REASONING_CONTENT, so it re-reasons from its draft and commits clean JSON.

Reasoning is read from the model's reasoning_content field; when empty (models like
Nemotron inline thinking in content as <think>...</think>), it is taken from the think
block. There are NO silent fallbacks: transport errors raise.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import threading
import time
import urllib.request

ROOT = pathlib.Path(__file__).parent.resolve()


# ─── JSON / reasoning extraction ────────────────────────────────────────────

def extract_json_object(text: str):
    """Return the model's committed JSON record, or None.

    Reasoning models inline thinking and close it with </think>, then emit JSON. That
    thinking contains brace-laden prose, so drop everything up to the final </think>,
    then return the LAST balanced top-level {...} that parses."""
    if not text:
        return None
    text = text.strip()
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for block in reversed(re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)):
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            pass
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


def reasoning_from(content: str, reasoning_content: str) -> str:
    """Call-1 reasoning: dedicated field, else the inline <think> block, else content."""
    if reasoning_content and reasoning_content.strip():
        return reasoning_content.strip()
    m = re.search(r"<think>(.*?)</think>", content, flags=re.S)
    if m:
        return m.group(1).strip()
    if "</think>" in content:
        return content.rsplit("</think>", 1)[0].strip()
    return (content or "").strip()


# ─── Brain ──────────────────────────────────────────────────────────────────

class Brain:
    def __init__(self, model_cfg: dict):
        self.cfg = dict(model_cfg or {})

    def transport(self) -> str:
        return self.cfg.get("transport", "openai")

    def think(self, system: str, user: str, parse_retries: int = 2) -> tuple[str, dict | None, str]:
        """One ROD decision. Returns (content, parsed_record_or_None, reasoning).

        Call 1 reasons; Call 2 commits with the reasoning echoed back. Retries only the
        pair on a parse miss (the model produced no valid JSON), bumping temperature."""
        base = self.cfg.get("temperature", 0.3)
        bump = self.cfg.get("temperature_bump", 0.15)
        content, parsed, reasoning = "", None, ""
        for attempt in range(parse_retries + 1):
            temp = base if attempt == 0 else min(1.0, base + bump * attempt)
            c1, r1 = self._call(system, user, temp)
            reasoning = reasoning_from(c1, r1)
            rod_user = user + "\n\nROD_REASONING_CONTENT:\n" + (reasoning or "(none)")
            content, _ = self._call(system, rod_user, temp)
            parsed = extract_json_object(content)
            if parsed:
                break
        return content, parsed, reasoning

    # ── transport dispatch ──────────────────────────────────────────────────
    def _call(self, system: str, user: str, temperature: float) -> tuple[str, str]:
        t = self.transport()
        if t == "file_proxy":
            return self._file_proxy(system, user), ""
        if t == "browser_ai":
            return self._browser_ai(system, user), ""
        return self._openai(system, user, temperature)

    def _openai(self, system: str, user: str, temperature: float) -> tuple[str, str]:
        host = str(self.cfg.get("host", "http://localhost:1234")).rstrip("/")
        payload = {
            "model": self.cfg.get("model", "local-model"),
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": self.cfg.get("max_tokens", 2048),
            "stream": False,
        }
        for key in ("top_p", "top_k", "repeat_penalty", "presence_penalty", "frequency_penalty", "stop", "thinking"):
            if key in self.cfg:
                payload[key] = self.cfg[key]
        req = urllib.request.Request(
            host + "/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=float(self.cfg.get("timeout", 900))) as r:
                resp = json.loads(r.read().decode("utf-8", errors="replace"))
        except Exception as e:
            raise RuntimeError(f"openai transport: {e}")
        msg = (resp.get("choices") or [{}])[0].get("message", {})
        return msg.get("content", ""), msg.get("reasoning_content", "")

    def _file_proxy(self, system: str, user: str) -> str:
        """Write an OpenAI-shaped request.json, wait for response.json. Fail hard on timeout."""
        cfg = self.cfg.get("file_proxy", {})
        req_path = ROOT / cfg.get("request_path", "comms/request.json")
        resp_path = ROOT / cfg.get("response_path", "comms/response.json")
        archive = ROOT / cfg.get("archive_dir", "comms/archive")
        for p in (req_path.parent, archive):
            p.mkdir(parents=True, exist_ok=True)
        rid = f"egai-{int(time.time()*1000)}-{os.getpid()}-{threading.get_ident() % 100000}"
        req_path.write_text(json.dumps({
            "id": rid, "status": "pending", "created_at": time.time(),
            "transport": "file_proxy", "model": self.cfg.get("model"),
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "system": system, "user": user,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        poll = max(0.05, int(cfg.get("poll_interval_ms", 1000)) / 1000.0)
        deadline = time.time() + float(self.cfg.get("timeout", 900))
        while time.time() < deadline:
            if resp_path.exists():
                try:
                    resp = json.loads(resp_path.read_text(encoding="utf-8") or "{}")
                except json.JSONDecodeError:
                    time.sleep(poll)
                    continue
                if resp.get("id") in (None, "", rid):
                    content = _proxy_content(resp)
                    try:
                        shutil.move(str(resp_path), str(archive / f"response.{rid}.json"))
                    except OSError:
                        pass
                    return content
            time.sleep(poll)
        raise TimeoutError(f"file_proxy transport timed out waiting for {resp_path}")

    def _browser_ai(self, system: str, user: str) -> str:
        """Drive a browser-hosted AI through the desktop I/O layer (actions.py)."""
        import actions
        if not hasattr(actions, "browser_ai_handoff"):
            raise RuntimeError("browser_ai transport: actions.browser_ai_handoff not available; use file_proxy")
        prompt = system + "\n\n" + user
        out = actions.browser_ai_handoff(self.cfg.get("browser_ai", {}), prompt)
        if str(out).upper().startswith("FAILED"):
            raise RuntimeError(f"browser_ai transport: {out}")
        return str(out).replace("browser_ai_response:", "", 1).strip()


def _proxy_content(resp: dict) -> str:
    if not isinstance(resp, dict):
        return ""
    choices = resp.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        msg = choices[0].get("message")
        if isinstance(msg, dict):
            return str(msg.get("content") or msg.get("reasoning_content") or "")
    return str(resp.get("content") or resp.get("response") or resp.get("text") or "")
