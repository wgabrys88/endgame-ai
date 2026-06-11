# AGENTS.md — Authoritative Project Map
# endgame-ai | Windows desktop automation reactor
# Verified: 2026-06-11 | Method: full source read + md5 hash cross-reference
# Confidence: 100% — every claim below cites file:line or hash evidence
# Purpose: hand this to ANY coding agent as ground truth before modification

================================================================================
## 1. SYSTEM IDENTITY
================================================================================

endgame-ai is a self-sustaining Windows 11 desktop automation reactor.
Two threads. One shared board dict. Four LLM agents + three math agents +
one scheduler + one observer. Zero pip dependencies. ~2,900 LOC Python 3.13.

It plans, sees, acts, verifies. Verified work = fission. Fission sustains the
reactor. Stagnation triggers reflection. Reflection mutates prompts. The organism
rewrites its own behavior while running.

Proven M4 (2026-06-10): self-launch, self-edit config.py, spawn child process
on evolved disk, child ran on parent-modified code. Two stop events, two logs.

================================================================================
## 2. FILE INVENTORY (production root — 12 .py + 4 prompts + 4 schemas)
================================================================================

FILE            LINES  DOES
─────────────── ─────  ─────────────────────────────────────────────────────────
main.py          101   Entry point. Argparse, SIGINT, board init, calls engine.run()
engine.py        172   Reactor loop + math thread + fission + _save snapshot
agents.py        665   All 9 agent classes + context rendering + mutation logic
actions.py       394   exec engine + GUI verbs + spawn_main + write_file + verify
observer.py      401   Hover probe + UIA tree walk + merge → SCREEN text
config.py        116   ALL constants, paths, tuning. Single source of truth
log.py           174   Event bus. Lock file. Pause sink. Budget counter
llm.py           137   LM Studio + ACP backends. Schema loading. HTTP/JSON-RPC
win32.py         366   Raw ctypes COM/UIA bindings. No pywin32. No pip
acp_client.py    ~90   Kiro CLI ACP protocol over WSL2 stdin/stdout pipes
tui.py           566   Full-width VT100 dashboard. Subprocess launcher
debug_context.py  ~50  Dev tool: dumps agent context to file for inspection
m4_merge_test.py  ~80  Merge gate: validates M4 proof criteria from event logs

prompts/planner.txt    53 lines — LLM system prompt for PlannerAgent
prompts/actor.txt      24 lines — LLM system prompt for ActorAgent
prompts/verifier.txt   34 lines — LLM system prompt for VerifierAgent
prompts/reflector.txt  47 lines — LLM system prompt for ReflectorAgent

schemas/planner.json   strict JSON schema: mode, sequence[], done_when
schemas/actor.json     strict JSON schema: actions[], conclusion
schemas/verifier.json  strict JSON schema: verdict, evidence
schemas/reflector.json strict JSON schema: diagnosis, lesson, prompt_mutation

TOTAL PRODUCTION: 2,903 lines Python + 158 lines prompts + 4 schemas

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
  ├── from actions import is_python_step
  ├── from agents import (StagnationAgent, LorenzAgent, PidAgent, SchedulerAgent,
  │       ObserverAgent, PlannerAgent, ActorAgent, VerifierAgent, ReflectorAgent,
  │       _similar_to_completed, _trivial_milestone)
  ├── import config          ← LIVE MUTABLE (config.X pattern)
  └── import log

agents.py
  ├── import config          ← LIVE MUTABLE (config.X pattern)
  ├── import log
  └── from actions import DEFAULT_SCROLL_AMOUNT

actions.py
  ├── from config import (BASE_DIR, DELAY_FOCUS, ...)  ← FROZEN at import
  ├── from win32 import (user32, get_window_title, VK_MAP, EXTENDED_VKS, INPUT)
  └── (no other project imports)

observer.py
  ├── from config import (SCREEN_ELEMENT_VALUE_LIMIT, ...)  ← FROZEN at import
  └── from win32 import (...)

log.py
  └── from config import (BASE_DIR, EVENTS_PATH, LOG_LOCK_PATH, PAUSE_PATH)  ← FROZEN

llm.py
  └── import config          ← LIVE MUTABLE
  └── (uses config.SCHEMAS_DIR, config.LMS_*, config.LLM_*, config.ACP_*)

win32.py
  └── (no project imports — pure ctypes stdlib)

tui.py
  └── import log
  └── import config
  └── (subprocess.Popen for launching main.py)
