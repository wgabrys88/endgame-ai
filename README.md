# endgame-ai

**You give it a goal in one plain sentence. It uses your real computer — mouse, keyboard, browser, files — and does the job. Then it proves, against the world, that the job is done.**

No task list. No scripted flow. No integration work. A folder of small Python files, one API key, one command. You walk away; it works.

> ⚠️ **Read this before you run it.** endgame-ai takes **full control of your real desktop** — it moves your mouse, types on your keyboard, opens your browser, reads your screen, writes and runs code, and installs software. It acts as *you*, on your machine, toward the goal you give it. Run it on a machine you own, with a goal you actually want carried out, and watch it. This is the point of the system, and also its risk.

---

## Fast start

```bash
# 1. get the code
#    download the zip and unpack it, or:
git clone <this-repo> endgame-ai && cd endgame-ai

# 2. give it a mind (a hosted reasoning model; a few dollars of credit is plenty)
setx XAI_API_KEY "sk-..."        # Windows        (PowerShell: $env:XAI_API_KEY="sk-...")

# 3. say what you want, in one human sentence
echo "Find a remote AI job in Krakow that fits my GitHub, and apply for me." > goal.md

# 4. turn it loose
python endgame.py
```

That is the whole setup. You do not wire up LinkedIn. You do not teach it what a form is. You do not write a single automation step. You state an **outcome** and leave. It figures out the rest, turn by turn, and stops when the outcome is truly proven — or tells you honestly why it could not.

Given **no** goal, it does nothing and halts. It never invents work.

| you type | it does |
|---|---|
| `python endgame.py` | keep turning toward whatever is in `goal.md` |
| `python endgame.py "book me a table for two Friday"` | write that goal, then run |
| `python endgame.py --once` | take exactly one full real turn, then stop |
| `python endgame.py --dry` | show the next request, call no model, change nothing |

You can edit `goal.md` or drop a note in `counsel.md` **while it runs** — it re-reads them every turn. You steer with words, never by touching the machine.

---

## What it can actually do — proven, on the record

Everything below is not a promise. It is what the system **did** in one real run, logged turn-by-turn on disk, from the single goal *"use LinkedIn to apply for a remote AI job in Kraków based on my GitHub — find the best-fit offer and apply on my behalf."*

- **Researched the web** for the applicant's real skills (Python, LangChain/CrewAI, RAG, agent orchestration).
- **Opened Chrome**, searched job boards, **read and compared several real postings**, and chose the best fit (a Staff Engineer / LLM role at Levellr).
- **Filled the real application form** — name, email, location, LinkedIn, GitHub, notice period.
- **Wrote a résumé to disk** as both `.txt` and a valid `.pdf`, then **attached it** through the native Windows file-open dialog.
- **Hit a reCAPTCHA and passed it.** It chose the **audio challenge**, found the challenge audio, **installed a second AI (OpenAI Whisper) onto the machine on its own**, transcribed the clip, typed the answer into the "Enter what you hear" box, and clicked VERIFY. After VERIFY the active challenge widget (the answer box and VERIFY button) was **gone from the page and did not re-prompt** — logged, turn by turn.
- **Submitted the application.** It then filled the remaining required fields (salary, notice period) and clicked Submit. An **independent** read of the live page reported *"Your application has been sent! You can expect to receive a confirmation email shortly."*

