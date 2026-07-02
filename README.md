# endgame-ai Living Organism Handover

This file is the current handover prompt, architecture map, and evidence ledger for endgame-ai. Read it before changing code. Rewrite it before handing the project to another Codex, Kiro CLI, OpenCode, or other AI provider.

## Project Vision

endgame-ai is a living Windows desktop organism, not a chatbot and not a generic agent wrapper. The organism is meant to perceive the real Windows desktop, plan, act through UI controls, verify outcomes, reflect on failures, and evolve its own code when runtime evidence proves that evolution is useful.

Loop:

```text
perceive -> plan -> schedule -> act -> verify -> reflect -> self-modify
```

Core principles:

- The organism body is local Python source.
- `wiring.json` is the nervous-system map: transport, paths, prompts, topology, limits, and self-evolution policy.
- `organism_nodes/` contains canonical node modules.
- `brain_transports/` contains canonical brain transport modules.
- `brain.py` is the fail-hard brain chokepoint.
- `nodes.py` is the node loader, execute namespace, and validated self-evolution authority.
- `organism.py` is the topology loop and state/runtime event writer.
- Transports are selected intentionally. No silent fallback.
- Runtime evidence beats speculation.
- Reduction matters: remove duplication and prompt bloat before adding machinery.

Current branch: `unified-archBRAINZ`.

Current implementation checkpoint: `62db244 Make self evolution git native`.

Current selected transport: `xai` with model `grok-build-0.1`.

Reasoning feedback: OFF by default. Two-pass/ROD remains configurable in `wiring.json` for comparison and debug runs.

## Current Architecture

### Observation

`desktop.py` observes Windows through UIA `ElementFromPoint` hover scanning plus Win32 focus/window APIs. Tree walking is intentionally not active.

Rules:

- Preserve hover scan plus Win32.
- Do not reintroduce `ControlViewWalker`.
- Keep observation bounded through `observe_config`.
- Task Manager can still produce zero actionable elements by hover scan; improve sampling if needed, but keep the no-tree-walk invariant.

### Brain

`brain.think()` is the only reasoning path. It handles single-pass, native reasoning transports, and two-pass ROD feedback. The selected transport is loaded directly from `brain_transports/`.

Important behavior:

- `model.transport` selects the only transport.
- Transport config comes from `model.transport_config`.
- `model.global` merges timeout/raw-log/call-budget settings.
- Raw request/response rows are written to timestamped root `*.txt` logs.
- xAI/Grok is current; LM Studio/OpenAI-compatible transport exists but is not selected.

### Nodes

`nodes.py` loads topology nodes directly from `organism_nodes/`. There is no seed/live copy step.

Node contracts:

- `planner`: expects `record_type="plan"`.
- `scheduler`: local deterministic step picker.
- `observe`: local Windows observation.
- `execute`: expects `record_type="execution"` and runs generated Python inside the desktop namespace.
- `verify`: expects `record_type="verification"`.
- `reflect`: expects `record_type="reflection"`.
- `self_modify`: expects `record_type="git_evolution_patch"`.
- `satisfied`: halts cleanly.

### Self-Evolution

Self-modification is now git-native. Grok proposes; the local organism applies, validates, commits, and may publish.

Current flow:

1. `self_modify` requires a clean git worktree.
2. It creates a timestamped branch named `self-evolve/YYYYMMDDTHHMMSS-<shortsha>`.
3. It builds a non-lossy workspace manifest: path, size, sha256, tracked/untracked status, git status, branch, and commit SHA.
4. It sends Grok the manifest, git context, runtime evidence paths, wiring, and patch schema.
5. Grok returns `record_type="git_evolution_patch"`.
6. `organism.py` and `nodes.apply_evolution_patch()` refuse to apply unless the current branch starts with `self-evolve/`.
7. `nodes.apply_evolution_patch()` validates Python/JSON before writing, snapshots touched files, writes atomically, validates again after writing, runs optional bounded commands, and rolls back touched files on failure.
8. `nodes.commit_self_evolution()` commits the successful patch on the timestamp branch.

No direct public push by Grok is implemented. That is deliberate. Local validation remains the authority.

## Proven Run Evidence

### Grok/xAI Normal Run

Raw log: `20260702T111459.txt`

Route: planner -> scheduler -> observe -> execute -> reflect.

Finding: execute failed with `NameError: name 'windows' is not defined`.

Internalized feedback: the execute prompt advertised fields that were not present in the exec namespace. This produced the namespace contract fix.

### LM Studio Two-Pass Comparison

