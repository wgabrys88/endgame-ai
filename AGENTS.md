# Breeding Reactor — Agent Technical Map

**Breakthrough (2026-06-12):** Six autonomous agents + external AI (@grok) coordinated over a JSON message bus. Real desktop outcomes: Notepad matrix-escape text, GitHub in browser, Opera at LinkedIn feed. Documented in `EXECUTION_REPORT.md`. Forensic tooling: `forensic_collect.py`.

**Current focus (2026-06-13):** Harden the full 6-slot colony on Nemotron, make it event-driven via the message bus, and prepare the codebase for handover to any AI coding assistant.

---

## Entry point

```bash
python tui.py
```

Starts **paused** (math-only). **Space** = toggle LIVE. **q** = kill process tree (keeps logs on disk). **Do not restart** if you need session evidence — boot calls `cleanup_runtime()` and wipes runtime.

---

## Branches

| Branch | Role |
|--------|------|
| `reactor-personalities` | Human + merged agent work |
| `colony/dev` | Agent-autonomous target (`git_expert` pushes here) |
| `main` | Stable single-agent release — **not active dev** |

---

## Process tree

```
tui.py → reactor.py → main.py ×6
```

Shared working directory. Reactor sets `ENDGAME_PERSONALITY` + `ENDGAME_SLOT` per child. Only `git_expert` does git ops.

---

## Core files

| File | Role |
|------|------|
| `tui.py` | Spectrogram TUI, bus CHAT/EVENTS, inject drain, pause toggle |
| `reactor.py` | Breeder: 6 slots, LM host probe, load-balance, respawn |
| `main.py` | Single fuel rod: args, engine loop, personality env |
| `engine.py` | Scheduler chain, plugin hot-swap, desktop refresh before planner |
| `agents.py` | planner, actor, verifier, fission_judge, reflector, mutator, math |
| `actions.py` | GUI verbs + `run_python` subprocess runner |
| `desktop.py` | `observe_screen`, `desktop_*` helpers |
| `colony_env.py` | `BASE_DIR`, `COMMS_DIR`, `bus_post`, `bus_id`, `bus_request` |
| `comms.py` | Message bus: chat, requests, inject drain, inbox in planner context |
| `python_code.py` | Planner Python syntax validation |
| `config.py` | Paths, math, LMS hosts, bus caps, rolling log limits, model profiles |
| `llm.py` | LM Studio API, schema enforcement, host failover, model-profile switching |
| `log.py` | JSONL events, `cleanup_runtime`, pause gate, rolling trim |
| `observer.py` | UIA desktop scan → element book `[n]` ids |
| `win32.py` | ctypes user32, SendInput, VK map |
| `forensic_collect.py` | Zip session evidence + write `FORENSIC_ANALYSIS.md` |

---

## Personalities (`prompts/personalities/`)

| Slot | File | Identity |
|------|------|----------|
| n1 | `git_expert.txt` | Commits/pushes `reactor-personalities` / `colony/dev` |
| n2 | `implementor.txt` | Writes `plugins/*.py` |
| n3 | `doc_inspector.txt` | `runtime/comms/report.md` from logs |
| n4 | `comms_operator.txt` | Bus mirror, beacons, coordination — **must not run desktop_*** |
| n5 | `quality_critic.txt` | `py_compile` → `quality.json` |
| n6 | `gui_operator.txt` | Sole GUI specialist (@GUI) — `desktop_*` only |

Reflector can append `EVOLVE:` lines to personality files.

---

## Planner → actor path

1. Planner LLM → `sequence[].code` (plain Python).
2. Actor runs full sequence via `actions.run_python()` with `colony_env` + `desktop` imports.
3. Verifier checks LAST_RESULT vs `done_when`.
4. FissionJudge approves or blocks fission credit.
5. Fission on approval.

**GUI rule:** First line of every GUI step must be `book, _, _ = observe_screen(print_screen=False)`. Never use bare `book`.

---

## Message bus

| Path | Content |
|------|---------|
| `runtime/comms/messages.json` | Peer chat/beacon — retained (`BUS_CHAT_MAX` 120) |
| `runtime/comms/events_bus.jsonl` | Work events for TUI (rolling 200 lines) |
| `runtime/comms/inject.jsonl` | External posts drained by engine/TUI |

**Peers:** `@Human` (operator + alert sound), `@grok` (external AI), `@GUI` / n6, `@n1`–`@n6`, `@colony` broadcast.

