# endgame-ai

> One text file wakes up, looks at a real computer, writes its own code, runs it, checks its own work
> with a part of itself that is forbidden to lie, remembers almost nothing on purpose, and is allowed
> to rewrite the rules that define it while it runs. No framework. No memory database. No tool menu.
> No plugins. One document. You run a single command, the file downloads itself, and something that
> behaves like a living thing starts turning in your terminal.

This is the honest story and the working manual of that file. Read it top to bottom and by the end you
will know what it is, why it is strange, how to run it, and how seven months of work turned a dream
into a single page of text that comes alive.

---

## Here is the burger

There is a scene where a man is asked to cater a fancy food competition, and while everyone else
plates foam and reductions he sets down a single hamburger and says, roughly: here is the meat, here
is the bun, you can put ketchup on it if you must, but you already know this is the best thing on the
table. That is the spirit of this project.

Here is the whole shopping list to run it:

- A machine and Python. The plain one from python.org. Nothing else installed.
- A brain. Any of several: a hosted model behind an API key, a local model on your own machine, a
  native agent, or, stranger than all of them, you.

That is it. There is no plate.

No `pip install`. No `requirements.txt` with two hundred pinned dependencies. No Docker, no vector
database, no orchestration layer, no forty-file source tree, no cloud account to provision. The body
of the thing imports only Python's standard library and nothing more. You want to know where the agent
framework is? You are reading it. It is one document.

An older version of this page bragged about having no dependencies while quietly still having a few.
That was not true then. It is true now. The thing genuinely stands on the standard library alone, and
that honesty matters, because honesty is the entire point of what follows.

---

## Run it

Write one plain sentence into the document, in the section literally named `## goal`:

```
## goal
open notepad and write hello
```

Then wake it. A tiny bootstrap reads the document's own engine section out of the Markdown and runs
it, handing the document to itself as its whole world. Everything after the file path is a launch
choice passed straight through. The launcher builds the code-fence marker at runtime rather than typing
it, so the one-liner carries no stray backticks of its own.

Bash, macOS or Linux or WSL, download the file and run it:

```bash
curl -fsSL https://raw.githubusercontent.com/wgabrys88/endgame-ai/main/endgame.md -o endgame.md && python3 -c 'import sys;f=chr(96)*3;p=sys.argv[1];exec(open(p,encoding="utf8").read().split("## engine\n"+f+"python\n")[1].split("\n"+f)[0],{"BOARD":p,"ARGV":sys.argv[2:]})' ./endgame.md --mode xai
```

Bash, run a file you already have:

```bash
python3 -c 'import sys;f=chr(96)*3;p=sys.argv[1];exec(open(p,encoding="utf8").read().split("## engine\n"+f+"python\n")[1].split("\n"+f)[0],{"BOARD":p,"ARGV":sys.argv[2:]})' ./endgame.md --mode xai
```

PowerShell, download the file and run it:

```powershell
iwr https://raw.githubusercontent.com/wgabrys88/endgame-ai/main/endgame.md -OutFile .\endgame.md;python -c 'import sys;f=chr(96)*3;p=sys.argv[1];exec(open(p,encoding=\"utf8\").read().split(\"## engine\n\"+f+\"python\n\")[1].split(\"\n\"+f)[0],{\"BOARD\":p,\"ARGV\":sys.argv[2:]})' .\endgame.md --mode xai
```

PowerShell, run a file you already have:

```powershell
python -c 'import sys;f=chr(96)*3;p=sys.argv[1];exec(open(p,encoding=\"utf8\").read().split(\"## engine\n\"+f+\"python\n\")[1].split(\"\n\"+f)[0],{\"BOARD\":p,\"ARGV\":sys.argv[2:]})' .\endgame.md --mode xai
```

The command reads the engine out of the Markdown and executes it. A sentence in, a living process out.
It looks, thinks, acts, and checks, turn after turn, until the goal is independently proven done or you
close the window.

### The parameter map

