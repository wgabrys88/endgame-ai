# endgame-ai

A **human-operated living organism** on Windows 11. Python is the body. The desktop is the world. `wiring.json` is the nervous system. Git is firmware memory.

This is not a chat agent. It is a **wiring harness**: a scheduler runs **hotswappable nodes** in a fixed topology. Each node emits one signal and one state patch. The LLM is a peripheral used only by nodes that need it.

**Constraints:** Windows 11 only. Stdlib + ctypes only (no pip). Unsafe by design — the operator watches it.

---

## Current size (2026-07-04)

| Area | Lines | Files |
|------|------:|------:|
| Core Python (`organism`, `nodes`, `brain`, `desktop`, `win32_api`, `bus`, `contract_check`, `stop_check`, `export_topology`) | 2,050 | 9 |
| `brain_transports/xai.py` | 141 | 1 |
| `organism_nodes/*.py` | 287 | 10 |
| **Python subtotal** | **2,478** | **20** |
| `wiring.json` | 118 | 1 |
| `README.md` (this file, pre-rewrite was 231) | — | 1 |
| `LICENSE` | 21 | 1 |
| **Project total** | **~2,617** | **23 tracked** |

Roughly **40% of wiring.json** and **15% of Python** is duplication, dead code, or ceremony that does not change behavior. Target after refactor: **~1,650 lines** (−37%) with the same organs and topology.

---

## How it works today

```
Goal → planner → scheduler → observe → execute → verify
                              ↑___________| step_denied → reflect → retry/replan/escalate/give_up
execute → frame_action (on failure)    escalate → self_modify → planner
```

**CLI**

```bash
python organism.py "open notepad"              # full loop
python organism.py --execute-node observe ""     # single hotswapped node
python organism.py --start-node reflect "..."    # start mid-topology
python contract_check.py                       # immune system
```

**Operator controls:** `comms/control.json` (`run` | `pause` | `step`), `stop.txt` to abort.

---

## What is wrong (architecture audit)

These are not style issues. They inflate LOC and break the “everything is a node” model.

### 1. Subdirectories for nodes and transports

`organism_nodes/` and `brain_transports/` exist only because `nodes.py` loads them with `importlib`. That adds path config in `wiring.json`, dynamic loading, and `contract_check` path rules. **Nodes should live at repo root** next to `organism.py`. One directory. One mental model.

### 2. The same metadata stored four times

| Copy | Where |
|------|--------|
| Node kind, signals, inputs, writes | `wiring.json` → `nodes` |
| Same again | each file → `DATASHEET = bus.datasheet(...)` |
| Same again | `wiring.json` → `signals` (human comments on edges) |
| Same again | `wiring.json` → `record_types` |

Topology edges already define legal signals. **Delete `nodes`, `signals`, and `record_types` blocks from wiring.** Node classes own their contract.

### 3. `nodes.py` is a god-module (521 lines)

It mixes: dynamic node loader, unused `BaseNode`, dead `build_capability_runtime`, topology export, git evolution apply/commit/rollback. **Four domains, one file.** Evolution alone is ~350 lines and belongs in `evolution.py`. Registry belongs in `registry.py` (~40 lines).

### 4. Half-abstractions and dead code

| Item | Problem |
|------|---------|
| `BaseNode` | Used only by `planner`. Other LLM nodes copy-paste `brain.think` + validate + `bus.emit`. |
| `build_capability_runtime` | ~80 lines. Never called. `execute` uses a hand-built `exec` namespace. |
| `desktop.last_desktop_tree` / `last_action_index` | Always empty stubs from deleted UIA tree era. |
| `Desktop` class | Duplicates module-level `observe()`; only one path sets `desktop_tree_text`. |
| `_RECORD_DATA_SCHEMAS` in `brain.py` | Never used. Stale vs real contract. |
| `bus.coerce_node_output(tuple)` | Legacy. All nodes should return `NodeOutput` only. |
| `reflect` Python override | Second routing policy on top of LLM + prompt. |
| `execute` conclusion fallbacks | Invalid conclusion silently becomes `CANNOT`. Fail-hard violation. |
| Stable prefix text | Still describes “node id” / UIA — wrong for hover grid. |
| `organism.run` exception handler | Routes to `error` then **exits without resuming loop**. |
| `run` vs `run_single_node` | ~40 lines duplicated tick logic. |

