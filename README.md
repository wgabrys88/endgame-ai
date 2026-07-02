# endgame-ai Living Organism Handover

This README is the working handover document for this branch. Read it first in any future Codex session or AI-provider handoff, then rewrite it before the next handoff so it always reflects the current organism.

## Project Vision

endgame-ai is a living Windows desktop organism, not a chatbot and not a generic agent wrapper. Its loop is:

```text
perceive -> plan -> schedule -> act -> verify -> reflect -> self-modify
```

The organism should observe the real Windows desktop, form concrete intentions, act through mouse/keyboard/Win32/UIA capabilities, verify outcomes, reflect on failures, and evolve its own wiring or code when runtime evidence proves that evolution is useful.

The intended core is small, local, explicit, and fail-hard:

- Python source files are the organism body.
- `wiring.json` is the nervous-system map: transport, topology, prompts, paths, limits.
- `seed_nodes/` and `seed_brains/` are durable source.
- `live_nodes/` and `live_brains/` are runtime caches regenerated from seeds.
- Transports are selected intentionally. No silent fallback.
- Runtime evidence wins over speculation.

Current branch: `unified-archBRAINZ`.

Current selected transport: `xai` using `grok-build-0.1`.

Reasoning feedback default: OFF. Two-pass feedback remains configurable for comparison/debug runs only.

## Ground Rules

- Keep the organism lean. Remove duplication and prompt bloat before adding machinery.
- Keep Windows observation native: UIA `ElementFromPoint` hover scan plus Win32 focus/window APIs.
- Do not reintroduce `ControlViewWalker`.
- Keep selected transports fail-hard.
- Treat `state.json`, `comms/runtime.ndjson`, and newest raw `*.txt` logs as the audit trail.
- Commit coherent chunks regularly.
- README is part of the living system. Keep it current.

## Current Architecture

Observation:

- `desktop.py` regenerates stale comtypes UIAutomation wrappers when needed.
- UIA constants come from the generated module with numeric fallbacks.
- Window tokens come from Win32 `EnumWindows`.
- Active/focused context comes from Win32/UIA foreground and focused APIs.
- Actionable elements come from bounded hover scanning with `ElementFromPoint`.
- Tree walking is intentionally not active.

Brain:

- `brain.think()` is the single path for `single_pass`, `native`, and `two_pass`.
- `model.global` merges into transport config.
- Raw request/response rows are written to timestamped root `*.txt` logs.
- xAI Responses API is used through `seed_brains/xai.py`. Official xAI docs confirm Responses API support and web-search tooling, including domain filters.

Node loop:

- `organism.py` runs topology nodes and can start from a specific node with `--start-node`.
- `execute` now captures generated-code stdout/stderr into `state.last_result`.
- Execute namespace includes `state`, `wiring`, `goal`, `last`, `screen`, `elements`, `windows`, `screen_text`, `focused_title`, action functions, modules, `repo_root`, `python_executable`, and self-modify helpers.
- `verify` advances `state.step` on success.
- `error` routes step failures toward reflection when a current step exists.

Self-evolution:

- `self_modify` receives recursive workspace metadata, including subfolders.
- Runtime/private directories are skipped: `.git`, `__pycache__`, `.pytest_cache`, `.vscode`, `.idea`, `pids`.
- Large text and timestamp raw logs are bounded by head/tail or tail-only fields to avoid huge self-modify prompts.
- Model patches target repository source, not live caches.
- `live_nodes/` and `live_brains/` are synchronized after source changes.
- `nodes.apply_evolution_patch()` validates Python/JSON content before writing.
- It snapshots touched files, writes atomically, performs post-write validation, syncs live caches, optionally executes bounded commands, and rolls back touched files on command failure.
- Core file rewrites such as `nodes.py` activate on the next run because the current process already imported them.

## Proven Evidence

### A. Initial Grok/xAI Run

Raw log: `20260702T111459.txt`

Route: planner -> scheduler -> observe -> execute -> reflect.

Finding: execute failed with `NameError: name 'windows' is not defined`.

Internalized Grok feedback: the execute prompt told Grok to use `windows` and `elements`, but the exec namespace did not expose them directly. This led to the namespace contract fix.

### B. LM Studio Two-Pass Comparison

Raw log: `20260702T111838.txt`

Temporary transport: `openai` at LM Studio local server.

Finding: two-pass worked mechanically, but execute returned `record_type="plan"` instead of `execution`.

Internalized feedback: large nested prompt strings and duplicated instructions caused prompt contamination. Execute/verify/reflect/self_modify now use structured payloads and shorter schema-focused prompts.

### C. Grok/xAI Verification After Contract Fixes

Raw log: `20260702T113237.txt`

Route: planner -> scheduler -> observe -> execute -> verify.

Result: execute succeeded, verify returned `step_confirmed`, and `state.step` advanced to 1.

Remaining observation gap from this run: Task Manager can still produce zero actionable elements through hover scan.

### D. Bounded Self-Modify Inspection Run

Raw log: `20260702T115105.txt`

Command shape:

```powershell
& "C:\Users\px-wjt\AppData\Local\Python\bin\python.exe" organism.py --reset --max-ticks 5 "Self-modify endgame-ai ..."
```

Route: planner -> scheduler -> observe -> execute -> verify.

Finding: within 5 ticks, normal topology did not reach `self_modify`; Grok used execute to inspect the runtime and reported missing visible sandboxing, syntax validation, rollback, and test execution. Some of that was stale relative to our just-committed applier, but it correctly identified the need for explicit validation/rollback evidence.

Implemented after this run:

- `--start-node` support in `organism.py`.
- stdout/stderr capture in execute.
- rollback around command failures in `apply_evolution_patch`.
- `last` object added to execute namespace.

### E. Direct Grok Self-Modify Run

Raw log: `20260702T115546.txt`

Command shape:

```powershell
& "C:\Users\px-wjt\AppData\Local\Python\bin\python.exe" organism.py --reset --max-ticks 5 --start-node self_modify "Self-modify endgame-ai ..."
```

Route: self_modify -> planner -> scheduler -> observe -> execute.

Result:

- Grok returned `record_type="wiring_patch"`.
- The patch rewrote `nodes.py` with one meaningful architecture addition: explicit post-write validation of changed Python/JSON files after atomic write and before live-cache sync/command execution.
- Runtime logged `self_modify_applied`.
- Applied file: `nodes.py`.
- Activation: `next_run`, because top-level source was rewritten while the current process still had the old module loaded.
- Follow-up execute failed with `NameError: name 'last' is not defined`.

Fix after analysis:

- `nodes.build_execute_namespace()` now exposes `last`.
- `seed_nodes/execute.py` and `wiring.json` now advertise `last`.

### F. Local Validation

Compile:

```powershell
& "C:\Users\px-wjt\AppData\Local\Python\bin\python.exe" -m compileall -q .
```

Result: passed.

Rollback probe:

- Wrote `self_evolve_probe.md` through `apply_evolution_patch`.
- Deleted it through `apply_evolution_patch`.
- Wrote it again with a deliberately failing command.
- Verified command failure raised and rollback removed the file.

Observed output:

```json
{
  "write_applied": true,
  "delete_applied": true,
  "rollback_failed_command": true,
  "rollback_removed_file": true
}
```

Workspace capture shape after bounding:

- Files enumerated: 46.
- Serialized capture: about 225k chars.
- Timestamp raw logs are represented as 5 KB tails with `kind="runtime_log_tail"`.
- This fixes the 482 KB raw self-modify request bloat seen in `20260702T115546.txt`.

## What Is Proven Now

- The organism can run with Grok/xAI transport and no fallback.
- It can observe desktop/window state through the Windows-native path.
- It can execute generated Python and retain stdout/stderr in state.
- It can start directly at `self_modify` for bounded evolution runs.
- `self_modify` can read the workspace recursively and propose repository-level source changes.
- `organism.py` can apply a self-modify patch, sync live caches, and log `self_modify_applied`.
- Python/JSON writes are validated before writing and again after writing.
- Failed post-write commands roll back touched files.
- Seed files are authoritative; live files are runtime cache.
- Grok self-modification produced an aligned architecture change that is now in the worktree.

## Current Issues

1. Generated execute code still runs in-process with broad Python powers.

   This is intentional for now because the organism is meant to act and evolve, but it is not a sandbox. The self-evolution applier is safer than raw file writes; execute remains powerful.

2. Rollback is file-level, not git-level.

   Failed commands restore touched files from snapshots. It does not automatically create a git branch, commit, revert, or open a PR.

3. Core rewrites activate on the next process run.

   `nodes.py`, `brain.py`, `organism.py`, `desktop.py`, and `stop_check.py` are already imported in the current process. If self_modify rewrites them, the current run records `activation.next_run`.

4. `self_modify` still asks the model for full file contents.

   This is simple and robust for a small repo, but expensive for large files. Future improvement can add unified-diff patches with strict apply/validate semantics.

5. Observation can still miss actionable controls.

   Task Manager produced zero actionable elements in one run. Do not solve this with tree walking. Improve hover sampling around focused window edges/centers and preserve bounded config knobs.

6. `reasoning_from()` still has old corrupted-marker compatibility.

   It compiles and is harmless for current xAI runs, but it should eventually be cleaned to normal `<think>...</think>` extraction if old compatibility is no longer needed.

7. Public-repo self-evolution is not implemented.

   The user proposed pointing Grok at the GitHub branch so Grok can fetch code itself and propose public commits. This is a useful direction, but not a replacement for local runtime evidence.

## Public GitHub Branch Idea

User idea: since the project is public and changes are pushed, maybe Grok should inspect the GitHub branch directly instead of receiving the whole workspace through `self_modify` payloads. Grok could use the online repo as source context and propose or commit changes publicly.

Assessment:

- This can reduce prompt size and avoid shipping the entire local workspace in every self-modify call.
- It fits xAI's current API surface because official docs describe a Responses API with a `web_search` tool and domain filters such as `allowed_domains`.
- It should be used as a source-context option, not as the only context. The live organism still needs local `state.json`, `comms/runtime.ndjson`, current raw logs, selected transport, desktop observation, and uncommitted diffs.
- Letting Grok commit directly to the public repository is higher risk. A safer design is: Grok reads public branch + local runtime summary, returns a patch, local applier validates, Codex/human commits and pushes.
- If implemented, add a `self_modify.context_mode` option:
  - `local_full`: current bounded local workspace capture.
  - `github_public`: send repo URL/branch plus local runtime summary.
  - `hybrid`: public branch URL plus changed local files, runtime logs, and state.
- If xAI web search is enabled, restrict domains to `github.com` and possibly the specific repository domain/path where possible.

Relevant docs:

- xAI overview: `https://docs.x.ai/overview`
- xAI Web Search tool: `https://docs.x.ai/developers/tools/web-search`

## Next Plan

1. Commit the current self-evolution hardening.

   Includes Grok's post-write validation addition, `last` namespace fix, and bounded self_modify workspace capture.

2. Run one more direct self_modify verification only if needed.

   Recommended command:

   ```powershell
   & "C:\Users\px-wjt\AppData\Local\Python\bin\python.exe" organism.py --reset --max-ticks 5 --start-node self_modify "Inspect and validate the existing self-evolution mechanism. Do not rewrite files unless a concrete missing validation or rollback invariant is found."
   ```

3. Add optional GitHub public-branch context mode.

   Do not let Grok push directly in the first implementation. Build it as context selection first, then keep local validated patch application.

4. Improve observation sampling without tree walking.

   Add focused-window center/edge probes and dedupe by runtime id, hwnd, rect, name, and control type.

5. Add expected-record metadata to `brain.think()`.

   The current node-level checks work, but passing expected record type into the brain chokepoint would improve logging and optional one-shot repair.

## Fresh Handover Prompt

Use this prompt for the next Codex session or another AI provider:

```text
Read README.md completely before acting. You are continuing endgame-ai on branch unified-archBRAINZ. This is a living Windows desktop organism, not a chatbot and not a generic agent wrapper. Preserve the loop: perceive -> plan -> schedule -> act -> verify -> reflect -> self-modify. Keep the core small, fail-hard, and evidence-driven. Current transport is xai/Grok with reasoning feedback OFF by default. Do not reintroduce ControlViewWalker.

First inspect git status, then newest state.json, comms/runtime.ndjson, and newest raw *.txt. The latest proven self-evolution path is repository-level: self_modify proposes file_writes/wiring_patches, nodes.apply_evolution_patch validates Python/JSON before write, snapshots touched files, writes atomically, validates again after write, syncs live caches, executes bounded commands, and rolls back touched files on command failure. live_nodes/live_brains are runtime caches; seed_nodes/seed_brains and top-level source are durable.

Known latest issue: the direct Grok self_modify run applied a useful nodes.py post-write validation change, then execute failed because generated code used `last`; this is now fixed by exposing `last` in nodes.build_execute_namespace and documenting it in execute payload/prompt. Workspace capture now enumerates non-private files recursively but bounds large/runtime logs.

Next best work: commit current hardening, then implement optional `self_modify.context_mode` with a `github_public` or `hybrid` mode so Grok can inspect the public GitHub branch while the local organism still provides runtime state/logs and applies patches locally. Do not let Grok push directly until the local validate/apply/commit gate is proven.
```

## Commands

Compile:

```powershell
& "C:\Users\px-wjt\AppData\Local\Python\bin\python.exe" -m compileall -q .
```

Limited normal Grok run:

```powershell
& "C:\Users\px-wjt\AppData\Local\Python\bin\python.exe" organism.py --reset --max-ticks 5 "Observe the current desktop and report focused window title plus a few interactive elements"
```

Direct self_modify run:

```powershell
& "C:\Users\px-wjt\AppData\Local\Python\bin\python.exe" organism.py --reset --max-ticks 5 --start-node self_modify "Inspect and validate the existing self-evolution mechanism. Do not rewrite files unless a concrete missing validation or rollback invariant is found."
```

Rollback probe pattern:

```powershell
@'
import pathlib, sys, brain, nodes
w = brain.load_json(brain.ROOT / "wiring.json")
p = pathlib.Path("self_evolve_probe.md")
p.unlink(missing_ok=True)
nodes.apply_evolution_patch(w, {"data": {"file_writes": [{"path": "self_evolve_probe.md", "content": "probe\n"}]}})
nodes.apply_evolution_patch(w, {"data": {"file_deletes": ["self_evolve_probe.md"]}})
try:
    nodes.apply_evolution_patch(w, {"data": {"file_writes": [{"path": "self_evolve_probe.md", "content": "rollback\n"}], "commands": [{"command": [sys.executable, "-c", "import sys; sys.exit(7)"], "shell": False}]}})
except Exception:
    pass
print("rollback_removed_file", not p.exists())
'@ | & "C:\Users\px-wjt\AppData\Local\Python\bin\python.exe" -
```
