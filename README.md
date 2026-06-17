# endgame-ai

## System Levels

```mermaid
flowchart TB
    subgraph LEVEL1["LEVEL 1: SLOT (proven, tested, 325 LOC)"]
        direction LR
        P1["Planner"] --> A1["Actor"] --> V1["Verifier"]
        V1 -->|"DONE"| P1
        V1 -->|"NOT_DONE"| RF["Reflector"]
        RF -->|"diagnosis"| MU["Mutator"]
        MU -->|"executes one-shot script<br/>mutates prompts/config/anything"| P1
        V1 -->|"UNKNOWN"| A1
    end

    subgraph LEVEL2["LEVEL 2: COLONY (proven, tested, 1422 LOC total)"]
        direction TB
        GOAL[/"python tui.py 'goal'"/] --> COMMS["CommsOperator<br/>decomposes + routes"]

        subgraph BUS_AREA["Shared Bus (in-memory blackboard)"]
            BUS[("Bus<br/>route | evidence | verdict<br/>diagnosis | mutation | task")]
        end

        COMMS <--> BUS

        subgraph SLOTS["4 Specialist Slots (same code, different personality prompts)"]
            S1["architect<br/>design + strategy"]
            S2["implementor<br/>execution + GUI + code"]
            S3["reviewer<br/>verification + quality"]
            S4["devops<br/>git + system health"]
        end

        BUS <--> S1
        BUS <--> S2
        BUS <--> S3
        BUS <--> S4

        GM["Global Mutator<br/>in-place planner prompt evolution"]
        GM <--> BUS
        GM -.->|"tunes planners"| S1
        GM -.->|"tunes planners"| S2
        GM -.->|"tunes planners"| S3
        GM -.->|"tunes planners"| S4

        LOCK{{"Actor Lock"}}
        LOCK --- S2

        subgraph DESKTOP["Windows 11 Desktop"]
            OBS["Mouse hover probe"]
            ACT["GUI actions"]
            SUB["Subprocess + filesystem"]
        end

        S2 <--> DESKTOP
    end

    subgraph LEVEL3["LEVEL 3: ORGANISM (not built, needs ~300 LOC network transport)"]
        direction TB
        C1["Colony A<br/>(machine 1)"]
        C2["Colony B<br/>(machine 2)"]
        NETBUS[("Network Bus")]
        C1 <--> NETBUS
        C2 <--> NETBUS
    end

    LEVEL1 -->|"4 instances form"| LEVEL2
    LEVEL2 -->|"N instances would form"| LEVEL3
```

## Execution Flow

```mermaid
sequenceDiagram
    participant U as User
    participant CO as CommsOperator
    participant B as Bus
    participant P as Planner
    participant A as Actor
    participant V as Verifier
    participant R as Reflector
    participant M as Mutator
    participant D as Desktop/Subprocess

    U->>CO: "goal"
    CO->>B: route records (decomposed sub-goals)
    B-->>P: slot picks up routed goal

    P->>P: plan task + contract
    P->>B: publish task record
    P->>A: next

    A->>D: execute (subprocess or GUI)
    D-->>A: output/observation
    A->>B: publish evidence
    A->>V: next (claimed_done)

    V->>V: judge evidence against contract
    alt DONE
        V->>B: publish verdict DONE
        V->>P: next task
    else NOT_DONE
        V->>B: publish verdict NOT_DONE
        V->>R: next
        R->>R: diagnose root cause
        R->>B: publish diagnosis
        R->>M: next
        M->>M: generate one-shot Python script
        M->>D: execute script ONCE (mutates prompts/files/anything)
        D-->>M: result
        M->>B: publish mutation record
        M->>P: next cycle (with mutated state)
    else UNKNOWN
        V->>A: gather more evidence
    end
```

## Mutation Mechanism

```mermaid
flowchart LR
    DENY["Verifier: NOT_DONE"] --> REFL["Reflector<br/>(LLM call: diagnose)"]
    REFL -->|"diagnosis text"| MUT["Mutator<br/>(LLM call: write script)"]
    MUT --> EXEC["run_script()<br/>executes ONCE"]
    EXEC --> EFF["EFFECT:<br/>prompt file rewritten<br/>OR config changed<br/>OR new file created<br/>OR anything"]
    EFF --> NEXT["Next cycle runs<br/>with mutated state"]

    style EXEC fill:#ff9,stroke:#333
    style EFF fill:#9f9,stroke:#333
```

## How to Run

```powershell
python tui.py "your goal"
```

One command. The system decides complexity. The user never manages slots or routing.

