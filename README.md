# endgame-ai

A forensic desktop automation organism. Python is the body, the desktop is the world, wiring.json is the nervous system, JSON records are the bus, git is firmware memory.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   planner   │────▶│  scheduler  │────▶│   observe   │────▶│  execute    │
│ (decompose) │     │  (select)   │     │  (scan UIA) │     │   (act)     │
└─────────────┘     └─────────────┘     └─────────────┘     └──────┬──────┘
                                                                     │
                                              ┌──────────────┐      │
                                              │  self_modify │◀─────┤
                                              │  (evolve)    │      │
                                              └──────────────┘      │
                                                    ▲               │
                                                    │               ▼
                                              ┌──────────────┐ ┌───────────┐
                                              │   verify   │ │  reflect  │
                                              │  (judge)   │ │ (diagnose)│
                                              └─────────────┘ └───────────┘
```

**Topology** (from `wiring.json`):
- `planner` → `scheduler` → `observe` → `execute` → `verify`
- `verify.step_confirmed` → `scheduler` (advance step)
- `verify.step_denied` → `reflect` → `retry`→`observe` | `replan`→`planner` | `escalate`→`self_modify` | `give_up`→`satisfied`
- `execute.frame` → `frame_action` → `framed`→`execute`
- `error` node routes failures back to `planner`/`reflect`/`halt`

## Key Components

| File | Role |
|------|------|
| `organism.py` | Main loop, pause/step control, topology routing |
| `brain.py` | Transport-agnostic LLM chokepoint (xAI, OpenAI, file_proxy, opencode) |
| `nodes.py` | Hot-swappable node loader, capability runtime, self-modify pipeline |
| `bus.py` | NodeOutput, signal validation, state briefs |
| `desktop.py` | Windows UIA COM observation (hover scan, window tokens, action index) |
| `contract_check.py` | Immune system - AST + wiring validation (runs after every self-modify) |
| `wiring.json` | Nervous system - topology, prompts, model config, observe config |
| `organism_nodes/*.py` | One file per topology node (planner, execute, verify, reflect, self_modify, etc.) |
| `brain_transports/*.py` | Single `call(messages, cfg)` export per transport |

## External Control (Pause/Step/Run)

Edit `comms/control.json` - no code changes needed:
```json
{"mode": "pause", "step_token": 0}   // pause before next node
{"mode": "step", "step_token": 1}    // advance one node
{"mode": "run"}                      // resume
```

## Quick Start

```bash
# 1. Set xAI API key (required for default wiring)
set XAI_API_KEY=your_key_here

# 2. Run with a goal (10 ticks max)
python -m organism "Open Opera browser and navigate to x.com" --max-ticks 10 --reset

# 3. Watch runtime
tail -f comms/runtime.ndjson

# 4. Pause/step externally
echo {"mode": "pause", "step_token": 0} > comms/control.json
```

## Observation System

- **Hover scan**: Grid probes across screen/window (configurable `step_px`, `delay_ms`)
- **Target modes**: Full desktop (`target_window_only=false`) or foreground window only (`true`)
- **Outputs**:
  - `desktop_tree_text` - semantic indented tree for brain
  - `action_index` - body-side targeting data (px, py, hwnd, rect) keyed by same IDs
  - `observation_artifact` - raw JSON in `comms/observations/{timestamp}.json`

## Capability Runtime (available to execute node)

```python
# Node-based actions (preferred - use IDs from action_index)
click_node(id)
scroll_node(id, amount)
node_by_id(id)
action_nodes(action="click")

# Raw coordinate actions
click(x, y, hwnd=0)
type_text(text)
press_key(key)
hotkey(keys)
scroll(x, y, amount, hwnd=0)
focus_window(target)  # "W1", "title substring", or "hwnd:12345"
open_url(browser, url)

# pyautogui-compatible facade
pyautogui.click(x, y)
pyautogui.write(text)
pyautogui.press("enter")
pyautogui.hotkey("ctrl", "l")
pag = pyautogui  # alias

# Stdlib
subprocess, ctypes, os, sys, json, re, time, pathlib, math, random, types
```

## Self-Modification Pipeline

Trigger: `reflect.escalate` → `self_modify` node runs → `nodes.apply_evolution_patch()` → `git apply --check` → `contract_check.py` → `git commit` → reload wiring

**Protected files** (require unified diffs, not full rewrites):
- `organism_nodes/*.py`, `brain_transports/*.py`
- `brain.py`, `bus.py`, `desktop.py`, `nodes.py`, `organism.py`, `stop_check.py`, `contract_check.py`, `wiring.json`

## Critical Bug Fixes (Applied)

| Bug | Fix | Location |
|-----|-----|----------|
| **App launch race** - execute→verify→observe with no delay | Added `post_execute_delay_ms` (default 3000ms) in `wiring.json`, consumed in `organism.py:run()` | `wiring.json:14`, `organism.py:172` |
| **Corrupt patch** - self_modify hallucinates line numbers | *Pending*: self_modify must read file first or use full-file replacement | `nodes.py:283` |

## Validation Pipeline (Run After Any Change)

```bash
python -m compileall -q .
python -m json.tool wiring.json
python contract_check.py
```

## File Ownership

| Path | Purpose |
|------|---------|
| `organism.py` | Main loop, step control |
| `brain.py` | Transport chokepoint, ROD pattern, stable prefix |
| `nodes.py` | Node loader, capability runtime, self-modify apply/commit |
| `bus.py` | Protocol, signal validation |
| `desktop.py` | UIA COM observation, hover scan, actions |
| `contract_check.py` | Immune system (AST + wiring) |
| `organism_nodes/*.py` | One organ per file, exports `run(ctx)` + `DATASHEET` |
| `brain_transports/*.py` | Single `call(messages, cfg)` export |
| `wiring.json` | Topology, prompts, model config |
| `state.json` | Mutable runtime state |
| `comms/control.json` | External pause/step/run |

## Extending the Organism

**New organ**: Create `organism_nodes/new_organ.py` with `run(ctx)` + `DATASHEET` → add to `wiring.json:topology.nodes` + `edges` + `prompts.new_organ`

**New transport**: Create `brain_transports/new_transport.py` with `call(messages, cfg)` → set `model.transport` in wiring

**New capability**: Add to `nodes.py:build_capability_runtime()` → available to execute immediately

**New wiring path**: Add to `self_modify.wiring_allowed_new_prefixes` before self-modify can create it

## Environment

- Windows 11 (UIA COM via comtypes)
- Python 3.10+
- xAI API key for default transport (`XAI_API_KEY`)

## License

MIT