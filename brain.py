"""Brain chokepoint for endgame-ai.

Brain transports are hot-swappable modules selected only by wiring.json model.transport.
Every transport lives under seed_brains/ and is copied to live_brains/ before use.
No selected transport has a fallback path.
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import re
import shutil
import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Protocol

ROOT = pathlib.Path(__file__).parent.resolve()
_RAW_LOG_PATH: pathlib.Path | None = None
_RAW_SEQ = 0
_RAW_LOCK = threading.Lock()
_CALLS_MADE = 0


class Transport(Protocol):
    """Protocol for brain transports. Each transport must implement call()."""
    
    def call(self, messages: list[dict[str, str]], cfg: dict[str, Any]) -> dict[str, str]:
        """Call the transport with messages and config. Returns {'content': str, 'reasoning': str}."""
        ...


class BaseTransport(ABC):
    """Base class for brain transports with common functionality."""
    
    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        self.timeout = float(cfg.get("timeout", 120))
    
    @abstractmethod
    def _call_impl(self, messages: list[dict[str, str]]) -> dict[str, str]:
        """Implementation-specific call logic."""
        ...
    
    def call(self, messages: list[dict[str, str]], cfg: dict[str, Any]) -> dict[str, str]:
        """Wrapper with common error handling and validation."""
        result = self._call_impl(messages)
        if not isinstance(result, dict):
            raise RuntimeError(f"transport contract violation: expected dict, got {type(result).__name__}")
        content = result.get("content")
        reasoning = result.get("reasoning", "")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("transport contract violation: missing non-empty content")
        if reasoning is not None and not isinstance(reasoning, str):
            raise RuntimeError("transport contract violation: reasoning must be string when present")
        return {"content": content, "reasoning": reasoning or ""}


class ReasoningStrategy(Protocol):
    """Protocol for reasoning strategies. Each strategy executes the ROD pattern."""
    
    def execute(self, system_prompt: str, payload: dict[str, Any], wiring: dict[str, Any], transport: str, cfg: dict[str, Any]) -> dict[str, Any]:
        """Execute the reasoning pattern and return the committed JSON record."""
        ...


class TwoPassStrategy:
    """Two-pass ROD: Call 1 gets reasoning, Call 2 injects reasoning and extracts JSON."""
    
    def execute(self, system_prompt: str, payload: dict[str, Any], wiring: dict[str, Any], transport: str, cfg: dict[str, Any]) -> dict[str, Any]:
        user_text = json.dumps(payload, ensure_ascii=False, default=str)
        first = call([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ], wiring, rod_feedback=False)
        reasoning = reasoning_from(first["content"], first.get("reasoning", ""))
        
        # Get injection template from config
        injection_template = cfg.get("reasoning", {}).get("injection_template", "ROD_REASONING_CONTENT:\n{reasoning}")
        second_user = user_text + "\n\n" + injection_template.format(reasoning=reasoning)
        
        second = call([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": second_user},
        ], wiring, rod_feedback=True)
        
        record = extract_json_object(second["content"])
        if record is None:
            raise RuntimeError(f"brain did not commit a valid JSON object: {second['content'][:800]}")
        if not isinstance(record.get("record_type"), str):
            raise RuntimeError(f"brain record missing string record_type: {record}")
        if "data" not in record or not isinstance(record["data"], dict):
            raise RuntimeError(f"brain record missing object data: {record}")
        record.setdefault("reasoning", reasoning)
        return record


class SinglePassStrategy:
    """Single-pass: One call with system + user, extract JSON directly."""
    
    def execute(self, system_prompt: str, payload: dict[str, Any], wiring: dict[str, Any], transport: str, cfg: dict[str, Any]) -> dict[str, Any]:
        user_text = json.dumps(payload, ensure_ascii=False, default=str)
        result = call([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ], wiring, rod_feedback=False)
        
        record = extract_json_object(result["content"])
        if record is None:
            raise RuntimeError(f"brain did not commit a valid JSON object: {result['content'][:800]}")
        if not isinstance(record.get("record_type"), str):
            raise RuntimeError(f"brain record missing string record_type: {record}")
        if "data" not in record or not isinstance(record["data"], dict):
            raise RuntimeError(f"brain record missing object data: {record}")
        # No separate reasoning in single-pass
        record.setdefault("reasoning", reasoning_from(result["content"], result.get("reasoning", "")))
        return record


class NativeReasoningStrategy:
    """Native reasoning: Model returns reasoning in a dedicated field (e.g., OpenAI reasoning_content)."""
    
    def execute(self, system_prompt: str, payload: dict[str, Any], wiring: dict[str, Any], transport: str, cfg: dict[str, Any]) -> dict[str, Any]:
        user_text = json.dumps(payload, ensure_ascii=False, default=str)
        result = call([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ], wiring, rod_feedback=False)
        
        # Extract reasoning from transport's native field
        reasoning = result.get("reasoning", "")
        if not reasoning:
            reasoning = reasoning_from(result["content"], "")
        
        record = extract_json_object(result["content"])
        if record is None:
            raise RuntimeError(f"brain did not commit a valid JSON object: {result['content'][:800]}")
        if not isinstance(record.get("record_type"), str):
            raise RuntimeError(f"brain record missing string record_type: {record}")
        if "data" not in record or not isinstance(record["data"], dict):
            raise RuntimeError(f"brain record missing object data: {record}")
        record.setdefault("reasoning", reasoning)
        return record


class CustomStrategy:
    """Custom reasoning: Configurable injection template and extractor."""
    
    def execute(self, system_prompt: str, payload: dict[str, Any], wiring: dict[str, Any], transport: str, cfg: dict[str, Any]) -> dict[str, Any]:
        reasoning_config = cfg.get("reasoning", {})
        pattern = reasoning_config.get("pattern", "two_pass")
        injection_template = reasoning_config.get("injection_template", "ROD_REASONING_CONTENT:\n{reasoning}")
        extractor = reasoning_config.get("extractor", "think_tags")
        
        user_text = json.dumps(payload, ensure_ascii=False, default=str)
        
        if pattern == "single_pass":
            result = call([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ], wiring, rod_feedback=False)
            reasoning = self._extract_reasoning(result["content"], result.get("reasoning", ""), extractor)
            
        elif pattern == "two_pass":
            first = call([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ], wiring, rod_feedback=False)
            reasoning = self._extract_reasoning(first["content"], first.get("reasoning", ""), extractor)
            
            second_user = user_text + "\n\n" + injection_template.format(reasoning=reasoning)
            result = call([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": second_user},
            ], wiring, rod_feedback=True)
            
        elif pattern == "native":
            result = call([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ], wiring, rod_feedback=False)
            reasoning = result.get("reasoning", "")
            if not reasoning:
                reasoning = self._extract_reasoning(result["content"], "", extractor)
        else:
            raise RuntimeError(f"unknown reasoning pattern: {pattern}")
        
        record = extract_json_object(result["content"])
        if record is None:
            raise RuntimeError(f"brain did not commit a valid JSON object: {result['content'][:800]}")
        if not isinstance(record.get("record_type"), str):
            raise RuntimeError(f"brain record missing string record_type: {record}")
        if "data" not in record or not isinstance(record["data"], dict):
            raise RuntimeError(f"brain record missing object data: {record}")
        record.setdefault("reasoning", reasoning)
        return record
    
    def _extract_reasoning(self, content: str, reasoning: str, extractor: str) -> str:
        if reasoning and reasoning.strip():
            return reasoning.strip()
        if extractor == "think_tags":
            m = re.search(r"�\u0085(.*?)�\u0085", content or "", flags=re.S)
            if m:
                return m.group(1).strip()
        elif extractor == "reasoning_field":
            # Already handled by transport returning reasoning field
            pass
        return (content or "").strip()


def _get_reasoning_strategy(cfg: dict[str, Any]) -> ReasoningStrategy:
    """Factory to get the reasoning strategy based on transport config."""
    reasoning_cfg = cfg.get("reasoning", {})
    if not reasoning_cfg.get("enabled", True):
        return SinglePassStrategy()  # Disabled = single pass
    
    pattern = reasoning_cfg.get("pattern", "two_pass")
    if pattern == "two_pass":
        return TwoPassStrategy()
    elif pattern == "single_pass":
        return SinglePassStrategy()
    elif pattern == "native":
        return NativeReasoningStrategy()
    elif pattern == "custom":
        return CustomStrategy()
    else:
        # Default to two_pass for backward compatibility
        return TwoPassStrategy()


def root_path(value: str | None, default: str = "") -> pathlib.Path:
    raw = os.path.expandvars(os.path.expanduser(str(value or default)))
    p = pathlib.Path(raw)
    return p if p.is_absolute() else ROOT / p


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


def raw_log_path(cfg: dict[str, Any] | None = None) -> pathlib.Path:
    global _RAW_LOG_PATH
    cfg = cfg or {}
    if _RAW_LOG_PATH is None:
        explicit = cfg.get("raw_log_path")
        if explicit:
            _RAW_LOG_PATH = root_path(str(explicit))
        else:
            _RAW_LOG_PATH = ROOT / f"{time.strftime('%Y%m%dT%H%M%S')}.txt"
        _RAW_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _RAW_LOG_PATH.touch(exist_ok=True)
    return _RAW_LOG_PATH


def _next_raw_seq() -> int:
    global _RAW_SEQ
    with _RAW_LOCK:
        _RAW_SEQ += 1
        return _RAW_SEQ


def log_raw_entry(cfg: dict[str, Any] | None, entry: dict[str, Any]) -> None:
    cfg = cfg or {}
    if cfg.get("raw_log", True) is False or cfg.get("log_raw", True) is False:
        return
    row = dict(entry)
    row.setdefault("ts", time.time())
    row.setdefault("iso", time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()))
    append_ndjson(raw_log_path(cfg), row)


def reset_call_budget() -> None:
    global _CALLS_MADE
    _CALLS_MADE = 0


def ensure_live_brains(wiring: dict[str, Any]) -> None:
    paths = wiring.get("paths", {})
    seed_dir = root_path(paths.get("seed_brains"), "seed_brains")
    live_dir = root_path(paths.get("live_brains"), "live_brains")
    if not seed_dir.exists():
        raise RuntimeError(f"missing seed_brains directory: {seed_dir}")
    live_dir.mkdir(parents=True, exist_ok=True)
    for src in seed_dir.glob("*.py"):
        dst = live_dir / src.name
        if not dst.exists() or src.read_bytes() != dst.read_bytes():
            shutil.copy2(src, dst)


def _load_transport_module(name: str, wiring: dict[str, Any]):
    paths = wiring.get("paths", {})
    live_dir = root_path(paths.get("live_brains"), "live_brains")
    module_path = live_dir / f"{name}.py"
    if not module_path.exists():
        raise RuntimeError(
            f"selected brain transport '{name}' has no live module at {module_path}; "
            "brain selection is fail-hard and no fallback was attempted"
        )
    spec = importlib.util.spec_from_file_location(f"endgame_live_brain_{name}", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load selected brain transport module: {module_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    if not hasattr(mod, "call"):
        raise RuntimeError(f"brain transport '{name}' does not export call(messages, cfg)")
    return mod


def _get_transport_config(wiring: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Extract transport name and merged config from wiring.json.
    
    New schema: model.transport_config.{transport} for per-transport config
    Legacy schema: model.{transport} for backward compatibility
    """
    model = wiring.get("model")
    if not isinstance(model, dict):
        raise RuntimeError("wiring.json missing object model")
    
    transport = str(model.get("transport") or "").strip()
    if not transport:
        raise RuntimeError("wiring model.transport is empty; no fallback transport is allowed")
    
    # New normalized schema: transport_config.{transport}
    transport_config = model.get("transport_config", {})
    if isinstance(transport_config, dict) and transport in transport_config:
        cfg = dict(transport_config[transport])
    else:
        # Legacy fallback: model.{transport}
        cfg = dict(model.get(transport) or {})
    
    # Merge global config (timeout, max_brain_calls, raw_log, etc.)
    global_keys = {"timeout", "max_brain_calls", "raw_log", "raw_log_path", "log_raw"}
    for k in global_keys:
        if k in model and k not in cfg:
            cfg[k] = model[k]
    
    cfg["transport"] = transport
    return transport, cfg


