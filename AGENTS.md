# AGENTS.md — Authoritative Project Map
# endgame-ai | Windows desktop automation reactor
# Verified: 2026-06-11 | Branch: evolution-m4
# Purpose: hand this to ANY coding agent as ground truth before modification

================================================================================
## 1. SYSTEM IDENTITY
================================================================================

endgame-ai is a self-sustaining Windows 11 desktop automation reactor.
Two threads. One shared board dict. Five LLM agents + three math agents +
one scheduler + one observer. Zero pip dependencies. ~5,300 LOC Python 3.13.

It plans, sees, acts, verifies. Verified work = fission. Fission sustains the
reactor. Stagnation triggers reflection. Reflection mutates prompts. The mutator
evolves plugins. The organism rewrites its own behavior while running.

Proven M4 (2026-06-10): self-launch, self-edit config.py, spawn child process
on evolved disk, child ran on parent-modified code. Two stop events, two logs.

================================================================================
## 2. FILE INVENTORY
================================================================================

FILE              LINES  DOES
────────────────  ─────  ─────────────────────────────────────────────────────────
main.py            111   Entry point. Argparse, SIGINT, board init, calls engine.run()
engine.py          264   Reactor loop + math thread + plugin loader + fission + _save
agents.py          742   All 10 agent classes + context rendering + mutation logic
actions.py         388   exec engine + GUI verbs + spawn_main + write_file + verify
observer.py        398   Hover probe + UIA tree walk + merge → SCREEN text
config.py          118   ALL constants, paths, tuning. Single source of truth
log.py             174   Event bus. Lock file. Pause sink. Budget counter
llm.py             137   LM Studio + ACP backends. Schema loading. HTTP/JSON-RPC
win32.py           366   Raw ctypes COM/UIA bindings. No pywin32. No pip
acp_client.py      252   Kiro CLI ACP protocol over WSL2 stdin/stdout pipes
tui.py             566   Full-width VT100 dashboard. Subprocess launcher
hud.py            1608   GDI transparent overlay HUD. Reads snapshot.json
debug_context.py    54   Dev tool: dumps agent context to file for inspection
m4_merge_test.py   132   Merge gate: validates M4 proof criteria from event logs

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

plugins/web_sentinel.py  First plugin — connectivity sentinel (UTC time fetch)

evolved-organism-code/   10 archived files from organism's own M4 evolution

================================================================================
## 3. DEPENDENCY GRAPH (verified from import statements)
================================================================================

```
main.py
  ├── from config import (PROCESS_DPI_AWARENESS_CONTEXT, RESPAWN_PATH, SIGINT_EXIT_CODE)
  ├── from llm import (set_backend, close_backend)
  ├── from engine import run
  ├── import log
  └── import config

engine.py
  ├── import importlib.util
  ├── from actions import is_python_step
  ├── from agents import (StagnationAgent, LorenzAgent, PidAgent, SchedulerAgent,
  │       ObserverAgent, PlannerAgent, ActorAgent, VerifierAgent, ReflectorAgent,
  │       MutatorAgent, _similar_to_completed, _trivial_milestone)
  ├── import config          ← LIVE MUTABLE
  └── import log

agents.py
  ├── import config          ← LIVE MUTABLE
  ├── import log
  └── from actions import DEFAULT_SCROLL_AMOUNT

actions.py
  ├── import config          ← LIVE MUTABLE
  └── from win32 import (user32, get_window_title, VK_MAP, EXTENDED_VKS, INPUT)

observer.py
  ├── import config          ← LIVE MUTABLE
  ├── from config import BASE_DIR  (Path reference only)
  └── from win32 import (...)

log.py
  └── import config          ← LIVE MUTABLE

acp_client.py
  └── import config          ← LIVE MUTABLE

llm.py
  └── import config          ← LIVE MUTABLE

win32.py
  └── (no project imports — pure ctypes stdlib)

tui.py
  ├── import log
  └── import config
```

