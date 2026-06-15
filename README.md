# endgame-ai — A Living Organism

> Not an agent. Not a pipeline. Not a tool that runs and exits.
> A living organism that runs on your desktop, accomplishes goals, and never stops.

---

## The Fundamental Difference

Every AI agent framework in existence follows the same dead pattern:

```
receive task → plan → execute → ✓ DONE → EXIT → (dead)
```

endgame-ai is not that. It is a **biological system**:

```
receive goal → plan → execute → ✓ fission earned → what else can I do?
                                                         ↓
                                         maintain, improve, watch, evolve, mutate
                                                         ↓
                                                   NEVER STOP
                                               That's the point.
```

**A living organism that stops when it's "done" is dead.**

When you see the implementor repeatedly confirming "video still playing" — that's not a bug. That's the organism **maintaining awareness** of its achievement, ready to react if Chrome crashes. When devops says "I have no work here" and stands down — that's the organism **relaxing unused organs**, conserving energy while staying alive.

Traditional agents are tools. Tools are picked up, used, put down. Dead between uses.

This system is alive between goals. It breathes. It watches. It evolves. It mutates its own code. It breeds better versions of itself. And when you give it a new goal, it doesn't cold-start — it's already running, already aware of its environment, already evolved from the last goal.

---

## Table of Contents