### 5. Prompt boilerplate in wiring

Every prompt repeats the same SPI bus identity paragraph (~400 chars × 7 organs). **Move shared identity to `brain.think` prefix.** Per-organ prompts keep only organ-specific schema and payload hooks.

### 6. `contract_check.py` validates fiction

It requires `build_capability_runtime`, `Desktop` methods, `organism_nodes/` paths, and minimum byte sizes. It encodes the old architecture. **Shrink to:** wiring topology consistency, node registry completeness, required root files exist, `run(ctx)` on each node class.

---

## Target architecture (flat, OOP, fail-hard)

### Layout after refactor

```
organism.py          # loop + control + single _tick() — ~90 LOC
registry.py          # NODE_REGISTRY: name → Node instance — ~50 LOC
evolution.py         # git patch apply/commit — ~280 LOC
bus.py               # NodeOutput, emit, validate_signal, briefs — ~45 LOC
brain.py             # think + xai transport inline — ~260 LOC
desktop.py           # observe() one path — ~120 LOC
win32_api.py         # ctypes body primitives — ~200 LOC (unchanged)
stop_check.py        # ~50 LOC

planner.py           # Node subclass — ~18 LOC
scheduler.py         # ~15 LOC
observe.py           # ~12 LOC
execute.py           # ~35 LOC
frame_action.py      # ~18 LOC
verify.py            # ~22 LOC
reflect.py           # ~18 LOC
self_modify.py       # ~45 LOC
satisfied.py         # ~8 LOC
error.py             # ~10 LOC
node.py              # abstract LlmNode + MechanicalNode — ~55 LOC

contract_check.py    # ~70 LOC
export_topology.py   # optional; merge into organism --topology — ~0 if deleted
wiring.json          # topology + prompts + model + timing — ~55 LOC
```

**23 Python files at root** (more files, fewer lines). No subdirectories for source. `paths.nodes` and `paths.brains` **removed** from wiring.

### OOP model (minimal, not enterprise)

```python
# node.py
class Node(ABC):
    name: str
    def run(self, ctx: Ctx) -> NodeOutput: ...

class LlmNode(Node):
    record_type: str
    prompt_key: str
    def payload(self, ctx) -> dict: ...
    def signal(self, data: dict) -> str: ...
    def patch(self, record: dict, ctx) -> dict: ...
    def run(self, ctx):
        record = brain.think(self.prompt_key, self.payload(ctx), ...)
        if record["record_type"] != self.record_type:
            raise RuntimeError(...)
        return bus.emit(self.signal(record["data"]), self.patch(record, ctx), record=record)

class MechanicalNode(Node):
    def run(self, ctx) -> NodeOutput: ...
```

Each organ file is **only** `class Planner(LlmNode): ...` plus `NODE = Planner()` or registry entry. No free `run(ctx)` + duplicate `DATASHEET`.

**Registry (fail-hard):**

```python
NODE_REGISTRY: dict[str, Node] = {
    "planner": Planner(),
    ...
}

def call_node(name: str, ctx) -> NodeOutput:
    node = NODE_REGISTRY[name]  # KeyError if missing — no dynamic import
    out = node.run(ctx)
    bus.validate_signal(ctx["wiring"], name, out.signal)
    return out
```

`topology.nodes` in wiring must match `NODE_REGISTRY.keys()` exactly. `contract_check` enforces set equality. **No branching** for unknown nodes.

### Hotswap / single-node CLI (unchanged behavior, simpler code)

```bash
python organism.py --execute-node observe ""
```

Implementation: `_tick(wiring, state, node_name, goal)` once. Full loop and single-node both call it. Single-node returns after one call. **No duplicated self_modify apply block.**

### Fail-hard rules (no silent edge cases)

| Today (soft) | After (hard) |
|--------------|--------------|
| `default_control` setdefault chain | `control_default` in wiring must be complete or `RuntimeError` |
| Invalid execute conclusion → `CANNOT` | `RuntimeError` on bad record |
| reflect overrides LLM signal | LLM signal only; escalation in prompt |
| `desktop.observe` returns `grid_text` without `desktop_tree_text` | `observe()` always sets `desktop_tree_text` or raises |
| `coerce_node_output` accepts tuple | `NodeOutput` only |
| `node_datasheets` swallows load errors | Registry is static; import errors fail at startup |
| Error in loop → return `None` | Resume loop at `error` node or re-raise |

