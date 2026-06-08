# ENDGAME-AI-META-CHECKLIST.md

Project-level checklist for making `endgame-ai` more efficient, more reliable, and less dependent on external AI providers over time.

## Current Session Findings

- [done] Reflection pipeline has been linearized: reflector extracts one lesson, Python stores/deduplicates it, optional prompt mutation is guarded, and tier-3 code evolution is a separate goal switch.
- [done] Prompt mutation is default-disabled behind `--enable-prompt-mutations`; lessons still extract when prompt mutation is disabled.
- [done] Prompt mutation is one-line-only inside mutable markers and does not allow full prompt rewrites.
- [done] Reflector schema cognitive load was reduced by removing full prompt rewrites, PID tuning, and goal rewrite fields.
- [done] Lesson metadata is typed and persisted with issue keys, prompt mutation history, and tier-3 escalation history.
- [done] `AGENTS.md` exists as a provider-agnostic handoff artifact.
- [done] Git ignore policy was validated: docs/tests need explicit unignore rules; runtime reports remain ignored.
- [done] Human goals are wrapped by Python and resumed snapshots are normalized so legacy unwrapped goals do not bypass the wrapper.
- [done] Goal wrapper now includes long-goal evidence gathering and provider-steering guidance while staying short enough for small models.
- [done] Child agents inherit prompt-mutation settings through the direct `spawn_agent` action path.
- [done] Actor-level `spawn_agent` now creates a unique non-main child id, registers it, attaches it to parent coordination state, and uses the normal child event channel.
- [done] ACP setup commands retry before surfacing transient WSL startup failures.
- [done] ACP smoke validation succeeded on 2026-06-08 with `read_file README.md`, verifier `confirmed`, `failure_type:null`, and no `cmd`, `write_file`, or `spawn_agent` action.
- [validated] `ENDGAME-AI-WHAT-IS-NOT-NEEDED.json` is runtime/session evidence, not source. Its useful findings are distilled below instead of committing the raw ignored report.

## Validated Report Findings

- [validated] Runtime reports can include fields useful for audit but noisy for LLM planning, including sha256 values, click coordinates, long recent history, and window controls irrelevant to the current goal.
- [validated] The code already compacts observations in `state._observation_record`, but LLM contexts can still receive compact hashes in history. Future work should decide per role whether hashes belong in context or only in logs.
- [validated] `CONTEXT_POLICY` is the correct control point for reducing LLM cognitive load without deleting blackboard truth.
- [validated] `used_fields` telemetry exists and should be aggregated across real runs before removing more role fields.
- [validated] Probe-first observation and semantic screen hashes are already part of the current architecture; future work should keep measuring them under real ACP/desktop runs.

## Next Efficiency Work

- [next] Add an offline analyzer that reads `blackboard_events.txt` and summarizes `role.used_fields` by role, field, acceptance, and missing-policy frequency.
- [next] Use that analyzer to propose `CONTEXT_POLICY` reductions from evidence rather than intuition.
- [next] Split audit evidence from role context: keep hashes and full observations in logs, but omit them from planner/actor contexts unless a verifier or recovery path needs them.
- [next] Make learned insights conditional by issue/role instead of always injecting all lessons into every matching role context.
- [next] Re-evaluate planner schema fields by mode. `decompose` and `sequence` may be avoidable in direct mode if Python can supply defaults.
- [next] Re-evaluate actor schema action naming against common LLM priors without hiding the actual Win32 implementation.
- [next] Continue measuring observer cost by phase: probe, tree walk, merge/classify, render/hash.
- [next] Validate semantic hash stability on dynamic web pages, not only desktop/static windows.

## Next Reliability Work

- [next] Build tier-3 code-evolution as an isolated local branch workflow: create branch, patch, run validation goal, compare evidence, then decide whether to merge.
- [next] Add a subagent validation goal dedicated to self-evolution invariants: lesson extraction, default-disabled prompt mutation, guarded enabled mutation, and tier-3 threshold behavior.
- [next] Harden `cmd` action semantics around Bash/WSL syntax and remove ambiguity with Windows shell syntax.
- [next] Test `comms/stop.txt` while an ACP request is waiting, not only before iterations/actions.
- [next] Validate child-agent termination behavior under a live multi-agent ACP goal.
- [next] Validate actor-level `spawn_agent` under live ACP with one child read-file task and verifier-confirmed parent completion.
- [next] Add runtime cleanup as a first-class command or script that preserves source and deletes only generated artifacts.
- [next] Decide whether `lessons.json` should remain runtime-only forever or whether a curated seed lesson file should be tracked separately.

## Release Checklist Before Push

- [required] `git status --short --ignored` reviewed.
- [required] Runtime artifacts cleaned.
- [required] `python -m compileall -q .` passes.
- [required] `python -m pyright` reports `0 errors, 0 warnings, 0 informations`.
- [done] ACP smoke validation exits successfully for a simple `read_file README.md` goal.
- [done] Runtime evidence from ACP is inspected: one `read_file` action on `README.md`, no prohibited `cmd`/`write_file`/`spawn_agent`, and verifier confirmation with `failure_type:null`.
- [required] Commit exists locally.
- [required] No GitHub push unless the human explicitly asks.