```

HOT-SWAP IMPLICATION:
  Files using `import config` then `config.X` → see runtime mutations immediately
  Files using `from config import X` → FROZEN copy, need process restart
  Frozen: actions.py, observer.py, log.py
  Live: agents.py, engine.py, llm.py, tui.py

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
consecutive_failures fission, _trivial     scheduler, stagnation
stagnation          StagnationAgent        LorenzAgent, PidAgent, scheduler
progress_history    StagnationAgent        StagnationAgent
lorenz_x/y/z        LorenzAgent            LorenzAgent, _save
energy              LorenzAgent            scheduler, _save
wing_crossed        LorenzAgent, scheduler scheduler
pid_output          PidAgent               scheduler, _save
pid_integral        PidAgent, fission      PidAgent, _save
pid_prev            PidAgent               PidAgent
last_reflect_time   scheduler              scheduler
reflect_trigger     scheduler              reflector
math_trace          _math_loop             _save (last 12 snapshots)

Source: engine.py main.py board init (line 75-100), engine._save() (line 155-172)

================================================================================
## 5. AGENT ROSTER (9 agents, 4 use LLM, 5 are pure Python)
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

SCHEDULING LOGIC (agents.py SchedulerAgent.run, line 147-210):
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

================================================================================
## 6. EXECUTION MODEL (how plan steps become actions)
================================================================================

Plan steps are TEXT STRINGS. The planner outputs mode:"direct" with sequence[].
engine._run_agent("actor") is called. But FIRST, actions.is_python_step() checks
if the step is headless:

  HEADLESS (actions.py execute_step, line 350-394):
    "exec <code>"       → execute_python(code) in sandboxed namespace
    "exec:\n<multiline>" → same, multiline
    "read_file <path>"  → reads file from disk, returns content
    "write_file <path> <content>" → writes file + py_compile verify if .py
    "wait <seconds>"    → time.sleep

  GUI (only when gui_mode file exists):
    ActorAgent LLM resolves element IDs from SCREEN text
    Emits: click, write, press, hotkey, scroll, focus, wait
    Each verb calls raw Win32 ctypes (user32.SetCursorPos, SendInput, etc.)

EXEC NAMESPACE (actions.py execute_python, line 275-320):
  Available without import: BASE_DIR, Path, os, sys, json, time, subprocess
  Available as functions: spawn_main(goal), enable_gui(), pause_reactor()

SAFETY GATE (actions.py _verify_python_edit, line 202-216):
  After ANY .py file write:
    1. py_compile.compile(file) — catches syntax errors
    2. subprocess.run([python, -c, "import config; import engine; ..."]) — catches import errors
  If either fails → write_file returns failure, organism retries

================================================================================
## 7. FISSION MECHANICS (engine.py _fission, line 132-155)
================================================================================

Triggered when: verifier returns verdict="confirmed"
                engine._main_loop receives next="done" from _run_agent chain

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
## 8. SELF-EVOLUTION MECHANISMS (verified, ranked by immediacy)
================================================================================

MECHANISM                    LATENCY    EVIDENCE
───────────────────────────  ─────────  ────────────────────────────────────────
1. Prompt file read          instant    agents.py _load_prompt() line 591: reads
                                        from disk on EVERY LLM call, no cache
2. Lessons append            instant    agents.py _render_field "lessons": reads
                                        last 8 lines from lessons.txt every call
3. Goal hot-swap             0.15s      engine._poll_goal(): reads goal.txt each
                                        cycle, clears plan on change
4. Pause/resume toggle       0.15s      log.paused(): PAUSE_PATH.exists() check
5. GUI mode toggle           0.15s      engine._needs_screen(): GUI_MODE_PATH.exists()
6. config.X runtime patch    instant    exec("import config; config.X = Y")
                                        — only for modules using `import config`
7. Prompt mutation            instant    agents._apply_mutation(): appends RULE to
                                        prompts/<target>.txt, respects MAX_RULES=8
8. Disk edit + child spawn   ~2-5s      actions._spawn_main(): Popen(main.py)
                                        child reads modified .py from disk fresh

WHAT CANNOT BE HOT-SWAPPED without child spawn:
  - observer.py constants (SCREEN_ELEMENT_VALUE_LIMIT, PROBE_STEP_PX, etc.)
  - actions.py timing constants (DELAY_FOCUS, EXEC_TIMEOUT, etc.)
  - log.py paths (EVENTS_PATH, PAUSE_PATH — frozen at import)
  - Any structural code change (new function, new class, new verb)

WHAT DOES NOT EXIST (verified — grep found zero matches):
  - importlib.reload() — not called anywhere
  - plugins/ directory — does not exist
  - File mtime scanning — not implemented
  - Dynamic verb registration at runtime — VERBS dict built at import only

================================================================================
## 9. EVOLVED-ORGANISM-CODE/ (what remains after deduplication)
================================================================================

After verified deduplication (2026-06-11), 10 files remain:

FILE                STATUS         VERDICT
──────────────────  ─────────────  ─────────────────────────────────────────────
prompts/planner.txt DIVERGED       8 rules re: plan-exhaustion stagnation
                                   Different content from root (root has 2 rules)
                                   WHY KEEP: contains solutions to a real problem
                                   (plan all-done but goal unmet) not in root
                                   ACTION: manually merge best rules into root

prompts/verifier.txt DIVERGED      8 near-duplicate "emit done=true" rules
                                   Shows reflector meltdown (same lesson 8×)
                                   WHY KEEP: evidence of failure mode
                                   ACTION: root version's 3 rules are better,
                                   keep root, use evolved as cautionary reference

agent_worker.py     PROTOTYPE      20 lines. Threaded worker calling bb.post_event()
                                   but Blackboard defines post() — API MISMATCH
                                   WHY NOT PROMOTE: broken, would raise AttributeError
                                   ACTION: reference only, delete when plugins exist

blackboard.py       PROTOTYPE      38 lines. Thread-safe deque(maxlen=200) bus
                                   Has post(sender, text), subscribe(), get_recent()
                                   WHY KEEP: sound pattern for multi-instance comms
                                   ACTION: promote after API fix (post→post_event or
                                   fix agent_worker to call post)

endgame_tui.py      VIOLATION      29 lines. Requires `textual` pip package
                                   VIOLATES zero-dep rule. Cannot run in production
                                   ACTION: delete (reference only)

evolved_reactor.py  DEMO           94 lines. tkinter + random.choice fake tasks
                                   Capability injection concept is valid
                                   ACTION: delete (concept lives in plugin spec)

instance_comm.py    PROTOTYPE      18 lines. File-based IPC via comms/ directory
                                   Clean, zero deps, works
                                   WHY KEEP: useful for multi-instance TUI
                                   ACTION: promote when multi-instance TUI built

reactor_demo.py     DEMO           146 lines. tkinter status display
                                   ACTION: delete (production TUI replaces this)

reflect.py          ALTERNATIVE    30 lines. JSON lesson store with scoring
                                   Production uses lessons.txt (simpler, works)
                                   ACTION: defer (promote if scoring needed later)

web_sentinel.py     STANDALONE     62 lines. urllib HN + time API fetcher
                                   Zero deps. Works. Not wired to production
                                   ACTION: promote as first plugin when plugins/ exists

================================================================================
## 10. WHAT TO DO NEXT (ordered by value, with reasoning)
================================================================================

PRIORITY 1: Fix `from config import` → `import config` pattern
  WHERE: observer.py (line 9-12), actions.py (line 12-17), log.py (line 11)
  WHY: makes ALL config values live-mutable via exec without child spawn
  WHY NOT skip: the organism's FIRST mutation was SCREEN_ELEMENT_VALUE_LIMIT
    which is frozen in observer.py — the very file that uses it. This defeats
    the organism's ability to tune its own vision without spawning a child.
  RISK: low — mechanical find/replace, verified by import check
  TEST: python -c "import observer, actions, log; print('OK')"

PRIORITY 2: Create plugins/ directory + PluginLoader in engine.py
  WHY: the organism can already write files via exec. If plugins/ existed with
    a scanner, the organism could add capabilities (web fetch, file watcher, etc.)
    without spawn_main. This is the "missing wire" identified by HOT-SWAP-EXPLAINED.md
  IMPLEMENTATION: ~40 lines in engine.py:
    - scan plugins/*.py each cycle
    - track mtime per file
    - importlib.util.spec_from_file_location on new/changed
    - call plugin.run(board) → merge writes
    - isolate exceptions (one broken plugin can't crash reactor)
  WHY NOT skip: without this, adding any new capability requires editing
    actions.py + restarting (or spawn_main). The organism cannot evolve its
    capabilities, only its prompts and config values.
  RISK: low — additive, doesn't modify existing loop logic

PRIORITY 3: Promote web_sentinel.py as first plugin
  WHY: proves the plugin system works end-to-end
  HOW: move to plugins/web_sentinel.py, add def run(board) wrapper
  TEST: start reactor, observe plugin event in log

PRIORITY 4: Add MutatorAgent (code evolution equivalent of ReflectorAgent)
  WHY: the reflector mutates prompts when stagnating. The mutator would mutate
    plugins when a plugin is failing. Completes the self-evolution story.
  CONSTRAINTS: only writes to plugins/ and config.py. Never touches engine/log/win32.
  WHY NOT NOW: depends on Priority 2 (plugins/ must exist first)
  RISK: medium — needs careful constraint prompting to prevent destructive mutations

PRIORITY 5: Multi-instance TUI columns
  WHY: the organism already spawns children (proven in M4 evening run). Currently
    you can only see one instance at a time. Side-by-side columns would show
    parent + child(ren) simultaneously.
  DEPENDS ON: instance_comm.py (promote from evolved-organism-code)
  WHY NOT NOW: cosmetic, not capability. Reactor works fine with single view.

================================================================================
## 11. THINGS TO NOT DO (failure modes from existing evidence)
================================================================================

DO NOT add pip dependencies. The zero-dep rule is load-bearing: the organism
  can exec("import X") only if X is stdlib or in-tree. Adding pip deps means
  the organism cannot self-install capabilities at runtime.

DO NOT use importlib.reload() on core modules (engine, agents, actions, log).
  Reload is fragile with stateful modules. The plugin pattern (new files, fresh
  import) is safer. Core modules stay fixed; behavior lives in prompts+plugins.

DO NOT change events.jsonl format {n, t, phase, d}. The TUI, m4_merge_test.py,
  and forensic analysis all parse this format. Breaking it loses traceability.

DO NOT rename board dict keys. snapshot.json and event logs reference them by
  name. Renaming breaks backward compatibility with saved sessions.

DO NOT remove _verify_python_edit from actions.py. This is the organism's
  immune system — it prevents self-written syntax errors from persisting.
  Without it, one bad exec could corrupt the codebase permanently.

DO NOT let the reflector mutate the same prompt more than PROMPT_MAX_RULES=8
  times. The evening M4 run proved what happens: 24 reflect cycles appending
  near-identical rules = reflector meltdown. The cap is correct and essential.

DO NOT add docstrings. The codebase is intentionally comment-minimal.
  Self-documenting names + this AGENTS.md = the documentation layer.

================================================================================
## 12. RUNTIME ARTIFACTS (gitignored, created on run)
================================================================================

FILE                CREATED BY       PURPOSE
──────────────────  ─────────────    ──────────────────────────────────────────
events.jsonl        log.init()       Primary event log (append-only)
events-<pid>.jsonl  log._acquire     Child instance log (when lock held)
snapshot.json       engine._save()   Board state for TUI reading
goal.txt            main.py/TUI      Current goal (polled every 0.15s)
pause               log.set_paused   Existence = reactor paused
gui_mode            enable_gui()     Existence = observer scans screen
lessons.txt         _write_lesson    Append-only reflector knowledge
disabled.json       TUI              Agent enable/disable toggles
.endgame.lock       log._acquire     Lock file (PID of log owner)
respawn.json        main.py          Contract for child spawn params
m4_posterity_ok.json organism exec   Proof artifact from M4 posterity run

================================================================================
## 13. CONFIG REFERENCE (config.py — all 116 lines, grouped)
================================================================================

PATHS: BASE_DIR, PROMPTS_DIR, SCHEMAS_DIR, EVENTS_PATH, SNAPSHOT_PATH,
  LESSONS_PATH, DISABLED_PATH, GUI_MODE_PATH, GOAL_PATH, PAUSE_PATH,
  RESPAWN_PATH, LOG_LOCK_PATH

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

================================================================================
## 15. PROVEN CAPABILITIES (from M4 event logs — not theoretical)
================================================================================

PROVEN (commit eff78fb + local evening logs):
  ✓ Self-launch: TUI → subprocess.Popen(main.py) → event #1 phase:start
  ✓ Self-edit config: exec rewrote SCREEN_ELEMENT_VALUE_LIMIT 500→1000 (event #357)
  ✓ Prompt mutation: reflector appended RULE to planner.txt (event #359)
  ✓ Spawn child: exec spawn_main(posterity_goal) (event #213)
  ✓ Pause self: exec pause_reactor() (event #215)
  ✓ Child inheritance: child booted on parent-modified disk (events-1960.jsonl #1)
  ✓ Child fission: child verified milestone, fissioned (events-1960.jsonl #662-663)
  ✓ Dual stop: parent #427, child #667 — two independent completions
  ✓ Hot goal swap: goal.txt modified → reactor pivoted immediately
  ✓ GUI automation: Opera browser, LinkedIn post, X.com interaction
  ✓ Safety gate: py_compile + import check prevented bad .py writes

NOT YET PROVEN:
  ✗ importlib.reload on any module (not implemented)
  ✗ Plugin loading from plugins/ directory (not implemented)
  ✗ Code mutation by MutatorAgent (agent doesn't exist yet)
  ✗ Multi-instance TUI display (not implemented)
  ✗ Resurrection (parent exits, not just pauses, after spawn)

================================================================================
## 16. ENTRY POINTS (how to run)
================================================================================

# Standard launch (TUI dashboard + reactor):
python tui.py "Your goal here" --backend lmstudio --event-budget 500

# Headless launch (no TUI, direct reactor):
python main.py "Your goal" --backend lmstudio --event-budget 200

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
  6. config.py values using `import config; config.X` pattern are live-mutable
  7. config.py values using `from config import X` are FROZEN — need restart/spawn
  8. The organism can write files via exec — don't rely on paths being constant
  9. Test with: python main.py "simple goal" --event-budget 5 (minimal run)

================================================================================
END OF AGENTS.md
================================================================================
