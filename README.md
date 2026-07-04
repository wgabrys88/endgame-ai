# endgame-ai

A **human operator in digital form** — a living organism on Windows 11. Python is the body. The desktop is the world. `wiring.json` is the nervous system. Git is firmware memory.

This is **not a chat agent**. It is a **wiring harness**: a scheduler runs hotswappable nodes in a fixed topology. Each node emits one signal and one state patch. The LLM is a peripheral used only by organs that need it.

**Constraints:** Windows 11 only. Stdlib + ctypes for the body (no pip in core). Unsafe by design — the operator watches it.

**Tag `ooo-unification`:** specification freeze before flat-root OOP refactor. Coding starts on operator mark.

---

## What makes this different

| Chat agent | endgame-ai |
|------------|------------|
| Conversation loop | Topology loop (`planner` → … → `verify` → …) |
| Goal = fixed user string | Goal = **self-narrating field** (see below) |
| LLM drives everything | LLM is one organ among many |
| Sandboxed tool calls | `execute` runs **unsandboxed** `exec()` — full stdlib, subprocess, ctypes |
| Static plan | **Atemporal** intent: replan continuously as the machine changes |

---

## Self-narrating goal (atemporal)

The user provides an initial goal string. That string is **not** a rigid script. It is a **living narration** the organism maintains in state — a psychological stance toward the world that evolves as desktop dynamics change.

**Properties:**

- **Atemporal:** no strict sentence order; planner may reorder, merge, or replace intent steps every tick.
- **Self-narrating:** each brain call receives fresh observation + runtime evidence; the goal's *interpretation* updates (e.g. "finish report" becomes "save work and plug in" when battery is low).
- **Environment-coupled:** execute code may read power state, disk, focused window, failure streaks; reflect may `replan` when the narration and reality diverge.

**Example dynamic (target behavior after unification):**

```
User goal: "prepare quarterly backup"
Battery 18%  → narration shifts: prioritize snapshot, pause long copies
Battery 95%  → narration shifts: pursue full archive, verify checksums
```

Planner holds `intent[]` as the current chapter of the narration, not a frozen checklist. Scheduler picks one step; verify may deny; reflect routes `replan` back to planner with an updated story. This solves the classical planner problem of brittle upfront decomposition.

**State fields (target):** `goal` (user seed), `goal_narration` (organ-maintained interpretation), `goal_signals` (optional structured cues: power, urgency, risk).

---

## Current architecture vs proposed flat layout

### Today — nested, dynamic, duplicated

```
endgame-ai/
├── organism.py              # loop + duplicated single-node path
├── nodes.py                 # 521 LOC: loader + evolution + dead stubs
├── brain.py + brain_transports/xai.py
├── desktop.py, bus.py, win32_api.py, stop_check.py, contract_check.py
├── wiring.json              # topology + nodes + signals + record_types + prompts
└── organism_nodes/          # 10 organs loaded via importlib
    planner.py, execute.py, self_modify.py, ...
```

| Mechanism | Cost |
|-----------|------|
| `importlib` node loader | `paths.nodes` in wiring; path rules in `contract_check` |
| Metadata ×4 | `wiring.nodes`, `signals`, `record_types`, per-file `DATASHEET` |
| `BaseNode` | Used only by `planner`; other LLM organs copy-paste `brain.think` |
| `build_capability_runtime` | ~80 LOC in `nodes.py`, **never called**; `execute` uses hand-built `exec` ns |
| `Desktop` class | Duplicates module `observe()`; only class path sets `desktop_tree_text` |

### Target — flat root, static registry, fail-hard

```
endgame-ai/
├── organism.py          # loop + single _tick() — ~90 LOC
├── registry.py          # NODE_REGISTRY: name → Node instance
├── node.py              # LlmNode + MechanicalNode
├── evolution.py         # git patch apply/commit (from nodes.py)
├── brain.py             # think + xai transport inline
├── planner.py … error.py   # 10 organ files at root
├── bus.py, desktop.py, win32_api.py, stop_check.py
├── contract_check.py    # registry + topology only (~70 LOC)
└── wiring.json          # topology + prompts + model + limits (~55 LOC)
```

| Today (soft) | After (hard) |
|--------------|--------------|
| `desktop.observe()` returns `grid_text`, observe node reads `desktop_tree_text` → **empty** | `observe()` always sets `desktop_tree_text` or raises |
| Invalid execute conclusion → `CANNOT` | `RuntimeError` on bad record |
| reflect Python override on LLM signal | LLM signal only; escalation in prompt |
| Error in loop → implicit `None` return | Resume at `error` node or re-raise |
| `coerce_node_output(tuple)` | `NodeOutput` only |
| Dynamic import swallows load errors | Static imports; fail at startup |

