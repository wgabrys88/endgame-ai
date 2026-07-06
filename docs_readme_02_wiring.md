# wiring.json: The Immutable Circuit

`wiring.json` is not configuration. It is **the organism's DNA** — a single JSON file that defines the complete topology, transports, prompts, and self-modification rules. The organism never rewires itself mid-run; `node_self_modify` proposes patches, the local body validates (Python compile + JSON parse), commits, and optionally pushes.

## Base Topology (Single Organism)

```mermaid
stateDiagram-v2
    [*] --> node_planner
    node_planner --> node_scheduler : step_ready
    node_planner --> node_reflect : reflect
    node_planner --> node_error : error
    node_scheduler --> node_observe : step_ready
    node_scheduler --> node_satisfied : plan_complete
    node_scheduler --> node_error : error
    node_observe --> node_planner : initial_screen
    node_observe --> node_execute : screen_ready
    node_observe --> node_error : error
    node_execute --> node_verify : verify
    node_execute --> node_frame_action : frame
    node_execute --> node_reflect : reflect
    node_execute --> node_self_modify : self_modify
    node_execute --> node_error : error
    node_verify --> node_scheduler : step_confirmed
    node_verify --> node_reflect : step_denied
    node_verify --> node_error : error
    node_reflect --> node_observe : retry
    node_reflect --> node_planner : replan
    node_reflect --> node_frame_action : frame
    node_reflect --> node_self_modify : escalate
    node_reflect --> node_satisfied : give_up
    node_reflect --> node_error : error
    node_self_modify --> node_planner : modified
    node_self_modify --> node_reflect : modify_failed
    node_self_modify --> node_error : error
    node_satisfied --> [*] : halt
    node_frame_action --> node_execute : framed
    node_frame_action --> node_reflect : reflect
    node_frame_action --> node_error : error
    node_error --> node_planner : planner
    node_error --> node_reflect : reflect
    node_error --> [*] : halt
```

## Recursive/Fractal Topology (Distributed Evolution)

When `node_self_modify` escalates to **distributed review**, the topology becomes a **tree of organisms** — each node in the tree is a full endgame-ai instance running the same wiring:

```mermaid
graph TD
    subgraph "META-LEVEL 0: Original Goal"
        O0[Organism A<br/>Proposer]
    end
    
    subgraph "META-LEVEL 1: Review"
        O1[Organism B<br/>Reviewer]
        O1_1[Organism B1<br/>Sub-reviewer]
    end
    
    subgraph "META-LEVEL 2: Audit"
        O2[Organism C<br/>Auditor]
    end
    
    O0 -.->|propose patch<br/>push to GitHub| O1
    O1 -.->|review: pyright, vulture,<br/>pyan3, tests| O1_1
    O1_1 -.->|audit reviewer| O2
    O1 -.->|verdict: approve/reject<br/>runtime_response.json| O0
    O0 -.->|hot-reload & continue| O0
    
    style O0 fill:#e1f5fe
    style O1 fill:#fff3e0
    style O1_1 fill:#fff3e0
    style O2 fill:#fce4ec
```

**Key insight**: The reviewer (Organism B) is **not a special node** — it's a full endgame-ai instance with the *same wiring.json*, same topology, same organs. Its "goal" is simply *"Review PR #42: validate evolution patch"*. It runs the same planner→scheduler→observe→execute→verify→reflect loop. The only difference is the goal string and the transport (file-proxy for review channel).

This makes the topology **fractal**: the same circuit at every meta-level.

## Transport Layer (Pluggable Brains)

```json
"model": {
  "transport": "transport_xai",
  "transport_config": {
    "transport_xai": {
      "mode": "api",
      "api_key_env": "XAI_API_KEY",
      "model": "grok-4.3",
      "reasoning": { "enabled": true, "effort": "low" }
    },
    "transport_file_proxy": {
      "request_path": "runtime_request.json",
      "response_path": "runtime_response.json"
    },
    "transport_openai": { "base_url": "http://localhost:1234", "model": "nemotron-3-nano-4b" },
    "transport_opencode": { "executable": "opencode-cli.exe" }
  }
}
```

Switching brains = changing one string. The organism doesn't care.

## Self-Modify as Topology Extension

The `node_self_modify` organ doesn't just patch files — it **extends the topology** by spawning a review organism:

```mermaid
sequenceDiagram
    participant A as Organism A (Proposer)
    participant GH as GitHub
    participant B as Organism B (Reviewer)
    
    A->>A: node_self_modify produces patch
    A->>A: Local validate (compile + pyright + vulture)
    A->>GH: git push origin feature/xyz
    GH->>B: Webhook / poll (trigger review)
    B->>B: Goal: "Review PR #42"
    B->>B: Planner: decompose review steps
    B->>B: Execute: clone, pyright, vulture, pyan3, tests
    B->>B: Verify: all checks pass?
    B->>B: Reflect: if fail, diagnose
    B->>B: Self-modify: (optional) patch review criteria
    B->>B: Satisfied: emit verdict
    B->>A: Write runtime_response.json (approve/reject)
    A->>A: Poll response
    A->>A: Approve? Hot-reload & continue : Hot-swap to known_good
```

The wiring.json doesn't change — the **topology extends dynamically** through the file-proxy protocol.