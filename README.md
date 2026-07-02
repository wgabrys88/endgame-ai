# endgame-ai Session Handover

This README is the current handover prompt and plan for Codex or any other AI provider. Read it first, then update it before every handoff.

## Project Vision

endgame-ai is a living Windows desktop organism. It should perceive the real desktop, form intentions, act through mouse/keyboard/Win32/UIA capabilities, verify outcomes, reflect on failures, and rewrite its own wiring when that improves the organism.

The main branch vision is not a chatbot or a task runner. It is a small, fail-hard organism built from Python files, `wiring.json`, seed nodes, and hot-swappable brain transports. Keep the core lean. Avoid frameworks in the organism loop. No silent transport fallback.

Current branch: `unified-archBRAINZ`.

Current selected transport: `xai` / Grok via xAI API.

Reasoning feedback default: OFF. Two-pass feedback remains configurable, but should be enabled only for explicit comparison/debug runs.

## Ground Rules

- Reduce code and prompt size before adding features.
- Keep observation Windows-native: UIA `ElementFromPoint` hover scan plus Win32 focus/window APIs.
- Do not reintroduce `ControlViewWalker`.
- Keep transports fail-hard. If the selected brain fails, raise and route through organism error/reflect paths.
- Runtime evidence beats speculation: inspect `state.json`, `comms/runtime.ndjson`, and the newest raw `*.txt`.
- Commit coherent chunks regularly.
- Keep this README fresh after every meaningful run or design decision.

## PID Decision

The PID mechanism is useful; the tracked PID file is not.

`stop_check.py` writes `pids/{name}.pid` at runtime and uses those files for emergency termination. The repo does not need a committed `pids/organism.pid` value. This branch now ignores `pids/*.pid` and removes the tracked PID artifact.

## Current Architecture Notes

Observation:

- `desktop.py` loads/regenerates the comtypes UIAutomation wrapper if the Windows typelib changed.
- UIA control/property IDs come from the generated UIA module with numeric fallbacks.
- `INTERACTIVE_CONTROL_TYPES` is defined.
- UIA rectangles are normalized for this environment's `(left, top, width, height)` values.
- Window tokens come from Win32 `EnumWindows`.
- Focus comes from Win32/UIA foreground/focused APIs.
- Actionable elements come from hover scanning with `ElementFromPoint`.

Brain:

- `brain.think()` has one consolidated path for `single_pass`, `native`, and `two_pass`.
- `model.global` config is merged into transport config.
- Reasoning feedback is OFF by default in `wiring.json`.
- Raw model I/O logs are written to timestamped root `*.txt` files.

Nodes/loop:

- Execute namespace exposes `state`, `wiring`, `goal`, `screen`, `elements`, `windows`, `screen_text`, and `focused_title`.
- Execute/verify/reflect/self_modify use structured payloads instead of nested prompt strings.
- Verify advances `state.step` on success.
- Error node routes step failures to reflection.
- `satisfied.py` is a valid terminal node.
- Self-modify patches are applied by `organism.py` and live-node writes are constrained under `live_nodes/`.

## Run Evidence

### Run A: Grok/xAI before contract fixes

Command:

```powershell
& "C:\Users\px-wjt\AppData\Local\Python\bin\python.exe" organism.py --reset --max-ticks 5 "Observe the current desktop and report focused window title plus a few interactive elements"
```

Raw log: `20260702T111459.txt`

Result:

- Transport: `xai`.
- Reached planner -> scheduler -> observe -> execute -> reflect.
- Three model calls: about 21.3s, 29.9s, 29.2s.
- Execute failed with `NameError: name 'windows' is not defined`.
- Grok reflection correctly diagnosed the namespace contract bug: the model was told to use `windows` and `elements`, but the exec namespace did not expose them directly.

Internalized fixes:

- `nodes.build_execute_namespace()` now exposes observation fields directly.
- `seed_nodes/execute.py` sends structured observation context.
- `wiring.json` execute prompt matches the real namespace.

### Run B: LM Studio/OpenAI with two-pass feedback ON

Temporary run config:

- `model.transport = "openai"`
- LM Studio endpoint: `http://localhost:1234/v1/chat/completions`
- Two-pass reasoning feedback ON for `openai`.

Raw log: `20260702T111838.txt`

Result:

- Reached planner -> scheduler -> observe -> execute.
- Two-pass confirmed: planner seq 1/2, execute seq 3/4.
- Model time for planner+execute was about 72.2s.
- Execute returned `record_type="plan"` instead of `execution`.
- Root cause: prompt/payload contamination from duplicate execute instructions and large nested prompt strings.