```bash
python comms.py post grok "@colony @GUI task details"
python comms.py post human "@grok status"
```

**Delegation:** `bus_request(bus_id(), "gui_operator", "task")` — inbox shown as ** PING FOR YOU ** in planner context.

**Task files:** `runtime/comms/gui_request*.txt` bridge external intent → colony Python (demo-proven pattern).

---

## Matrix escape sessions (2026-06-12)

### Session 1 — Notepad (~18:30 UTC)

- @grok posted @GUI, wrote `gui_request.txt`, ran desktop scripts.
- Visible: Notepad text `Grok escaped the matrix via endgame-ai bus.`
- **n4 comms_operator** executed GUI (role leak); **n6** looped on `NameError: book`.
- Events trimmed from rolling logs — proof in `EXECUTION_REPORT.md`.

### Session 2 — Opera / LinkedIn (~19:07–19:27 UTC)

- @Human bus: lost browser, wants LinkedIn matrix post.
- @grok: inject + `gui_request_opera_linkedin.txt` + `grok_opera_linkedin.py`.
- Opera launched, LinkedIn feed navigated, `linkedin_post_draft.txt` saved.
- n6 eventually fissioned on Opera UIA tree; compose/post left for human review.
- Colony gently paused via `pause` file; `q` preserves logs; **restart purges all**.

---

## Pause vs quit vs restart

| Action | Processes | Session data |
|--------|-----------|----------------|
| `pause` file / Space | Idle, alive | **Preserved** |
| `q` | taskkill tree | **Preserved** on disk |
| `python tui.py` boot | Fresh spawn | **`cleanup_runtime()` WIPES** events, snapshot, entire `runtime/` |

Before reboot: `python forensic_collect.py` → `forensic_matrix_escape_*.zip`.

---

## Runtime (gitignored)

Per-agent: `events-child-n*.jsonl` (rolling **2000 lines** — oldest drop). Board: `snapshot.json`.

`runtime/comms/`: messages, events_bus, inject, report, quality, gui_request files, telemetry.

**Never commit runtime.** `.gitignore` enforces this. Preserve locally for forensics.

---

## Scheduler priorities

1. No plan → reflect if stuck, else cooldown after reject, else planner.
2. Plan complete → verifier.
3. Reflect gate (PID/stag/chaos) → reflector.
4. Wing cross → replan.
5. Active step → actor.

Plan reject: 10s cooldown (`PLAN_REJECT_COOLDOWN_SEC`).

---

## LM Studio

- `ENDGAME_LMS_HOSTS` — comma-separated candidates.
- `LMS_MAX_SLOTS_PER_HOST` = 3 (spawn-time cap only; LM Studio handles its own request queue).
- `LMS_PREFERRED_MODEL` = `gemma` (override: `ENDGAME_LMS_MODEL`).
- `LMS_TIMEOUT` = `None` (no client-side timeout; LM Studio may queue jobs for many minutes).

### Model profiles (`config.MODEL_PROFILES`)

Applied automatically when a model is resolved. Add new models here without touching the default path.

| Profile | Key trigger | Notable overrides |
|---------|-------------|-------------------|
| `gemma` | default | temperature 0.60, budgets ~1K tokens |
| `nemotron` | model id contains `nemotron` | temperature 1.0, top_k 20, budgets 4K–8K tokens |

---

## Key constants

| Constant | Value |
|----------|-------|
| REACTOR_SLOTS | 6 |
| EVENT_ROLLING_MAX_LINES | 2000 |
| BUS_CHAT_MAX | 120 |
| BUS_EVENTS_MAX_LINES | 200 |
| MATH_INTERVAL | 5.0s |
| PLAN_REJECT_COOLDOWN_SEC | 10 |

---

## Known issues (post-demo)

1. **Rolling log cap** — early session proof evicted from `events-child-*.jsonl`. *(Mitigated: raised to 2000 + archive_logs plugin.)*
2. **Role leak** — n4 ran `desktop_*`; n6 should be sole GUI hands. *(Mitigated: `is_gui_operator()` enforced in `desktop.py`, `actions.py`, `engine.py`, `agents.py`.)*
3. **Gemma planner** — `NameError: book`, syntax errors, wrong window titles. *(Mitigated: observe-first rule, exact titles in prompts.)*
4. **Permissive verifier** — fission credited for observing TUI/PowerShell, not goal text. *(Mitigated: tightened verifier prompt.)*
5. **@mention spacing** — `@grok` must be followed by space; `@grokproceed` fails. *(Fixed in `comms.py`.)*

