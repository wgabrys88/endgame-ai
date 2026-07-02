# endgame-ai Handover Prompt

Use this file as the first context block for any future Codex session or other AI provider. Keep it current after every run and commit. The goal is to make a new session productive without relying on hidden chat history.

## Mission

endgame-ai is a Windows desktop automation organism. It observes the desktop with UIA `ElementFromPoint` hover scanning plus Win32 window/focus APIs, then uses a hot-swappable brain transport to plan, execute, verify, reflect, and self-modify.

Primary target: make the system reliable and fast for Grok/xAI while preserving local LM Studio/OpenAI-compatible testing.

Hard constraints:

- Prefer reduction over feature growth.
- Keep observation Windows-native: hover scan plus Win32. Do not reintroduce `ControlViewWalker`.
- Keep 2-call reasoning feedback supported, but OFF by default.
- Avoid prompt/context string truncation. Bound data at observation/config level instead.
- Keep transports fail-hard. Do not silently fall back to another model.
- Commit coherent chunks regularly.

## Current State

Current selected transport in `wiring.json`: `xai`.

Reasoning feedback default: OFF.

Two-pass reasoning remains configurable under each transport:

- `model.global.reasoning_enabled`
- `model.transport_config.<transport>.reasoning.enabled`
- `model.transport_config.<transport>.reasoning.pattern`

Recent commits:

- `e80453f` - `Fix Windows hover observation runtime`
- `ac98c4e` - `Reduce brain and node runtime contracts`

Runtime files are generated and should not be treated as source unless explicitly needed:

- `state.json`
- `comms/runtime.ndjson`
- root timestamp raw logs like `20260702T111459.txt`
- `live_nodes/`
- `live_brains/`
- `pids/organism.pid`

## Evidence From Runs

### Run 1: current transport, Grok/xAI

Command:

```powershell
& "C:\Users\px-wjt\AppData\Local\Python\bin\python.exe" organism.py --reset --max-ticks 5 "Observe the current desktop and report focused window title plus a few interactive elements"
```

Raw log: `20260702T111459.txt`

Outcome:

- Completed 5 ticks with transport `xai`.
- Nodes reached: planner -> scheduler -> observe -> execute -> reflect.
- Model calls: 3 single calls.
- Call latencies were about 21.3s, 29.9s, 29.2s.
- Observation worked after UIA import fix and produced focused title `Task Manager`, Win32 window tokens, and actionable elements.
- Execute failed with `NameError: name 'windows' is not defined`.
- Grok reflection diagnosed the real contract bug: generated code was told to use `windows` and `elements`, but the exec namespace exposed only `state`.

Internalized changes from Grok feedback:

- `nodes.build_execute_namespace()` now exposes `screen`, `elements`, `windows`, `screen_text`, and `focused_title` directly.
- `seed_nodes/execute.py` now sends structured observation payloads instead of a nested prompt string.
- The execute prompt in `wiring.json` now explicitly matches the actual namespace.

### Run 2: LM Studio/OpenAI transport with two-pass feedback ON

Temporary config used for this run:

- `model.transport = "openai"`
- OpenAI-compatible base URL: `http://localhost:1234/v1/chat/completions`
- Two-pass reasoning enabled for the run.

Raw log: `20260702T111838.txt`

Outcome:

- Completed planner, scheduler, observe, then errored in execute.
- Two-pass feedback was confirmed: planner used seq 1/2, execute used seq 3/4.
- Total model time for planner+execute was about 72.2s.
- Execute returned `record_type="plan"` instead of `record_type="execution"` in both feedback passes.
- Root cause: prompt/payload contamination. Execute had an execute system prompt plus a second large execute prompt embedded inside JSON, and LM Studio repeated the planner-shaped response.

Internalized changes from LM Studio feedback:

- `brain.think()` now uses one consolidated path for `single_pass`, `native`, and `two_pass`.
- `seed_nodes/execute.py`, `verify.py`, `reflect.py`, and `self_modify.py` now pass structured payloads under one system prompt.
- `wiring.json` prompts are shorter and schema-focused.
- Reasoning feedback is OFF by default for speed, but still configurable.

