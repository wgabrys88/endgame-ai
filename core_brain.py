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
_CALLS_MADE = 0
_STABLE_PREFIX_CACHE: "StablePrefix | None" = None
_STABLE_PREFIX_LOCK = threading.Lock()
_LAST_OBSERVATION: dict[str, Any] | None = None

class StablePrefix:
    def __init__(self, w: dict[str, Any], root: pathlib.Path = ROOT, focus_files: list[str] | None = None):
        self.root = root
        self.source = w["model"]["stable_prefix"]["source"]
        self.focus_files = focus_files  # selective evolution: only these + core wiring if set (for targeted node fixes)
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
        skip_prefixes = tuple(self.source["skip_prefixes"])
        if set(path.parts) & set(self.source["skip_parts"]) or path.name.startswith(skip_prefixes):
            return False
        if self.focus_files is not None:
            # Focused self-evolution: include only relevant node/tools/wiring + always core for context
            core_always = {".gitattributes", ".gitignore", "wiring.json", "core_bus.py", "core_wiring.py", "core_loader.py", "check_topology.py"}
            focus_set = set(self.focus_files) | core_always
            return path.name in focus_set or path.suffix in {".py", ".json"} and any(f in str(path) for f in self.focus_files)
        return path.name in set(self.source["names"]) or path.suffix in set(self.source["suffixes"])

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


def stable_prefix(w: dict[str, Any], focus_files: list[str] | None = None) -> StablePrefix:
    global _STABLE_PREFIX_CACHE
    with _STABLE_PREFIX_LOCK:
        fresh = StablePrefix(w, ROOT, focus_files=focus_files)
        # Note: cache ignores focus for simplicity; in practice for evolution we bypass or key on focus
        if focus_files is not None or _STABLE_PREFIX_CACHE is None or _STABLE_PREFIX_CACHE.fingerprint != fresh.fingerprint:
            _STABLE_PREFIX_CACHE = fresh
        return _STABLE_PREFIX_CACHE


def _messages(system_prompt: str, user_text: str, prefix: StablePrefix | None, stable_context: str = "") -> list[dict[str, str]]:
    system = system_prompt + ("\n\n" + stable_context if stable_context else "")
    if prefix is not None:
        system = prefix.text + "\n\n" + system
    return [{"role": "system", "content": system}, {"role": "user", "content": user_text}]


def get_record_contract(w: dict[str, Any], record_type: str) -> dict[str, Any]:
    contract = w["record_contracts"][record_type]
    if not isinstance(contract, dict):
        raise RuntimeError(f"wiring.record_contracts.{record_type} must be object")
    return contract


def _validate_record_contract(w: dict[str, Any], record: bus.Record, expected_record_type: str | None = None) -> None:
    if expected_record_type and record.record_type != expected_record_type:
        raise RuntimeError(f"brain record_type mismatch: expected {expected_record_type!r}, got {record.record_type!r}")
    contract = get_record_contract(w, record.record_type)
    required = list(contract["required"])
    enums = dict(contract["enums"])
    types = dict(contract.get("types", {}))
    non_empty = set(contract.get("non_empty", []))
    missing = [key for key in required if key not in record.data]
    if missing:
        raise RuntimeError(f"{record.record_type} record missing required data keys: {missing}")
    if not contract.get("additional_properties", True):
        allowed = set(required) | set(enums) | set(types) | {"next_signal"}
        unexpected = sorted(set(record.data) - allowed)
        if unexpected:
            raise RuntimeError(f"{record.record_type} record has unexpected data keys: {unexpected}")
    json_types = {"string": str, "boolean": bool, "array": list, "object": dict, "number": (int, float), "integer": int}
    for key, type_name in types.items():
        if key in record.data and (not isinstance(record.data[key], json_types[type_name]) or type_name in {"number", "integer"} and isinstance(record.data[key], bool)):
            raise RuntimeError(f"{record.record_type}.data.{key} must be {type_name}")
    for key in non_empty:
        if key in record.data and not record.data[key]:
            raise RuntimeError(f"{record.record_type}.data.{key} must be non-empty")
        if key in record.data and isinstance(record.data[key], str) and not record.data[key].strip():
            raise RuntimeError(f"{record.record_type}.data.{key} must be non-blank")
    for key, values in enums.items():
        if key in record.data and record.data[key] not in set(values):
            raise RuntimeError(f"{record.record_type}.data.{key}={record.data[key]!r} outside {values!r}")


