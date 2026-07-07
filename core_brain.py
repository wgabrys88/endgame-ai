from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import pathlib
import re
import subprocess
import threading
import time
from typing import Any

import core_stop_check as stop_check
import core_bus as bus
import core_wiring as wiring
import core_state as state

ROOT = pathlib.Path(__file__).parent.resolve()
_EVENT_SEQ = 0
_EVENT_LOCK = threading.Lock()
_CALLS_MADE = 0
_STABLE_PREFIX_CACHE: "StablePrefix | None" = None
_STABLE_PREFIX_LOCK = threading.Lock()
_LAST_FRESH_OBSERVATION: dict[str, Any] | None = None

_OPEN_OBJECT_SCHEMA = {"type": "object", "additionalProperties": True}

STATIC_PREFIX_SUFFIXES = {".py", ".json", ".md"}
STATIC_PREFIX_NAMES = {".gitattributes", ".gitignore", "LICENSE"}
STATIC_PREFIX_SKIP_PARTS = {".git", "__pycache__", ".pytest_cache"}
STATIC_PREFIX_SKIP_PREFIXES = ("runtime_",)


_RECORD_DATA_SCHEMAS: dict[str, dict[str, Any]] = {
    "plan": {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "next_signal": {"enum": ["step_ready", "reflect"]},
            "intent": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": True,
                    "properties": {
                        "description": {"type": "string"},
                        "done_when": {"type": "string"},
                    },
                },
            },
        },
        "required": ["next_signal", "intent"],
    },
    "schedule": {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "next_signal": {"enum": ["step_ready", "plan_complete"]},
            "step": {
                "anyOf": [
                    {"type": "object", "additionalProperties": True},
                    {"type": "null"},
                ]
            },
        },
        "required": ["next_signal", "step"],
    },
    "execution": {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "next_signal": {"enum": ["verify", "frame", "reflect"]},
            "conclusion": {"enum": ["EXECUTE", "CANNOT", "FRAME"]},
            "code": {"type": "string"},
        },
        "required": ["next_signal", "conclusion", "code"],
    },
    "action_frame": {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "next_signal": {"enum": ["framed", "reflect"]},
            "screen_summary": {"type": "string"},
            "target": {"type": "string"},
            "strategy": {"type": "string"},
            "risk": {"enum": ["low", "medium", "high"]},
            "notes": {"type": "string"},
        },
        "required": ["next_signal", "screen_summary", "target", "strategy", "risk", "notes"],
    },
    "verification": {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "next_signal": {"enum": ["step_confirmed", "step_denied"]},
            "success": {"type": "boolean"},
            "reasoning": {"type": "string"},
        },
        "required": ["next_signal", "success", "reasoning"],
    },
    "reflection": {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "next_signal": {"enum": ["retry", "replan", "frame", "escalate", "give_up"]},
            "lesson": {"type": "string"},
            "diagnosis": {"type": "string"},
        },
        "required": ["next_signal", "lesson", "diagnosis"],
    },
    "git_evolution_patch": {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "next_signal": {"enum": ["modified"]},
            "summary": {"type": "string"},
            "rationale": {"type": "string"},
            "read_files": {"type": "array", "items": {"type": "string"}},
            "file_writes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": True,
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
            },
            "file_deletes": {"type": "array", "items": {"type": "string"}},
            "wiring_patches": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": True,
                    "properties": {
                        "op": {"enum": ["set", "delete"]},
                        "path": {"type": "string"},
                    },
                    "required": ["op", "path"],
                },
            },
            "commands": {"type": "array", "items": {"type": "object", "additionalProperties": True}},
            "expected_validation": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "object", "additionalProperties": True},
                    {"type": "null"},
                ]
            },
        },
        "required": ["next_signal", "summary", "rationale", "read_files", "file_writes", "file_deletes", "wiring_patches", "commands", "expected_validation"],
    },
    "satisfied": {
        "type": "object",
        "additionalProperties": True,
        "properties": {"next_signal": {"const": "halt"}},
        "required": ["next_signal"],
    },
}


