# grok_build_api.py - REFERENCE ONLY (non-functional)

"""
This file is kept as a reference for the xAI Responses API integration with grok-build-0.1 model.
It is NOT functional in its current state - it references undefined variables and brain internals.

For a working xAI Responses API transport, see:
- seed_brains/xai_responses.py (current xAI Responses API transport)
- Future: consolidate into a single xai_responses.py with model selection

The xAI API endpoint for grok-build-0.1:
  POST https://api.x.ai/v1/responses
  Headers: Authorization: Bearer $XAI_API_KEY, Content-Type: application/json
  Body: {"model": "grok-build-0.1", "input": [{"role": "user", "content": "..."}]}

Reference implementation (pseudocode):
"""
# import json
# import os
# import urllib.request
# 
# 
# def call(messages, cfg):
#     api_key = os.environ.get("XAI_API_KEY") or cfg.get("api_key")
#     if not api_key:
#         raise RuntimeError("xai_responses/grok_build_api: XAI_API_KEY missing")
#     
#     url = "https://api.x.ai/v1/responses"
#     # Convert messages to input format
#     input_data = []
#     for m in messages:
#         role = m.get("role", "user")
#         content = m.get("content", "")
#         if role == "system":
#             input_data.append({"role": "system", "content": content})
#         elif role == "user":
#             input_data.append({"role": "user", "content": content})
#         elif role == "assistant":
#             input_data.append({"role": "assistant", "content": content})
#     
#     payload = {
#         "model": cfg.get("model", "grok-build-0.1"),
#         "input": input_data,
#         "temperature": cfg.get("temperature", 0.2),
#     }
#     
#     req = urllib.request.Request(
#         url,
#         data=json.dumps(payload).encode("utf-8"),
#         headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
#         method="POST"
#     )
#     
#     with urllib.request.urlopen(req, timeout=cfg.get("timeout", 120)) as resp:
#         body = resp.read().decode("utf-8", errors="replace")
#     
#     obj = json.loads(body)
#     # Extract output_text or content from responses
#     content = obj.get("output_text") or ""
#     if not content and isinstance(obj.get("output"), list):
#         for item in obj["output"]:
#             if isinstance(item, dict) and item.get("type") == "message":
#                 for c in item.get("content", []) or []:
#                     if isinstance(c, dict) and c.get("type") == "output_text":
#                         content = c.get("text", "")
#                         break
#     
#     return {"content": content, "reasoning": "", "body": obj}