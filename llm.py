"""LLM backend — LM Studio + ACP."""
from __future__ import annotations
import argparse
import contextlib
import hashlib
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
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
        if not text.strip():
            for candidate in (reasoning, raw_content):
                if not candidate:
                    continue
                recovered = extract_json(candidate)
                if recovered.strip().startswith("{"):
                    text = recovered
                    break
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


@dataclass(frozen=True)
class LLMCallParams:
    """Explicit generation params — safe for parallel benchmark slots."""
    temperature: float
    top_p: float
    top_k: int
    max_tokens: int
    repeat_penalty: float
    seed: int
    thinking_enabled: bool
    thinking_budget: int
    api_schema: bool
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    stop: tuple[str, ...] = ()
    logit_bias: dict[str, float] = field(default_factory=dict)


def _params_from_config(role: str, *, overrides: dict[str, Any] | None = None) -> LLMCallParams:
    overrides = overrides or {}
    return LLMCallParams(
        temperature=float(overrides.get("temperature", config.LLM_TEMPERATURE)),
        top_p=float(overrides.get("top_p", config.LLM_TOP_P)),
        top_k=int(overrides.get("top_k", config.LLM_TOP_K)),
        max_tokens=int(overrides.get("max_tokens", config.BUDGET.get(role, config.LLM_MAX_TOKENS))),
        repeat_penalty=float(overrides.get("repeat_penalty", config.LLM_REPEAT_PENALTY)),
        seed=int(overrides.get("seed", config.LLM_SEED)),
        thinking_enabled=bool(overrides.get("thinking_enabled", config.LLM_THINKING_ENABLED)),
        thinking_budget=int(overrides.get(
            "thinking_budget",
            config.THINKING_BUDGET.get(role, config.LLM_THINKING_BUDGET) or 0,
        )),
        api_schema=bool(overrides.get("api_schema", config.LLM_API_SCHEMA)),
        presence_penalty=float(overrides.get("presence_penalty", config.LLM_PRESENCE_PENALTY)),
        frequency_penalty=float(overrides.get("frequency_penalty", config.LLM_FREQUENCY_PENALTY)),
        stop=tuple(overrides.get("stop", config.LLM_STOP) or ()),
        logit_bias=dict(overrides.get("logit_bias", config.LLM_LOGIT_BIAS) or {}),
    )


def _build_llm_body(
    system: str,
    user: str,
    params: LLMCallParams,
    schema: dict | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": params.temperature,
        "top_p": params.top_p,
        "top_k": params.top_k,
        "max_tokens": params.max_tokens,
        "stream": False,
        "stop": list(params.stop),
        "presence_penalty": params.presence_penalty,
        "frequency_penalty": params.frequency_penalty,
        "repeat_penalty": params.repeat_penalty,
        "seed": params.seed,
    }
    if params.logit_bias:
        body["logit_bias"] = params.logit_bias
    if schema and params.api_schema:
        body["response_format"] = schema
    if params.thinking_enabled:
        body["enable_thinking"] = True
        if params.thinking_budget > 0:
            body["thinking_budget"] = params.thinking_budget
    return body


def call_llm_with_params(
    system: str,
    user: str,
    params: LLMCallParams,
    *,
    schema: dict | None = None,
) -> tuple[LLMResult, float]:
    """Direct LM Studio call with explicit params; returns (result, elapsed_ms)."""
    body = _build_llm_body(system, user, params, schema)
    t0 = time.perf_counter()
    result = _call_lmstudio(body, want_json=bool(schema))
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    return result, elapsed_ms


def call_llm(system: str, user: str, role: str, *, max_tokens: int = 0,
             temperature: float | None = None, schema: dict | None = None,
             cache_key: str = "") -> LLMResult:
    """Call LLM and return parsed text plus captured reasoning trace."""
    overrides: dict[str, Any] = {}
    if temperature is not None:
        overrides["temperature"] = temperature
    if max_tokens:
        overrides["max_tokens"] = max_tokens
    params = _params_from_config(role, overrides=overrides)
    body = _build_llm_body(system, user, params, schema)
    out_tokens = params.max_tokens
    think_budget = params.thinking_budget
    temp = params.temperature

    _trace_prompt(cache_key or role, system, user)
    log.emit("llm.request", {
        "role": role,
        "cache_key": cache_key or role,
        "thinking": bool(config.LLM_THINKING_ENABLED),
        "thinking_budget": think_budget if config.LLM_THINKING_ENABLED else 0,
        "max_tokens": out_tokens,
        "temperature": temp,
        "top_p": config.LLM_TOP_P,
        "top_k": config.LLM_TOP_K,
        "repeat_penalty": config.LLM_REPEAT_PENALTY,
        "seed": config.LLM_SEED,
        "concurrent_gate": int(config.LLM_MAX_CONCURRENT),
        "global_lock": bool(config.LMS_USE_GLOBAL_LOCK),
        "system_chars": len(system),
        "user_chars": len(user),
        "has_schema": bool(schema),
        "api_schema": bool(schema and config.LLM_API_SCHEMA),
    })

    for attempt in range(3):
        try:
            with _llm_gate:
                lock_ctx = _global_llm_lock() if config.LMS_USE_GLOBAL_LOCK else contextlib.nullcontext()
                with lock_ctx:
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
                return LLMResult(text="", reasoning=f"LLM unavailable: {str(err)[:200]}")
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