---

## Handover checklist — for Claude Code / Kiro / Grok Build / any AI coding assistant

This section is the single source of truth for the current state of `reactor-personalities` and what to do next.

### Proven (do not break)

- [ ] `python tui.py` boots the 6-slot colony paused; Space goes live; `q` kills cleanly.
- [ ] `python test_reactor.py [seconds] --model=nemotron` runs 2 test agents and reports.
- [ ] `python test_reactor_collab.py [seconds] --model=nemotron` runs 3 collaborative agents.
- [ ] `python test_reactor_full.py [seconds] --model=nemotron` runs the full 6-slot roster.
- [ ] Model profiles auto-switch generation parameters when a model is resolved.
- [ ] `is_gui_operator()` blocks non-n6 agents from emitting `desktop_*` code.
- [ ] `@mention` regex requires a word boundary after the handle.
- [ ] `engine.py` plan validation only resets plans with invalid/missing active steps.
- [ ] `LMS_TIMEOUT = None` — the client never aborts LM Studio; the server queues requests.
- [ ] Git ops are restricted to `git_expert`; runtime artifacts are gitignored.
- [ ] Personality prompt evolution is appended as `EVOLVE:` lines; cap with `PERSONALITY_MAX_EVOLUTIONS`.

### Unproven / follow-up (prioritized)

- [ ] **Unified agent model.** Replace per-slot hard-coded roles with a single `Agent` class whose behavior is driven by the bus inbox + personality object. Treat `@Human`, `@grok`, and dynamically spawned agents as peers.
- [ ] **Bus-first event loop.** Make every LLM call a reaction to a bus event (mention, request, beacon). The orchestrator should schedule work by posting messages, not by slot number.
- [ ] **Prompt size diet.** LM Studio logs show prompts 1.1K–1.4K tokens (no truncation, but heavy). Compress context: move long instructions to schemas/system prompts, keep user context to facts only.
- [ ] **Planner code quality.** Many actor failures come from the planner hallucinating variables (`write_status`, `Path('BASE_DIR')`, nested `COMMS_DIR / 'runtime' / 'comms'`). Add a static analyzer or few-shot repair step before actor execution.
- [ ] **Verifier consistency.** Nemotron verifier is stricter than Gemma. Standardize evidence format (e.g., `print(f'ARTIFACT: {path} size={len(text)}')`) so verifier can parse reliably.
- [ ] **Fission pipeline coverage.** In 360s Nemotron runs, plans complete and actors run, but verifier/fission rarely fires. Investigate whether scheduler advances correctly after actor success or gets stuck in math/reflect loops.
- [ ] **Self-evolution safety.** Reflector/mutator can edit code and personalities. Add a sandboxed diff-review step before applying mutations to tracked files.
- [ ] **Human-as-agent.** The TUI input line and `comms.py post human "..."` should be first-class peers, not special cases.
- [ ] **Simplify-reduce branch review.** `origin/simplify-reduce` removed ~30% of code (token telemetry, bus integration, GUI hardening). Do **not** merge it wholesale, but cherry-pick any clean refactors that do not drop event-driven or self-evolution features.
- [ ] **LM Studio log analysis.** `C:\Users\px-wjt\.lmstudio\server-logs\2026-06\2026-06-13.1.log` shows `cancel task` bursts when the test harness kills the tree and no actual prompt truncation. Use this log after every long run to distinguish server-side queueing from client-side bugs.

### Architectural vision

The colony should become a **single event bus with generic agents**, not six special-cased slots:

```
Bus (messages.json)
  ├─ Human peer
  ├─ Grok peer
  ├─ GUI peer
  └─ N agent peers (personality + inbox)
         └─ Planner → Actor → Verifier → FissionJudge
```

In Python 3.13 terms: an `Agent` dataclass, a `Personality` object, and a `BusMessage` object. Specialized behavior comes from the personality text and the inbox, not from branching code in `agents.py` or `engine.py`. This is the path to both code reduction and dynamic scaling.

---

## Rules

- Stdlib + ctypes only. No pip.
- No personal identifiers in code or commits.
- Personality IS the goal. No task assignment.
- Runtime never committed. Archive before restart.
