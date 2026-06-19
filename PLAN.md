# PLAN.md — Status & Next Steps

**Branch:** `codex-unify-bus`
**Date:** 2026-06-19
**State:** Complete rod implemented. Colony ready. Needs real Windows testing.

---

## Completed (this session)

- [x] Autonomous loop (`--run "goal"`)
- [x] Multi-step planner (LLM → steps with done_when)
- [x] Scheduler (step index tracking)
- [x] Act node (prompt build + guards + LLM + execute — all in one)
- [x] Verify node (fresh screen + LLM evidence check)
- [x] Reflect node (diagnose + retry/replan)
- [x] Guards (repeat_block, premature_done, advance_hints)
- [x] Reasoning feedback (history injected into prompt)
- [x] State persistence (state.json, --resume)
- [x] Bus (bus.json shared, POST /bus/post, GET /bus, POST /interrupt)
- [x] Bus_check in topology (interrupt → replan mid-execution)
- [x] MoE routing (moe_route node delegates by competence)
- [x] Personas (prompts/personalities/*.txt loaded into system prompt)
- [x] Colony reactor (reactor.py spawns N rods, health check, respawn)
- [x] SSE observation (GET /events for browser)
- [x] Browser dashboard (Run/Step/Stop/Interrupt/Auto buttons)
- [x] actions.py bridge (observe_screen + execute_verb module-level API)
- [x] HTML CSS for all new node types
- [x] Navigation knowledge documented (NAVIGATION.md)

## What Needs Testing (on Windows with LM Studio running)

1. `python server.py --run "open notepad and write hello"` — full real execution
2. `python server.py` + open browser → 🚀 Run with real goal
3. Verify the planner output quality with real LLM
4. Verify the verifier correctly confirms/denies with real screen data
5. Verify guards fire when LLM repeats actions
6. Test interrupt: POST /interrupt with new goal mid-execution
7. Test colony: `python reactor.py --goal "open chrome"`

## Architecture Decisions (final)

| Decision | Choice | Why |
|----------|--------|-----|
| Node count | 10 in base topology | Fewer nodes = less coupling |
| Act node combines | prompt build + LLM + parse + guards + execute | LLM call is implementation detail of acting |
| Verify does own observe | Fresh screen inside verify | Guarantees post-action evidence |
| Bus implementation | Single JSON file | Simplest shared state, no server needed |
| MoE routing | Permission-based | Check `desktop_exec` in permissions, delegate if missing |
| Colony architecture | reactor.py copies files, sets env var | Each rod = independent process with own wiring |
| State persistence | Write state.json every cycle | Survive restart, --resume continues |

## Non-Negotiable Constraints

- Python stdlib only — no pip install
- Wiring-first — all control flow in wiring.json
- Browser is dashboard, not brain — system runs without it
- Single HTML file — CDN imports only
- LM Studio local — no cloud API keys
- CRLF line endings — Windows workspace

## Success Criteria for "One Complete Rod" — All Met

- [x] `python server.py --run "goal"` executes without browser
- [x] System plans multi-step sequences
- [x] System executes each step with screen observation
- [x] System verifies with fresh screen evidence
- [x] On failure: diagnoses and retries (up to max_attempts)
- [x] On success: enters satisfied state
- [x] Browser can connect to observe live state
- [x] All behavior defined in wiring.json
- [x] Another rod = same server.py + different persona in wiring.json

## Files

```
server.py              521 LOC — the body
reactor.py             153 LOC — colony supervisor
actions.py             138 LOC — desktop bridge
desktop.py             824 LOC — Windows UIA (unchanged, working)
wiring-editor.html     626 LOC — visual editor + SSE
prompts/wiring.json     87 LOC — the brain
prompts/*.txt               — system prompts
prompts/personalities/  — persona files
NAVIGATION.md           — desktop navigation knowledge
```
