# Phase 0 Calc Unicore 1200s Analysis

Status after three proper 1200-second unicore runs on `phase0_calc_notepad`:

| Run | Events | Verified confirmed | Verified denied | Fissions | Errors | Internal success rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `phase0-calc-unicore-1200-r01` | 293 | 1 | 15 | 0 | 2 | 0.0625 |
| `phase0-calc-unicore-1200-r02` | 287 | 6 | 9 | 3 | 6 | 0.4 |
| `phase0-calc-unicore-1200-r03` | 230 | 2 | 10 | 0 | 2 | 0.1667 |

The earlier exported summaries counted `events-child-s*.jsonl` twice because the summarizer globbed both `events*.jsonl` and `events-child-s*.jsonl`. Current `ablation.py summarize` deduplicates event files; the table above uses the corrected unique-event counts.

Run 2 looks better than run 1 by internal metrics, but LM Studio server-log evidence shows the apparent improvement is unreliable. The model repeatedly plans and verifies against placeholder paths such as `C:\\Users\\user\\Desktop` instead of the actual user desktop, then accepts printed claims like "Result copied to Notepad" or "Saved file on Desktop" as proof.

Observed LM Studio log patterns from `C:\Users\px-wjt\.lmstudio\server-logs\2026-06\2026-06-16.1.log`:

- `C:\\Users\\user\\Desktop`: 43 matches
- `C:\\Users\\px-wjt\\Desktop`: 0 matches
- `FileNotFoundError`: 155 matches
- `SyntaxError`: 169 matches
- `pyperclip`: 16 matches
- `file exists and contains`: 52 matches
- `Result copied to Notepad`: 45 matches
- `Saved file on Desktop`: 4 matches

Root cause candidate:

- `prompts/planner.txt` still tells the planner: `All file paths are Windows: C:\Users\user\Downloads\...`
- `prompts/personalities/architect.txt` and `prompts/personalities/implementor.txt` also contain `C:\Users\user\Downloads\...`

Recommendation: pause repeated 1200-second testing here. Continuing more runs before fixing the path prompt and final external evidence check will mostly measure prompt-path drift and verifier self-certification, not real desktop task completion.

Follow-up fix direction accepted by owner: stop repeated tests, correct real path guidance, and require actual Desktop path/readback evidence before fission credit on file/Desktop tasks. The next run after this fix should still use exactly `--timeout 1200`.

Run 3 after the path/evidence fixes changed the failure pattern:

- The planner prompt contained the full `ACTIVE_TASK`; the main LLM request was not losing the goal text.
- The fission gate denied calculator-only substep confirmations because no real Desktop file readback existed, so the earlier false-positive fissions did not recur.
- The run still timed out and did not produce durable external task success evidence.
- A new blocker appeared: the local mutator rewrote `plugins/fission_log.py` and `plugins/comms_beacon.py` with task-specific calculator/notepad code. Those files are core measurement/control plugins; mutating them corrupts the experiment.
- The mutated `comms_beacon.py` called GUI helpers that are not injected into plugin runtime, causing `plugin.error name 'desktop_click' is not defined`.

Updated recommendation: do not start repeated batches yet. First keep full-goal propagation, keep strict path/readback fission, and block Phase 0 task mutation from rewriting core instrumentation plugins. The next useful run is another single `phase0_calc_notepad` 1200-second unicore run after that guard is committed and pushed.
