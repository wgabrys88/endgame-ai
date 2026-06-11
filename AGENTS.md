# AGENTS.md — Authoritative Project Map
# endgame-ai | Windows desktop automation reactor
# Updated: 2026-06-12 | Post-scheduler-fix session
# Purpose: hand this to ANY coding agent as ground truth before modification

================================================================================
## 1. SYSTEM IDENTITY
================================================================================

endgame-ai is a self-sustaining Windows 11 desktop automation reactor.
Two threads. One shared board dict. Five LLM agents + three math agents +
one scheduler + one observer. Zero pip dependencies.
~3,900 LOC Python 3.13. It plans, sees, acts, verifies.
Verified work = fission. Fission sustains the reactor.
Stagnation triggers reflection. Reflection mutates prompts.
When reflection fails, the mutator writes new code (plugins).
The organism rewrites its own behavior while running.

DESIGN PRINCIPLE: Math is the environment. LLMs are agents inside it.
LLMs never see math values or knobs. Fish don't tune water pressure.
Math decides WHEN agents fire. LLMs decide WHAT to do when called.

Proven M4 (2026-06-10): self-launch, self-edit config.py, spawn child process
on evolved disk, child ran on parent-modified code. Two stop events, two logs.

Proven M4+ (2026-06-12): scheduler priority inversion fixed, math gates fire
correctly, 4 reflections + 2 fissions in 529 events, activity dampening works.

================================================================================
## 2. FILE INVENTORY (production root — 12 .py + 5 prompts + 5 schemas)
================================================================================

FILE            LINES  DOES
───────────────  ─────  ─────────────────────────────────────────────────────────
main.py           114  Entry point. Argparse, SIGINT, board init, calls engine.run()
engine.py         286  Reactor loop + math thread + plugin loading + fission + _save
agents.py         740  All agent classes + context rendering + mutation logic
actions.py        388  exec engine + GUI verbs + spawn_main + write_file + verify
observer.py       401  Hover probe + UIA tree walk + merge → SCREEN text
config.py         135  ALL constants, paths, tuning. Single source of truth
log.py            174  Event bus. Lock file. Pause sink. Budget counter
llm.py            300  LM Studio + ACP backends. Schema loading. LLMReply + token est
token_state.py    194  Token accounting reducer (burn rate, per-agent, trace)
lessons.py         84  Scored JSON lesson store with keyword retrieval + decay
win32.py          366  Raw ctypes COM/UIA bindings. No pywin32. No pip
acp_client.py     252  Kiro CLI ACP protocol over WSL2 stdin/stdout pipes
tui.py            540  VT100 two-panel dashboard (parent upper / child lower)

prompts/planner.txt    LLM system prompt for PlannerAgent
prompts/actor.txt      LLM system prompt for ActorAgent
prompts/verifier.txt   LLM system prompt for VerifierAgent
prompts/reflector.txt  LLM system prompt for ReflectorAgent
prompts/mutator.txt    LLM system prompt for MutatorAgent

schemas/planner.json   strict JSON schema: mode, sequence[], done_when
schemas/actor.json     strict JSON schema: actions[], conclusion
schemas/verifier.json  strict JSON schema: verdict, evidence
schemas/reflector.json strict JSON schema: diagnosis, lesson, prompt_mutation
schemas/mutator.json   strict JSON schema: diagnosis, action, filename, content

plugins/web_sentinel.py  UTC time API heartbeat (connectivity proof)
plugins/lessons_decay.py Periodic score decay for old lessons

TOTAL PRODUCTION: ~3,980 lines Python + prompts + schemas

================================================================================
## 3. DEPENDENCY GRAPH (verified from import statements, 2026-06-11)
================================================================================