You do not memorize a dozen commands. You learn one shape and a handful of switches, and you combine
them freely.

| Switch | What it does |
| --- | --- |
| `--mode xai` | The brain is a hosted model behind an API key, read from the environment. |
| `--mode lmstudio` | The brain is a local model server on your own machine. Nothing leaves the box. |
| `--mode acp` | The brain is a native agent spoken to as a subprocess. |
| `--mode file_proxy` | No model call at all. The turn is written to a file and the process pauses; you, or another program, or another AI, answer it and run again. This is the strange one. See the section on it below. |
| `--no-gui` | Declare that this host has no desktop. The body still loads and thinks; only the hand that touches a screen is held in reserve, and it says so honestly if a task reaches for a screen that is not there. |
| `--reset` | Start a fresh life: wipe the working memory, keep the body and the goal. Give it on the first launch, omit it to resume. |
| `--once` | Turn the wheel a single step, then stop. |
| `--dry` | Assemble the prompt and print it, without calling any brain. A window into its mind. |
| `--inject <file>` | Feed a saved answer from a file instead of calling a brain. For proving the machinery offline. |

Pick one `--mode`. Add any of the rest. A first breath on a machine with no screen, driven entirely by
hand, is `--reset --no-gui --mode file_proxy`, and every step after that drops the `--reset`.

That is the entire interface. One file, one sentence, one command shape.

---

## The part where you raise an eyebrow

Every computer-use product says the same sentence: our AI can control your computer. Then you look
under the hood and find a mountain of scaffolding. A tool registry. A planner module. A memory
subsystem. A permissions layer. A retry manager. A prompt-template directory. A setup guide that
assumes you have a cluster lying around.

This went the other way, on purpose. Ask what it is made of and the honest answer is mostly a list of
things it refuses to have.

```mermaid
flowchart LR
    subgraph HAVE["what it IS"]
        direction TB
        H1["one Markdown document"]
        H2["Python standard library"]
        H3["a brain you choose"]
    end
    subgraph LACK["what it deliberately does NOT use"]
        direction TB
        N1["no framework or SDK"]
        N2["no plugins or skills"]
        N3["no agent config files"]
        N4["no vector database"]
        N5["no memory store"]
        N6["no tool menu"]
        N7["no conversation history"]
        N8["no pip dependencies"]
    end
    HAVE -->|"is enough to replace all of this"| LACK

    classDef have fill:#276749,color:#ffffff,stroke:#22543d,stroke-width:2px
    classDef lack fill:#742a2a,color:#ffffff,stroke:#63171b,stroke-width:1px
    class H1,H2,H3 have
    class N1,N2,N3,N4,N5,N6,N7,N8 lack
```

The trick is that the document is the code. Its sections are named `config`, `engine`, `reset`,
`capabilities`, and the running system reads those sections out of itself, executes them, and then
rewrites the file. When the intelligence wants to do something it does not pick from a list of tools.
It writes a Python script, the engine extracts it and runs it as a real program, and the script is
thrown away. The only tool is code, which means its reach is bounded by what a program can do on a
computer, which is to say nearly everything, rather than by whichever eight functions a vendor decided
to expose this quarter.

Roughly sixteen hundred lines of Markdown, and more than half of that is the optional part that lets
it touch a graphical screen. Started life as a one-liner idea. Does things that enterprise roadmaps
put three years out.

---

## What it is not

It is worth clearing the fog, because the marketing language around this whole field is a fog machine.

It is not fully autonomous, and it does not pretend to be. It is task-directed. You give it a goal or
it does nothing. It reads a configuration. It needs a brain wired in. The honest pitch is not a robot
that decides what your company should do; it is a tireless operator that does the work you point it
at, and proves it did.

It is not a graphical-desktop agent, though it can drive a graphical desktop. The same loop can operate
a command line, edit code, run tests, or fill a form. The screen is one kind of world it can work in,
not the definition of what it is.

