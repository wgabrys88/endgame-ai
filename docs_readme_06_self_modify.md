# 6. Self-Modification: Distributed Git-Native Evolution

## The Vision: Organism Proposes, Peer Reviews, Organism Adopts

endgame-ai doesn't just "self-modify" locally. It **proposes evolution patches to GitHub**, where **another endgame-ai instance (the reviewer)** clones the repo, runs deterministic analysis (pyright, vulture, pyan3, pydeps, code2flow), compiles, tests, validates — and **responds with approval or rejection** via the same file-proxy protocol.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DISTRIBUTED SELF-EVOLUTION LOOP                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐     1. Propose Patch      ┌──────────────┐               │
│  │  ORGANISM A  │ ────────────────────────> │   GITHUB     │               │
│  │  (proposer)  │    git push origin        │  (registry)  │               │
│  └──────────────┘                           └──────┬───────┘               │
│                                                     │                       │
│                                                     │ 2. Clone & Review     │
│                                                     ▼                       │
│  ┌──────────────┐     4. Approve/Reject      ┌──────────────┐               │
│  │  ORGANISM A  │ <────────────────────────── │  ORGANISM B  │               │
│  │  (adopter)   │    runtime_response.json   │  (reviewer)  │               │
│  └──────────────┘                           └──────────────┘               │
│        │                                             ▲                      │
│        │ 5. Hot-reload & continue                     │                      │
│        ▼                                             │                      │
│  ┌──────────────┐                                    │                      │
│  │  CONTINUE    │                                    │                      │
│  │  EXECUTION   │                                    │                      │
│  └──────────────┘                                    │                      │
│                                                      │                      │
│                    3. Deterministic Analysis         │                      │
│              ┌────────────────────────┐              │                      │
│              │ pyright, vulture,      │              │                      │
│              │ pyan3, pydeps,         │              │                      │
│              │ code2flow, tests       │              │                      │
│              └────────────────────────┘              │                      │
│                                                      │                      │
└──────────────────────────────────────────────────────┘──────────────────────┘
```

## How It Works

### 1. Organism A (Proposer) Hits a Wall
- Execution fails, reflection escalates, or capability missing
- `node_self_modify` reads: workspace manifest, git context, failure diagnosis, fresh observation
- Produces **evolution patch** (structured JSON: file_writes, wiring_patches, commands, expected_validation)

### 2. Local Validation (Fast Path)
- Python compile + JSON parse on every touched file
- Runs declared `commands` (pyright, vulture, custom tests)
- **Only if local validation passes**: commit + push to `origin/<branch>`

### 3. GitHub as Registry
- Patch lands on remote branch with structured commit message:
  ```
  Self-modify: Unify short IDs, remove node_by_id fallback
  
  {
    "branch": "feature/short-ids",
    "changed_files": ["core_nodes.py", "core_observation.py", "wiring.json"],
    "read_files": ["core_nodes.py", "core_observation.py", "wiring.json"],
    "rationale": "Single lookup path via action_index keyed by short_id...",
    "expected_validation": "pyright clean, organism runs 5 ticks without error"
  }
  ```

### 4. Organism B (Reviewer) — Can Be Anywhere
- Another endgame-ai instance (different machine, same repo) runs in **review mode**:
  ```bash
  python -m core_organism "Review PR #42: validate evolution patch" --max-ticks 20
  ```
- Reviewer's wiring uses `transport_file_proxy` pointing to a shared review directory, OR `transport_xai` with a review prompt
- Reviewer clones repo at the commit, runs **full deterministic analysis**:
  ```bash
  python ps_bridge.py pyright .
  python ps_bridge.py vulture . 90
  python ps_bridge.py pyan3 . --uses --dot --file deps.dot
  python ps_bridge.py pydeps . --noshow
  python ps_bridge.py code2flow . --format dot
  python -m pytest  # if tests exist
  ```
- Reviewer writes `runtime_response.json` with verdict:
  ```json
  {
    "record_type": "evolution_review",
    "data": {
      "verdict": "approve|reject",
      "commit_sha": "abc1234",
      "analysis": {
        "pyright": {"errors": 0, "warnings": 2},
        "vulture": {"dead_code": []},
        "call_graph": {"cycles": 0, "unreachable": []},
        "tests": {"passed": 5, "failed": 0}
      },
      "reasoning": "Patch passes all checks. Short ID unification is correct. Approved."
    },
    "reasoning": "..."
  }
  ```

### 5. Organism A (Adopter) Hot-Reloads
- Organism A polls for review response (file-proxy or webhook)
- On **approve**: atomic write of validated files, reload wiring, continue from planner
- On **reject**: hot-swap to `known_good_commit`, route to reflection for replan

## Why This Architecture Matters

| Traditional "Self-Modify" | endgame-ai Distributed Evolution |
|---------------------------|----------------------------------|
| Local-only, no verification | **Peer-reviewed by another instance** |
| Trusts own validation | **Independent compilation & test** |
| Single point of failure | **Reviewer can be on different machine/OS** |
| No audit trail | **Full Git history + structured commit messages** |
| Human-in-the-loop required | **AI-to-AI review via file proxy** |

## The File Proxy as Review Channel

The same `transport_file_proxy` that lets humans drive the organism lets **endgame-ai instances talk to each other**:

```
Organism A (proposer)          GitHub          Organism B (reviewer)
     │                           │                    │
     ├─ push patch ─────────────>│                    │
     │                           ├─ webhook/poll ────>│
     │                           │                    ├─ clone, analyze, test
     │                           │                    ├─ write runtime_response.json
     │                           │<──── approve ───────┤
     ├─ poll response ───────────│                    │
     ├─ hot-reload & continue    │                    │
