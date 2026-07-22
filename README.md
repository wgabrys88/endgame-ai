# endgame-ai

> A single Markdown document that wakes up, looks at your screen, writes its own Python, runs it,
> checks its own work with a part of itself that isn't allowed to lie, and rewrites its own rules —
> then carries its faculties' feedback forward and does it again. No framework. No separate memory
> store. No tool menu. One file.

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

Then wake it up in the required mode. Each command downloads the pushed board and runs its own `engine`:

```powershell
iwr https://raw.githubusercontent.com/wgabrys88/endgame-ai/lego-refactor/endgame.md -OutFile .\endgame.md;python -c 'import sys;p=sys.argv[1];s=open(p,encoding=\"utf8\").read();exec(s.split(\"## engine\n```python\n\",1)[1].split(\"\n```\",1)[0],{\"BOARD\":p,\"ARGV\":sys.argv[2:]})' .\endgame.md --mode xai
iwr https://raw.githubusercontent.com/wgabrys88/endgame-ai/lego-refactor/endgame.md -OutFile .\endgame.md;python -c 'import sys;p=sys.argv[1];s=open(p,encoding=\"utf8\").read();exec(s.split(\"## engine\n```python\n\",1)[1].split(\"\n```\",1)[0],{\"BOARD\":p,\"ARGV\":sys.argv[2:]})' .\endgame.md --mode lmstudio
iwr https://raw.githubusercontent.com/wgabrys88/endgame-ai/lego-refactor/endgame.md -OutFile .\endgame.md;python -c 'import sys;p=sys.argv[1];s=open(p,encoding=\"utf8\").read();exec(s.split(\"## engine\n```python\n\",1)[1].split(\"\n```\",1)[0],{\"BOARD\":p,\"ARGV\":sys.argv[2:]})' .\endgame.md --mode acp
iwr https://raw.githubusercontent.com/wgabrys88/endgame-ai/lego-refactor/endgame.md -OutFile .\endgame.md;python -c 'import sys;p=sys.argv[1];s=open(p,encoding=\"utf8\").read();exec(s.split(\"## engine\n```python\n\",1)[1].split(\"\n```\",1)[0],{\"BOARD\":p,\"ARGV\":sys.argv[2:]})' .\endgame.md --mode file_proxy
```

The command reads the `engine` section out of the Markdown and executes it, with the document as its world.

The selected mode uses LM Studio Chat Completions, xAI Responses, native `grok agent stdio`, or `file_proxy`; every call remains an independent stateless turn using the same cache-ordered prompt and strict record schema. The xAI mode reads `XAI_API_KEY`. File proxy publishes `runtime_request.json`; answer it in `runtime_response.json` as `{"id":"copied request id","record":{...}}`.

That's the entire interface. A sentence in the document. A living desktop out. It reads its own
`engine`, takes your goal as its sole source of purpose, and starts *looking, thinking, acting, and
checking* with its accumulated developer feedback as advisory context — turn after turn — until the
goal is independently proven done, or you close the window.

---
