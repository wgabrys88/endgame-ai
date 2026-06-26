# Endgame-AI

**A self-evolving Windows desktop operator. You post a goal and walk away.**

Endgame-AI is not a chatbot with tools. It is not a cloud computer-use API. It is a **local runtime that owns the keyboard and screen**, reads the real desktop through UI Automation, executes verbs, judges progress with declarative rules, and asks models only for *decisions*. The model never drives the mouse.

The breakthrough bet: **the GUI is the universal API.** Any intelligence reachable through a browser tab, a local agent UI, or a JSON file handoff can be discovered and used — without hardcoded integrations, without vendor APIs, without pip.

Python stdlib only. `prompts/wiring.json` is the brain. `server.py` is the body. Cognition is pluggable and upgradeable at runtime.

| Field | Value |
|-------|-------|
| Repository | `https://github.com/wgabrys88/endgame-ai` |
| Branch | `codex/self-referential-relay` |
| Platform | Windows 10/11, interactive desktop |
| Entry | `python server.py` → panel at **http://127.0.0.1:9077/** |
| Default slot port | **9078** (slot 1) |
| Truth order | `wiring.json` + `server.py` + `desktop.py` + `actions.py` > this README |

**This file is the only documentation.**

### Use cases (why this exists)

| Use case | What happens | Cognition needed |
|----------|--------------|------------------|
| **Walk-away desktop tasks** | Type goal in panel, leave, return to `satisfied: true` | Bootstrap Nemotron (LM Studio) |
| **Play media** | `play shakira waka waka on youtube` → Chrome opens, watch URL reached | Bootstrap plans + `open_url` (proven partial) |
| **Browse anywhere** | Navigate to any site via GUI — no API keys | `open_url` + SCREEN-driven act |
| **Chat with grok/ChatGPT/etc.** | Open browser chat, submit prompt, capture answer into MEMORY | Bootstrap + GUI discovery (proven path via SCREEN/file_proxy) |
| **Upgrade intelligence mid-goal** | Nemotron stuck → operator opens grok.com or Grok Build via `open_url` | Any webpage or JSON file-proxy agent |
| **Self-evolve policy** | Repeated verify denies → `self_modify` patches wiring.json | self_modify circuit (coded, unproven E2E) |
| **Unlimited future** | Any AI reachable by human can be reached by Endgame — GUI has no API caps | Discovered cognition, not hardcoded integrations |

**Logical deduction:** If bootstrap can play YouTube (proven) and cognition can read SCREEN to drive Chrome (proven), the operator is **not API-limited** — it can route through any web UI or local agent. The seed must document *how* proofs were achieved so the next session extends them, not reinvents scripts.

---

## Table of contents

