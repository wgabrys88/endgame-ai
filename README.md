# endgame-ai

A **human operator in digital form** on Windows 11 — wiring harness, not chat agent. Python is the body. Desktop is the world. `wiring.json` is the nervous system. Git is firmware memory.

**Tags:** `ooo-unification` (spec) · `arch-flat-root` (flat refactor) · **`first-live-loop`** (first Grok-backed multi-tick run)

---

## Breakthrough (2026-07-04)

First **live organism loop** on a real Windows desktop with Grok API:

| Proof | Evidence |
|-------|----------|
| Self-narrating goal works | Planner emitted `goal_narration` + 2-step `intent[]` from fresh observation + `body_signals` (battery 96%, AC, 85GB free) |
| Observation is deep | **3071 chars** hierarchical tree — Task Manager, Chrome/YouTube, grok IDE, 11 windows, GRID |
| Topology executes | planner → scheduler → observe → execute in **4 ticks** without human steering |
| Brain + body coupling | Execute returned `FRAME` (honest “need framing”) — topology routed to `frame_action` |
| Raw audit trail | `comms/brain_raw.jsonl` — full think payloads + API request/response bodies (keys redacted) |

Run stopped at tick 4: `--max-brain-calls 2` exhausted (planner + execute); `frame_action` needed call #3. **Not a architecture failure — a budget cap.**

---

## First run log (archived in README; runtime cleaned)

**Goal:** `survey desktop and note open applications`

| Tick | Node | Signal | Brain | Notes |
|------|------|--------|-------|-------|
| 0 | planner | step_ready | 8.0s | `goal_narration` rewritten; intent: catalog windows + record focus |
| 1 | scheduler | step_ready | — | Step 0: extract window titles from observation |
| 2 | observe | screen_ready | — | 212 elements, focus Task Manager, 3071-char tree |
| 3 | execute | frame | 6.3s | Conclusion FRAME (no code); routed to frame_action |
| 4 | frame_action | — | **budget** | `brain call budget exceeded: 2/2` |

**Planner narration (excerpt):** *Survey desktop noting open applications; Task Manager focused amid visible windows including Chrome/YouTube, grok terminal…*

---

## Progress

| Phase | Status | Notes |
|-------|--------|-------|
| 0–8 | **done** | Flat root, registry, evolution, inline xai, wiring v2, contract_check |
| 9 fail-hard | **partial** | Planner/execute/reflect hard errors; budget error recovery TBD |
| 10 request limits | **done** | `limits` + preflight + observation cap |
| 11 self-narrating goal | **done** | `body_signals.py`; planner requires `goal_narration` + `intent[]` |
| 12 stdout visibility | **done** | `[organism]`/`[observe]`/`[brain]` on every long step |
| 13 raw comms log | **done** | `comms/brain_raw.jsonl` — think, api_request, api_response_body |
| 14 next live loop | **planned** | `--max-brain-calls 6`; complete frame → verify → scheduler |

---

## Plan (aligned to first results)

```mermaid
gantt
    title Next work after first-live-loop
    dateFormat YYYY-MM-DD
    section Immediate
    Full survey loop max_brain_calls 6     :a1, 2026-07-04, 1d
    Budget-aware routing or default bump   :a2, after a1, 1d
    section Hardening
    Error node resume after budget error   :b1, after a2, 2d
    Fail-hard phase 9 complete             :b2, after b1, 1d
    section Evolution
    Self_modify live patch test            :c1, after b2, 3d
```

| Priority | Task | Why |
|----------|------|-----|
| P0 | Re-run survey with `--max-brain-calls 6 --max-ticks 8` | Finish frame_action → verify path |
| P1 | Default `max_brain_calls` in wiring or per-run guidance | Prevent false “hang” at FRAME |
| P2 | Budget error → reflect instead of hard stop | Graceful degradation |
| P3 | Self-modify tick on real defect | Git firmware path proof |

---

## Architecture

```mermaid
flowchart LR
    subgraph body [Body - stdlib ctypes]
        desktop[desktop.observe]
        signals[body_signals]
        exec[execute.exec]
    end
    subgraph harness [Wiring harness]
        organism[organism._tick]
        registry[registry.NODE_REGISTRY]
        bus[bus.NodeOutput]
    end
    subgraph brain [Brain peripheral]
        think[brain.think]
        xai[xai API inline]
    end
    subgraph comms [Runtime comms - gitignored]
        raw[comms/brain_raw.jsonl]
        rt[comms/runtime.ndjson]
        obs[comms/observations/]
    end
    organism --> registry --> bus
    registry --> think --> xai
    think --> raw
    organism --> rt
    desktop --> think
    signals --> registry
    exec --> body
```

