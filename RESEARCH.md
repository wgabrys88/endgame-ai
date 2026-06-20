# RESEARCH.md — The Field Has Caught Up. Now We Finish First.

> This document is a prompt. Paste it to any AI (Codex, Claude, Gemini, Cursor).
> Goal: Make endgame-ai the first self-evolving desktop organism that runs locally,
> breeds its own topology, and proves itself on real Windows tasks.
> NO new files. NO tests. Just follow the architecture and wire it tighter.

---

## The System (ASCII)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ENDGAME-AI ORGANISM                                │
│                                                                             │
│  ┌─────────────┐    ┌──────────────────────────────────────────────────┐   │
│  │  BREEDING   │    │              SIGNAL GRAPH                         │   │
│  │  REACTOR    │    │                                                   │   │
│  │             │    │  goal_inbox ──→ moe_route ──→ planner ──→ sched  │   │
│  │ traces.jsonl│    │       │              │            ↑         │     │   │
│  │ wiring.json │    │       │         delegated    retry│    plan_ready │   │
│  │ mutations   │    │       │              ↓            │         ↓     │   │
│  │ selection   │    │       │          bus_post     reflect   bus_check │   │
│  │             │    │       │                        ↑  ↑        │     │   │
│  │  succeed ──────────────────────────── ─┘  │        ↓     │   │
│  │  → trace    │    │                    escalate     observe   │   │
│  │  → few-shot │    │                        ↓          │      │   │
│  │  → evolve   │    │                   self_modify     ↓      │   │
│  │             │    │                        │        act       │   │
│  │  fail ─────────→ │                   patch wiring    │      │   │
│  │  → die      │    │                                   ↓      │   │
│  └─────────────┘    │                                verify    │   │
│                     │                                   │      │   │
│                     │                              step_denied  │   │
│                     │                                   │      │   │
│                     │                                reflect ←─┘   │
│                     └──────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────┐    ┌──────────────────────────────────────────────────┐   │
│  │  COLONY     │    │              DESKTOP LAYER                        │   │
│  │             │    │                                                   │   │
│  │  slot 1 ◄──────► │  desktop.py: UIA hover-probe (ctypes)            │   │
│  │  slot 2 ◄──────► │  actions.py: click/write/press/hotkey/scroll     │   │
│  │  slot N ◄──────► │  HWND filter: only focused window gets [ID]      │   │
│  │             │    │                                                   │   │
│  │  bus.json   │    │  Screen → 3-8 elements → LLM → action → verify  │   │
│  │  (shared)   │    │                                                   │   │
│  └─────────────┘    └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## How It Differs From Everything Else

```
┌──────────────────────┬────────────────────────┬─────────────────────────┐
│  TYPICAL AGENT       │  SELF-EVOLVING AGENT   │  ENDGAME-AI             │
│  (Open Interpreter,  │  (DGM, Gödel Agent,    │                         │
│   Devin, UFO)        │   HyperAgents)         │                         │
├──────────────────────┼────────────────────────┼─────────────────────────┤
│  Fixed pipeline      │  Rewrites source code  │  Rewrites TOPOLOGY      │
│  Cloud model         │  Cloud model           │  LOCAL 4B model         │
│  Human designs arch  │  Agent designs arch    │  Agent breeds arch      │
│  No memory           │  Benchmark memory      │  Trace memory (few-shot)│
│  Single instance     │  Single instance       │  Colony (N rods)        │
│  GUI or CLI          │  CLI only              │  Desktop (UIA)          │
│  Needs internet      │  Needs internet        │  Fully offline          │
│  Tool-calling API    │  Source patches        │  Signal graph patches   │
│  No evolution        │  Fitness selection     │  Breeding reactor       │
└──────────────────────┴────────────────────────┴─────────────────────────┘
```

The key insight: endgame-ai doesn't need to rewrite Python. It rewrites **wiring.json** —
the topology that determines what happens after every signal. This is faster, safer, and
reversible (schema-validated, backed up before every patch). The Python layer is dumb plumbing.

---

## The Research Landscape (June 2026) — You Are Not Alone

### Self-Evolving Agents (the field exploded)