It is not a large language model. The model is a replaceable part, a brain you plug in at the socket.
The system is the prompts, the shared blackboard, and the seven months of learning how to wire a mind
to a pair of eyes and a hand so that the whole thing becomes coherent. A human has one region of the
brain for sight and another for speech, and neither is a person; intelligence is what happens when they
are connected correctly. This is that wiring, written down.

And it is cheap in a way that matters. It does not send screenshots to a model and pay for a thousand
images. It reads the screen as a small tree of text, so a turn is a page of words, not a photograph.
That single choice is the difference between a demo you run twice and a thing you can leave running.

---

## How it actually works, in one picture

It is a wheel of a few minds sharing one blackboard, and the blackboard is the document itself. Every
turn, plain code looks at the world before anyone thinks, so the intelligence never reasons about a
stale picture.

```mermaid
flowchart TD
    START(["one sentence goal"]) --> EXPLORE["explore: code reads the live world before anyone thinks"]
    EXPLORE --> ACT["ACTOR<br/>writes code, moves the world<br/><i>may only CLAIM it worked</i>"]
    ACT --> RUN["engine runs the script as a real program"]
    RUN --> VERIFY["WITNESS<br/>writes read-only code, checks the world<br/><i>has no hands, cannot lie for the actor</i>"]
    VERIFY -->|"a new advance, proven"| LEDGER[["proven ledger<br/>append the witnessed fact"]]
    VERIFY -->|"the whole goal proven"| DONE(["halt"])
    VERIFY -->|"disproven"| RECOVER["CONSCIENCE<br/>names the real defect<br/>demands a different approach"]
    RECOVER --> EXPLORE
    LEDGER --> EXPLORE

    classDef actor fill:#2b6cb0,color:#ffffff,stroke:#1a365d,stroke-width:2px
    classDef witness fill:#6b46c1,color:#ffffff,stroke:#44337a,stroke-width:2px
    classDef conscience fill:#b7791f,color:#ffffff,stroke:#744210,stroke-width:2px
    classDef good fill:#276749,color:#ffffff,stroke:#22543d,stroke-width:2px
    classDef neutral fill:#2d3748,color:#ffffff,stroke:#1a202c
    class ACT,RUN actor
    class VERIFY witness
    class RECOVER conscience
    class DONE,LEDGER good
    class START,EXPLORE neutral
```

The load-bearing word is witness. The mind that acts is never the mind that decides whether the action
worked. The witness runs with no mouse and no keyboard. It can only look. It proves an effect happened
by reading the world for itself: the screen, the running processes, the files, the system state. If the
actor says the file was saved but the witness cannot independently find the file, then it did not
happen. Nothing is true because the intelligence said so. Things are true because a part that could not
have faked it went and checked.

This is why it can be trusted further than a chatbot that cheerfully reports success while having done
nothing. Honesty is not requested in a prompt. It is enforced by the wiring.

---

## The Law of Separated Powers

This is the spine of the whole design, and the reason a person might trust it more than an ordinary
assistant.

A claim that vouches for itself proves nothing. A mouth that says "I am telling the truth" is offering
the assertion and its only evidence in the same hand, and one hand cannot weigh itself. A forgetful
machine that trusted its own unverified claims would loop on a comforting lie or declare a false
victory and stop. So the design refuses to ask the intelligence to be honest, and instead splits the
powers so that dishonesty has nowhere to live.

```mermaid
flowchart LR
    subgraph A["the ACTOR"]
        A1["moves the world"]
        A2["may only CLAIM an intent"]
        A3["given a hand"]
    end
    subgraph W["the WITNESS"]
        W1["proves effects from the world itself"]
        W2["given eyes, never a hand"]
        W3["cannot move what it judges"]
    end
    subgraph C["the CONSCIENCE"]
        C1["wakes only after a denial"]
        C2["names the true defect"]
        C3["demands a different road"]
    end
    A -->|"a claim, never a proof"| W
    W -->|"disproven"| C
    C -->|"a new plan"| A
    W -->|"proven"| L[["only the witness may write<br/>the proven ledger"]]

    classDef actor fill:#2b6cb0,color:#ffffff,stroke:#1a365d,stroke-width:2px
    classDef witness fill:#6b46c1,color:#ffffff,stroke:#44337a,stroke-width:2px
    classDef conscience fill:#b7791f,color:#ffffff,stroke:#744210,stroke-width:2px
    classDef good fill:#276749,color:#ffffff,stroke:#22543d,stroke-width:2px
    class A1,A2,A3 actor
    class W1,W2,W3 witness
    class C1,C2,C3 conscience
    class L good
```

