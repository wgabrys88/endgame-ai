# 001_unicore_phase0-calc-notepad

- run_id: `20260615_193614_unicore_phase0-calc-notepad`
- batch_id: `phase0-calc-unicore-r04`
- sequence: `1`
- mode: `unicore`
- task_id: `phase0_calc_notepad`
- model_profile: `nemotron`
- timeout_seconds: `45`
- stop_reason: `timeout`
- returncode: `1`
- evaluator: `ablation_runner`
- verdict: `success_evidence_present`
- note: stop_reason=timeout; returncode=1; confirmed=2; denied=0; fissions=0; errors=2

## Goal

open calculator, add two numbers, and get the result copied from the calculator into the notepad, save file on desktop.

## Command

```powershell
C:\Users\px-wjt\AppData\Local\Python\pythoncore-3.13-64\python.exe reactor.py --mode unicore --model-profile nemotron --ablation-task-id phase0_calc_notepad --unicore-persona generalist
```

## Evidence

- events: `39`
- verify_confirmed: `2`
- verify_denied: `0`
- fissions: `0`
- errors: `2`
- mutations: `0`
- respawns: `0`

## Paths

- raw_session_dir: `C:\Users\px-wjt\Downloads\endgame-ai\sessions\20260615_213614`
- raw_ablation_dir: `C:\Users\px-wjt\Downloads\endgame-ai\runtime\ablation\20260615_193614_unicore_phase0-calc-notepad`
