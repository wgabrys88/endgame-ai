"""LLM backend — LM Studio + ACP."""
from __future__ import annotations
import contextlib
import hashlib
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import config
import log

_backend: str = "lmstudio"
_cached_host: str | None = None
_cached_model: str | None = None
_llm_gate = threading.Semaphore(max(1, config.LLM_MAX_CONCURRENT))
_prompt_fingerprints: dict[str, str] = {}
_prompt_meta_lock = threading.Lock()

_THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL | re.IGNORECASE)
_JSON_RE = re.compile(r"\{[\s\S]*\}")


@dataclass(frozen=True)
class LLMResult:
    """Parsed LLM output — JSON/text plus optional reasoning trace."""
    text: str
    reasoning: str = ""
    reasoning_tokens: int = 0
    completion_tokens: int = 0


def set_backend(name: str) -> None:
    global _backend
    _backend = name


def close_backend() -> None:
    if _backend == "acp":
        from acp_client import close_pool
        close_pool()


def extract_thinking(raw: str) -> tuple[str, str]:
    """Split inline thinking blocks and optional JSON preamble from visible content."""
    thinks: list[str] = []

    def _capture(match: re.Match[str]) -> str:
        thinks.append(match.group(1).strip())
        return ""

    text = _THINK_RE.sub(_capture, raw).strip()
    reasoning = "\n\n".join(t for t in thinks if t)
    if not reasoning and text and not text.lstrip().startswith("{"):
        brace = text.find("{")
        if brace > 0:
            preamble = text[:brace].strip()
            if len(preamble) >= 20:
                reasoning = preamble
                text = text[brace:].strip()
    return text, reasoning


def extract_json(raw: str) -> str:
    """Strip Nemotron thinking traces and return the first JSON object."""
    text, _ = extract_thinking(raw)
    text = text.strip()
    if text.startswith("{"):
        try:
            obj, _end = json.JSONDecoder().raw_decode(text)
            return json.dumps(obj, ensure_ascii=False)
        except json.JSONDecodeError:
            pass
    m = _JSON_RE.search(text)
    if not m:
        return text
    try:
        obj, _end = json.JSONDecoder().raw_decode(m.group(0))
        return json.dumps(obj, ensure_ascii=False)
    except json.JSONDecodeError:
        return m.group(0)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _cap_reasoning(text: str) -> str:
    limit = int(config.LLM_REASONING_LOG_MAX)
    if limit <= 0 or len(text) <= limit:
        return text
    return text[:limit]


def _usage_meta(usage: Any) -> tuple[int, int]:
    if not isinstance(usage, dict):
        return 0, 0
    completion = int(usage.get("completion_tokens", 0) or 0)
    details = usage.get("completion_tokens_details") or {}
    reasoning = 0
    if isinstance(details, dict):
        reasoning = int(details.get("reasoning_tokens", 0) or 0)
    return reasoning, completion


def _parse_lmstudio_message(msg: dict[str, Any], usage: Any, *, want_json: bool) -> LLMResult:
    raw_content = str(msg.get("content") or "")
    api_reasoning = str(
        msg.get("reasoning_content") or msg.get("reasoning") or ""
    ).strip()
    text, inline_reasoning = extract_thinking(raw_content)
    reasoning = api_reasoning or inline_reasoning
    if want_json:
        text = extract_json(text if text else raw_content)
    reasoning_tokens, completion_tokens = _usage_meta(usage)
    return LLMResult(
        text=text,
        reasoning=reasoning,
        reasoning_tokens=reasoning_tokens,
        completion_tokens=completion_tokens,
    )