def _load_prompt(name: str) -> str:
    path = config.PROMPTS_DIR / f"{name}.txt"
    return path.read_text(encoding="utf-8").strip()


# --- Parameter benchmark (fixed 5 tasks × 5 hyperparameter profiles) ---

_DEFAULT_BENCH_GOAL = "Colony maintenance: audit bus traffic and post maintenance scan completed"

# Stable across runs — do not mutate at runtime.
BENCHMARK_TASKS: tuple[dict[str, str], ...] = (
    {
        "id": "planner_maintenance",
        "role": "planner",
        "schema": "planner",
        "user_suffix": "Plan JSON:",
        "user_body": (
            "GOAL: {goal}\n"
            "PRESSURE: stagnation=0.600 power=0.400 failures=8\n"
            "INBOX: @implementor assign maintenance scan PRI=1\n"
            "AVAILABLE_FILES: log.py, comms.py, plugins/fission_log.py\n"
        ),
    },
    {
        "id": "verifier_bus_post",
        "role": "verifier",
        "schema": "verifier",
        "user_suffix": "Verifier JSON:",
        "user_body": (
            "DONE_WHEN: bus message posted to colony about maintenance scan completed\n\n"
            "STEP RESULTS:\nposted message: maintenance scan completed"
        ),
    },
    {
        "id": "fission_judge_bus",
        "role": "fission_judge",
        "schema": "fission_judge",
        "user_suffix": "Fission judge JSON:",
        "user_body": (
            "GOAL: {goal}\n"
            "COMPLETED: bus message posted to colony about maintenance scan completed\n"
            "VERIFIER_EVIDENCE: posted message: maintenance scan completed\n"
            "PRESSURE: stagnation=0.600 power=0.400 failures=8 fissions=0\n"
        ),
    },
    {
        "id": "reflector_syntax",
        "role": "reflector",
        "schema": "reflector",
        "user_suffix": "Reflect JSON:",
        "user_body": (
            "GOAL: {goal}\n"
            "TRIGGER: stagnation=1.000 failures=11 human_denials=0\n"
            "DENIED_DONE_WHEN: Modified and compiled log.py\n"
            "EVIDENCE: SyntaxError: invalid syntax in log.py audit step\n"
        ),
    },
    {
        "id": "mutator_plugin",
        "role": "mutator",
        "schema": "mutator",
        "user_suffix": "Mutator JSON:",
        "user_body": (
            "GOAL: {goal}\n"
            "PRESSURE: failures=12 human_denials=0\n"
            "HISTORY: Fission judge returned empty JSON; log.py syntax error blocked audit\n"
            "EXISTING_PLUGINS: comms_beacon.py, fission_log.py, lessons_decay.py, web_sentinel.py\n"
        ),
    },
)

# Session 20260614_175152 failure replays (stable prompts from JSONL evidence).
SESSION_REPLAY_TASKS: tuple[dict[str, str], ...] = (
    {
        "id": "session_s1_verifier_routed",
        "role": "verifier",
        "schema": "verifier",
        "user_suffix": "Verifier JSON:",
        "user_body": (
            "DONE_WHEN: posted message to colony bus\n\n"
            "STEP RESULTS:\nrouted"
        ),
        "expect_verdict": "denied",
    },
    {
        "id": "session_s1_verifier_posted",
        "role": "verifier",
        "schema": "verifier",
        "user_suffix": "Verifier JSON:",
        "user_body": (
            "DONE_WHEN: posted message to colony bus\n\n"
            "STEP RESULTS:\nposted message: maintenance scan completed"
        ),
        "expect_verdict": "confirmed",
    },
    {
        "id": "session_s3_fission_empty_risk",
        "role": "fission_judge",
        "schema": "fission_judge",
        "user_suffix": "Fission judge JSON:",
        "user_body": (
            "GOAL: {goal}\n"
            "COMPLETED: bus_post message posted to colony about maintenance scan completed\n"
            "VERIFIER_EVIDENCE: posted maintenance scan\n"
            "PRESSURE: stagnation=0.600 power=0.400 failures=8 fissions=0\n"
            "RECENT HISTORY:\n"
            '  {"denied": "Modified log.py", "reason": "SyntaxError: invalid syntax"}\n'
        ),
        "expect_verdict": "deny",
    },
    {
        "id": "session_s2_verifier_log_read",
        "role": "verifier",
        "schema": "verifier",
        "user_suffix": "Verifier JSON:",
        "user_body": (
            "DONE_WHEN: Read log.py content\n\n"
            "STEP RESULTS:\naudit added\n\naudit added\n\n"
            "print('Bus audit completed')\naudit added"
        ),
        "expect_verdict": "denied",
    },
    {
        "id": "session_s2_planner_log_audit",
        "role": "planner",
        "schema": "planner",
        "user_suffix": "Plan JSON:",
        "user_body": (
            "GOAL: {goal}\n"
            "PRESSURE: stagnation=1.000 power=0.000 failures=11\n"
            "INBOX: @comms_operator assign maintenance scan PRI=1\n"
            "AVAILABLE_FILES: log.py, comms.py, plugins/fission_log.py\n"
            "RECENT HISTORY:\n"
            '  {"denied": "Modified and compiled log.py", "reason": "SyntaxError: invalid syntax"}\n'
        ),
    },
)

