# AGENTS.md — AI session handover (endgame-ai)

**Read this first** if you are Codex, Cursor, Grok, or any AI continuing work on this repo.

| Doc | Purpose |
|-----|---------|
| `AGENTS.md` | **You** — rules, state, next steps, test procedure |
| `KNOWLEDGE.md` | Protocol and architecture reference (cite when editing comms/engine) |
| `README.md` | Human quick start only — do not duplicate here |

**Branch:** `grok-dev` · tip `afe87ac` (GUI guard + human cap + MoE yield + token diet)  
**Milestone:** Colony Alpha ~78% — infra live-tested; human→verifiable-action retest pending  
**Merge:** `unify-rewrite` is the likely integration target later; `main` is a parallel lineage — do not assume parent/child

---

## What this project is

Five parallel **slots** (OS processes). Each slot runs one **persona** with an internal agent pipeline. Coordination is **blackboard-only** (`comms.py`). Routing is **MoE softmax** on pressure telemetry (`engine._moe_route`). One LLM at a time for Nemotron (`LLM_MAX_CONCURRENT=1`).

**Core insight:** The LLM is a subroutine inside a deterministic Python loop. Math (pressure, priority, MoE) runs every cycle regardless of LLM state.

**Vision (papers):** Blackboard (CAS 2025) + Pressure fields (Rodriguez 2026) + MoE gating (Bause 2026) + Orchestrator pattern + AgentBreeder scaffold (Oxford 2026, ~5% wired). Full vision text lives in Grok memory / local `vision/` — not in git.

---

## Process tree

```
python tui.py --model-profile nemotron
  └── reactor.py
        ├── main.py [s1 comms_operator]  — MoE router, never reassigned
        ├── main.py [s2 architect]
        ├── main.py [s3 implementor]
        ├── main.py [s4 reviewer]
        └── main.py [s5 devops]
```

Slot 1 is fixed. Slots 2–5 can be **reassigned** via `control.jsonl` on MoE escalation (`quality_critic` is default escalation target).

---

## Priority interrupt

| pri | Name | Source |
|-----|------|--------|
| 3 | HUMAN | `@persona` in TUI → `inject.jsonl` |
| 2 | CRITICAL | `moe.escalate` + `post_control(reassign)` |
| 1 | NORMAL | `kind=route` from comms_operator |
| 0 | MAINTENANCE | Default; workers sleep until inbox |

Workers wake on inbox kinds: `route`, `request`, `ping` (`comms.pending_for()`).

---

## Pipeline (per persona)

```
scheduler → planner → actor → verifier → fission_judge
```

| Stage | LLM? | Notes |
|-------|------|-------|
| scheduler | No | Workers return `None` if no inbox and pri≤0 |
| planner | Yes | JSON plan; nemotron thinking via `extract_json()` |
| actor | No | `run_python()` with `colony_env` sandbox; GUI blocked |
| verifier | Yes | Posts `kind=verdict` |
| fission_judge | Partial | Deterministic +1 today |

comms_operator: `_moe_route()` every 20s — **no LLM**. Yields maintenance when `comms.human_task_active()`.

---

## Blackboard v1 (`comms.py`)

Schema: `schemas/bus_v1.json`

| Store | Path | Role |
|-------|------|------|
| Intent | `runtime/comms/messages.json` | chat, route, request |
| Observation | `runtime/comms/events_bus.jsonl` | telemetry, mirrored events |
| Control | `runtime/comms/control.jsonl` | reactor `reassign` (drain every 5s) |
| Inject | `runtime/comms/inject.jsonl` | human/TUI input |

Envelope: `v, id, ts, from, slot, kind, pri, text, payload`

Key kinds: `message`, `ping`, `request`, `route`, `telemetry`, `event`, `evolve` (reserved), `verdict`, `status`

MoE APIs: `colony_state()`, `softmax_route()`, `route()`, `post_control()`, `post_telemetry()`, `human_task_active()`

