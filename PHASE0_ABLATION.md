# Phase 0 Ablation

Phase 0 measures whether the colony earns its keep before mutator or bus rewrites.

## Run Modes

Colony keeps the current five-slot behavior:

```powershell
python tui.py "goal text" --mode colony --model-profile nemotron_parallel
python reactor.py --mode colony --goal "goal text" --model-profile nemotron_parallel
```

Unicore runs one rod with the documented baseline persona:

```powershell
python tui.py "goal text" --mode unicore --model-profile nemotron --unicore-persona generalist
python reactor.py --mode unicore --goal "goal text" --model-profile nemotron --unicore-persona generalist
python main.py "goal text" --model-profile nemotron --persona generalist --slot 1
```

The default TUI mode remains `colony` to preserve current behavior. Explicit `--mode unicore` is the Phase 0 baseline path.

## Single-Rod Baseline

The primary unicore baseline persona is `prompts/personalities/generalist.txt`.

It is intentionally a do-everything rod: planner, actor, verifier, browser operator, filesystem worker, repo worker, and external-AI coordinator in one process. It does not delegate to sibling rods.

For a stronger baseline comparison, Phase 0 can also run:

```powershell
python main.py "goal text" --model-profile nemotron --persona implementor --slot 1
python main.py "goal text" --model-profile nemotron
```

Those cover the existing execution-heavy persona and the current no-persona fallback.

## Accepted Owner Task List

These are the owner-provided real-machine tasks for Phase 0:

1. open calculator, add two numbers, and get the result copied from the calculator into the notepad, save file on desktop.
2. open chrome and play on youtube shakira waka waka
3. open chrome and use grok.com ai to provide to him the single source code file of the endgame-ai workspace and asking what endgame is why it is asking and asking for code review, then when the grok instructions are provided, the endgame-ai system must validate if they can be implemented and the implementation must happen and then system must find a way, to validate the changes, that the entire system will benefit from them, this actually must be explained via multiturn conversation with grok, so endgame-ai asks grok for review of file and then follows the grok suggestion and asks grok if needed for clarifications and treat grok as an persona that the endgame-ai system must be aware of , its a large remote ai model that can act as part of the system on demand of the system, the realization of that by the endgame-ai itself will be a succes
4. post on x.com and linkedin.com usin chrome an updates about endgame-ai evolution process and self maintenance on behalf of owners account

The same fixtures are available from:

```powershell
python ablation.py list-tasks
```

Run a fixture by task id:

```powershell
python tui.py --mode unicore --ablation-task-id phase0_calc_notepad
python tui.py --mode colony --ablation-task-id phase0_calc_notepad
```

## Metrics

Every reactor run writes a manifest and rolling summary under `runtime/ablation/<run_id>/`.

The summary includes all core metric fields from the README:

- task success rate
- first-pass success
- external verifier agreement
- median and p95 latency
- tokens per solved task
- bus overhead ratio
- solution diversity
- mutation uplift
- regression rate
- crash recovery rate

Some fields remain `null` until the run has enough evidence or an external/human verdict. That is intentional: Phase 0 logging records missing evidence instead of pretending it exists.

Summarize the latest session manually:

```powershell
python ablation.py summarize --session latest
```