@contextlib.contextmanager
def _global_llm_lock():
    """Cross-process lock so LLM_MAX_CONCURRENT applies colony-wide."""
    path = config.LMS_GLOBAL_LOCK_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_CREAT | os.O_RDWR)
    try:
        if os.name == "nt":
            import msvcrt
            acquired = False
            while not acquired:
                try:
                    msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
                    acquired = True
                except OSError:
                    time.sleep(0.05)
            try:
                yield
            finally:
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _trace_prompt(cache_key: str, system: str, user: str) -> None:
    if not config.LMS_TRACE_PROMPTS or not cache_key:
        return
    sys_fp = _sha(system)
    usr_fp = _sha(user)
    with _prompt_meta_lock:
        prev = _prompt_fingerprints.get(cache_key)
        if prev is None:
            _prompt_fingerprints[cache_key] = sys_fp
        elif prev != sys_fp:
            log.emit("prompt_drift", {"cache_key": cache_key, "prev": prev, "curr": sys_fp})
            _prompt_fingerprints[cache_key] = sys_fp
    log.emit(
        "prompt_signature",
        {"cache_key": cache_key, "system_fp": sys_fp, "user_fp": usr_fp,
         "system_chars": len(system), "user_chars": len(user)},
    )


def _emit_llm_response(role: str, cache_key: str, result: LLMResult) -> None:
    payload: dict[str, Any] = {
        "role": role,
        "cache_key": cache_key or role,
        "has_reasoning": bool(result.reasoning),
        "reasoning_chars": len(result.reasoning),
        "reasoning_tokens": result.reasoning_tokens,
        "completion_tokens": result.completion_tokens,
        "output_chars": len(result.text),
    }
    if result.reasoning:
        payload["reasoning"] = _cap_reasoning(result.reasoning)
    log.emit("llm.response", payload)


def call_llm(system: str, user: str, role: str, *, max_tokens: int = 0,
             temperature: float | None = None, schema: dict | None = None,
             cache_key: str = "") -> LLMResult:
    """Call LLM and return parsed text plus captured reasoning trace."""
    temp = temperature if temperature is not None else config.LLM_TEMPERATURE
    body: dict[str, Any] = {
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": temp, "top_p": config.LLM_TOP_P, "top_k": config.LLM_TOP_K,
        "max_tokens": max_tokens or config.BUDGET.get(role, config.LLM_MAX_TOKENS),
        "stream": False, "stop": config.LLM_STOP,
        "presence_penalty": config.LLM_PRESENCE_PENALTY,
        "frequency_penalty": config.LLM_FREQUENCY_PENALTY,
        "repeat_penalty": config.LLM_REPEAT_PENALTY,
        "seed": config.LLM_SEED,
    }
    if schema and config.LLM_API_SCHEMA:
        body["response_format"] = schema
    if config.LLM_THINKING_ENABLED:
        body["enable_thinking"] = True
        if config.LLM_THINKING_BUDGET > 0:
            body["thinking_budget"] = config.LLM_THINKING_BUDGET

    _trace_prompt(cache_key or role, system, user)
    log.emit("llm.request", {
        "role": role,
        "cache_key": cache_key or role,
        "thinking": bool(config.LLM_THINKING_ENABLED),
        "thinking_budget": int(config.LLM_THINKING_BUDGET) if config.LLM_THINKING_ENABLED else 0,
        "temperature": temp,
        "system_chars": len(system),
        "user_chars": len(user),
        "has_schema": bool(schema),
        "api_schema": bool(schema and config.LLM_API_SCHEMA),
    })

    for attempt in range(3):
        try:
            with _llm_gate:
                with _global_llm_lock():
                    match _backend:
                        case "lmstudio":
                            result = _call_lmstudio(body, want_json=bool(schema))
                        case "acp":
                            result = _call_acp(body, want_json=bool(schema))
                        case _:
                            raise ValueError(f"unknown backend: {_backend}")
            _emit_llm_response(role, cache_key or role, result)
            return result
        except (RuntimeError, ConnectionError, TimeoutError, OSError) as err:
            log.emit("llm_retry", {"attempt": attempt + 1, "error": str(err)[:200]})
            if attempt >= 2:
                log.emit("llm_fail", {"error": str(err)[:200]})
                fallback = json.dumps({"mode": "done", "sequence": [], "done_when": "LLM unavailable"})
                return LLMResult(text=fallback)
            time.sleep(min(2 ** attempt, 10))
    return LLMResult(text="")