Full kind table and payloads: `KNOWLEDGE.md`

---

## Session logs — what must appear (vision)

Per-slot JSONL under `sessions/<timestamp>/events-child-sN.jsonl`.

| Phase | Slot | Required for vision? | Notes |
|-------|------|---------------------|-------|
| `moe.route` | s1 | **Yes** | ~every 20s; proves Bause MoE closed loop |
| `pressure` | all | **Yes** | ~every 10 cycles; Rodriguez stagnation/power |
| `interrupt` | target | **Yes** | Human pri=3 wake |
| `plan` / `actor` / `verify` / `fission` | worker | **Yes** | Pipeline proof |
| `moe.yield` | s1 | **Yes** | MoE paused during human task (`afe87ac`+) |
| `plugin.web_sentinel` | all | **No** | Session noise only; skipped on bus |

**Debugging:** Session JSONL is verbose by design. Bus (`events_bus.jsonl`) is leaner — plugins and `schedule` are filtered. See log tiers in `KNOWLEDGE.md`.

---

## Pressure + MoE (implementation map)

| Concern | File | Symbol |
|---------|------|--------|
| Stagnation math | `engine.py` | `_update_pressure()` |
| MoE cycle | `engine.py` | `_moe_route()` |
| Human yield | `engine.py` + `comms.py` | `human_task_active()` |
| Telemetry | `plugins/comms_beacon.py` | → `post_telemetry()` |
| Softmax gate | `comms.py` | `softmax_route(powers)` — `exp(power*3)` |
| Reassign | `reactor.py` | `drain_control()` → `reassign()` |
| GUI guard | `python_code.py` | `validate_python()`, `goal_needs_gui()` |
| Thresholds | `config.py` | `STAG_ESCALATE=0.7`, `VEL_STUCK=0.01`, `STUCK_TICKS_ESCALATE=5` |

**Stuck:** `stag >= 0.7` AND `|velocity| <= 0.01` for 5 consecutive MoE cycles → escalate + swap slot persona.

**Critical fix (do not regress):** `reactor.is_alive()` uses `OpenProcess(0x1000)` — wrong mask `0x00100000` caused false 5s respawn loop.

---

## Research pillars → code (honest scores)

| Pillar | Score | Status |
|--------|-------|--------|
| Blackboard (CAS 2025) | ~88% | v1 envelope live; human on bus |
| Orchestrator pattern | ~80% | idle workers, 1 LLM gate, human yield |
| Pressure fields (Rodriguez 2026) | ~65% | core math; escalation wired |
| MoE (Bause 2026) | ~75% | closed loop + yield on human |
| AgentBreeder (Oxford 2026) | ~5% | `evolve` reserved; mutator/reflector not in pipeline |

---

## Hard rules

1. **Never create new `.py` files** — edit existing modules only
2. **No env vars for runtime colony config** — CLI args and `config.py` only (`.env` for LMS hosts is OK)
3. **Personas coordinate via bus only** — no shared mutable state between processes
4. **Do not add markdown files to the repo** — only `README.md`, `KNOWLEDGE.md`, `AGENTS.md`
5. **Test on `grok-dev`** before claiming stability fixes
6. Every Python change must pass `python -m py_compile <file>`
7. **No GUI agent** — never launch desktop apps; file I/O + bus only

---

## Live test results (2026-06-13, session `20260613_164412`)

### Infrastructure PASS
- 5 slots stable >8 min, 0 false respawn
- 40+ `moe.route` on s1
- Human `@devops` → `interrupt` pri=3 on s5 (~2s)
- MoE escalation fired (reviewer/architect → quality_critic)
- Bus plugin spam fixed (`plugin.*` not on `events_bus`)

### Behavior FAIL (fixed in `afe87ac`)
- GUI task (`open notepad`) → actor spawned Notepad, 60s timeouts, orphan windows
- Planner ignored GUI limitation; deny→replan loop
- Architect `planner.error` ~8k tokens (nemotron budget too high) — budget reduced
- MoE kept routing maintenance during human task — now `moe.yield`

