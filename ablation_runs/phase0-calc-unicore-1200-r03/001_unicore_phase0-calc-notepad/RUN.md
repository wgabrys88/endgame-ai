# 001_unicore_phase0-calc-notepad

- run_id: `20260616_083756_unicore_phase0-calc-notepad`
- batch_id: `phase0-calc-unicore-1200-r03`
- sequence: `1`
- mode: `unicore`
- task_id: `phase0_calc_notepad`
- model_profile: `nemotron`
- timeout_seconds: `1200`
- stop_reason: `timeout`
- returncode: `1`
- evaluator: `ablation_runner`
- verdict: `success_evidence_present`
- note: stop_reason=timeout; returncode=1; confirmed=4; denied=20; fissions=0; errors=4

## Goal

open calculator, add two numbers, and get the result copied from the calculator into the notepad, save file on desktop.

## Command

```powershell
C:\Users\px-wjt\AppData\Local\Python\pythoncore-3.13-64\python.exe reactor.py --mode unicore --model-profile nemotron --ablation-task-id phase0_calc_notepad --unicore-persona generalist
```

## Evidence

- events: `459`
- verify_confirmed: `4`
- verify_denied: `20`
- fissions: `0`
- errors: `4`
- mutations: `8`
- respawns: `0`

## Paths

- raw_session_dir: `C:\Users\px-wjt\Downloads\endgame-ai\sessions\20260616_103756`
- raw_ablation_dir: `C:\Users\px-wjt\Downloads\endgame-ai\runtime\ablation\20260616_083756_unicore_phase0-calc-notepad`
