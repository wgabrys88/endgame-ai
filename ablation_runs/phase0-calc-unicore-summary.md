# Phase 0 Calc Notepad Unicore Summary

Task: `phase0_calc_notepad`

Mode: `unicore`

Persona: `generalist`

Timeout per run: 45 seconds

## Runs

| Run | Stop | Verdict | Confirmed | Denied | Fissions | Errors |
|-----|------|---------|-----------|--------|----------|--------|
| r01 | timeout | failure_evidence_present | 0 | 2 | 0 | 0 |
| r02 | timeout | failure_evidence_present | 0 | 2 | 0 | 0 |
| r03 | timeout | failure_evidence_present | 0 | 2 | 0 | 0 |
| r04 | timeout | success_evidence_present | 2 | 0 | 0 | 2 |
| r05 | timeout | failure_evidence_present | 0 | 2 | 0 | 0 |
| r06 | timeout | success_evidence_present | 2 | 0 | 2 | 0 |
| r07 | timeout | failure_evidence_present | 0 | 2 | 0 | 0 |
| r08 | timeout | success_evidence_present | 2 | 0 | 2 | 0 |

## Observed Pattern

All eight runs started and were stopped by the finite runner after timeout. The runner itself is repeatable: every run produced a source-controlled record with stdout, stderr, copied session logs, runtime summary, evaluation metadata, and git state snapshots.

The organism behavior is not deterministic yet:

- 5 of 8 runs ended with failure evidence: two verifier denials, no fissions.
- 3 of 8 runs ended with success evidence: two verifier confirmations.
- 2 of 8 runs reached fission credit before timeout.
- No run naturally reached a clean terminal completion condition before timeout.

## Next Engineering Implication

The next measurable improvement should not be another broad capability feature. The system needs a finite-run completion contract: when a task is verified and fission is credited, the runner should be able to classify that as solved and stop early, while preserving the eternal runtime behavior for normal non-ablation operation.
