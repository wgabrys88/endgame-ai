from __future__ import annotations
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import threading
import time
from typing import Any
import stop_check
ROOT = pathlib.Path(__file__).parent.resolve()
_RAW_LOG_PATH: pathlib.Path | None = None
_RAW_SEQ = 0
_RAW_LOCK = threading.Lock()
_CALLS_MADE = 0
_STABLE_PREFIX_CACHE: 'StablePrefix | None' = None
_STABLE_PREFIX_LOCK = threading.Lock()
_LAST_FRESH_OBSERVATION: dict[str, Any] | None = None
_OPEN_OBJECT_SCHEMA = {'type': 'object', 'additionalProperties': True}
STATIC_PREFIX_SUFFIXES = {'.py', '.json', '.md'}
STATIC_PREFIX_NAMES = {'.gitattributes', '.gitignore', 'LICENSE'}
STATIC_PREFIX_SKIP_PARTS = {'.git', '__pycache__', '.pytest_cache', 'comms', 'pids'}
STATIC_PREFIX_SKIP_PREFIXES = {'reports/'}
_RECORD_DATA_SCHEMAS: dict[str, dict[str, Any]] = {'plan': {'type': 'object', 'additionalProperties': True, 'properties': {'next_signal': {'enum': ['step_ready', 'reflect']}, 'intent': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': True, 'properties': {'description': {'type': 'string'}, 'done_when': {'type': 'string'}}}}}, 'required': ['next_signal', 'intent']}, 'schedule': {'type': 'object', 'additionalProperties': True, 'properties': {'next_signal': {'enum': ['step_ready', 'plan_complete']}, 'step': {'anyOf': [{'type': 'object', 'additionalProperties': True}, {'type': 'null'}]}}, 'required': ['next_signal', 'step']}, 'execution': {'type': 'object', 'additionalProperties': True, 'properties': {'conclusion': {'enum': ['EXECUTE', 'CANNOT']}, 'code': {'type': 'string'}}, 'required': ['conclusion', 'code']}, 'verification': {'type': 'object', 'additionalProperties': True, 'properties': {'next_signal': {'enum': ['step_confirmed', 'step_denied']}, 'success': {'type': 'boolean'}, 'reasoning': {'type': 'string'}}, 'required': ['next_signal', 'success', 'reasoning']}, 'reflection': {'type': 'object', 'additionalProperties': True, 'properties': {'next_signal': {'enum': ['retry', 'replan', 'escalate', 'give_up']}, 'lesson': {'type': 'string'}, 'diagnosis': {'type': 'string'}}, 'required': ['next_signal', 'lesson', 'diagnosis']}, 'git_evolution_patch': {'type': 'object', 'additionalProperties': True, 'properties': {'summary': {'type': 'string'}, 'rationale': {'type': 'string'}, 'read_files': {'type': 'array', 'items': {'type': 'string'}}, 'file_writes': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': True, 'properties': {'path': {'type': 'string'}, 'content': {'type': 'string'}}, 'required': ['path', 'content']}}, 'unified_diffs': {'type': 'array', 'items': {'anyOf': [{'type': 'string'}, {'type': 'object', 'additionalProperties': True, 'properties': {'diff': {'type': 'string'}}, 'required': ['diff']}]}}, 'file_deletes': {'type': 'array', 'items': {'type': 'string'}}, 'wiring_patches': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': True, 'properties': {'op': {'enum': ['set', 'delete']}, 'path': {'type': 'string'}}, 'required': ['op', 'path']}}, 'commands': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': True}}, 'expected_validation': {'anyOf': [{'type': 'string'}, {'type': 'object', 'additionalProperties': True}, {'type': 'null'}]}}, 'required': ['summary', 'rationale', 'read_files', 'file_writes', 'file_deletes', 'wiring_patches', 'commands', 'expected_validation']}, 'satisfied': {'type': 'object', 'additionalProperties': True, 'properties': {'next_signal': {'const': 'halt'}}, 'required': ['next_signal']}}