# --- LM Studio ---

def _resolve_host_model() -> tuple[str, str]:
    global _cached_host, _cached_model
    if _cached_host is not None:
        return _cached_host, _cached_model or ""
    for host in config.LMS_HOSTS:
        model = _fetch_model(host)
        if model:
            _cached_host, _cached_model = host.rstrip("/"), model
            if not config.active_model_profile():
                activated, changed = config.apply_model_profile(model)
                if changed:
                    log.emit("model_profile", {"model": model, "profile": activated})
            return _cached_host, _cached_model
    _cached_host = config.LMS_HOSTS[0].rstrip("/") if config.LMS_HOSTS else ""
    _cached_model = ""
    return _cached_host, _cached_model


def _fetch_model(host: str) -> str | None:
    try:
        req = Request(f"{host.rstrip('/')}/v1/models", method="GET")
        with urlopen(req, timeout=config.LMS_MODEL_LIST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        models = [m["id"] for m in data.get("data", []) if "id" in m]
        return models[0] if models else None
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None


def _call_lmstudio(body: dict[str, Any], *, want_json: bool) -> LLMResult:
    host, model = _resolve_host_model()
    if model:
        body["model"] = model
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    for i in range(config.LMS_REQUEST_ATTEMPTS):
        try:
            req = Request(f"{host}/v1/chat/completions", data=payload,
                         headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(req, timeout=config.LMS_TIMEOUT) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            choices = result.get("choices")
            if choices and isinstance(choices, list):
                msg = choices[0].get("message") or {}
                if isinstance(msg, dict):
                    return _parse_lmstudio_message(msg, result.get("usage"), want_json=want_json)
            raise RuntimeError(f"no choices: {str(result)[:200]}")
        except (HTTPError, URLError, TimeoutError, OSError) as e:
            if i < config.LMS_REQUEST_ATTEMPTS - 1:
                time.sleep(config.LMS_RETRY_DELAY)
            else:
                raise RuntimeError(str(e)) from e
    return LLMResult(text="")


# --- ACP ---

def _call_acp(body: dict[str, Any], *, want_json: bool) -> LLMResult:
    from acp_client import prompt_once
    msgs = body.get("messages", [])
    sys_c = next((m["content"] for m in msgs if m["role"] == "system"), "")
    usr_c = next((m["content"] for m in msgs if m["role"] == "user"), "")
    schema = body.get("response_format", {})
    schema_def = json.dumps(schema.get("json_schema", {}).get("schema", {}), indent=2) if schema else "{}"
    prompt = f"{sys_c}\n\nOutput ONLY valid JSON matching:\n{schema_def}\n\n---\n{usr_c}\n---\nJSON only."

    import msvcrt
    lock_path = config.BASE_DIR / ".acp.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
    try:
        msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        try:
            raw = prompt_once(prompt)
        finally:
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    finally:
        os.close(fd)
    text, reasoning = extract_thinking(raw)
    if want_json:
        text = extract_json(text if text else raw)
    return LLMResult(text=text, reasoning=reasoning)


def _load_schema(name: str) -> dict:
    path = config.SCHEMAS_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _bench_prompts(persona: str = "architect") -> tuple[tuple[str, str], tuple[str, str]]:
    """Return (legacy_system,user) and (optimized_system,user) for A/B."""
    planner = (config.PROMPTS_DIR / "planner.txt").read_text(encoding="utf-8").strip()
    persona_text = ""
    pfile = config.PROMPTS_DIR / "personalities" / f"{persona}.txt"
    if pfile.exists():
        persona_text = pfile.read_text(encoding="utf-8").strip()
    goal = "Write maintenance.py audit log entry and post confirmation to bus"
    legacy_system = planner
    if persona_text:
        legacy_system += f"\n\nPERSONA ({persona}):\n{persona_text}"
    legacy_user = (
        f"GOAL: {goal}\n\nPRESSURE: stagnation=0.120 power=0.880\n\n"
        "Plan JSON:"
    )
    opt_parts = [f"PERSONA_NAME: {persona}"]
    if persona_text:
        opt_parts += ["PERSONA_MISSION:", persona_text, ""]
    opt_parts += [
        f"GOAL: {goal}",
        "",
        "PRESSURE: stagnation=0.120 power=0.880",
        "",
        "Plan JSON:",
    ]
    return (legacy_system, legacy_user), (planner, "\n".join(opt_parts))


def _bench_parse(raw: str) -> tuple[bool, str]:
    try:
        parsed = json.loads(extract_json(raw))
    except (json.JSONDecodeError, TypeError):
        return False, "invalid_json"
    if not isinstance(parsed, dict):
        return False, "not_object"
    if parsed.get("mode") == "done":
        return False, "done_fallback"
    if parsed.get("mode") == "direct" and parsed.get("sequence"):
        return True, "ok"
    return False, "missing_sequence"


def run_bench(personas: list[str] | None = None) -> dict[str, Any]:
    """A/B: nemotron_legacy vs nemotron on same planner prompts."""
    global _cached_host, _cached_model
    _cached_host = _cached_model = None
    personas = personas or ["architect", "implementor", "reviewer", "devops"]
    schema = _load_schema("planner")
    rows: list[dict[str, Any]] = []
    for persona in personas:
        (leg_sys, leg_usr), (opt_sys, opt_usr) = _bench_prompts(persona)
        for label, profile in (("legacy", "nemotron_legacy"), ("optimized", "nemotron")):
            _cached_host = _cached_model = None
            config.apply_model_profile(profile, force=True)
            _prompt_fingerprints.clear()
            t0 = time.time()
            result = call_llm(opt_sys if label == "optimized" else leg_sys,
                              opt_usr if label == "optimized" else leg_usr,
                              "planner", schema=schema, cache_key="planner")
            elapsed = round(time.time() - t0, 2)
            ok, reason = _bench_parse(result.text)
            rows.append({
                "persona": persona,
                "profile": label,
                "ok": ok,
                "reason": reason,
                "elapsed_s": elapsed,
                "system_fp": _sha(opt_sys if label == "optimized" else leg_sys),
                "temp": config.LLM_TEMPERATURE,
                "thinking_budget": config.LLM_THINKING_BUDGET,
                "reasoning_chars": len(result.reasoning),
                "reasoning_tokens": result.reasoning_tokens,
            })
    legacy = [r for r in rows if r["profile"] == "legacy"]
    optimized = [r for r in rows if r["profile"] == "optimized"]
    legacy_fps = {r["system_fp"] for r in legacy}
    opt_fps = {r["system_fp"] for r in optimized}
    report = {
        "legacy_ok": sum(1 for r in legacy if r["ok"]),
        "optimized_ok": sum(1 for r in optimized if r["ok"]),
        "legacy_avg_s": round(sum(r["elapsed_s"] for r in legacy) / max(1, len(legacy)), 2),
        "optimized_avg_s": round(sum(r["elapsed_s"] for r in optimized) / max(1, len(optimized)), 2),
        "legacy_system_fps": len(legacy_fps),
        "optimized_system_fps": len(opt_fps),
        "rows": rows,
    }
    return report


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 2 and sys.argv[1] == "bench":
        result = run_bench()
        print(json.dumps(result, indent=2))
        n = len(result["rows"]) // 2
        print(
            f"\nSUMMARY: legacy {result['legacy_ok']}/{n} ok "
            f"avg {result['legacy_avg_s']}s ({result['legacy_system_fps']} system fps) | "
            f"optimized {result['optimized_ok']}/{n} ok "
            f"avg {result['optimized_avg_s']}s ({result['optimized_system_fps']} system fps)"
        )
    else:
        print("Usage: python llm.py bench")