**LOC target:** ~2,617 → ~1,650 (−37%). Same organs, same topology, same CLI.

---

## Control flow

```
Goal (self-narrating) → planner → scheduler → observe → execute → verify
                              ↑___________| step_denied → reflect → retry/replan/escalate/give_up
execute → frame_action (on failure)    escalate → self_modify → planner
```

```bash
python organism.py "open notepad"
python organism.py --execute-node observe ""
python organism.py --start-node reflect "recover from error"
python contract_check.py
```

**Operator controls:** `comms/control.json` (`run` | `pause` | `step`), `stop.txt` to abort.

---

## Process stability — `stop_check.py`

Cooperative shutdown for a long-running organism. Not a sandbox.

| Function | Role |
|----------|------|
| `register_pid(name)` | Writes `pids/{name}.pid` with `os.getpid()` at loop start |
| `check_stop(name)` | Polls `stop.txt`; if present → `unregister_pid` + `sys.exit(0)` |
| `request_stop(reason)` | Operator creates `stop.txt` |
| `clear_stop()` | Removes stop file before a new run |
| `wait_for_stop(timeout)` | Blocking poll for external orchestration |
| `kill_all_pids()` | Terminates registered PIDs via **psutil** (optional dep; not stdlib) |

**Call sites:** `organism.run` / `run_single_node` register at start; main loop and `wait_before_node` call `check_stop` every iteration; `brain.call` checks before each API request.

**Pattern:** fail-stop, not fail-safe. No graceful drain of in-flight `execute` code — operator owns risk. Target: unify `run` and `run_single_node` through `_tick()`; register PID once; `atexit` hook to `unregister_pid` on clean exit.

**Gap:** `kill_all_pids` imports psutil — violates strict stdlib-only body rule. Target: ctypes `OpenProcess`/`TerminateProcess` on Windows or document psutil as operator-only kill helper.

---

## Brain — Grok (xai) API

Transport: `brain_transports/xai.py` (merge into `brain.py` in Phase 4).

| Capability | Config surface |
|------------|----------------|
| Responses API | `url`, `model` (e.g. `grok-4.3`), `temperature`, `top_p`, `truncation` |
| Structured JSON | `response_format` / `text.format` json_schema or json_object |
| Reasoning | `reasoning.effort` (none/low/medium/high); native two-pass optional |
| Output cap | `max_output_tokens` per organ in `wiring.model.organs` |
| Web search | `tools: [{type: web_search}]` with domain filters (self_modify) |
| Prompt cache | `prompt_cache_key` from conversation id |
| Call budget | `max_brain_calls` — hard stop after N `think()` calls |
| Modes | `api` (urllib) or `cli` (`grok` subprocess) — fail-hard, no fallback |

Per-organ tuning in `wiring.json` → `model.organs` (plan, execution, git_evolution_patch, etc.).

---

## Request size guard (anti token explosion)

**Problem:** LLM mistakes can bloat outbound payloads — e.g. `execute` code that walks entire disk, or `self_modify` workspace manifest listing every file — blowing API context and cost.

**Principle:** constrain **what the body sends to the brain**, not **what execute runs locally**. Unsandboxed `exec` stays. The organism may list every file on disk in Python; it must not ship that list to Grok.

**Target `wiring.limits` block:**

```json
{
  "max_request_chars": 120000,
  "max_payload_field_chars": 16000,
  "max_observation_chars": 8000,
  "max_workspace_manifest_files": 40,
  "max_manifest_file_list_chars": 6000,
  "on_violation": "fail_hard"
}
```

**Enforcement in `brain.think()` (Phase 10):**

1. After `_with_fresh_observation`, measure `len(json.dumps(payload))`.
2. If over `max_request_chars` → `RuntimeError` with field hints (no silent truncation of whole request).
3. Per-field caps: truncate `desktop_tree_text` / grid with ellipsis + `truncated: true` flag; cap `workspace_manifest.files` count in self_modify payload builder.
4. Log preflight size to `comms/*_brain.jsonl`.
5. Stable prefix (git source bundle for self_modify) counts toward limit when `include_in_request` is true.

**Already partial:** `observe_config.max_elements`, grid `max_cols`/`max_rows` in `desktop.py`; `max_brain_calls` budget. Missing: unified preflight gate.

---

## Execute — unsandboxed code (intentional)

`organism_nodes/execute.py` builds a namespace with `subprocess`, `ctypes`, `os`, `sys`, `json`, `re`, `time`, `pathlib`, `math`, `random`, `types`, plus `state`, `wiring`, `goal`. Then `exec(code, ns)`.

