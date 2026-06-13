# AGENTS.md — AI session handover (endgame-ai)

**Read this first** if you are Codex, Cursor, Grok, or any AI continuing work on this repo.

| Doc | Purpose |
|-----|---------|
| `AGENTS.md` | **You** — rules, state, next steps, test procedure |
| `KNOWLEDGE.md` | Protocol and architecture reference (cite when editing comms/engine) |
| `README.md` | Human quick start only — do not duplicate here |

**Branch:** `grok-dev` · tip `894e72c` (MoE closed loop + blackboard docs)  
**Milestone:** Colony Alpha ~72% — ready for human live test, not AgentBreeder-complete  
**Merge:** `unify-rewrite` is the likely integration target later; `main` is a parallel lineage — do not assume parent/child

---

## What this project is

Five parallel **slots** (OS processes). Each slot runs one **persona** with an internal agent pipeline. Coordination is **blackboard-only** (`comms.py`). Routing is **MoE softmax** on pressure telemetry (`engine._moe_route`). One LLM at a time for Nemotron (`LLM_MAX_CONCURRENT=1`).

**Core insight:** The LLM is a subroutine inside a deterministic Python loop. Math (pressure, priority, MoE) runs every cycle regardless of LLM state.

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
| actor | No | `run_python()` with `colony_env` sandbox |
| verifier | Yes | Posts `kind=verdict` |
| fission_judge | Partial | Deterministic +1 today |

comms_operator: `_moe_route()` every 20s — **no LLM**. Planner only when `pri >= 3` (human interrupt).

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

MoE APIs: `colony_state()`, `softmax_route()`, `route()`, `post_control()`, `post_telemetry()`

Full kind table and payloads: `KNOWLEDGE.md`

---

## Pressure + MoE (implementation map)

| Concern | File | Symbol |
|---------|------|--------|
| Stagnation math | `engine.py` | `_update_pressure()` |
| MoE cycle | `engine.py` | `_moe_route()` |
| Telemetry | `plugins/comms_beacon.py` | → `post_telemetry()` |
| Softmax gate | `comms.py` | `softmax_route(powers)` — `exp(power*3)` |
| Reassign | `reactor.py` | `drain_control()` → `reassign()` |
| Thresholds | `config.py` | `STAG_ESCALATE=0.7`, `VEL_STUCK=0.01`, `STUCK_TICKS_ESCALATE=5` |

**Stuck:** `stag >= 0.7` AND `|velocity| <= 0.01` for 5 consecutive MoE cycles → escalate + swap slot persona.

**Critical fix (do not regress):** `reactor.is_alive()` uses `OpenProcess(0x1000)` — wrong mask `0x00100000` caused false 5s respawn loop.

---

## Research pillars → code (honest scores)

| Pillar | Score | Status |
|--------|-------|--------|
| Blackboard (CAS 2025) | ~85% | v1 envelope live |
| Orchestrator pattern | ~75% | idle workers, 1 LLM gate |
| Pressure fields (Rodriguez 2026) | ~60% | core math; escalation wired |
| MoE (Bause 2026) | ~70% | closed loop on grok-dev |
| AgentBreeder (Oxford 2026) | ~5% | `evolve` reserved; mutator/reflector not in pipeline |

---

## Hard rules

1. **Never create new `.py` files** — edit existing modules only
2. **No env vars for runtime colony config** — CLI args and `config.py` only (`.env` for LMS hosts is OK)
3. **Personas coordinate via bus only** — no shared mutable state between processes
4. **Do not add markdown files to the repo** — only `README.md`, `KNOWLEDGE.md`, `AGENTS.md`
5. **Test on `grok-dev`** before claiming stability fixes
6. Every Python change must pass `python -m py_compile <file>`

---

## What works (verified in code, pending full human test)

