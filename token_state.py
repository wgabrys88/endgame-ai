from __future__ import annotations

import time
from typing import Any

import config


def initial_state() -> dict[str, Any]:
    return {
        "last_role": "",
        "last_backend": "",
        "last_prompt_est": 0,
        "last_completion_est": 0,
        "last_total_est": 0,
        "last_prompt_actual": None,
        "last_completion_actual": None,
        "last_total_actual": None,
        "last_max_effective": 0,
        "last_warning": "",
        "cumulative_prompt_est": 0,
        "cumulative_completion_est": 0,
        "cumulative_total_est": 0,
        "cumulative_prompt_actual": 0,
        "cumulative_completion_actual": 0,
        "cumulative_total_actual": 0,
        "calls": 0,
        "per_agent": {},
        "burn_rate_tpm": 0.0,
        "remaining_context_pct": 100.0,
        "trace": [],
        "warnings": [],
    }


def record_reply(state: dict[str, Any] | None, reply: Any) -> dict[str, Any]:
    current = _copy_state(state)
    event = _event_from_reply(reply)
    now = time.time()
    role = str(event.get("role", ""))
    backend = str(event.get("backend", ""))
    prompt_est = int(event.get("prompt_est") or 0)
    completion_est = int(event.get("completion_est") or 0)
    total_est = int(event.get("total_est") or prompt_est + completion_est)
    prompt_actual = _maybe_int(event.get("prompt_actual"))
    completion_actual = _maybe_int(event.get("completion_actual"))
    total_actual = _maybe_int(event.get("total_actual"))
    max_effective = int(event.get("max_effective") or 0)
    context_limit = int(event.get("context_limit") or getattr(config, "LLM_MAX_TOKENS", 200000))
    warning = str(event.get("warning") or "")

    current["last_role"] = role
    current["last_backend"] = backend
    current["last_prompt_est"] = prompt_est
    current["last_completion_est"] = completion_est
    current["last_total_est"] = total_est
    current["last_prompt_actual"] = prompt_actual
    current["last_completion_actual"] = completion_actual
    current["last_total_actual"] = total_actual
    current["last_max_effective"] = max_effective
    current["last_warning"] = warning
    current["calls"] = int(current.get("calls", 0)) + 1
    current["cumulative_prompt_est"] = int(current.get("cumulative_prompt_est", 0)) + prompt_est
    current["cumulative_completion_est"] = int(current.get("cumulative_completion_est", 0)) + completion_est
    current["cumulative_total_est"] = int(current.get("cumulative_total_est", 0)) + total_est
    if prompt_actual is not None:
        current["cumulative_prompt_actual"] = int(current.get("cumulative_prompt_actual", 0)) + prompt_actual
    if completion_actual is not None:
        current["cumulative_completion_actual"] = int(current.get("cumulative_completion_actual", 0)) + completion_actual
    if total_actual is not None:
        current["cumulative_total_actual"] = int(current.get("cumulative_total_actual", 0)) + total_actual

    per_agent = dict(current.get("per_agent") or {})
    agent = dict(per_agent.get(role) or {})
    agent["calls"] = int(agent.get("calls", 0)) + 1
    agent["prompt_est"] = int(agent.get("prompt_est", 0)) + prompt_est
    agent["completion_est"] = int(agent.get("completion_est", 0)) + completion_est
    agent["total_est"] = int(agent.get("total_est", 0)) + total_est
    if prompt_actual is not None:
        agent["prompt_actual"] = int(agent.get("prompt_actual", 0)) + prompt_actual
    if completion_actual is not None:
        agent["completion_actual"] = int(agent.get("completion_actual", 0)) + completion_actual
    if total_actual is not None:
        agent["total_actual"] = int(agent.get("total_actual", 0)) + total_actual
    per_agent[role] = agent
    current["per_agent"] = per_agent

    trace_entry = {
        "t": round(now, 3),
        "role": role,
        "backend": backend,
        "prompt": prompt_est,
        "completion": completion_est,
        "total": total_est,
        "actual_total": total_actual,
        "max_effective": max_effective,
        "warning": warning,
    }
    trace = list(current.get("trace") or [])
    trace.append(trace_entry)
    trace_len = int(getattr(config, "TOKEN_TRACE_LEN", 120))
    current["trace"] = trace[-trace_len:]
    current["burn_rate_tpm"] = _burn_rate_tpm(current["trace"], now)
    used = min(context_limit, prompt_est + max_effective)
    current["remaining_context_pct"] = round(100.0 * max(0, context_limit - used) / max(context_limit, 1), 2)

    if warning:
        warnings = list(current.get("warnings") or [])
        warnings.append({"t": round(now, 3), "role": role, "backend": backend, "warning": warning})
        warn_len = int(getattr(config, "TOKEN_WARNING_TRACE_LEN", 20))
        current["warnings"] = warnings[-warn_len:]
    return current


