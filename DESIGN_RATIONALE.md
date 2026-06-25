# Design Rationale

## Why Colony Mode Solves Blocking

Slot 1 can keep its actual project state local and linear: plan, act, verify, and continue. When it needs stronger reasoning, it writes `comms/llm_request.json` with the exact prompt and waits for `comms/llm_response.json`.

Slot 2 is a separate always-running ROD loop. It can spend many cycles focusing the browser, submitting the prompt, waiting for streaming to finish, extracting the response, and recovering from UI drift without blocking or corrupting Slot 1's project plan.

## Reliable Browser Chat Control

The relay wiring keeps browser control declarative:

- `llm_request_check` claims only pending request files.
- `relay_planner` always creates the same relay shape: focus chat, submit exact prompt, wait for completion, remember `llm_response`.
- `relay_act` is the only circuit with SCREEN and is constrained to visible `[ID]` targets.
- Act rules reject writing to address/search/url/location targets.
- Capture rules reject prompt echoes, questions, short captures, and captures while streaming/loading markers remain visible.
- `llm_response_write` atomically writes the final response file and archives the request.

## True Self-Referential Loop

The agent controls the same browser chat it uses as a stronger brain. Slot 1 asks for high-level reasoning through a file request. Slot 2 pushes that request into the web model, waits for the answer, and returns it to Slot 1 memory. Slot 1 then uses `MEMORY.llm_response` to continue the original task.

This is closed loop: Endgame-AI drives the external model UI, consumes the result, and can use that result to improve Endgame-AI itself.

## Failure Modes Considered

- Wrong field: address/search-bar writes are rejected before execution.
- Streaming not complete: capture is rejected if stop/generating/loading markers remain.
- Prompt echo captured: verifier denies memory that matches the prior write or looks like a question.
- UI focus drift: planner/act focus browser chat first and retry from fresh observations.
- File races: state, bus, request, and response writes use atomic replace.
- Relay prompt drift: `REQUEST_PROMPT` is preserved exactly and overrides stale history.
- Repeated UI failure: `self_modify` can add rules, tune observe settings, or append role guidance in `wiring_relay.json`.

## Scaling To Long Autonomous Builds

The handoff is file-based, inspectable, and restartable. Slot 1 can issue multiple intelligence requests over a long project; Slot 2 processes one pending request at a time and returns to polling. More relay slots can be added later by giving each slot a distinct request path or queue convention while keeping the same ROD graph.