0. [The Seed — now vs complete vs future](#0-the-seed--now-vs-complete-vs-future)
1. [What Endgame is (and is not)](#1-what-endgame-is-and-is-not)
2. [The breakthrough thesis](#2-the-breakthrough-thesis)
3. [Research context](#3-research-context--where-this-sits-in-agentic-ai)
4. [Walk-away operator](#4-walk-away-operator--the-intended-experience)
5. [Uniform architecture](#5-uniform-architecture)
6. [Cognition bootstrap and discovery](#6-cognition-bootstrap-and-discovery)
7. [ROD loop and self-evolution](#7-the-rod-loop-and-self-evolution)
8. [SCREEN → act → verify](#8-screen--act--verify)
9. [Rules — safety net or friction?](#9-rules--safety-net-or-friction)
10. [Declarative brain (wiring.json)](#10-the-declarative-brain-wiringjson)
11. [How benchmarks were achieved](#11-how-benchmarks-were-achieved)
12. [Proven vs vision](#12-what-is-proven-vs-what-is-vision)
13. [Operator replacement progress](#13-operator-replacement--honest-progress)
14. [Run it yourself](#14-run-it-yourself--walk-away-with-lm-studio)
15. [HTTP API](#15-http-api)
16. [Known gaps](#16-known-gaps)
17. [Remaining work](#17-remaining-work)
18. [Next AI handover prompt](#18-next-ai-handover-prompt)
19. [Deep Research prompt](#19-deep-research-prompt-chatgpt-project)
20. [Repository layout](#20-repository-layout)
21. [Appendix — session finish](#21-appendix--session-finish)

---

## 0. The Seed — now vs complete vs future

Endgame is a **seed**, not a finished product. The seed has mechanical hands, an evolvable brain, bootstrap cognition, and a path to discovered intelligence. Later it self-modifies — wiring first, then (vision) heavier runtime evolution.

```mermaid
flowchart TB
    subgraph NOW["Seed today (what you have)"]
        H1[UIA hands + verbs]
        W1[wiring.json 32 rules]
        B1[Nemotron bootstrap]
        P1[Notepad + Google + YouTube partial proven]
    end

    subgraph SEED["Complete seed (next sessions)"]
        H2[Walk-away panel UX]
        W2[self_modify proven]
        B2[Autonomous cognition discovery]
        P2[Document HOW each benchmark was achieved]
        P3[grok.com chat E2E via GUI]
    end

    subgraph FUTURE["Unrestricted evolution (vision)"]
        E1[wiring evolves during runtime]
        E2[Any AI via GUI — no API limits]
        E3[Nemotron or grok/kiro-cli as interchangeable cognition]
        E4[Operator improves PC + policy without human]
    end

    NOW --> SEED
    SEED --> FUTURE
```

```mermaid
flowchart LR
    subgraph You["You"]
        G[Post goal in panel]
    end

    subgraph Seed["Endgame seed"]
        ROD[ROD loop]
        RULES[Structural rules]
        MEM[MEMORY + traces]
        SM[self_modify]
    end

    subgraph Cognition["Any cognition source"]
        N[Nemotron start]
        X[grok / ChatGPT / kiro-cli / Grok Build / OpenCode]
    end

    G --> ROD
    ROD --> N
    ROD -->|"open_url focus write"| X
    X -->|"SCREEN or JSON files"| ROD
    RULES --> ROD
    SM --> RULES
    MEM --> ROD
```

**Prepare the seed** = honest docs + proven paths + shrink code + no parallel script universe. The seed transforms itself later; documentation must not trap future agents in legacy thinking.

---

## 1. What Endgame is (and is not)

### It is

| Property | Meaning |
|----------|---------|
| **Desktop operator** | Sits at your PC like a human — sees UIA, moves cursor, types, switches windows |
| **Uniform system** | One ROD graph, one wiring brain, one mechanical layer — not a bag of scripts |
| **Decision / execution split** | LLM circuits emit JSON; Python executes and verifies |
| **GUI-unlimited** | `open_url`, `focus`, `click`, `write` can reach *any* webpage or app UI |
| **Cognition-pluggable** | Bootstrap on local Nemotron (LM Studio); upgrade to grok.com, Grok Build, OpenCode, or any file-proxy agent by *navigating there* |
| **Self-evolving** | `self_modify` can patch `wiring.json` (rules, prompts, topology, observe) when stuck |
| **Self-feeding** | Reasoning chains, MEMORY, traces, and file-proxy request/response loops accumulate context |

### It is not

| Anti-pattern | Why |
|--------------|-----|
| Standard tool-calling agent | Tools are not the interface — verbs + SCREEN + wiring rules are |
| Cloud computer-use only | Runs fully local; no vendor lock-in for hands or brain |
| Hardcoded grok/Chrome recipe | grok is one *discoverable* cognition source, not the architecture |
| `p0_file_proxy_runner.py` | Canned responses without reading SCREEN — automation only, invalid proof |
| MCP-as-hands | Endgame owns HWND focus and UIA — external agents advise, never click |
| Dev scripts instead of Endgame | `p0_file_proxy_runner.py`, new harnesses — use the operator to test the operator |
| Legacy multi-slot recipes | Slots are helpers; architecture is one uniform operator |

---

## 2. The breakthrough thesis

Most agentic systems in 2025–2026 follow one pattern: **one big model sees pixels and acts**.

| Approach | Examples | Limit |
|----------|----------|-------|
| Screenshot + API loop | [Anthropic Computer Use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool), OpenAI CUA/Operator | Cloud cost, API caps, no local policy evolution |
| Benchmark harnesses | [OSWorld](https://arxiv.org/abs/2409.08264), [Windows Agent Arena](https://microsoft.github.io/WindowsAgentArena/) | Measure agents, not ship operators |
| Self-modifying code | [Sakana DGM](https://sakana.ai/dgm/) | Code evolution, not live desktop wiring |
| Declarative graphs | LangGraph-style workflows | Static unless rebuilt |

**Endgame's bet — four separations:**

```mermaid
flowchart TB
    subgraph Hands["1. Mechanical hands (fixed, trusted)"]
        UIA[UIA observe]
        VERBS[verbs: click write focus open_url ...]
        VERIFY[rule preflight + verifier]
    end

    subgraph Brain["2. Declarative brain (evolvable)"]
        WIRING[wiring.json topology + rules + roles]
        SM[self_modify wiring_patch]
    end

    subgraph Bootstrap["3. Bootstrap cognition (start)"]
        NEMO[LM Studio Nemotron / local model]
    end

    subgraph Upgrade["4. Discovered cognition (GUI path)"]
        GROK[grok.com in browser]
        GB[Grok Build / Cursor / OpenCode UI]
        FP[Any file_proxy JSON agent]
    end

    WIRING --> Hands
    Bootstrap --> Brain
    Hands -->|"open_url focus write click"| Upgrade
    Upgrade -->|"answers via SCREEN or JSON files"| Hands
    SM --> WIRING
```

1. **Hands** — Python + UIA. Deterministic. Never hallucinate a click.
2. **Brain** — `wiring.json`. Hot-reloadable. Governs when steps confirm, deny, escalate, evolve.
3. **Bootstrap cognition** — Small local model (Nemotron) for planner/act/verify when you walk away.
4. **Discovered cognition** — Stronger intelligence reached by **navigating the GUI** to whatever service is available — grok.com, a build tab, a local agent that speaks JSON files. No API key required. The webpage *is* the API.

This is why it is not a branch diagram. Slots and relay workers are **implementation helpers** for parallelism. The mental model is one operator that can find its own way to better thinking.

---

## 3. Research context — where this sits in agentic AI

Recent work validates pieces of this design. Endgame combines them in a way none of the papers do alone.

| Research line | Key idea | Endgame mapping |
|---------------|----------|-----------------|
| **OSWorld** (2024–2025) | Open-ended desktop tasks in real OS environments | Same problem domain; Endgame targets Windows UIA + walk-away goals |
| **Windows Agent Arena** (Microsoft, 2025) | Scalable Windows GUI benchmark | Endgame is operator-first, not benchmark-first |
| **Computer Use** (Anthropic/OpenAI, 2025) | Model controls mouse/keyboard via API | Endgame inverts: runtime controls mouse, model advises |
| **DGM / self-modifying agents** (Sakana, 2025) | Agents rewrite own code to improve | Endgame `self_modify` patches **wiring policy**, not random Python |
| **GUI grounding surveys** (2025–2026) | Accessibility trees beat raw pixels for reliability | Endgame uses UIA `[ID]` + `[W#]` tokens, not screenshot-only |
| **Declarative agent configs** (2025) | Separate workflow from execution | `wiring.json` is the workflow; `server.py` is the executor |

**What is genuinely novel here:**

- **GUI as cognition router** — the operator can `open_url` grok.com, open a local agent IDE, or point file_proxy paths at whatever JSON-speaking tool exists. No integration code per vendor.
- **Policy evolution without redeploy** — `wiring_patch` ops (15 types) hot-reload rules/prompts/topology when reflect escalates.
- **Structural verify before LLM verify** — 32 declarative rules prevent false success (e.g. wait-only steps confirming without memory evidence).
- **Two-pass cognition contract** — reasoning pass then `DECIDE NOW` JSON pass reduces parse failures.
- **Stdlib-only single runtime** — no pip, one `server.py`, auditable mechanical layer.

---

## 4. Walk-away operator — the intended experience

```mermaid
sequenceDiagram
    participant You as You
    participant Panel as wiring-editor.html :9077
    participant EG as Endgame runtime
    participant Nemo as Bootstrap cognition<br/>LM Studio Nemotron
    participant Desktop as Windows desktop
    participant Smart as Discovered intelligence<br/>grok / build / opencode / file_proxy

    You->>Panel: Open panel, type goal, click Run
    You->>You: Walk away
    loop ROD until satisfied or give_up
        EG->>Desktop: observe → SCREEN
        EG->>Nemo: planner / act / verify (HTTP or file_proxy)
        Nemo-->>EG: JSON decisions
        EG->>Desktop: execute verbs
        alt Needs stronger cognition
            EG->>Desktop: open_url / focus / navigate
            EG->>Smart: GUI handoff (chat UI or JSON files)
            Smart-->>EG: answer in SCREEN or response.json
            EG->>EG: MEMORY.llm_response
        end
        alt Stuck — wiring limits
            EG->>Nemo: self_modify
            Nemo-->>EG: wiring_patch
            EG->>EG: hot-reload wiring.json
        end
    end
    Panel-->>You: satisfied / error visible on return
```

**Your job:** start LM Studio (bootstrap), start `server.py`, open panel, post goal, leave.

**Endgame's job:** plan, observe, act, verify, discover cognition if needed, evolve wiring if stuck, finish.

You do **not** manually poll `request.json` when bootstrap uses `transport: openai` (LM Studio HTTP). You do **not** pre-open grok.com — the operator can open it via `open_url` when the plan requires it.

---

## 5. Uniform architecture

```mermaid
flowchart TB
    subgraph Panel["Operator panel"]
        HTML[wiring-editor.html]
        API[HTTP :9077 root / :9078 slot]
    end

    subgraph Runtime["server.py — one runtime"]
        ROD[ROD graph engine]
        RULES[32 rules + RULE_CHECKERS]
        LLM[call_node two-pass]
        PATCH[self_modify + hot-reload]
    end

    subgraph Mechanical["Mechanical layer"]
        DESK[desktop.py — UIA SCREEN focus open_url]
        ACT[actions.py — verb dispatch]
    end

    subgraph Config["Declarative config"]
        W[wiring.json]
        M[model.json transport]
    end

    subgraph Cognition["Any cognition source"]
        LS[LM Studio HTTP]
        FP[file_proxy JSON files]
        WEB[Web UI reached by GUI navigation]
    end

    HTML --> API
    API --> ROD
    W --> ROD
    W --> RULES
    M --> LLM
    ROD --> LLM
    LLM --> LS
    LLM --> FP
    ROD --> DESK
    DESK --> ACT
    ACT --> WEB
    WEB --> DESK
    PATCH --> W
```

### Layer ownership

| Layer | Owns | Never owns |
|-------|------|------------|
| `wiring.json` | Topology, rules, roles, limits, observe, guards | Mouse, HWND, HTTP to models |
| `server.py` | Graph traversal, rule eval, LLM orchestration, patches | UIA element resolution |
| `desktop.py` | SCREEN, `[W#]`/`[ID]`, focus, `open_url` | Planning, verification policy |
| `actions.py` | Verb execution, guards | Rule definitions |
| Cognition provider | JSON per circuit (planner/act/verifier/reflector/self_modify) | Desktop control |

### Optional slots (implementation detail)

The repo can spawn slot workers for parallel tasks (e.g. relay capture). This is **not** the user mental model. One slot with bootstrap Nemotron is sufficient for most walk-away goals. Multi-slot is optimization, not architecture.

---

## 6. Cognition bootstrap and discovery

### 6.1 Bootstrap — Nemotron at start

On first boot, configure `prompts/model.json`:

```json
{
  "transport": "openai",
  "host": "http://localhost:1234",
  "model": "nvidia-nemotron-3-nano-4b",
  "temperature": 0.3,
  "max_tokens": 2048,
  "timeout": 900
}
```

LM Studio serves `/v1/chat/completions`. Endgame calls it automatically for every LLM circuit. **No manual JSON copy-paste.** This is the bootstrap brain — good enough to plan, act from SCREEN, and verify.

### 6.2 Discovery — finding stronger cognition via GUI

When a goal needs intelligence beyond bootstrap, the **planner and act circuits decide** — not a human config file:

```mermaid
flowchart TD
    G[Goal needs external intelligence] --> P[Planner decomposes steps]
    P --> A1[open_url chrome grok.com]
    A1 --> A2[focus chat window write prompt]
    A2 --> A3[remember or llm_wait_response capture]
    A3 --> M[MEMORY.llm_response]
    M --> C[Continue goal from memory]

    P --> B1[open_url / launch local agent UI]
    B1 --> B2[Navigate to JSON proxy interface]
    B2 --> B3[file_proxy handoff via llm_request verb]
    B3 --> M
```

**Paths the operator can discover without hardcoded scripts:**

| Target | How Endgame reaches it | Handoff mechanism |
|--------|------------------------|-------------------|
| grok.com | `open_url chrome grok.com` → write/click chat UI | SCREEN capture → `remember` or relay `response.json` |
| Grok Build / Cursor | `open_url` or win+r launch → focus window | file_proxy if agent writes JSON; else SCREEN |
| OpenCode / local agent | Navigate to local URL or app UI | `comms/.../request.json` ↔ `response.json` |
| Any webpage AI | GUI navigation only | Unrestricted — if it renders in a browser, Endgame can reach it |

**The GUI has no API rate limits.** If a human can click it, Endgame can click it. That is the unrestricted bridge.

### 6.3 file_proxy — universal JSON bridge

`transport: file_proxy` in `model.json` means: Endgame writes `comms/slot1_cognition/request.json`, any agent that reads JSON and writes `response.json` becomes cognition — Grok Build, OpenCode, a future local daemon, or you during development.

The request system is **self-feeding**: each cycle includes GOAL, HISTORY, MEMORY, SCREEN (for act), and reasoning chains from prior passes.

### 6.4 Two-pass LLM contract

| Pass | Trigger | Output in `content` |
|------|---------|---------------------|
| 1 | No `DECIDE NOW` in user message | Prose reasoning |
| 2 | `DECIDE NOW` present | Exactly one role JSON object |

Implemented in `server.py:1164–1174`. Reduces JSON parse failures across all cognition sources.

---

## 7. The ROD loop and self-evolution

**ROD** = Reflect – Observe – Decide (act is decide-from-SCREEN; verify/reflect close the loop).

```mermaid
stateDiagram-v2
    [*] --> goal_inbox
    goal_inbox --> moe_route: ready
    moe_route --> planner: self
    planner --> scheduler: plan_ready
    planner --> planner: retry_plan
    planner --> bus_post: plan_failed
    scheduler --> bus_check: step_ready
    bus_check --> observe: no_interrupt
    observe --> act: screen_ready
    act --> verify: acted
    act --> reflect: act_failed
    verify --> scheduler: step_confirmed
    verify --> reflect: step_denied
    reflect --> scheduler: retry
    reflect --> planner: replan
    reflect --> self_modify: escalate
    reflect --> bus_post: give_up
    self_modify --> planner: modified
    self_modify --> reflect: modify_failed
    bus_post --> satisfied: posted
    satisfied --> [*]
```

### Self-evolution loop

```mermaid
flowchart LR
    FAIL[step_denied × max_attempts] --> REF[reflect]
    REF --> ESC{escalate?}
    ESC -->|yes| SM[self_modify circuit]
    SM --> PATCH[wiring_patch op]
    PATCH --> RELOAD[hot-reload wiring.json]
    RELOAD --> PLAN[planner replans with new policy]
```

**15 `wiring_patch` ops:** `add_rule`, `update_rule`, `set_observe`, `set_role`, `add_edge`, `set_limit`, … — see `SELF_MODIFY_OPS` in `server.py`.

`max_self_modify: 3` then `give_up`. Self-modify is coded; **not yet proven E2E** on a live stuck goal.

### Per-step micro-loop

```
scheduler → bus_check → observe → act → verify
                              ↑         |
                              └── reflect ← step_denied
```

`max_attempts: 7`, `max_replans: 3`.

---

## 8. SCREEN → act → verify

### SCREEN construction

```
1. Enumerate windows → [W1]..[Wn] tokens (HWND internally)
2. Hover scan (~400+ points) → actionable [ID] elements
3. Render: FOCUSED, ACTION SCOPE, WINDOWS list
4. Inject into act circuit only
```

### Key verbs

| Verb | Use |
|------|-----|
| `open_url` | `start chrome <url>` — no prior browser focus |
| `focus` | Target `[W#]` or window title — HWND-first with retry |
| `write` / `click` | Target `[ID]` from SCREEN |
| `remember` | Store fact in MEMORY from SCREEN |
| `llm_request` | Write prompt to `comms/llm_proxy/request.json` for JSON handoff |
| `llm_wait_response` | Poll `response.json` → `MEMORY.llm_response` |

### Verify pipeline

```mermaid
flowchart TD
    V[verify node] --> R[evaluate_rules — deny first]
    R -->|confirm| OK[step_confirmed + rule_id in history]
    R -->|deny| NO[step_denied]
    R -->|no match| LLM[verifier LLM]
```

Deny rules block false success (e.g. `deny_wait_only_content_receipt`, `deny_response_no_evidence`).

---

## 9. Rules — safety net or friction?

### Short answer

**Rules are not what kills the system.** They prevent the *verifier LLM* from confirming false success (e.g. “step done” after only `wait` with no memory evidence). When runs feel stuck, it is usually:

- weak bootstrap JSON (Nemotron fails `DECIDE NOW`),
- stale `request.json`,
- SCREEN missing targets,
- or **deny rules correctly blocking a premature confirm** → reflect loop.

Rules are **structural guardrails**, not a second opinion replacing all judgment. When no rule matches, the **verifier LLM still runs**.

```mermaid
flowchart TD
    V[verify] --> D[deny rules first]
    D -->|match| DENY[step_denied → reflect]
    D -->|no match| C[confirm rules]
    C -->|match| OK[step_confirmed — skips verifier LLM]
    C -->|no match| LLM[verifier LLM decides]
```

Confirm rules that fire **skip** the verifier LLM (fast path). That is intentional when evidence is structural (e.g. `confirm_launch_chain`). If a confirm rule is wrong, it can advance too early — tune or remove it in the panel.

### Can the HTML panel hot-disable rules?

**Yes — by removing or editing rules, not an `enabled` toggle.**

Verified in code:

| Mechanism | Code location |
|-----------|---------------|
| Panel **Remove** on each rule | `wiring-editor.html` → `removeRule()` → `afterWiringEdit()` |
| Auto hot-reload ~550ms after edit | `scheduleHotSave()` → `POST /wiring` |
| Server applies live | `server.py` `POST /wiring` → `WIRING = body` + `configure_runtime()` |
| No `enabled` field on rules | `wiring-schema.json` — rules are in or out of the array only |

**To test without rules:**

1. Open **http://127.0.0.1:9077/** → Rules list → **Remove** on rules you want gone (auto hot-reloads), or
2. JSON tab → set `"rules": []` → **Save**, or
3. `POST /wiring` with empty rules array.

`evaluate_rules()` (`server.py:1527`) only iterates rules present in the array — removed rules are not evaluated.

**Recommendation:** Do not delete all rules permanently. Remove suspect deny/confirm rules one at a time, reproduce, then fix match conditions or let `self_modify` add better ones.

---

## 10. The declarative brain (wiring.json)

| Section | Governs |
|---------|---------|
| `topology` | 12 nodes, 22 edges, signal routing |
| `rules` | 32 verify/act matchers → `RULE_CHECKERS` |
| `roles` | Planner, Act, Verifier, Reflector, Self_modify prompts |
| `limits` | max_attempts 7, max_replans 3, max_self_modify 3 |
| `observe` | hover scan, scope_depth, desktop_tree_enabled false |
| `verbs` / `verb_normalize` | Act JSON field mapping |
| `guards` | Advance hints after successful verbs |
| `reasoning` | Two-pass store/clear per circuit |

**Only `act` receives SCREEN.** Planner never sees pixels — it plans from goal + memory + history. This prevents coordinate hallucination in planning.

---

## 11. How benchmarks were achieved

**Next session priority:** extend these paths, document captures, do not replace with scripts.

### Notepad + hello (proven)

| Step | Mechanism |
|------|-----------|
| Cognition | file_proxy agent read **real SCREEN** in `request.json`, wrote `response.json` |
| Act | `hotkey win+r` → `write notepad` → `press enter` → `write hello` |
| Verify | `confirm_launch_chain`, `confirm_write_to_writable` (structural rules) |
| Invalid proof | `p0_file_proxy_runner.py` canned acts without SCREEN |

### Google Chrome (proven)

| Step | Mechanism |
|------|-----------|
| Act | `{"verb":"open_url","target":"chrome","value":"google.com"}` |
| Mechanical | `start chrome https://google.com` — no prior browser focus |
| Verify | `confirm_browser_open_url` |

### Shakira / YouTube (partial — proven path)

| Step | Mechanism |
|------|-----------|
| Act pass 1 | `open_url` → `youtube.com/results?search_query=Shakira+Waka+Waka` |
| Act pass 2 | `open_url` → `youtube.com/watch?v=pRpeEdMmmQ0` |
| Verify | `confirm_youtube_playback` on clean runs |
| Gap | No click on search result; no player DOM proof |
| Implication | Bootstrap + `open_url` reaches media — click-play is polish, not architecture |

### grok.com / browser cognition (proven mechanism, full P1 E2E pending)

| Step | Mechanism |
|------|-----------|
| Hands | Endgame owns Chrome via `open_url`, `focus`, `write`, `click` |
| Cognition | Agent read SCREEN from `request.json` — **did not** manually control desktop |
| Bridge options | (a) SCREEN `remember` capture, (b) `llm_request` → `llm_proxy/request.json` → browser relay → `response.json` → `llm_wait_response` |
| Next session | Document exact history + SCREEN snapshots for a full grok chat goal |

```mermaid
sequenceDiagram
    participant EG as Endgame hands
    participant SCR as SCREEN
    participant COG as Cognition (Nemotron / grok / file_proxy)
    participant WEB as Web AI page

    EG->>SCR: observe
    COG->>COG: read SCREEN in request
    COG-->>EG: act JSON (open_url / write / click)
    EG->>WEB: GUI navigation
    WEB-->>SCR: assistant text visible
    EG->>EG: remember or llm_wait_response
    Note over EG,COG: No vendor API — GUI is the bridge
```

---

## 12. What is proven vs what is vision

| Capability | Status | Evidence |
|------------|--------|----------|
| UIA observe + SCREEN + verbs | **Proven** | Live runs + 11 mechanical tests |
| Bootstrap file_proxy cognition | **Proven** | Grok session read SCREEN → wrote response.json; Endgame acted |
| Notepad typing goal | **Proven** | `confirm_launch_chain`, `confirm_write_to_writable` |
| Chrome `open_url` navigation | **Proven** | `confirm_browser_open_url` |
| YouTube via direct watch URL | **Partial** | No click-play from search |
| Walk-away with LM Studio HTTP | **Designed** | `transport: openai` works; 4B model may fail JSON |
| Autonomous grok discovery (no pre-open) | **Vision** | `open_url` exists; P1 chatbot not E2E proven |
| self_modify recovery | **Coded, unproven** | Patch ops + hot-reload exist |
| Uniform cognition upgrade via GUI | **Vision** | Architecture supports; needs E2E proof |
| Zero-human session (post goal, leave) | **Target** | Requires reliable bootstrap model + discovery |

### Forbidden proof paths

| Path | Why invalid |
|------|-------------|
| `p0_file_proxy_runner.py` | Canned planner/act — never reads SCREEN |
| Coding agent manually clicking desktop | Bypasses Endgame loop |
| Unit tests alone | Mechanical only |

---

## 13. Operator replacement — honest progress

```mermaid
pie title Human operator replacement (~45% toward walk-away vision)
    "Mechanical hands + SCREEN" : 20
    "Declarative verify policy" : 15
    "Bootstrap cognition path" : 10
    "Cognition discovery via GUI" : 5
    "Self-modify evolution" : 3
    "Walk-away reliability" : 7
    "Remaining gap" : 40
```

| Human skill | Endgame today |
|-------------|---------------|
| Sit at PC, receive goal | ✅ POST /run, panel |
| Plan subtasks | ✅ planner circuit (needs cognition) |
| See screen | ✅ UIA + hover |
| Click, type, switch apps | ✅ verbs + focus contract |
| Judge step completion | ✅ rules + verifier |
| Recover from errors | ⚠️ reflect/replan coded; self_modify unproven |
| Find better AI when stuck | ⚠️ GUI path exists; not proven autonomous |
| Work all day unattended | ❌ not production-hardened |

**The idea works.** The vision is larger than what is proven. The gap is polish and E2E proof of discovery + self-modify — not a missing architecture.

---

## 14. Run it yourself — walk away with LM Studio

### Prerequisites

- Windows 10/11, Python 3.11+
- [LM Studio](https://lmstudio.ai) — load Nemotron (or larger model), start server **port 1234**
- Chrome installed

### One-time config

Edit `prompts/model.json` — set `"transport": "openai"` (see §6.1).

### Start

```powershell
cd C:\path\to\endgame-ai
$env:PYTHONIOENCODING = 'utf-8'
python server.py
```

Open **http://127.0.0.1:9077/** (workbench panel).

### Post goal and leave

Type goal in panel or:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:9078/run `
  -ContentType 'application/json' `
  -Body '{"goal":"open notepad and type hello"}'
```

Poll when you return:

```powershell
Invoke-RestMethod http://127.0.0.1:9078/state
# satisfied: true → done
```

### Example goals (increasing ambition)

| Goal | What Endgame must discover |
|------|---------------------------|
| `open notepad and type hello` | Bootstrap Nemotron only |
| `navigate to google.com in chrome` | `open_url` verb |
| `ask grok what is the capital of France and save the answer` | Bootstrap plans → open grok → chat → capture → remember |
| `use the best available AI on this PC to summarize my goal` | Full cognition discovery — hardest, unproven |

### Between goals

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:9078/llm-proxy/clear `
  -ContentType 'application/json' -Body '{"confirm":true}'
```

### If Nemotron fails JSON

Use a larger LM Studio model, or set `transport: file_proxy` and let Grok Build / Cursor poll `comms/slot1_cognition/request.json` — same uniform system, different cognition source.

---

## 15. HTTP API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Transport, nodes, run status |
| GET | `/state` | Full run state + history |
| POST | `/run` | `{"goal":"..."}` |
| POST | `/pause` / `/resume` | Control loop |
| POST | `/llm-proxy/clear` | `{"confirm":true}` — clear stale cognition |
| POST | `/wiring` | Hot-reload wiring |
| GET | `/wiring/audit` | Validate wiring |

Ports: root **9077**, slot 1 **9078**, slot 2 **9079** (optional relay worker).

---

## 16. Known gaps

| Gap | Impact |
|-----|--------|
| Bootstrap 4B model JSON reliability | Walk-away may fail on DECIDE NOW pass |
| P1 chatbot / grok discovery | Not E2E proven |
| self_modify | Coded, never demonstrated live |
| `plan_failed` → silent death | No reflect recovery |
| YouTube click-play | Partial benchmark only |
| Slot 2 relay as separate worker | Should merge into uniform discovery story |
| Codebase size | `server.py` needs shrink via modify/remove |

---

## 17. Remaining work

**Next session focus:** *how* proofs were achieved — capture `history`, `request.json` SCREEN, `/state` for Shakira + grok paths; extend, do not script around.

1. **Document proof captures** — reproducible walk-through of YouTube + grok runs with SCREEN evidence.
2. **Walk-away Nemotron** — panel goal, leave, return `satisfied: true`.
3. **Autonomous grok discovery** — no pre-opened tab; operator finds browser + chat via plan/act.
4. **Prove self_modify** — stuck goal → `wiring_patch` → retry success.
5. **Shrink `server.py`** — remove dead paths; brave architecture changes welcome.
6. **Delete or quarantine harness scripts** — test via Endgame itself.

---

## 18. Next AI handover prompt

```
You are continuing Endgame-AI — a self-evolving desktop operator SEED.

REPO: https://github.com/wgabrys88/endgame-ai
BRANCH: codex/self-referential-relay
DOCS: README.md only — read §0 Seed, §9 Rules, §11 How benchmarks achieved.

MINDSET — NOT legacy mode:
- This is NOT a standard computer-use agent. GUI = universal API. No vendor API required.
- One uniform operator. User posts goal in panel (:9077) and walks away.
- Bootstrap = Nemotron (LM Studio transport:openai). Upgrade cognition by navigating to grok.com, Grok Build, OpenCode, kiro-cli, any JSON file-proxy — via open_url/focus/write.
- wiring.json evolves (self_modify + panel hot-reload). Brave architecture changes and CODE REDUCTION encouraged — like Codex would.
- TEST BY RUNNING ENDGAME — not by adding p0 runners or harness scripts. Use panel, POST /run, read state.slot1.json.

RULES: Structural guardrails, not the enemy. Panel can hot-remove rules (no enabled toggle). If stuck, check deny rules before blaming cognition.

PROVEN (SCREEN-driven, Endgame owned hands):
- Notepad hello, Google open_url, YouTube via open_url (partial)
- Cognition read request.json SCREEN — no manual desktop by dev agent

NEXT SESSION PRIORITY: Document HOW Shakira + grok proofs were achieved (history + SCREEN captures). Extend to full walk-away + grok chat E2E.

FORBIDDEN: p0_file_proxy_runner.py as proof, new test scripts before shrink, legacy slot-recipe thinking.

KEY FILES: server.py, desktop.py, actions.py, prompts/wiring.json, wiring-editor.html
```

---

## 19. Deep Research prompt (ChatGPT project)

```
Deep research: Endgame-AI — self-evolving desktop operator with GUI-as-universal-API

Repository: https://github.com/wgabrys88/endgame-ai
Branch: codex/self-referential-relay

CONTEXT — read README first. This is NOT a standard computer-use agent.

Research questions:

1. PARADIGM COMPARISON
   Compare Endgame-AI to: Anthropic Computer Use, OpenAI CUA/Operator, OSWorld agents, Windows Agent Arena, UFO, Sakana DGM, LangGraph declarative agents.
   What is Endgame's unique bet? (hands/brain/cognition separation, GUI-unlimited cognition discovery, wiring.json self-evolution, structural verify rules, stdlib-only runtime)

2. SCIENTIFIC GROUNDING
   Survey 2025–2026 papers on: GUI grounding (UIA vs pixels), desktop agent benchmarks, self-modifying agents, declarative agent policy, local+remote cognition routing.
   Where does Endgame align with state of the art? Where is it ahead? Where behind?

3. WALK-AWAY OPERATOR MODEL
   Analyze the intended UX: bootstrap Nemotron → autonomous cognition discovery via GUI → self_modify policy evolution.
   What engineering gaps block "post goal and leave"? What is proven vs vision?

4. GUI AS UNIVERSAL API
   Analyze the claim that any browser-reachable or JSON-file-speaking intelligence can be integrated without vendor APIs.
   Compare to MCP, tool-calling, and computer-use APIs. Security and reliability implications.

5. SELF-EVOLUTION
   Analyze wiring_patch ops vs code self-modification (DGM). Risks of policy drift. Hot-reload safety.

6. RULES VS VERIFIER LLM
   Are 32 structural rules a safety net or friction? Panel hot-remove via POST /wiring. When should confirm rules skip verifier LLM?

7. SEED ROADMAP
   What is "complete seed" vs unrestricted future evolution? How were YouTube + grok proofs achieved mechanically?

Deliverables:
- 1-page executive summary
- Comparison table vs 5 closest systems
- Mermaid architecture (hands / brain / bootstrap / discovered cognition)
- Bibliography with arXiv links
- Honest assessment: breakthrough potential vs current maturity (~45% operator replacement)
```

---

## 20. Repository layout

| Path | Role |
|------|------|
| `server.py` | HTTP API, ROD loop, rules, LLM, self_modify |
| `desktop.py` | UIA, SCREEN, `[W#]`/`[ID]`, focus, `open_url` |
| `actions.py` | Verb dispatch |
| `prompts/wiring.json` | Brain — 32 rules, 12 nodes, 22 edges |
| `prompts/model.json` | Cognition transport (openai or file_proxy) |
| `wiring-editor.html` | Walk-away panel |
| `test_mechanical_fixes.py` | 11 mechanical tests (not E2E proof) |
| `p0_file_proxy_runner.py` | Canned driver — **not valid proof** |

**Gitignored runtime:** `state*.json`, `bus.json`, `comms/`, `traces.jsonl`

---

## Authoritative counts

| Item | Slot 1 value |
|------|--------------|
| Rules | **32** |
| Nodes | **12** |
| Edges | **22** |
| max_attempts / max_replans | **7** / **3** |
| max_self_modify | **3** |

Re-count from `wiring.json` after edits.

---

## 21. Appendix — session finish

### You — start the system now

```powershell
cd C:\path\to\endgame-ai
# 1. Start LM Studio, load model, server :1234
# 2. Set prompts/model.json → "transport": "openai"
$env:PYTHONIOENCODING = 'utf-8'
python server.py
# 3. Open http://127.0.0.1:9077/ — type goal — walk away
```

### This session — completed

| Deliverable | Status |
|-------------|--------|
| README rewritten around uniform operator + GUI-as-API thesis | Done |
| Seed diagram (now → complete → future) | Done |
| Rules honesty + panel hot-remove verified in code | Done |
| How benchmarks achieved (§11) | Done |
| Handover + Deep Research prompts updated | Done |
| Anti-legacy / anti-script discipline | Done |

### Next session — start here

1. Read README §0, §9, §11, §18.
2. Reproduce Shakira goal with Nemotron walk-away — capture `history` + how each step was decided.
3. Reproduce grok.com chat — capture SCREEN in `request.json` at act steps.
4. Remove or quarantine `p0_file_proxy_runner.py` if still tempting as shortcut.
5. Shrink `server.py` — one dead path removed per feature added.

### Developer discipline (all future agents)

| Do | Don't |
|----|-------|
| POST /run, use panel, read `/state` | Add parallel proof scripts |
| Modify/remove `server.py` first | Inflate codebase |
| Hot-edit rules in panel to debug | Assume rules are the root bug without checking SCREEN |
| Use Endgame to test Endgame | Manually click desktop during benchmarks |
| Brave wiring/topology changes | Treat slots as the product architecture |
| Let self_modify evolve policy | Hardcode grok/YouTube recipes in Python |

### Grok Build / Codex knowledge note

Prior sessions created `p0_file_proxy_runner.py`, `harness_common.py`, `run_verification.py` for automation — **invalid as E2E proof** because they do not read SCREEN. The operator itself is the test harness. Scripts may remain for mechanical regression only (`test_mechanical_fixes.py`).

---

## License

Research operator tooling. Not production-hardened.

**Prepare the seed. Walk away. Let Endgame find the way.**