### Retest criteria (next session)
1. `@devops open notepad` → instant decline, **zero** Notepad, `human.decline` or bus "not supported"
2. `@implementor create hello.txt with hello world` → interrupt → actor → `verify: confirmed`

---

## What works (verified)

- 5 slots without false respawn (`is_alive` fix)
- Structured `kind=telemetry` on blackboard
- `_moe_route` posts `kind=route` every 20s; yields on human task
- Escalation: `moe.escalate` → `post_control` → reactor `MOE REASSIGN`
- Human `@mention` → pri=3 wake + preemption
- GUI guard + human retry cap (3 denials)
- TUI: 5/5 slots, session JSONL per slot
- Plugin hot-swap; `web_sentinel` session-only

## Not built yet (do not claim done)

- `kind=evolve` writer (AgentBreeder loop)
- reflector / mutator in live pipeline (schemas + prompts exist)
- LLM fission_judge (deterministic +1 only)
- GUI / desktop observer agent (port from `main` when requested)
- Long-run breeding / MAP-Elites fitness

---

## Test procedure (run after changes)

**Before start**

- [ ] `git checkout grok-dev && git pull`
- [ ] LM Studio + nemotron, or `--backend acp`
- [ ] No stale tui/reactor/notepad processes
- [ ] `runtime/comms/` empty or fresh (TUI wipes on start)

**Launch**

```bash
python tui.py --model-profile nemotron
```

- [ ] TUI 45 lines; header `5/5 slots`
- [ ] Slots alive > 30s
- [ ] s1: `moe.route` ~every 20s; `pressure` ~every 20s
- [ ] `python comms.py state` — telemetry per persona
- [ ] Human GUI test: decline, no desktop spawn
- [ ] Human file test: `@implementor` → confirmed fission

**Smoke:** `python run_test.py 120`

---

## Suggested next work (priority order)

1. **Retest** human file task on `grok-dev` after `afe87ac`
2. Wire **reflector** after verifier failure
3. Wire **mutator** + `kind=evolve` for AgentBreeder scaffold
4. Optional: throttle `plugin.web_sentinel` further (vision does not require it)
5. MAP-Elites fitness from fission + stagnation history
6. Merge `grok-dev` → `unify-rewrite` when human decides

---

## File traceability

| Component | Files |
|-----------|-------|
| MoE gate | `engine.py`, `comms.py` |
| Pressure | `engine.py`, `plugins/comms_beacon.py` |
| Human cap / GUI | `agents.py`, `python_code.py`, `actions.py` |
| Reactor | `reactor.py` |
| Orchestrator scheduler | `agents.py` |
| TUI | `tui.py` |
| Config | `config.py` |
| Prompts | `prompts/planner.txt`, `prompts/personalities/*.txt` |
| Schemas | `schemas/bus_v1.json`, `route.json`, `telemetry.json`, `planner.json` |

---

## Session history (grok-dev)

| Commit | Summary |
|--------|---------|
| `afe87ac` | GUI guard, human cap, MoE yield, token diet |
| `2bac993` | Harden sandbox + human preemption |
| `894e72c` | MoE closed loop + docs |
| `6906eac` | Blackboard protocol v1 |
| `ad4e70f` | False respawn fix + orchestrator + Nemotron |

---

## External session memory (not in git)

Grok project memory: `C:\Users\ewojgab\.grok\memory\endgame-ai-3448e172\`  
Live test report: `sessions/2026-06-13-live-test-report.md` (in memory, not git)

---

## Branches reference

| Branch | Notes |
|--------|-------|
| `grok-dev` | **Work here** |
| `unify-rewrite` | Rewrite base; merge target TBD |
| `main` | refactor-v4 organism M4; parallel species |

`main` and `grok-dev` are **parallel species**, not linear history.