def _commit_record(content: str, w: dict[str, Any], expected_record_type: str | None = None) -> bus.Record:
    record = extract_json_object(content)
    if record is None:
        raise RuntimeError(f"brain did not commit a valid JSON object: {content}")
    if not isinstance(record.get("record_type"), str) or "data" not in record or not isinstance(record["data"], dict):
        raise RuntimeError(f"brain record must contain string record_type and object data: {record}")
    committed = bus.Record.from_json(record)
    _validate_record_contract(w, committed, expected_record_type)
    return committed



def _node_docstring(w: dict[str, Any], node: str) -> str:
    """Read a node's own input-contract declaration: the module docstring of its .py file.
    The docstring IS the node's input pin spec — what it expects to receive. For a declarative
    node (no .py), fall back to its node_defs expected_record_type as its spec."""
    import ast
    base = node.split(":", 1)[0]
    node_dir = wiring.root_path(w["paths"]["nodes"])
    path = node_dir / f"{base}.py"
    if path.is_file():
        try:
            doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8")))
            if doc:
                return doc.strip()
        except SyntaxError:
            pass
    defn = w.get("node_defs", {}).get(node) or w.get("node_defs", {}).get(base)
    if isinstance(defn, dict):
        return f"declarative node; expects a payload for record_type '{defn.get('expected_record_type', '')}'."
    return ""


def downstream_contract(w: dict[str, Any], emitting_node: str | None) -> str:
    """The producer reads, live, the input contracts (docstrings) of every node its output
    edges are wired to, and copies them in. This is the whole contract mechanism: no stored
    record_contracts, no pins registry — X learns what to produce by reading Y and Z's own
    files, resolved through the JSON wiring. Rewire the edges and this changes automatically."""
    if not emitting_node:
        return ""
    edges = w.get("topology", {}).get("edges", {}).get(emitting_node, {})
    seen: list[tuple[str, str]] = []
    for signal, value in edges.items():
        if signal == "error":
            continue
        targets = [value] if isinstance(value, str) else (value if isinstance(value, list) else [])
        for t in targets:
            if isinstance(t, str) and t not in ("halt", "wait"):
                seen.append((signal, t))
    if not seen:
        return ""
    lines = ["DOWNSTREAM CONTRACT — your output is wired (via topology) to these consumers; produce what they expect:"]
    for signal, succ in seen:
        doc = _node_docstring(w, succ)
        lines.append(f"\n[on signal '{signal}' -> {succ}]\n{doc}" if doc else f"\n[on signal '{signal}' -> {succ}] (no declared input contract)")
    lines.append("\nChoose next_signal to route your output to the intended consumer.")
    return "\n".join(lines)


def _record_contract_prompt(w: dict[str, Any], record_type: str | None, emitting_node: str | None = None) -> str:
    if not record_type:
        return ""
    contract = get_record_contract(w, record_type)
    # next_signal is emergent from wiring: the node's outgoing edges define what it may emit.
    enums = dict(contract["enums"])
    emergent = bus.emergent_signals(w, emitting_node)
    if emergent:
        enums = {**enums, "next_signal": emergent}
    return "\n".join([
        "RECORD CONTRACT (data shape from wiring.record_contracts; next_signal from topology edges):",
        f"record_type: {record_type}",
        "required data keys: " + json.dumps(contract["required"], ensure_ascii=False),
        "enum data values: " + json.dumps(enums, ensure_ascii=False),
        "data types: " + json.dumps(contract.get("types", {}), ensure_ascii=False),
        "non-empty data keys: " + json.dumps(contract.get("non_empty", []), ensure_ascii=False),
        "additional data keys allowed: " + json.dumps(contract.get("additional_properties", True)),
    ])


