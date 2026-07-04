from __future__ import annotations
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
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
STATIC_PREFIX_SUFFIXES = {'.py', '.json', '.md'}
DYNAMIC_LAST_KEYS = ('fresh_observation', 'observation', 'desktop_tree_text', 'evidence', 'workspace_manifest')
ORGAN_IDENTITY = {'planner': 'You are planner: maintain goal_narration (required every tick) as a living interpretation of goal_seed. Use goal_signals.power/disk/urgency to adapt narration and intent. Emit one JSON record.', 'execute': 'You are execute: generate runnable Python with full local power (subprocess, ctypes, os, sys, files, registry, no sandbox). You may run any code on this Windows body. Emit one JSON execution record.', 'frame_action': 'You are frame_action: explore the screen evidence and frame the next concrete action strategy. Emit one JSON record.', 'verify': 'You are verify: compare step.done_when against fresh observation and execution evidence. Emit one JSON record.', 'reflect': 'You are reflect: diagnose failures and choose one recovery signal. Emit one JSON record.', 'self_modify': 'You are self_modify: propose git-native firmware patches grounded in repository evidence. Emit one JSON record.', 'satisfied': 'You are satisfied: honest halt gate. Emit one JSON record.'}
ORGAN_CORE = 'IDENTITY: Technical computer-control organ inside endgame-ai, a living organism on Windows 11. Python is the body, desktop is the world, wiring.json is the nervous system, git is firmware memory. Stance: exploratory, adaptive, source-grounded. BUS: emit exactly one signal + one patch per tick; topology routes signals only. OUTPUT: one JSON object with record_type, data, reasoning. Dynamic runtime data is in the user message tail; treat it as freshest truth.'
STATIC_PREFIX_NAMES = {'.gitattributes', '.gitignore', 'LICENSE'}
STATIC_PREFIX_SKIP_PARTS = {'.git', '__pycache__', '.pytest_cache', 'comms', 'pids'}
STATIC_PREFIX_SKIP_PREFIXES = {'reports/'}
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
        chunks = ['ENDGAME-AI STABLE PREFIX', 'Checked-out firmware for KV-cache reuse. Dynamic runtime payload is appended after this block in the user message.', ORGAN_CORE, '', 'STATIC MANIFEST:', json.dumps(manifest, ensure_ascii=False, indent=2), '', 'STATIC SOURCE FILES:']
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

def _organ_system_prompt(organ: str, static_prompt: str) -> str:
    organ_line = ORGAN_IDENTITY.get(organ, f'You are {organ}, an endgame-ai organ.')
    return ORGAN_CORE + '\n' + organ_line + '\n\nORGAN PROMPT:\n' + static_prompt

def _order_payload(payload: dict[str, Any]) -> dict[str, Any]:
    head: dict[str, Any] = {}
    tail: dict[str, Any] = {}
    for key, value in payload.items():
        if key in DYNAMIC_LAST_KEYS:
            tail[key] = value
        else:
            head[key] = value
    return {**head, **tail}

def _cap_observation_fields(payload: dict[str, Any], wiring: dict[str, Any]) -> dict[str, Any]:
    limits = wiring.get('limits', {})
    max_obs = int(limits.get('max_observation_chars', 8000))
    out = dict(payload)
    for key in ('fresh_observation', 'observation'):
        block = out.get(key)
        if isinstance(block, dict) and isinstance(block.get('desktop_tree_text'), str):
            text = block['desktop_tree_text']
            if len(text) > max_obs:
                block = dict(block)
                block['desktop_tree_text'] = text[:max_obs] + f'\n... observation capped at {max_obs} chars'
                block['truncated'] = True
                out[key] = block
    return out

def _preflight_request(wiring: dict[str, Any], user_text: str) -> None:
    limits = wiring.get('limits', {})
    max_chars = int(limits.get('max_request_chars', 120000))
    if len(user_text) > max_chars:
        raise RuntimeError(f'brain request size {len(user_text)} exceeds limits.max_request_chars={max_chars}')

def _messages(organ: str, static_prompt: str, user_text: str, prefix: StablePrefix | None) -> list[dict[str, str]]:
    system = _organ_system_prompt(organ, static_prompt)
    if prefix is not None:
        system = prefix.text + '\n\n' + system
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': user_text}]

