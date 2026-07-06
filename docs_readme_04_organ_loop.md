# 4. The Organ Loop: One Bus, One Signal

## Bus Contract

Every organ receives **one typed record** and emits **exactly one JSON record** whose `data.next_signal` is the only value the body routes on. Organs never call each other directly.

```mermaid
sequenceDiagram
    participant Body
    participant Planner
    participant Scheduler
    participant Observe
    participant Execute
    participant Verify
    participant Reflect
    participant SelfModify
    participant Satisfied
    
    Body->>Planner: {goal, state, observation}
    Planner-->>Body: {record_type:"plan", data:{next_signal:"step_ready", intent:[...]}}
    Body->>Scheduler: {step: 0}
    Scheduler-->>Body: {record_type:"schedule", data:{next_signal:"step_ready", step:0}}
    Body->>Observe: (mechanical, no brain)
    Observe-->>Body: {desktop_tree, desktop_tree_text, action_index}
    Body->>Execute: {step, frame, observation}
    Execute-->>Body: {record_type:"execution", data:{conclusion:"EXECUTE", code:"..."}}
    Body->>Body: runs code in capability runtime
    Body->>Verify: {step, done_when, result, observation}
    Verify-->>Body: {record_type:"verification", data:{next_signal:"step_confirmed", success:true}}
    Body->>Scheduler: (advances to next step)
    Note over Body,Scheduler: loop until plan_complete
    Body->>Satisfied: {goal, evidence}
    Satisfied-->>Body: {record_type:"satisfied", data:{next_signal:"halt"}}
```

## Organ Roles

| Organ | Brain | Role |
|-------|-------|------|
| `node_planner` | ✅ | Decomposes goal into verifiable steps |
| `node_scheduler` | ❌ | Mechanical: advances to next step |
| `node_observe` | ❌ | Mechanical: whole-screen UIA scan |
| `node_execute` | ✅ | Writes Python code, runs in capability runtime |
| `node_verify` | ✅ | Judges step success from fresh observation only |
| `node_reflect` | ✅ | Diagnoses failure, routes: retry/replan/frame/escalate/give_up |
| `node_self_modify` | ✅ | Produces git-native evolution patches |
| `node_satisfied` | ✅ | Halts when goal complete or honest give-up |

## Capability Runtime (Injected into Execute)

```python
{
  "click_node": click_node,      # click_node("W1E2")
  "read_node": read_node,        # read_node("W1E4")
  "scroll_node": scroll_node,    # scroll_node("W2E3", -3)
  "action_nodes": action_nodes,  # filter by action type
  "pyautogui": pag,              # coordinate fallback
  "subprocess", "ctypes", "os", "sys", "json", "re", "time",
  "pathlib", "math", "random", "types",
  "wiring_limit", "repo_root", "topology_mermaid",
  "state", "wiring", "goal", "last", "fresh_observation",
  "desktop_tree_text", "action_index"
}
```

No sandbox. Full Python. The body trusts the brain.

## Recursive Organ Loops: Meta-Levels

When `node_self_modify` escalates to distributed review, the **same organ loop runs at a higher meta-level**:

```
META-LEVEL 0 (Work)          META-LEVEL 1 (Review)          META-LEVEL 2 (Audit)
┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
│ Goal: "Write    │          │ Goal: "Review   │          │ Goal: "Audit    │
│  PS bridge"     │          │  PR #42"        │          │  reviewer B"    │
├─────────────────┤          ├─────────────────┤          ├─────────────────┤
│ Planner →       │          │ Planner →       │          │ Planner →       │
│ Scheduler →     │          │ Scheduler →     │          │ Scheduler →     │
│ Observe →       │          │ Observe →       │          │ Observe →       │
│ Execute →       │          │ Execute →       │          │ Execute →       │
│ Verify →        │          │ Verify →        │          │ Verify →        │
│ Reflect →       │          │ Reflect →       │          │ Reflect →       │
│ SelfMod → ──────┼─────────>│ SelfMod →       │          │ SelfMod →       │
│ Satisfied       │          │ Satisfied       │          │ Satisfied       │
└─────────────────┘          └─────────────────┘          └─────────────────┘
       │                            │                            │
       │  runtime_request.json      │  runtime_request.json      │
       ▼                            ▼                            ▼
  File Proxy                  File Proxy                  File Proxy
```

**The reviewer is not a special node** — it's a full endgame-ai instance. Its `node_execute` runs `pyright`, `vulture`, `pyan3`, `pydeps`, `code2flow`, `pytest`. Its `node_verify` judges: "Do all checks pass?" Its `node_satisfied` emits the verdict.

The wiring.json doesn't change. The topology extends **dynamically** through the file-proxy protocol. Same organs, same bus, same signals — different goal.