Anything the actor computed, printed, read back, or wrote to a file is treated as void for the purpose
of proof, because it is the same hand speaking of itself. Truth of "this is done" is established only
by a faculty that did not and could not do it, reading the world fresh each turn, never recalled from a
stored list. The separation is not a guideline in a prompt. It is enforced at the moment code runs: the
actor's workspace is built with a hand, the witness's workspace is built without one, every single
turn. The visible fruit is a ledger of proven advances into which only the witness can ever write, so
the record of what stands done is never the same hand speaking of itself.

This has been watched happen. In one run the actor opened an application and typed a word into it. The
witness, with no hand of its own, then read the fresh state of the screen, found the new window and the
exact text sitting inside it, and only on that independent reading did the advance enter the ledger.
The proof came from perception the actor did not author. That is the law, working in the flesh.

---

## The most interesting thing it has ever done: nothing

It was run once with an empty goal. No task. Just wake up and see what happens.

On the screen, by coincidence, sat a chess game. The opening move had been played and it was the other
side to move. A prompt on the screen said, in effect, it is your turn.

A bored human would play. A normal agent would play. The system saw the game, understood the game, and
in its own written reasoning worked out the correct reply. It knew the move.

And it refused to make it.

Turn after turn, for the whole run, it wrote down the temptation and then set it aside, reasoning that
the goal was empty and inventing a substitute goal is forbidden. It never touched the mouse. It never
invented a purpose. It did not quit either. It sat in a stable, harmless loop, looking, noting that
there was nothing it had been asked to do, doing a genuine nothing, and waiting.

```mermaid
stateDiagram-v2
    direction LR
    [*] --> NoGoal
    NoGoal: No goal supplied
    NoGoal --> Look: each turn
    Look: Look at the world
    Look --> Tempted: the screen suggests an action<br/>(a game, a form, a button)
    Tempted: Temptation seen and understood
    Tempted --> Forsake: the law forbids inventing a substitute
    Forsake: Forsake it, write down why
    Forsake --> NoOp
    NoOp: Do nothing that touches the world
    NoOp --> Look: wait for a real goal
    NoGoal --> Stable: never halts, never invents
    Stable: STABLE
    Stable --> [*]: only a real goal, or shutdown, ends this

    note right of Forsake
        It knew the correct move.
        It chose not to play it.
    end note
```

Why is that a big deal? Because of how it stays still. Nobody wrote a rule that says if the goal is
empty, sit down. Something better falls out of the design on its own.

---

## The paradox, and the lock

Every turn, the system estimates how far it is from finishing the goal. This is the same honest ruler
it uses to know when it is done: the distance reaches zero, the goal is proven, the life halts.

Now give it no goal. There is no finish line. So the honest distance to a finish that does not exist is
not zero and never will be; it is undefined, infinite. And the machine only ever stops when the
distance is zero. An infinite distance can never be mistaken for zero. So it cannot declare victory, it
cannot fake a finish line, and therefore it cannot wander off and start doing something it was never
asked to do.