def _organ_tuning(w: dict[str, Any], record_type: str | None) -> dict[str, Any]:
    organ = w["model"]["organs"].get(record_type) if record_type else None
    return dict(organ) if isinstance(organ, dict) else {}


def _normalize_observation(obj: Any) -> dict[str, Any] | None:
    if not isinstance(obj, dict) or not obj.get("desktop_tree_text"):
        return None
    fields = ("desktop_tree_text", "focused_elements", "observed_at", "screen", "scan_stats", "rendered_node_count", "max_llm_nodes", "llm_node_limit_hit")
    return {key: obj[key] for key in fields if key in obj}


def _observation_payload(w: dict[str, Any], payload: dict[str, Any] | None = None) -> dict[str, Any]:
    global _LAST_OBSERVATION
    if payload:
        candidates = [payload.get("observation")]
        evidence = payload.get("evidence")
        if isinstance(evidence, dict):
            candidates.append(evidence.get("observation"))
        for candidate in candidates:
            normalized = _normalize_observation(candidate)
            if normalized is not None:
                _LAST_OBSERVATION = normalized
                return normalized
    raise RuntimeError("observation missing: observe node must run before any brain call")


def last_observation() -> dict[str, Any]:
    return dict(_LAST_OBSERVATION or {})


def _with_observation(payload: dict[str, Any], w: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(payload)
    enriched["observation"] = _observation_payload(w, enriched)
    return enriched


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def summarize_messages_for_log(messages: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for message in messages:
        role = str(message.get("role") or "user")
        content = str(message.get("content") or "")
        row: dict[str, Any] = {"role": role, "chars": len(content), "sha256": _sha256_text(content), "content": content}
        out.append(row)
    return out


def reset_call_budget() -> None:
    global _CALLS_MADE
    _CALLS_MADE = 0


def _load_transport_module(name: str, w: dict[str, Any]):
    return loader.load("transport", name, w)


def _structured_outputs_enabled(cfg: dict[str, Any]) -> bool:
    structured = cfg.get("structured_outputs")
    return bool(structured.get("enabled", False)) if isinstance(structured, dict) else bool(structured)


def _record_response_format(w: dict[str, Any], record_type: str, emitting_node: str | None = None) -> dict[str, Any]:
    contract = get_record_contract(w, record_type)
    data_properties = {key: {} for key in contract["required"]}
    for key, type_name in contract.get("types", {}).items():
        data_properties.setdefault(key, {})["type"] = type_name
    for key in contract.get("non_empty", []):
        type_name = contract.get("types", {}).get(key)
        limit_name = {"string": "minLength", "array": "minItems", "object": "minProperties"}.get(type_name)
        if limit_name:
            data_properties.setdefault(key, {})[limit_name] = 1
    # next_signal enum is emergent from the node's topology edges, not the stored contract.
    enums = dict(contract["enums"])
    emergent = bus.emergent_signals(w, emitting_node)
    if emergent:
        enums = {**enums, "next_signal": emergent}
    for key, values in enums.items():
        data_properties.setdefault(key, {})["enum"] = list(values)
    return {
        "type": "json_schema",
        "name": f"{record_type}_record",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "record_type": {"enum": [record_type]},
                "data": {
                    "type": "object",
                    "additionalProperties": contract.get("additional_properties", True),
                    "properties": data_properties,
                    "required": list(contract["required"]),
                },
                "reasoning": {"type": "string"},
            },
            "required": ["record_type", "data", "reasoning"],
        },
    }


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
    try:
        result = _load_transport_module(transport, w).call(messages, cfg)
    except Exception as exc:
        raise RuntimeError(f"{transport} brain failed hard: {exc}") from exc
    if not isinstance(result, dict):
        raise RuntimeError(f"{transport} brain contract violation: expected dict, got {type(result).__name__}")
    content, reasoning = result.get("content"), result.get("reasoning", "")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(f"{transport} brain contract violation: missing non-empty content")
    if reasoning is not None and not isinstance(reasoning, str):
        raise RuntimeError(f"{transport} brain contract violation: reasoning must be string when present")
    out = {"content": content, "reasoning": reasoning or ""}
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


