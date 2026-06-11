# endgame-ai AGENTS.md — evolution-m4 production map

This document is the operational map for the current productionized evolution-m4 branch. It must be updated whenever the reactor core, UI entry points, schema contracts, or runtime artifacts change.

## Current State vs Production Target

| Area | Current production state | Target now implemented |
| --- | --- | --- |
| Reactor core | `main.py` initializes a shared board and `engine.py` schedules math, observer, planner, actor, verifier, reflector, and mutator agents. | Core scheduling remains unchanged; token telemetry is added as an observational board field and snapshot extension. |
| LLM backend | `llm.py` supports LM Studio structured responses and ACP text-over-JSON-RPC. | `LLMReply` adds estimate-first token telemetry; legacy `call_llm()` still returns text; LM Studio keeps the hardened structured request body and optional preferred-model selection; ACP prompt construction remains text-only. |
| UI | `tui.py` is the launcher/fallback dashboard; `hud.py` is a Win32 layered overlay monitor. | HUD is the primary monitor for runtime/token economics; TUI remains the reliable launcher and recovery UI. |
| Token control | Per-agent output budgets existed, but no input estimates, usage capture, board state, snapshot, or HUD/TUI visibility. | Prompt estimates, effective completion caps, optional LM Studio usage, token events, board `token_state`, snapshot `token_trace`, HUD plots, and TUI status are wired. |
| Truncation policy | Several LLM-facing reductions existed (`history[-MAX_HISTORY:]`, `_render_field(history)[-40:]`, terminal tail, element value clip). | No new truncation is introduced; major LLM-facing truncation paths are removed or made opt-out with `-1` config values. Display-only snapshot/HUD tails remain bounded. |

## File Inventory

- `main.py`: CLI entry point, backend selection, respawn contract, board initialization including `token_state`.
- `engine.py`: scheduler loop, plugin loading, fission, snapshot save, token-state persistence.
- `agents.py`: math agents, scheduler, observer wrapper, planner, actor, verifier, reflector, mutator, context rendering, JSON extraction.
- `llm.py`: LM Studio and ACP dispatch, strict schema loading, `LLMReply`, token estimation/admission, LM Studio usage capture, optional `LMS_PREFERRED_MODEL` model selection.
- `token_state.py`: reducer for cumulative/per-agent token accounting and bounded snapshot traces.
- `hud.py`: Win32/GDI layered topmost overlay, snapshot/event polling, math/Lorenz/token plots, recent-event panel.
- `tui.py`: terminal launcher/fallback dashboard, goal input, pause/resume, event tail, token status line.
- `observer.py`: UIA/window observer. Values and terminal tails are not clipped when the corresponding config limit is `-1`.
- `actions.py`: GUI/headless action execution and self-edit safety checks.
- `log.py`: event envelope writer. Event shape remains `{n,t,phase,d}`.
- `acp_client.py`: ACP/Kiro JSON-RPC client. No token-specific behavior belongs here.
- `schemas/*.json`: strict output contracts for planner, actor, verifier, reflector, and mutator.
- `prompts/*.txt`: mutable role prompts used by self-evolution. Current prompts are deliberately short and schema-first for Gemma4 E2B/small local instruction models.


## LM Studio / Gemma4 E2B Operating Profile

The LM Studio request body must retain the hardened structure: `messages`, `response_format`, `temperature`, `top_p`, `top_k`, `max_tokens`, `stream`, `stop`, penalties, `logit_bias`, `repeat_penalty`, and `seed`. `llm.py` resolves `/v1/models` and chooses the first loaded model unless `config.LMS_PREFERRED_MODEL` is set to an exact or substring match.

Small local models are sensitive to prompt overload. The production prompts therefore use short imperative rules, one role/job per file, explicit JSON shapes, and no long examples. Generation defaults are conservative: low temperature, smaller top-k/top-p, a mild repeat penalty, 128k context admission, and smaller completion budgets. Actor output remains allowed to carry long `value` text because real GUI writing tasks may require it.

