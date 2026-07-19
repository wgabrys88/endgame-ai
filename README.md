# endgame-ai

A stateless, atemporal, **task-agnostic** self-modifying LLM organism that drives a real Windows 11 desktop the way a human operator would: it beholds the screen, moves mouse and keyboard, runs commands, and can author code that rewrites its own body.

It is not a program that runs one task and stops. It is a kernel turning a wheel of wired nodes, whose single wiring document (`wiring.json`) is the entire definition of the organism. A goal is supplied from outside in one plain-language sentence and pursued through one repeating motion. No task is baked into the body — not web work, not file editing, not self-improvement. Every faculty, prompt, and edge stays general; the goal is read afresh each life.

**The narration is the memory.** The organism keeps no state between wakings. Each atemporal, stateless API call tells the next what was learned through a small "living word" of rows — and nothing else crosses the gap. It has no MCP, no skills, no RAG, no vector store. It edits a real LinkedIn profile, or any GUI/terminal task, using only a language model authoring Python against a UI-Automation view of the screen. The deliberately biblical (KJV) prose in its prompts is a steering technique, not ornament: commandment register pulls the model out of the chatty, confabulation-prone assistant basin into a high-fidelity, low-variance region.

## How it works

### The wheel (topology)

`node_observe` is one module instanced three ways (`:act` / `:verify` / `:recover`), run afresh before each thinking faculty so none reasons on a stale view. `node_probe` beholds the host (not the screen) between the act-observation and the executor.

```
node_guidance       --attend-->         node_observe:act
node_observe:act    --observed-->       node_probe
node_probe          --probed-->         node_execute
node_execute        --done-->           node_observe:verify
node_execute        --deed_denied-->    node_observe:recover
node_observe:verify --observed-->       node_verify
node_observe:recover --observed-->      node_recover
node_recover        --recovered-->      node_guidance
node_verify         --deed_confirmed--> node_guidance
node_verify         --deed_denied-->    node_observe:recover
node_verify         --unwitnessed-->    node_observe:verify
node_verify         --halt-->           (life ends)
```

Prompts are built dynamically from the wiring plus the topology: a node's downstream consumers are read from its edges and their module docstrings injected as a DOWNSTREAM CONTRACT. The model-facing text is `shared_prompt_prefix + node prompt + downstream_contract` (the static system message), then a volatile per-turn tail (observation brief, proven ledger, goal-interpretation table, and the standing host facts) as the user message.

### The faculties

- **guidance** — reads the living word and root goal, sets the guiding intent for the lap.
- **observe** (act/verify/recover) — pure Python, no model call: calls `desktop.observe()` and emits the fresh desktop tree. Blind and fast by design.
- **probe** — pure Python, no model call: beholds the host — platform, screen, shell tools, open windows, installed apps — and lays them at the tail of the executor's message so the actor builds on what stands.
- **execute** — the actor. From the living word, the fresh observation, the standing host, and any recovery frame, it authors **one Python script** and enacts it. The language is the only tool; there is no tool menu. A script that raises routes to recovery — it never kills the life.
- **verify** — the witness. Authors **read-only** code proving a system *other* than the actor produced the effect. Judges by independent effect, never the actor's testimony.
- **recover** — on a denied deed, distils the lesson and frames the next attempt, commanding a change in the *kind* of road, never a retry of the failed one.

### The laws

- **Task-agnostic.** No task is baked into any faculty, prompt, or edge.
- **Code-as-action.** The executor authors and runs Python; the language is the only tool. Actions chain within one script only behind deterministic self-checks of environment state — one deed carries the world to a single point of uncertainty, then ceases.
- **Independent witness.** A value the actor computed, printed, read back, or wrote to a file is testimony, not proof. No verdict rests on it.
- **Living word of proven effects only.** A confirmed deed deposits a proven-done fact (written by the witness, never the actor) into a channel every faculty reads, so the amnesiac organism does not redo what already stands.
- **Hot-swappable body.** Every node and the topology itself are ordinary Python/JSON files. The organism is invited to edit them when the true fault lies in its own code — mend a node whose name deceives its effect, rewrite the wiring, author a new faculty (memory or otherwise) when it proves needed, and commit that DNA change. There are no limits placed that the organism cannot itself rewrite. **Never cage it.**

### Perception — one rule

Observation is a single rule: enumerate the top-level windows (their rectangles are ground truth), then for **each** window probe its own rectangle and keep only the elements whose OS owner is *that* window. A pixel where a nearer window lies answers with the nearer window's element, whose owner fails the test and is dropped — so what survives per window is exactly its **visible, reachable face**, and the click-point is proven by the very probe that found it.

Everything else falls out for free: z-order needs no computation (front-to-back is the enumeration order); occlusion is not a computed concept (a covered element is simply never collected); a covered window contributes nothing while a visible one contributes its face. The window enumeration is deliberately loose (no title filter) so context menus, dropdowns, tooltips, system dialogs, and the taskbar are all seen.

The model reads a shallow tree — one line per interactive element (short id, role, name, and state tags), with **no pixel coordinates in the text** (the body reads coordinates from an in-memory index by short id). Elements deepen on demand via `expand()`, a fresh independent look that harvests a subtree whole. Only `desktop_tree_text` and a sparse focused-element map ever reach the model; the full action index stays Python-side.

## Repository shape

- `core_organism.py` — the kernel that turns the wheel.
- `core_wiring.py` / `wiring.json` — the single source of truth: nodes, edges, prompts, contracts, model and observe config.
- `core_brain.py`, `core_bus.py`, `core_node_base.py`, `core_nodes.py`, `core_loader.py` — prompt assembly, the inter-node channel, the capability namespace, loading.
- `core_observation.py` — the single-rule perception (window enumeration + per-window scan + tree render + `expand`) and the reusable UI-Automation extractor.
- `core_desktop.py` — the hand: `click`, `type_text` (real Unicode keystrokes), `paste_clipboard`, `press_key`, `hotkey`, `scroll`, `open_url`, `observe`, `expand`.
- `node_*.py` — the faculties (guidance, observe, probe, execute, verify, recover).
- `transport_xai.py` — the model transport.
- `check_topology.py` — offline coherence gate.
- `tools_parse_requests.py`, `tools_probe_observation.py`, `tools_replay_grok.py` — non-core instruments (may use third-party deps) for log analysis, live observation testing against the real pipeline, and replay.

## Running

The organism runs on Windows 11 (UI Automation is Windows-only). Editing is done from a WSL2 mount; anything touching the real desktop or git runs through the host Windows shell.

```
python core_organism.py "<one-sentence goal>"
```

Offline coherence gates (necessary, never sufficient — behavioural truth lives only on the real desktop):

```
python -c "import ast,glob;[ast.parse(open(f).read()) for f in glob.glob('*.py')]"
python -c "import core_wiring as w; w.load_wiring()"
python check_topology.py
```

## Design philosophy

Prefer removing a defect to adding machinery — a thing is essential or it is removed completely. Keep changes small, explicit, reversible. Add no unsolicited safety. The system's own defects are the substrate of its emergent behaviour: a fault the organism can itself observe and rewrite is a feature of the self-modifying design, so defects are made **visible and auditable** rather than hidden. The body trends toward fewer, more general laws — never a new commandment per stumble.

The most recent landmark: perception was rebuilt from zero onto the single window-first rule above, deleting three files and an entire class of machinery (separate hit-point resolution, occlusion detection, z-order sorting, window reconstruction, and a thicket of tuning knobs) while making the observation faster, leaner, and truer — the taskbar and previously-lost windows now appear, and occlusion ceased to be a concept because covered elements are simply never collected.