def think(system_prompt: str, payload: dict[str, Any], w: dict[str, Any], *, expected_record_type: str | None = None, emitting_node: str | None = None, request_config: dict[str, Any] | None = None) -> dict[str, Any]:
    _, cfg = wiring.get_transport_config(w)
    reasoning_cfg = dict(cfg["reasoning"])
    organ_tuning = _organ_tuning(w, expected_record_type)
    include_prefix = bool(w["model"]["stable_prefix"]["include_in_request"] or organ_tuning.get("include_stable_prefix"))
    focus_files = None
    if expected_record_type == "git_evolution_patch":
        # Enable focused self-evolution: extract candidate files from last_reflection diagnosis or failure to target only relevant node + wiring
        st = payload.get("state", {}) if isinstance(payload, dict) else {}
        last_refl = st.get("last_reflection", {}) or {}
        diagnosis = str(last_refl.get("diagnosis", "")) + str(last_refl.get("lesson", ""))
        import re
        candidates = re.findall(r"(node_[a-z_]+\.py|tools\.py|core_[a-z_]+\.py|wiring\.json)", diagnosis)
        if candidates:
            focus_files = sorted(set(candidates))
    prefix = stable_prefix(w, focus_files=focus_files) if w["model"]["stable_prefix"]["enabled"] and include_prefix else None
    prefix_for_messages = prefix
    conv_id = w.get("_conv_id")
    if not conv_id:
        conv_id = f"endgame-ai-{int(time.time())}-{hashlib.md5(str(w).encode()).hexdigest()[:8]}"
        w["_conv_id"] = conv_id
    payload = _with_observation(payload, w)
    goal = str(payload.pop("goal") or "") if "goal" in payload else ""
    user_text = json.dumps(payload, ensure_ascii=False, default=str)
    response_format = _record_response_format(w, expected_record_type, emitting_node) if expected_record_type and _structured_outputs_enabled(cfg) else None
    request_cfg = dict(request_config or {})
    request_cfg["expected_record_type"] = expected_record_type
    if prefix is not None:
        request_cfg["stable_prefix"] = prefix.metadata()
    for key, value in organ_tuning.items():
        if key in {"reasoning_effort", "max_output_tokens"} and value is not None:
            request_cfg.setdefault(key, value)
    if cfg.get("transport") == "transport_xai":
        request_cfg.setdefault("prompt_cache_key", prefix.cache_key if prefix is not None else conv_id)
    stable_context_parts = []
    if goal:
        stable_context_parts.append(f"CURRENT GOAL (fixed for this run):\n{goal}")
    contract_context = _record_contract_prompt(w, expected_record_type, emitting_node)
    if contract_context:
        stable_context_parts.append(contract_context)
    downstream = downstream_contract(w, emitting_node)
    if downstream:
        stable_context_parts.append(downstream)
    stable_context = "\n\n".join(stable_context_parts)
    pattern = str(reasoning_cfg.get("pattern") or "single_pass")
    if not reasoning_cfg["enabled"] or pattern in {"single_pass", "native"}:
        result = call(_messages(system_prompt, user_text, prefix_for_messages, stable_context), w, response_format=response_format, request_config=request_cfg)
        record = _commit_record(result["content"], w, expected_record_type)
        transport_reasoning = str(result.get("reasoning") or "").strip()
        return bus.Record(record.record_type, record.data, transport_reasoning or record.reasoning).to_json()
    if pattern != "two_pass":
        raise RuntimeError(f"unknown reasoning pattern: {pattern}")
    first = call(_messages(system_prompt, user_text, prefix_for_messages, stable_context), w, rod_feedback=False, request_config=request_cfg)
    reasoning = reasoning_from(first["content"], first.get("reasoning", ""))
    template = str(reasoning_cfg.get("injection_template") or "REASONING:\n{reasoning}")
    second = call(_messages(system_prompt, user_text + "\n\n" + template.format(reasoning=reasoning), prefix_for_messages, stable_context), w, rod_feedback=True, response_format=response_format, request_config=request_cfg)
    record = _commit_record(second["content"], w, expected_record_type)
    return bus.Record(record.record_type, record.data, reasoning).to_json()