## Implemented Architecture Changes

Observation:

- `desktop.py` regenerates stale comtypes UIAutomation wrappers when the Windows typelib changes.
- UIA control/property IDs now come from the generated UIA module with numeric fallbacks.
- `INTERACTIVE_CONTROL_TYPES` is defined.
- UIA rectangle normalization handles this environment's `(left, top, width, height)` values.
- Active window/window list comes from Win32 `GetForegroundWindow` and `EnumWindows`.
- Active element discovery stays hover-scan based through `ElementFromPoint`.
- `ControlViewWalker` was removed from active observation.

Brain:

- `think()` now uses one consolidated implementation.
- Reasoning feedback is governed by effective transport config.
- `model.global` config is now merged into transport config.
- Brain call budgeting checks global config too.

Nodes/loop:

- Execute namespace now matches the model contract.
- Execute/verify/reflect/self_modify payloads are structured and no longer manually truncated.
- `satisfied.py` is now a valid node.
- Planner default signal is now `step_ready`, not an invalid signal.
- Verify advances `state.step` on success.
- Error node routes step failures to reflection.
- Self-modify patches are now actually applied by `organism.py`.
- Self-modify node file writes are constrained to configured `live_nodes/`.

## Known Issues To Fix Next

1. Run the updated Grok/xAI path again and compare against `20260702T111459.txt`.

Expected improvement:

- Execute should no longer fail on undefined `windows` or `elements`.
- Raw prompt size should be smaller.
- Reasoning feedback should be absent unless explicitly enabled.

2. Validate the observation after rectangle normalization.

Expected improvement:

- `snapshot.active_window.rect.right` should be greater than `left`.
- Target-window hover scan should probe the focused window instead of falling back to whole screen.
- More focused-window elements should appear when the active app exposes UIA controls.

3. Consider adding model contract repair at the brain chokepoint.

Potential design:

- Node calls should pass `expected_record_type` into `brain.think()`.
- If the model returns a different record type, optionally do one cheap repair call only when configured.
- Default should remain fail-hard and fast.

4. Finish removing legacy reasoning marker handling if not needed.

Current status:

- Old strategy classes are removed.
- The legacy `reasoning_from()` marker still exists for compatibility.
- Add clean `<think>...</think>` extraction only if a real transport emits it.

5. Re-run LM Studio with two-pass feedback only after Grok path is stable.

Purpose:

- Confirm structured execute payload prevents the previous `record_type="plan"` failure.
- Compare latency and request sizes against `20260702T111838.txt`.

6. Decide whether generated runtime files should be ignored or documented.

Current repo already tracks `pids/organism.pid`, which changes during runs and creates noise.

## Recommended Next Session Prompt

Start with this exact prompt:

```text
Read README.md completely. Continue the endgame-ai reliability/speed mission from the current git state. First inspect git status and the latest commits. Do not reintroduce ControlViewWalker. Run the limited organism with current xai transport and --reset, analyze state.json, comms/runtime.ndjson, and the latest raw log. Compare against the run evidence recorded in README.md. Then implement the smallest reduction-focused fixes needed, commit each coherent chunk, update README.md with fresh evidence and the next handover plan, and leave wiring.json on xai with reasoning feedback OFF by default unless a run explicitly requires otherwise.
```

## Validation Commands

Compile:

```powershell
& "C:\Users\px-wjt\AppData\Local\Python\bin\python.exe" -m compileall -q .
```

Limited Grok/xAI run:

```powershell
& "C:\Users\px-wjt\AppData\Local\Python\bin\python.exe" organism.py --reset --max-ticks 5 "Observe the current desktop and report focused window title plus a few interactive elements"
```

Limited LM Studio run:

```powershell
# Temporarily set wiring.json model.transport to "openai" and enable reasoning for the openai transport.
& "C:\Users\px-wjt\AppData\Local\Python\bin\python.exe" organism.py --reset --max-ticks 5 "Observe the current desktop and report focused window title plus a few interactive elements"
```