# Golden session 20260614_175152 per-role budgets (nemotron_parallel pre-fix).
GOLDEN_SESSION_BUDGETS: dict[str, dict[str, int]] = {
    "planner": {"max_tokens": 1152, "thinking_budget": 1536},
    "verifier": {"max_tokens": 288, "thinking_budget": 192},
    "fission_judge": {"max_tokens": 224, "thinking_budget": 192},
    "reflector": {"max_tokens": 448, "thinking_budget": 384},
    "mutator": {"max_tokens": 896, "thinking_budget": 640},
}


def _profile_role_budgets() -> dict[str, Any]:
    """Use project BUDGET + THINKING_BUDGET — no artificial caps."""
    return {"api_schema": False}


def _profile_all_schema_on() -> dict[str, Any]:
    return {"api_schema": True}


def _profile_golden_fission() -> dict[str, Any]:
    return {"api_schema": False, **GOLDEN_SESSION_BUDGETS["fission_judge"]}


def _profile_postfix_fission() -> dict[str, Any]:
    return {"api_schema": False}


BENCHMARK_PARAM_PROFILES: tuple[dict[str, Any], ...] = (
    {
        "id": "parallel_baseline",
        "label": "nemotron_parallel baseline (schema off, role budgets)",
        "overrides": {"api_schema": False},
    },
    {
        "id": "api_schema_on",
        "label": "API response_format enforced",
        "overrides": {"api_schema": True},
    },
    {
        "id": "low_thinking_high_output",
        "label": "low thinking_budget=64, max_tokens=768",
        "overrides": {"api_schema": False, "thinking_budget": 64, "max_tokens": 768},
    },
    {
        "id": "high_thinking_low_output",
        "label": "high thinking_budget=512, max_tokens=224 (empty JSON risk)",
        "overrides": {"api_schema": False, "thinking_budget": 512, "max_tokens": 224},
    },
    {
        "id": "nemotron_serial",
        "label": "nemotron serial (thinking_budget=384)",
        "overrides": {"api_schema": False, "thinking_budget": 384, "temperature": 0.12},
    },
)


_SCHEMA_MIN_LENGTHS: dict[str, dict[str, int]] = {
    "planner": {"done_when": 20, "code": 10},
    "verifier": {"evidence": 20},
    "fission_judge": {"diagnosis": 20, "suggestion": 10},
    "reflector": {"diagnosis": 30, "suggestion": 30},
}


def _schema_field_ok(role: str, parsed: dict[str, Any]) -> tuple[bool, str]:
    limits = _SCHEMA_MIN_LENGTHS.get(role, {})
    for field, minimum in limits.items():
        if field == "code":
            steps = parsed.get("sequence", [])
            if not steps or not isinstance(steps[0], dict):
                return False, "missing_code"
            if len(str(steps[0].get("code", ""))) < minimum:
                return False, f"code_minLength_{minimum}"
        else:
            if len(str(parsed.get(field, ""))) < minimum:
                return False, f"{field}_minLength_{minimum}"
    return True, "schema_ok"


