# Entity

An organism that is a markdown file. `entity.md` holds the goal, the memory, and the whole
topology (in its `## config` block). `entity.py` is a tiny engine that reads the board, renders
one LLM request from the sections a stage declares, writes the reply back, execs any returned
code, and routes to the next stage. There are no node classes.

## run

```
set XAI_API_KEY=...            # required for live turns
python entity.py entity.md            # live loop
python entity.py entity.md --dry      # print the assembled request for the current stage, stop
python entity.py entity.md --once     # one stage then stop
python entity.py entity.md --inject FILE   # use FILE as the reply (no LLM), run its exec, stop
```

## parts

- `entity.md` — the organism (emailable). Edit `## goal` any time. Edit `## config` to add,
  rename, or re-prompt a stage; changes take effect on the next turn.
- `entity.py` — the engine (~150 lines). Knows nothing about executor/verify/recover.
- `capabilities.py` — the hands. The one native dependency. On first use it downloads the
  Windows body files (`core_desktop.py`, `core_observation.py`) from GitHub raw and caches
  them under `.body_cache/`, then imports them. Change `_REPO`/`_BRANCH` in it to point at a
  different body.

The logic ships as a document; the hands ship as a pointer to raw.githubusercontent.
