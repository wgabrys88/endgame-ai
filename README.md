# endgame-ai

A **human operator in digital form** on Windows 11 — wiring harness, not chat agent. Python is the body. Desktop is the world. `wiring.json` is the nervous system. Git is firmware memory.

**Tag `ooo-unification`:** spec freeze. **Branch `main`:** flat-root refactor in progress (see Progress).

---

## Progress (live)

| Phase | Status | Notes |
|-------|--------|-------|
| 0 Observation | **done** | Hierarchical `desktop_tree_text`; focused window first; smart cell dedupe; char budget via `observe_config` |
| 1 Flat root + registry | **done** | `node.py`, `registry.py`, 10 organ `*.py` at root; `organism_nodes/` deleted |
| 2 LlmNode organs | **done** | LLM organs use `LlmNode`; mechanical organs use `MechanicalNode` pattern |
| 3 evolution.py | **done** | Git firmware from old `nodes.py`; `nodes.py` deleted |
| 4 xai inline | **done** | Transport merged into `brain.py`; `brain_transports/` deleted |
| 5 organism._tick | **done** | Single tick path; error routes into recovery loop |
| 6 desktop slim | **done** | One `observe()` contract; `Desktop` class removed |
| 7 slim wiring | **done** | v2 wiring: topology + prompts + limits only |
| 8 contract_check | **done** | Registry ↔ topology equality |
| 9 fail-hard | **partial** | execute/reflect/planner hard errors; tuple coerce removed |
| 10 request limits | **done** | `limits` + `brain._preflight_request` + observation cap |
| 11 self-narrating goal | **done** | `body_signals.py`; planner requires `goal_narration` + `intent[]` each tick |
| 12 operator visibility | **done** | `[organism]`/`[observe]`/`[brain]` progress on stdout (no silent long steps) |

**Last verified:** observe → 2409-char tree (Chrome/IDE visible). Full loop needs `XAI_API_KEY`; observe scan ~30–90s at `step_px=32` — progress prints every row band.

**Operator rule:** long steps always print to stdout (`[observe] scan 42%…`, `[brain] calling transport…`). Never silent sleep.

---

## Prompt engineering (KV cache + capabilities)

Every organ prompt is two layers — **static (cacheable)** in system message, **dynamic (runtime)** at end of user JSON.

**System message order (stable → cacheable):**

1. `ORGAN_CORE` — technical computer-control identity + living organism vision + exploratory stance
2. `ORGAN_IDENTITY[organ]` — organ role + **declared capabilities** (execute: unsandboxed full Python/subprocess/ctypes on Windows)
3. `wiring.prompts[organ]` — short record hint (not a JSON schema wall)

**User message order (dynamic tail for KV reuse):**

1. `goal`, `goal_narration`, `state`, `step`, `evidence`, `failure`, `git_context`, …
2. **Last keys:** `fresh_observation`, `observation`, `workspace_manifest`

**Design rules:**

- Identity = precision machine control **and** adaptive organism psychology
- Prompts tell the model what it **can** do (execute: any local code; self_modify: git diffs)
- Avoid over-specified JSON schema in prompts — `json_object` output + Python `record_type` check is enough; giant schema blocks were removed as overcomplication
- `prompt_cache_key` per run; stable prefix optional for `git_evolution_patch`
- `limits.max_request_chars` fail-hard before API call — prevents token explosion from LLM mistakes (e.g. listing entire disk in payload)

---

## Architecture (current)

```
organism.py → registry.NODE_REGISTRY → organ.run(ctx) → bus.NodeOutput
brain.think(organ=…) → xai API (inline) → JSON record
evolution.apply_evolution_patch → git apply → contract_check → commit/push
desktop.observe → hierarchical desktop_tree_text
```

Flat root organs: `planner.py` … `error.py`. No `importlib` node loader.

---

## Self-narrating goal

User seed `goal` + runtime `goal_narration` (planner-maintained). Atemporal intent — replan as battery, focus window, failures change. Execute may read OS signals locally; planner re-narrates in `intent[]`.

---

## CLI

```bash
python organism.py "open notepad"
python organism.py --execute-node observe ""
python contract_check.py
```

`comms/control.json` (`run`|`pause`|`step`), `stop.txt` abort.

---

## Observation

Win32 hover scan → hierarchical tree: FOCUS → WINDOWS (by hwnd, focused first) → per-window cells → compact GRID. Config: `wiring.observe_config` (`max_tree_chars`, `max_windows`, `max_cells_per_window`, `step_px`).

Fail-hard: empty `desktop_tree_text` raises.

---

## Execute (unsandboxed)

`exec(code, ns)` with full stdlib + subprocess + ctypes + `state`/`wiring`/`goal`. No sandbox. Safety = operator + topology.

---

## Self-modify (git firmware)

`self_modify` organ → `git_evolution_patch` → `evolution.apply_evolution_patch` → immune contract (protected core + organ files, unified diffs, `contract_check` before commit) → `commit_self_evolution` → push.

---

## Limits (`wiring.limits`)

| Key | Default |
|-----|---------|
| `max_request_chars` | 120000 |
| `max_observation_chars` | 8000 |
| `max_workspace_manifest_files` | 40 |

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