```
main.py
├── from config import (PROCESS_DPI_AWARENESS_CONTEXT, RESPAWN_PATH, SIGINT_EXIT_CODE)
├── from llm import (set_backend, close_backend)
├── from engine import run
├── import log
└── import config

engine.py
├── from actions import is_python_step
├── from agents import (StagnationAgent, LorenzAgent, PidAgent, SchedulerAgent,
│     ObserverAgent, PlannerAgent, ActorAgent, VerifierAgent, ReflectorAgent,
│     MutatorAgent, _similar_to_completed, _trivial_milestone)
├── import config          ← LIVE MUTABLE
├── import log
└── import token_state

agents.py
├── import config          ← LIVE MUTABLE
├── import log
├── import lessons         ← scored retrieval
└── from actions import DEFAULT_SCROLL_AMOUNT

actions.py
├── import config          ← LIVE MUTABLE (fixed from frozen)
└── from win32 import (user32, get_window_title, VK_MAP, EXTENDED_VKS, INPUT)

observer.py
├── import config          ← LIVE MUTABLE (fixed from frozen)
├── from config import BASE_DIR  # path reference only
└── from win32 import (...)

log.py
├── import config          ← LIVE MUTABLE (fixed from frozen)

llm.py
├── import config          ← LIVE MUTABLE

token_state.py
├── import config          ← LIVE MUTABLE

lessons.py
├── import config          ← LIVE MUTABLE

win32.py
├── from config import (PROCESS_DPI_AWARENESS_CONTEXT, READ_TEXT_MAX_LENGTH)
└── (pure ctypes stdlib otherwise)

tui.py
├── import log
├── import config          ← LIVE MUTABLE
├── import lessons
└── (subprocess.Popen for launching main.py)

plugins/lessons_decay.py
├── import lessons
└── (runs via engine plugin scanner)
```

HOT-SWAP STATUS: ALL modules now use `import config` then `config.X`.
Every config value is live-mutable via exec("import config; config.X = Y")
without child spawn. The frozen-import problem is RESOLVED.

================================================================================
## 4. THE BOARD DICT (single mutable state — passed by reference)
================================================================================

FIELD               WRITER(S)                READER(S)
──────────────────  ─────────────────────    ─────────────────────────────────────
goal                main.py, _poll_goal      planner, verifier, reflector, scheduler
plan                planner, fission         scheduler, actor, verifier, reflector
done_when           planner, fission         verifier, scheduler
history             actor                    planner, actor, verifier, reflector
completed           fission                  planner, verifier, reflector, scheduler
power               fission                  (logged in stop/fission events)
start_time          main.py                  fission (elapsed time calc)
screen              observer                 actor, verifier
screen_elements     observer                 actor (element book for GUI verbs)
desktop_summary     observer                 planner
focused_window      observer                 planner, _save
consecutive_failures fission, _trivial       scheduler, stagnation, reflector
activity_events     reflector, mutator       stagnation (dampens signal, resets to 0)
stagnation          StagnationAgent          LorenzAgent, PidAgent, scheduler
progress_history    StagnationAgent          StagnationAgent
lorenz_x/y/z       LorenzAgent              LorenzAgent, _save
energy              LorenzAgent              scheduler, _save
wing_crossed        LorenzAgent, scheduler   scheduler
pid_output          PidAgent                 scheduler, _save
pid_integral        PidAgent, fission        PidAgent, _save
pid_prev            PidAgent                 PidAgent
last_reflect_time   scheduler                scheduler
reflect_trigger     scheduler                reflector
math_trace          _math_loop               _save
token_state         engine._run_agent        _save, tui

================================================================================
## 5. AGENT ROSTER
================================================================================

AGENT             TYPE     READS                          OUTPUT
──────────────    ────────  ──────────────────────────────  ────────────────────────
StagnationAgent   math     plan, progress_history, fails,  stagnation (0.0-1.0)
                           activity_events                 (resets activity to 0)
LorenzAgent       math     lorenz_x/y/z, stagnation        energy, wing_crossed
PidAgent          math     stagnation, pid_integral, prev  pid_output
SchedulerAgent    routing  stag,wing,energy,pid,plan,goal  next agent to fire
ObserverAgent     sensing  screen                          screen, elements, window
PlannerAgent      LLM      goal,desktop,plan,history,...    plan[], done_when
ActorAgent        LLM      instruction, screen, history    actions[] (GUI verbs)
VerifierAgent     LLM      goal,done_when,screen,history   verdict: confirmed|denied
ReflectorAgent    LLM      goal,plan,history,trigger       diagnosis, lesson, mutation
MutatorAgent      LLM      goal,plan,history,trigger       diagnosis, action, filename, content