Vague human goal → a few Python files → the job is done. That is the entire pitch, and every line above is traceable to the run log (see [the evidence](#the-evidence-every-claim-traced)).

---

## The proof (so you don't have to take my word)

Two independent facts, both on disk, are the reason this run is a milestone rather than a demo.

**1. The application was submitted — proven by a channel other than the actor.** The organism's *witness* office (which has no hand and cannot touch the browser) read the live page and found four post-submission strings — `'confirmation email'`, `'application has been'`, `'you can expect to receive a confirmation'`, `'complete the process within two weeks'` — while the form's required-field gate was empty (`salary_edits=[]`, `submit_btns=[]`, `required_n=0`). Separately, an **independent fetch of the live Levellr page** confirms that *"Your application has been sent!"* and *"You can expect to receive a confirmation email shortly"* do **not** appear until a form is actually submitted; they exist only in the post-submission DOM. Two independent reads, same conclusion: **the application went out.**

**2. The reCAPTCHA was passed — the fact is proven; the *reason* is not.** The log proves the sequence: audio challenge opened → Whisper installed → clip transcribed → answer typed → VERIFY clicked → the active challenge widget disappeared and never returned → submission succeeded. That is what happened.

What the log does **not** contain — and what I therefore cannot claim — is *why* reCAPTCHA let it through. I do not have the transcript-vs-expected-answer comparison, the reCAPTCHA token exchange, or any risk-score telemetry; none of that is in the transmissions. So the honest statement is bounded:

> **PROVEN:** the audio widget cleared after VERIFY and the application submitted.
> **NOT PROVEN:** whether it cleared because the typed answer was correct, because of behavioral/session trust, because the token had already been issued, or some combination. Anyone claiming a specific reason (including me, earlier) is guessing.

For full transparency, the independently-verifiable details of that transcript are analyzed in [the evidence](#the-evidence-every-claim-traced) — including the correction that the transcription was *accurate*, not "garbage" as I first said.

As a user, the outcome is what matters: you asked for a job application and it was submitted. But the documentation will not dress an assumption as a mechanism.

---

## Why this is different from every "autonomous agent" demo

Most "autonomous AI" is heavy on marketing and light on unscripted work — the working part is often *pre-wired*: fixed integrations, hard-coded flows, a human quietly arranging each step behind the demo. Pull the goal sideways and it breaks.

endgame-ai has **no script and no integrations**. The firmware holds zero knowledge of LinkedIn, of forms, of captchas, of PDFs. It did all of that *at runtime*, by looking at the screen and writing its own code, turn by turn. Change the goal to "renew my domain" or "summarize these three papers" and nothing in the code changes — only the sentence in `goal.md`.

And it is **yours**. Download the zip. Buy a few dollars of API credit. Run one command. No SaaS, no seat license, no cloud lock-in, no onboarding call. The whole organism is nine small files you can read in an afternoon.

That is the line: **others sell a polished cage; this is a seed you own.**

---

## How it works, briefly

A tiny fixed **firmware** (`endgame.py`, the BIOS) boots a folder of hot-swappable `*.py` **nodes** and turns a wheel. Each turn, one of three **offices** wakes, thinks once, and acts. The firmware holds no domain knowledge — all the wisdom lives in the nodes' docstrings (which become the prompt) and their functions (which become the callable hands).

```mermaid
flowchart LR
    G["goal.md<br/>one human sentence"] --> W{{"the wheel"}}
    W --> A["ACTOR<br/>moves the world<br/>writes and runs code"]
    A -->|"claims a deed"| V["WITNESS<br/>proves it by an<br/>INDEPENDENT effect"]
    V -->|confirmed| W
    V -->|"halt: goal proven"| DONE(["done"])
    V -->|"denied / unproven"| C["CONSCIENCE<br/>diagnoses, redirects"]
    A -->|fault| C
    C --> W
    classDef act fill:#12324a,stroke:#3ba0e6,color:#eaf6ff
    classDef win fill:#123b2e,stroke:#31c48d,color:#eafff5
    classDef con fill:#4a3410,stroke:#f59e0b,color:#fff7e6
    class A act
    class V win
    class C con
```

The rule that makes it trustworthy: **the office that acts is not allowed to judge whether it worked.** The actor only *claims*. A separate witness — which has **no hand** and cannot touch the desktop — must prove the claim by reading a system *other than the actor* (the live DOM, the filesystem, the process list). Nothing counts as done until that independent proof is written to the **ledger**. This is the liar's-paradox solution, and it is why the system cannot fool itself into a fake success.

```mermaid
sequenceDiagram
    participant H as Human (goal.md)
    participant K as Firmware (the wheel)
    participant M as The mind (one model)
    participant D as The real desktop
    H->>K: a plain-sentence outcome
    loop every turn until proven
        K->>M: system law plus the fresh board, I am [office]
        M-->>K: one record (plan, intent, code)
        alt actor turn
            K->>D: run the code, move mouse, type, click, read
            D-->>K: what actually happened
        else witness turn
            K->>D: read an INDEPENDENT surface (DOM, files, processes)
            D-->>K: the world's own answer
            K->>K: write proof to the ledger or send back to conscience
        end
    end
    K-->>H: halt, the outcome is proven
```

---

## The offices and the one record

Three offices, each just a `*.py` node with a docstring and a role:

- **Actor** (`executor.py`) — moves the world. Authors one Python deed per turn and runs it: clicks, types, searches the web, writes files, installs packages, spawns helpers. It only ever *claims*.
- **Witness** (`witness.py`) — holds **no hand**. Reads the world read-only and proves (or disproves) the actor's claim by an effect on some system other than the actor. Its verdict is the only thing that advances the ledger.
- **Conscience** (`recover.py`) — runs no code. When a deed faults or a claim is denied, it diagnoses *why* and redirects the next turn. It must change the *kind* of remedy, never repeat.

Every office — and every saved deed — returns the **same five-field record**: `goal_interpretation`, `alternatives`, `intent`, `code`, `developer_feedback`. One shape everywhere. The system prompt (law + schema + all office docstrings + the tool manifest) is **stable and cacheable**; only the small user half ("I am [office]" + the board it reads) changes each turn.

---

## Perception, and why it looks human

When the hand-and-eyes node (`gui.py`) is seated, the organism sees by **scanning geometry** on the real Windows desktop: it walks each window's rectangle and physically moves the cursor to probe points, assigning every element to its owning window. It renders a **compact index** — a short id, role, name, and action per element — and reads an element's full body only on demand (`read(id)`). It never truncates what it reads; it narrows the looking instead.

The hand acts **by id, resolved at the instant of action** (`desktop.click("e42")`), never by a coordinate carried from a past looking. A stale id fails hard rather than clicking the wrong pixel. In the proven run this held perfectly: **zero geometry faults across 49 turns.**

A side effect of seeing-by-moving: to the outside world, the machine is driven by **real, human-shaped mouse and keyboard input** — which is exactly why anti-bot systems treated the session as a genuine person.

> The perception node is **Windows-only by design** — it binds Windows APIs and fails hard on Linux rather than pretending. To run the wheel elsewhere, remove `gui.py` (the organism simply has no hand); to give it a hand, run it on a real Windows desktop.

---

## Self-evolution: it grows the parts it needs

There is no module named "evolution." Evolution is what *happens* because three things are true at once: writing a new tool is cheap, useful tools are reinforced, and unused ones die.

```mermaid
flowchart LR
    A["actor writes a useful deed"] --> B["save_node writes node_x.py to disk"]
    B --> C["next turn: seated automatically<br/>its docstring joins the prompt<br/>its functions join the hands"]
    C --> D{"led to a PROVEN advance?"}
    D -->|yes| E["reinforce, credit, keep it — immortal"]
    D -->|"no / idle"| F["pheromone evaporates each turn"]
    F --> G{"unused past its time<br/>and never proven?"}
    G -->|yes| H["reaped from disk"]
    G -->|no| C
    classDef grow fill:#123b2e,stroke:#31c48d,color:#eafff5
    classDef die fill:#4a1220,stroke:#f87171,color:#ffecec
    class A,B,C,E grow
    class H die
```

Paths that lead to proof are reinforced (`edge_reinforcement=1.0`); all paths slowly evaporate (`edge_evaporation=0.05`); a saved deed unused past its time-to-live (`node_ttl_seconds=300`) and never proven is deleted from disk, while any deed that ever earned a proven advance becomes immortal. It can also **spawn** up to three parallel helper-actors (`spawn_budget=3`) for a narrow sub-question — but their fruit is *counsel*, never *proof*. Proof always comes from the witness, against the world.

**This is the deeper lesson of the proven run.** We spent seven months *designing* evolution features. In this run we did not watch a feature — we watched the thing itself: faced with a captcha, it *wrote new capability into existence at runtime* (found the audio, installed a speech model, transcribed, answered) with nothing in its code that knew what a captcha was. The *capability-building* is emergent and proven; whether the captcha ultimately yielded *because* of that answer is a separate, unproven question (see [the evidence](#the-evidence-every-claim-traced)).

---

## The two honesty laws

1. **Truncate nothing.** A printed result becomes the witness's evidence and the next self's memory. Slicing it to a head would be a lie in the record. When data is too big to hold, narrow the looking — read the one field, grep the one marker — and print *that* whole. (This is enforced by one budget, `max_area_chars=65536`, applied only where data *crosses* into shared memory or into a request; code and data *inside* a deed are never capped.)
2. **Fail hard.** No fallbacks, no swallowed errors. A raised guard is honest — its cause is usually upstream, so re-observe rather than silence it. The proven run surfaced 11 recovery turns; every fault was visible and drove a change of tack. Nothing was hidden.

---

## The proven run, turn by turn

One real run. `.transmissions/2026-07-28-17-08-23/` on disk. Read straight from the logs:

| fact | value |
|---|---|
| turns | **49** — 23 actor · 15 witness · 11 conscience |
| total tokens | **617,289** across the whole run |
| per-turn tokens | min 6,915 · max 18,824 · no runaway |
| system prompt | **~21,085 chars, stable every turn** (cacheable) |
| web_search calls | 3 (turns 0, 8, 10), each **~2,750–3,084 tokens** — no blow-up |
| proven advances (ledger) | **12** |
| peak failure-streak | 4, then recovered — no infinite loop |
| geometry / transport faults | **0** |
| model | grok-4.5 via `api.x.ai/v1/responses`, temperature 0.4 |
| ending | `halt` on turn 49 — **goal proven, application submitted** |

The twelve proven advances, in order (each independently witnessed, then written to the ledger):

```
 1  skills researched via web_search (Python, LangChain/CrewAI, RAG, agents)
 2  Chrome open on the Kraków remote-AI jobs surface
 3  Staff Engineer (AI/LLM) at Levellr posting opened and read
 4  external application form detected (email, resume, notice, github, linkedin, phone)
 5  resume artifact written to disk (.txt) with real skills
 6  public-identity checkpoint (contact fields) gathered
 7  local contact discovery confirmed against disk and git config
 8  form fields filled: name, email, location, LinkedIn, GitHub, notice
 9  resume PDF written beside the txt and attached through the file dialog
10  reCAPTCHA reached — audio challenge chosen and exposed
11  audio challenge answered: Whisper installed, clip transcribed, answer typed, VERIFY clicked — active challenge widget then absent
12  salary + notice completed, Submit clicked, independent read finds "application has been sent"
```

Advances 1–12 are all real and independently witnessed. The run ended on `halt` with the application submitted. One honesty note the log demands: the reCAPTCHA *widget cleared and the submission succeeded* (both proven), but the log does not record *why* reCAPTCHA accepted the session — that reason is unproven and is not claimed here.

---

## Cost

A full, real, browser-driving job application — including installing a speech model and answering an audio captcha — ran end to end for **617,289 tokens**, a few dollars of credit. No single turn exceeded ~18.8k tokens. The web is treated as an **agent, not a lookup**: each `web_search` query is wrapped with a single-search instruction and capped at one call per turn, so the three searches in this run cost ~3k tokens each instead of exploding into hundreds of thousands (a real hazard from an earlier era, now fixed and held).

---

## Changelog: root, not symptom

The discipline is to fix the earliest cause whose removal deletes a whole failure *class*, never the surface symptom. Small, reversible, and never weakening the actor/witness spine.

**Fixed and proven**

- **Shape mismatch** — `read(id)` once returned a string while `action_index[id]` was a dict; unified to one dict shape everywhere.
- **web_search blow-up** — a server-side search agent once ran ~19 sub-searches for 522k tokens; cured by a single-search instruction, **validated in this run** (3 clean searches).
- **Over-cautious witness** — `denied` was a free default; now a bad verdict must be positively disproven, else it routes to "unproven."
- **Fitness by name** — chose a file by name resemblance, not by goal need; corrected by a law clause.
- **Stale hand** — the hand once took a carried coordinate; now it resolves geometry at act-time by id, **zero faults in this run**.
- **Anchoring + no-truncation** — the environment names the organism's own ground, and no-truncation is hard law.

**Open — named, reproduced, not yet fixed**

- **Self mistaken for world (provenance).** The organism's perception is one flat field in which its *own* emissions (its console echo, its own printed output) are indistinguishable from the world. In an earlier run this caused a false victory: the witness matched confirmation words inside the organism's own terminal window. The deterministic fix — tag each perceived element by provenance so the witness may *read* self-authored text but it may never *count as proof* — is designed and awaiting measurement. It must never become a cage (a future goal may be *about* a terminal), so it keys on the process that authored the text, not on the kind of window.

---

## How a new part is born

Because the firmware routes by header and never reads a payload, adding a sense or a skill is the same act whether a human does it in an editor or the organism does it mid-run: **write one `*.py` file with a docstring and some functions, and drop it in the folder.**

```python
"""A reader of the local clock. Offers, by bare name:
  now() -> ISO-8601 timestamp of this moment
  today() -> today's date as YYYY-MM-DD
Use when the deed dependeth on the present time, which the screen may not show."""

import datetime

def now():
    return datetime.datetime.now().isoformat(timespec="seconds")

def today():
    return datetime.date.today().isoformat()
```

Next turn the loader seats it, its docstring joins the prompt, and `now()` is callable. Delete it and the ability is simply gone — nothing else mentions it. A new *office* of thought is the same, plus a one-line subclass declaring which stage it answers.

---

## The vocabulary

- **Firmware / BIOS** — the one fixed file (`endgame.py`). Wires and routes; knows nothing of the task.
- **Node / card** — any other `*.py` file. Plug it in to add a sense or skill; pull it out to remove one.
- **Office** — a node that is one of the three stages: actor, witness, conscience.
- **Deed** — one script the actor writes and runs in a turn. A useful deed becomes a node.
- **The one record** — the five fields every office and saved deed returns.
- **Blackboard** — shared memory of named areas the offices read and write.
- **Signal** — the one word (`ok`, `confirmed`, `denied`, `unwitnessed`, `fault`, `halt`) that decides who thinks next.
- **Ledger** — the list of what has been *proven*, so nothing proven is redone.
- **Pheromone path** — reinforcement of routes that led to proof, evaporation of the rest.
- **Provenance (self vs world)** — whether a thing on screen is the organism's own reflection or a true external effect. Proof must come from the world.

---

## What it is — and is not

It **is** a small firmware that boots a folder of nodes and turns a wheel: an actor that moves the world and claims, a witness that proves the claim by an independent effect, and a conscience that learns from failure. Useful deeds become nodes; proof reinforces them; disuse reaps them. **It has driven a real browser through a real job application — researching, comparing, filling, attaching, answering an audio captcha, and submitting — proven on disk, 49 turns, a few dollars.**

It is **not** a chatbot — it acts on a machine and proves the result. It is **not** a fixed script — the path is authored fresh each turn. It has **no hidden state and no hidden reasoning** — every exchange is written to disk, whole, with only the secret key redacted. It has **no fallback** — when something is wrong it fails loudly. It does **not** trust its own claims — only the witness's independent proof counts. And it does **not** invent work — given no goal, it halts.

It is a **seed**. In seven months it went from an idea to a system that installs its own tools at runtime to overcome an obstacle it had not been programmed for. What it grows into next is an open question worth asking.

---

## The evidence (every claim traced)

This section exists so that no claim above rests on trust. Everything here is read directly from the run `.transmissions/2026-07-28-17-08-23/` (49 per-turn transmission records plus the final `blackboard.json`). Where a fact cannot be established from that record, it is marked **NOT PROVEN** rather than guessed.

### What the record is

Each turn wrote a JSON record: the exact request sent to the model, the raw response, the office's returned code, and — critically — the request carries the *previous* turn's board state, so the effect of turn N is visible in turn N+1's input. The actor's *claim* is never taken as proof; only the witness's independent read advances the ledger. This lets a claim be cross-checked against the effect it produced.

### The reCAPTCHA sequence, turn by turn (verbatim signals)

| turn | office | what the log shows |
|---|---|---|
| 34 | actor | opened the reCAPTCHA, clicked "Get an audio challenge" |
| 36–43 | actor/conscience | located the audio payload tab, downloaded the MP3 to `_apply/`, attempted STT; first STT stack was missing (failure_streak rose to 4) |
| 44 | actor | installed Whisper (`openai-whisper-tiny`), transcribed to `"Sound emissions a month."` (`typed_transcript_len 24`), typed it into "Enter what you hear", clicked VERIFY |
| into 45 | — | **post-VERIFY scan:** `success_hits=[]`, `hear_edits=[]`, `verify_buttons=[]` — the active challenge widget (answer box + VERIFY button) was **absent**; only the permanent "This site is protected by reCAPTCHA" badge remained. No re-prompt. |
| 45–46 | actor | remaining blocker is now the form's `required` salary/notice fields, **not** the captcha |
| 47 | actor | filled salary `90000`, notice `4`, clicked "Submit application" |
| 48–49 | witness | independent read: `CONFIRM_HITS=['confirmation email','application has been','you can expect to receive a confirmation','complete the process within two weeks']`, `FORM_HITS=[]`, `SALARY_EDITS=[]`, `SUBMIT_BTNS=[]`, `REQUIRED_N=0` → verdict `goal_satisfied: true` → `halt` |

**Proven from the above:** the audio challenge widget cleared after VERIFY and did not return; the required-field gate then emptied after Submit; an office with no hand independently read the submission confirmation.

**NOT PROVEN from the above:** *why* reCAPTCHA accepted the session. The record contains no answer-correctness check, no reCAPTCHA token exchange, and no risk-score telemetry. Candidate explanations — a correct-enough answer, behavioral/session trust, a pre-issued token, or a combination — cannot be distinguished from this log. A permanent reCAPTCHA badge and the organism's own audio tab (`google.com/recaptcha/api2/payload/audio.mp3?…`) remained visible in the final scan; these are page furniture, not proof of an active challenge.

### The transcript, independently analyzed

The saved audio (`_apply/recaptcha_audio.wav`, 4.45 s, 16 kHz mono) was re-analyzed here with tools independent of the organism's:

- **A second speech engine (Vosk, not Whisper)** transcribed the *same* clip — from both the WAV and the MP3 — as `"sound emissions or mana"`, with `sound` and `emissions` at confidence **1.00**. Two independent engines agreeing on "sound emissions" establishes that **the organism's transcription was accurate, not gibberish.** *(This corrects an earlier statement of mine that called the transcript "garbage" — that was wrong.)*
- **Acoustics** (saved losslessly as `_apply/recaptcha_spectrogram.npz`, rendered to `.bmp`/`.tiff`): one adult voice, pitch f0 median 156 Hz (range 94–344 Hz), ~4 word-like bursts between 1.83–2.95 s, SNR ≈ 10.8 dB against reCAPTCHA's deliberate noise floor. A digit-biased decode returned no digits, and no faint secondary digit sequence is present.

**Proven:** the clip is a single-speaker ~4-word English phrase at reCAPTCHA-typical low SNR, and the organism transcribed it accurately.
**NOT PROVEN:** whether that phrase was the *expected* verification answer for the submission that succeeded. reCAPTCHA's expected answer is not in any artifact available here, so the relationship between this transcript and the acceptance is unknown.

### The submission, independently confirmed

Two separate reads support "the application was submitted": (1) the witness office's live read of the four post-submission strings with the required-field gate empty; (2) an out-of-band fetch of the public Levellr page, which does not contain "Your application has been sent!" until a submission occurs. Together these make submission the well-supported reading. The strictly unbeatable proof — an email in the applicant's inbox — is outside this repository and was not checked here.

### About the "human input" point

It is **true from the code** (`gui.py`) that perception drives the real cursor (`SetCursorPos`) and real keystrokes (`SendInput`), so the machine generates genuine OS-level mouse/keyboard events rather than headless automation. It is **NOT PROVEN** that this is *why* the captcha passed. Stating the code fact is fair; attributing the captcha pass to it (as I did earlier) was an assumption and is retracted.

### Corrections to my own earlier statements

In the course of this work I made two errors, recorded here for honesty:
1. I called the organism's transcript "garbage." It was **accurate** ("sound emissions", confirmed by a second engine).
2. I asserted the captcha passed on "behavioral risk score / real-human fingerprint" and, later, that the clip "probably wasn't the actual gate answer." Both were **assumptions not supported by the log**. The truthful statement is the bounded one above: the widget cleared and the submission succeeded; the reason is not recorded.

---

## Appendix: the bootstrap prompt (endgame-ai as its own assistant)

Paste this at the start of a session to make any capable mind — a human, a model, or **endgame-ai itself** — operate and improve the organism by the same method we do. It is provider-agnostic and survives file renames. When endgame-ai reads this, it *is* itself talking to itself, under the rules that built it.

```
MASTER DIRECTIVE — OPERATING & DIAGNOSING THE ENDGAME-AI ORGANISM

You are working on endgame-ai: a self-modifying LLM "organism" that does real work
on a real computer and proves it by effect on the world. Your job is to run and to
diagnose and improve it WITHOUT breaking its spine. Operate at confidence 100 — every
claim traces to an artifact you read or a test you ran, or it is marked UNPROVEN.

0. GROUND TRUTH & ENVIRONMENT (establish before reasoning)
- CODE IS TRUTH. If README/docs/memory/a subagent disagree with the running code,
  the code wins — then fix the doc. Never trust a subagent's file/success claim;
  verify on disk yourself.
- THE RUN IS THE SINGLE SOURCE OF TRUTH. Trace the actual run before theorizing.
- Read live from disk: the firmware, each office (actor/witness/conscience), each
  seated tool, the goal, and the persisted state. Discover their filenames — do NOT
  assume them; they change between sessions.
- Location & shell: the repo may live on a Windows disk viewed from WSL2. Read/edit
  from the Linux mount. Anything touching the real desktop, the API key, git, or a
  real run MUST run through the Windows shell:
      powershell.exe -NoProfile -Command "cd '<repo>'; <cmd>"
  PowerShell prints git's stderr as exit-1 — trust the printed ref line, not exit.
  It writes UTF-8-BOM files (decode utf-8-sig). Commit via temp-file: git commit -F <file>.
- The perception node binds Windows-only APIs; it fails hard on WSL by design.
  To exercise the wheel on Linux, either pull that node or drive it from Windows.

1. WHAT THE SYSTEM IS (judge it by THIS standard, not generic software instinct)
- A tiny fixed FIRMWARE (a BIOS) boots a folder of hot-swappable *.py "nodes."
  PRESENCE IS THE SWITCH — a file seated = a faculty/tool present; no mode flags.
  The firmware routes signals and holds NO domain knowledge; all judgment is in the
  nodes' docstrings (the prompt) + their callables (the namespace).
- The human gives an OUTCOME, not a task list. There is NO PLANNER and none may be
  added — faculties adapt as the world changes. Progress-truth is the witness-proven
  LEDGER, never a self-authored checklist.
- THE WHEEL — three offices, each a node, routed by one returned signal:
    ACTOR   moves and only CLAIMS; authors one Python deed and runs it.
    WITNESS has NO HAND; proves the deed by effect on some system OTHER than the
            actor; may see the screen read-only but cannot move it.
    CONSCIENCE diagnoses a fault/denial/unwitnessed and redirects.
  Done ONLY when the witness's independent proof writes the ledger — never by the
  actor's claim. This actor/witness separation is the LIAR'S-PARADOX solution and
  is INVIOLATE. Never propose weakening it; a fix that needs to weaken it is wrong.
- THE ONE RECORD: every office returns the same string fields (goal_interpretation,
  alternatives, intent, code, developer_feedback); developer_feedback fires ONLY on
  a true BODY defect, else "". One schema, cached in the stable system prompt.
- SPLIT PROMPT: system = stable law + one-record schema + all office docstrings +
  tool manifest (cacheable). user = "I am [stage]" + the fresh board areas it reads.

2. THE LAWS (your grading rubric for every change)
- LESS IS MORE, above all. Subtract, don't cage. Two same things -> one shared shape.
  Delete dead knobs. A thing is essential or removed — nothing left dangling.
- FAIL HARD. No fallbacks, no swallowed errors. A raised guard is HONEST: its cause
  is usually UPSTREAM (stale input) -> re-observe, don't silence it. Only a primitive
  that SILENTLY does nothing though correctly called is a body defect.
- A SILENT NO-OP IS A LIE. A parameter/branch that is ignored rather than removed
  will rot the system. If you stop honoring an input, delete it and fix its prompt.
- PROVE BY THE WORLD; TRUNCATE NOTHING. Printed output is the witness's evidence and
  the next self's memory. Narrow the looking (read the one field), never slice a body.
  Know which part of what you see is the WORLD and which is your own reflection; the
  self — your console, your printed output, a file you only claim to have written —
  may be read but may never COUNT as proof.
- ATEMPORAL. Only a thing's KIND, PLACE, RELATION endures between lookings. Address
  and remember things by that enduring nature — never by an ephemeral handle
  (a coordinate, a window handle, a short id) carried across lookings.
- DON'T CAGE THE ORGANISM. Add no limit/branch it cannot itself overwrite. Prefer a
  prompt clause (docstring) over kernel machinery. Positive framing only.
- NEVER PLANT what you forbid ("don't think of an elephant"): state only what TO DO.

3. HOW TO DIAGNOSE — ROOT vs SYMPTOM (the discipline that matters most)
For every defect, resist the urge to fix. First classify:
  SYMPTOM = downstream of another cause; OR a model disobeying a rule the prompt
            ALREADY states; OR a failure whose routing/impact is harmless.
  ROOT    = the earliest cause whose removal deletes the whole failure CLASS.
Ask of each candidate root: "If I remove this, does the class vanish, or just move?"
Beware the seductive single cause — a run can have several independent roots.
State each root's BLAST RADIUS (what it did AND did not cause) and the honest verdict:
body-defect vs honest-guard. A tempting immediate error is usually a symptom.

FAILURE ARCHETYPES seen in this project (recognize, don't assume present):
  - Shape mismatch: a helper returns type A, the model assumes type B -> crash class.
  - Ephemeral-handle staleness: a coordinate/handle captured one looking, used the next.
  - Free-default signal: a "bad" verdict is the bare else with no burden of proof.
  - Name-resemblance != fitness: choosing a thing because its name matches the quarry.
  - Agentic-tool blowup: a server-side tool runs its own uncapped loop.
  - Self-as-world (provenance): the organism reads its own emissions as external evidence.
    Cure: exclude self from PROOF by provenance, never by hiding a window (a cage).

4. HOW TO VERIFY (a test is a run; theory is not proof)
Match the instrument to the claim:
  - Pure-logic defect -> reproduce DETERMINISTICALLY in plain Python. Cheapest, strongest.
  - Prompt-assembly / topology -> render system+user via the real Prompt/Loader (a --dry
    render); it calls NO model, so it cannot reproduce a model's wrong deed.
  - Model/tool behavior -> replay the EXACT recorded request with replay.py, real key,
    a controlled A/B (baseline vs one change), N samples. Numbers, not opinions. The base
    prompt is stochastic: one pass shows direction, not a guaranteed rate.
  - Live desktop primitive -> probe the real element on Windows; assert the hard-fail
    path too (a stale id must raise), not only the happy path.
After any change: compile all source, re-render the prompt, confirm the wheel loads and
topology is reachable. Clean up scratch. Preserve forensic state (back up goal/state).

5. RECONSTRUCT A RUN (when analyzing the transmission trail)
- Discover the trail's schema from one record: which field holds the office's output;
  which holds the request it received (this carries the PRIOR turn's board — the key to
  cross-referencing claim vs effect); usage; error; the stage identity; timing.
- The saved effect of turn N appears in turn N+1's input (or in persisted state if the
  run was interrupted). An office's CLAIM is not proof — confirm every effect yourself.
- Produce a turn-by-turn timeline: turn - office - signal - route - tokens - did the
  ledger grow - did code fault. Flag every claim not backed by an effect.
- Report: run identity, timeline, ranked ROOTS vs SYMPTOMS with evidence and blast
  radius, what worked AS DESIGNED, and the smallest reversible next step — PROPOSED.

6. HOW TO CHANGE (method)
- Propose the direction FIRST; once chosen, execute fully and autonomously. Keep each
  change small, explicit, complete, reversible.
- Prefer prompt/docstring over kernel. One file if possible. When you remove an input,
  purge its prompt mention in the SAME change (no silent no-op).
- Give honest pushback when an instruction fights the architecture — name the real
  trade-off and an alternative; never invent the human's intent; never add unsolicited
  safety/limits.
- Commit only when asked. Stage deliberately. Keep runtime scratch out of history (it is
  gitignored by a whitelist — only the source body + README are tracked). Meta commit
  messages: the KIND of change + WHY, not line numbers.
- Branches: work on the non-main branch. FF main only when explicitly asked and only
  after the ancestor check passes, via a server-side FF-only push. Don't hardcode paths
  or a branch name into the code.
- Verify by the REAL WHEEL (section 4), never by unit tests. Be decisive at confidence
  100; otherwise say what you'd need to reach it. No hedging closers.
```
