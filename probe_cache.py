"""probe_cache.py — deterministic probe: does prompt_cache_key revive the dead KV cache?

Measured in production: input_tokens_details.cached_tokens is pinned near a low floor on
every /v1/responses call though prompts run thousands of tokens. Hypothesis (from the request
log, deductively): requests hit different servers each call because no routing hint is sent, so
no server holds the KV prefix. prompt_cache_key is the documented Responses-API routing hint.

This probe reconstructs ONE logged moment's EXACT messages (via tools_replay_grok) and sends it
four ways, reading usage.input_tokens_details.cached_tokens each time:
  A1 WARM   fixed key, first send    (establishes KV on a server)
  A2 HIT?   fixed key, second send   (same server -> prefix should cache)
  B  COLD   different random key     (different server -> no cache)
  C  NOKEY  no key (production today) (random routing baseline)

PASS if A2 cached >> A1 and A2 cached >> B/C. Then routing was the disease.
FAIL if A2 stays at the floor -> not routing; suspect prefix instability or a model minimum.

Stateless: store=false is already in wiring; each send is an independent waking.
Run on Windows via powershell so XAI_API_KEY is in env:
  python probe_cache.py request-logs-2026-07-17.jsonl 0
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

import core_brain as brain
import core_wiring as wiring
import tools_replay_grok as replay
from core_bus import deep_merge, drop_nulls

FIXED_KEY = "probe-endgame-cache-stable-key-001"
RANDOM_KEY = "probe-endgame-cache-random-key-999"


def _payload(cfg, messages, response_format, override):
    body = deep_merge(cfg["request"], override or {})
    body["input"] = [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in messages
        if m.get("role", "user") in {"system", "user", "assistant"}
    ]
    if isinstance(response_format, dict):
        if str(response_format.get("type", "json_schema")) == "json_object":
            body["text"] = {"format": {"type": "json_object"}}
        else:
            body["text"] = {"format": {
                "type": response_format.get("type", "json_schema"),
                "name": response_format.get("name", "record"),
                "schema": response_format.get("schema", {}),
                "strict": bool(response_format.get("strict", True)),
            }}
    return drop_nulls(body)


def _send(label, cfg, messages, response_format, override):
    payload = _payload(cfg, messages, response_format, override)
    api_key = os.environ["XAI_API_KEY"]
    req = urllib.request.Request(
        cfg["url"], data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=float(cfg["timeout"])) as resp:
        obj = json.loads(resp.read().decode("utf-8"))
    usage = obj.get("usage", {}) or {}
    details = usage.get("input_tokens_details", {}) or {}
    cached = int(details.get("cached_tokens", 0) or 0)
    total = int(usage.get("input_tokens", 0) or usage.get("promptTokens", 0) or 0)
    pct = (100 * cached // total) if total else 0
    print(f"[{label:<8}] input_tokens={total:>6}  cached_tokens={cached:>6}  ({pct}% cached)")
    return cached, total


def main() -> int:
    log = sys.argv[1] if len(sys.argv) > 1 else "request-logs-2026-07-17.jsonl"
    line = int(sys.argv[2]) if len(sys.argv) > 2 else 0

    obj = replay._line(log, line)
    messages = replay._messages(obj)
    record_type = replay._record_type(obj)

    w = wiring.load_wiring()
    _, cfg = wiring.get_transport_config(w)
    node = replay._EMITTING_NODE.get(record_type)
    response_format = brain._record_response_format(w, record_type, node) if record_type else None

    print("=" * 64)
    print(f"KV-CACHE PROBE — log={log} line={line} record_type={record_type}")
    print("=" * 64)
    print("\n--- A1 WARM (fixed key, first send) ---")
    a1, _ = _send("A1-WARM", cfg, messages, response_format, {"prompt_cache_key": FIXED_KEY})
    print("\n--- A2 HIT? (fixed key, second send, identical payload) ---")
    a2, _ = _send("A2-HIT", cfg, messages, response_format, {"prompt_cache_key": FIXED_KEY})
    print("\n--- B COLD (different random key) ---")
    b, _ = _send("B-COLD", cfg, messages, response_format, {"prompt_cache_key": RANDOM_KEY})
    print("\n--- C NOKEY (production baseline, no routing hint) ---")
    c, _ = _send("C-NOKEY", cfg, messages, response_format, None)

    print("\n" + "=" * 64)
    if a2 > a1 and a2 > b and a2 > c:
        print(f"PASS — prompt_cache_key REVIVES the cache. A2={a2} vs A1={a1} B={b} C={c}.")
        print("Root cause confirmed: missing routing hint => random server => no KV reuse.")
    else:
        print(f"FAIL/INCONCLUSIVE — A1={a1} A2={a2} B={b} C={c}.")
        print("Not routing. Suspect prefix instability or a model/provider minimum. Do NOT ship the key.")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