ESCALATION PATH:
  scheduler → reflector (1st-order: prompt mutation, when math gates fire)
  reflector → mutator   (2nd-order: code generation, after ≥3 failures persist)

SCHEDULER PRIORITY (evaluated in this order):
  1. Reflection gates — stag+pid/stag+failures/energy+stag thresholds met → reflector
  2. Wing cross — Lorenz regime change → replan
  3. No plan → planner
  4. Active step → actor
  5. All done → verifier
  6. Fallback → planner

ACTIVITY DAMPENING:
  Reflections and mutations emit activity_events=1
  StagnationAgent subtracts 0.2/event then resets to 0
  Prevents infinite reflect/mutate loops — gives work loop a window

================================================================================
## 6. EXECUTION MODEL
================================================================================

Plan steps are TEXT STRINGS. The planner outputs mode:"direct" with sequence[].

HEADLESS:
  "exec <code>"       → execute_python(code) in sandboxed namespace
  "exec:\n<multiline>"→ same, multiline
  "read_file <path>"  → reads file from disk
  "write_file <path> <content>" → writes file + py_compile verify if .py
  "wait <seconds>"    → time.sleep

GUI (only when gui_mode file exists):
  ActorAgent LLM resolves element IDs from SCREEN text
  Emits: click, write, press, hotkey, scroll, focus, wait
  Each verb calls raw Win32 ctypes

EXEC NAMESPACE:
  Available: BASE_DIR, Path, os, sys, json, time, subprocess
  Functions: spawn_main(goal), enable_gui(), pause_reactor()

SAFETY GATE:
  After ANY .py file write: py_compile + import check

================================================================================
## 7. FISSION MECHANICS
================================================================================

Triggered when: verifier returns verdict="confirmed"

STEPS:
1. _similar_to_completed(done_when, completed) — reject repeats
2. _trivial_milestone(goal, done_when) — reject observational milestones
3. Append done_when to completed[]
4. Calculate power = len(completed) / elapsed_seconds
5. Reset: plan, done_when, failures, progress_history, pid_integral
6. log.emit("fission", {power, completions})

================================================================================
## 8. SELF-EVOLUTION MECHANISMS
================================================================================

MECHANISM                   LATENCY    STATUS
───────────────────────────  ─────────  ──────
1. Prompt file read          instant    LIVE (reads from disk every LLM call)
2. Lessons append            instant    LIVE (scored store with keyword retrieval)
3. Goal hot-swap             0.15s      LIVE (goal.txt polled each cycle)
4. Pause/resume toggle       0.15s      LIVE (PAUSE_PATH.exists())
5. GUI mode toggle           0.15s      LIVE (GUI_MODE_PATH.exists())
6. config.X runtime patch    instant    LIVE — ALL modules see changes immediately
7. Prompt mutation           instant    LIVE (reflector appends RULE)
8. Plugin hot-load           per-cycle  LIVE (engine scans plugins/ each cycle)
9. Plugin mutation           ~5-10s     LIVE (mutator writes new .py to plugins/)
10. Disk edit + child spawn  ~2-5s      LIVE (actions._spawn_main)

ALL CONFIG VALUES ARE NOW LIVE-MUTABLE without child spawn.
The frozen-import problem documented in earlier AGENTS.md versions is FIXED.

================================================================================
## 9. PLUGIN SYSTEM
================================================================================

Directory: plugins/
Scanner: engine.py loads plugins each cycle via importlib.
Interface: each plugin must expose def run(board) → dict of writes
Isolation: one broken plugin cannot crash the reactor

Current plugins:
  web_sentinel.py  — UTC time fetch every 30s (connectivity heartbeat)
  lessons_decay.py — ages old lessons by -1 score/5min (forces fresh knowledge)

================================================================================
## 10. LESSONS SYSTEM
================================================================================

Store: lessons.jsonl (JSONL, scored entries)
Module: lessons.py
Interface:
  lessons.record(lesson, action="", score=7) — write scored entry
  lessons.relevant(keyword, n=5)             — keyword search weighted by score
  lessons.recent(n=5)                        — last N entries
  lessons.format_for_context(keyword)        — ready string for LLM context