HOT-SWAP STATUS:
  ALL production modules now use `import config` + `config.X` pattern.
  This means every config value is live-mutable at runtime via:
    exec("import config; config.SCREEN_ELEMENT_VALUE_LIMIT = 2000")
  No child spawn needed to change any tuning parameter.

================================================================================
## 4. THE BOARD DICT (single mutable state — passed by reference)
================================================================================

FIELD               WRITER(S)              READER(S)
──────────────────  ─────────────────────  ─────────────────────────────────────
goal                main.py, _poll_goal    planner, verifier, reflector, scheduler
plan                planner, fission       scheduler, actor, verifier, reflector
done_when           planner, fission       verifier, scheduler
history             actor                  planner, actor, verifier, reflector
completed           fission                planner, verifier, reflector, scheduler
power               fission                (logged in stop/fission events)
start_time          main.py                fission (elapsed time calc)
screen              observer               actor, verifier
screen_elements     observer               actor (element book for GUI verbs)
desktop_summary     observer               planner
focused_window      observer               planner, _save
consecutive_failures fission, _trivial     scheduler, stagnation, mutator
stagnation          StagnationAgent        LorenzAgent, PidAgent, scheduler, mutator
progress_history    StagnationAgent        StagnationAgent
lorenz_x/y/z        LorenzAgent            LorenzAgent, _save
energy              LorenzAgent            scheduler, _save, mutator
wing_crossed        LorenzAgent, scheduler scheduler
pid_output          PidAgent               scheduler, _save
pid_integral        PidAgent, fission      PidAgent, _save
pid_prev            PidAgent               PidAgent
last_reflect_time   scheduler              scheduler
reflect_trigger     scheduler              reflector
math_trace          _math_loop             _save (last N snapshots)

================================================================================
## 5. AGENT ROSTER (10 agents: 5 LLM, 3 math, 1 scheduler, 1 observer)
================================================================================