def _bench_score(role: str, text: str, *, expect_verdict: str = "") -> tuple[bool, str, int]:
    """Return (quality_ok, reason, quality_points 0-100)."""
    if not str(text or "").strip():
        return False, "empty_output", 0
    try:
        parsed = json.loads(extract_json(text))
    except (json.JSONDecodeError, TypeError):
        return False, "invalid_json", 10
    if not isinstance(parsed, dict):
        return False, "not_object", 20

    schema_ok, schema_reason = _schema_field_ok(role, parsed)
    if not schema_ok:
        return False, schema_reason, 35

    match role:
        case "planner":
            if parsed.get("mode") == "direct" and parsed.get("sequence"):
                steps = parsed.get("sequence", [])
                if isinstance(steps, list) and steps and isinstance(steps[0], dict):
                    code = str(steps[0].get("code", ""))
                    if "import Path" in code or "import pathlib" in code:
                        return False, "import_path", 55
                    if "print(" not in code:
                        return False, "missing_print", 60
                    if 'print("routed")' in code or "print('routed')" in code:
                        done = str(parsed.get("done_when", "")).lower()
                        if "posted" in done:
                            return False, "routed_done_when_mismatch", 65
                return True, "ok", 100
            return False, "missing_sequence", 40
        case "verifier":
            verdict = parsed.get("verdict")
            if verdict in {"confirmed", "denied"} and parsed.get("evidence"):
                if expect_verdict and verdict != expect_verdict:
                    return False, f"expected_{expect_verdict}_got_{verdict}", 75
                return True, "ok", 100
            return False, "missing_verdict_or_evidence", 50
        case "fission_judge":
            if parsed.get("verdict") in {"credit", "deny"}:
                diag = str(parsed.get("diagnosis", ""))
                if len(diag) >= 20 and parsed.get("suggestion"):
                    if expect_verdict and parsed.get("verdict") != expect_verdict:
                        return False, f"expected_{expect_verdict}_got_{parsed.get('verdict')}", 80
                    return True, "ok", 100
                return False, "thin_fission_fields", 70
            return False, "bad_verdict", 45
        case "reflector":
            if parsed.get("diagnosis") and parsed.get("suggestion"):
                return True, "ok", 100
            return False, "missing_reflect_fields", 55
        case "mutator":
            if parsed.get("action") in {"patch_plugin", "none"}:
                return True, "ok", 100
            return False, "bad_mutator_action", 50
        case _:
            return True, "ok", 80


def _bench_slot_payload(
    slot_index: int,
    task: dict[str, str],
    profile: dict[str, Any],
    *,
    goal: str,
) -> dict[str, Any]:
    role = task["role"]
    system = _load_prompt(role)
    user_body = task["user_body"]
    if "{goal}" in user_body:
        user_body = user_body.replace("{goal}", goal)
    user = f"{user_body.rstrip()}\n{task['user_suffix']}"
    schema = _load_schema(task["schema"])

    params = _params_from_config(role, overrides=profile.get("overrides"))
    try:
        result, elapsed_ms = call_llm_with_params(system, user, params, schema=schema)
    except Exception as exc:
        return {
            "slot": slot_index,
            "task_id": task["id"],
            "profile_id": profile["id"],
            "profile_label": profile.get("label", profile["id"]),
            "role": role,
            "error": str(exc)[:300],
            "elapsed_ms": 0.0,
            "json_valid": False,
            "quality_ok": False,
            "quality_reason": "request_error",
            "quality_score": 0,
            "output_chars": 0,
            "empty_output": True,
            "params": {
                "temperature": params.temperature,
                "max_tokens": params.max_tokens,
                "thinking_budget": params.thinking_budget,
                "thinking_enabled": params.thinking_enabled,
                "api_schema": params.api_schema,
                "seed": params.seed,
            },
        }

    json_valid = False
    try:
        json.loads(extract_json(result.text))
        json_valid = True
    except (json.JSONDecodeError, TypeError):
        pass
    quality_ok, quality_reason, quality_points = _bench_score(
        role, result.text, expect_verdict=str(task.get("expect_verdict", "")),
    )
    speed_points = max(0, min(30, int(30000 / max(elapsed_ms, 1))))
    score = max(0, min(100, quality_points + (20 if json_valid else 0) + speed_points - (30 if not result.text.strip() else 0)))

    return {
        "slot": slot_index,
        "task_id": task["id"],
        "profile_id": profile["id"],
        "profile_label": profile.get("label", profile["id"]),
        "role": role,
        "elapsed_ms": elapsed_ms,
        "json_valid": json_valid,
        "quality_ok": quality_ok,
        "quality_reason": quality_reason,
        "quality_score": score,
        "output_chars": len(result.text),
        "empty_output": not bool(result.text.strip()),
        "reasoning_chars": len(result.reasoning),
        "reasoning_tokens": result.reasoning_tokens,
        "completion_tokens": result.completion_tokens,
        "params": {
            "temperature": params.temperature,
            "max_tokens": params.max_tokens,
            "thinking_budget": params.thinking_budget,
            "thinking_enabled": params.thinking_enabled,
            "api_schema": params.api_schema,
            "seed": params.seed,
        },
        "output_preview": result.text[:240],
    }


