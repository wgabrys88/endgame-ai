# Phase 0 Calc Unicore 1200s Analysis

Status after two proper 1200-second unicore runs on `phase0_calc_notepad`:

| Run | Events | Verified confirmed | Verified denied | Fissions | Errors | Internal success rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `phase0-calc-unicore-1200-r01` | 585 | 2 | 30 | 0 | 4 | 0.0625 |
| `phase0-calc-unicore-1200-r02` | 573 | 12 | 18 | 6 | 12 | 0.4 |

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