def snapshot(state: dict[str, Any] | None) -> dict[str, Any]:
    current = _copy_state(state)
    trace_len = int(getattr(config, "TOKEN_TRACE_LEN", 120))
    warning_len = int(getattr(config, "TOKEN_WARNING_TRACE_LEN", 20))
    return {
        "last_role": current.get("last_role", ""),
        "last_backend": current.get("last_backend", ""),
        "last_prompt_est": current.get("last_prompt_est", 0),
        "last_completion_est": current.get("last_completion_est", 0),
        "last_total_est": current.get("last_total_est", 0),
        "last_prompt_actual": current.get("last_prompt_actual"),
        "last_completion_actual": current.get("last_completion_actual"),
        "last_total_actual": current.get("last_total_actual"),
        "last_max_effective": current.get("last_max_effective", 0),
        "last_warning": current.get("last_warning", ""),
        "cumulative_prompt_est": current.get("cumulative_prompt_est", 0),
        "cumulative_completion_est": current.get("cumulative_completion_est", 0),
        "cumulative_total_est": current.get("cumulative_total_est", 0),
        "cumulative_prompt_actual": current.get("cumulative_prompt_actual", 0),
        "cumulative_completion_actual": current.get("cumulative_completion_actual", 0),
        "cumulative_total_actual": current.get("cumulative_total_actual", 0),
        "calls": current.get("calls", 0),
        "per_agent": current.get("per_agent", {}),
        "burn_rate_tpm": current.get("burn_rate_tpm", 0.0),
        "remaining_context_pct": current.get("remaining_context_pct", 100.0),
        "trace": list(current.get("trace", []))[-trace_len:],
        "warnings": list(current.get("warnings", []))[-warning_len:],
    }


def _copy_state(state: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(state, dict) or not state:
        return initial_state()
    current = initial_state()
    current.update(state)
    current["per_agent"] = dict(current.get("per_agent") or {})
    current["trace"] = list(current.get("trace") or [])
    current["warnings"] = list(current.get("warnings") or [])
    return current


def _event_from_reply(reply: Any) -> dict[str, Any]:
    if isinstance(reply, dict):
        return reply
    if hasattr(reply, "token_event"):
        event = reply.token_event()
        if isinstance(event, dict):
            return event
    return {
        "backend": getattr(reply, "backend", ""),
        "role": getattr(reply, "role", ""),
        "prompt_est": getattr(reply, "prompt_tokens_est", 0),
        "completion_est": getattr(reply, "completion_tokens_est", 0),
        "total_est": getattr(reply, "total_tokens_est", 0),
        "prompt_actual": getattr(reply, "prompt_tokens_actual", None),
        "completion_actual": getattr(reply, "completion_tokens_actual", None),
        "total_actual": getattr(reply, "total_tokens_actual", None),
        "max_effective": getattr(reply, "max_tokens_effective", 0),
        "context_limit": getattr(reply, "context_limit", getattr(config, "LLM_MAX_TOKENS", 200000)),
        "warning": getattr(reply, "warning", ""),
    }


def _maybe_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _burn_rate_tpm(trace: list[dict[str, Any]], now: float) -> float:
    window = float(getattr(config, "TOKEN_BURN_WINDOW_SEC", 300.0))
    recent = [r for r in trace if now - float(r.get("t", now)) <= window]
    if not recent:
        return 0.0
    elapsed = max(1.0, now - float(recent[0].get("t", now)))
    tokens = sum(int(r.get("total") or 0) for r in recent)
    return round(tokens * 60.0 / elapsed, 2)