def call(messages: list[dict[str, str]], wiring: dict[str, Any], *, rod_feedback: bool = False) -> dict[str, str]:
    """Call the selected transport exactly once or raise.
    
    The function logs request, response, and error rows. It never switches transport.
    """
    global _CALLS_MADE
    ensure_live_brains(wiring)
    transport, cfg = _get_transport_config(wiring)
    max_calls = wiring.get("model", {}).get("max_brain_calls")
    if max_calls is not None and _CALLS_MADE >= int(max_calls):
        raise RuntimeError(f"brain call budget exceeded: {_CALLS_MADE}/{max_calls}")
    _CALLS_MADE += 1
    seq = _next_raw_seq()
    started = time.time()
    log_raw_entry(cfg, {
        "seq": seq,
        "phase": "request",
        "transport": transport,
        "rod_feedback": rod_feedback,
        "messages": messages,
    })
    mod = _load_transport_module(transport, wiring)
    try:
        result = mod.call(messages, cfg)
    except Exception as exc:
        log_raw_entry(cfg, {
            "seq": seq,
            "phase": "error",
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
    log_raw_entry(cfg, {
        "seq": seq,
        "phase": "response",
        "transport": transport,
        "elapsed_s": round(time.time() - started, 3),
        "content": content,
        "reasoning": reasoning or "",
        "raw": {k: v for k, v in result.items() if k not in {"content", "reasoning"}},
    })
    return out


def reasoning_from(content: str, reasoning: str = "") -> str:
    if reasoning and reasoning.strip():
        return reasoning.strip()
    m = re.search(r"�\u0085(.*?)�\u0085", content or "", flags=re.S)
    if m:
        return m.group(1).strip()
    return (content or "").strip()


def extract_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    s = text.strip()
    if "�\u0085" in s:
        s = s.rsplit("�\u0085", 1)[1].strip()
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


def think(system_prompt: str, payload: dict[str, Any], wiring: dict[str, Any]) -> dict[str, Any]:
    """Pluggable ROD brain pattern returning the committed JSON record."""
    _, cfg = _get_transport_config(wiring)
    
    # Check global reasoning toggle
    global_reasoning = wiring.get("model", {}).get("global", {}).get("reasoning_enabled", True)
    if not global_reasoning:
        # Fallback to single pass without reasoning
        return SinglePassStrategy().execute(system_prompt, payload, wiring, cfg["transport"], cfg)
    
    strategy = _get_reasoning_strategy(cfg)
    return strategy.execute(system_prompt, payload, wiring, cfg["transport"], cfg)


def read_raw_log_tail(path: pathlib.Path | None = None, *, max_lines: int = 200, max_bytes: int = 600_000) -> list[dict[str, Any]]:
    p = path or raw_log_path({"raw_log": True})
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