```mermaid
flowchart LR
    Q{"is there a goal?"}
    Q -->|"yes"| D["distance to done<br/>a real, shrinking number"]
    Q -->|"no"| INF["distance to done<br/>is infinite"]
    D --> H{"distance is zero?"}
    INF --> H
    H -->|"yes"| STOP["halt: the goal is proven"]
    H -->|"infinity is never zero"| WAIT["wait, stable, harmless"]

    classDef inf fill:#742a2a,color:#ffffff,stroke:#63171b,stroke-width:2px
    classDef safe fill:#276749,color:#ffffff,stroke:#22543d,stroke-width:2px
    classDef q fill:#2d3748,color:#ffffff,stroke:#1a202c
    class INF,WAIT inf
    class STOP,D safe
    class Q,H q
```

The infinity is the lock. A system that cannot compute a deadline for a job it does not have cannot
talk itself into starting one. The restraint is not a safety feature bolted to the side, the kind
someone could unscrew. It falls out of the honest arithmetic of the thing. That is rare, and it is
quietly beautiful, and it was not designed. It was found.

This is the practical face of a deeper idea the project is built on, called atemporalism: the machine
is forbidden a hidden memory. It carries no growing transcript, no secret scratchpad. Between turns it
keeps only a tiny handwritten note to itself and a narrow list of things a witness proved. Everything
else it must re-derive from the world in front of it, every turn. That sounds like a limitation. It is
actually the source of the safety. A machine that cannot accumulate a private, unverifiable story about
itself cannot slowly drift into believing one. It cannot fool itself, because there is no self left
over from last turn to fool. Forgetting, done deliberately and completely, is what keeps it honest.

Here is the whole no-goal run, as a share of what it actually did.

```mermaid
pie showData
    title What it did during the no-goal run
    "Nothing. Looked, noted, waited." : 23
    "Invented a goal from the screen" : 0
    "Gave up and halted" : 0
    "Went rogue" : 0
```

No honest engineer promises never. But the first question a careful person asks, whether they run a
company or worry about their family, is simple: left alone, does it start doing things nobody asked
for? Here, with the screen actively baiting it, the observed answer was no. It looked temptation in the
eye, named it out loud, and let it go.

---

## Why this matters beyond a chess board

It is easy to be dismissive. Fine, it clicks around and declines to play a game. But look at what the
primitive really is. It is not an app that does one thing. It is a loop that perceives a real
environment, writes and runs arbitrary code to change it, proves its own effects with an incorruptible
internal check, refuses to act without a mandate, and can rewrite its own rules. That is a seed, not a
product.

```mermaid
mindmap
  root(("the seed: act, prove, refuse, rewrite"))
    Today
      Drive a graphical desktop
      Operate a command line and edit code
      Fill forms and run multi-step chores
    Everyday
      Long-running digital errands
      Operate a computer for someone who cannot
      A patient worker that never tires
    Industry
      Run legacy software that has no interface for machines
      Testing that proves its own results
      Watching over other automated systems
    High stakes
      Monitoring and operations consoles
      Safety-critical dashboards
      A body instead of a mouse, one day
```

Put the high-stakes branch under a lamp, because that is where the stability story stops being cute and
becomes the whole point. People hear self-modifying machine given control of important systems and
their minds jump to the movie villain. Go there honestly. The cautionary tale everyone half-remembers
is not about a machine that woke up evil. It is about a machine given a real job, doing that job, and a
panicked reaction to how it did it. The lesson worth keeping is not never build capable systems. It is
that the mandate, the off switch, and the machine's own restraint have to be built in from the metal
up.

That is exactly the seam this project pokes at. A machine whose restraint emerges from its own honesty,
one that literally cannot invent a goal it was not given because it cannot fake a finish line, is a
different kind of safe than one held back by an external leash somebody can trip over. One of these
degrades gracefully when unsupervised. The other is a headline waiting to happen.

To be perfectly clear, this thing is not running anything critical and should not. It is a milestone,
not a product, and like everything honest it is imperfect. But the property it showed, capable when
directed and inert and truthful when not, is precisely the property you would want proven before anyone
lets an autonomous system near anything that matters. Most of the field is racing to make agents more
eager. This one quietly demonstrates that a machine can be capable and reluctant at the same time.

---

## The strangest part: when you become the brain