Construct invariants so invalid states cannot be represented. The organism will self-modify later — give it a **small, rigid** core.

---

## wiring.json reduction

**Keep**

- `schema`, `topology` (cycle_start, nodes, edges)
- `prompts` (shortened per-organ)
- `model` (transport, organs tuning)
- `observe_config`, `timing`, `self_modify`, `control_default`, `paths` (state, control, runtime_log only)

**Delete**

- `bus` prose block (SPI is code in `bus.py`)
- `signals` (duplicate of edges)
- `nodes` (duplicate of Python registry)
- `record_types` (duplicate of LlmNode.record_type + prompts)
- `paths.nodes`, `paths.brains`

**Prompt compression**

Shared prefix injected by `brain.think`:

```
You are organ {name} in endgame-ai. Emit one JSON record. Topology routes your signal only.
```

Per-organ prompt: schema line + `{{goal}}` placeholders only. **Estimated wiring save: ~50 lines.**

---

## LOC budget (confident targets)

| Module | Now | Target | How |
|--------|----:|-------:|-----|
| `nodes.py` | 521 | 0 | → `registry.py` + `evolution.py` + `node.py` |
| `registry.py` + `node.py` + `evolution.py` | — | 375 | split |
| `organism_nodes/` | 287 | 0 | → 10 root `*.py` nodes (~161) |
| `organism.py` | 225 | 90 | `_tick`, fix error loop |
| `brain.py` + `xai.py` | 515 | 260 | merge transport, drop dead schemas |
| `desktop.py` | 228 | 120 | one `observe()`, drop `Desktop` |
| `bus.py` | 88 | 45 | drop mermaid or move to CLI flag |
| `contract_check.py` | 184 | 70 | registry + topology only |
| `wiring.json` | 118 | 55 | delete duplicate blocks + shorten prompts |
| `README.md` | 231 | 120 | this doc stabilizes shorter |
| Dead stubs (`build_capability_runtime`, etc.) | ~120 | 0 | delete |

**Project total: ~2,617 → ~1,650 lines** (same features, same topology, same CLI flags).

---

## Implementation order

Pure reduction. No new organs. No removed organs.

| Phase | Work | LOC delta |
|-------|------|----------:|
| **1** | Add `node.py` + `registry.py`; static imports; flat root node files; delete `organism_nodes/` | −80 |
| **2** | `LlmNode` for all LLM organs; delete per-file think boilerplate | −100 |
| **3** | Extract `evolution.py`; delete `nodes.py` | −70 |
| **4** | Merge `xai.py` into `brain.py`; delete dead schema/prefix lies | −90 |
| **5** | `organism._tick()`; fix error resume; delete `run_single_node` dup | −50 |
| **6** | `desktop.observe` one contract; delete `Desktop`, stubs | −60 |
| **7** | Slim `wiring.json`; slim `contract_check.py` | −120 |
| **8** | Delete `build_capability_runtime`; wire `execute` to `body.exec_ns(ctx)` or inline minimal ns | −40 |
| **9** | Fail-hard pass: remove fallbacks listed above | −30 |

After each phase: `python -m compileall -q .` and `python contract_check.py`.

---

## What the organism is allowed to evolve

Self-modify may patch prompts, topology edges, organ tuning, and node implementations. It may **not** break:

- SPI bus: one signal + one patch per tick
- `NODE_REGISTRY` names match `topology.nodes`
- `contract_check.py` passes before commit
- Root-only layout (no new subdirectories for organs)
- Fail-hard: no new silent fallbacks

The immune system contract updates in the same refactor — protected paths become `planner.py` not `organism_nodes/planner.py`.

---

## Observation (body)

Win32 hover scan → Excel grid (`A1=ibeam B1=hand`). No UIA. Config: `wiring.json` → `observe_config`.

Output contract (fail-hard after refactor):

```
desktop_tree_text  # grid text, always set by observe()
focused_title
observed_at
fresh_scan
```

---

## Brain

Single transport: `xai` (API or CLI). Fail-hard if API credentials are unset in API mode (env var name is in `wiring.json`, never commit values).

Per-organ tuning: `model.organs`. Logging: `comms/*_brain.jsonl`.

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