AGENT           TYPE      READS                           OUTPUT
──────────────  ────────  ──────────────────────────────  ────────────────────────
StagnationAgent math      plan, progress_history, fails   stagnation (0.0-1.0)
LorenzAgent     math      lorenz_x/y/z, stagnation        energy, wing_crossed
PidAgent        math      stagnation, pid_integral, prev  pid_output
SchedulerAgent  routing   stag,wing,energy,pid,plan,goal  next agent to fire
ObserverAgent   sensing   screen                          screen, elements, window
PlannerAgent    LLM       goal,desktop,plan,history,...    plan[], done_when
ActorAgent      LLM       instruction, screen, history    actions[] (GUI verbs)
VerifierAgent   LLM       goal,done_when,screen,history   verdict: confirmed|denied
ReflectorAgent  LLM       goal,plan,history,math,trigger  diagnosis, lesson, mutation
MutatorAgent    LLM       goal,plan,history,stag,energy   writes plugins/*.py

SCHEDULING LOGIC (agents.py SchedulerAgent.run):
  1. wing_crossed=True → fire planner (force replan)
  2. no plan → fire planner
  3. active step + reflect_wanted + failures≥1 → fire reflector
  4. active step → fire actor
  5. reflect_wanted (no active) → fire reflector
  6. all steps done → fire verifier
  7. pending step exists → activate it, fire actor
  8. else → fire planner (stuck)

REFLECT GATES (must ALL be true):
  - time since last reflect ≥ 6s (REFLECT_MIN_INTERVAL_SEC)
  - at least one of: pid≥0.6+stag≥0.5, stag≥0.5+failures≥1, energy≥2.0+stag≥0.5

MUTATOR TRIGGER: the scheduler does not yet auto-fire the mutator. It must be
invoked explicitly or wired into the scheduler based on plugin.error accumulation.

================================================================================
## 6. PLUGIN SYSTEM (engine.py _run_plugins)
================================================================================

The plugin loader runs EVERY cycle, before the scheduler:

  1. Scan plugins/*.py (sorted alphabetically)
  2. Track file mtime per path
  3. On new/changed file: importlib.util.spec_from_file_location → exec_module
  4. Call plugin.run(board) → expect dict with optional {writes, phase, data}
  5. Merge writes into board, emit phase event
  6. Isolate exceptions — one broken plugin cannot crash the reactor
  7. Emit plugin.load on successful hot-load, plugin.error on failure

PLUGIN CONTRACT:
  - File: plugins/<name>.py where name matches [a-z0-9_]+
  - Must define: def run(board) -> dict | None
  - Return format: {"writes": {key: value}, "phase": "plugin.name", "data": {...}}
  - Allowed imports: stdlib only (json, time, os, pathlib, urllib, etc.)
  - FORBIDDEN: importing from reactor core (engine, agents, actions, log, win32)
  - FORBIDDEN: pip packages

HOT-SWAP BEHAVIOR:
  - Drop a .py file in plugins/ → loaded next cycle (~0.15s)
  - Edit an existing plugin → reloaded on mtime change
  - Delete a plugin file → stops running (module stays cached but path gone)

================================================================================
## 7. EXECUTION MODEL (how plan steps become actions)
================================================================================

Plan steps are TEXT STRINGS. The planner outputs mode:"direct" with sequence[].
engine._run_agent("actor") is called. But FIRST, actions.is_python_step() checks
if the step is headless:

  HEADLESS (actions.py execute_step):
    "exec <code>"       → execute_python(code) in sandboxed namespace
    "exec:\n<multiline>" → same, multiline
    "read_file <path>"  → reads file from disk, returns content
    "write_file <path> <content>" → writes file + py_compile verify if .py
    "wait <seconds>"    → time.sleep

  GUI (only when gui_mode file exists):
    ActorAgent LLM resolves element IDs from SCREEN text
    Emits: click, write, press, hotkey, scroll, focus, wait
    Each verb calls raw Win32 ctypes (user32.SetCursorPos, SendInput, etc.)

EXEC NAMESPACE (actions.py execute_python):
  Available without import: BASE_DIR, Path, os, sys, json, time, subprocess
  Available as functions: spawn_main(goal), enable_gui(), pause_reactor()

SAFETY GATE (actions.py _verify_python_edit):
  After ANY .py file write:
    1. py_compile.compile(file) — catches syntax errors
    2. subprocess.run([python, -c, "import config; import engine; ..."]) — import check
  If either fails → write_file returns failure, organism retries

================================================================================
## 8. FISSION MECHANICS (engine.py _fission)
================================================================================

Triggered when: verifier returns verdict="confirmed"

FISSION STEPS:
  1. Check _similar_to_completed(done_when, completed) — reject repeats
  2. Check _trivial_milestone(goal, done_when) — reject observational milestones
  3. If passed: append done_when to completed[], trim to 50
  4. Calculate power = len(completed) / elapsed_seconds
  5. Reset: plan=[], done_when="", consecutive_failures=0, progress_history=[], pid_integral=0
  6. log.emit("fission", {power, completions})

ANTI-REPEAT: _similar_to_completed uses token-set overlap ≥ 0.55 threshold
ANTI-TRIVIAL: rejects "visible/showing/readable" milestones when goal requires action

================================================================================
## 9. SELF-EVOLUTION MECHANISMS (ranked by immediacy)
================================================================================

MECHANISM                    LATENCY    HOW
───────────────────────────  ─────────  ────────────────────────────────────────
1. Prompt file read          instant    agents._load_prompt() reads from disk on
                                        EVERY LLM call, no cache
2. Lessons append            instant    reads last 8 lines from lessons.txt every call
3. Goal hot-swap             0.15s      engine._poll_goal(): reads goal.txt each cycle
4. Pause/resume toggle       0.15s      log.paused(): config.PAUSE_PATH.exists() check
5. GUI mode toggle           0.15s      engine._needs_screen(): config.GUI_MODE_PATH.exists()
6. config.X runtime patch    instant    exec("import config; config.X = Y")
                                        ALL modules use live import config pattern
7. Prompt mutation           instant    agents._apply_mutation(): appends RULE to
                                        prompts/<target>.txt, respects MAX_RULES=8
8. Plugin hot-load           0.15s      Drop .py in plugins/ → engine._run_plugins
                                        loads it next cycle via importlib.util
9. Plugin mutation           ~5-10s     MutatorAgent writes new plugin to disk →
                                        plugin loader picks it up next cycle
10. Disk edit + child spawn  ~2-5s      actions._spawn_main(): Popen(main.py)
                                        child reads modified .py from disk fresh

WHAT CAN BE HOT-SWAPPED (no restart, no spawn):
  - Any config.py value (all modules read config.X live)
  - All prompts (read from disk each LLM call)
  - Goals (polled each cycle)
  - Capabilities (via new plugins)

WHAT REQUIRES CHILD SPAWN:
  - Structural code changes to core .py files (new function, new class, new verb)
  - Changes to import-time constants in win32.py or tui.py

================================================================================
## 10. WHAT TO DO NEXT (ordered by value)
================================================================================

PRIORITY 1: Wire MutatorAgent into scheduler trigger logic
  CONDITION: fire mutator when board["consecutive_failures"] > 3 OR
    when plugin.error events exceed 2 in recent cycles
  WHERE: agents.py SchedulerAgent.run — add mutator routing rule
  WHY: mutator exists but has no automatic trigger yet

PRIORITY 2: Multi-instance TUI columns
  WHY: the organism spawns children (proven M4). Side-by-side view needed.
  DEPENDS ON: instance_comm.py pattern (in evolved-organism-code/)

PRIORITY 3: Plugin unload mechanism
  WHY: if a plugin file is deleted, its cached module still exists in
    _plugin_modules. Add cleanup when path disappears from disk scan.

PRIORITY 4: Merge evolved prompts rules
  WHERE: evolved-organism-code/prompts/planner.txt has 8 rules about
    plan-exhaustion stagnation that are absent from root prompts/planner.txt.
  ACTION: manually merge the best rules into production prompts.

PRIORITY 5: Clean up evolved-organism-code/
  Delete: endgame_tui.py (pip dep violation), reactor_demo.py (superseded by hud.py),
    evolved_reactor.py (superseded by plugin system)
  Promote: instance_comm.py (when multi-instance TUI is built)
  Keep as reference: reflect.py, blackboard.py, agent_worker.py

================================================================================
## 11. THINGS TO NOT DO
================================================================================

DO NOT add pip dependencies. The zero-dep rule is load-bearing: the organism
  can exec("import X") only if X is stdlib or in-tree.

DO NOT use importlib.reload() on core modules (engine, agents, actions, log).
  The plugin pattern (new files, fresh importlib.util load) is safer.

DO NOT change events.jsonl format {n, t, phase, d}. The TUI, m4_merge_test.py,
  and forensic analysis all parse this format.

DO NOT rename board dict keys. snapshot.json and event logs reference them by
  name. Renaming breaks backward compatibility with saved sessions.

DO NOT remove _verify_python_edit from actions.py. This is the organism's
  immune system — prevents self-written syntax errors from persisting.

DO NOT let the reflector mutate the same prompt more than PROMPT_MAX_RULES=8
  times. The evening M4 run proved what happens: 24 reflect cycles appending
  near-identical rules = meltdown. The cap is essential.

================================================================================
## 12. RUNTIME ARTIFACTS (gitignored, created on run)
================================================================================

FILE                CREATED BY       PURPOSE
──────────────────  ─────────────    ──────────────────────────────────────────
events.jsonl        log.init()       Primary event log (append-only)
events-<pid>.jsonl  log._acquire     Child instance log (when lock held)
snapshot.json       engine._save()   Board state for TUI/HUD reading
goal.txt            main.py/TUI      Current goal (polled every 0.15s)
pause               log.set_paused   Existence = reactor paused
gui_mode            enable_gui()     Existence = observer scans screen
lessons.txt         _write_lesson    Append-only reflector knowledge
disabled.json       TUI              Agent enable/disable toggles
.endgame.lock       log._acquire     Lock file (PID of log owner)
respawn.json        main.py          Contract for child spawn params
hud_design.json     (user-created)   Hot-swap HUD design overrides

================================================================================
## 13. CONFIG REFERENCE (config.py — 118 lines, grouped)
================================================================================

PATHS: BASE_DIR, PROMPTS_DIR, SCHEMAS_DIR, PLUGINS_DIR, EVENTS_PATH,
  SNAPSHOT_PATH, LESSONS_PATH, DISABLED_PATH, GUI_MODE_PATH, GOAL_PATH,
  PAUSE_PATH, RESPAWN_PATH, LOG_LOCK_PATH

BUDGET: EVENT_BUDGET=20 (override via --event-budget)

LLM (LM Studio): LMS_HOSTS=["localhost:1234"], LMS_TIMEOUT=300s,
  LMS_REQUEST_ATTEMPTS=3, LMS_RETRY_DELAY=2s

LLM (ACP/Kiro): ACP_TIMEOUT=90s, ACP_PROTOCOL_VERSION=1,
  ACP_DEFAULT_TIMEOUT=300s, ACP_WORKSPACE_BASE="/tmp/poke-acp"

LLM PARAMS: temperature=0.30, top_p=0.95, top_k=64, repeat_penalty=1.05,
  seed=3407, max_tokens=200000

AGENT BUDGETS: planner=4000, actor=4000, verifier=4000, reflector=8000 tokens

TIMING: DELAY_BETWEEN_CYCLES=0.15s, MATH_INTERVAL=3.0s, EXEC_TIMEOUT=60s,
  MAX_WAIT_SECONDS=10s

OBSERVER: TREE_WALK_TIMEOUT=5s, PROBE_STEP_PX=90, SCREEN_ELEMENT_VALUE_LIMIT=1000,
  OBSERVER_TIMEOUT=30s

LORENZ: sigma=10, rho=28, beta=8/3, dt=0.05, mag_cap=80, wing_stag_min=0.25

PID: Kp=1.2, Ki=0.4, Kd=0.6, integral_max=8, integral_decay=0.5, dead_zone=0.05

SCHEDULING: STAGNATION_CYCLES_WINDOW=4, REFLECT_THRESHOLD=0.6,
  REFLECT_MIN_INTERVAL_SEC=6s, REFLECT_STAG_THRESHOLD=0.5,
  CHAOS_ENERGY_THRESHOLD=2.0, PROMPT_MAX_RULES=8

LIMITS: MAX_HISTORY=100, MAX_PLAN_STEPS=12, COMPLETED_SIMILARITY_THRESHOLD=0.55

CONTEXT_POLICY (which fields each LLM agent sees):
  planner:   goal, desktop, plan, history, completed, budget, failures, lessons
  actor:     instruction, screen, history, lessons
  verifier:  goal, done_when, screen, history, plan, completed
  reflector: goal, plan, history, math, trigger, completed
  mutator:   goal, plan, history, math, trigger, completed

================================================================================
## 14. SCHEMA CONTRACTS (what each LLM agent MUST output)
================================================================================

PLANNER (schemas/planner.json):
  { mode: "direct"|"done", sequence: string[0..12], done_when: string[5..200] }
  CONSTRAINT: sequence items must NOT contain [element_id] (regex enforced)
  CONSTRAINT: sequence items 3-300 chars each

ACTOR (schemas/actor.json):
  { actions: [{verb, target, value}][0..5], conclusion: "EXECUTE"|"DONE"|"CANNOT" }
  VERBS: click, write, press, hotkey, scroll, wait, focus
  CONSTRAINT: target 0-200 chars, value 0-8000 chars

VERIFIER (schemas/verifier.json):
  { verdict: "confirmed"|"denied", evidence: string[100..800] }
  Binary output. No middle ground. Evidence must be substantial (min 100 chars)

REFLECTOR (schemas/reflector.json):
  { diagnosis: string[100..500], lesson: string[50..300],
    prompt_mutation: {target: "planner"|"actor"|"verifier"|"", append: string[0..500]} }
  Empty target+append = no mutation (most common case)

MUTATOR (schemas/mutator.json):
  { diagnosis: string[50..500], action: "write_plugin"|"patch_plugin"|"none",
    filename: string[0..100], content: string[0..4000] }
  Filename must match [a-z0-9_]+.py. Content must contain def run(board).

================================================================================
## 15. PROVEN CAPABILITIES (from M4 event logs)
================================================================================

PROVEN (M4 run 2026-06-10):
  ✓ Self-launch: TUI → subprocess.Popen(main.py) → event #1 phase:start
  ✓ Self-edit config: exec rewrote SCREEN_ELEMENT_VALUE_LIMIT 500→1000
  ✓ Prompt mutation: reflector appended RULE to planner.txt
  ✓ Spawn child: exec spawn_main(posterity_goal)
  ✓ Pause self: exec pause_reactor()
  ✓ Child inheritance: child booted on parent-modified disk
  ✓ Child fission: child verified milestone, fissioned
  ✓ Dual stop: parent + child — two independent completions
  ✓ Hot goal swap: goal.txt modified → reactor pivoted immediately
  ✓ GUI automation: Opera browser, LinkedIn post, X.com interaction
  ✓ Safety gate: py_compile + import check prevented bad .py writes

NOT YET PROVEN (implemented but untested in live run):
  ○ Plugin hot-loading from plugins/ directory
  ○ MutatorAgent writing a new plugin
  ○ Multi-instance TUI display
  ○ Runtime config mutation affecting live observer/actions behavior

================================================================================
## 16. ENTRY POINTS (how to run)
================================================================================

# Standard launch (TUI dashboard + reactor):
python tui.py "Your goal here" --backend lmstudio --event-budget 500

# Headless launch (no TUI, direct reactor):
python main.py "Your goal" --backend lmstudio --event-budget 200

# GDI overlay HUD (reads snapshot.json, renders transparent overlay):
python hud.py

# Debug context dump (see what an agent would receive):
python debug_context.py planner --goal "test goal"

# Merge validation (checks M4 proof criteria):
python m4_merge_test.py

# Import health check:
python -c "import config,engine,agents,actions,log,llm,observer,win32,acp_client,tui;print('OK')"

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
  6. config.py values are live-mutable (all modules use import config pattern)
  7. Plugins in plugins/*.py are hot-loaded each cycle — drop a file to extend
  8. The organism can write files via exec — don't rely on paths being constant
  9. Test with: python main.py "simple goal" --event-budget 5 (minimal run)
  10. MutatorAgent only writes to plugins/ — never let it touch core files

================================================================================
## 18. HUD OVERLAY (hud.py — 1608 lines)
================================================================================

A standalone GDI-based transparent overlay that visualizes reactor state:

LAUNCH: python hud.py (reads snapshot.json in a polling loop)

FEATURES:
  - WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TRANSPARENT (click-through)
  - Two layout modes: "dashboard" (full panels) and "column" (compact sidebar)
  - Hot-swap design via hud_design.json (same directory, polled each frame)
  - Math trace curves (Catmull-Rom smoothed), Lorenz attractor plot
  - Agent state visualization, plan display, metric cards
  - Zero pip deps — pure ctypes GDI32/User32

DESIGN OVERRIDE (hud_design.json):
  Optional JSON file with any subset of design keys. Applied on mtime change.
  Keys: layout, scale_w_pct, scale_h_pct, align, font_name, font_size,
    font_weight, backdrop_*, panel_*, plot_*, c_*_r/g/b, right_panel_w_ratio, etc.

================================================================================
END OF AGENTS.md
================================================================================