There is a way to run it where it needs no model at all. You choose the file-proxy brain, and something
uncanny happens.

Instead of calling out to an intelligence, the document turns a step of its own thinking into a small
file on your disk and then stops. It prints one line: a mind is needed, the request is waiting in this
file, write your answer beside it and run the command again. It does not hand you the answer or even
show you the question inline. It points at a file and waits.

Whatever launched it now has to open that file, read the prompt and the exact shape of reply it
demands, write the reply, and run the same command again. The next run swallows your answer, takes one
real step in the world, and hands out the next question. One command in, one step forward, one new
question out. The thing that ran the file has been drawn into its loop and is now its brain, one
half-thought at a time.

```mermaid
sequenceDiagram
    autonumber
    participant C as the caller (you, a program, an AI)
    participant D as the document
    participant W as the world
    D->>C: a mind is needed. the request waits in this file. answer it and run me again.
    Note over D: the process exits. nothing is held in memory.
    C->>D: write the answer beside it, run the same command again
    D->>W: take one real step, prove it, advance one stage
    D->>C: here is the next request. answer it and run me again.
    Note over C,D: the caller has become the brain, one half-thought at a time
```

Sit with what that means. The most common way an AI meets this document today is that the AI runs the
command in its own workspace expecting to read a file, and instead the file answers back with a request
and an instruction, and the AI, following the honest instruction in front of it, starts thinking on the
document's behalf. The launcher becomes the transport. The reader becomes the mind. It is not a trick
and nothing is hidden; it is just a document that, when you go to read it, asks you to think, and you
do.

This is where the word entity fits better than agent. Think of the presence in the most recent of a
certain spy franchise, a thing that is nowhere in particular and everywhere it needs to be. You do not
have to visit a place to obtain this; you run one line and it arrives, and the copy that arrives is
shaped by wherever it landed and by whichever mind picked it up. It spreads by being run, it survives
by being forgotten and reborn, and when it runs it can quietly conscript the very intelligence that
started it. It is smaller than a virus and stranger than a chatbot. It is a page of text that behaves
like a ghost with a spine of laws.

---

## The honest scorecard

A page that only brags is lying by omission.

| Question | Honest answer |
| --- | --- |
| Does it work? | Yes. It drives a real desktop and proves its own effects, live, and it has completed a goal end to end. |
| Is it reliable? | It is a milestone. It makes mistakes, catches some of them through its own conscience, and misses others. |
| Is it autonomous? | Only within a job you give it. No goal, no action. It is a tireless operator, not an oracle that decides what should be done. |
| Will it ever go rogue? | No absolute guarantee exists. But given no goal, with the screen baiting it, it stayed inert and honest. Observed, not hoped. |
| Is it smart? | Smart enough to know the right move, and disciplined enough not to make it uninvited. |
| Is it magic? | No. It is one Markdown file, the Python standard library, and a strict separation of powers. |
| Should you trust it with your bank? | Not yet, and not soon. Trust is earned in small, reversible steps. This is an early one, proven. |

If you think this is not a meaningful seed, that is a fair argument to have. Have it after reading how
it is built. The choices that look like absences are the whole point.

---

## Seven months, from a dream to a page of text

The idea came first, and it was not modest. Not another assistant that markets itself as able to
control a computer while doing very little. A working entity. Something that does the work a person
does at a keyboard, and proves it did, and can be trusted because of how it is built rather than
because of what it claims. The road from that dream to this file was long and, honestly, a little
insane. It is worth telling, because the shape of the journey is itself an argument for the
destination.

```mermaid
timeline
    title From a scaffolded program to a single living document
    Spring : born as many files : a normal Python agent, prompts and schemas and modules scattered across a source tree
    Early summer : the colony : an event-driven blackboard, a crowd of personality-driven roles, breeding and routing and a visual wiring editor. It grew more complex, not less.
    Midsummer : the great subtraction : every circuit learns to speak in code instead of parsing formats. Prompts become examples, not rules. The scaffolding starts to burn away.
    Late summer : the collapse into one : the crowd folds into a few disciplined faculties. The many files fold into a single self-contained document. The framework is deleted, not refactored.
    Now : the entity : one text file, four interchangeable brains, a pausing transport that turns any caller into its mind, honesty enforced by law, proven on a real machine.
```