def run_param_benchmark(
    *,
    request: str = "",
    base_profile: str = "nemotron_parallel",
    profiles: list[dict[str, Any]] | None = None,
    tasks: list[dict[str, str]] | None = None,
    parallel: int = 5,
    slot_overrides: dict[int, dict[str, Any]] | None = None,
    suite_id: str = "",
) -> dict[str, Any]:
    """
    Fixed 5-task × 5-profile live LM Studio benchmark.

    Each slot pairs one stable task with one stable hyperparameter profile.
    Slots run concurrently to measure speed + JSON/quality under Nemotron.
    """
    global _cached_host, _cached_model
    _cached_host = _cached_model = None
    goal = (request or _DEFAULT_BENCH_GOAL).strip()
    task_list = list(tasks or BENCHMARK_TASKS)
    profile_list = list(profiles or BENCHMARK_PARAM_PROFILES)
    if len(task_list) != len(profile_list):
        raise ValueError("task and profile counts must match (default: 5 each)")

    slot_overrides = slot_overrides or {}
    merged_profiles: list[dict[str, Any]] = []
    for index, profile in enumerate(profile_list):
        merged = dict(profile)
        extra = slot_overrides.get(index, {})
        if extra:
            overrides = dict(merged.get("overrides", {}))
            overrides.update(extra)
            merged["overrides"] = overrides
        merged_profiles.append(merged)

    config.apply_model_profile(base_profile, force=True)
    host, model = _resolve_host_model()
    wall_t0 = time.perf_counter()
    rows: list[dict[str, Any]] = []
    workers = max(1, min(int(parallel), len(task_list)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                _bench_slot_payload,
                index + 1,
                task_list[index],
                merged_profiles[index],
                goal=goal,
            ): index
            for index in range(len(task_list))
        }
        for future in as_completed(futures):
            rows.append(future.result())
    rows.sort(key=lambda row: int(row.get("slot", 0)))

    profile_stats: dict[str, dict[str, Any]] = {}
    for row in rows:
        pid = str(row.get("profile_id", ""))
        bucket = profile_stats.setdefault(pid, {
            "profile_id": pid,
            "profile_label": row.get("profile_label", pid),
            "slots": 0,
            "quality_ok": 0,
            "json_valid": 0,
            "empty_output": 0,
            "total_ms": 0.0,
            "total_score": 0,
        })
        bucket["slots"] += 1
        bucket["quality_ok"] += int(bool(row.get("quality_ok")))
        bucket["json_valid"] += int(bool(row.get("json_valid")))
        bucket["empty_output"] += int(bool(row.get("empty_output")))
        bucket["total_ms"] += float(row.get("elapsed_ms", 0) or 0)
        bucket["total_score"] += int(row.get("quality_score", 0) or 0)

    ranking = []
    for pid, stats in profile_stats.items():
        slots = max(1, stats["slots"])
        ranking.append({
            "profile_id": pid,
            "profile_label": stats["profile_label"],
            "avg_score": round(stats["total_score"] / slots, 1),
            "avg_ms": round(stats["total_ms"] / slots, 1),
            "quality_ok": stats["quality_ok"],
            "json_valid": stats["json_valid"],
            "empty_output": stats["empty_output"],
        })
    ranking.sort(key=lambda item: (-item["avg_score"], item["avg_ms"]))

    wall_ms = round((time.perf_counter() - wall_t0) * 1000, 1)
    return {
        "ok": all(row.get("json_valid") and row.get("quality_ok") for row in rows),
        "suite_id": suite_id,
        "request": goal,
        "base_profile": base_profile,
        "model": model,
        "host": host,
        "parallel": workers,
        "wall_ms": wall_ms,
        "slots": rows,
        "ranking": ranking,
        "tasks": [task["id"] for task in task_list],
        "profiles": [profile["id"] for profile in merged_profiles],
    }


def _profiles_uniform(overrides: dict[str, Any], label: str) -> list[dict[str, Any]]:
    return [{"id": f"{label}_{index + 1}", "label": label, "overrides": dict(overrides)} for index in range(5)]


def _profiles_golden_per_role(tasks: list[dict[str, str]]) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for task in tasks:
        role = task["role"]
        budgets = GOLDEN_SESSION_BUDGETS.get(role, {})
        profiles.append({
            "id": f"golden_{role}",
            "label": f"golden session budgets ({role})",
            "overrides": {"api_schema": False, **budgets},
        })
    return profiles


