# endgame-ai

> A single Markdown document that wakes up, looks at your screen, writes its own Python, runs it,
> checks its own work with a part of itself that isn't allowed to lie, and rewrites its own rules —
> then forgets everything and does it again. No framework. No memory store. No tool menu. One file.

---

## What you need to run it

Here is the burger. Here is the meat. There is no plate.

- **An xAI API key.** Get one at [x.ai](https://x.ai). That is the brain.
- **Windows 11.** Because it drives a *real* desktop — real mouse, real keyboard, real windows.
- **Python.** The standard one. [python.org](https://www.python.org/downloads/).

That's it. That's the whole shopping list.

No `npm install`. No Docker. No vector database. No LangChain. No orchestration layer. No 40-file
`src/` tree. No `requirements.txt` with 200 pinned transitive dependencies. No cloud account to
provision. The body imports only Python's standard library. You want to know where the "agent
framework" is? You're reading it. It's one document.

## How you use it

Point it at the document, hand it one sentence, and let go.

First, write your goal into the document — it has a section literally named `## goal`. Put one plain
sentence there, for example:

```
## goal
make my desktop wallpaper solid black
```

Then wake it up. A tiny bootstrap reads the document's own `engine` section and runs it:

```powershell
## Command 1:
$env:XAI_API_KEY = "your-key-here"

## Command 2: (one-liner, run it from the dir where the file is located)
python -c 'import re,pathlib,sys; f=chr(96)*3; t=pathlib.Path(sys.argv[1]).read_text(encoding=\"utf-8\"); m=re.search(r\"##\s+engine\s*\n\"+f+r\"python\n(.*?)\n\"+f+r\"\s*\n##\s+\", t, re.S); exec(m.group(1), {\"BOARD\": sys.argv[1], \"ARGV\": sys.argv[2:]})' .\endgame.md
```

`Command 2` is about as small as a launcher gets, it reads the `engine` section out of the Markdown and executes it, with the document as its world:

```python
import pathlib, sys
fence = chr(96) * 3                      # the triple-backtick code-fence marker
board = pathlib.Path(sys.argv[1])
text = board.read_text(encoding="utf-8")
engine = text.split("## engine")[1].split(fence + "python")[1].split(fence)[0]
exec(engine, {"BOARD": str(board), "ARGV": sys.argv})
```

That's the entire interface. A sentence in the document. A living desktop out. It reads its own
`engine`, comes alive with your goal as its only instruction, and starts *looking, thinking, acting,
and checking* — turn after turn — until the goal is independently proven done, or you close the
window.

---
