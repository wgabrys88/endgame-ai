AGENTS.md - Session State (2026-06-10)

MILESTONE: M4-adjacent — autonomous prompt self-evolution proven locally
Branch: refactor-v4 @ 8901988 (8 commits ahead of origin/refactor-v4, not pushed)
main: untouched @ 109173b

SESSION SUMMARY:
  Consolidated git to single dev branch (refactor-v4). Code reduction landed
  (config slim, constants in win32/actions/tui). Flow TUI replaces butterfly
  plot. System autonomously rewrote all four prompts from lessons + events —
  2 fissions, 75 work events, zero .py edits.

WHAT CHANGED (local, unpushed):
  1. UNIFIED EXECUTION: cmd/read_file/write_file/wait run headless via execute_step
  2. CONFIG SLIM: GUI/UIA constants in win32.py; input constants in actions.py
  3. TUI: Flow diagram (MATH → LOOP → SIDE), sync repaint, no braille Lorenz
  4. PROMPT SOUL EVOLUTION: All prompts/*.txt rewritten from runtime evidence
  5. VERIFIER: Denies read-only milestones on self-evolution goals
  6. REFLECTOR: Anti-duplication guards before mutating prompts

ARCHITECTURE (unchanged):
  Math thread (stagnation → lorenz → pid) + scheduler + planner/actor/verifier/reflector
  Headless-first; observer only when gui_mode file exists
  MAX_HISTORY: 100 entries (config.MAX_HISTORY)

RUNTIME FILES (gitignored):
  events.jsonl, snapshot.json, lessons.txt, gui_mode, disabled.json
  agent-tools/, terminals/, _debug_context_dump.txt

PROVEN THIS SESSION:
  - Prompt self-evolution: read README + prompts + lessons + events → rewrite 4 prompts → verified
  - Code self-evolution (prior): reduce.py broke config — fixed manually; lesson #37 holds

OPEN ISSUES:
  1. Post-fission idle: planner mode:done loops after goal satisfied (needs halt on done)
  2. Post-edit syntax check: no import gate after write_file on .py files
  3. Push review pending — 8 local commits on refactor-v4

FILES:
  12 .py core + debug_context.py + acp_client.py
  4 prompts, 4 schemas
  ~3000 LOC core

DEBUG:
  python debug_context.py planner --goal "your goal"
  Requires gui_mode for screen data. Writes _debug_context_dump.txt (gitignored).