| Flag | Purpose |
|------|---------|
| `--host url` | LM Studio address (default: http://localhost:1234) |
| `--no-desktop` | Skip screen observation for pure subprocess tasks |
| `--workspace path` | Working directory |
| `--bus-file path` | Persist bus records to disk |

| Runtime Key | Action |
|-------------|--------|
| Enter | Send new goal |
| 1-4 | Toggle slot on/off |
| q | Quit |

## Governance Model

```
CODE:     permits everything (no restrictions, no guards, no permission checks)
PROMPTS:  instruct who does what (soft governance, not enforcement)
BUS:      records what happened (observability, feedback)
VERIFIER: judges outcomes (correction signal)
CYCLE CAP: 5 attempts then abandon (emergency brake, only hard limit)
```

The system is **unsecured by design**. The mutator can rewrite any file, execute any command, modify any prompt. This is the self-evolution mechanism. Any restriction in code would create a dead zone in the adaptation space.

The prompts tell the local mutator to tune actor/verifier only. The global mutator tunes planners. But nothing in code enforces this. If the local mutator touches the planner, the next cycle's verifier will show whether that helped or hurt. Bad mutations self-correct through the feedback loop.

## What Differentiates Slots

All slots run the same `Slot` class. They differ by:

1. **Personality prompt** — loaded from `prompts/personalities/{name}.txt` or `prompts/{name}/personality.txt`
2. **Routed goal** — CommsOperator sends different sub-goals to different slots
3. **can_act_desktop** — only implementor touches the GUI (others use subprocess)

The LLM behaves differently because the personality prompt tells it what it specializes in. The code is identical. This means any slot can evolve into any role if the mutator rewrites its personality prompt.

## Files (1422 LOC)

```
endgame-ai/
  tui.py        (225 LOC)  Entry point + display + keyboard
  colony.py     (175 LOC)  CommsOperator + GlobalMutator + orchestration
  slot.py       (325 LOC)  Planner + Actor + Verifier + Reflector + Mutator
  desktop.py    (428 LOC)  Screen observation + GUI actions
  llm.py        (112 LOC)  LM Studio HTTP client
  actions.py    ( 82 LOC)  Verb executor
  bus.py        ( 75 LOC)  Shared blackboard
  prompts/                  Mutable role prompts (governance layer)
    planner.txt
    actor.txt
    verifier.txt
    reflector.txt
    mutator.txt
```

No external dependencies. Python 3.12+ stdlib only.

## LLM: Nemotron 4B

- ~30-60s per response. One cycle = 2-4 LLM calls.
- Frequently returns malformed JSON. Handled by regex fallback parsing.
- Limited context. Prompts kept short. History capped at 6 entries.
- Will make mistakes. That is expected. The reflector/mutator loop exists because of this.
- Temperature 0.12 (low creativity, high consistency).

## Requirements

- Windows 11
- Python 3.12+
- LM Studio running with any model loaded

---

## HANDOVER FOR AI CONTINUATION

If you are an AI coding tool continuing work on this project, read this section.

### Identity

`endgame-ai` — a self-evolving agentic runtime. 1422 LOC Python. Zero dependencies. Operates Windows 11 desktop autonomously. Runs on small local models (Nemotron 4B).

### Architecture Rules

1. **OOP with injection.** No globals, no singletons, no env vars.
2. **Bus is the only IPC.** Slots never call each other. All through bus records.
3. **Single process.** No subprocesses for slots. No reactor. No file IPC.
4. **No code-level constraints.** Governance is via prompts, not enforcement.
5. **Prompts are mutable at runtime.** Mutator can rewrite them. That's the mechanism.
6. **Cycle cap = 5.** Only hard safety net. Never remove.
7. **Verifier never trusts actor.** Requires independent evidence. Never shortcut this.
8. **Colony is composable.** Takes (llm, bus, prompts_dir, workspace). Can be instantiated N times.
9. **Mutation is one-shot.** Mutator writes a script, it runs once, it's done. Not a loop.
10. **Reflector diagnoses, Mutator prescribes.** Two LLM calls, two concerns.

### File Responsibilities

| File | Does | Does NOT |
|------|------|----------|
| `bus.py` | Store/query records | Enforce permissions |
| `slot.py` | Run the P→A→V→R→M loop | Decide which slot gets what goal |
| `colony.py` | Route goals, manage slots | Execute tasks |
| `tui.py` | Display + input + orchestrate | Business logic |
| `desktop.py` | Observe screen + act on GUI | Decide what to click |
| `llm.py` | HTTP to LM Studio | Parse domain logic |
| `actions.py` | Execute verbs on elements | Decide which verb |

### Testing Without LM Studio

```python
from slot import Slot
from bus import Bus
from llm import LLMResult

class MockLLM:
    def __init__(self, responses):
        self._r = list(responses); self._i = 0
    def call(self, system, user, **kw):
        if self._i < len(self._r):
            r = self._r[self._i]; self._i += 1; return r
        return LLMResult(text='')

bus = Bus()
slot = Slot(name="test", llm=MockLLM([...]), bus=bus, prompts_dir=..., workspace=...)
slot.set_goal("test")
result = slot.step()
```

### The System Will Error

Errors are input to self-correction. Do not prevent all errors. Ensure:
1. Errors are caught (try/except in LLM-facing code)
2. Errors produce bus records (so reflector/mutator can read them)
3. Cycle cap triggers (so loops terminate)
4. Planner receives failure history (so it replans differently)

**Correct behavior: plan → fail → reflect → mutate → retry differently → succeed.**