class StablePrefix:

    def __init__(self, root: pathlib.Path=ROOT):
        self.root = root
        self.files = self._source_files()
        self.text, self.fingerprint = self._render()
        self.cache_key = f'endgame-ai-{self.fingerprint[:24]}'

    def _git(self, args: list[str]) -> str:
        cp = subprocess.run(['git', *args], cwd=self.root, capture_output=True, text=True)
        if cp.returncode != 0:
            detail = (cp.stderr or cp.stdout or '').strip()
            raise RuntimeError(f"git {' '.join(args)} failed while building stable prefix: {detail}")
        return cp.stdout

    def _include(self, rel: str) -> bool:
        rel = rel.replace('\\', '/')
        parts = set(pathlib.PurePosixPath(rel).parts)
        if parts & STATIC_PREFIX_SKIP_PARTS:
            return False
        if any((rel.startswith(prefix) for prefix in STATIC_PREFIX_SKIP_PREFIXES)):
            return False
        path = pathlib.PurePosixPath(rel)
        return path.name in STATIC_PREFIX_NAMES or path.suffix in STATIC_PREFIX_SUFFIXES

    def _source_files(self) -> list[str]:
        raw = self._git(['ls-files', '-z'])
        files = [item for item in raw.split('\x00') if item]
        return sorted((item.replace('\\', '/') for item in files if self._include(item)))

    def _read_file(self, rel: str) -> str:
        return (self.root / rel).read_text(encoding='utf-8', errors='replace')

    def _render(self) -> tuple[str, str]:
        digest = hashlib.sha256()
        manifest: list[dict[str, Any]] = []
        file_text: list[tuple[str, str]] = []
        for rel in self.files:
            content = self._read_file(rel)
            encoded = content.encode('utf-8', errors='replace')
            digest.update(rel.encode('utf-8'))
            digest.update(b'\x00')
            digest.update(encoded)
            manifest.append({'path': rel, 'chars': len(content), 'bytes': len(encoded)})
            file_text.append((rel, content))
        chunks = ['ENDGAME-AI STABLE PREFIX', 'This is the real checked-out source used by the local organism.', 'Provider prompt caches can reuse this prefix because dynamic run data appears after it.', 'Self-evolution must ground changes in these files, not in hallucinated structure.', '', 'ORGANISM OPERATING RULES:', 'You are one organ inside endgame-ai, a local desktop organism controlled by the Python body.', 'Organs: planner makes intent, scheduler selects a step, observe scans the screen, execute acts, verify judges, reflect diagnoses, self_modify evolves the repository, satisfied halts, error routes mechanical failures.', 'The body can use mouse, keyboard, subprocesses, files, apps, browser, Python modules, and git through the shared capability runtime.', 'Every brain call receives a fresh whole-screen hover observation at the end of the dynamic payload. Treat stale state as history only.', 'The brain-facing desktop_tree is semantic and id-based. Coordinates, hwnds, runtime ids, and UIA metadata live in body-side action_index/raw artifacts; act by node id.', '', 'STATIC MANIFEST:', json.dumps(manifest, ensure_ascii=False, indent=2), '', 'STATIC SOURCE FILES:']
        for rel, content in file_text:
            chunks.append(f'\n--- BEGIN FILE {rel} ---')
            chunks.append(content)
            chunks.append(f'--- END FILE {rel} ---')
        return ('\n'.join(chunks), digest.hexdigest())

def stable_prefix() -> StablePrefix:
    global _STABLE_PREFIX_CACHE
    with _STABLE_PREFIX_LOCK:
        fresh = StablePrefix(ROOT)
        if _STABLE_PREFIX_CACHE is None or _STABLE_PREFIX_CACHE.fingerprint != fresh.fingerprint:
            _STABLE_PREFIX_CACHE = fresh
        return _STABLE_PREFIX_CACHE

def _stable_prefix_enabled(wiring: dict[str, Any], expected_record_type: str | None=None) -> bool:
    sp_cfg = wiring.get('model', {}).get('stable_prefix', {})
    if bool(sp_cfg.get('enabled', False)):
        return True
    record_types = sp_cfg.get('for_record_types') or []
    return bool(expected_record_type and expected_record_type in set(map(str, record_types)))

def _stable_prefix_include_in_request(wiring: dict[str, Any], expected_record_type: str | None=None) -> bool:
    sp_cfg = wiring.get('model', {}).get('stable_prefix', {})
    if bool(sp_cfg.get('include_in_request', False)):
        return True
    include_for = sp_cfg.get('include_for_record_types') or []
    return bool(expected_record_type and expected_record_type in set(map(str, include_for)))

def _messages(system_prompt: str, user_text: str, prefix: StablePrefix | None) -> list[dict[str, str]]:
    if prefix is not None:
        return [{'role': 'system', 'content': prefix.text + '\n\nDYNAMIC NODE PROMPT:\n' + system_prompt}, {'role': 'user', 'content': user_text}]
    return [{'role': 'system', 'content': 'DYNAMIC NODE PROMPT:\n' + system_prompt}, {'role': 'user', 'content': user_text}]