Eviction: when >200 entries, lowest-scored dropped first
Decay: lessons_decay plugin ages all entries -1 score/5min (floor=1)
Context: agents.py renders lessons RELEVANT TO CURRENT ACTIVE STEP
         (keyword = active plan step text)

Effect: small models see only the highest-quality, most-relevant knowledge.
Old noise decays to score=1 and gets evicted on overflow.

================================================================================
## 11. THINGS TO NOT DO
================================================================================

- DO NOT add pip dependencies (zero-dep rule is load-bearing)
- DO NOT use importlib.reload() on core modules
- DO NOT change events.jsonl format {n, t, phase, d}
- DO NOT rename board dict keys
- DO NOT remove _verify_python_edit from actions.py
- DO NOT let reflector exceed PROMPT_MAX_RULES=8 mutations per prompt
- DO NOT add docstrings (self-documenting names + this file = docs)
- DO NOT expose math values to LLMs (math is environment, not cognitive load)
- DO NOT add ewojgab or personal paths to committed code

================================================================================
## 12. PARENT-CHILD ARCHITECTURE
================================================================================

Parent (ACP, smart model) supervises child (LM Studio, local model).

LAUNCH:
  python tui.py --backend acp --event-budget 1000 "goal"
  Parent spawns child via: spawn_main(goal)
  → python main.py goal --backend lmstudio --event-budget 200 --events-path events-child.jsonl

ISOLATION:
  - main.py --events-path patches config.EVENTS_PATH before log.init()
  - Child writes to events-child.jsonl, parent writes to events.jsonl
  - TUI reads both: upper half = parent, lower half = child

PARENT DUTIES:
  - Monitor child progress via events-child.jsonl
  - Rewrite child's goal.txt when stuck
  - Harvest child lessons into parent lessons store
  - Spawn progressively harder children until system runs on local models alone

================================================================================
## 13. RUNTIME ARTIFACTS (gitignored, created on run)
================================================================================

FILE               CREATED BY     PURPOSE
────────────────── ─────────────  ────────────────────────────────────────
events.jsonl       log.init()     Primary event log (append-only)
events-child.jsonl child process  Child instance event log
snapshot.json      engine._save() Board state for TUI reading
goal.txt           main.py/TUI    Current goal (polled every 0.15s)
pause              log.set_paused Existence = reactor paused
gui_mode           enable_gui()   Existence = observer scans screen
lessons.jsonl      lessons.record Scored lesson entries (JSONL)
disabled.json      TUI            Agent enable/disable toggles
.endgame.lock      log._acquire   Lock file (PID of log owner)
respawn.json       main.py        Contract for child spawn params

================================================================================
## 14. CONFIG REFERENCE (config.py — 135 lines)
================================================================================

PATHS: BASE_DIR, PROMPTS_DIR, SCHEMAS_DIR, PLUGINS_DIR, EVENTS_PATH,
       SNAPSHOT_PATH, LESSONS_PATH, DISABLED_PATH, GUI_MODE_PATH, GOAL_PATH,
       PAUSE_PATH, RESPAWN_PATH, LOG_LOCK_PATH, CHILD_EVENTS_PATH

BUDGET: EVENT_BUDGET=20 (override via --event-budget)

LLM (LM Studio): LMS_HOSTS, LMS_TIMEOUT=300s, LMS_REQUEST_ATTEMPTS=3
LLM (ACP/Kiro):  ACP_TIMEOUT=90s, ACP_PROTOCOL_VERSION=1
LLM PARAMS:      temperature=0.30, top_p=0.95, top_k=64, seed=3407

AGENT BUDGETS: planner=4000, actor=4000, verifier=4000, reflector=8000

TIMING: DELAY_BETWEEN_CYCLES=0.15s, MATH_INTERVAL=3.0s, EXEC_TIMEOUT=60s

OBSERVER: TREE_WALK_TIMEOUT=5s, PROBE_STEP_PX=90,
          SCREEN_ELEMENT_VALUE_LIMIT=-1 (unlimited),
          TERMINAL_CONTEXT_TAIL_LINES=-1 (unlimited)

