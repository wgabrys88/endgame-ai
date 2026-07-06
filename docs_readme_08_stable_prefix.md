# 8. Stable Prefix: Prompt Caching for Free

## The Problem

Every brain call sends the full system prompt + static source files. For large repos, this burns tokens and latency.

## The Solution: Stable Prefix

```json
"stable_prefix": {
  "enabled": true,
  "include_in_request": true
}
```

When enabled, the organism computes a **content-addressed fingerprint** of all tracked source files (`.py`, `.json`, `.md`, `.gitattributes`, `.gitignore`, `LICENSE` — excluding `.git`, `__pycache__`, `runtime_*`).

```python
class StablePrefix:
    def _render(self) -> tuple[str, str]:
        digest = hashlib.sha256()
        for rel in self.files:  # sorted git ls-files
            content = self._read_file(rel)
            digest.update(rel.encode("utf-8"))
            digest.update(b"\0")
            digest.update(content.encode("utf-8"))
        # cache_key = f"endgame-ai-{fingerprint[:24]}"
```

The fingerprint becomes the **prompt cache key** (`prompt_cache_key` sent to xAI API). Provider caches the prefix; only dynamic data (goal, state, fresh observation) follows.

## Manifest + Source In Prompt

```
ENDGAME-AI STABLE PREFIX
This is the real checked-out source used by the local organism.
Provider prompt caches can reuse this prefix because dynamic run data appears after it.
Self-evolution must ground changes in these files, not in hallucinated structure.

ORGANISM OPERATING RULES:
You are one organ inside endgame-ai...

STATIC MANIFEST:
[{"path": "core_nodes.py", "chars": 23456, "bytes": 23456}, ...]

STATIC SOURCE FILES:
--- BEGIN FILE core_nodes.py ---
[full file content]
--- END FILE core_nodes.py ---
```

## Why It Matters

- **Tokens**: Static source sent once, cached by provider
- **Latency**: Cache hit = faster first token
- **Correctness**: Brain *always* sees actual checked-out code, never hallucinated structure
- **Self-modify grounding**: Patches must match the fingerprint or cache invalidates

Enable in `wiring.json`:
```json
"model": {
  "stable_prefix": { "enabled": true, "include_in_request": true },
  "transport": "transport_xai",
  "transport_config": { "transport_xai": { "mode": "api", "model": "grok-4.3" } }
}
```