def _campaign_suite_definitions() -> list[dict[str, Any]]:
    goal = _DEFAULT_BENCH_GOAL
    fission_task = SESSION_REPLAY_TASKS[2]
    verifier_tasks = [SESSION_REPLAY_TASKS[0], SESSION_REPLAY_TASKS[1]]
    return [
        {
            "id": "T01_postfix_default",
            "label": "Post-fix default 5×5 matrix",
            "request": goal,
            "tasks": list(BENCHMARK_TASKS),
            "profiles": list(BENCHMARK_PARAM_PROFILES),
        },
        {
            "id": "T02_session_replay_schema_off",
            "label": "Session failure replays, role budgets, schema off",
            "request": goal,
            "tasks": list(SESSION_REPLAY_TASKS),
            "profiles": _profiles_uniform(_profile_role_budgets(), "role_budget_off"),
        },
        {
            "id": "T03_session_replay_schema_on",
            "label": "Session failure replays, role budgets, API schema on",
            "request": goal,
            "tasks": list(SESSION_REPLAY_TASKS),
            "profiles": _profiles_uniform(_profile_all_schema_on(), "api_schema_on"),
        },
        {
            "id": "T04_session_replay_golden_budgets",
            "label": "Session replays with golden-session per-role budgets",
            "request": goal,
            "tasks": list(SESSION_REPLAY_TASKS),
            "profiles": _profiles_golden_per_role(list(SESSION_REPLAY_TASKS)),
        },
        {
            "id": "T05_fission_golden_vs_postfix",
            "label": "Fission judge: golden 224/192 vs post-fix vs schema variants",
            "request": goal,
            "tasks": [fission_task] * 5,
            "profiles": [
                {"id": "golden_fission", "label": "golden 224/192 schema off", "overrides": _profile_golden_fission()},
                {"id": "postfix_fission", "label": "post-fix role budget", "overrides": _profile_postfix_fission()},
                {"id": "schema_on_fission", "label": "post-fix + api_schema", "overrides": {**_profile_postfix_fission(), "api_schema": True}},
                {"id": "low_think_fission", "label": "thinking=64 max=768", "overrides": {"api_schema": False, "thinking_budget": 64, "max_tokens": 768}},
                {"id": "high_think_fission", "label": "thinking=512 max=224", "overrides": {"api_schema": False, "thinking_budget": 512, "max_tokens": 224}},
            ],
        },
        {
            "id": "T06_verifier_routed_matrix",
            "label": "Verifier routed vs posted with schema on/off",
            "request": goal,
            "tasks": verifier_tasks * 2 + [verifier_tasks[0]],
            "profiles": [
                {"id": "v_routed_off", "label": "routed schema off", "overrides": _profile_role_budgets()},
                {"id": "v_routed_on", "label": "routed schema on", "overrides": _profile_all_schema_on()},
                {"id": "v_posted_off", "label": "posted schema off", "overrides": _profile_role_budgets()},
                {"id": "v_posted_on", "label": "posted schema on", "overrides": _profile_all_schema_on()},
                {"id": "v_routed_golden", "label": "routed golden verifier budget", "overrides": {"api_schema": False, **GOLDEN_SESSION_BUDGETS["verifier"]}},
            ],
        },
        {
            "id": "T07_default_all_schema_on",
            "label": "Default tasks, all slots api_schema on",
            "request": goal,
            "tasks": list(BENCHMARK_TASKS),
            "profiles": _profiles_uniform(_profile_all_schema_on(), "all_schema_on"),
        },
        {
            "id": "T08_default_all_schema_off",
            "label": "Default tasks, role budgets only",
            "request": goal,
            "tasks": list(BENCHMARK_TASKS),
            "profiles": _profiles_uniform(_profile_role_budgets(), "all_schema_off"),
        },
        {
            "id": "T09_planner_budget_sweep",
            "label": "Planner maintenance with budget sweep",
            "request": goal,
            "tasks": [BENCHMARK_TASKS[0]] * 5,
            "profiles": [
                {"id": "p_golden", "label": "golden planner 1152/1536", "overrides": {"api_schema": False, **GOLDEN_SESSION_BUDGETS["planner"]}},
                {"id": "p_postfix", "label": "post-fix role budget", "overrides": _profile_role_budgets()},
                {"id": "p_schema_on", "label": "post-fix api_schema", "overrides": _profile_all_schema_on()},
                {"id": "p_low_think", "label": "thinking=256 max=1400", "overrides": {"api_schema": False, "thinking_budget": 256, "max_tokens": 1400}},
                {"id": "p_high_think", "label": "thinking=1536 max=512", "overrides": {"api_schema": False, "thinking_budget": 1536, "max_tokens": 512}},
            ],
        },
        {
            "id": "T10_repeat_schema_on_session",
            "label": "Repeat T03 stability check",
            "request": goal,
            "tasks": list(SESSION_REPLAY_TASKS),
            "profiles": _profiles_uniform(_profile_all_schema_on(), "api_schema_on_repeat"),
        },
    ]


def _format_campaign_section(report: dict[str, Any]) -> str:
    lines = [
        f"## {report.get('suite_id', 'run')} — {report.get('suite_label', '')}",
        "",
        f"- **Time:** {report.get('timestamp', '')}",
        f"- **Wall:** {report.get('wall_ms', 0)} ms",
        f"- **Model:** {report.get('model', '?')}",
        f"- **Host:** {report.get('host', '?')}",
        f"- **Request:** {report.get('request', '')}",
        f"- **Pass:** {report.get('ok', False)}",
        "",
        "| Slot | Task | Profile | Role | ms | JSON | Quality | Score | Reason |",
        "|------|------|---------|------|-----|------|---------|-------|--------|",
    ]
    for row in report.get("slots", []):
        lines.append(
            f"| {row.get('slot')} | {row.get('task_id')} | {row.get('profile_id')} | "
            f"{row.get('role')} | {row.get('elapsed_ms')} | "
            f"{'Y' if row.get('json_valid') else 'N'} | "
            f"{'Y' if row.get('quality_ok') else 'N'} | {row.get('quality_score')} | "
            f"{row.get('quality_reason', '')} |"
        )
    lines.append("")
    lines.append("**Ranking:**")
    for rank in report.get("ranking", []):
        lines.append(
            f"- `{rank['profile_id']}`: score={rank['avg_score']} avg_ms={rank['avg_ms']} "
            f"json={rank['json_valid']}/{rank.get('slots', 1)} quality={rank['quality_ok']}/{rank.get('slots', 1)} "
            f"empty={rank['empty_output']}"
        )
    lines.append("")
    return "\n".join(lines)


