# Design Rationale

## Why Slot Separation Matters

Slot 1 owns the user's real goal. It plans, observes, acts, verifies, and keeps project MEMORY local to its graph.

Slot 2 is a dedicated browser relay. It can spend many cycles focusing a browser chat, submitting a prompt, waiting for streaming to finish, extracting the latest assistant answer, and recovering from UI drift without corrupting Slot 1's plan.

The queues are split by purpose:

- Slot 1/root cognition proxy: `comms/slot1_cognition/`
- Slot 2 cognition proxy: `comms/relay_cognition/`
- Browser relay handoff: `comms/llm_proxy/`

This prevents a file-proxy model request from being mistaken for a browser relay request, and prevents the relay response path from blocking the model transport.

## Reliable Browser Chat Control

Browser control remains declarative:

- `llm_request_check` claims only pending browser-relay requests.
- `relay_planner` creates a browser-chat relay plan from the exact request prompt.
- `relay_act` is the only relay circuit with SCREEN.
- Desktop actions use visible `[ID]` action-scope targets; `WINDOWS` and `DESKTOP_TREE` are context only.
- Act rules reject writing relay prompts to address/search/url/location targets.
- Capture rules reject prompt echoes, questions, short captures, stale captures, URL/title-only captures, and captures while streaming/loading markers are visible.
- `llm_response_write` atomically writes the relay response and archives the completed request.

## True Self-Referential Loop

The same local system that needs help controls the browser model it uses as external intelligence:

1. Slot 1 writes a browser-relay request.
2. Slot 2 uses the real desktop/browser environment to submit that request to a web model.
3. Slot 2 captures the answer and writes it back.
4. Slot 1 reads it into `MEMORY.llm_response` and continues.

Slot 1 does not need to know whether a response came from LM Studio, a coding agent file proxy, or a browser AI relay. It only sees its configured cognition result or MEMORY.

## Failure Modes Considered

- Wrong target: chat prompt writes to browser address/search/url/location fields are rejected.
- Streaming not complete: capture is rejected while generating/loading markers remain.
- Prompt echo captured: verifier denies memory that matches prior submitted prompt text.
- Weak capture: questions, titles, URLs, and too-short captures are denied.
- UI focus drift: observe includes hover scan, action scope, desktop tree, overlays, and window list.
- File races: state, bus, request, response, and archive writes use atomic replace.
- Queue collision: Slot 1 cognition, Slot 2 cognition, and browser relay handoff now use separate paths.

## Scaling To Long Work

The graph is inspectable and restartable. Long runs can interleave local model reasoning, coding-agent file proxy reasoning, browser AI relay reasoning, desktop actions, and self-modifying wiring patches. The system should still report actual evidence and limitations rather than claiming capabilities not proven by the current runtime.
