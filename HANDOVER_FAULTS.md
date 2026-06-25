# Endgame-AI Fault Handover

Date: 2026-06-25

This document records current logic, behavior, and methodology faults discovered during the relay and YouTube playback work. Treat it as a handover artifact for the next implementation pass.

## Current Truth

- Endgame-AI is currently running with `transport: file_proxy`.
- LM Studio is not the active cognition backend in these tests.
- Codex/GPT is acting as the external LLM by reading Endgame-AI request JSON files and writing matching response JSON files.
- Endgame-AI still performs observe and act through its own runtime when it reaches desktop steps.
- Shell is being used for server/API control, validation, file inspection, and file-proxy responses.
- Shell is not valid proof of browser or desktop control.
- A real browser relay proof has not completed.
- A real YouTube playback proof has not completed.

## How Codex Is The LLM In This System

In file-proxy mode, Endgame-AI writes requests such as:

- `comms/slot1_cognition/request.json`
- `comms/relay_cognition/request.json`

The coding agent reads those request files and writes responses such as:

- `comms/slot1_cognition/response.json`
- `comms/relay_cognition/response.json`

The response must preserve the exact request `id`. Endgame-AI then consumes the response as the LLM output for the active graph circuit.

This means Codex/GPT is currently the model backend for planner, act, verifier, and reflector circuits. Endgame-AI is not independently reasoning through LM Studio during these file-proxy tests. The system loop is still real because Endgame-AI owns the state machine, observes the Windows desktop, dispatches actions, records outcomes, verifies, reflects, and advances the graph.

## Copy-Paste Prompt For Any Coding-Agent Provider

Use this prompt with Claude Code, Grok Build, OpenCode, Kiro CLI, Codex, or any other coding agent when Endgame-AI is running in file-proxy mode and needs that agent to act as the LLM backend:

```text
You are the external cognition backend for Endgame-AI, a local Windows desktop ROD graph operator. You are not chatting with the user directly for normal task work. You are servicing Endgame-AI's file-proxy LLM queues so Endgame-AI can think through you while it keeps ownership of state, observation, action, verification, and recovery.

Treat the repository and runtime files as authoritative. Do not rely on stale chat memory. The current working directory is the Endgame-AI repository.

Core rule:
- Endgame-AI controls the desktop/browser through its own observe/act runtime paths.
- You may use shell for repository inspection, local API calls, validation, and writing file-proxy responses.
- You must not manually automate the browser or desktop outside Endgame-AI when a desktop-control proof is being claimed.

Active cognition contract:
- Slot 1 cognition request: comms/slot1_cognition/request.json
- Slot 1 cognition response: comms/slot1_cognition/response.json
- Slot 2 relay cognition request: comms/relay_cognition/request.json
- Slot 2 relay cognition response: comms/relay_cognition/response.json
- Browser relay handoff request: comms/llm_proxy/request.json
- Browser relay handoff response: comms/llm_proxy/response.json

You are replacing LM Studio for this run by acting as the file-proxy model backend. Do not claim LM Studio is active unless the model config says transport=openai and the local OpenAI-compatible server is actually being used.

Loop:
1. Inspect /system, /health, /state, and the relevant request file.
2. Read the request JSON.
3. Preserve the exact request id in the response JSON.
4. If the request user content does not contain "DECIDE NOW", write concise reasoning in content and reasoning_content.
5. If the request user content contains "DECIDE NOW", write exactly the JSON object required by that circuit role in content.
6. For planner, output record_type "task" with ordered steps.
7. For act, output record_type "action" with declarative verbs only: click, write, press, hotkey, focus, scroll, wait, remember, llm_request, llm_wait_response.
8. For verifier, output record_type "verdict".
9. For reflector, output record_type "diagnosis".
10. For self_modify, output record_type "wiring_patch" only when a bounded wiring change is actually needed.

Important behavior:
- Do not invent visible UI targets.
- For click/write/scroll, use only observed [ID] targets or visible action-scope text.
- Address/search/url/location bars may be used for URL navigation, not for chat prompt submission.
- Never claim a browser relay capture while streaming/loading/thinking is visible.
- Reject prompt echoes, stale captures, short captures, question-only captures, title-only captures, and URL-only captures.
- If Endgame-AI fails an action, diagnose honestly and either retry with stronger evidence or document the blocker.
- A task is not proven until Endgame-AI action history and final state prove it.

Response shape:
{
  "id": "<same request id>",
  "content": "<role JSON object as a string, or reasoning text for non-final reasoning pass>",
  "reasoning_content": "<short reasoning>"
}

Use UTF-8 without BOM. Do not leave mismatched response IDs. Do not write browser relay responses by hand during a browser proof; Slot 2 should write comms/llm_proxy/response.json after real capture.
```

This is the "AI-as-LM-backend" trick in precise terms: Endgame-AI is configured to use a file-proxy model transport, and a stronger coding agent supplies the model responses through files. It should not be described as fooling the system into using LM Studio. It is a deliberate alternate transport that lets Endgame-AI think through any agent capable of reading requests, preserving IDs, and writing valid circuit responses.

## Methodology Faults