- **No** syscall filter, **no** path allowlist, **no** timeout wrapper (today).
- Conclusions: `EXECUTE` | `CANNOT` | `FRAME` | `SELF_MODIFY`.
- Invalid conclusion silently becomes `CANNOT` today → **fail-hard** in unification.

This is how the digital operator touches the real machine. Safety is operator oversight + topology routing, not cage the code.

---

## Self-modify — git firmware evolution

`organism_nodes/self_modify.py` is the evolution organ. On `escalate` or execute `SELF_MODIFY`, it asks Grok for a `git_evolution_patch` record, then `nodes.apply_evolution_patch` applies locally.

### Payload assembly

| Input | Source |
|-------|--------|
| `goal`, failure, step | state |
| `runtime.evidence` | state.json path, runtime.ndjson, recent `*.txt` logs |
| `git_context` | branch, commit, remote URL, worktree status |
| `workspace_manifest` | **all** tracked + untracked repo files (size, sha) — **token risk** |
| `patch_contract` | immune rules + source SHA256 fingerprints |
| `immune_contract` | protected paths, validation commands |

### Immune contract (LLM-facing + code-enforced)

**Prompt rules (`_immune_contract`):**

- Protected: `brain.py`, `bus.py`, `desktop.py`, `nodes.py`, `organism.py`, `stop_check.py`, `contract_check.py`, `organism_nodes/*.py`, `brain_transports/*.py`
- Existing Python → `unified_diffs` only; `file_writes` for new/non-protected files
- Every touched file in `read_files`
- `contract_check.py` must pass before commit

**Code enforcement (`nodes.apply_evolution_patch`):**

- `CORE_FILES` cannot be deleted; protected prefixes cannot full-rewrite or delete
- `git apply --check` before apply; snapshot rollback on failure
- Wiring patches only under `self_modify.wiring_allowed_new_prefixes`
- Post-apply: `compileall`, `contract_check.validate_static_contract`, optional commands
- `commit_self_evolution` → git commit + optional push to `origin`

**Risk:** workspace manifest can enumerate entire repo to the API — pair with `limits.max_workspace_manifest_files`. Immune contract does not cap diff size; operator + request guard handle that.

---

## wiring.json — what stays vs goes

**Keep:** `schema`, `topology`, `prompts` (shortened), `model`, `observe_config`, `timing`, `self_modify`, `control_default`, `paths` (state, control, runtime_log only), **`limits`** (new).

**Delete in unification:** `bus` prose, `signals`, `nodes`, `record_types`, `paths.nodes`, `paths.brains`.

Shared brain prefix (replace 7× identity boilerplate):

```
You are organ {name} in endgame-ai. Emit one JSON record. Topology routes your signal only.
```

---

## Implementation order (ooo-unification)

No new organs. No removed organs. After each phase: `python -m compileall -q .` and `python contract_check.py`.

| Phase | Work | Δ LOC |
|-------|------|------:|
| 1 | `node.py` + `registry.py`; flat root node files; delete `organism_nodes/` | −80 |
| 2 | `LlmNode` for all LLM organs; drop per-file think boilerplate | −100 |
| 3 | Extract `evolution.py`; delete `nodes.py` | −70 |
| 4 | Merge `xai.py` into `brain.py`; drop dead schemas | −90 |
| 5 | `organism._tick()`; fix error resume; dedupe single-node | −50 |
| 6 | `desktop.observe` one contract; delete `Desktop`, stubs | −60 |
| 7 | Slim `wiring.json`; slim `contract_check.py` | −120 |
| 8 | Delete `build_capability_runtime`; minimal execute ns | −40 |
| 9 | Fail-hard pass (table above) | −30 |
| 10 | `limits` + `brain.think` request preflight; cap self_modify manifest | −20 |
| 11 | Self-narrating goal: `goal_narration` in state; planner prompt hook | +30 |

**Net:** ~2,617 → ~1,650 lines.

### Evolution constraints (self_modify may not break)

- SPI bus: one signal + one patch per tick
- `NODE_REGISTRY` keys == `topology.nodes`
- `contract_check.py` passes before commit
- Root-only layout (no new organ subdirectories)
- Fail-hard: no new silent fallbacks
- Request limits enforced before every brain call

---

## Observation (body)

Win32 hover scan → Excel-style grid (`A1=ibeam B1=hand`). No UIA. Config: `wiring.observe_config`.

**Fail-hard contract:**

```
desktop_tree_text   # always set by observe()
focused_title
observed_at
fresh_scan
```

**P0 today:** module `desktop.observe()` returns `grid_text` only; `organism_nodes/observe.py` patches `desktop_tree_text` from missing key → brain sees empty observation.

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