# endgame-ai — Session Handover / Bootstrap Prompt

**Version:** 2.0 | **Date:** 2026-06-20 | **Branch:** `experiment/endgame` | **Repo:** https://github.com/wgabrys88/endgame-ai

Paste this entire file into a new AI coding session. Zero prior context assumed.

---

## Mission

Build **endgame-ai** — a task-agnostic Windows desktop agent that cannot see the screen or click directly. It **writes Python, executes it, reads stdout, reasons, acts, verifies, reflects, replans**. Goal is **artificial persistence** on a local 4B-class model, not open-ended reasoning.

**ROD loop:** Read → Orient → Decide → Act → Verify → Reflect.

You (the AI) must use the same loop to develop this repo: small steps, verify every change, expect failure, diagnose from observations.

---

## Current State (proven)

| Layer | Status |
|-------|--------|
| Graph engine | `server.py` — 12 topology nodes, SSE, hot-reload wiring/nodes |
| Brain | `prompts/wiring.json` — topology + prompts + guards + limits |
| Desktop | `desktop.py` — Windows UIA hover-probe, scroll enrich, element IDs |
| Actions | `actions.py` — verb dispatch; fixed resolver (no digit-stripping bug) |
| Simulation | `simulation.py` + `ENDGAME_SIM=1` |
| Colony | `colony.py` — multi-slot via `ENDGAME_SLOT` / `ENDGAME_PERMISSIONS` |
| Tests | `test_server.py` 26/26 · `test_llm_live.py` 3/3 · `test_desktop_live.py` 2/2 · `test_colony_delegate.py` PASS |

**Live desktop proven:** cold-start → `open notepad` (11 cycles) and `open notepad and type hello` (16 cycles) with real UIA + LLM at `prompts/model.json`.

---

## Architecture

```
goal_inbox → moe_route → planner → scheduler → bus_check → observe → act → verify
                ↓ delegated → bus_post → satisfied
                reflect → retry | replan | escalate → self_modify
```

- **LLM nodes (4 only):** planner, act, verify, reflect (+ self_modify on escalate)
- **Everything else:** deterministic Python; behavior changes via `wiring.json`, not code
- **Slot:** one `server.py` instance, port `9077 + slot`
- **Colony:** N slots, shared `bus.json` (runtime, gitignored)

---

## Essential Files

| File | Role |
|------|------|
| `server.py` | HTTP + graph engine + node handlers |
| `desktop.py` | UIA observer |
| `actions.py` | click/write/press/hotkey/focus/scroll |
| `simulation.py` | Deterministic fake desktop |
| `colony.py` | Spawn multi-slot colony |
| `prompts/wiring.json` | **THE BRAIN** |
| `prompts/model.json` | LLM endpoint |
| `wiring-editor.html` | Live topology editor |
| `test_*.py` | Mock, live LLM, live desktop, colony tests |

---

## First Commands (mandatory onboarding)

```powershell
cd <repo>
$env:PYTHONIOENCODING="utf-8"
python test_server.py              # 26/26 — no LLM needed
python test_llm_live.py            # skips if LLM down
python test_desktop_live.py        # real UIA + LLM (Windows only)
python server.py                   # → http://localhost:9078 (slot 1)
python colony.py --sim 1 2         # multi-slot simulation
```

Smoke: `curl http://127.0.0.1:9078/smoke` → 6/6

---

## Development Rules

1. **ROD every turn:** Read files → Orient → one micro-step → Act → Verify → Reflect
2. **Max 1–2 file edits** or one test run per step
3. **Never claim done** without test output in the same turn
4. **Prefer wiring.json** over Python for behavior changes
5. **Self-critique every ~5 steps:** What worked? What assumption was wrong? What's the precise next action?
6. **Continue autonomously** unless user says pause/new goal

---

## Known Fixes (do not regress)

- `_trigger_rod_run` uses `http_port(slot)` not `colony_port`
- Element resolver: only `[ID]` numeric targets, not digits stripped from names
- `PRIOR_TRACES` only on replan (`replan_count > 0`)
- Verify preflight denies `FAILED:` / `BLOCKED` outcomes before LLM
- `node_satisfied`: false on `plan_failed`, true only when `step >= len(plan)`

---

## Next Priorities

| P | Task | Verify |
|---|------|--------|
| 1 | YouTube/browser goal via `server.run()` on real desktop | multi-step satisfied |
| 2 | Colony: slot 2 delegates → slot 1 executes goal end-to-end | bus + slot1 state |
| 3 | Align `rod_test.py` with `server.run()` topology | same goal, fewer ad-hoc prompts |
| 4 | Probe density / wait-for loading in verify | fewer false CANNOT on sparse screens |

---

## Environment

| Var | Effect |
|-----|--------|
| `ENDGAME_SIM=1` | Use `simulation.py` desktop |
| `ENDGAME_SLOT=N` | Override instance slot / port |
| `ENDGAME_PERMISSIONS=desktop_exec` | MoE self-route vs delegate |
| `PYTHONIOENCODING=utf-8` | Required on Windows |

---

## Session Start Checklist

- [ ] `git checkout experiment/endgame`
- [ ] `python test_server.py` → 26/26
- [ ] Read `server.py` graph engine (`run`, `call_node`, node handlers)
- [ ] Read `prompts/wiring.json` topology + roles
- [ ] Pick one P1 task; document state dict; execute first micro-step with verification

**The topology is waiting. Persistence starts with one verified micro-step.**