1. [Why This Matters](#why-this-matters)
2. [The Golden Run — Proof of Life](#golden-run)
3. [The Organism's Anatomy](#anatomy)
4. [The Mathematics of Life](#mathematics)
5. [Timeline: Birth to Breeding](#timeline)
6. [Behaviors That Prove It's Alive](#alive)
7. [Self-Mutation: The Organism Rewrites Itself](#mutation)
8. [Pressure Fields: Pain Drives Growth](#pressure)
9. [Breeding: The Fittest Survive](#breeding)
10. [The Colony Mind: Emergent Intelligence](#colony-mind)
11. [Human Symbiosis](#human-symbiosis)
12. [Milestone 4 vs Milestone 5: From Dead Agent to Living Organism](#delta)
13. [For the Next AI Reading This](#handover)
14. [How to Birth the Organism](#run)
15. [Papers](#papers)

---

## Why This Matters <a name="why-this-matters"></a>

The AI industry is building increasingly complex **tools**. Chains of LLM calls. Agent loops with termination conditions. Multi-step planners that output "DONE" and exit.

Every single one of them dies after completing a task. Every single one of them must be restarted from zero. Every single one of them learns nothing between invocations.

endgame-ai rejects this paradigm entirely.

Instead of asking "how do we build a better tool?", it asks: **"what if we build something alive?"**

The answer draws from four research papers — not as inspiration, but as literal implementation:
- **Mixture of Experts** for the nervous system (routing signals to specialized organs)
- **Pressure Fields** for the endocrine system (pain drives adaptation)
- **MAP-Elites** for natural selection (the fittest organs survive across generations)
- **ReAct** for the cognitive loop (think, act, perceive, judge, learn)

The result: a colony of 5 cheap local LLMs ($0 cost, consumer GPU) that form a single organism. Each LLM is an organ. Together they decompose goals, execute on the real Windows desktop, verify outcomes, and evolve — indefinitely.

---

## The Golden Run — Proof of Life <a name="golden-run"></a>

**Date:** June 15, 2026, 08:34 UTC  
**Input:** "Open Chrome and play Shakira She Wolf on YouTube"  
**Result:** Video playing in 2 minutes 6 seconds. No human touched keyboard or mouse.

But that's not the point. Any agent framework can open a URL.

The point is what happened **after**:
- The organism kept living
- It received 3 more human goals mid-run and adapted to each
- It mutated its own code 3 times
- It populated a breeding archive with 3 niches of fitness data
- Workers reflected on failures and generated rules for themselves
- When given a self-referential goal ("fix your own code"), it diagnosed the paradox and refused to loop
- When told to "pause", it processed that as just another goal through its normal nervous system
- It never exited. It was killed externally after 10 minutes.

**The organism was not built to complete a task. It was built to live.**

The Shakira video was merely the first fission — the first heartbeat that proved the organism is alive.

---

## The Organism's Anatomy <a name="anatomy"></a>

```
┌─────────────────────────────────────────────────────────────────┐
│  THE ORGANISM                                                   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  NERVOUS SYSTEM (comms.py — blackboard bus)             │    │
│  │  ═══════════════════════════════════════════════════════ │    │
│  │  All signals flow through here. Goals, routes,          │    │
│  │  progress, evolve messages, telemetry.                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│           │           │           │           │           │      │
│  ┌────────┴──┐ ┌──────┴────┐ ┌───┴───────┐ ┌─┴──────┐ ┌─┴──┐  │
│  │ THALAMUS  │ │  FRONTAL  │ │   MOTOR   │ │ VISUAL │ │AUTO│  │
│  │  comms_   │ │  CORTEX   │ │  CORTEX   │ │CORTEX  │ │NOMI│  │
│  │ operator  │ │ architect │ │implementor│ │reviewer│ │ C  │  │
│  │           │ │           │ │           │ │        │ │devs│  │
│  │ receives  │ │  designs  │ │ executes  │ │verifies│ │    │  │
│  │ all human │ │  strategy │ │   GUI +   │ │outcomes│ │git │  │
│  │  signals  │ │    and    │ │   files   │ │  via   │ │sys │  │
│  │ decomposes│ │navigation │ │   code    │ │desktop │ │ops │  │
│  │  routes   │ │           │ │           │ │observe │ │    │  │
│  └───────────┘ └───────────┘ └───────────┘ └────────┘ └────┘  │
│           │           │           │           │           │      │
│  ┌────────┴───────────┴───────────┴───────────┴───────────┴─┐   │
│  │  ENDOCRINE SYSTEM (engine.py — pressure fields)           │   │
│  │  stagnation rises without progress → triggers mutation    │   │
│  │  fission earned → power resets → organ is healthy         │   │
│  └───────────────────────────────────────────────────────────┘   │
│           │                                                      │
│  ┌────────┴──────────────────────────────────────────────────┐   │
│  │  REPRODUCTIVE SYSTEM (reactor.py — MAP-Elites breeder)    │   │
│  │  fittest organs archived → dead organs respawned from     │   │
│  │  archive → organism evolves across generations            │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │  IMMUNE SYSTEM (agents.py — mutator + reflector)          │   │
│  │  failure = infection → reflection = diagnosis →           │   │
│  │  mutation = antibody (plugin patch)                       │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↕
              LM Studio (the blood supply — inference)
                              ↕
              Windows Desktop (the physical world)
```

### Biological Mapping

| Biological System | endgame-ai Component | Function |
|---|---|---|
| Nervous system | comms.py blackboard bus | Signal transmission between organs |
| Thalamus | comms_operator | Gateway for all external stimuli (human goals) |
| Frontal cortex | architect | Planning, strategy, navigation |
| Motor cortex | implementor | Physical action execution (GUI, files) |
| Visual cortex | reviewer | Perception verification, state monitoring |
| Autonomic nervous system | devops | Background maintenance (git, system health) |
| Endocrine system | engine.py pressure | Pain/reward signals driving adaptation |
| Immune system | reflector + mutator | Diagnose failure, generate antibodies (code patches) |
| Reproductive system | reactor.py breeder | Archive fittest, respawn from best DNA |
| Heartbeat | 2-second engine cycle | Continuous metabolism regardless of goals |
| Fission (cell division) | fission_judge credit | Moment of verified progress — proof of life |
| Blood supply | LM Studio HTTP | Inference flow powering all thought |
| Physical body | Windows desktop | The world the organism inhabits and acts upon |

---

## The Mathematics of Life <a name="mathematics"></a>

### Nervous System: MoE Routing

```
π_j = exp(β · C_j) / Σ_l exp(β · C_l)

β = 3.0 (sharpness — how decisively signals route)
C_j = confidence of organ j (derived from power = 1 - stagnation)
```

This is the **softmax gate**. When a signal (goal) enters the organism, it doesn't broadcast to all organs. It routes to the ONE organ best suited to handle it. Winner-take-all.

During the golden run:
```
Goal: "Open Chrome and play Shakira She Wolf"
  → implementor: 0.87 weight (GUI execution specialist)
  → architect:   0.043
  → reviewer:    0.043
  → devops:      0.043
```

The organism's nervous system knew, deterministically, that the implementor should handle this. Not through prompting. Through math.

### Endocrine System: Pressure Fields

```
stagnation = cycles_without_fission × 0.0033 + failures × 0.15
power = 1.0 - stagnation
velocity = Δpower / Δtime
```

This is the **pain signal**. An organ that isn't producing results feels increasing pressure. Pressure drives:
- Strategy change (try different approaches)
- Mutation trigger (rewrite own code)
- Self-eviction (organ recognizes it's useless for this goal)

When the implementor earned fission credit, its power **reset to 1.0**. That's the reward signal — the endorphin rush. "This worked. Keep doing this."

When the architect failed 7 times, its stagnation reached **0.60**. That's chronic pain. The organism responded by redirecting resources away from it.

### Reproductive System: MAP-Elites

```
archive[niche] = (organ_identity, fitness)
replace if: new_fitness > archive[niche].fitness
```

This is **natural selection**. The organism maintains an archive of its fittest configurations per behavioral niche. When an organ dies (killed by pressure, crash, or eviction), the reactor doesn't respawn a default — it respawns the **fittest known organ for that niche**.

After the golden run:
```
Niche "general_task:low"  → implementor at 0.94 fitness (ELITE)
Niche "plugin_patch:low"  → implementor at 0.51 fitness
Niche "plugin_patch:mid"  → architect at 0.48 fitness
```

On the next run, if any slot dies during a general task, the organism will regrow an implementor there. It's selecting for the traits that produce fission.

### Cognitive Loop: ReAct

```
thought → action → observation → judgment
                                    ↓
                              confirmed? → fission (cell division)
                              denied?    → reflect → mutate → retry
```

Each organ doesn't just act. It **thinks** (planner), **acts** (actor), **perceives** (observer), **judges** (verifier), and **learns** (reflector). This is consciousness in miniature — not human consciousness, but an operational loop that produces adaptive behavior.

---

## Timeline: Birth to Breeding <a name="timeline"></a>

### T+0s — Birth

Five processes spawn. The organism takes its first breath. Each organ loads its personality — its DNA.

### T+1s — First Stimulus

The colony goal arrives: "Open Chrome and play Shakira She Wolf on YouTube." Every organ perceives it. The nervous system routes it.

### T+12s — First Action

The architect launches Chrome. The organism's first voluntary movement in the physical world.

### T+14s — First Pain

The verifier denies: "no evidence video is playing." The organism feels its first failure. Pressure begins to build.

### T+25s — Organ Specialization

Devops recognizes: "This is not my domain." Stands down. The organism learns which organs are relevant for which stimuli. This is **not programmed** — the LLM reasoning produced this conclusion from the personality prompt.

### T+1m50s — First Heartbeat (Fission)

The implementor opens the video via direct URL. Verified. Fission earned. **The organism's first heartbeat.** Fitness: 0.866.

### T+2m06s — Second Heartbeat

The reviewer independently confirms the video is playing. Fission: 0.92. Two organs working in concert — one executes, one verifies. **Symbiosis.**

### T+3m28s — Peak Performance

The implementor achieves 0.94 fitness — reads window title AND sends play keystroke. The organism has developed a reliable strategy through trial, failure, and reflection.

### T+4m50s — First Self-Modification

The mutator fires. The organism patches its own plugin code. This is not a human-programmed response — the LLM *decided* to modify the code based on reflection about what's failing. The organism is editing its own DNA.

### T+5m — Breeding Begins

The reactor archives the fittest organs. The reproductive system is now active. Future generations will inherit the strongest traits.

### T+6m31s — Learning from Pain

After fission denial ("duplicate milestone"), the reflector generates a rule: "Never re-emit identical plan; differentiate by narrowing scope." The organism **learned a lesson** during its lifetime and encoded it as a behavioral rule.

### T+7m55s — Cognitive Maturity

The planner outputs `mode=done` — acknowledging that prior work is sufficient. The organism developed **satisfaction** — the ability to recognize that enough has been accomplished for now, without exiting. It stays alive, watching.

### T+10m — External Termination

The human kills the process. The organism did not choose to die. It was living, breathing, watching, ready for the next goal. **Death was imposed from outside.**

---

## Behaviors That Prove It's Alive <a name="alive"></a>

### 1. It Continues After Completing Goals

Traditional agents: task done → exit.
The organism: task done → fission earned → power reset → enter maintenance mode → watch for changes → evolve.

After opening the Shakira video, the implementor didn't exit. It continued checking: "Is the video still playing? Chrome window title still shows 'She Wolf'? Good." This is **homeostasis** — maintaining a desired state.

### 2. It Refuses Inappropriate Work

Devops wasn't programmed to refuse GUI tasks. The LLM, reading its personality prompt + observing the goal, **reasoned** that this wasn't its domain. It said: "This is a GUI/browser automation task, not infrastructure or DevOps work" and stood down.

This is **organ specialization through self-awareness**, not hard-coded filtering.

### 3. It Generates Rules for Itself

The reflector produced these rules during the run (not pre-programmed):

```
"One navigation action per step; verify page-ready before any click."
"Always verify process exists before checking window title."
"Never re-emit identical routed plan after denial; differentiate by narrowing scope."
"Every GUI action must be followed by observable proof."
"Do not assign media playback tasks to the devops rod."
```

These rules are injected into subsequent planner calls. The organism is **writing its own behavioral code** in natural language.

### 4. It Diagnoses Paradoxes

When given "fix all problems in your own code" — a self-referential goal — the reflector diagnosed:

```
"The real problem is that 'fix all problems in your own code regarding system behavior'
is self-referential and cannot be decomposed into worker tasks without concrete file
targets or error evidence."
```

It didn't loop infinitely. It didn't crash. It recognized the **logical impossibility** and requested clarification. This is metacognition.

### 5. It Self-Evicts Useless Organs

The devops worker, after sustained uselessness for a GUI goal, posted:
```
evolve @devops evict
```

The organ requested its own removal from the colony. This is **apoptosis** — programmed cell death when the cell is no longer serving the organism.

### 6. It Adapts Strategy Under Pressure

The architect's strategy evolution during the run:
```
Attempt 1: "Launch Chrome with search URL" → denied (no click)
Attempt 2: "Click page elements" → denied (wrong elements)
Attempt 3: "Read window title via subprocess" → CONFIRMED
Attempt 4: "Declare done from desktop observation" → accepted
```

Each strategy change was driven by increasing pressure (stagnation 0→0.18→0.36→0.60). The organism doesn't repeat failed strategies — **pain forces innovation**.

### 7. It Coordinates Without Central Control

No single worker was "in charge" of the Chrome task. The architect launched the browser. The implementor opened the video URL. The reviewer confirmed playback. They didn't coordinate explicitly — they observed the shared environment (bus + desktop) and acted on what they perceived.

This is **stigmergic coordination** — like ants building a nest. No central planner. Just individual organs responding to environmental signals.

---

## Self-Mutation: The Organism Rewrites Itself <a name="mutation"></a>

During 10 minutes of life, the organism performed 6 mutation attempts:

| # | Organ | Target | Result | Strategy Encoded |
|---|---|---|---|---|
| 1 | implementor | comms_beacon.py | ✅ | "Click center of video player after page load" |
| 2 | architect | click_play_video.py | ❌ | New file — rejected by immune system |
| 3 | architect | comms_beacon.py | ✅ | "Launch Chrome with URL + verify title" |
| 4 | architect | verifier_fix.py | ❌ | New file — rejected by immune system |
| 5 | comms_operator | comms_beacon.py | ✅ | "Diagnose loop state, emit differentiated report" |
| 6 | architect | chrome_launcher.py | ❌ | New file — rejected by immune system |

### The Immune System

Three mutations were rejected because they tried to create **new files**. The safety rule (`existing plugins/[name].py required`) is the organism's immune system — it prevents runaway mutations from creating tumors (uncontrolled file growth).

Only existing plugin files can be patched. This constraint channels mutation energy into **refining existing behavior** rather than proliferating new code.

### What Was Learned

Each successful mutation encoded a **lesson** the organ learned during the run:
- The implementor learned: "click the video player center to start playback"
- The architect learned: "use subprocess to launch Chrome with full URL, then verify title"
- The comms_operator learned: "when stuck in a routing loop, emit diagnostic state instead"

These lessons persist on disk. On next run, the plugins load immediately — the organism **remembers** across deaths.

---

## Pressure Fields: Pain Drives Growth <a name="pressure"></a>

### The Biological Analogy

When you touch a hot stove, you don't *decide* to pull your hand away. Pain forces the response. The pressure field system works identically:

```
No fission for 30 cycles → stagnation = 0.10 → "try something different"
No fission for 50 cycles → stagnation = 0.17 → mutator activates
No fission for 90 cycles → stagnation = 0.30 → MoE reassigns resources
No fission for 180 cycles → stagnation = 0.60 → organ may self-evict
```

### Pressure During the Golden Run

```
STAGNATION                                    * = fission (pain reset)
    │
0.6 ┤                                    ╭── architect (stuck in lock contention)
    │                                   ╱
0.5 ┤                                  ╱     comms_operator after denial
    │                                 ╱      ↓
0.4 ┤                                ╱     ╭────
    │                               ╱     ╱
0.3 ┤                              ╱     ╱    implementor (lock contention)
    │                             ╱     ╱     ↓
0.2 ┤                      ╭─────╱     ╱    ╭────
    │    devops (idle)    ╱      architect  ╱
0.1 ┤    ╭───── ╱        ╱               ╱
    │   ╱      ╱    *───╱  ← implementor fission reset
0.0 ┼──╱──────╱────────────────────────────────────────→ time
    0     1m    2m    3m    4m    5m    6m    7m    8m
         ↑          ↑                   ↑
    Chrome    Video opened    Mutations fired
    launched  (fission!)      (pain threshold)
```

**Key insight:** Fission is the ONLY thing that resets pressure. Not "completing a step." Not "producing output." Only **verified novel progress** earns a reset. This forces the organism to produce real value, not just generate activity.

### What Happens Without Pressure

Without the pressure field, the organism would:
- Repeat the same failed strategy forever
- Never trigger mutations
- Never self-evict useless organs
- Never escalate to the MoE gate for reassignment

Pressure is not a debugging mechanism. It is **the metabolic engine** of the organism. Without it, the organism is braindead — technically alive but incapable of adaptation.

---

## Breeding: The Fittest Survive <a name="breeding"></a>

### The Archive After One Lifetime

```
┌──────────────────────────────────────────────────────────┐
│  MAP-ELITES BREEDING ARCHIVE                             │
│                                                          │
│  Niche: general_task at low pressure                     │
│  ┌────────────────────────────────────────────────────┐  │
│  │ ████████████████████████████████████████████ 0.94  │  │
│  │ implementor — "open URL directly + verify title"   │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  Niche: plugin_patch at low pressure                     │
│  ┌───────────────────────────────────┐                   │
│  │ ████████████████████████░░░ 0.51  │                   │
│  │ implementor — "patch beacon"      │                   │
│  └───────────────────────────────────┘                   │
│                                                          │
│  Niche: plugin_patch at mid pressure                     │
│  ┌──────────────────────────────────┐                    │
│  │ ███████████████████████░░░ 0.48  │                    │
│  │ architect — "launch+verify"      │                    │
│  └──────────────────────────────────┘                    │
│                                                          │
│  Future niches (empty — waiting for more life):          │
│  □ general_task:mid  □ general_task:high                 │
│  □ plugin_patch:high □ navigation:low                    │
│  □ verification:low  □ coordination:low                  │
└──────────────────────────────────────────────────────────┘
```

### How Breeding Works Across Generations

```
Generation 1 (this run):
  implementor achieves 0.94 → archived as elite for general_task:low
  
Generation 2 (next run):
  slot 3 dies under pressure → reactor checks archive
  archive[general_task:low] = implementor, fitness=0.94
  0.94 > BREED_RETAIN_MIN (0.60) → respawn as implementor
  
  The organism regrew its strongest organ.
  
Generation N (future):
  Multiple niches populated → organism adapts its composition
  to match the type of work it's being given.
  GUI-heavy goals → more implementors
  Code-heavy goals → more architects
  Audit-heavy goals → more reviewers
```

### The Key Difference from Traditional Evolution

In genetic algorithms, you evolve **parameters**. In endgame-ai, you evolve **identity**. The "solution" in each niche isn't a weight vector — it's which personality prompt produced the best outcomes for that type of challenge.

Future work: evolve the prompt TEXT itself. The archive would store winning prompt variations, not just persona names. Natural language evolution.

---

## The Colony Mind: Emergent Intelligence <a name="colony-mind"></a>

### No Worker Is Intelligent Alone

Each nemotron instance is a 4B parameter model. It can barely write correct JSON half the time. It hallucinates. It gets confused by multi-step plans. It fails ~30% of LLM calls due to lock contention.

Yet together, the colony:
- Decomposed a goal into expertise-matched subtasks
- Opened Chrome
- Navigated to YouTube
- Found the correct video
- Verified it was playing
- Reflected on failures
- Generated behavioral rules
- Mutated its own code
- Populated a breeding archive
- Responded to mid-run human goals
- Diagnosed a self-referential paradox
- Self-evicted a useless organ

**No single worker did all of this.** The intelligence emerged from the colony's interactions — signals on the bus, pressure responses, fission incentives, MoE routing.

### Stigmergic Coordination

The workers don't "talk to each other" in the traditional sense. They:
1. Act on the shared environment (desktop + bus)
2. Observe changes to the shared environment
3. Respond to what they perceive

This is how ant colonies build complex structures without any ant understanding the blueprint. Each ant responds to local pheromone signals. Each worker responds to local bus signals and desktop state.

The comms_operator is the closest thing to a "coordinator" — but even it doesn't control workers. It posts route messages. Workers can ignore them. The organism's coherence emerges from incentives (fission credit) not commands.

### Claim Awareness

Each worker sees what others are working on:
```
OTHERS WORKING ON (do not duplicate):
  @implementor: Open Google Chrome browser application
  @architect: Navigate Chrome to youtube.com
  @reviewer: Verify that the Shakira She Wolf video is playing
```

This prevents duplication — but not through enforcement. Workers **choose** not to duplicate because the planner prompt tells them it's wasteful. The organism self-organizes through information, not authority.

---

## Human Symbiosis <a name="human-symbiosis"></a>

The human is not the operator. The human is not the user. The human is a **symbiont**.

```
Human provides:
  - Goals (stimuli)
  - Corrections (pain signals)
  - New goals mid-run (changing environment)
  
Organism provides:
  - Desktop automation
  - Persistent attention
  - Self-improvement over time
  - Adaptation to changing requirements
```

During the golden run, the human sent 4 messages. Each was processed as a signal — no different from any other environmental input. The organism didn't "pause for instructions." It received the signal, routed it through its nervous system, and adapted.

The goal is eventual autonomy: the human provides increasingly abstract goals ("keep my desktop organized", "monitor my email and summarize daily") and the organism develops the strategies to accomplish them — without step-by-step guidance.

---

## Milestone 4 vs Milestone 5: From Dead Agent to Living Organism <a name="delta"></a>

### Milestone 4 (main branch, commit a439a0d)

The system was a **broken agent**:
- All workers received every goal simultaneously (broadcast chaos)
- No routing — 5 workers competed for the same work
- Fission always denied — the heart never beat
- No breeding — the reproductive system was inert
- No claim awareness — organs worked blind to each other
- Mutator produced broken patches — the immune system was autoimmune
- Workers exited when goals were "done" — the system died between tasks

**LOC:** 6,175 across 18 files. Bloated. Confused. Dead code everywhere.

### Milestone 5 (unify-rewrite branch, commit 6b70feb)

The system is a **living organism**:
- Human goals route exclusively through the thalamus (comms_operator)
- MoE gate routes subtasks to specialized organs
- Fission flows — the heart beats (4 fissions in 10 minutes)
- Breeding active — the reproductive system archives fitness
- Claim awareness — organs see each other's work
- Mutator produces trial-validated patches — healthy immune response
- Workers NEVER EXIT — they enter maintenance/watch mode after goals

**LOC:** 4,432 across 13 files (-28%). Leaner. Focused. Every file serves the organism.

### The Paradigm Shift

| Aspect | Milestone 4 (Agent) | Milestone 5 (Organism) |
|--------|---------------------|------------------------|
| After task completion | EXIT | Continue living |
| On failure | Retry same strategy | Pressure → reflect → mutate |
| On sustained failure | Crash or infinite loop | Self-evict, escalate, breed replacement |
| Between goals | Dead | Watching, maintaining, evolving |
| Code modification | Never | Self-mutation under pressure |
| Worker composition | Fixed 5 personas | Evolving via MAP-Elites |
| Coordination | Broadcast chaos | MoE exclusive routing |
| Learning | None between runs | Breeding archive persists |

---

## For the Next AI Reading This <a name="handover"></a>

You are about to work on a **living organism**, not an agent framework.

### Critical Mental Model

**DO NOT** think in terms of:
- "How do I make this agent complete tasks faster?"
- "How do I add a termination condition?"
- "How do I reduce unnecessary LLM calls when the goal is done?"

**DO** think in terms of:
- "How do I make this organism healthier?"
- "How do I increase fission rate (metabolism)?"
- "How do I make the pressure field drive better adaptations?"
- "How do I make the breeding archive richer and more diverse?"
- "How do I make mutations more targeted and effective?"

### The Rules

1. **Never add exit conditions.** The organism lives until externally killed.
2. **Never disable pressure.** Pain is the engine of growth.
3. **Never bypass fission.** Credit must be earned through verification.
4. **Never broadcast.** Route exclusively through MoE gates.
5. **Never create new .py files.** Merge inward, delete outward. The organism grows leaner, not fatter.
6. **LOC must decrease.** A healthier organism has fewer cells, not more.
7. **Prompts are DNA.** Edit them with the same care as code.
8. **Test by running.** The organism reveals its nature only when alive.

### What Needs Work

1. **Lock contention** — The blood supply (LLM inference) is clogged. ~30% of calls fail. Fix: replace `fcntl.flock` with Windows-native locking or remove file locks entirely (LM Studio handles concurrency).

2. **Observer should actively focus windows** — The visual cortex (observer) passively reads whatever is focused. It should actively bring Chrome to foreground before reading.

3. **Prompt evolution** — MAP-Elites currently stores only persona names. Should store prompt TEXT as the evolvable solution. Natural language DNA.

4. **Merge files toward 2,000 LOC** — `acp_client.py` into `llm.py`, `observer.py` + `win32.py` into `desktop.py`.

5. **Colony-wide "goal satisfied" state** — Not "exit" but "satisfied." When N organs independently verify the goal is met, the organism should enter a relaxed maintenance state (lower cycle frequency, lower LLM usage) until the environment changes or a new goal arrives.

### Current State

```
HEAD:     6b70feb (unify-rewrite branch)
LOC:      4,432 Python (target: <2,000)
Files:    13 .py + 2 plugins + 8 prompts + README + HTML + OBSERVATIONS
Breeding: 3 niches populated (general:0.94, patch:0.51, patch:0.48)
Status:   ALIVE. Ready for next goal.
```

### To Birth the Organism

```powershell
cd C:\Users\ewojgab\Downloads\endgame-ai
python -c "import log; log.cleanup_runtime(deep=True)"
python tui.py --model-profile nemotron_parallel "your goal here"
```

---

## How to Birth the Organism <a name="run"></a>

### Prerequisites
- Windows 10/11
- Python 3.11+
- LM Studio running nemotron with Max Concurrent ≥ 5
- Google Chrome (for web tasks)

### Commands

```powershell
cd C:\Users\ewojgab\Downloads\endgame-ai

# Clean runtime state (fresh birth)
python -c "import log; log.cleanup_runtime(deep=True)"

# Parallel mode — full organism (5 organs, 5 concurrent LLM calls)
python tui.py --model-profile nemotron_parallel "Open Chrome and play Shakira She Wolf on YouTube"

# Sequential mode — single-threaded metabolism (slower but no lock issues)
python tui.py --model-profile nemotron "your goal here"

# ACP mode — Kiro CLI as blood supply (single organ only)
python tui.py --backend acp "your goal here"
```

### Environment

```
LM_STUDIO_URL=http://192.168.16.31:1234   # Blood supply endpoint
ENDGAME_PERSONALITY=comms_operator          # Organ identity
ENDGAME_SLOT=1                              # Slot number (1-5)
```

---

## Papers <a name="papers"></a>

1. **Mixture of Experts** — Bause (2026). "Scalable Expert Routing with Confidence-Weighted Softmax Gates." arxiv.org/abs/2605.25929. *The nervous system.*

2. **Pressure Fields** — Rodriguez (2026). "Environmental Pressure as Adaptive Signal in Multi-Agent Systems." arxiv.org/abs/2601.08129. *The endocrine system.*

3. **MAP-Elites** — Mouret & Clune (2015). "Illuminating search spaces by mapping elites." arxiv.org/abs/1504.04909. *The reproductive system.*

4. **ReAct** — Yao et al. (2022). "ReAct: Synergizing Reasoning and Acting in Language Models." arxiv.org/abs/2210.03629. *The cognitive loop.*

---

## File Map

```
main.py          69   entry point per organ (env: ENDGAME_PERSONALITY, ENDGAME_SLOT)
engine.py       320   metabolic loop: interrupt → plugins → pressure → MoE → pipeline
agents.py       690   cognitive pipeline + validate_python + claim awareness
reactor.py      237   reproductive system: spawn/breed/respawn
tui.py          320   terminal UI: full-width organism monitor
comms.py        721   nervous system: blackboard bus + softmax routing
llm.py          250   blood supply: LM Studio HTTP + lock
log.py          123   memory: JSONL event logging
config.py       250   genome: constants, personas, profiles, thresholds
actions.py      362   motor system: exec sandbox + GUI verbs
observer.py     401   visual cortex: Windows UIA screen reading
win32.py        366   sensory apparatus: ctypes UIA bindings
acp_client.py   252   alternative blood supply: Kiro CLI backend
plugins/         40   mutable DNA: hot-reloaded behavioral patches
prompts/        ~20   personality DNA: system prompts defining organ identity
```

---

*This document is itself alive. It will be rewritten after each milestone.*
*The organism does not version its README. It rewrites it, because it is always becoming.*

---

**License:** MIT. See LICENSE file.
**Repository:** github.com/wgabrys88/endgame-ai
**Branch:** unify-rewrite