def _commit_record(content: str, expected_record_type: str | None=None) -> dict[str, Any]:
    record = extract_json_object(content)
    if record is None:
        raise RuntimeError(f'brain did not commit a valid JSON object: {content}')
    if not isinstance(record.get('record_type'), str) or not str(record.get('record_type', '')).strip():
        if expected_record_type:
            reasoning = record.get('reasoning', '') if isinstance(record.get('reasoning'), str) else ''
            data = record.get('data') if isinstance(record.get('data'), dict) else {k: v for k, v in record.items() if k != 'reasoning'}
            record = {'record_type': expected_record_type, 'data': data, 'reasoning': reasoning}
        else:
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
        explicit = cfg.get('raw_log_path') or 'comms/brain_raw.jsonl'
        _RAW_LOG_PATH = root_path(str(explicit))
        _RAW_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _RAW_LOG_PATH.touch(exist_ok=True)
    return _RAW_LOG_PATH

def _redact_secrets(obj: Any) -> Any:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for key, value in obj.items():
            lk = str(key).lower()
            if lk in {'authorization', 'api_key', 'xai_api_key'} or 'api_key' in lk:
                out[key] = '[REDACTED]'
            else:
                out[key] = _redact_secrets(value)
        return out
    if isinstance(obj, list):
        return [_redact_secrets(item) for item in obj]
    return obj

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

def reset_raw_log() -> None:
    global _RAW_LOG_PATH, _RAW_SEQ
    _RAW_LOG_PATH = None
    _RAW_SEQ = 0

def _transport_call(transport: str, messages: list[dict[str, str]], cfg: dict[str, Any]) -> dict[str, Any]:
    if transport != 'xai':
        raise RuntimeError(f"unsupported brain transport: {transport}")
    return _xai_call(messages, cfg)

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
    try:
        result = _transport_call(transport, messages, cfg)
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
    log_raw_entry(cfg, {'seq': seq, 'phase': 'response', 'transport': transport, 'elapsed_s': round(time.time() - started, 3), 'content': content, 'reasoning': reasoning or '', 'api_response_body': result.get('api_response_body'), 'usage': result.get('usage'), 'raw': {k: v for k, v in result.items() if k not in {'content', 'reasoning', 'api_response_body'}}})
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

def think(system_prompt: str, payload: dict[str, Any], wiring: dict[str, Any], *, organ: str, expected_record_type: str | None=None, request_config: dict[str, Any] | None=None) -> dict[str, Any]:
    print(f'[brain] organ={organ} record={expected_record_type or "none"} calling transport...', flush=True)
    _, cfg = _get_transport_config(wiring)
    reasoning_cfg = _effective_reasoning_config(wiring, cfg)
    prefix = stable_prefix() if _stable_prefix_enabled(wiring, expected_record_type) else None
    prefix_for_messages = prefix if _stable_prefix_include_in_request(wiring, expected_record_type) else None
    conv_id = wiring.get('_conv_id')
    if not conv_id:
        import hashlib, time
        conv_id = f'endgame-ai-{int(time.time())}-{hashlib.md5(str(wiring).encode()).hexdigest()[:8]}'
        wiring['_conv_id'] = conv_id
    payload = _cap_observation_fields(_with_fresh_observation(payload, wiring), wiring)
    user_text = json.dumps(_order_payload(payload), ensure_ascii=False, default=str)
    _preflight_request(wiring, user_text)
    log_raw_entry(cfg, {'phase': 'think', 'organ': organ, 'expected_record_type': expected_record_type, 'payload': payload, 'user_text': user_text, 'user_text_len': len(user_text)})
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
        result = call(_messages(organ, system_prompt, user_text, prefix_for_messages), wiring, rod_feedback=False, response_format=response_format, request_config=request_cfg)
        record = _commit_record(result['content'], expected_record_type)
        record.setdefault('reasoning', reasoning_from(result['content'], result.get('reasoning', '')))
        print(f'[brain] organ={organ} record={record.get("record_type")} ok', flush=True)
        return record
    if pattern == 'native':
        result = call(_messages(organ, system_prompt, user_text, prefix_for_messages), wiring, rod_feedback=False, response_format=response_format, request_config=request_cfg)
        record = _commit_record(result['content'], expected_record_type)
        record.setdefault('reasoning', reasoning_from(result['content'], result.get('reasoning', '')))
        print(f'[brain] organ={organ} record={record.get("record_type")} ok', flush=True)
        return record
    if pattern != 'two_pass':
        raise RuntimeError(f'unknown reasoning pattern: {pattern}')
    first = call(_messages(organ, system_prompt, user_text, prefix_for_messages), wiring, rod_feedback=False, request_config=request_cfg)
    reasoning = reasoning_from(first['content'], first.get('reasoning', ''))
    template = str(reasoning_cfg.get('injection_template') or 'REASONING_FEEDBACK:\n{reasoning}')
    second = call(_messages(organ, system_prompt, user_text + '\n\n' + template.format(reasoning=reasoning), prefix_for_messages), wiring, rod_feedback=True, response_format=response_format, request_config=request_cfg)
    record = _commit_record(second['content'], expected_record_type)
    record.setdefault('reasoning', reasoning)
    print(f'[brain] organ={organ} record={record.get("record_type")} ok', flush=True)
    return record