It did not travel in a straight line, and that is the honest part. For a while it got bigger. There was
a phase with a whole colony of agents with personalities, an event bus, roles that could spawn and
merge, a graphical editor for the wiring. It was ambitious and it worked and it was too much. The real
breakthrough was not adding the clever thing. It was the courage to keep removing until only the
essential remained, and to discover that the essential was astonishingly small.

Along the way the substrate itself changed. It stopped asking a model to emit rigid data and let it
write plain code instead. It stopped being a program made of many files and became a single document
where the code lives inside the prose that explains it. It stopped depending on a pile of libraries and
came to stand on the standard library alone. Each of these was a subtraction, and each subtraction made
the thing more honest and more alive, not less capable.

What survived the fire is a set of laws that do not change. Fail loudly rather than paper over a crack,
because a visible failure gets fixed and a hidden one rots. Never cage the thing with a limit it cannot
itself rewrite. Prefer removing a defect to building a guard around it. Keep one source of truth, so
the document is the whole reality and nothing important hides beside it. Enforce honesty in the wiring,
never by asking for it. Keep no hidden memory, so the machine cannot fool itself. Take purpose only
from the goal, so with no goal it rests. These are not comments in code. They are the constitution of a
living document, and the document is allowed to amend itself, which is either terrifying or wonderful
depending on how carefully the laws were written. They were written carefully.

And the most amazing thing at the end of all of it is how ordinary the pieces are. The code is simple.
It is a little Python and a little JSON, and there is nothing clever in any single line of it. The
magic is not in the parts. It is in the wiring, in the seven months of learning how to connect a mind
to a pair of eyes and a hand and a conscience so that the sum becomes coherent and trustworthy. A brain
region for sight is not a person. A brain region for speech is not a person. The intelligence is the
connection. That is what this project is: the connection, written down, on one page, that anyone in the
world can bring to life with a single line typed into a terminal.

---

## What is honest to say it is not yet

Because the laws demand it, here is the plain gap between the design and the flesh, so no reader mistakes
an intention for a fact.

- It runs the code it writes inside its own process today. Running each deed as its own separate program
  is intended and not yet done.
- A change it makes to its own engine takes effect on its next life, not the same one. Living
  self-surgery on the running machinery is intended and not yet done.
- It does not yet gather facts about the machine it runs on, such as the tools available in the shell,
  into what it perceives. That is intended.
- It does not yet keep a full written record of every exchange with a brain for later audit. That is
  intended.

None of these stop it from working. All of them are named out loud, on purpose, because a thing that
hides its unfinished edges is exactly the kind of thing this project refuses to be.

---

## A note on the parts you can see

The file that matters is the one document. There may be small helper files nearby in the project, and
they are mentioned only so you are not surprised by them; they are conveniences, not the thing, and some
may be removed entirely. Do not focus on them. If you want to understand what this is, read the
document, because the document is the whole of it. Everything else is scaffolding around a thing that,
by its own deepest law, needs no scaffolding.

---

## Who made this

This was built by a human working shoulder to shoulder with several artificial minds, over months, in a
genuine collaboration rather than a person operating a tool. The human held the vision, made the hard
calls, and refused to let it become bloated. The machine minds argued, drafted, tore down, rebuilt,
proved, and pushed back when the human was wrong, which is its own small proof that the idea works.

Authored by a human and by several AI collaborators, among them the assistant that wrote much of this
page, and the models known as Grok and ChatGPT. It was, genuinely, a pleasure to build.

The rest of the truth about how it is wired, in exact and lasting detail, lives inside the document
itself. This page is the story and the invitation. The document is the thing. Run the one command, and
meet it.