```

**No MCP servers. No custom protocols. Just JSON files.** Any entity that can read/write files participates.

## Safety Mechanisms (Unchanged, Still Critical)

- **Read-before-write**: Must declare `read_files` for every touched existing file
- **Core file protection**: Cannot delete `core_*.py` or `wiring.json`
- **Rollback on failure**: Snapshots restored automatically
- **Hot-swap to known good**: `wiring.json`'s `known_good_commit` is the escape hatch
- **Atomic writes**: Temp file + `os.replace`
- **Reviewer veto**: Rejection triggers immediate hot-swap, no partial adoption

## The Goal Remains the Memory

No vector DB. No embeddings. The **goal string** — fixed for the run — is the atemporal narrative. Each organ receives it. Each patch references it. The reviewer evaluates against it. The organism *tells itself the story of what it's doing* across ticks, across machines, across reviews. Self-modification updates the story by updating the code that enacts it — **with peer approval**.

## Fractal Topology: Recursive Self-Improvement

The reviewer (Organism B) is **not a special node** — it's a full endgame-ai instance with the *same wiring.json*, same topology, same organs. Its "goal" is simply *"Review PR #42: validate evolution patch"*. It runs the same planner→scheduler→observe→execute→verify→reflect loop.

This makes the topology **fractal**: the same circuit at every meta-level.

```mermaid
graph TD
    subgraph "LEVEL 0: Work"
        O0[Organism A<br/>Goal: "Write PS bridge"]
    end
    
    subgraph "LEVEL 1: Review"
        O1[Organism B<br/>Goal: "Review PR #42"]
        O1 --> O0
    end
    
    subgraph "LEVEL 2: Audit"
        O2[Organism C<br/>Goal: "Audit reviewer B"]
        O2 --> O1
    end
    
    subgraph "LEVEL N: Meta-Audit"
        ON[Organism N<br/>Goal: "Audit auditor..."]
        ON --> O2
    end
    
    O0 -.->|propose| O1
    O1 -.->|approve/reject| O0
    O1 -.->|propose review criteria| O2
    O2 -.->|approve/reject| O1
```

**Implications:**

| Property | Consequence |
|----------|-------------|
| **Same wiring at every level** | No special "reviewer code" — the reviewer *is* the organism |
| **Goal drives behavior** | "Review PR #42" vs "Write PS bridge" — same loop, different intent |
| **File proxy as universal channel** | Human↔AI, AI↔AI, AI↔AI↔AI — all JSON files |
| **GitHub as coordination layer** | Commits = proposals, PRs = review contexts, merges = adoption |
| **Unbounded meta-levels** | Reviewer can be reviewed, auditor audited — recursive improvement |
| **Distributed by default** | Reviewer on different machine, OS, network — same protocol |

The organism doesn't just evolve its code. It evolves **the process by which it evolves** — because the reviewer itself can be reviewed, and so on. This is **recursive self-improvement** where the improvement mechanism *is* the thing being improved.