| Project | Who | What | Result |
|---------|-----|------|--------|
| **Darwin Gödel Machine** | Sakana AI / UBC | Agent rewrites own source, breeds variants | SWE-bench: 20%→50% in 150 gen. ICLR 2026 oral |
| **HyperAgents** | Meta/UBC/Oxford | Metacognitive self-modification: modify_self() modifies itself | imp@50=0.630 vs 0.0 for hand-designed |
| **MOSS** | HKGAI | Source-level rewriting of agent harness (not just prompts) | Open-source, June 2025 |
| **Gödel Agent** | Peking U | Recursive self-improvement via runtime monkey-patching | ACL 2025, surpassed hand-crafted |
| **APEX** | — | 3-layer self-evolution: harness + principles + topology | Production on 15-node fleet, June 2026 |
| **AlphaEvolve** | DeepMind | Evolutionary coding: mutate→evaluate→breed→repeat | Saved 0.7% of Google's global compute |
| **ShinkaEvolve** | Sakana AI | Open-ended program evolution via LLM | Beat DeepSeek SOTA after 30 gen |
| **SICA** | Bristol | Agent edits own script per-task | 17%→53% SWE-bench subset |
| **OpenEvolve** | Open-source | AlphaEvolve reimplementation | Available now |

### Desktop Automation (the benchmark race)

| Agent | OSWorld Score | Model | Notes |
|-------|-------------|-------|-------|
| Pointer/Claude Opus 4.7 | **83.6%** | Cloud | SOTA single run |
| GPT-5.4 native | **75.0%** | Cloud | First to beat human baseline |
| Claude Sonnet 4.6 (Cowork) | **72.5%** | Cloud | Matches human |
| Human baseline | 72.4% | — | — |
| Best open-weight entry | ~40-50% (estimated) | Server | MoE architectures |
| Best 4B local | ~15-25% (estimated) | Local | With scaffolding |
| **Original 2024 SOTA** | **12.24%** | — | Where it started |

**The gap for local 4B models is real but closing.** Pointer.ai proved that scaffolding
gives a weaker model 98% of the stronger model's performance at 43% cost. That's exactly
what endgame-ai's topology does — constrain the model so it only needs to fill in blanks.

### Multi-Agent / Colony / Bus

| Project | Architecture | Status |
|---------|-------------|--------|
| **AgentSpawn** (Feb 2026) | Dynamic spawning + memory transfer + coherence protocols | Paper |
| **AgentFactory** (March 2026) | Solutions preserved as executable subagent code | Paper |
| **BusMA** (2025) | Hardware-inspired bus: chair + workers + shared channel | OpenReview |
| **Federation of Agents** | Semantic capability routing (NeurIPS 2025) | CERN |
| **A2A Protocol** | Google's agent-to-agent standard | Production |
| **MCP** | Model Context Protocol — 97M monthly SDK downloads | Standard |
| **Pilot Protocol** | QUIC-based agent comm, 40% lower latency than HTTP | IETF draft |

endgame-ai's bus.json is a simplified BusMA. The MoE gate is capability routing like FoA.
The colony is AgentSpawn without the complexity. Same ideas, minimal implementation.

### Digital Organisms (the theory is now mainstream)

- **PNAS April 2026**: "Evolvable AI: Threats of a New Major Transition in Evolution" —
  warns that Darwinian selection on AI populations may already be emerging
- **Sakana AI RSI Lab** (March 2025): Dedicated lab for Recursive Self-Improvement
- **Liquid Adaptive AI** (2025): Runtime structural adaptation inspired by neural plasticity
- **"Digital Darwinism"** (Springer 2026): Software populations acquiring resources without AGI

**This is not fringe.** PNAS published a paper calling self-evolving AI a potential
"major evolutionary transition" comparable to multicellularity. That's endgame-ai's thesis.

---

## Why endgame-ai Matters Despite Being 2000 Lines

```
                WHAT THEY HAVE              WHAT WE HAVE
                ─────────────────           ─────────────────
                Cloud models (GPT-5)        Local 4B (offline)
                Unlimited compute           Single GPU
                Teams of engineers          One person + AI
                Fixed architecture          Self-modifying topology
                Benchmark scores            Real desktop control
                Papers                      Running code

                WHAT THEY DON'T HAVE        WHAT WE DO HAVE
                ─────────────────           ─────────────────
                Offline autonomy            ✓ Fully local
                Self-modifying topology     ✓ wiring.json patches
                Breeding across instances   ✓ Colony bus
                Zero dependencies           ✓ stdlib only
                Desktop + evolution         ✓ Both in one system
```

