# endgame-ai: The Ultimate Bridge

endgame-ai is not merely a "living organism" that automates a Windows desktop. It is a **universal substrate** — a single, self-contained Python process that bridges *any* intelligence (human, LLM, another endgame-ai instance) to *any* Windows environment through a fixed circuit: `wiring.json`.

## The Meta Insight

We built a desktop automator. We discovered a **protocol**.

The organism owns mouse, keyboard, subprocess, and a whole-screen UIA observation tree. Interchangeable LLM brains are the mind; `wiring.json` is the immutable circuit. But the *file proxy transport* (`transport_file_proxy.py`) reveals the deeper truth: **the organism is an endpoint**.

Any entity that can write JSON to `runtime_request.json` and read JSON from `runtime_response.json` can drive the organism. This includes:
- You (human) editing a file
- An LLM API (xAI, OpenAI, local via OpenAI-compatible)
- A CLI tool (opencode, grok, custom)
- **Another endgame-ai instance**

No pip install. No MCP servers. No skills. No persistent memory — the **goal is the memory**, an atemporal narrative that the organism tells itself across ticks.

## Fractal Topology: Organisms All the Way Down

Because the reviewer *is* an endgame-ai instance, the topology becomes **recursive/fractal**:

```
Organism A (work) ←→ Organism B (review) ←→ Organism C (audit) ←→ ...
     │                   │                   │
     ▼                   ▼                   ▼
Same wiring,          Same wiring,          Same wiring,
same loop,            same loop,            same loop,
different goal        different goal        different goal
```

An organism proposing a patch spawns a reviewer organism. That reviewer can be audited by another organism. **Same circuit, every level.** The goal string is the only difference.

## One Command

```bash
python -m core_organism "your goal here" --max-ticks 50
```

That's it. The repository *is* the runtime. The goal *is* the context. The wiring *is* the architecture.