### Topology

```mermaid
stateDiagram-v2
    [*] --> planner : cycle_start
    planner --> scheduler : step_ready
    planner --> reflect : reflect
    scheduler --> observe : step_ready
    scheduler --> satisfied : plan_complete
    observe --> execute : screen_ready
    execute --> verify : verify
    execute --> frame_action : frame
    execute --> reflect : reflect
    execute --> self_modify : self_modify
    verify --> scheduler : step_confirmed
    verify --> reflect : step_denied
    reflect --> observe : retry
    reflect --> planner : replan
    reflect --> self_modify : escalate
    reflect --> satisfied : give_up
    self_modify --> planner : modified
    frame_action --> execute : framed
    satisfied --> [*] : halt
    error --> planner : recovery
    error --> reflect : recovery
```

### First run actual path

```mermaid
sequenceDiagram
    participant O as organism
    participant P as planner
    participant S as scheduler
    participant Ob as observe
    participant E as execute
    participant F as frame_action
    participant B as brain/xai

    O->>P: tick 0
    P->>B: think plan (8s)
    B-->>P: goal_narration + intent
    P-->>O: step_ready
    O->>S: tick 1
    S-->>O: step_ready
    O->>Ob: tick 2
    Ob-->>O: screen_ready 3071 chars
    O->>E: tick 3
    E->>B: think execution (6s)
    B-->>E: FRAME
    E-->>O: frame
    O->>F: tick 4
    F-xB: budget exceeded 2/2
```

---

## Agent operator protocol (how the human’s AI partner works)

When running endgame-ai on behalf of the operator:

1. **Never silent long runs** — organism prints `[organism]`/`[observe]`/`[brain]`; agent does not background without telling the operator.
2. **Raw logs on disk** — every brain call writes to `comms/brain_raw.jsonl` (payloads + API bodies; secrets redacted). Runtime events in `comms/runtime.ndjson`. Observations in `comms/observations/`.
3. **Sport commentary every ~30s** — agent runs `python comms_poll.py 30 N` or reads those files and reports: current node, tick, phase, last signal, narration excerpt, observation size, last brain phase, errors.
4. **No secrets in git** — never commit `comms/`, `state.json`, API keys, or raw logs with credentials.
5. **Cleanup after archival** — once results are captured in README, delete runtime artifacts; commit code + README only.
6. **Ask permission** before the next live loop (API cost + desktop control).

```mermaid
flowchart TD
    A[Operator requests run] --> B[Agent starts organism in foreground or bg with notice]
    B --> C[Poll comms every 30s]
    C --> D{New event?}
    D -->|yes| E[Commentary: node signal narration obs brain]
    D -->|no| F[Report still scanning or waiting on API]
    E --> C
    F --> C
    C --> G{Run ended?}
    G -->|no| C
    G -->|yes| H[Read logs archive to README cleanup commit tag ask permission]
```

---

## Prompt engineering (KV cache + capabilities)

**System (cacheable):** `ORGAN_CORE` + `ORGAN_IDENTITY[organ]` + short `wiring.prompts[organ]`

**User JSON (dynamic tail):** `goal_seed`, `goal_narration`, `goal_signals`, state… then `fresh_observation` last.

- Execute prompt declares **unsandboxed** full Python/subprocess/ctypes
- No giant JSON schema in prompts — `json_object` + `record_type` check
- `limits.max_request_chars` fail-hard before API

---

## Self-narrating goal

| Field | Role |
|-------|------|
| `goal_seed` | Immutable user intent |
| `goal_narration` | Planner-maintained living interpretation (required every planner tick) |
| `goal_signals` | `body_signals.collect()` — power, disk, urgency |

---

## CLI

```bash
python organism.py "survey desktop" --max-ticks 8 --max-brain-calls 6 --reset
python organism.py --execute-node observe ""
python comms_poll.py 30 12
python contract_check.py
```

`comms/` and `state.json` are runtime-only (gitignored). `stop.txt` aborts.

---

## Comms layout (runtime)

| Path | Content |
|------|---------|
| `comms/brain_raw.jsonl` | think, api_request, api_response_body, response |
| `comms/runtime.ndjson` | organism_start, node_start, node_complete, error |
| `comms/observations/*.json` | Full hover scan artifacts |
| `comms/control.json` | run / pause / step |
| `state.json` | Live state patch |

---

## Validation

```bash
python -m compileall -q .
python -m json.tool wiring.json
python contract_check.py
```

---

## License

MIT — see `LICENSE`.