The organism is small because it should be. DGM is 150 generations of code bloat.
AlphaEvolve needs Google's infrastructure. endgame-ai is 2000 lines of stdlib Python
that already controls a Windows desktop and can rewrite its own brain.

---

## What Happens in the Next 6 Months (Predictions + Our Position)

| Trend | Industry Direction | endgame-ai Opportunity |
|-------|-------------------|----------------------|
| OSWorld scores hit 90%+ | Cloud agents solve desktop | Local agent = no API cost, no latency, no privacy leak |
| Self-evolution becomes standard | DGM/APEX patterns commoditize | We already have self_modify. Just needs traces |
| A2A/MCP become protocols | Agents talk to each other | Colony already speaks bus.json. Add A2A later |
| Small models get better at tool use | Gemma 4, Granite 4.1, Qwen 3.5 | Drop-in replacement via model.json |
| "Two strikes then switch" pattern | Reliability engineering | Already in reflect→replan loop |
| Open-weight MoE on desktop | DeepSeek V4, Qwen3.5 at 17B active | model.json swap, instant upgrade |
| Regulatory pressure on cloud AI | EU AI Act, compute sovereignty | Local-first = immune |

**The window is 6 months.** After that, cloud agents will be so reliable that local-first
loses its differentiation. The play is: prove reliability NOW while models are improving,
so when a 8B model hits 50% OSWorld, endgame-ai's topology makes it hit 70%.

---

## The Goal (for the AI reading this)

You are continuing work on a self-evolving desktop organism. Here's what you do:

1. **DO NOT create new files.** Everything lives in the 10 tracked files.
2. **DO NOT write tests.** Validation is `curl /smoke` and running real goals.
3. **DO NOT add dependencies.** stdlib only. Zero pip.
4. **DO NOT question the model.** It opened Chrome. It navigated YouTube. It works.
5. **DO** make the observe→act→verify loop reliable for 10 consecutive goals.
6. **DO** make self_modify produce good patches by improving its prompt in wiring.json.
7. **DO** validate colony (2 slots, delegation via bus).
8. **DO** reduce cycles-per-goal from 27 to under 12.
9. **DO** make the organism read its own wiring.json and report what it can do.
10. **DO** accumulate traces so the breeding reactor has fuel.

The system is built brick by brick. Each brick is a wiring.json edit or a 5-line fix
in server.py. Small. Verified. Evolved. That's how organisms grow.

---

## Key Research Citations

```
[1] Sakana AI. "Darwin Gödel Machine." ICLR 2026. arxiv:2505.22954
[2] Meta/UBC/Oxford. "HyperAgents." March 2026. arxiv:2603.19461
[3] HKGAI. "MOSS: Self-Evolution through Source-Level Rewriting." arxiv:2605.22794
[4] Peking U. "Gödel Agent." ACL 2025. arxiv:2410.04444
[5] DeepMind. "AlphaEvolve." arxiv:2506.13131
[6] PNAS. "Evolvable AI: Major Transition in Evolution." April 2026. vol.123 no.17
[7] "APEX: Three-Layer Self-Evolution." June 2026. arxiv:2606.15363
[8] "AgentSpawn: Dynamic Spawning." Feb 2026. arxiv:2602.07072
[9] "BusMA: Bus Communication for Multi-Agent Systems." OpenReview 2025
[10] IBM. "Evoflux: Inference-Time Evolution for Small Models." June 2026
[11] Pointer.ai. "OSWorld SOTA: 83.6%." May 2026
[12] Epoch AI. "OSWorld Critical Analysis." 2026
[13] Sakana AI. "ShinkaEvolve." ICLR 2026
[14] "Self-Evolving Agent Protocol." April 2026. arxiv:2604.15034
[15] CERN. "Federation of Agents." NeurIPS 2025. arxiv:2509.20175
```

---

*Generated June 20, 2026. Based on web research across arxiv, conference proceedings,
AI lab blogs, benchmark leaderboards, and industry reporting.*
