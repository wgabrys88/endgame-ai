# Phase 3 Run Log — browser_ai Transport Implementation

**Date**: 2026-06-26
**Branch**: runtime-optimization
**Objective**: Implement browser_ai transport in server.py so the system can use grok.com as its LLM brain via GUI automation.

---

## Meta-MoE Observations

### Architecture Assessment Before Starting

The system now has:
- 12 confirm-only rules (accelerators, no blockers)
- Fresh SCREEN observation in verifier
- Proven pipeline: open_url → click → write → press → remember → satisfied

**What browser_ai transport needs to do:**
1. Receive (system_prompt, user_message) from any node (planner/act/verifier/reflector)
2. Navigate to grok.com (or confirm it's already open)
3. Format the prompt as a single text block and type it into chat
4. Press Enter, wait for response
5. Read the response text from SCREEN observation
6. Return (content, reasoning_content, raw) tuple

**Efficiency concern**: The current pipeline calls LLM 2x per node (pass A reasoning + pass B decision). With browser_ai, each call means typing into grok.com and waiting. This doubles the browser interactions. For Phase 3, this is acceptable as proof. Optimization (single-pass mode) is Phase 4.

**Risk**: Grok.com may have long responses that overflow the observation window. The desktop.py observation may truncate. Need to handle partial reads.

---

## Implementation Log


### 19:47 — browser_ai Transport Implemented

Code added:
- `llm_via_browser_ai(system, user)` — 60 lines
- Reads `model.browser_ai` config for browser, url, input_hint, wait_ms, max_len
- Sequence: focus → click input → ctrl+a → write prompt → enter → wait → read screen
- Extracts response by parsing `Text "..." = "..."` lines from screen observation
- Falls back to element 1 if input_hint not found in elements

**MoE Assessment**: The implementation is minimal and correct for a proof. However:
- The prompt formatting (`[SYSTEM]...[USER]...[RESPOND WITH JSON ONLY]`) puts full system prompt + user message in ONE chat message. This may confuse Grok or hit character limits.
- The response extraction is fragile — parsing screen text lines. If Grok's response spans multiple Text elements, only the first match is captured.
- The 15s wait is fixed. Should be adaptive (poll until "Thinking" disappears).
- These are all Phase 4 optimizations. For proof, this is sufficient.

### 19:47 — Testing browser_ai Live

Switching transport to browser_ai, posting a SIMPLE goal first (not the full grok pipeline — just testing if the transport can call grok and get a response back).

