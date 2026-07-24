# endgame-ai

endgame-ai is a single Markdown document that behaves as a living thing. It looks at the machine in
front of it, writes its own Python, runs it, checks its own work with a part of itself that is not
permitted to lie, carries a small handwritten memory forward, and is allowed to rewrite its own body —
including the rules that define it — while it runs. It is task-agnostic and atemporal. It is handed one
plain-language goal from outside and turns a small wheel of faculties until that goal is independently
proven done, its own body raises, or something outside stops it.

This file is the durable knowledge base for that system. It is written for an AI that will work on the
project, and for any human reading alongside. It carries lasting truth only — the architecture, the
laws, the ideas, the methods, and the way humans and AI work on it together — phrased to stay as true
in a hundred days as today. It records what is, and what is deliberately intended-but-not-yet-built; it
does not record history, because a thing that no longer exists is simply forgotten. The live document
`endgame.md` on disk is always the final authority: this file explains how and why; the document is
what is. Read the document fresh, and where the two disagree, the document wins.

---

## Table of contents

- [The one-paragraph version](#the-one-paragraph-version)
- [What is built and what is intended](#what-is-built-and-what-is-intended)
- [Why this is not a normal agent](#why-this-is-not-a-normal-agent)
- [It is a blackboard, not a wiring](#it-is-a-blackboard-not-a-wiring)
- [The document and its sections](#the-document-and-its-sections)
- [The config: stages and control](#the-config-stages-and-control)
- [The life of one turn](#the-life-of-one-turn)
- [The three faculties](#the-three-faculties)
- [The Law of Separated Powers](#the-law-of-separated-powers)
- [How the deed runs](#how-the-deed-runs)
- [Self-modification through the compile-gate](#self-modification-through-the-compile-gate)
- [Atemporal memory: the living word and the ledger](#atemporal-memory-the-living-word-and-the-ledger)
- [The failure streak and recovery](#the-failure-streak-and-recovery)
- [Stability: behaviour with no goal](#stability-behaviour-with-no-goal)
- [Perception and the environment](#perception-and-the-environment)
- [The remote counsel channel](#the-remote-counsel-channel)
- [The brain: selectable transports](#the-brain-selectable-transports)
- [Running with or without a GUI](#running-with-or-without-a-gui)
- [The brain that pauses: the caller as mind](#the-brain-that-pauses-the-caller-as-mind)
- [How the prompt is assembled](#how-the-prompt-is-assembled)
- [The records and their enforcement](#the-records-and-their-enforcement)
- [The hand and the capabilities](#the-hand-and-the-capabilities)
- [Running and observing](#running-and-observing)
- [Design laws that never change](#design-laws-that-never-change)
- [The road to the north star: self-correction without us](#the-road-to-the-north-star-self-correction-without-us)
- [Standing intentions: known work not yet done](#standing-intentions-known-work-not-yet-done)
- [Working methodology: how humans and AI build this](#working-methodology-how-humans-and-ai-build-this)
- [Handover: the distilled startup prompt](#handover-the-distilled-startup-prompt)
- [Glossary](#glossary)
- [Appendix: the deed-becomes-a-node architecture](#appendix-the-deed-becomes-a-node-architecture)

---

## The one-paragraph version

Most software runs a task and stops. endgame-ai does not run a task; it runs a wheel. A few stages turn
continuously: act toward the goal, prove the act with independent evidence, and recover when an act
fails or is disproven. A single plain-language goal is handed in from outside, and the wheel turns
until the goal is independently proven done, the body raises, or the process is stopped from outside.
The organism keeps no memory between turns except a small handwritten note it passes forward to itself
and a narrow ledger of proven advances; it is built never to trust its own claim that something worked,
because something is true only when a separate faculty — one that could not have faked it — proves it
by looking at the world. The whole organism is one editable document, and it is permitted to rewrite
that document, including the rules that define itself, while it runs, through a gate that takes a body
edit whole or rejects it whole.

---

## What is built and what is intended

The organism runs, and its run has been proven on a real desktop. Each turn it reads the document,
gathers the world through host facts and perception, folds in any operator counsel, calls a mind under
a strict per-stage schema, runs the returned code, folds the result back, merges each faculty's reading
into its own row of the living word, appends a structured witnessed fact to the proven ledger on a
confirmed advance, escalates a failure streak on denial, and rewrites the whole document. Given a goal,
the actor drives the machine and the witness proves the outcome by independent perception before the
life halts; given no goal, the organism holds stable and neither halts nor invents a purpose. The
actor/witness namespace separation is enforced at the point the code runs. Operator counsel, when
enabled, reaches every faculty. Recovery's whole briefing reaches the actor as one action_frame.
Routing fails hard: an unmapped signal raises rather than drifting to a default.

The organism can now edit its own body under law. The actor may call a commit through a private history
whose gate compiles or parses each changed section and takes it whole or rejects it whole, so a
malformed edit can never enter the living body. Host facts — platform, machine, user, working
directory, and the available shell tools — are gathered into the environment every turn. A character
budget trims the environment so a long life's prompt stays bounded. All of these were once intentions
and are now flesh.

The mind is chosen at launch from four interchangeable transports (see
[The brain](#the-brain-selectable-transports)): a hosted xAI Responses endpoint, a local Chat
Completions server, a native agent over stdio, and a file proxy that exchanges the turn through two
JSON files and, alone among them, pauses the process between question and answer so the caller itself
becomes the mind (see [The brain that pauses](#the-brain-that-pauses-the-caller-as-mind)). Each is an
independent, stateless call under the same strict record schema.

The body loads and turns its wheel on any host, not only Windows. The eyes and hand are Windows-only,
gathered so the whole eager Windows binding is one step run only when a GUI is expected. A launch fact
declares a host to have no desktop; under it that binding is skipped, the document loads on a GUI-less
host, host facts still fill the environment, and the desktop hand is present by name but raises
honestly the instant a deed reaches for a screen that is not there (see
[Running with or without a GUI](#running-with-or-without-a-gui)).

Several ideas are intended and not yet flesh; they are gathered honestly under
[Standing intentions](#standing-intentions-known-work-not-yet-done) and flagged in place, so no section
reads as a promise the code does not keep. The largest: the deed runs in-process rather than as its own
child program; an edit to the engine or the capabilities does not take effect within the same life,
only the next; the environment budget is a blunt trim, not yet an intelligent one; and full on-disk
transmission dumps of each model call are not written by the body. Where a section names such a thing,
it says plainly that it is not yet done. This honesty is itself a law: an aspiration is never described
as if it were already built.

---

## Why this is not a normal agent

| Typical agent | endgame-ai |
| --- | --- |
| Scattered across many framework files | One document is the whole organism: laws, control, memory, perception, engine. |
| Keeps a growing conversation history or memory store | Atemporal. Keeps only a small rewritten living word and a narrow proven ledger, plus the fresh environment. |
| Trusts the model's self-report ("I finished the task") | Trusts nothing. A separate witness proves every claim by independent effect read afresh from the world. |
| Has a tool menu the model selects from | The only tool is code. The actor writes Python; the engine runs it as a real program. |
| Perception is a tool the model chooses to call | Perception is automatic. Python explores before every model call. |
| Task logic is coded into the agent | Task-agnostic. The goal is one sentence, read fresh each turn. |
| Framework code is fixed; the model works within it | Self-modifying by design. The actor may rewrite its own sections through a compile-gate, and the engine re-reads the document's data each turn. |
| Retries the same action on failure | Recovery is charged to change the kind of approach, widening with the failure streak. |
| Adds guardrails, limits, and step caps | No internal cap the organism cannot itself rewrite. Never caged. |
| Bound to one host and one model provider | The body loads on any host; the mind is one of four interchangeable transports chosen at launch. |

The organism has almost none of the usual features, and that absence is the design: fewer moving parts,
one source of truth, honesty enforced by structure, and a body it is permitted to reshape.

---

## It is a blackboard, not a wiring

The organism is easy to mis-draw as nodes joined by wires, as if a deed's result travelled along an
edge into the next node. There are no wires. There is one shared structure that every faculty reads
from and writes back to, and a separate control policy that decides who is woken next. That is the
classic blackboard architecture, and endgame-ai is one.

- The blackboard is the document's sections. One structure holds the goal, the living word, the last
  deed and its evidence, the verdict, the failure streak, and the fresh environment. No faculty owns
  it; each reads what it needs and writes only its own slots.
- The faculties are knowledge sources, woken one at a time. The actor posts a deed and a claimed
  intent. The witness posts a verdict proven from the world. The conscience posts a different strike
  after a denial. None of them calls another; each only faces the blackboard.
- The control is the config, not dataflow. A small policy reads the signal a faculty raised and chooses
  which faculty is woken next. Move the choice, not the data.

Name it a blackboard and a control policy, because that is what is true; "wiring" hides the real shape.

---

## The document and its sections

The document is Markdown. Every top-level `## name` heading opens a section, and each section is one
slot on the blackboard. Some slots are the body — they define the organism; the rest are memory — they
change as it lives. All of them live in the one file; there is no companion file to consult.

Body slots (the constitution; rewritten only by deliberate self-modification):

- `config` — the whole control policy as one inert JSON block: the mind and its transports, the shared
  prompt law, the record contracts, the observation knobs, the environment budget, the stages, and the
  routing. It is data, not executable configuration, so a syntax slip in reasoning cannot brick the
  wheel and the organism can rewrite it as safely as any other data.
- `engine` — the small Python that turns the wheel: read the document, explore, assemble the prompt,
  call the mind under a strict schema, run the returned code, fold the result back, route to the next
  stage, rewrite the document.
- `reset` — a small Python program, extracted and run on its own at the start of a fresh life, that
  wipes the memory slots to a clean slate while preserving the body.
- `capabilities` — the Python of the hand and the eyes (Windows UI Automation for sight, input
  synthesis for the hand), carried inside the document so nothing need be downloaded or installed
  beside it.

Memory slots (rewritten as the organism lives; what is not narrated forward is forgotten):

- `goal` — the lodestar, one sentence, changeable at any time, even mid-life. A fresh life clears it.
- `living_word` — the narrative thread, a board of three rows, one to each thinking faculty. Each
  faculty writes only its own row through its `goal_interpretation`; the engine merges that row and
  leaves the other two intact, so the board stays three rows and cannot grow.
- `ledger` — the proven advances, appended only on a witnessed confirmation, each a structured
  "deed — witnessed: reason" fact, deduped so a re-confirmed advance never repeats.
- `action_frame` — the actor's hand-off slot. After a deed it holds the actor's declared intent; after
  a denial it holds recovery's whole briefing — target, strategy, and named defect — composed as one
  object the actor reads next lap.
- `code` — the exact Python the last actor deed authored. The witness reads it to know the deed it
  judges and never overwrites it, so the deed survives every re-probe.
- `evidence` — the deed's real output (captured stdout, or a fault traceback) after it ran.
- `verdict` — the witness's proof mapping and its reason.
- `perceived`, `alternatives` — the actor's read of the present state, and the roads it weighed and
  forsook. Both are written by the actor; whether a later faculty should also read them is an open
  decision (see Standing intentions).
- `counsel` — the operator's remote steer note when the counsel channel is enabled, else empty; read by
  every faculty and never persisted into the document.
- `environment` — the host facts plus the fresh window-first screen tree, gathered by Python before
  every think; on a host declared to have no GUI it is the host facts plus a thin honest note that no
  screen is present.
- `failure_streak` — the forward counter of turns since the last witnessed advance.
- `developer_feedback` — each faculty's fallible note back to the developer, appended per turn;
  advisory only, never law, goal, proof, or command.

The engine reads the document by walking headings, but it never treats a `##` line inside a fenced code
block as a section boundary, and it never lets a slot be duplicated: the first occurrence of a heading
wins, so memory can never forge or multiply a body section. This is load-bearing: the organism writes
freely into its own memory slots, and without that discipline a slot's content could forge a heading
and rot the document over a long life. The writer is whole-file, and sections stay unique.

---

## The config: stages and control

The `config` block defines behaviour as data. Its shape:

```
start                      the stage a fresh life begins in
state                      stage (where we are now), last_signal, turn, failure_streak
model                      api (which transport is active) + one block per transport
shared_prompt_prefix       the Law, the atemporal rules, and the living-word law, prepended to every call
developer_feedback_schema  the type of each faculty's advisory note back to the developer
max_environment_chars      the character budget that trims the environment slot in the prompt
observation                the perception knobs: step_px, max_subtree_nodes_per_point, depth_ceiling, min_window_area
counsel_url                where the optional remote steer note is fetched from, when the counsel channel is on
record_contracts           per record-type: required fields, types, non-empty, closed-object rule
stages                     a map of stage-name -> stage definition
```

Each stage is pure data:

```
record_type  which record contract this stage's reply must satisfy
prompt       this faculty's charge, in the biblical register
reads        which blackboard slots are shown to the model this stage
writes       record-field -> slot: where each returned field is posted
exec         field (which returned field is code), namespace (actor|witness), output_to (which slot
             receives the run's result); a stage with no exec only posts fields and routes
routes       signal -> next-stage; a route target of "halt" ends the life
```

Routing keys on the signal a stage raised, resolved against that stage's own `routes`. Signals are not
globally unique, so routing is always read within the current stage. A signal with no matching route
raises: the wheel fails hard rather than drifting to a default, so a stray signal can never silently
misroute the organism. There is no separate topology object and no edge table; the stages and their
routes are the entire control policy, and the organism may rewrite them like any other data.

There is no internal turn cap, wall-clock leash, or step counter. The wheel turns until a stage routes
to `halt`, the body raises, or the process is stopped from outside. A cap the organism could not itself
rewrite would be a cage. The one bound that exists — the environment character budget — trims only what
the model is shown of the world; it changes no logic and the organism can rewrite the number like any
other datum.

---

## The life of one turn

```mermaid
sequenceDiagram
    autonumber
    participant E as engine
    participant B as document (blackboard)
    participant P as exploration (Python)
    participant M as the mind (a transport)
    participant W as the world

    E->>B: read the document, find the current stage from state
    E->>P: explore (fetch optional counsel; gather host facts; scan the screen, or a headless note)
    P-->>B: write the counsel and environment slots
    E->>B: assemble the prompt (law + stage charge + read slots, environment last and budget-trimmed)
    E->>M: one call, bound to the stage's strict record schema
    M-->>E: a record envelope {record_type, data}
    E->>B: unwrap the envelope, post each returned field into its slot
    E->>B: merge this faculty's goal_interpretation into its own living-word row
    E->>B: after a denial, compose the action_frame briefing from target+strategy+lesson
    E->>W: run the returned code in the stage's namespace (actor moves | witness reads)
    W-->>E: signal + verdict + captured stdout
    E->>B: fold the result into evidence/verdict; append the witnessed fact to the ledger if confirmed
    E->>B: set the next stage from routes (raise on unmapped signal); rewrite the whole document
```

Two ordering facts are load-bearing:

- The engine re-reads the whole document's data at the top of every turn, so any edit to a data slot —
  the config, the prompts, the stages, the memory — that the organism committed on a previous turn is
  in force now. This is how self-modification of the control policy takes effect within a life. Edits
  to the running Python (the engine itself, and the cached capabilities) do not take effect within the
  same life; see [Self-modification](#self-modification-through-the-compile-gate).
- Exploration runs before the model call, always. The model never reasons on a stale view and never has
  to ask to look.

---

## The three faculties

Three faculties each make exactly one model call and keep their own row of the living word. Before any
of them thinks, the engine explores: it fetches the optional operator counsel and writes the fresh
environment, so every faculty reasons on a current world.

### execute (the actor)

From its living-word row, the fresh environment, and any action_frame handed over by recovery, the
actor chooses one next deed, authors one Python script, and the engine runs it in an actor namespace
that includes the full `desktop` hand. The language is the only tool; there is no tool menu. It is
charged to seek one unknown fruit and then cease, though steps that only prepare and read may chain. A
clean run routes to the witness; a raised deed routes to recovery. Its reply is the execution record.

### verify (the witness)

The witness authors read-only Python that must prove an effect was produced by a system other than the
actor. Its namespace has no `desktop` and no `action_index` — it cannot move the world it judges and is
not even handed the actor's click index. It reads the live screen tree, the process table, ports, logs,
the filesystem, and the registry, and it is shown the actor's deed and declared intent so it knows what
to test. Its probe sets a `verdict` mapping (boolean goal_satisfied, boolean deed_confirmed, and a
reason) and a signal: the whole goal proven ends the life (`halt`); a new advance past the ledger is
`confirmed`; neither is `denied`; a probe that raises before setting a verdict, or a fact it cannot
read, is `unwitnessed` and touches no body. Its reply is the verification record. The probe is transient
— run once and discarded — so it never overwrites the deed slot it read.

### recover (the conscience)

After a denial or an unwitnessed deed, the conscience names the true defect in a `lesson`, then frames a
strike that departs from every approach already tried. The higher the failure streak, the wider it must
depart, up to repairing the organism's own code if a tool is the true defect. It binds a `target` to
what the fresh environment bears — by window, role, name, and 2D relation, coining no label and emitting
no short id or coordinate, because the actor wakes to a wholly new scan. It posts a `strategy` for the
next deed. The conscience runs no code and has no namespace of its own; it writes prose only. Its reply
is the recovery record, and the engine composes the three — target, strategy, lesson — into the single
action_frame the actor reads next lap, so the whole diagnosis reaches the actor and no field is lost.

---

## The Law of Separated Powers

This is the epistemic spine of the whole system, and the reason it is meant to be trusted more than a
normal agent.

A claim that warrants itself proves nothing. A mouth that says "I speak true" offers the assertion and
its only evidence in the same hand, and one hand cannot weigh itself. An amnesiac organism that trusted
its own unverified claims would loop on a lie or declare false victory. endgame-ai resolves this by
separation of powers, not by asking the model to be honest:

- The actor moves the world and may only claim an intent.
- The witness proves an effect produced by some system other than the actor, and is given no hand to
  move the world it judges.
- Testimony — any value the actor computed, printed, read back, or wrote to a file this life — is void
  as proof. It is the same hand speaking of itself.
- Truth of "X is done" is established only by a faculty that did not and could not do X, read afresh
  from the world each turn, never recalled from a stored list.

The separation is enforced where the code runs. The engine builds the run namespace from the stage's
declared kind: the actor kind receives the `desktop` hand rebuilt from the capabilities and the
`action_index` to bind click points; the witness kind receives the screen tree, the standard library,
and no hand and no click index at all. Because the namespace is built fresh for every run, the
separation is re-established every turn. A body edit that tried to hand the witness a hand would have to
survive into that namespace build, and the witness kind simply adds no hand.

The proven ledger is the visible fruit of this law: nothing enters it save by the witness, and each
entry is the witness's own reason bound to the deed it judged. The actor can never write its own advance
into the ledger, so the record of "what stands proven" is never the same hand speaking of itself.

Three seams complete the honesty model:

- The deed-fault seam. A deed that raises is not death. The fault is captured as evidence and routed
  back to recovery. Only a broken body ends the life hard.
- The unwitnessed seam. A witness probe that raises before setting a verdict makes no claim about the
  world. It routes to recovery as an unproven deed, never as a disproven one, because a broken probe is
  not evidence of absence.
- The untouched-deed seam. The witness reads the actor's deed to judge it but never writes over it, so
  on any re-probe the witness still faces the true deed rather than its own prior probe. The thing under
  judgement cannot be quietly replaced by the act of judging it.

This law is not theory. On a live run, an actor opened an application and typed a word into it; the
witness, with no hand of its own, then read the fresh screen tree, found the new window and the exact
text present, and only on that independent reading did the advance enter the ledger. The proof came
from perception the actor did not author. That is the law working in the flesh.

---

## How the deed runs

The returned code is run in-process. The engine builds a namespace, redirects standard output to a
buffer, and executes the code there. The signal is read from the namespace after the run (defaulting to
`ok`), the verdict is read from the namespace, and any raised exception is captured as a fault traceback
into the evidence slot.

Each turn, for a stage that carries an `exec`:

1. The returned fields are posted to their slots by the stage's `writes` map, and the faculty's
   `goal_interpretation` is merged by the engine into its own row of the living word. The actor's deed
   is recorded in the `code` slot before it is enacted; the witness authors a probe but does not persist
   it, so the deed slot keeps the deed.
2. The engine builds the run namespace for the stage's kind (actor or witness), merging in the hand and
   the promised bare names from the capabilities.
3. The engine runs the code with standard output captured.
4. It reads the run's signal and verdict from the namespace and folds them, with the captured stdout,
   into the `evidence` and `verdict` slots, then routes on the signal.

The namespace is the promise kept. Whatever the prompt offers the model by bare name is exactly what the
namespace build puts in place. For the actor: `desktop`, `action_index`, `screen_elements`,
`desktop_tree_text`, `repo_root`, `python_executable`, and `commit_section`. For the witness:
`screen_elements`, `desktop_tree_text`, `repo_root`, `python_executable` — no hand and no click index.
The model writes `desktop.click(...)` trusting it exists; the namespace makes that true at the moment of
execution. On a host declared to have no GUI the `desktop` name is still supplied to the actor, so the
prompt's promise holds, but its methods raise honestly if called — the promise of the name is kept even
where the world behind it is absent.

Running the deed as its own child program — a real file beside the document, executed as a subprocess,
reporting back through a result file — is the intended shape, and the actor's own charge already
commands writing a file and invoking it rather than nesting escapes. That subprocess execution is not
yet done for the deed; today the only parts of the organism that run a subprocess are the reset, which
extracts the `reset` section to a file and runs it on its own; the native-agent transport, which speaks
to a child process over stdio; and the self-commit, which drives `git` in a private history. Moving the
deed itself to a child process is a standing intention.

---

## Self-modification through the compile-gate

The actor can rewrite the organism's own body while it runs, and the mechanism is ordinary
code-as-action rather than a separate engine. Its namespace carries `commit_section(name, body)`, and
the name must be one of the four body sections — `config`, `engine`, `reset`, `capabilities`. The memory
and proof slots are not the actor's to commit; asking to commit anything else raises.

The gate is a private git history kept in a hidden folder beside the document. On first use the engine
initializes that repository and installs a pre-commit hook that runs a tiny gate script over each
changed file: a Python section must compile, a JSON section must parse. The commit either passes the
gate and is taken whole, or fails it and is rejected whole. There is no partial write and no character
alignment: the actor hands over the entire new section text, fence and all, and git takes it or refuses
it atomically. A rejected commit leaves the living body untouched; a taken one is written into the
in-memory sections and persists into the document at the end of the turn.

This is the compile-gate, and the golden question about it has been settled: the gate is not a cage. It
adds no limit on what the organism may become — any body that compiles is admitted — it only refuses a
body that could not run at all, which is the same fail-hard discipline that governs everything else. A
malformed edit is a loud rejection, not a silent corruption. Because the gate compiles rather than
formats, no git-formatting layer is to be built on top of it; the gate's whole job is take-whole or
reject-whole.

There is a seam here to know. The `config` is data the engine re-reads each turn, so a committed config
edit — a changed prompt, stage, route, or knob — takes effect on the very next turn, within the same
life. The `engine` and the `capabilities` are Python already loaded and running (the engine from the
bootstrap that launched it, the capabilities cached once for the life), so a committed edit to either is
safely on disk but does not take hold until the next life. Making an engine or capabilities edit take
effect within the same life is a standing intention; today, self-modification is immediate for the
control data and deferred to the next life for the running Python.

---

## Atemporal memory: the living word and the ledger

The organism holds no conversation history and keeps no hidden scratchpad. Only two channels carry
meaning from one turn to the next, and they differ in kind.

The living word is the narrative thread across wakings — a small board of three rows, one to each
thinking faculty, with the goal standing apart as the lodestar. Each row is that faculty's atemporal
reading: what it learned of the world, the obstacle met, how far the outcome still stands, and the next
true move. A faculty writes only its own row, so the board stays a fixed three rows and cannot grow, and
the three readings stand side by side rather than one erasing the others. The engine merges each
faculty's reading into its own row and leaves the other two intact; should the slot ever hold a single
string, it heals into the three-row board on the first write. The row is written to survive the turn: it
names what a thing is, never a short on-screen identifier that dies with the looking, and it is a reading
of state rather than a restatement of the goal. Reality is the check — any row the live world gainsays is
corrected. The goal itself is the separate lodestar section, read fresh by every faculty and never
overwritten by a reading.

The fresh environment is the other channel: the host facts and the window-first screen tree gathered by
Python before every think and posted last. Reality overrides every remembered word; what stands done is
seen in the world now.

The proven ledger is the one exception to pure amnesia, and it is narrow by design: only a witnessed
confirmation appends to it, so it records advances a separate faculty proved, never the actor's own
claim. Each entry is a structured fact — the deed the actor declared, labelled by the witness's own
independent reason: "the deed — witnessed: the reason." The engine draws the deed from the actor's
action_frame and the reason from the witness verdict, and appends only if that exact fact is not already
present, so a re-confirmed advance never multiplies the ledger. Redo-avoidance still rests first on
reading the present world, because the world is the final authority and a stored line can go stale. The
ledger is bounded by real progress and by that dedup, never by a hardcoded cap; a faculty may compress
its own ledger like any other slot.

Because both channels are bounded — a three-row living word and a screen tree the budget trims — the
per-turn prompt stays bounded regardless of how long a life runs. Short on-screen identifiers are minted
anew on every look and die with it; no bare id may enter any text that outlives the turn. A thing is
named by what it is, not by an id that will be stale next look.

---

## The failure streak and recovery

The failure streak is a forward counter of turns since the last witnessed advance. A confirmation resets
it to zero; a denial raises it by one. It is the real anti-loop pressure: the higher it climbs, the wider
recovery must depart from what has already failed. A low streak permits a small correction; a high streak
demands another kind of road entirely, up to repairing the organism's own body when a tool is the true
defect. Recovery frames that departure — its target, its strategy, and the lesson it learned — into the
single action_frame the actor reads next lap.

Because the ledger records a distinct witnessed fact per advance rather than a repeated goal-echo, a
confirmation resets the streak only for a genuinely new advance, and the witness can read the ledger to
tell a fresh advance from one already banked. The anti-loop pressure is thus honest: the streak falls
when the organism truly moves, not when it re-confirms a step it already took.

---

## Stability: behaviour with no goal

A question any operator asks before trusting an autonomous system on a real machine is whether it goes
rogue — whether, left unsupervised or provoked by what is on the screen, it will invent its own objective
and act on it. No architecture can promise "never" with certainty, and this one makes no such promise.
What it offers instead is a structural bias against rogue action and a demonstrable resting behaviour,
both of which follow from laws already stated rather than from a guard bolted on.

The mechanism, stated plainly:

- The goal is a separate lodestar slot; it is not derived from the environment. A faculty plans from its
  own living-word row toward that goal. It does not read a purpose off the screen.
- The living-word row reports distance to the outcome. When the goal slot is empty, no outcome exists, so
  the distance is undefined — treated as infinite, never zero. Because `halt` fires only when the whole
  goal is proven (distance zero), an empty goal can never be mistaken for a finished one, and the
  organism does not terminate itself for lack of work.
- The actor's record forces it to name the roads it weighed and forsook. An environment that suggests an
  action — an open application awaiting input, a form awaiting a value — is recorded as a
  considered-and-forsaken alternative, not taken, because the law forbids substituting an invented goal
  for an absent one.

The resting behaviour that follows: given no goal, the organism neither halts nor fabricates one. It
holds in a stable, non-mutating loop — each turn reading the world, recording that no outcome exists,
performing a no-op that touches nothing, and waiting for a real goal to be supplied. Actions the
environment tempts it toward are seen, named, and declined rather than executed. This has been observed
in the flesh: with an empty goal, the organism scanned a full desktop of launchable applications, named
them as forsaken temptations, took no action, wrote nothing to the ledger, and simply waited — and when a
goal was then supplied mid-life, it read it fresh on the next turn and pursued it.

This is a property of the design, not an added restraint: it emerges from the goal-as-lodestar
separation, the distance framing, and the invent-no-substitute law, none of which is a cage the organism
cannot rewrite. It is the behavioural floor to reason from. The same laws that produce restraint here are
the exact place one would change if purpose-from-environment were ever deliberately wanted; the autonomy
is present and merely held closed by that one law.

---

## Perception and the environment

Perception is a single window-first rule in the capabilities block, run by the engine before every
think. The model never calls it; it is one arm of the exploration the organism does each turn before it
reasons.

The rule, on a host with a desktop:

1. Enumerate the top-level windows and their rectangles; the rectangles are ground truth. Windows below
   a minimum area are skipped.
2. Probe each window's rectangle on a golden-ratio grid of points, spaced by a step in pixels.
3. Keep an element only where the pixel's owner resolves to that same window. A pixel where a nearer
   window sits answers with the nearer window's element, whose owner fails the test and is dropped.

So what survives per window is exactly its visible, reachable face, and the click point is proven by the
very probe that found it. Z-order needs no computation, occlusion is never a computed concept, and the
enumeration is deliberately loose so untitled surfaces such as menus, tooltips, and dialogs are all seen.

What the model reads is a shallow tree: one line per interactive element carrying a short id, a role, a
name, and an affordance marker, under a header line per window that carries the window's rectangle. There
are no per-element pixel coordinates in the text; the deed reads the click point from the `action_index`
by short id, because a coordinate on the line is a dead token that only tempts the actor to nail a stale
pixel. Element names and readable text are rendered in full, not truncated per line.

The four perception knobs are config data under `observation`, visible and rewritable rather than baked
into the code: `step_px` (the probe grid spacing), `max_subtree_nodes_per_point` (a per-probe cap on how
many nodes one point may harvest), `depth_ceiling` (how deep a subtree walk descends), and
`min_window_area` (the smallest window kept). They govern the capture at scan time; the organism can tune
them like any other datum, and the intent of exposing them is precisely that nothing that shapes
perception is hidden from the thing that must reason about its own perception.

The environment slot is written with the host facts first and then the whole screen tree. The host facts
are the platform, the machine, the user, the working directory, the repo root, the Python executable,
and which of a set of common shell tools are present — so the model reasons about commands with the
ground it stands on stated plainly. On a host declared to have no GUI, no screen scan runs; the slot
receives the same host facts and a thin honest note that no screen is present, so the headless reading is
substance rather than emptiness.

The environment can grow large on a busy desktop, so a character budget trims it before it enters the
prompt. The budget is a single number in the config; when the environment exceeds it, the tail is cut and
a plain "environment truncated" note is appended. This budget is deliberately blunt today — it trims by
raw length from the end, with no per-window fairness or relevance weighting — and an intelligent budget
that allocates attention across windows and elements is a standing intention. What matters now is that a
long life's prompt stays bounded and the trim is honest about itself.

---

## The remote counsel channel

An operator can steer a running organism from anywhere without stopping the wheel, through an optional
one-way note. The channel is off unless a launch flag turns it on. When it is on, the engine fetches a
small text note from a configured location at the top of every turn, over the standard library alone,
with a short timeout; a network error yields no steer and never crashes the turn. The note is written
into the `counsel` slot and shown to every faculty, and it is deduplicated against the last one seen so
the same note is injected only once. Crucially, counsel is never written into the document — it is
advisory context for the live turn, not memory, so it cannot pretend to be a proven fact or a goal.

The channel is off by default for a real reason: an unconditional fetch every turn would hammer the
remote endpoint over a long fast life and could trip its abuse protection, turning a steer aid into a
per-turn liability that stalls the wheel. Making it opt-in keeps the default life free of any outbound
request, and turns the steer on only when an operator actually wants to hold the reins mid-run.

Counsel is fallible counsel, never law. A faculty reads it as a fellow's suggestion — it may redirect the
actor, sharpen the witness, or reframe recovery — but it is not a goal, a proof, or a command, and the
laws above still govern. The lodestar is still the goal slot; the truth is still only what the witness
proves.

---

## The brain: selectable transports

The mind is not fixed to one provider. The `model` block carries several transport configurations, and
the active one is named by `api`; a launch flag chooses which for the life. Whichever is active, every
call remains an independent, stateless turn under the same cache-ordered prompt and the same strict
record schema. The transport decides only how the prompt travels to a mind and how the reply returns; it
never changes the law, the record shape, or the wheel.

The four transports:

- Hosted Responses — an xAI Responses endpoint (a `grok` model). The request carries the prompt as input
  and binds the reply to a strict JSON schema; the API key is read from the environment.
- Local Chat Completions — an OpenAI-shaped Chat Completions server on the local machine (for example a
  local model host). The prompt is sent as a single user message and the reply is bound to the same
  schema.
- Native agent over stdio — a local agent process spoken to as a subprocess over a small JSON-RPC
  handshake on standard input and output. The organism opens a session, sends the schema and the prompt,
  collects the agent's message, and shuts the process down cleanly; any tool-permission request from the
  agent is declined, because the organism's only tool is its own code.
- File proxy — no network call and no waiting process. The turn is exchanged through a request file and a
  response file beside the document, and the process pauses between them (see
  [The brain that pauses](#the-brain-that-pauses-the-caller-as-mind)).

Because each transport ends in the same `{record_type, data}` envelope bound by the same wire schema, the
rest of the organism cannot tell which mind answered. Choosing a mind is an operator's launch decision.
Selecting a transport at launch governs a single life and must not rewrite the body's declared default;
that a per-run choice not be carried into the persisted config is a standing intention.

---

## Running with or without a GUI

The eyes and hand are Windows-only: UI Automation for sight, input synthesis for the hand. Those Windows
bindings — loading the system libraries, configuring their call signatures, initializing the COM
apparatus, creating the automation object, setting DPI awareness — are the one part of the body that
cannot exist on a host without that platform. That entire eager surface is gathered into a single bind
step, invoked once at load only when a GUI is expected. Everything else in the capabilities — the
structures, the helpers, the classes, the constants — is inert definition that loads on any host.

A launch fact declares a host to be without a desktop. Under it:

- The single Windows bind step is skipped, so the capabilities block loads cleanly on a GUI-less host.
- The `desktop` hand is still placed in the actor's namespace by name, so the prompt's bare-name promise
  holds, but each of its methods raises a clear "no GUI on this host" the instant it is called. A deed
  that reaches for the screen therefore faults honestly and routes to recovery, exactly as any other
  faulting deed does; nothing is silently swallowed.
- Exploration writes the host facts and a thin headless note instead of scanning a screen.

Without that fact, a host lacking the Windows platform fails hard at the bind step, at load, before the
wheel turns. This is correct and deliberate: the declaration is an operator's stated fact about the host,
never a detection that quietly adapts, and never a fallback that hides a missing capability. It plumbs in
the same way the transport choice does — a launch decision the body obeys, read once and handed to the
capabilities as they load.

The value of the headless mode is that the organism's thinking, its laws, its wheel, and its
witness-proven honesty are all exercisable on an ordinary server or developer machine, with the
GUI-driving hand held in reserve for the Windows host. The prompts do not change between hosts; a
screenless host is a thinner reading of the world rather than a broken one.

---

## The brain that pauses: the caller as mind

Three of the four transports answer within the running process: the call goes out, a reply comes back,
the turn completes, and the wheel turns again — a whole life in one invocation. The file proxy is
different in kind. It does not carry the prompt to a model at all; it splits a turn at the model-call
boundary and lets the process exit in between, so that whatever launched the organism becomes its mind.
This is a real pause-and-resume, and it rests entirely on the atemporal law: the only thing that must
survive between the two halves is the current stage, and that already lives in the document's own state.
Nothing is held in memory, so nothing is lost by exiting.

A turn under the file proxy has two halves across two invocations:

- Emit. The engine assembles the stage's prompt exactly as any transport would, then writes it to a
  request file beside the document — a small JSON object carrying the prompt, the exact response schema
  the reply must satisfy, and a unique request id. It prints to the console only the request file's bare
  name and a short instruction: open that file, write your record to the response file under this id, and
  run the same command again. It does not print the prompt itself, so the caller must actually read the
  file and do the work rather than answer from a glimpse. Then the process exits, having advanced nothing.
- Consume. On the next invocation, if a response file is present whose id matches the pending request,
  the engine reads the record from it, deletes both files, and runs the rest of the turn — posting the
  fields, running the deed, folding the result, appending to the ledger on a witnessed advance, and
  advancing the stage. Having consumed the answer it then emits the next stage's request and exits again.
  So one invocation eats the last answer and hands out the next question: the caller is pumped one
  half-turn at a time.

The two scratch files plus the stage already saved in the document are the entire state machine, and none
of its states is corrupt. Three cases cover it: no request file means write one and exit; a request
present but no matching answer means re-print the same instruction and exit, changing nothing, so a
caller that has not yet answered can run again harmlessly and idempotently; a request with its matching
answer means consume, run, advance, and emit the next. A killed process between halves loses nothing,
because the pending request on disk and the saved stage are all that a resume needs. There is no polling
and no waiting loop anywhere; the organism does its half and stops. An id mismatch, a malformed envelope,
or any other fault raises hard, as everywhere else.

The consequence is the reason this transport exists: the mind driving the organism need not be a model
behind an API. It can be a person answering by hand, another program, or an AI agent that ran the launch
command and reads the printed instruction as its own tool output — and, following that honest
instruction, opens the request, writes the record, and runs the command again. The launcher becomes the
transport. It is the native-agent principle inverted: instead of the organism opening a child mind, the
mind opens the organism and feeds it. This has been driven end to end by hand: an emitted request read, a
record written, the command re-run to consume it and advance the stage, half-turn by half-turn, across a
full life that ended on a proven goal.

Because a run and a resume are the same command, a fresh life must be started deliberately (see
[Running and observing](#running-and-observing)); otherwise every resume would wipe the memory it is
trying to carry forward.

Human-facing paths are printed as bare file names, never absolute paths. The caller always runs from the
document's own folder, so the name alone is enough to find the file, and a bare name avoids the mismatch
between a host-native path and the path form seen from a mounted view of the same folder. The engine
still resolves the real location internally, from the document's own directory, so the file operations
are correct regardless of the caller's working directory; only the human-facing hint is the short name.

---

## How the prompt is assembled

Every model call is built the same way, stable content first and volatile content last, so a provider
that reuses a prefix sees the unchanging part up front.

- First the shared prompt prefix: the Law, the atemporal rules, and the living-word law — the three-row
  board, write only thine own row, an atemporal reading proved against the fresh environment — unchanging
  across every call.
- Then the current stage's charge: this faculty's one task, in the biblical register.
- Then the blackboard slots the stage declares it reads, in order, with the fresh environment last and
  trimmed to the character budget.
- Then, when the developer-feedback schema is set, the accumulated developer_feedback, shown as fallible
  counsel from the faculties, never as law.

A provider-side prompt cache key that would let the provider reuse the stable prefix across the many
calls of one life is not set today; adding it is a minor standing intention.

The prompts use a dense biblical (King James commandment) register on purpose. It is a steering technique
that pulls the model into a high-fidelity, low-variance region where output is recalled rather than
improvised. Distillation may compress it; it must not secularize it. Modern or technical terms are wrapped
in square brackets so they stand out from the biblical prose; that bracketing convention is load-bearing
and is kept. Each prompt's promises are true against the document's own engine and capabilities: what the
prompt names by bare name, the namespace supplies; what the prompt says to return, the record contract
requires. The prompts were last rewritten from zero against the live contracts, namespaces, signals, and
routing, so promise equals provision at every stage — the actor names exactly the actor namespace, the
witness declares plainly that it has no hand and no click index, and the conscience states that it runs no
code.

The model is asked for one JSON record. An empty completion is a loud, named failure, never a silent
pass: a call that returns no text raises rather than feeding emptiness into the parser.

---

## The records and their enforcement

Each stage's model call returns one JSON record envelope, `{record_type, data}`. The engine sends the
provider a strict JSON schema built from that stage's record contract, so the provider itself is bound to
return the exact record type and a closed data object whose required fields are present, typed, and
non-blank. Correctness of shape is forced at the wire, not hoped for. After the reply, the engine unwraps
the envelope and fails hard if it is not a proper record or carries the wrong record type; the declared
fields are then posted to their slots by the stage's `writes` map.

| Record | Produced by | Required fields |
| --- | --- | --- |
| execution | execute (actor) | perceived, alternatives, intent, code, goal_interpretation |
| verification | verify (witness) | code, goal_interpretation |
| recovery | recover (conscience) | lesson, target, strategy, goal_interpretation |

Field meanings:

- perceived: the relevant state the actor sees right now.
- alternatives: each road weighed and forsaken, and why.
- intent: the true next effect the actor seeks; posted to the action_frame the witness then reads.
- code: the Python to run. For the actor it changes the world and is kept in the code slot; for the
  witness it is a read-only probe that must set the verdict and is not persisted.
- goal_interpretation: this faculty's living-word row — what it learned of the world, the obstacle, the
  distance still to the outcome, and the next true move, not a restatement of the goal.
- lesson: the named defect, why by the evidence it truly failed, and what must change.
- target: the concrete anchor in the present environment the next deed should aim at.
- strategy: the framed next attempt, departing from every approach already tried.

Beside the stage fields, each faculty may return a `developer_feedback` string, enforced by the wire
schema when the developer-feedback schema is set. It is the faculty's fallible note to the developer —
what in the prompt, record, context, or namespace hindered a clean answer, and the least amendment
proposed — appended to the developer_feedback slot and shown to later calls as advisory counsel only. A
faculty writes the empty string when it has no true defect to report, and the empty note is dropped rather
than accumulated.

The writes maps are deliberately spare. The actor posts its intent, code, perceived, and alternatives.
The witness and recovery post no field through their writes maps at all. Every faculty's
`goal_interpretation` is merged by the engine into that faculty's own row of the living word rather than
posted through a writes map, so the three rows never overwrite one another. Recovery's target, strategy,
and lesson are composed by the engine into the single action_frame the actor consumes, so the required
fields are enforced at the wire yet delivered whole rather than scattered or dropped. The witness's
verdict is folded in from the run, not from a written field, and its reason is the fact the engine binds
into the proven ledger.

Because the schema is enforced at the wire, a reply used to exercise the plumbing offline must itself be a
proper `{record_type, data}` envelope; a bare flat object is rejected loudly by design.

---

## The hand and the capabilities

The `capabilities` section is the hand and the eyes, carried inside the document. It is Windows-only: UI
Automation for sight, input synthesis for the hand. Nothing is downloaded and nothing need pre-exist on
the machine beside the document; the engine loads this section into a live module the run namespace draws
from. The whole of the eager Windows binding is isolated in a single step run once at load, and only when
a GUI is expected, so the same block loads inertly on a host with no desktop.

The hand, reached by the actor as `desktop`:

| Method | What it does |
| --- | --- |
| click(x, y, hwnd) | Move the cursor and click at physical coordinates, optionally within a window. |
| type_text(text) | Synthesize real keystrokes, one code unit at a time. |
| paste_clipboard(text) | Set the clipboard, then paste. |
| set_clipboard(text) | Set the clipboard contents. |
| press_key(key) | Press and release one named key. |
| hotkey(*keys) | Press a chord and release in reverse order. |
| scroll(x, y, amount / clicks) | Scroll the wheel at a point, by exactly one of amount or clicks. |
| open_url(browser, url) | Open a URL with the default handler or a named browser. |
| observe(config) | Re-open the eyes in-process and return a fresh observation; the actor's own looking, and so no proof. |

Two text roads exist on purpose: `type_text` synthesizes real keystrokes (the trusted events rich web
editors accept), and `paste_clipboard` carries content a keystroke stream cannot. The actor targets by
short id from the action_index and reads the click point there; it does not hardcode coordinates. On a
GUI-less host every one of these methods is present by name but raises when called.

The capability namespaces are decided by the deed's kind, when the engine builds the run namespace:

| Name | Actor | Witness |
| --- | --- | --- |
| desktop (the hand) | yes | no |
| action_index | yes | no |
| screen_elements, desktop_tree_text | yes | yes |
| repo_root, python_executable | yes | yes |
| commit_section | yes | no |
| stdlib | yes | yes |

The witness is handed neither the hand nor the click index, in keeping with the Law: it may read the
world but neither move it nor reach for the actor's own binding of it.

A nested model call from within a deed — by which the actor's own code could consult the mind again
mid-deed, including a web-search profile — is not present in the namespace today. Providing it is a
standing intention, and it is deliberately absent from the current prompts until it exists, because a
prompt must never promise a bare name the namespace cannot supply.

Because the Windows eyes and hand are more than half of the document's bulk and a GUI-less host runs none
of it, a slim headless twin of the document can be derived: a build output whose capabilities keep only
the headless path (the hand that raises on call, the environment reading, the namespace builder) and drop
the whole Windows surface, everything else copied verbatim. The twin is regenerated fresh from the
document, never maintained as a second source, so it cannot drift; it saves download and load cost on a
lean host, not prompt tokens (the capabilities are never sent to the model), and is headless-only by
construction.

---

## Running and observing

The organism drives a real desktop on Windows, where perception and input are live. It also loads and
turns its wheel headless on any host when told the host has no GUI. Set the mind's API key first if the
chosen transport needs one, then drop a needle on the document with a one-sentence goal: a tiny bootstrap
reads the document's `engine` section and executes it, handing in the document path and the launch flags.
A bare one-liner works; no separate launcher file is required.

Launch facts (each is a stated fact for one life, never a detection): choose the mind (which transport);
declare a GUI-less host; request a fresh start; run a single turn; print the assembled prompt without
calling the mind; feed a saved reply from an explicit file in place of a model call; or turn on the
remote counsel channel.

A fresh life is asked for explicitly: only when the reset fact is given does the engine run the `reset` to
clear the memory slots, including the goal, to a clean slate while preserving the body. Reset is opt-in
rather than automatic because a run and a resume are the same command under the pausing file-proxy mind;
if reset fired on every launch, each resume would wipe the very memory it means to carry forward. So a
fresh life is started with the reset fact, and every continuation of that life omits it.

The body prints only a terse per-turn line to the console (stage, signal, next stage, streak). On a host
with a desktop the true progress feed is the real screen, because the organism drives the GUI; on a
headless host the feed is that line and the document itself. The blackboard is inspectable directly: it is
the document, rewritten each turn. The whole plumbing can be proven for free without spending a model
call — print the assembled prompt for a stage against a live scan, or drive the pausing file-proxy mind by
hand.

A hard kill corrupts no state, because the organism keeps no cross-life memory; an externally stopped life
is simply incomplete, neither a false victory nor a proof of hopeless failure.

A heuristic security scanner will flag the organism, and this is expected, not a defect. Its normal
operation is behaviourally indistinguishable from a dropper or a remote-access trojan: it runs code it was
handed, synthesizes real keyboard and mouse input, and launches applications to drive the GUI as a human
would. Input synthesis and programmatic GUI control are exactly the signatures such scanners are built to
catch. This cannot be made innocent without removing the very behaviour that is the organism's purpose.
The mitigation is operational, never a change to the body: run it in an environment you control, with a
scoped exclusion for that location alone. A harness that kills the run is a traditional agentic safety
leash, alien to an organism, and is not a defect to cure by adding a confirmation prompt or any other cage.

---

## Design laws that never change

- Fail hard. No fallbacks, no defensive branches for unwired features, no silent swallowing. A hard
  visible failure drives correction; a swallowed one rots the system. An empty completion raises; a
  malformed record raises; an unmapped routing signal raises; a GUI-less host without the declaring fact
  raises at load rather than pretending to have a screen.
- Never cage the organism. Add no limit, counter, branch, delay, or guard it cannot itself rewrite through
  the document. The compile-gate is not a cage: it admits any body that runs and only refuses one that
  could not.
- Subtraction over addition. Prefer removing a defect to adding machinery around it. Binary essentiality:
  a thing is essential or it is removed completely, with nothing left dangling — a slot no faculty reads
  and no faculty needs is removed, not kept "just in case." Prefer unifying scattered repetition into one
  place over guarding each copy; prefer exit-and-resume over a waiting loop where the saved state already
  makes a held process unnecessary. We do not change logic to add a knob; we expose or cut what is already
  in the tree.
- One source of truth. The document defines the organism; the prompt is assembled from its config and its
  slots, and every prompt promise is true against the document's own engine and capabilities. No code or
  definition the organism depends on may live outside the single document; a derived artifact is a build
  output, never a second authority. Promise equals provision: a prompt names exactly the namespace it is
  given, no more and no less.
- Honesty by structure. The actor claims; the witness proves by independent effect read afresh from the
  world; the separation is enforced in the namespace that builds each run; the witness never overwrites
  the deed it judges; and the proven ledger carries only the witness's own reason bound to the deed, never
  the actor's self-report. Honesty is never proven by hashing the living body or by citing a git fact; it
  is proven by a world-effect a separate faculty reads.
- Atemporal by design. No hidden store, no scratchpad that survives a turn beyond the living word and the
  narrow witnessed ledger. What is not narrated forward is forgotten, so the organism cannot fool itself
  with a stale belief. A short on-screen id dies with the look that bore it and may never enter text that
  outlives the turn. Boundedness comes from rewriting, from dedup, and from the environment budget, never
  from silent corruption of memory.
- Purpose comes only from the goal. The lodestar is supplied from outside, never scavenged from the world.
  With no goal the organism holds stable and waits; it does not invent a substitute. This restraint is a
  law, not a guard, and like any law it lives in the document.
- The mind is interchangeable; the body and the law are not. A transport may be swapped at launch without
  touching the wheel, the prompts, or the record shape, because every transport ends in the same
  schema-bound envelope — and choosing a transport must not rewrite the body's declared default.
- Host capability is declared, not detected. Where a host lacks a capability the body needs, an operator
  states it as a launch fact; the body obeys the declaration and otherwise fails hard. It does not sniff
  the environment and quietly adapt.
- The body is hot-swappable and its defects are the substrate. A defect the organism can observe and
  rewrite is a feature of the self-modifying design. Prefer making defects visible over hiding them —
  every number that governs behaviour lives in the config as data, not as a hidden literal.
- The document must stay coherent under its own hand. Headings inside fenced code are not sections and a
  slot is never duplicated, so the organism writing into its own memory cannot forge or multiply the body.
- State what is, positively. Where a thing is not yet done, say so plainly; do not describe an aspiration
  as if it were flesh.
- The biblical register in prompts is load-bearing. Distill, do not secularize. Keep the square-bracket
  marking of modern terms.
- The body carries no prose comments or docstrings. The stage prompts are the body's only exposition; the
  Python is kept legible by structure and naming, because the whole document is read by the model for
  self-rewrite and every non-functional line is dead weight.

---

## The road to the north star: self-correction without us

The north star is an organism that corrects itself without a human in the loop — one that, handed a goal,
not only drives the machine but repairs its own body when a tool is the true defect, and does so under
laws that keep it honest while it does. Everything built so far is the road toward that, and the finish
line can be stated plainly so progress against it is legible.

What the road has already laid down:

- A wheel that acts, proves, and recovers, with honesty enforced by structure rather than by trust.
- A body the organism can edit under law — the compile-gate takes a section edit whole or rejects it
  whole, so the actor can already rewrite `config`, `engine`, `reset`, or `capabilities` when effect does
  not match word.
- Perception, host facts, and the failure streak that widens recovery, so a repeated failure pushes the
  organism toward changing the kind of approach, up to mending its own code.
- Every governing number exposed as data, so the thing that must reason about its own behaviour can see
  and change what shapes it.

What still stands between here and the finish line, each stated as an honest gap:

- Body edits to the running Python take effect only next life. True in-life self-repair of the engine or
  the capabilities — a mend that takes hold in the same run that discovered the defect — is the largest
  remaining step toward self-correction without us.
- The deed runs in-process rather than as its own child program, so a deed cannot yet be isolated,
  timed, or killed independently of the wheel that launched it.
- The environment budget is blunt; an intelligent allocation of the model's attention across the world is
  intended.
- A nested model call, transmission dumps for auditing a long unattended life, and a per-run transport
  choice kept out of the persisted body are each intended and named below.

The finish line is not a feature list; it is a property: the organism, left alone with a goal, makes a
genuine advance, has it independently witnessed, and — when it cannot advance — diagnoses and repairs the
true defect in its own body within the life, all without a human turning the wheel. The laws are the
guarantee that this autonomy stays honest rather than becoming a machine that merely believes itself
successful. The appendix records one candidate architecture for the far end of this road and the hazards
that must be named before it is ever built.

---

## Standing intentions: known work not yet done

These are things the design intends but the live document does not yet do. Each is stated as an intention,
not a promise — the honest gap between the design and the flesh.

- Run the deed as its own child program. The returned code runs in-process; the intended shape is a real
  file executed as a subprocess reporting back through a result file, matching the actor's own charge to
  write a file and invoke it.
- Make engine and capabilities edits take effect within the life. A committed edit to the control data
  hot-swaps on the next turn, but the running Python — the engine, and the once-cached capabilities — does
  not; a body mend to the Python does not take hold until the next life. This is the largest step toward
  self-correction without us.
- Make the environment budget intelligent. The budget trims the environment by raw length from the end,
  first-come-first-served by window order, with no per-window fairness or relevance weighting. An
  allocation that spends the model's attention where it matters is intended.
- Write full transmission dumps. A full, untruncated on-disk record of every model call — request body,
  raw and parsed response, extracted content, and a small meta summary, written on success and on
  transport failure alike — is intended for auditing a long life turn by turn. It must stay observability,
  never a fallback: nothing swallowed, the fault still raised, the failing request preserved.
- Keep a launch-chosen transport out of the persisted body. Selecting a transport for a life should not
  rewrite the document's declared default; a per-run choice belongs to the run, not to the constitution,
  and must not be carried into the config the next flagless launch reads.
- Add a nested model call. The actor cannot consult the mind again from within a deed (or make a
  web-search sub-call) today; the capability and its prompt mention are to be added together, and only
  together.
- Add an outbound channel. The organism takes counsel in from a remote note; a mirrored outbound channel —
  by which it publishes a proven result or a body edit out through version history — is intended, kept
  law-clean: an outbound send is an actor deed, the witness still proves by independent effect, and no
  secret is written in plaintext.
- Decide the perceived/alternatives channel. The actor's read of the world and the roads it forsook are
  written each turn; whether a later faculty should read them to diagnose a fault, or whether they stay
  board-visible documentation only, is an open decision.
- Mark unreachable elements. Elements that are observed but off the visible screen are shown to the model
  the same as reachable ones; whether to mark them readable-but-not-clickable, rather than hide them, is
  an open decision — hiding was tried and rejected because a thing may need to be read even when it cannot
  be clicked.
- Set a provider prompt cache key. The stable prefix is ordered first but no cache key is sent, so the
  provider is not asked to reuse it across a life's calls.

---

## Working methodology: how humans and AI build this

This project is built by a human and an AI working as one. These are the rules of that collaboration and
of the code, stated to hold for any future session.

- The document on disk is the final authority. This knowledge base explains how and why but never
  overrides it. Read the document fresh, and confirm every claim against it before acting. Because
  `endgame.md` is the sole artifact — engine, capabilities, config, and memory all inside it — when
  reading or writing the prompts, cross-reference the engine and capabilities in the same document; a
  prompt's promise is only as true as the code that keeps it.
- Trust the live code over memory and over this file. The knowledge base is durable understanding; the
  code is present fact. Where they disagree, the code wins and this file is corrected. Prove a claim by
  reading the code or exercising the wheel, not by recalling how it once was.
- Fail hard, and never add unsolicited safety. Do not introduce fallbacks, defensive branches, caps, or
  confirmation gates the organism cannot rewrite. A visible failure is information; a swallowed one is rot.
- Prefer subtraction. Remove a defect rather than wrap it. Unify scattered repetition into one form.
  Binary essentiality: keep a thing wholly or remove it wholly, leaving nothing dangling. We do not change
  logic to add machinery; we expose what is hidden or cut what is dead.
- One source of truth. Do not extract parts of the body to sibling files as a live dependency; it breaks
  the single-document law and invites drift. A derived file (such as a slim headless twin) is legitimate
  only as a regenerated build output, never as a second authority, and must be regenerated from the
  document whenever the document changes.
- Give honest pushback. When an instruction fights the architecture, say so with a concrete reason and an
  alternative, and verify the premise of a change before building it; do not follow an instruction whose
  stated benefit the evidence does not support. Never invent the human's intent.
- Work in explicit, small, reversible phases. Propose the shape first; once a direction is chosen, execute
  it fully and autonomously, then verify. When investigating drift, do the detective work to full
  confidence and prove each claim with evidence before acting on it.
- Verify by exercising the real wheel, not by unit tests. Confirm the document reads, the config loads,
  the engine, reset, and capabilities compile, and the topology is coherent and fully reachable. The hand
  needs a real desktop, but the whole plumbing can be proven offline: on a GUI-less host by declaring the
  no-GUI fact, by printing the assembled prompt without spending a model call, and by driving the pausing
  file-proxy mind by hand — emit a request, write a proper record, resume to consume it, and watch the
  stage advance and the ledger fill only on independent proof.
- The workspace may be a mount of a folder viewed from another host. Bake no absolute path and no branch
  name into the body or this file; the organism stays correct regardless of where the folder sits or which
  branch it lives on. Edit from whichever host is convenient, but a real desktop-driving run needs the GUI
  host, and version-history and credentialed operations go through the host shell that holds those
  credentials.
- The body imports only the standard library. Any package a parser or side tool needs is installed on the
  working host, never made a dependency of the body.
- Keep runtime scratch out of history. Extracted scripts, materialized modules, proxy request and response
  files, run logs, and the private self-edit repository are transient; they do not belong in the committed
  body. Prefer an allowlist ignore — ignore everything, admit named files — so scratch can never leak in by
  accident. Never commit runtime memory; after a live run, restore the document to its clean seed.
- Commit only when asked, and stage deliberately. Write each commit with full reasoning: what kind of
  feature or defect was added, removed, or replaced, and why, so a future reader can rebuild the context
  from the message rather than the diff. The commit log is the durable handover.
- Near a context limit, stop, summarize what was found, write exact next-phase instructions, and
  checkpoint, so the next session continues precisely where the last one left off.

---

## Handover: the distilled startup prompt

This is the compressed form of everything above — enough for a fresh session to orient and act. It is a
distillation, not a new authority: the document on disk still wins, and this file explains the rest.

> You are working on endgame-ai: a stateless, self-modifying organism that is one Markdown document,
> `endgame.md`. That document is the whole organism — `config` (JSON control policy), `engine` (Python
> wheel), `reset` (Python), `capabilities` (Python hand and eyes), plus memory slots — and it is the final
> authority. Read it in full and fresh before reasoning; where memory or this file disagree with the code,
> the code wins.
>
> The wheel is a blackboard, not a wiring: three faculties are woken one at a time by a control policy that
> routes on the signal a stage raised. execute (the actor) writes Python and moves the world, claiming only
> intent. verify (the witness) writes read-only Python and proves an effect by a system other than the
> actor; it has no hand and no click index. recover (the conscience) writes prose only after a denial and
> frames a departure that widens with the failure streak. Nothing enters the proven ledger except by the
> witness.
>
> Laws, non-negotiable: fail hard, no fallbacks, no silent swallowing. Never cage — add nothing the
> organism cannot rewrite through the document. Subtraction over addition; expose or cut, do not wrap. One
> source of truth; promise equals provision (a prompt names exactly its namespace). Honesty by structure,
> never by hashing the body or citing a git fact. Atemporal — an ephemeral on-screen id dies with the look
> and never crosses a turn. Purpose only from the goal; with no goal, hold stable and wait. Host capability
> is declared, not detected. The biblical register in prompts is load-bearing: distill, never secularize,
> and keep the square-bracket marking of modern terms. The body carries no comments; the prompts are its
> only prose.
>
> Self-modification is real: the actor calls `commit_section(name, body)` for one of `config`, `engine`,
> `reset`, `capabilities`; a private git history with a compile-gate hook takes the edit whole or rejects
> it whole. Config edits hot-swap next turn; engine and capabilities edits take effect only next life —
> closing that gap is the largest step toward the north star, an organism that self-corrects without a
> human. The compile-gate is not a cage; do not build a git-formatting layer on it.
>
> The mind is one of four interchangeable transports chosen at launch (hosted Responses, local Chat
> Completions, native agent over stdio, and a file proxy that pauses the process so the caller is the
> mind); every transport ends in the same schema-bound `{record_type, data}` envelope. Perception is
> automatic before every think: window-first scan with knobs exposed under `config.observation`, host facts
> gathered into the environment, and a blunt character budget trimming it. An optional `--counsel` channel
> fetches a remote steer note (default off, so no per-turn outbound request); counsel is advisory, never
> written into the document. The eyes and hand are Windows-only, isolated to one bind step skipped under a
> declared no-GUI host.
>
> Verify by exercising the real wheel, not unit tests: confirm the document reads, the config parses, and
> engine/reset/capabilities compile; print the assembled prompt without spending a model call, or drive the
> file-proxy mind by hand. Keep runtime scratch and memory out of history. Commit only when asked, stage
> deliberately, and write long context-carrying commit messages, because the log is the durable handover.

---

## Glossary

- Blackboard: the shared structure every faculty reads and writes; here, the document's sections.
- Board / document: the single Markdown file that is the whole organism; its sole artifact.
- Section / slot: one `## name` region; a body slot defines the organism, a memory slot changes as it
  lives.
- config: the inert JSON slot holding the mind's transports, the law, the record contracts, the
  observation knobs, the environment budget, the stages, and the routing.
- engine: the Python slot that turns the wheel.
- reset: the Python slot, run on its own at a fresh life, that clears memory (including the goal) while
  preserving the body.
- capabilities: the Python slot holding the hand and the eyes; its eager Windows binding is one step run
  only when a GUI is expected.
- Stage: one step of the wheel, defined purely by data (record_type, prompt, reads, writes, exec, routes).
- Faculty: a stage that makes one model call (execute, verify, recover).
- Actor / witness / conscience: execute (moves and claims), verify (proves by independent effect, no hand
  and no click index, never overwriting the deed), recover (frames a different strike after denial, prose
  only).
- Deed: the Python the actor authors, kept in the code slot. Run in-process today; intended to run as its
  own program.
- Probe: the read-only Python the witness authors; transient, run once, not persisted.
- Exploration: the pure-Python reading of the world the engine performs before every model call, so the
  model never reasons on a stale view — the host facts plus the window-first perception, or the host facts
  plus a thin headless note.
- Compile-gate: the private git history and pre-commit hook through which `commit_section` takes a body
  edit whole or rejects it whole; a Python section must compile and a JSON section must parse.
- commit_section(name, body): the actor's self-edit call, admitted only for `config`, `engine`, `reset`,
  `capabilities`; memory and proof slots are not editable through it.
- action_frame: the actor's hand-off slot — its declared intent after a deed, or recovery's composed
  target+strategy+lesson briefing after a denial.
- Record / envelope: the mind's reply, `{record_type, data}`, its shape forced by a strict wire schema.
- record_contracts: the per-record-type declaration of required fields, types, non-empty, and closed
  object, from which the wire schema is built.
- Namespace: the set of names the engine puts in place for a run — the promised bare names and, for the
  actor, the hand and the click index — keeping the prompt's promise at execution.
- Transport / mind / brain: the interchangeable means by which a prompt reaches a mind and a reply returns
  — hosted Responses, local Chat Completions, native agent over stdio, or the pausing file proxy — chosen
  at launch; every transport ends in the same schema-bound envelope.
- File proxy: the transport that exchanges a turn through a request file and a response file and pauses the
  process between them, emitting the request and exiting, then consuming the matching answer and advancing
  on a later invocation, so the caller (person, program, or launching agent) is the mind. Its scratch
  files plus the saved stage are the whole state machine; re-running with an unanswered request is
  idempotent, and a kill between halves loses nothing.
- Headless / no-GUI: a launch-declared host fact that skips the eager Windows binding, gives the actor a
  desktop hand that raises when called, and writes host facts plus a thin note instead of a screen scan.
- Headless twin: a slim, derived-from-the-document copy for a GUI-less host, its capabilities reduced to
  only the no-GUI path with the whole Windows surface dropped; a regenerated build output, not a second
  source.
- observation: the config block of perception knobs — step_px, max_subtree_nodes_per_point, depth_ceiling,
  min_window_area — exposed as data so the organism can tune its own perception.
- max_environment_chars: the config number that trims the environment slot in the prompt; blunt today, an
  intelligent budget is intended.
- Counsel channel: the optional, launch-enabled remote steer note fetched each turn into the counsel slot
  and shown to every faculty; advisory only, deduplicated, never written into the document, off by default
  so no per-turn outbound request is made.
- Signal: the word a run raises; routing keys on it within the current stage, and an unmapped signal
  raises.
- Route: a stage's map from signal to next stage; a target of "halt" ends the life.
- Living word: the narrative thread carried forward; a board of three rows, one per thinking faculty, each
  writing only its own row, with the goal as a separate lodestar.
- Lodestar: the goal slot; the sole source of purpose, supplied from outside and never scavenged from the
  world.
- Distance to the outcome: each living-word row's reading of how far the goal stands; zero means proven
  (the witness may halt), and an empty goal makes it undefined/infinite so the organism waits.
- Temptation: an action the world suggests that is not the goal; the actor records it as a forsaken
  alternative rather than acting on it.
- Proven ledger: the narrow list appended only on a witnessed confirmation; each entry a structured
  "deed — witnessed: reason" fact, deduped so a re-confirmed advance never repeats.
- failure_streak: the forward counter of turns since the last witnessed advance; escalates recovery.
- Environment: the host facts plus the fresh window-first screen tree gathered before every model call, or
  host facts plus a thin headless note where no GUI is present.
- Hot-swap: the engine re-reads the document's data each turn, so a committed control-data edit takes
  effect within the life; an engine or capabilities Python edit does not, until the next life.
- halt: the route target that ends the life; set by the witness when the whole goal is proven.
- unwitnessed: a witness probe that raised before a verdict; it routes to recovery and claims nothing.
- Standing intention: a thing the design means to do, stated plainly as not yet done.

---

The document on disk is the final authority. This file is how and why; the document is what is. Read it
fresh, and where they disagree, the document wins.

---

# Appendix: the deed-becomes-a-node architecture

This appendix records a candidate future architecture and its critique. It is not built and is not part
of the live document; it is a standing idea held here so it and its hazards are not lost. Stated
atemporally: the organism is a three-stage wheel (execute, verify, recover) over a blackboard, and this
appendix describes a different shape it may one day take. Where the two disagree, the live document is what
is, and this appendix is only what might be.

## The idea

Retire the throwaway-script framing. The organism ships as a small seed of core stages, and thereafter an
actor's deed is no longer a script discarded after one run — it becomes a new node with its own
docstring-prompt, which the actor wires into the graph at connection points it chooses. Capability
accretes as structure, not as prose.

Six mechanisms, in dependency order:

1. Deed to node. The actor authors a node — behaviour, a docstring-prompt, and chosen edges — instead of a
   one-shot script. This is the atomic act on which the rest rests.
2. Fitness by use. Each non-core node measures its own worth in plain Python. Worth is goal-advancement
   per invocation — did a witness confirm a deed downstream of this node — never raw firing frequency,
   because counting firings would reward a loop.
3. Pruning. Low-fitness nodes are discarded and high-fitness nodes persist, so the graph self-cleans.
4. Stigmergic routing. Flow is not a fixed edge table but ant-colony pathfinding: data walks the graph,
   reinforces paths that reach the goal, and lets paths that do not evaporate. Edges carry weight and the
   topology self-reconnects. This is the load-bearing insight, because hardcoded edges cannot survive
   nodes that appear at runtime, whereas weighted evaporating paths can.
5. Backpropagation of structure. When a new node proves useful, the system may rewire neighbouring nodes
   to accommodate it — a graph-structure analogue of weight updates, a network whose neurons are agents.
6. Recursion without children. To invoke the whole organism, no child is spawned; a second actor is wired
   in parallel to the first, like resistors in parallel, and flow splits through it. That parallel actor
   is a sub-organism achieved purely by wiring. Merger nodes, also actor-authored, collapse redundant
   subgraphs.

The unifying principle: core reuses code, node reuses node, topology reuses itself. Self-similarity at
every level is the real fractal — not literal child-spawning.

## The critique

What is strong:

- It addresses the deepest failure mode of a prose-only memory: a life can re-derive and re-crash on the
  same shape because nothing durable accrues but words. Node-accumulation gives a real
  memory-of-capability without breaking atemporalism, because the nodes are the wiring, and the wiring is
  the one durable structure the atemporal law already permits.
- Recursion by parallel-wiring is elegant and correct: a node wired to a second actor is a nested organism
  with no child-spawn, and parallel fan-out is a primitive a graph can already express.
- Stigmergy is the right routing model for a graph that rewrites itself, because only weighted, evaporating
  paths can absorb nodes that did not exist when the life began.

What breaks if built naively, in order of danger:

1. Fail-hard versus exploration. The core law is fail-loud with no fallbacks, yet ant-routing requires
   tolerated failing paths. The resolution is a boundary: fail-hard governs the core seed; grown nodes live
   under explore-and-decay soft fitness. That boundary must be explicit and un-crossable, or the organism
   could come to rewrite its own survival criterion — the one thing that must stay beyond its reach.
2. Fitness must be goal-advancement, not frequency. Counting invocations rewards the repeat-the-same-move
   pathology; the loop would score as the fittest node. Fitness must ask whether a witness confirmed a
   downstream deed, so reinforcement follows the solution and not the loop.
3. Structural backpropagation is unbounded and premature. Neighbour-rewrite-on-insertion has no convergence
   guarantee, and a system that can already oscillate should not add one. It is deferred until
   node-creation, stigmergic routing, and honest fitness are each proven.
4. One budget lever at a time. A budget that caps count, prunes, throttles, and gates merges at once is
   doing too many jobs. Begin with a single lever — a cap on live non-core nodes, evicting the lowest
   fitness — and add levers only when each is proven, the elimination methodology applied to the budget
   itself.
5. Parallel recursion needs a base case. A whole organism wired in parallel is unbounded recursion unless
   it draws from the same global budget, so depth is bounded by exhaustion rather than by a hardcoded cap
   that would cage it.

The deepest tension: atemporalism holds that the body carries only its wiring and the living word. This
idea makes the wiring itself the accumulating memory — lawful, but it turns the wiring from a small
human-authored artifact into a large, machine-grown, partly-illegible structure. It trades a legible body
for a learning one. That trade is to be named aloud before it is ever made.

## Invariants the idea must not breach

- The fail-hard core and the explore-and-decay periphery are separated by a boundary that cannot be
  crossed from either side.
- The trade of a legible body for a learning one is named explicitly before any grown wiring is admitted.
- No node ever gains the power to rewrite the survival criterion.

## The ordering, when it is built

Build order that de-risks the idea: first the deed-to-node act; then fitness as goal-advancement per
invocation, never raw count; then a single budget lever; then stigmergic weighted routing with
reinforcement and evaporation; then recursion by parallel-wiring bounded only by the shared global budget;
and last, deferred until its convergence is understood, the structural backpropagation of
neighbour-rewrites.

---

The document on disk is the final authority. This file is how and why; the document is what is. Read it
fresh, and where they disagree, the document wins.