class StablePrefix:

    def __init__(self, root: pathlib.Path = ROOT):
        self.root = root
        self.files = self._source_files()
        self.text, self.fingerprint = self._render()
        self.cache_key = f"endgame-ai-{self.fingerprint[:24]}"

    def _git(self, args: list[str]) -> str:
        cp = subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True)
        if cp.returncode != 0:
            detail = (cp.stderr or cp.stdout or "").strip()
            raise RuntimeError(f"git {' '.join(args)} failed while building stable prefix: {detail}")
        return cp.stdout

    def _include(self, rel: str) -> bool:
        rel = rel.replace("\\", "/")
        parts = set(pathlib.PurePosixPath(rel).parts)
        if parts & STATIC_PREFIX_SKIP_PARTS:
            return False
        name = pathlib.PurePosixPath(rel).name
        if name.startswith(STATIC_PREFIX_SKIP_PREFIXES):
            return False
        path = pathlib.PurePosixPath(rel)
        return path.name in STATIC_PREFIX_NAMES or path.suffix in STATIC_PREFIX_SUFFIXES

    def _source_files(self) -> list[str]:
        raw = self._git(["ls-files", "-z"])
        files = [item for item in raw.split("\0") if item]
        return sorted(item.replace("\\", "/") for item in files if self._include(item))

    def _read_file(self, rel: str) -> str:
        return (self.root / rel).read_text(encoding="utf-8", errors="replace")

    def _render(self) -> tuple[str, str]:
        digest = hashlib.sha256()
        manifest: list[dict[str, Any]] = []
        file_text: list[tuple[str, str]] = []
        for rel in self.files:
            content = self._read_file(rel)
            encoded = content.encode("utf-8", errors="replace")
            digest.update(rel.encode("utf-8"))
            digest.update(b"\0")
            digest.update(encoded)
            manifest.append({"path": rel, "chars": len(content), "bytes": len(encoded)})
            file_text.append((rel, content))

        chunks = [
            "ENDGAME-AI STABLE PREFIX",
            "This is the real checked-out source used by the local organism.",
            "Provider prompt caches can reuse this prefix because dynamic run data appears after it.",
            "Self-evolution must ground changes in these files, not in hallucinated structure.",
            "",
            "ORGANISM OPERATING RULES:",
            "You are one organ of endgame-ai, a real local Windows desktop organism controlled by the Python body.",
            "The body can observe the actual desktop through UIA, control real GUI nodes, and run Python/process/file/browser actions with local process permissions.",
            "GUI control and Python/process control are equal first-class powers. The organism lives in a bus-routed organ graph, not a linear conveyor belt.",
            "Organs: planner architects semantic obligations, scheduler selects a step, observe scans the desktop, frame shapes a route, execute acts, verify witnesses proof, reflect judges routing, self_modify performs rare surgery, satisfied halts, error routes mechanical failures.",
            "Most failures are task-route failures. Only true consumed organism-contract failures justify reflect -> self_modify escalation.",
            "Execute is an actor, not a doctor. Broken emitted code is actor evidence, not permission to rewrite the organism.",
            "Prompts are runtime code. Stay strictly in your assigned organ role. Do not perform another organ's job. Do not escape your contract by rewriting the codebase.",
            "Every brain call receives fresh_observation from the observe node state patch. No rescan fallback exists.",
            "The brain-facing desktop_tree is semantic and id-based. Coordinates, hwnds, runtime ids, and UIA metadata live in body-side action_index/raw artifacts; act by node id. Use focused observation helpers when whole-screen evidence is too shallow.",
            "",
            "STATIC MANIFEST:",
            json.dumps(manifest, ensure_ascii=False, indent=2),
            "",
            "STATIC SOURCE FILES:",
        ]
        for rel, content in file_text:
            chunks.append(f"\n--- BEGIN FILE {rel} ---")
            chunks.append(content)
            chunks.append(f"--- END FILE {rel} ---")
        return "\n".join(chunks), digest.hexdigest()

    def metadata(self) -> dict[str, Any]:
        return {
            "fingerprint": self.fingerprint,
            "cache_key": self.cache_key,
            "files": self.files,
            "chars": len(self.text),
        }

def stable_prefix() -> StablePrefix:
    global _STABLE_PREFIX_CACHE
    with _STABLE_PREFIX_LOCK:
        fresh = StablePrefix(ROOT)
        if _STABLE_PREFIX_CACHE is None or _STABLE_PREFIX_CACHE.fingerprint != fresh.fingerprint:
            _STABLE_PREFIX_CACHE = fresh
        return _STABLE_PREFIX_CACHE