def _xai_call(messages: list[dict[str, str]], cfg: dict[str, Any]) -> dict[str, Any]:
    if cfg.get('mode') == 'cli':
        return _xai_call_cli(messages, cfg)
    api_key = os.environ.get(str(cfg.get('api_key_env') or 'XAI_API_KEY')) or cfg.get('api_key')
    if not api_key:
        raise RuntimeError('xai api: API key missing')
    url = str(cfg.get('url') or 'https://api.x.ai/v1/responses')
    model = str(cfg.get('model') or 'grok-4.3')
    input_data = [{'role': m.get('role', 'user'), 'content': m.get('content', '')} for m in messages]
    payload: dict[str, Any] = {'model': model, 'input': input_data, 'temperature': cfg.get('temperature', 0.2), 'truncation': str(cfg.get('truncation') or 'disabled')}
    for key in ('top_p', 'parallel_tool_calls', 'tool_choice', 'prompt_cache_key', 'store', 'metadata', 'max_output_tokens'):
        if cfg.get(key) is not None:
            payload[key] = cfg[key]
    if isinstance(cfg.get('include'), list):
        payload['include'] = list(cfg['include'])
    response_format = cfg.get('response_format')
    if isinstance(response_format, dict):
        payload['text'] = {'format': {'type': 'json_object'}} if response_format.get('type') == 'json_object' else {'format': response_format}
    effort = cfg.get('reasoning_effort') or (cfg.get('reasoning') or {}).get('effort')
    if effort or str(model).startswith('grok-4'):
        payload['reasoning'] = {'effort': str(effort or 'low')}
    web_search_cfg = cfg.get('web_search') or {}
    if isinstance(web_search_cfg, dict) and web_search_cfg.get('enabled'):
        tool: dict[str, Any] = {'type': 'web_search'}
        allowed = web_search_cfg.get('allowed_domains')
        if allowed:
            tool['filters'] = {'allowed_domains': [str(item) for item in allowed][:5]}
        payload['tools'] = [tool]
    log_raw_entry(cfg, {'phase': 'api_request', 'url': url, 'payload': _redact_secrets(payload)})
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=float(cfg.get('timeout') or 120)) as resp:
            body = resp.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode('utf-8', errors='replace')
        log_raw_entry(cfg, {'phase': 'api_error', 'status': exc.code, 'body': err_body})
        raise RuntimeError(f'xai api HTTP {exc.code}: {err_body[:2000]}') from exc
    log_raw_entry(cfg, {'phase': 'api_response_body', 'body': body})
    obj = json.loads(body)
    content = obj.get('output_text') or ''
    reasoning = ''
    if not content and isinstance(obj.get('output'), list):
        parts = []
        for item in obj['output']:
            if not isinstance(item, dict):
                continue
            if item.get('type') == 'reasoning':
                for c in item.get('content', []) or []:
                    if isinstance(c, dict) and c.get('text'):
                        reasoning += str(c['text']) + '\n'
                continue
            for c in item.get('content', []) or []:
                if isinstance(c, dict) and c.get('text'):
                    parts.append(str(c['text']))
        content = '\n'.join(parts)
    return {'content': content, 'reasoning': reasoning.strip(), 'usage': obj.get('usage', {}), 'body': obj, 'api_response_body': body}

def _xai_call_cli(messages: list[dict[str, str]], cfg: dict[str, Any]) -> dict[str, Any]:
    raw = os.path.expandvars(os.path.expanduser(str(cfg.get('executable') or 'grok')))
    exe = str(pathlib.Path(raw)) if pathlib.Path(raw).exists() else shutil.which(raw)
    if not exe:
        raise RuntimeError(f'grok cli missing: {raw}')
    prompt = '\n\n'.join((f"[{m.get('role', 'user').upper()}]\n{m.get('content', '')}" for m in messages))
    cp = subprocess.run([exe, '-p', '--output-format', 'json', '--no-auto-update', prompt], capture_output=True, text=True, timeout=float(cfg.get('timeout') or 120))
    if cp.returncode != 0:
        raise RuntimeError(f'grok cli exit {cp.returncode}: {cp.stderr.strip()[:2000]}')
    try:
        obj = json.loads(cp.stdout.strip())
        return {'content': obj.get('content') or obj.get('message') or cp.stdout, 'reasoning': obj.get('reasoning') or '', 'stdout': cp.stdout}
    except json.JSONDecodeError:
        return {'content': cp.stdout, 'reasoning': '', 'stdout': cp.stdout}