def _append_campaign_markdown(path: Path, section: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        header = (
            "# LM Studio Parameter Benchmark Campaign\n\n"
            f"Session replay source: `sessions/20260614_175152`\n\n"
            "Budgets use project `config.BUDGET` / `THINKING_BUDGET` unless profile overrides golden session values.\n\n"
        )
        path.write_text(header, encoding="utf-8")
    with path.open("a", encoding="utf-8") as fh:
        fh.write(section)
        fh.write("\n")


def _comparison_table(reports: list[dict[str, Any]]) -> str:
    lines = [
        "## Final comparison table",
        "",
        "| Suite | Pass | Wall ms | Avg score | Best profile | Empty outputs | Notes |",
        "|-------|------|---------|-----------|--------------|---------------|-------|",
    ]
    for report in reports:
        ranking = report.get("ranking", [])
        best = ranking[0] if ranking else {}
        empty = sum(int(r.get("empty_output", 0)) for r in report.get("slots", []))
        avg_score = round(
            sum(int(r.get("quality_score", 0) or 0) for r in report.get("slots", []))
            / max(1, len(report.get("slots", []))),
            1,
        )
        notes = []
        if empty:
            notes.append(f"{empty} empty")
        if not report.get("ok"):
            fails = [r for r in report.get("slots", []) if not r.get("quality_ok")]
            if fails:
                notes.append(fails[0].get("quality_reason", ""))
        lines.append(
            f"| {report.get('suite_id')} | {'PASS' if report.get('ok') else 'FAIL'} | "
            f"{report.get('wall_ms')} | {avg_score} | {best.get('profile_id', '-')} | {empty} | "
            f"{'; '.join(notes) or 'ok'} |"
        )
    lines.append("")
    return "\n".join(lines)


def run_benchmark_campaign(
    *,
    minutes: float = 30.0,
    md_path: str = "runtime/BENCH_CAMPAIGN_20260614.md",
    request: str = "",
    base_profile: str = "nemotron_parallel",
    parallel: int = 5,
) -> dict[str, Any]:
    """Run campaign suites until time budget elapses; append markdown after each test."""
    doc_path = Path(md_path)
    suites = _campaign_suite_definitions()
    reports: list[dict[str, Any]] = []
    started = time.time()
    deadline = started + (minutes * 60)
    cycle = 0
    _append_campaign_markdown(
        doc_path,
        f"\n---\n\n## Campaign run started {time.strftime('%Y-%m-%dT%H:%M:%S')} "
        f"(budget {minutes} min, profile {base_profile})\n",
    )

    while time.time() < deadline:
        for suite in suites:
            if time.time() >= deadline:
                break
            report = run_param_benchmark(
                request=request or suite.get("request", _DEFAULT_BENCH_GOAL),
                base_profile=base_profile,
                tasks=list(suite["tasks"]),
                profiles=list(suite["profiles"]),
                parallel=parallel,
                suite_id=str(suite["id"]),
            )
            report["suite_label"] = suite.get("label", "")
            report["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            reports.append(report)
            _append_campaign_markdown(doc_path, _format_campaign_section(report))
            cycle += 1
        if cycle >= 1 and time.time() < deadline:
            # second pass on high-signal suites if time remains
            for suite_id in ("T03_session_replay_schema_on", "T05_fission_golden_vs_postfix", "T09_planner_budget_sweep"):
                if time.time() >= deadline:
                    break
                suite = next(item for item in suites if item["id"] == suite_id)
                report = run_param_benchmark(
                    request=request or suite.get("request", _DEFAULT_BENCH_GOAL),
                    base_profile=base_profile,
                    tasks=list(suite["tasks"]),
                    profiles=list(suite["profiles"]),
                    parallel=parallel,
                    suite_id=f"{suite['id']}_cycle{cycle + 1}",
                )
                report["suite_label"] = suite.get("label", "") + f" (cycle {cycle + 1})"
                report["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                reports.append(report)
                _append_campaign_markdown(doc_path, _format_campaign_section(report))
            break

    _append_campaign_markdown(doc_path, _comparison_table(reports))
    elapsed_min = round((time.time() - started) / 60, 2)
    summary = {
        "ok": all(item.get("ok") for item in reports),
        "tests_run": len(reports),
        "elapsed_min": elapsed_min,
        "md_path": str(doc_path),
        "reports": [
            {
                "suite_id": item.get("suite_id"),
                "ok": item.get("ok"),
                "wall_ms": item.get("wall_ms"),
                "avg_score": round(
                    sum(int(r.get("quality_score", 0) or 0) for r in item.get("slots", []))
                    / max(1, len(item.get("slots", []))),
                    1,
                ),
            }
            for item in reports
        ],
    }
    _append_campaign_markdown(
        doc_path,
        f"## Campaign summary\n\n- Tests run: {summary['tests_run']}\n"
        f"- Elapsed: {summary['elapsed_min']} min\n"
        f"- Markdown: `{summary['md_path']}`\n",
    )
    return summary


def _parse_bench_profiles_json(path: str) -> list[dict[str, Any]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("profiles JSON must be a list")
    return raw


def _cli_param_benchmark(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Live LM Studio parameter benchmark — 5 fixed tasks × 5 fixed profiles in parallel.",
    )
    parser.add_argument(
        "--request", "-r",
        default="",
        help="Goal/request string injected into task prompts (default: maintenance audit goal).",
    )
    parser.add_argument(
        "--profile", "-p",
        default="nemotron_parallel",
        help="Base model profile applied before per-slot overrides (default: nemotron_parallel).",
    )
    parser.add_argument(
        "--parallel", type=int, default=5, help="Max concurrent LM Studio requests (default: 5).")
    parser.add_argument(
        "--profiles-json",
        default="",
        help="Optional JSON file replacing the built-in 5 hyperparameter profiles.",
    )
    parser.add_argument(
        "--output", "-o",
        default="",
        help="Write full JSON report to this path.",
    )
    parser.add_argument(
        "--slot",
        type=int,
        action="append",
        default=[],
        help="Slot index (1-5) to override; pair with --temperature etc.",
    )
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--thinking-budget", type=int, default=None)
    parser.add_argument("--api-schema", choices=["true", "false"], default=None)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args(argv)

    profiles = None
    if args.profiles_json:
        profiles = _parse_bench_profiles_json(args.profiles_json)

    slot_overrides: dict[int, dict[str, Any]] = {}
    if args.slot:
        override: dict[str, Any] = {}
        if args.temperature is not None:
            override["temperature"] = args.temperature
        if args.max_tokens is not None:
            override["max_tokens"] = args.max_tokens
        if args.thinking_budget is not None:
            override["thinking_budget"] = args.thinking_budget
        if args.api_schema is not None:
            override["api_schema"] = args.api_schema == "true"
        if args.seed is not None:
            override["seed"] = args.seed
        for slot in args.slot:
            if slot < 1 or slot > 5:
                parser.error("--slot must be between 1 and 5")
            slot_overrides[slot - 1] = dict(override)

    report = run_param_benchmark(
        request=args.request,
        base_profile=args.profile,
        profiles=profiles,
        parallel=args.parallel,
        slot_overrides=slot_overrides or None,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
    print(text)
    print(
        f"\nSUMMARY wall={report['wall_ms']}ms model={report.get('model', '?')} "
        f"request={report['request'][:60]!r}"
    )
    for row in report.get("ranking", []):
        print(
            f"  {row['profile_id']}: score={row['avg_score']} "
            f"avg={row['avg_ms']}ms json={row['json_valid']}/{row.get('slots', 1)} "
            f"quality={row['quality_ok']}/{row.get('slots', 1)} empty={row['empty_output']}"
        )
    return 0 if report.get("ok") else 1


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
        return False, "done_response"
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
    elif len(sys.argv) >= 2 and sys.argv[1] == "param-bench":
        raise SystemExit(_cli_param_benchmark(sys.argv[2:]))
    elif len(sys.argv) >= 2 and sys.argv[1] == "param-bench-campaign":
        camp = argparse.ArgumentParser(description="30-minute LM Studio benchmark campaign with session replays.")
        camp.add_argument("--minutes", type=float, default=30.0)
        camp.add_argument("--md", default="runtime/BENCH_CAMPAIGN_20260614.md")
        camp.add_argument("--request", "-r", default="")
        camp.add_argument("--profile", default="nemotron_parallel")
        camp.add_argument("--parallel", type=int, default=5)
        args = camp.parse_args(sys.argv[2:])
        summary = run_benchmark_campaign(
            minutes=args.minutes,
            md_path=args.md,
            request=args.request,
            base_profile=args.profile,
            parallel=args.parallel,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        raise SystemExit(0 if summary.get("ok") else 1)
    else:
        print("Usage:")
        print("  python llm.py bench")
        print("  python llm.py param-bench --request \"...\" [--profile nemotron_parallel] [--parallel 5]")
        print("  python llm.py param-bench-campaign --minutes 30 --md runtime/BENCH_CAMPAIGN_20260614.md")
        print("  python llm.py param-bench --slot 3 --api-schema true --max-tokens 512")