LORENZ: sigma=10, rho=28, beta=8/3, dt=0.05, mag_cap=80
PID: Kp=1.2, Ki=0.4, Kd=0.6, integral_max=8
SCHEDULING: REFLECT_MIN_INTERVAL_SEC=6s, REFLECT_THRESHOLD=0.6 (pid gate),
            REFLECT_STAG_THRESHOLD=0.5, CHAOS_ENERGY_THRESHOLD=2.0,
            MUTATOR_ESCALATION_FAILURES=3, PROMPT_MAX_RULES=8
LIMITS: MAX_HISTORY=100, MAX_PLAN_STEPS=12

CONTEXT_POLICY (which fields each LLM agent sees):
  planner:   goal, desktop, plan, history, completed, budget, failures, lessons
  actor:     instruction, screen, history, lessons
  verifier:  goal, done_when, screen, history, plan, completed
  reflector: goal, plan, history, trigger, completed, lessons
  mutator:   goal, plan, history, trigger, completed

NOTE: Math values are NEVER shown to LLMs. Math is the environment,
not a tuning target. LLMs get "trigger" (reason + failures + step) only.

================================================================================
## 14. SCHEMA CONTRACTS
================================================================================

PLANNER: { mode: "direct"|"done", sequence: string[], done_when: string }
ACTOR:   { actions: [{verb, target, value}], conclusion: "EXECUTE"|"DONE"|"CANNOT" }
VERIFIER:{ verdict: "confirmed"|"denied", evidence: string }
REFLECTOR:{ diagnosis, lesson, prompt_mutation: {target, append} }
MUTATOR: { diagnosis, action, filename, content }

================================================================================
## 15. TOKEN TELEMETRY
================================================================================

- llm.py produces LLMReply with token estimates (char/word based)
- engine._run_agent feeds replies into token_state.record_reply()
- Board["token_state"] tracks cumulative, per-agent, burn rate, trace
- snapshot.json includes token_trace and token_warnings for TUI display
- Admission control: fails loudly rather than silently truncating context

================================================================================
## 16. ENTRY POINTS
================================================================================

# Standard launch (TUI dashboard + reactor):
python tui.py "Your goal here" --backend lmstudio --event-budget 500

# Headless launch (no TUI, direct reactor):
python main.py "Your goal" --backend lmstudio --event-budget 200

# Import health check:
python -c "import config,engine,agents,actions,log,llm,observer,win32,acp_client,tui,token_state,lessons;print('OK')"

REQUIREMENTS: Windows 10/11, Python 3.13, LM Studio on localhost:1234 OR Kiro CLI (ACP)

================================================================================
## 17. QUICK START FOR CODING AGENTS
================================================================================

Before modifying this codebase:
1. Run the import health check above — it must pass
2. After ANY .py edit, run it again — must still pass
3. Never add pip dependencies
4. Never change events.jsonl format or board dict key names
5. prompts/*.txt are the "program" — edit freely, effect is immediate
6. config.py values are ALL live-mutable via `import config; config.X`
7. The organism can write files via exec — don't rely on paths being constant
8. Test with: python main.py "simple goal" --event-budget 5 (minimal run)

================================================================================
## 18. WHAT WAS REMOVED (2026-06-11 cleanup session)
================================================================================

DELETED (dead code / non-essential):
  hud.py                              850 LOC Win32 GDI overlay (cosmetic only)
  debug_context.py                     50 LOC dev tool
  m4_merge_test.py                     80 LOC merge gate (M4 proven)
  tests_validate_schemas.py            60 LOC schema checks
  evolved-organism-code/endgame_tui.py 29 LOC pip violation (textual)
  evolved-organism-code/evolved_reactor.py 94 LOC tkinter demo
  evolved-organism-code/reactor_demo.py 146 LOC tkinter demo
  evolved-organism-code/agent_worker.py 20 LOC broken prototype

  TOTAL REMOVED: ~1,330 LOC

WHAT WAS FIXED:
  observer.py, actions.py, log.py — `from config import` → `import config`
  (already done before this session, but AGENTS.md was stale)

================================================================================
END OF AGENTS.md
================================================================================
