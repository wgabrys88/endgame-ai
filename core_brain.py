import hashlib
import json
import os
import pathlib
import re
import subprocess
import threading
import time
from typing import Any

import core_bus as bus
import core_loader as loader
import core_stop_check as stop_check
import core_wiring as wiring

ROOT = pathlib.Path(__file__).parent.resolve()
_EVENT_SEQ = 0
_EVENT_LOCK = threading.Lock()
_CALLS_MADE = 0
_STABLE_PREFIX_CACHE: "StablePrefix | None" = None
_STABLE_PREFIX_LOCK = threading.Lock()
_LAST_FRESH_OBSERVATION: dict[str, Any] | None = None

STATIC_PREFIX_SUFFIXES = {".py", ".json", ".md"}
STATIC_PREFIX_NAMES = {".gitattributes", ".gitignore", "LICENSE"}
STATIC_PREFIX_SKIP_PARTS = {".git", "__pycache__", ".pytest_cache"}
STATIC_PREFIX_SKIP_PREFIXES = ("runtime_",)


_RECORD_RULES: dict[str, tuple[list[str], dict[str, list[Any]]]] = {
    "plan": (["next_signal", "intent"], {"next_signal": ["step_ready", "reflect"]}),
    "schedule": (["next_signal", "step"], {"next_signal": ["step_ready", "plan_complete"]}),
    "execution": (["next_signal", "conclusion", "code"], {"next_signal": ["verify", "frame", "reflect"], "conclusion": ["EXECUTE", "CANNOT", "FRAME"]}),
    "dispatch": (["next_signal", "faculties", "rationale"], {"next_signal": ["dispatch"]}),
    "action_frame": (["next_signal", "screen_summary", "target", "strategy", "risk", "notes"], {"next_signal": ["framed", "reflect"], "risk": ["low", "medium", "high"]}),
    "verification": (["next_signal", "success", "reasoning"], {"next_signal": ["step_confirmed", "step_denied"]}),
    "reflection": (["next_signal", "lesson", "diagnosis"], {"next_signal": ["retry", "replan", "frame", "escalate", "give_up", "topology_patch", "spawn"]}),
    "git_evolution_patch": (["next_signal", "summary", "rationale", "read_files", "file_writes", "file_deletes", "wiring_patches", "commands", "expected_validation"], {"next_signal": ["modified"]}),
    "satisfied": (["next_signal"], {"next_signal": ["halt"]}),
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
            raise RuntimeError(f"git {' '.join(args)} failed while building stable prefix: {(cp.stderr or cp.stdout or '').strip()}")
        return cp.stdout

    def _include(self, rel: str) -> bool:
        path = pathlib.PurePosixPath(rel.replace("\\", "/"))
        if set(path.parts) & STATIC_PREFIX_SKIP_PARTS or path.name.startswith(STATIC_PREFIX_SKIP_PREFIXES):
            return False
        return path.name in STATIC_PREFIX_NAMES or path.suffix in STATIC_PREFIX_SUFFIXES

    def _source_files(self) -> list[str]:
        return sorted(item.replace("\\", "/") for item in self._git(["ls-files", "-z"]).split("\0") if item and self._include(item))

    def _render(self) -> tuple[str, str]:
        digest = hashlib.sha256()
        manifest: list[dict[str, Any]] = []
        chunks = ["ENDGAME-AI STABLE PREFIX", "Tracked source below is the self-evolution substrate.", "", "STATIC MANIFEST:"]
        file_text: list[tuple[str, str]] = []
        for rel in self.files:
            content = (self.root / rel).read_text(encoding="utf-8", errors="replace")
            encoded = content.encode("utf-8", errors="replace")
            digest.update(rel.encode()); digest.update(b"\0"); digest.update(encoded)
            manifest.append({"path": rel, "chars": len(content), "bytes": len(encoded)})
            file_text.append((rel, content))
        chunks.extend([json.dumps(manifest, ensure_ascii=False, indent=2), "", "STATIC SOURCE FILES:"])
        for rel, content in file_text:
            chunks.extend([f"\n--- BEGIN FILE {rel} ---", content, f"--- END FILE {rel} ---"])
        return "\n".join(chunks), digest.hexdigest()

    def metadata(self) -> dict[str, Any]:
        return {"fingerprint": self.fingerprint, "cache_key": self.cache_key, "files": self.files, "chars": len(self.text)}


def stable_prefix() -> StablePrefix:
    global _STABLE_PREFIX_CACHE
    with _STABLE_PREFIX_LOCK:
        fresh = StablePrefix(ROOT)
        if _STABLE_PREFIX_CACHE is None or _STABLE_PREFIX_CACHE.fingerprint != fresh.fingerprint:
            _STABLE_PREFIX_CACHE = fresh
        return _STABLE_PREFIX_CACHE


def _messages(system_prompt: str, user_text: str, prefix: StablePrefix | None, stable_context: str = "") -> list[dict[str, str]]:
    system = system_prompt + ("\n\n" + stable_context if stable_context else "")
    if prefix is not None:
        system = prefix.text + "\n\n" + system
    return [{"role": "system", "content": system}, {"role": "user", "content": user_text}]


def _validate_record_contract(record: bus.Record, expected_record_type: str | None = None) -> None:
    if expected_record_type and record.record_type != expected_record_type:
        raise RuntimeError(f"brain record_type mismatch: expected {expected_record_type!r}, got {record.record_type!r}")
    rule = _RECORD_RULES.get(record.record_type)
    if not rule:
        return
    required, enums = rule
    missing = [key for key in required if key not in record.data]
    if missing:
        raise RuntimeError(f"{record.record_type} record missing required data keys: {missing}")
    for key, values in enums.items():
        if key in record.data and record.data[key] not in set(values):
            raise RuntimeError(f"{record.record_type}.data.{key}={record.data[key]!r} outside {values!r}")


def _commit_record(content: str, expected_record_type: str | None = None) -> bus.Record:
    record = extract_json_object(content)
    if record is None:
        raise RuntimeError(f"brain did not commit a valid JSON object: {content}")
    if not isinstance(record.get("record_type"), str) or "data" not in record or not isinstance(record["data"], dict):
        raise RuntimeError(f"brain record must contain string record_type and object data: {record}")
    committed = bus.Record.from_json(record)
    _validate_record_contract(committed, expected_record_type)
    return committed


def _organ_tuning(w: dict[str, Any], record_type: str | None) -> dict[str, Any]:
    organ = w["model"]["organs"].get(record_type) if record_type else None
    return dict(organ) if isinstance(organ, dict) else {}


def _normalize_observation(obj: Any) -> dict[str, Any] | None:
    if not isinstance(obj, dict) or not obj.get("desktop_tree_text"):
        return None
    return {"desktop_tree_text": obj.get("desktop_tree_text", ""), "observed_at": obj.get("observed_at"), "fresh_scan": obj.get("fresh_scan", True)}


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


def summarize_messages_for_log(messages: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for message in messages:
        role = str(message.get("role") or "user")
        content = str(message.get("content") or "")
        row: dict[str, Any] = {"role": role, "chars": len(content), "sha256": _sha256_text(content), "content": content}
        if role == "user":
            try:
                row["dynamic_payload"] = json.loads(content)
            except json.JSONDecodeError:
                row["dynamic_payload"] = content
        out.append(row)
    return out


def log_runtime_event(w: dict[str, Any], event: str, **payload: Any) -> None:
    append_ndjson(wiring.event_log_path(w), {"schema": "endgame-ai.runtime-event.v1", "ts": time.time(), "iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()), "event": event, **payload})


def reset_call_budget() -> None:
    global _CALLS_MADE
    _CALLS_MADE = 0


def _load_transport_module(name: str, w: dict[str, Any]):
    return loader.load("transport", name, w)


def _structured_outputs_enabled(cfg: dict[str, Any]) -> bool:
    structured = cfg.get("structured_outputs")
    return bool(structured.get("enabled", False)) if isinstance(structured, dict) else bool(structured)


def _record_response_format(record_type: str) -> dict[str, Any]:
    return {"type": "json_schema", "name": f"{record_type}_record", "strict": True, "schema": {"type": "object", "additionalProperties": False, "properties": {"record_type": {"enum": [record_type]}, "data": {"type": "object", "additionalProperties": True}, "reasoning": {"type": "string"}}, "required": ["record_type", "data", "reasoning"]}}


def call(messages: list[dict[str, str]], w: dict[str, Any], *, rod_feedback: bool = False, response_format: dict[str, Any] | None = None, request_config: dict[str, Any] | None = None) -> dict[str, str]:
    stop_check.check_stop("brain call")
    global _CALLS_MADE
    transport, cfg = wiring.get_transport_config(w)
    if response_format is not None:
        cfg = {**cfg, "response_format": response_format}
    if request_config:
        cfg = {**cfg, **request_config}
    max_calls = w["model"].get("brain_call_budget") or w["model"]["global"]["brain_call_budget"]
    if max_calls is not None and _CALLS_MADE >= int(max_calls):
        raise RuntimeError(f"brain call budget exceeded: {_CALLS_MADE}/{max_calls}")
    _CALLS_MADE += 1
    seq, started = _next_event_seq(), time.time()
    log_runtime_event(w, "brain_request", seq=seq, transport=transport, rod_feedback=rod_feedback, prompt_cache_key=cfg.get("prompt_cache_key"), stable_prefix=cfg.get("stable_prefix"), response_format=cfg.get("response_format"), messages=summarize_messages_for_log(messages))
    try:
        result = _load_transport_module(transport, w).call(messages, cfg)
    except Exception as exc:
        log_runtime_event(w, "brain_error", seq=seq, transport=transport, elapsed_s=round(time.time() - started, 3), error=f"{type(exc).__name__}: {exc}")
        raise RuntimeError(f"{transport} brain failed hard: {exc}") from exc
    if not isinstance(result, dict):
        raise RuntimeError(f"{transport} brain contract violation: expected dict, got {type(result).__name__}")
    content, reasoning = result.get("content"), result.get("reasoning", "")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(f"{transport} brain contract violation: missing non-empty content")
    if reasoning is not None and not isinstance(reasoning, str):
        raise RuntimeError(f"{transport} brain contract violation: reasoning must be string when present")
    out = {"content": content, "reasoning": reasoning or ""}
    log_runtime_event(w, "brain_response", seq=seq, transport=transport, elapsed_s=round(time.time() - started, 3), content=content, reasoning=reasoning or "", raw={k: v for k, v in result.items() if k not in {"content", "reasoning"}})
    return out


def reasoning_from(content: str, reasoning: str = "") -> str:
    if reasoning and reasoning.strip():
        return reasoning.strip()
    match = re.search(r"think(.*?)answer", content or "", flags=re.S | re.I)
    return match.group(1).strip() if match else (content or "").strip()


def extract_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    s = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", s, flags=re.S | re.I)
    if fenced:
        s = fenced.group(1).strip()
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    in_str = esc = False
    depth, start = 0, -1
    candidates: list[str] = []
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
            depth += 1
        elif ch == "}" and depth:
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


def think(system_prompt: str, payload: dict[str, Any], w: dict[str, Any], *, expected_record_type: str | None = None, request_config: dict[str, Any] | None = None) -> dict[str, Any]:
    _, cfg = wiring.get_transport_config(w)
    reasoning_cfg = dict(cfg["reasoning"])
    prefix = stable_prefix() if w["model"]["stable_prefix"]["enabled"] else None
    prefix_for_messages = prefix if w["model"]["stable_prefix"]["include_in_request"] else None
    conv_id = w.get("_conv_id")
    if not conv_id:
        conv_id = f"endgame-ai-{int(time.time())}-{hashlib.md5(str(w).encode()).hexdigest()[:8]}"
        w["_conv_id"] = conv_id
    payload = _with_fresh_observation(payload, w)
    goal = str(payload.pop("goal") or "") if "goal" in payload else ""
    user_text = json.dumps(payload, ensure_ascii=False, default=str)
    response_format = _record_response_format(expected_record_type) if expected_record_type and _structured_outputs_enabled(cfg) else None
    request_cfg = dict(request_config or {})
    request_cfg["expected_record_type"] = expected_record_type
    if prefix is not None:
        request_cfg["stable_prefix"] = prefix.metadata()
    for key, value in _organ_tuning(w, expected_record_type).items():
        if key in {"reasoning_effort", "max_output_tokens"} and value is not None:
            request_cfg.setdefault(key, value)
    if cfg.get("transport") == "transport_xai":
        request_cfg.setdefault("prompt_cache_key", prefix.cache_key if prefix is not None else conv_id)
    stable_context = f"CURRENT GOAL (fixed for this run):\n{goal}" if goal else ""
    pattern = str(reasoning_cfg.get("pattern") or "single_pass")
    if not reasoning_cfg["enabled"] or pattern in {"single_pass", "native"}:
        result = call(_messages(system_prompt, user_text, prefix_for_messages, stable_context), w, response_format=response_format, request_config=request_cfg)
        record = _commit_record(result["content"], expected_record_type)
        return bus.Record(record.record_type, record.data, reasoning_from(result["content"], result.get("reasoning", ""))).to_json()
    if pattern != "two_pass":
        raise RuntimeError(f"unknown reasoning pattern: {pattern}")
    first = call(_messages(system_prompt, user_text, prefix_for_messages, stable_context), w, rod_feedback=False, request_config=request_cfg)
    reasoning = reasoning_from(first["content"], first.get("reasoning", ""))
    template = str(reasoning_cfg.get("injection_template") or "REASONING:\n{reasoning}")
    second = call(_messages(system_prompt, user_text + "\n\n" + template.format(reasoning=reasoning), prefix_for_messages, stable_context), w, rod_feedback=True, response_format=response_format, request_config=request_cfg)
    record = _commit_record(second["content"], expected_record_type)
    return bus.Record(record.record_type, record.data, reasoning).to_json()