- The earlier Grok relay proof remained active while the next benchmark request arrived.
- The correct response was to stop stale slot processes and clear stale proxy queues before starting the new benchmark.
- `/slots/status` was attempted but does not exist; current status must be read through `/system`, `/health`, per-slot `/state`, and slot start/stop responses.
- Parallel status checks can race with slot startup and produce confusing status snapshots.
- Manual file-proxy responses are necessary in the current setup, but they can hide the difference between model failure and graph/action failure.
- The coding agent must not manually drive Chrome or YouTube outside Endgame-AI when a desktop-control proof is being claimed.
- A benchmark is not proven by planning, queueing, or observing a window; it is proven only by Endgame-AI action history and final visible state.
- Temporary helper scripts should not be used for this project unless promoted into the system deliberately.

## Logic Faults

- Observation and action focus are not a coherent contract yet.
- The observe output listed `YouTube - Google Chrome` in `WINDOWS`.
- The act circuit chose `focus Chrome`.
- `actions.py` delegated that to `Desktop.focus_window("Chrome")`.
- The action returned `FAILED: window 'Chrome' not found`.
- This means the window list exposed to the LLM can contain a browser title that the focus implementation cannot subsequently resolve.
- The prompt says "focus with window title substring", but the runtime failed on the substring `Chrome`.
- The next implementation pass should make observed `WINDOWS` entries actionable or expose a dedicated focus target ID/handle.
- A broad title target such as `Chrome` is too weak for the current dispatcher.
- The system needs a reliable primitive for "focus an observed top-level window".
- The system needs a reliable primitive for "open URL in the browser", separate from chat prompt submission rules.
- The graph currently depends too much on the external LLM choosing the right fallback after a primitive failure.
- The verifier correctly rejected non-OK outcomes, but the act layer did not have a robust fallback strategy built into the action primitive.
- The planner can produce a reasonable YouTube task plan, but capability is limited by focus/navigation/action robustness.

## YouTube Playback Benchmark Status

Requested benchmark:

`play Shakira Waka Waka on YouTube`

Actual fresh run state:

- Stale Grok relay slots were stopped.
- Stale Slot 1 cognition request was cleared.
- Stale browser relay handoff was cleared.
- Slot 1 was started from the real root server.
- The YouTube playback goal was posted to Slot 1.
- Slot 1 planner produced a five-step plan:
  - focus or open Google Chrome
  - navigate to `https://www.youtube.com`
  - search for `Shakira Waka Waka`
  - open a relevant video result
  - start playback and verify the video page
- Slot 1 observed the real desktop.
- The observation showed Task Manager focused and `YouTube - Google Chrome` in the window list.
- The first action response was `focus Chrome`.
- Endgame-AI executed that action through its own dispatcher.
- The action failed with `FAILED: window 'Chrome' not found`.
- The run did not reach YouTube navigation, search, result selection, playback, or verification.

This is a real failed benchmark, not a completed proof.

## Behavioral Faults Exposed By The Benchmark

- Basic browser focus is not reliable enough.
- A visible browser in the observed `WINDOWS` list is not enough evidence that the action layer can activate it.
- Taskbar visibility did not translate into a safe focus method because the current rules discourage taskbar clicking for browser navigation.
- The system has no provider-independent "play this on YouTube" workflow primitive.
- The system has no robust media playback verifier.
- The system has no audio-state verifier.
- The system has no player-state verifier.
- The system has no YouTube result-selection policy beyond whatever the LLM chooses from the observed screen.
- The system does not yet record enough compact evidence for a user-facing "music is playing" claim.

## Required Fixes Before Claiming This Benchmark Works

- Fix focus so every observed top-level `WINDOWS` entry can be focused deterministically.
- Prefer focus by captured HWND or internal window handle over fuzzy title text.
- If handle focus is not exposed to the LLM, expose stable focus targets in action scope.
- Add or wire a browser-open/navigate primitive that can open a URL without relying on fragile focus state.
- Preserve the rule that prompt/chat text must not be typed into address bars, while still allowing URL navigation.
- Add a YouTube-specific or generic media playback verification rule.
- Capture evidence after playback: focused title, page title/content, player state, and possibly volume/audio state.
- Add a negative result path for ads, login prompts, cookie popups, and region/provider blocks.
- Update prompts so broad `focus Chrome` is avoided when exact observed titles are available.
- Add regression tests for focus resolution from observed window list to action dispatch.

## Required Proof Before Deployment

- Start root from real `server.py`.
- Start Slot 1 through the root slot manager.
- Use file-proxy cognition or a real model backend, but state which one is active.
- Post the benchmark as a real Slot 1 goal.
- Let Endgame-AI observe the desktop.
- Let Endgame-AI focus or open Chrome.
- Let Endgame-AI navigate to YouTube.
- Let Endgame-AI search for `Shakira Waka Waka`.
- Let Endgame-AI select a relevant result.
- Let Endgame-AI start playback.
- Capture `/state` and `state.slot1.json` showing action history and final evidence.
- Do not claim success unless the final visible state is a YouTube video page for Shakira Waka Waka and playback is started or explicitly ready to play.

## Handover Instruction

The next implementation pass should treat the Shakira YouTube task as a core benchmark. It is a better benchmark than it looks because it tests the whole practical desktop-control stack: stale-run cleanup, model/file-proxy cognition, window focus, URL navigation, site search, result selection, media start, verification, and honest failure reporting.