## Runtime Data Flow

```text
main.py
  -> board{goal, plan, history, math..., token_state}
  -> engine.run(board)
       -> scheduler/math/observer/LLM agents
       -> llm.call_llm_reply(...) -> LLMReply
       -> log.emit("token_usage" | "token_warning", data)
       -> engine._run_agent consumes last reply and writes board["token_state"]
       -> engine._save writes snapshot.json with token_state/token_trace/token_warnings
  -> hud.py polls snapshot.json + events.jsonl and plots math/token dynamics
  -> tui.py tails events.jsonl and renders fallback dashboard/token status
```

## Token Telemetry and Admission Control

Token control is estimate-first because ACP returns text only and exposes no usage object. LM Studio usage is captured only when the `/v1/chat/completions` response includes a `usage` object. The estimator is intentionally simple and zero-dependency: character and word estimates are both computed, and the larger value is used.

Admission control never drops input context. If prompt estimate plus safety margin leaves too little completion room, `llm.py` emits `token_warning` and raises a clear `RuntimeError`. Agents then follow their existing error path. This is deliberate: failing loudly is safer than silently truncating history, screen, lessons, desktop state, or plan data.

## Truncation Map

| Site | Status | Rationale |
| --- | --- | --- |
| `agents.py` actor history writes | Removed. History is written back whole. | LLM-facing history must not be destructively sliced. |
| `agents.py` `_render_field("history")` | Removed. Full history is rendered. | Token admission replaces hidden context loss. |
| `agents.py` lessons/completed render tails | Removed. Full lessons/completed context is rendered. | Same no-hidden-loss rule. |
| `observer.py` terminal tail | Disabled when `TERMINAL_CONTEXT_TAIL_LINES <= 0`; default is `-1`. | Full terminal context is preserved unless explicitly configured otherwise. |
| `observer.py` screen element value clip | Disabled when `SCREEN_ELEMENT_VALUE_LIMIT <= 0`; default is `-1`. | Full UI values are preserved. |
| `engine.py` `completed[-50:]` | Removed. | Completed milestones remain available for no-repeat checks. |
| `engine.py` snapshot `completed[-10:]`, `math_trace[-12:]`, token trace tail | Display-only bounded projections. | Snapshot/HUD artifacts must stay compact; board state remains authoritative. |

## ACP Compatibility Rules

- Do not change `acp_client.py` for token telemetry.
- Keep `llm._call_acp()` as a plain text prompt containing system text, schema JSON, user context, and “Respond with the JSON object only.”
- Keep top-level schema keys stable.
- Keep `_extract_json()` tolerant of ACP wrapper text.
- Derive token telemetry locally from the exact prompt/context and returned text.

## UI Entry Points

```bash
python hud.py
python tui.py --backend lmstudio --event-budget 20 "goal text"
python tui.py --backend acp --event-budget 20 "goal text"
python main.py --backend lmstudio --event-budget 5 "smoke goal"
python main.py --backend acp --event-budget 5 "ACP smoke goal"
```

HUD is the preferred monitor. TUI remains the preferred launcher and fallback recovery UI until HUD grows first-class input controls.

## Validation Checklist Before Release Tag

```bash
python -m py_compile config.py log.py llm.py token_state.py acp_client.py agents.py engine.py main.py observer.py actions.py tui.py hud.py win32.py debug_context.py tests_validate_schemas.py
python tests_validate_schemas.py
python debug_context.py planner --goal "production smoke"
python m4_merge_test.py
python main.py --backend lmstudio --event-budget 5 "production token telemetry smoke"
python main.py --backend acp --event-budget 5 "production ACP smoke"
python tui.py --backend lmstudio --event-budget 10 "TUI fallback smoke"
python hud.py
```

Windows-specific HUD and UIA behavior must be validated on Windows. LM Studio and ACP/Kiro smoke runs must be validated against the actual local services.