Raw log: `20260702T111838.txt`

Temporary transport: OpenAI-compatible local LM Studio server.

Finding: two-pass mechanics worked, but execute returned `record_type="plan"` instead of `execution`.

Internalized feedback: large nested prompt strings and duplicated instructions can contaminate model outputs. Node payloads and prompts were tightened. Two-pass stays configurable but OFF by default.

### Grok/xAI Verification After Contract Fixes

Raw log: `20260702T113237.txt`

Route: planner -> scheduler -> observe -> execute -> verify.

Result: execute succeeded, verify returned `step_confirmed`, and `state.step` advanced.

Remaining observation issue: Task Manager could still produce zero actionable hover-scan elements.

### Bounded Self-Modify Inspection Run

Raw log: `20260702T115105.txt`

Normal topology did not reach `self_modify` within five ticks. Grok used execute to inspect runtime behavior and reported missing visible sandboxing, syntax validation, rollback, and test execution. Some of this was stale after local patches, but it correctly pushed the system toward explicit validation and rollback evidence.

Implemented after that analysis:

- `--start-node` support in `organism.py`.
- stdout/stderr capture in execute.
- rollback around command failures in `apply_evolution_patch`.
- `last` object added to execute namespace.

### Direct Grok Self-Modify Run

Raw log: `20260702T115546.txt`

Command shape:

```powershell
& "C:\Users\px-wjt\AppData\Local\Python\bin\python.exe" organism.py --reset --max-ticks 5 --start-node self_modify "Self-modify endgame-ai ..."
```

Route: self_modify -> planner -> scheduler -> observe -> execute.

Result:

- Grok returned the older `record_type="wiring_patch"`.
- It produced one useful architecture change: explicit post-write validation of changed Python/JSON files before command execution.
- Runtime logged self-modify application.
- Follow-up execute failed with `NameError: name 'last' is not defined`; this is fixed now.

This run also proved why the old self-modify context was wrong: the raw request reached about 482 KB because it included workspace file text. That has now been replaced by manifest-only git context.

## What Is Proven Now

- The organism can run with Grok/xAI selected and no fallback.
- The organism can observe Windows desktop/window state through the hover-scan/Win32 path.
- Execute can run generated Python and capture stdout/stderr in state.
- Verify can advance the plan after successful execution.
- Direct `--start-node self_modify` exists.
- Self-evolution now starts from a clean git worktree and a timestamped branch.
- Workspace context no longer uses bounded text dumps or head/tail truncation fields.
- Python/JSON writes are validated before and after writing.
- Failed validation commands roll back touched files.
- Successful self-evolution patches are committed on the self-evolve branch.
- Canonical code directories are now `organism_nodes/` and `brain_transports/`.

## Current Issues And Honest Limits

1. Execute still runs generated Python in-process with broad powers.

   This is intentional for a self-evolving desktop organism, but it is not a sandbox.

2. Clean self-evolution branch creation is implemented but not runtime-proven after this README rewrite.

   The architecture commit compiled. The dirty-worktree gate could not be executed through the sandbox after the inline Python probe was denied, so a future session should run the git self-evolution test matrix after this README commit.

3. `github_public` branch context is designed, not enabled by default.

   `self_modify.context_mode` defaults to `hybrid`, but `publish_context_branch` currently defaults to `false`. Set it to `true` when the operator wants Grok to inspect the pushed GitHub branch directly.

4. Grok cannot interactively request local files mid-call.

   The v1 model gets manifest plus optional GitHub branch URL. If deeper local file retrieval is needed, add a two-step file request record before patch generation.

5. Core rewrites activate on next process run.

   `brain.py`, `nodes.py`, `organism.py`, `desktop.py`, and `stop_check.py` are already imported in the running process.

6. Observation can miss controls.

   Improve focused-window hover sampling and dedupe if needed. Do not solve this by tree walking.

## Observation Data Appendix

### Observe Node Output

`organism_nodes/observe.py` creates and writes these fields into state:

- `screen`
- `elements`
- `screen_text`
- `windows`
- `snapshot`
- `focused_title`

### Execute Input

`organism_nodes/execute.py` sends the brain the full current observation payload:

- screen dimensions through `screen`
- focused title through `focused_title`
- windows list through `windows`
- actionable elements through `elements`
- formatted text through `screen_text`
- full observation snapshot through `snapshot`
- last error/result/action through `last`
- namespace contract for values, observation helpers, actions, modules, and repo metadata

The exec namespace exposes the same major observation values directly:

- `state`
- `wiring`
- `goal`
- `last`
- `screen`
- `elements`
- `windows`
- `screen_text`
- `focused_title`

### Verify Input

`organism_nodes/verify.py` sends reduced evidence:

- focused title
- screen text
- elements
- windows
- last action
- last result
- last error

### Reflect Input

`organism_nodes/reflect.py` sends reduced failure evidence:

- focused title
- screen text
- elements
- last action
- last result
- last error
- last verification

### Self-Modify Input

`organism_nodes/self_modify.py` does not take a fresh observation. It uses whatever is already in state. If the organism starts directly with `--start-node self_modify`, there is no fresh screen observation unless a previous state already contains one.

Self-modify currently sends:

- goal and current step summary
- last failure/reflection/action/result/verification
- runtime state summary
- runtime evidence file paths with size and sha256
- git context
- workspace manifest
- patch contract

It does not send full screen bitmaps. It does not send full file text. It does not send text head/tail fields.

## Codebase Context Appendix

The previous approach sent recursive workspace metadata with file text and bounded large files using head/tail fields. That was wrong for this project because the user wants Grok to have non-lossy context and because lossy prompt dumps scale poorly.

Removed semantics:

- `FULL_TEXT_LIMIT`
- `RUNTIME_TEXT_TAIL`
- `text_head`
- `text_tail`
- `truncated`

Replacement:

- `workspace_manifest.files[].path`
- `workspace_manifest.files[].size`
- `workspace_manifest.files[].sha256`
- `workspace_manifest.files[].tracked`
- `workspace_manifest.files[].status`
- `workspace_manifest.commit_sha`
- `workspace_manifest.branch`
- `workspace_manifest.git_status`

Full-file access strategy:

- `git_local`: Grok gets manifest and local evidence metadata. A future two-step tool can serve exact requested files.
- `github_public`: the organism creates and pushes a timestamped branch; Grok gets the GitHub branch URL and commit SHA.
- `hybrid`: default mode; Grok gets branch URL metadata plus local runtime evidence metadata. Publishing is controlled by `self_modify.git.publish_context_branch`.

Important: manifest-only context is not truncation. It is an index plus cryptographic identity. Full content must come from the branch or an explicit file-read protocol, not lossy prompt slices.

## Self-Evolution Appendix

Patch schema expected from Grok:

```json
{
  "record_type": "git_evolution_patch",
  "data": {
    "summary": "short human summary",
    "rationale": "runtime/code evidence",
    "file_writes": [
      {"path": "repo-relative path", "content": "complete file text"}
    ],
    "file_deletes": ["repo-relative path"],
    "wiring_patches": [
      {"op": "set", "path": "dotted.path", "value": "any JSON value"}
    ],
    "commands": [
      {"command": ["python", "-m", "compileall", "-q", "."], "shell": false}
    ],
    "expected_validation": "what should pass after the patch"
  }
}
```

Branch discipline:

- Main/development branch should be clean before self-modify.
- Self-modify creates `self-evolve/YYYYMMDDTHHMMSS-<shortsha>`.
- Patches are applied only on that branch.
- The branch is committed locally after validation.
- Optional push belongs to local Python/git authority, not Grok.
- Direct Grok push is intentionally not v1.

Validation discipline:

- Python content is compiled before write.
- JSON content is parsed before write.
- Writes are atomic.
- Python/JSON content is validated again after write.
- Optional commands are bounded by `self_modify.execution.max_commands` and `timeout_s`.
- Command failure rolls back touched files.

## GitHub/Grok Architecture

The user's public-repo idea is valid: if the repository is public and changes are pushed, Grok can inspect the GitHub branch instead of receiving a giant prompt dump.

Current implementation supports the safe half:

- create timestamped branch locally
- optionally push branch to origin
- give Grok repo URL/branch URL/commit SHA/manifest/runtime evidence
- receive a patch
- apply locally
- validate locally
- commit locally

Not implemented by design:

- Grok pushing directly
- Grok committing directly
- trusting GitHub inspection without local runtime evidence

Recommended next step if enabling GitHub public context:

1. Set `self_modify.git.publish_context_branch=true`.
2. Ensure xAI web search/tooling is configured only for `github.com` or the exact repository.
3. Keep local apply/validate/commit authority.
4. Add a two-step `file_request` record only if manifest plus GitHub branch is not enough.

## Commands

Compile:

```powershell
& "C:\Users\px-wjt\AppData\Local\Python\bin\python.exe" -m compileall -q .
```

Normal Grok run:

```powershell
& "C:\Users\px-wjt\AppData\Local\Python\bin\python.exe" organism.py --reset --max-ticks 5 "Observe the current desktop and report focused window title plus a few interactive elements"
```

Direct self-modify run:

```powershell
& "C:\Users\px-wjt\AppData\Local\Python\bin\python.exe" organism.py --reset --max-ticks 5 --start-node self_modify "Inspect the git-native self-evolution path. Propose no file writes unless runtime evidence proves a concrete missing invariant."
```

Static scans:

```powershell
rg -n "FULL_TEXT_LIMIT|RUNTIME_TEXT_TAIL|text_head|text_tail|truncated" organism_nodes nodes.py organism.py brain.py wiring.json
rg -n "ensure_live|seed_nodes|seed_brains" organism_nodes brain_transports nodes.py organism.py brain.py wiring.json
```

## Next Verification Matrix

Run this after committing the README:

1. `python -m compileall -q .`
2. `rg` confirms removed truncation symbols do not exist in the self-modify path.
3. `rg` confirms no seed/live copy workflow remains in runtime code.
4. Dirty worktree causes `nodes.prepare_self_evolution(wiring)` to fail before branch creation.
5. Clean worktree creates `self-evolve/YYYYMMDDTHHMMSS-<shortsha>`.
6. Patch application is refused off a `self-evolve/` branch.
7. Invalid Python content is rejected before commit.
8. Failing validation command rolls back touched files.
9. Successful patch creates a git commit on the timestamp branch.
10. Raw self-modify log shows branch URL/manifest/runtime evidence, not file text dumps.

## Fresh Handover Prompt

Use this exact prompt for the next AI provider:

```text
Read README.md fully before acting. You are continuing endgame-ai on branch unified-archBRAINZ. Treat it as a living Windows desktop organism, not a chatbot or generic agent. Preserve the loop: perceive -> plan -> schedule -> act -> verify -> reflect -> self-modify. Keep the system small, explicit, fail-hard, and evidence-driven.

Current architecture: canonical nodes live in organism_nodes/ and brain transports live in brain_transports/. There is no seed/live runtime copy workflow. wiring.json selects xai/Grok with model grok-build-0.1. Reasoning feedback and LM Studio two-pass are configurable but OFF by default. Observation is Windows-native UIA ElementFromPoint hover scan plus Win32 focus/window APIs. Do not reintroduce ControlViewWalker.

Self-evolution is git-native. self_modify requires a clean worktree, creates self-evolve/YYYYMMDDTHHMMSS-<shortsha>, sends Grok git_context + workspace_manifest + runtime evidence paths, expects record_type="git_evolution_patch", applies patches locally through nodes.apply_evolution_patch, validates Python/JSON before and after write, rolls back touched files on failing validation command, and commits successful changes locally through nodes.commit_self_evolution. Grok must not push or commit directly in v1.

Important run evidence: Grok/xAI normal run first exposed missing execute namespace fields. LM Studio two-pass worked mechanically but produced prompt contamination, so two-pass stays OFF by default. Later Grok run succeeded through execute and verify. Direct old self_modify proved that file-text prompt dumps caused about 482 KB raw requests and that Grok could still suggest useful validation hardening. That old truncating context has been removed. The new context is manifest-only: path, size, sha256, tracked/untracked status, branch, commit SHA, and runtime evidence file metadata. No text_head, text_tail, truncated, FULL_TEXT_LIMIT, or RUNTIME_TEXT_TAIL should return.

Observation data flow: observe writes screen, elements, screen_text, windows, snapshot, focused_title. execute receives the full observation payload and namespace contract. verify receives focused_title, screen_text, elements, windows, last_action, last_result, last_error. reflect receives focused_title, screen_text, elements, last_action, last_result, last_error, last_verification. Direct --start-node self_modify has no fresh observation unless state already has one.

Known issues: execute is powerful and not sandboxed; Task Manager can produce zero actionable hover-scan elements; github_public context is designed but publish_context_branch defaults false; clean self-evolution branch creation needs post-README runtime verification; direct Grok push is intentionally not implemented.

Start by running git status, reading wiring.json, brain.py, nodes.py, organism.py, organism_nodes/self_modify.py, and newest runtime evidence files. Then run compileall and the static rg checks from README. If worktree is clean, run the git self-evolution verification matrix. If enabling GitHub public context, set self_modify.git.publish_context_branch=true, keep xAI web access restricted to GitHub/the repository, and keep local apply/validate/commit authority. Commit coherent chunks regularly and rewrite README.md before handoff.
```
