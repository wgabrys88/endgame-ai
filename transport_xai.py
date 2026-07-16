"""[transport_xai] — the mouth that speaketh unto grok-4.3 at POST /v1/responses.

This module is the SCHEMA AUTHORITY: the catalog below names every field the
grok-4.3 Responses API accepts and its allowed values. wiring.json holds only the
values the organism actually sends (its [request] base plus named [request_profiles]
and per-organ overrides); this file records what is POSSIBLE. To send a field the
organism does not yet use, add it to wiring — its legal shape is documented here.

═══════════════════════════════════════════════════════════════════════════════
 GROK-4.3  /v1/responses  REQUEST FIELD CATALOG  (allowed values | default)
═══════════════════════════════════════════════════════════════════════════════
 REQUIRED
   model                 str                      e.g. "grok-4.3" / "grok-4.3-latest"
   input                 array[{role,content}]    filled by the caller each turn
 SAMPLING
   temperature           float 0..2              | default 0.7
   top_p                 float 0..1              | default 0.95
   max_output_tokens     int > 0                 | default null (model max)
   seed                  int                     | default null
 REASONING
   reasoning.effort      none|low|medium|high    | default low  (grok-4.3 alone allows "none")
   reasoning.summary     null|"auto"|"concise"|"detailed"
 OUTPUT FORMAT
   text.format.type      text|json_object|json_schema
   text.format           {type,name,schema,strict}   built from a record contract
 TOOLS   (max 128 tools; structured-output+tools = Grok-4 family only)
   tools[]               function: {type:"function", name, description, parameters(json-schema, root object)}
                         server:   {type:"web_search"[, filters:{allowed_domains|excluded_domains (<=5)}]}
                                   {type:"x_search"} {type:"code_interpreter"}
                                   {type:"file_search", vector_store_ids:[...]}
                                   {type:"mcp", server_label, server_url, headers}
   tool_choice           "auto"|"none"|"required"|{"type":"function","function":{"name":X}}   | default auto
   parallel_tool_calls   bool                    | default true
   max_tool_calls        int                     | default null
 STORAGE / CHAINING
   store                 bool                    | default true
   prompt_cache_key      str  (route to same cache; volatile-tail caching)
   previous_response_id  str  — REQUIRES store:true; incompatible with store:false
 TRANSPORT / MISC
   truncation            disabled|auto           | default disabled
   service_tier          default|priority        | default default
   stream                bool                    | default false
   background            bool                    | default false
   include               array  e.g. ["reasoning.encrypted_content"]
   metadata              object (<=16 pairs)
   instructions          str  (system layer, separate from input)
   top_logprobs          int 0..8                | default 0
 ACCEPTED BUT NO-OP ON REASONING MODELS
   frequency_penalty, presence_penalty          (echoed, no effect); "stop" absent from this API
═══════════════════════════════════════════════════════════════════════════════
"""
import json
import os
import time
import urllib.error
import urllib.request

import core_bus as bus


def _build_body(cfg, messages, body_override, response_format):
    """The body is wiring's [request] base, laid over by the caller's [body_override]
    (an organ tuning or a named request profile), with the dynamic fields filled and
    every null-valued key dropped. Null in an override explicitly unsets a base field."""
    body = bus.deep_merge(cfg["request"], body_override or {})
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
    return bus.drop_nulls(body)


def call(messages, cfg, *, body_override=None, response_format=None):
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        raise RuntimeError("xai transport: XAI_API_KEY missing; no fallback was attempted")
    payload = _build_body(cfg, messages, body_override, response_format)
    url = str(cfg["url"])
    timeout = float(cfg["timeout"])
    max_retries = int(cfg["max_retries"])
    base_delay = float(cfg["retry_base_delay"])
    for attempt in range(max_retries):
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                obj = json.loads(resp.read().decode("utf-8", errors="replace"))
            content = obj.get("output_text") or ""
            reasoning = ""
            if not content and isinstance(obj.get("output"), list):
                parts = []
                for item in obj["output"]:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") == "reasoning":
                        reasoning += "\n".join(str(c["text"]) for c in item.get("content", []) or [] if isinstance(c, dict) and c.get("text"))
                    else:
                        parts.extend(str(c["text"]) for c in item.get("content", []) or [] if isinstance(c, dict) and c.get("text"))
                content = "\n".join(parts)
            return {"content": content, "reasoning": reasoning.strip()}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 503 and attempt < max_retries - 1:
                time.sleep(base_delay * (2 ** attempt))
                continue
            raise RuntimeError(f"xai transport HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            if attempt < max_retries - 1:
                time.sleep(base_delay * (2 ** attempt))
                continue
            raise RuntimeError(f"xai transport URL error: {getattr(exc, 'reason', exc)}; no fallback was attempted") from exc
    raise RuntimeError("xai transport exhausted retries")