def _commit_record(content: str) -> dict[str, Any]:
    record = extract_json_object(content)
    if record is None:
        raise RuntimeError(f'brain did not commit a valid JSON object: {content}')
    if not isinstance(record.get('record_type'), str):
        raise RuntimeError(f'brain record missing string record_type: {record}')
    if 'data' not in record or not isinstance(record['data'], dict):
        raise RuntimeError(f'brain record missing object data: {record}')
    return record

def _effective_reasoning_config(wiring: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    model_global = wiring.get('model', {}).get('global', {})
    reasoning_cfg = dict(cfg.get('reasoning') or {})
    reasoning_cfg['enabled'] = bool(reasoning_cfg.get('enabled', model_global.get('reasoning_enabled', False)))
    reasoning_cfg.setdefault('pattern', 'two_pass' if reasoning_cfg['enabled'] else 'single_pass')
    reasoning_cfg.setdefault('extractor', 'think_tags')
    reasoning_cfg.setdefault('injection_template', 'REASONING_FEEDBACK:\n{reasoning}\n\nReturn only the requested JSON record.')
    return reasoning_cfg

def _normalize_observation(obj: Any) -> dict[str, Any] | None:
    if not isinstance(obj, dict) or not obj.get('desktop_tree_text'):
        return None
    return {'focused_title': obj.get('focused_title', ''), 'desktop_tree_text': obj.get('desktop_tree_text', ''), 'observed_at': obj.get('observed_at'), 'fresh_scan': obj.get('fresh_scan', True)}

def _fresh_observation_payload(wiring: dict[str, Any], payload: dict[str, Any] | None=None) -> dict[str, Any]:
    global _LAST_FRESH_OBSERVATION
    if payload:
        candidates = [payload.get('fresh_observation'), payload.get('observation')]
        evidence = payload.get('evidence')
        if isinstance(evidence, dict):
            candidates.extend([evidence.get('fresh_observation'), evidence.get('observation')])
        for candidate in candidates:
            normalized = _normalize_observation(candidate)
            if normalized is not None:
                _LAST_FRESH_OBSERVATION = normalized
                return normalized
    import desktop
    obs = desktop.observe(wiring.get('observe_config', {}))
    result = {'focused_title': obs.get('focused_title', ''), 'desktop_tree_text': obs.get('desktop_tree_text', ''), 'observed_at': obs.get('observed_at'), 'fresh_scan': obs.get('fresh_scan', True)}
    _LAST_FRESH_OBSERVATION = result
    return result

def last_fresh_observation() -> dict[str, Any]:
    return dict(_LAST_FRESH_OBSERVATION or {})

def _with_fresh_observation(payload: dict[str, Any], wiring: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(payload)
    enriched['fresh_observation'] = _fresh_observation_payload(wiring, enriched)
    if isinstance(enriched.get('observation'), dict) and enriched['observation'].get('desktop_tree_text'):
        enriched.pop('observation', None)
    return enriched

def root_path(value: str | None, default: str='') -> pathlib.Path:
    raw = os.path.expandvars(os.path.expanduser(str(value or default)))
    p = pathlib.Path(raw)
    return p if p.is_absolute() else ROOT / p

def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f'malformed JSON in {path}: {exc}') from exc

def atomic_write_json(path: pathlib.Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f'{path.name}.tmp.{os.getpid()}.{threading.get_ident()}')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    os.replace(tmp, path)

def append_ndjson(path: pathlib.Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(obj, ensure_ascii=False, default=str) + '\n')

def raw_log_path(cfg: dict[str, Any] | None=None) -> pathlib.Path:
    global _RAW_LOG_PATH
    cfg = cfg or {}
    if _RAW_LOG_PATH is None:
        explicit = cfg.get('raw_log_path')
        if explicit:
            _RAW_LOG_PATH = root_path(str(explicit))
        else:
            _RAW_LOG_PATH = ROOT / f"{time.strftime('%Y%m%dT%H%M%S')}_brain.jsonl"
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
    if cfg.get('raw_log', True) is False:
        return
    row = dict(entry)
    row.setdefault('ts', time.time())
    row.setdefault('iso', time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime()))
    row.setdefault('seq', _next_raw_seq())
    path = raw_log_path(cfg)
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + '\n')

def reset_call_budget() -> None:
    global _CALLS_MADE
    _CALLS_MADE = 0