Internalized fixes:

- `brain.think()` consolidated.
- Execute/verify/reflect/self_modify now pass structured payloads.
- Prompts in `wiring.json` are shorter and schema-focused.
- Reasoning feedback returned to OFF by default.

### Run C: final Grok/xAI verification after fixes

Raw log: `20260702T113237.txt`

Result:

- Transport: `xai`.
- Reasoning feedback: OFF.
- Reached planner -> scheduler -> observe -> execute -> verify.
- Three model calls: about 10.9s, 37.0s, 7.8s.
- Execute succeeded, verify returned `step_confirmed`, and `state.step` advanced to 1.
- `focused_title` was `Task Manager`.
- Window rectangles were correct after UIA rect normalization.
- Actionable elements were 0 for the focused Task Manager view. This is not an execution failure; it is an observation/actionability gap to investigate.

## Current Known Gaps

1. Hover scan can still return zero actionable elements for some Win32-heavy windows such as Task Manager.

   Next work: add better hover sampling around the focused window and inspect whether UIA returns panes/text without actionable control types. Do not tree-walk.

2. The model can still produce code with local truncation patterns, such as `windows[:5]`, inside generated action code.

   Next work: consider adding an execute prompt rule or post-generation lint that rejects unnecessary truncating slices when the task asks for full observation.

3. `reasoning_from()` still contains compatibility handling for the old corrupted marker.

   Next work: keep it if old logs/transports need it; otherwise replace with clean `<think>...</think>` extraction.

4. README and wiring disagree with main branch's old "safe default LM Studio" recommendation because this mission explicitly required switching back to Grok/xAI after both comparison runs.

   Next work: preserve this explicit branch decision unless the user asks to make LM Studio default again.

5. Self-modify is wired through but not deeply validated by a live self-modification run.

   Next work: run a bounded self-modify scenario with `--max-ticks` and inspect whether wiring/live-node changes apply and reload cleanly.

## Next Implementation Plan

1. Run another bounded Grok/xAI verification with a focused app that exposes controls, not Task Manager.

   Goal: prove hover scan returns useful actionable elements when the active window has real UIA controls.

2. Improve observation without tree walking.

   Candidate changes:

   - Add focused-window edge/center sampling in addition to grid sampling.
   - Deduplicate by runtime id, hwnd/rect/name/control type.
   - Preserve Win32 window tokens.
   - Keep `observe_config` as the only knob for scan density.

3. Add expected record type into the brain/node contract.

   Candidate design:

   - Node calls pass `expected_record_type` to `brain.think()`.
   - Default behavior remains fail-hard.
   - Optional one-shot repair can be enabled in `wiring.json`, default OFF.

4. Validate self-modify path.

   Candidate scenario:

   - Force a controlled failure.
   - Route reflect -> self_modify.
   - Confirm `organism.py` applies wiring patch, reloads wiring/live nodes, and logs `self_modify_applied`.

5. Keep commits small.

   Suggested commit boundaries:

   - Observation sampling improvement.
   - Brain expected-record contract.
   - Self-modify validation/fixes.
   - README evidence refresh.

## Fresh Handover Prompt

Use this prompt for a new Codex session or another AI provider:

```text
Read README.md completely. You are continuing endgame-ai on branch unified-archBRAINZ. The project is a living Windows desktop organism, not a chatbot. Keep the core small, fail-hard, and evidence-driven. Current selected transport is xai/Grok, reasoning feedback OFF by default, after completed comparison runs against xai and LM Studio. Do not reintroduce ControlViewWalker. First inspect git status and the newest raw log/state evidence. Then run a bounded organism test only if needed, analyze state.json + comms/runtime.ndjson + newest *.txt, implement the smallest reduction-focused fix, commit it, and rewrite README.md with fresh evidence and the next exact handover plan. PID files are runtime artifacts; do not track pids/*.pid.
```

## Commands

Compile:

```powershell
& "C:\Users\px-wjt\AppData\Local\Python\bin\python.exe" -m compileall -q .
```

Grok/xAI limited run:

```powershell
& "C:\Users\px-wjt\AppData\Local\Python\bin\python.exe" organism.py --reset --max-ticks 5 "Observe the current desktop and report focused window title plus a few interactive elements"
```

LM Studio comparison run:

```powershell
# Temporarily set model.transport to "openai" and enable reasoning for that transport if two-pass feedback is being tested.
& "C:\Users\px-wjt\AppData\Local\Python\bin\python.exe" organism.py --reset --max-ticks 5 "Observe the current desktop and report focused window title plus a few interactive elements"
```
