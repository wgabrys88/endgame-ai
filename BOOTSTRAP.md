# BOOTSTRAP.md — endgame-ai Session Bootstrap

## MoE Vision
**endgame-ai** is a living Windows desktop organism, not a traditional agentic CCA. Python = mechanical body; `wiring.json` = mutable genome. Nodes and brain transports are hot-swappable modules copied from `seed_*/` → `live_*/` at runtime. The ROD loop (Reason→Observe→Decide with pluggable reasoning feedback) is in `brain.think()` and is the core innovation enabling 4B models to self-evolve. No fallbacks — fail-hard always. Self-modification = rewiring `wiring.json` AND writing new node files to `live_nodes/`.

**The execute node IS the action layer, the evolution layer, and the desktop automation layer — unified.**

## State (2026-07-01, commit 368a091)
- **Branch:** `unified-archBRAINZ` (clean, pushed)
- **Core files:** `brain.py` (Transport protocol, BaseTransport, ReasoningStrategy, config resolution), `nodes.py` (BaseNode ABC), `organism.py` (loop, error routing, `--max-ticks`), `wiring.json` (v1 schema with reasoning + error topology)
- **Transports:** `seed_brains/{openai,file_proxy,opencode,xai}.py` + stub `browser_ai.py`; legacy archived to `archive/`
- **Nodes:** `seed_nodes/{planner,decide,verify,reflect}.py` use BaseNode (~10 lines each); `observe,act,self_modify,error` mechanical; `satisfied,scheduler` orphaned (future plan-completion)
- **Topology:** 8-node cycle with `error` node + recovery edges; `halt` signal for clean exit
- **Workbench:** Modular ES6: `workbench.py` + `workbench.html` + `workbench.{css,js,api,state,graph,editor}.js`
- **Stop mechanism:** `stop_check.py` (stop.txt + PID tracking) — to be removed in Phase 5D

## Plan
**Phase 5 — Unification & Self-Evolution** (next)

### Phase 5A: Foundation — Desktop + Observe
1. Replace `desktop.py` with main's 1600-line version (UIA COM, Element/Observation, hover probing, window tokens, bounded tree, `configure_observation()`)
2. Rewrite `seed_nodes/observe.py` → call `Desktop.observe()` → return `{screen, elements, snapshot, focused_title}`
3. Add `observe_screen()`, `last_observation_snapshot()`, `get_focused_title()` to `nodes.py`
4. Merge main's `observe` config + `verbs` + `prompts.roles` + `topology` with scheduler into `wiring.json`
5. Test: `python organism.py --reset --max-ticks 3 "observe desktop"` → verify `state.json` has `screen`, `elements`, `snapshot`

### Phase 5B: Execute Node — Core Unification
1. Create `seed_nodes/execute.py` — Grok writes Python, `exec()` runs it with full desktop namespace
2. Add `build_execute_namespace(ctx)` to `nodes.py` with raw desktop actions + convenience verbs + system modules + self-modify helpers
3. Delete `seed_nodes/decide.py`, `seed_nodes/act.py`, `actions.py`
4. Update `wiring.json` topology: remove `decide`/`act`, add `execute`; add `execute` prompt role
5. Test: `python organism.py --reset --max-ticks 5 "open notepad"` → Grok writes `subprocess.Popen(["notepad.exe"])`

### Phase 5C: Self-Modify + Scheduler + Verify/Reflect
1. Resurrect `seed_nodes/scheduler.py` — step index management, plan completion detection
2. Rewrite `seed_nodes/self_modify.py` — output `wiring_patch` record with `wiring_patches`, `node_writes`, `node_deletes`
3. Extend `nodes.py:apply_wiring_patch()` — handle wiring patches + node file writes + atomic wiring save
4. Enhance `seed_nodes/verify.py` — evidence-based intent judgment (not literal matching)
5. Enhance `seed_nodes/reflect.py` — concrete diagnosis + specific suggestion, routes to `retry`/`replan`/`escalate`/`give_up`
6. Update `wiring.json` prompts from main branch patterns
7. Test: Self-modify changes temperature, adds new skill node, modifies execute.py

### Phase 5D: Cleanup + Polish
1. Remove `control.json` pause/step logic from `organism.py`; remove `--max-brain-calls` arg
2. Remove control endpoints from `workbench.py`; keep read-only status + wiring viewer + transport probe + brain test
3. Clean workbench UI — remove pause/step, keep dashboard
4. Keep `stop_check.py` for external kill signal (or remove if `--max-ticks` only)
5. Regenerate `README.md` from chunks (this document)
6. Update `BOOTSTRAP.md` with Phase 5 state
7. Full integration test: `python organism.py --reset --max-ticks 20 "open notepad, write hello, save as test.txt"`

## Done (Phases 1-4)
- ✅ Archived legacy transports: `grok_build.py`, `grok_build_api.py`, `xai_responses.py` → `archive/`
- ✅ `Transport` Protocol + `BaseTransport` ABC — common logging, validation, error handling
- ✅ `BaseNode` ABC — 4 brain-calling nodes reduced from ~14 to ~10 lines each
- ✅ Consolidated `xai_responses.py` + `grok_build.py` → `xai.py` (API + CLI modes)
- ✅ Normalized `wiring.json`: `transport_config.{transport}` + `global` keys
- ✅ Verified end-to-end: `openai` (LM Studio), `file_proxy`, `opencode` transports
- ✅ **Pluggable ROD ReasoningStrategy** — `TwoPassStrategy`, `SinglePassStrategy`, `NativeReasoningStrategy`, `CustomStrategy` configurable per transport
- ✅ **Error-handling topology** — `error` node + edges from all nodes, `halt` signal for clean exit
- ✅ **Modern Workbench** — SVG topology graph, hybrid wiring editor, transport probe, ROD test, mobile-responsive
- ✅ README rewritten with full handover prompt (773 lines)

## Scientist Mode (always active)
1. Claims: (a) tested-in-this-session or (b) untested-prior. Untested → propose falsifying experiment.
2. No hedging, no industry norms, no simulated measurements.
3. Tool insufficient → "experiment pending" and stop.
4. Counter-intuitive = hypothesis to test, not error to correct.
5. On evidence: update state plainly. "I was wrong; measurement shows X" is valid.
6. Audit prior turns for violations (hedging, conventions, invented data, refusal to update).

## Fail-Hard Rule
No fallbacks. If transport fails, organism stops with clear error. This is self-evolution.

## Quick Commands
```powershell
# Validate
python -m py_compile brain.py nodes.py organism.py workbench.py desktop.py
python -c "import py_compile, pathlib; [py_compile.compile(str(p), doraise=True) for d in ['seed_nodes','seed_brains'] for p in pathlib.Path(d).glob('*.py')]"

# Run (change model.transport in wiring.json)
python organism.py --reset --max-ticks 5 "open notepad"

# Workbench
python workbench.py  # http://127.0.0.1:8800/
```

## Handover
Next session: Begin Phase 5A. Port `desktop.py` from main, rewrite `observe` node, merge wiring.json. Then Phase 5B: create `execute` node. The README.md contains the complete specification — implement exactly as written.