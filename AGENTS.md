# Breeding Reactor — Agent Technical Map

**Breakthrough (2026-06-12):** Six autonomous agents + external AI (@grok) coordinated over a JSON message bus. Real desktop outcomes: Notepad matrix-escape text, GitHub in browser, Opera at LinkedIn feed. Documented in `EXECUTION_REPORT.md`. Forensic tooling: `forensic_collect.py`.

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
| `config.py` | Paths, math, LMS hosts, bus caps, rolling log limits |
| `llm.py` | LM Studio API, schema enforcement, host failover |
| `log.py` | JSONL events, `cleanup_runtime`, pause gate, rolling trim |
| `observer.py` | UIA desktop scan → element book `[n]` ids |
| `win32.py` | ctypes user32, SendInput, VK map |
| `forensic_collect.py` | Zip session evidence + write `FORENSIC_ANALYSIS.md` |

---

## Personalities (`prompts/personalities/`)

| Slot | File | Identity |
|------|------|----------|
| n1 | `git_expert.txt` | Commits/pushes `colony/dev` |
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

Per-agent: `events-child-n*.jsonl` (rolling **450 lines** — oldest drop). Board: `snapshot.json`.

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
- `LMS_MAX_SLOTS_PER_HOST` = 3.
- `LMS_PREFERRED_MODEL` = `gemma` (override: `ENDGAME_LMS_MODEL`).
- `LMS_TIMEOUT` = 90s.

---

## Key constants

| Constant | Value |
|----------|-------|
| REACTOR_SLOTS | 6 |
| EVENT_ROLLING_MAX_LINES | 450 |
| BUS_CHAT_MAX | 120 |
| BUS_EVENTS_MAX_LINES | 200 |
| MATH_INTERVAL | 5.0s |
| PLAN_REJECT_COOLDOWN_SEC | 10 |

---

## Known issues (post-demo)

1. **Rolling log cap** — early session proof evicted from `events-child-*.jsonl`.
2. **Role leak** — n4 ran `desktop_*`; n6 should be sole GUI hands.
3. **Gemma planner** — `NameError: book`, syntax errors, wrong window titles.
4. **Permissive verifier** — fission credited for observing TUI/PowerShell, not goal text.
5. **@mention spacing** — `@grok` must be followed by space; `@grokproceed` fails.

---

## Rules

- Stdlib + ctypes only. No pip.
- No personal identifiers in code or commits.
- Personality IS the goal. No task assignment.
- Runtime never committed. Archive before restart.