def _stable_prefix_enabled(w: dict[str, Any]) -> bool:
    sp_cfg = w.get("model", {}).get("stable_prefix", {})
    return bool(sp_cfg.get("enabled", False))


def _stable_prefix_include_in_request(w: dict[str, Any]) -> bool:
    sp_cfg = w.get("model", {}).get("stable_prefix", {})
    return bool(sp_cfg.get("include_in_request", False))


def _messages(system_prompt: str, user_text: str, prefix: StablePrefix | None, stable_context: str = "") -> list[dict[str, str]]:
    system = system_prompt
    if stable_context:
        system = system + "\n\n" + stable_context
    if prefix is not None:
        system = prefix.text + "\n\n" + system
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_text},
    ]


def _commit_record(content: str, expected_record_type: str | None = None) -> bus.Record:
    record = extract_json_object(content)
    if record is None:
        raise RuntimeError(f"brain did not commit a valid JSON object: {content}")
    if not isinstance(record.get("record_type"), str):
        raise RuntimeError(f"brain record missing string record_type: {record}")
    if "data" not in record or not isinstance(record["data"], dict):
        raise RuntimeError(f"brain record missing object data: {record}")
    committed = bus.Record.from_json(record)
    _validate_record_contract(committed, expected_record_type)
    return committed


def _validate_record_contract(record: bus.Record, expected_record_type: str | None = None) -> None:
    if expected_record_type and record.record_type != expected_record_type:
        raise RuntimeError(
            f"brain record_type mismatch: expected {expected_record_type!r}, got {record.record_type!r}"
        )
    schema = _RECORD_DATA_SCHEMAS.get(record.record_type)
    if not schema:
        return
    data = record.data
    missing = [key for key in schema.get("required", []) if key not in data]
    if missing:
        raise RuntimeError(f"{record.record_type} record missing required data keys: {missing}")
    properties = schema.get("properties", {})
    for key, rule in properties.items():
        if key not in data or not isinstance(rule, dict):
            continue
        value = data.get(key)
        if "const" in rule and value != rule["const"]:
            raise RuntimeError(f"{record.record_type}.data.{key} must be {rule['const']!r}, got {value!r}")
        if "enum" in rule and value not in set(rule["enum"]):
            raise RuntimeError(f"{record.record_type}.data.{key}={value!r} outside {rule['enum']!r}")


def _organ_tuning(w: dict[str, Any], record_type: str | None) -> dict[str, Any]:
    organs = w.get("model", {}).get("organs", {})
    if not record_type or not isinstance(organs, dict):
        return {}
    organ = organs.get(record_type)
    return dict(organ) if isinstance(organ, dict) else {}


def _effective_reasoning_config(w: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    reasoning_cfg = dict(cfg.get("reasoning") or {})
    reasoning_cfg["enabled"] = bool(reasoning_cfg.get("enabled", False))
    reasoning_cfg.setdefault("pattern", "two_pass" if reasoning_cfg["enabled"] else "single_pass")
    reasoning_cfg.setdefault("extractor", "think_tags")
    reasoning_cfg.setdefault("injection_template", "REASONING_FEEDBACK:\n{reasoning}\n\nReturn only the requested JSON record.")
    return reasoning_cfg


def _normalize_observation(obj: Any) -> dict[str, Any] | None:
    if not isinstance(obj, dict) or not obj.get("desktop_tree_text"):
        return None
    return {
        "desktop_tree_text": obj.get("desktop_tree_text", ""),
        "observed_at": obj.get("observed_at"),
        "fresh_scan": obj.get("fresh_scan", True),
    }


def _fresh_observation_payload(w: dict[str, Any], payload: dict[str, Any] | None = None) -> dict[str, Any]:
    global _LAST_FRESH_OBSERVATION
    if payload:
        candidates = [payload.get("fresh_observation"), payload.get("observation")]
        evidence = payload.get("evidence")
        if isinstance(evidence, dict):
            candidates.extend([evidence.get("fresh_observation"), evidence.get("observation")])
        for candidate in candidates:
            normalized = _normalize_observation(candidate)
            if normalized is not None:
                _LAST_FRESH_OBSERVATION = normalized
                return normalized
    raise RuntimeError("fresh_observation missing: observe node must run before any brain call")


def last_fresh_observation() -> dict[str, Any]:
    return dict(_LAST_FRESH_OBSERVATION or {})


def _with_fresh_observation(payload: dict[str, Any], w: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(payload)
    enriched["fresh_observation"] = _fresh_observation_payload(w, enriched)
    if isinstance(enriched.get("observation"), dict) and enriched["observation"].get("desktop_tree_text"):
        enriched.pop("observation", None)
    return enriched


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"malformed JSON in {path}: {exc}") from exc


def atomic_write_json(path: pathlib.Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}.{threading.get_ident()}")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def append_ndjson(path: pathlib.Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")