def _load_transport_module(name: str, wiring: dict[str, Any]):
    paths = wiring.get('paths', {})
    brain_dir = root_path(paths.get('brains'), 'brain_transports')
    module_path = brain_dir / f'{name}.py'
    if not module_path.exists():
        raise RuntimeError(f"selected brain transport '{name}' has no module at {module_path}; brain selection is fail-hard and no fallback was attempted")
    spec = importlib.util.spec_from_file_location(f'endgame_brain_transport_{name}', module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'cannot load selected brain transport module: {module_path}')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, 'call'):
        raise RuntimeError(f"brain transport '{name}' does not export call(messages, cfg)")
    return mod

def _get_transport_config(wiring: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    model = wiring.get('model')
    if not isinstance(model, dict):
        raise RuntimeError('wiring.json missing object model')
    transport = str(model.get('transport') or '').strip()
    if not transport:
        raise RuntimeError('wiring model.transport is empty; no fallback transport is allowed')
    transport_config = model.get('transport_config', {})
    if not isinstance(transport_config, dict) or transport not in transport_config:
        raise RuntimeError(f'wiring model.transport_config.{transport} missing; no fallback transport config is allowed')
    cfg = dict(transport_config[transport])
    global_keys = {'timeout', 'max_brain_calls', 'raw_log', 'raw_log_path', 'log_raw'}
    global_cfg = model.get('global', {})
    for k in global_keys:
        if isinstance(global_cfg, dict) and k in global_cfg and (k not in cfg):
            cfg[k] = global_cfg[k]
        if k in model and k not in cfg:
            cfg[k] = model[k]
    cfg['transport'] = transport
    return (transport, cfg)

def _structured_outputs_enabled(cfg: dict[str, Any]) -> bool:
    structured = cfg.get('structured_outputs')
    if isinstance(structured, dict):
        return bool(structured.get('enabled', False))
    return bool(structured)

def _record_response_format(record_type: str) -> dict[str, Any]:
    return {'type': 'json_object'}

def _organ_request_config(wiring: dict[str, Any], record_type: str | None) -> dict[str, Any]:
    if not record_type:
        return {}
    organs = wiring.get('model', {}).get('organs', {})
    if not isinstance(organs, dict):
        return {}
    cfg = organs.get(record_type)
    if not isinstance(cfg, dict):
        return {}
    allowed_keys = {'temperature', 'top_p', 'max_output_tokens', 'timeout', 'truncation', 'reasoning_effort', 'web_search', 'tool_choice', 'parallel_tool_calls'}
    return {key: value for key, value in cfg.items() if key in allowed_keys}

def call(messages: list[dict[str, str]], wiring: dict[str, Any], *, rod_feedback: bool=False, response_format: dict[str, Any] | None=None, request_config: dict[str, Any] | None=None) -> dict[str, str]:
    stop_check.check_stop('brain call')
    global _CALLS_MADE
    transport, cfg = _get_transport_config(wiring)
    if response_format is not None:
        cfg = dict(cfg)
        cfg['response_format'] = response_format
    if request_config:
        cfg = dict(cfg)
        cfg.update(request_config)
    model_cfg = wiring.get('model', {})
    max_calls = model_cfg.get('max_brain_calls')
    if max_calls is None and isinstance(model_cfg.get('global'), dict):
        max_calls = model_cfg['global'].get('max_brain_calls')
    if max_calls is not None and _CALLS_MADE >= int(max_calls):
        raise RuntimeError(f'brain call budget exceeded: {_CALLS_MADE}/{max_calls}')
    _CALLS_MADE += 1
    seq = _next_raw_seq()
    started = time.time()
    log_raw_entry(cfg, {'seq': seq, 'phase': 'request', 'transport': transport, 'rod_feedback': rod_feedback, 'messages': messages})
    mod = _load_transport_module(transport, wiring)
    try:
        result = mod.call(messages, cfg)
    except Exception as exc:
        log_raw_entry(cfg, {'seq': seq, 'phase': 'error', 'transport': transport, 'elapsed_s': round(time.time() - started, 3), 'error': f'{type(exc).__name__}: {exc}'})
        raise RuntimeError(f'{transport} brain failed hard: {exc}') from exc
    if not isinstance(result, dict):
        raise RuntimeError(f'{transport} brain contract violation: expected dict, got {type(result).__name__}')
    content = result.get('content')
    reasoning = result.get('reasoning', '')
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(f'{transport} brain contract violation: missing non-empty content')
    if reasoning is not None and (not isinstance(reasoning, str)):
        raise RuntimeError(f'{transport} brain contract violation: reasoning must be string when present')
    out = {'content': content, 'reasoning': reasoning or ''}
    log_raw_entry(cfg, {'seq': seq, 'phase': 'response', 'transport': transport, 'elapsed_s': round(time.time() - started, 3), 'content': content, 'reasoning': reasoning or '', 'raw': {k: v for k, v in result.items() if k not in {'content', 'reasoning'}}})
    return out

def reasoning_from(content: str, reasoning: str='') -> str:
    if reasoning and reasoning.strip():
        return reasoning.strip()
    m = re.search('<think>(.*?)</think>', content or '', flags=re.S | re.I)
    if m:
        return m.group(1).strip()
    return (content or '').strip()

def extract_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    s = text.strip()
    if '</think>' in s.lower():
        s = re.split('</think>', s, maxsplit=1, flags=re.I)[-1].strip()
    fenced = re.fullmatch('```(?:json)?\\s*(.*?)\\s*```', s, flags=re.S | re.I)
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
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == '{':
            if depth == 0:
                start = i
                starts.append(i)
            depth += 1
        elif ch == '}':
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

def think(system_prompt: str, payload: dict[str, Any], wiring: dict[str, Any], *, expected_record_type: str | None=None, request_config: dict[str, Any] | None=None) -> dict[str, Any]:
    _, cfg = _get_transport_config(wiring)
    reasoning_cfg = _effective_reasoning_config(wiring, cfg)
    prefix = stable_prefix() if _stable_prefix_enabled(wiring, expected_record_type) else None
    prefix_for_messages = prefix if _stable_prefix_include_in_request(wiring, expected_record_type) else None
    conv_id = wiring.get('_conv_id')
    if not conv_id:
        import hashlib, time
        conv_id = f'endgame-ai-{int(time.time())}-{hashlib.md5(str(wiring).encode()).hexdigest()[:8]}'
        wiring['_conv_id'] = conv_id
    payload = _with_fresh_observation(payload, wiring)
    user_text = json.dumps(payload, ensure_ascii=False, default=str)
    pattern = str(reasoning_cfg.get('pattern') or 'single_pass')
    response_format = _record_response_format(expected_record_type) if expected_record_type and _structured_outputs_enabled(cfg) else None
    request_cfg = _organ_request_config(wiring, expected_record_type)
    request_cfg.update(dict(request_config or {}))
    if cfg.get('transport') == 'xai':
        request_cfg.setdefault('prompt_cache_key', conv_id)
    if cfg.get('transport') == 'xai' and expected_record_type:
        default_effort_map = {'plan': 'medium', 'action_frame': 'medium', 'execution': 'low', 'verification': 'none', 'reflection': 'medium', 'git_evolution_patch': 'high', 'schedule': 'none', 'satisfied': 'none'}
        request_cfg.setdefault('reasoning_effort', default_effort_map.get(expected_record_type, 'low'))
    if not reasoning_cfg['enabled'] or pattern == 'single_pass':
        result = call(_messages(system_prompt, user_text, prefix_for_messages), wiring, rod_feedback=False, response_format=response_format, request_config=request_cfg)
        record = _commit_record(result['content'])
        record.setdefault('reasoning', reasoning_from(result['content'], result.get('reasoning', '')))
        return record
    if pattern == 'native':
        result = call(_messages(system_prompt, user_text, prefix_for_messages), wiring, rod_feedback=False, response_format=response_format, request_config=request_cfg)
        record = _commit_record(result['content'])
        record.setdefault('reasoning', reasoning_from(result['content'], result.get('reasoning', '')))
        return record
    if pattern != 'two_pass':
        raise RuntimeError(f'unknown reasoning pattern: {pattern}')
    first = call(_messages(system_prompt, user_text, prefix_for_messages), wiring, rod_feedback=False, request_config=request_cfg)
    reasoning = reasoning_from(first['content'], first.get('reasoning', ''))
    template = str(reasoning_cfg.get('injection_template') or 'REASONING_FEEDBACK:\n{reasoning}')
    second = call(_messages(system_prompt, user_text + '\n\n' + template.format(reasoning=reasoning), prefix_for_messages), wiring, rod_feedback=True, response_format=response_format, request_config=request_cfg)
    record = _commit_record(second['content'])
    record.setdefault('reasoning', reasoning)
    return record