- 5 slots without false respawn (`is_alive` fix)
- Structured `kind=telemetry` on blackboard
- `_moe_route` posts `kind=route` every 20s to highest-power worker
- Escalation path: `moe.escalate` → `post_control` → reactor `MOE REASSIGN`
- Human `@mention` → pri=3 wake
- TUI: session slot reset, sync output, CHAT/EVENTS panels
- Plugin hot-swap by mtime in `engine._run_plugins()`

---

## Post live-test fixes (`894e72c`+)

- `colony_env.py` — forgiving `bus_post` / `bus_id` / `bus_route` shims
- `engine._run_plugins` — apply plugin `writes` (30s throttle works)
- `plugins/telemetry.py` — disabled (use comms_beacon)
- Human preemption — `_apply_human_goal` + stronger `_check_interrupt`
- `comms.format_bus_context` — human first, cap route spam
- `tui.py` — staggered slot scan (5/5 display)

## Not built yet (do not claim done)

- `kind=evolve` writer (AgentBreeder loop)
- reflector / mutator in live pipeline (schemas + prompts exist)
- LLM fission_judge (deterministic +1 only)
- `quality_critic` as default slot (available via escalation reassign)
- Long-run breeding / MAP-Elites fitness
- Desktop observer port from `main` lineage

---

## Test procedure (run after changes)

**Before start**

- [ ] `git checkout grok-dev`
- [ ] LM Studio + nemotron, or `--backend acp`
- [ ] No stale tui/reactor processes

**Launch**

```bash
python tui.py --model-profile nemotron
```

- [ ] TUI 45 lines, no flicker; header `5/5 slots` (not 10/5)
- [ ] Slots alive > 30s — no restart every 5s
- [ ] Session JSONL: one `start` per slot, not 10+
- [ ] Workers idle until ~20s then `moe.route` on s1
- [ ] `python comms.py state` — `pwr`, `stag`, `vel`, `slot` per persona
- [ ] `@implementor read config.py` — wakes s3, pri=3

**Pass (minimum):** stable slots, idle workers, one `moe.route`/20s, structured telemetry.

**Pass (full):** escalation reassigns stuck slot to `quality_critic`, human interrupt works, TUI clean.

**Smoke:** `python run_test.py 120`

---

## File traceability

| Component | Files |
|-----------|-------|
| MoE gate | `engine.py`, `comms.py` |
| Pressure | `engine.py`, `plugins/comms_beacon.py` |
| Reactor | `reactor.py` |
| Orchestrator scheduler | `agents.py` |
| TUI | `tui.py` |
| Config | `config.py` |
| Prompts | `prompts/planner.txt`, `prompts/personalities/*.txt` |
| Schemas | `schemas/bus_v1.json`, `route.json`, `telemetry.json`, `planner.json` |

---

## Suggested next work (priority order)

1. Human live test on `grok-dev`; fix regressions from test
2. Wire **reflector** after verifier failure (plugin or pipeline stage)
3. Wire **mutator** + `kind=evolve` for AgentBreeder scaffold
4. MAP-Elites fitness from fission + stagnation history
5. Port desktop observer patterns from `main` when user requests
6. Merge `grok-dev` → `unify-rewrite` when user decides (not yet)

---

## Session history (grok-dev)

| Commit | Summary |
|--------|---------|
| `894e72c` | MoE closed loop + docs |
| `6906eac` | Blackboard protocol v1 |
| `ad4e70f` | False respawn fix + orchestrator + Nemotron |
| `4bbf8c9` | TUI stability |

Consolidated from deleted `fix/tui-stability` and `fix/orchestrator-nemotron`.

---

## External session memory (not in git)

Grok project memory index:

```
C:\Users\ewojgab\.grok\memory\endgame-ai-3448e172\
```

Session interval notes and vision context live there. Do not commit handover/checklist/vision markdown into the repo.

---

## Branches reference

| Branch | Notes |
|--------|-------|
| `grok-dev` | **Work here** |
| `unify-rewrite` | Rewrite base; merge target TBD |
| `main` | refactor-v4 organism M4; self-rewrite proven; different architecture |

`main` and `grok-dev` are **parallel species**, not linear history.