def _next_event_seq() -> int:
    global _EVENT_SEQ
    with _EVENT_LOCK:
        _EVENT_SEQ += 1
        return _EVENT_SEQ


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _json_payload(content: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return content


def summarize_messages_for_log(messages: list[dict[str, str]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for message in messages:
        role = str(message.get("role") or "user")
        content = str(message.get("content") or "")
        row: dict[str, Any] = {
            "role": role,
            "chars": len(content),
            "sha256": _sha256_text(content),
            "content": content,
        }
        if role == "user":
            row["dynamic_payload"] = _json_payload(content)
        summary.append(row)
    return summary


def log_runtime_event(cfg: dict[str, Any] | None, event: str, **payload: Any) -> None:
    row = {
        "schema": "endgame-ai.runtime-event.v1",
        "ts": time.time(),
        "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        "event": event,
        **payload,
    }
    append_ndjson(wiring.event_log_path(cfg) if cfg else wiring.event_log_path({}), row)


def reset_call_budget() -> None:
    global _CALLS_MADE
    _CALLS_MADE = 0


def _load_transport_module(name: str, w: dict[str, Any]):
    brain_dir = wiring.root_path(w.get("paths", {}).get("brains"), ".")
    module_path = brain_dir / f"{name}.py"
    if not module_path.exists():
        raise RuntimeError(
            f"selected brain transport '{name}' has no module at {module_path}; "
            "brain selection is fail-hard and no fallback was attempted"
        )
    spec = importlib.util.spec_from_file_location(f"endgame_brain_transport_{name}", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load selected brain transport module: {module_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "call"):
        raise RuntimeError(f"brain transport '{name}' does not export call(messages, cfg)")
    return mod


def _get_transport_config(w: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    model = w.get("model")
    if not isinstance(model, dict):
        raise RuntimeError("wiring.json missing object model")

    transport = str(model.get("transport") or "").strip()
    if not transport:
        raise RuntimeError("wiring model.transport is empty; no fallback transport is allowed")

    transport_config = model.get("transport_config", {})
    if not isinstance(transport_config, dict) or transport not in transport_config:
        raise RuntimeError(f"wiring model.transport_config.{transport} missing; no fallback transport config is allowed")
    cfg = dict(transport_config[transport])

    global_keys = {"timeout", "brain_call_budget"}
    global_cfg = model.get("global", {})
    for k in global_keys:
        if isinstance(global_cfg, dict) and k in global_cfg and k not in cfg:
            cfg[k] = global_cfg[k]
        if k in model and k not in cfg:
            cfg[k] = model[k]
    paths = w.get("paths", {})
    if isinstance(paths, dict):
        cfg.setdefault("event_log_path", paths.get("event_log") or "runtime_events.jsonl")

    cfg["transport"] = transport
    return transport, cfg


def _structured_outputs_enabled(cfg: dict[str, Any]) -> bool:
    structured = cfg.get("structured_outputs")
    if isinstance(structured, dict):
        return bool(structured.get("enabled", False))
    return bool(structured)


def _record_response_format(record_type: str) -> dict[str, Any]:
    data_schema = _RECORD_DATA_SCHEMAS.get(record_type)
    if data_schema:
        return {
            "type": "json_schema",
            "name": f"{record_type}_record",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "record_type": {"enum": [record_type]},
                    "data": data_schema,
                    "reasoning": {"type": "string"},
                },
                "required": ["record_type", "data", "reasoning"],
            },
        }
    return {
        "type": "json_object",
    }


def call(
    messages: list[dict[str, str]],
    w: dict[str, Any],
    *,
    rod_feedback: bool = False,
    response_format: dict[str, Any] | None = None,
    request_config: dict[str, Any] | None = None,
) -> dict[str, str]:
    stop_check.check_stop("brain call")
    global _CALLS_MADE
    transport, cfg = _get_transport_config(w)
    if response_format is not None:
        cfg = dict(cfg)
        cfg["response_format"] = response_format
    if request_config:
        cfg = dict(cfg)
        cfg.update(request_config)
    model_cfg = w.get("model", {})
    max_calls = model_cfg.get("brain_call_budget")
    if max_calls is None and isinstance(model_cfg.get("global"), dict):
        max_calls = model_cfg["global"].get("brain_call_budget")
    if max_calls is not None and _CALLS_MADE >= int(max_calls):
        raise RuntimeError(f"brain call budget exceeded: {_CALLS_MADE}/{max_calls}")
    _CALLS_MADE += 1
    seq = _next_event_seq()
    started = time.time()
    log_runtime_event(cfg, "brain_request", **{
        "seq": seq,
        "transport": transport,
        "rod_feedback": rod_feedback,
        "prompt_cache_key": cfg.get("prompt_cache_key"),
        "stable_prefix": cfg.get("stable_prefix"),
        "response_format": cfg.get("response_format"),
        "messages": summarize_messages_for_log(messages),
    })
    _check_message_size(messages, w)
    mod = _load_transport_module(transport, w)
    try:
        result = mod.call(messages, cfg)
    except Exception as exc:
        log_runtime_event(cfg, "brain_error", **{
            "seq": seq,
            "transport": transport,
            "elapsed_s": round(time.time() - started, 3),
            "error": f"{type(exc).__name__}: {exc}",
        })
        raise RuntimeError(f"{transport} brain failed hard: {exc}") from exc
    if not isinstance(result, dict):
        raise RuntimeError(f"{transport} brain contract violation: expected dict, got {type(result).__name__}")
    content = result.get("content")
    reasoning = result.get("reasoning", "")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(f"{transport} brain contract violation: missing non-empty content")
    if reasoning is not None and not isinstance(reasoning, str):
        raise RuntimeError(f"{transport} brain contract violation: reasoning must be string when present")
    out = {"content": content, "reasoning": reasoning or ""}
    log_runtime_event(cfg, "brain_response", **{
        "seq": seq,
        "transport": transport,
        "elapsed_s": round(time.time() - started, 3),
        "content": content,
        "reasoning": reasoning or "",
        "raw": {k: v for k, v in result.items() if k not in {"content", "reasoning"}},
    })
    return out


def _check_message_size(messages: list[dict[str, str]], w: dict[str, Any], max_chars: int = 800000) -> None:
    """Safety guard: reject requests exceeding max_chars before sending to transport."""
    total = sum(len(str(m.get("content", ""))) for m in messages)
    if total > max_chars:
        transport, cfg = _get_transport_config(w)
        log_runtime_event(cfg, "brain_request_rejected", **{
            "transport": transport,
            "total_chars": total,
            "max_chars": max_chars,
            "message_sizes": [{"role": m.get("role"), "chars": len(str(m.get("content", "")))} for m in messages],
        })
        raise RuntimeError(f"brain request rejected: {total} chars exceeds limit {max_chars}. Reduce observation data or use focused observation.")


def reasoning_from(content: str, reasoning: str = "") -> str:
    if reasoning and reasoning.strip():
        return reasoning.strip()
    m = re.search(r"think(.*?)answer", content or "", flags=re.S | re.I)
    if m:
        return m.group(1).strip()
    return (content or "").strip()


def extract_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    s = text.strip()
    if "```" in s.lower():
        s = re.split(r"", s, maxsplit=1, flags=re.I)[-1].strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", s, flags=re.S | re.I)
    if fenced:
        s = fenced.group(1).strip()
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    starts: list[int] = []
    candidates: list[str] = []
    in_str = False
    esc = False
    depth = 0
    start = -1
    for i, ch in enumerate(s):
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
                starts.append(i)
            depth += 1
        elif ch == "}":
            if depth:
                depth -= 1
                if depth == 0 and start >= 0:
                    candidates.append(s[start:i + 1])
    for candidate in reversed(candidates):
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def think(
    system_prompt: str,
    payload: dict[str, Any],
    w: dict[str, Any],
    *,
    expected_record_type: str | None = None,
    request_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _, cfg = _get_transport_config(w)
    reasoning_cfg = _effective_reasoning_config(w, cfg)

    prefix = stable_prefix() if _stable_prefix_enabled(w) else None

    prefix_for_messages = prefix if _stable_prefix_include_in_request(w) else None

    conv_id = w.get("_conv_id")
    if not conv_id:
        import hashlib, time
        conv_id = f"endgame-ai-{int(time.time())}-{hashlib.md5(str(w).encode()).hexdigest()[:8]}"
        w["_conv_id"] = conv_id

    payload = _with_fresh_observation(payload, w)
    goal = ""
    if isinstance(payload, dict) and "goal" in payload:
        goal = str(payload.pop("goal") or "")
    stable_context = f"CURRENT GOAL (fixed for this run):\n{goal}" if goal else ""
    user_text = json.dumps(payload, ensure_ascii=False, default=str)
    pattern = str(reasoning_cfg.get("pattern") or "single_pass")
    response_format = (
        _record_response_format(expected_record_type)
        if expected_record_type and _structured_outputs_enabled(cfg)
        else None
    )
    request_cfg = dict(request_config or {})
    request_cfg["expected_record_type"] = expected_record_type
    if prefix is not None:
        request_cfg["stable_prefix"] = prefix.metadata()

    tuning = _organ_tuning(w, expected_record_type)
    if tuning.get("reasoning_effort") is not None:
        request_cfg.setdefault("reasoning_effort", tuning["reasoning_effort"])
    if tuning.get("max_output_tokens") is not None:
        request_cfg.setdefault("max_output_tokens", tuning["max_output_tokens"])

    if cfg.get("transport") == "transport_xai":
        request_cfg.setdefault("prompt_cache_key", prefix.cache_key if prefix is not None else conv_id)

    if not reasoning_cfg["enabled"] or pattern == "single_pass":
        result = call(
            _messages(system_prompt, user_text, prefix_for_messages, stable_context),
            w,
            rod_feedback=False,
            response_format=response_format,
            request_config=request_cfg,
        )
        record = _commit_record(result["content"], expected_record_type)
        reasoning = reasoning_from(result["content"], result.get("reasoning", ""))
        record = bus.Record(record.record_type, record.data, reasoning)
        return record.to_json()

    if pattern == "native":
        result = call(
            _messages(system_prompt, user_text, prefix_for_messages, stable_context),
            w,
            rod_feedback=False,
            response_format=response_format,
            request_config=request_cfg,
        )
        record = _commit_record(result["content"], expected_record_type)
        reasoning = reasoning_from(result["content"], result.get("reasoning", ""))
        record = bus.Record(record.record_type, record.data, reasoning)
        return record.to_json()

    if pattern != "two_pass":
        raise RuntimeError(f"unknown reasoning pattern: {pattern}")

    first = call(_messages(system_prompt, user_text, prefix_for_messages, stable_context), w, rod_feedback=False, request_config=request_cfg)
    reasoning = reasoning_from(first["content"], first.get("reasoning", ""))
    template = str(reasoning_cfg.get("injection_template") or "REASONING_FEEDBACK:\n{reasoning}")
    second = call(
        _messages(system_prompt, user_text + "\n\n" + template.format(reasoning=reasoning), prefix_for_messages, stable_context),
        w,
        rod_feedback=True,
        response_format=response_format,
        request_config=request_cfg,
    )
    record = _commit_record(second["content"], expected_record_type)
    record = bus.Record(record.record_type, record.data, reasoning)
    return record.to_json()


def read_runtime_event_tail(path: pathlib.Path | None = None, *, max_lines: int = 200, max_bytes: int = 600_000) -> list[dict[str, Any]]:
    p = path or wiring.event_log_path({})
    if not p.exists():
        return []
    size = p.stat().st_size
    with p.open("rb") as f:
        if size > max_bytes:
            f.seek(size - max_bytes)
            f.readline()
        raw = f.read()
    rows: list[dict[str, Any]] = []
    for line in raw.decode("utf-8", errors="replace").splitlines()[-max_lines:]:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows