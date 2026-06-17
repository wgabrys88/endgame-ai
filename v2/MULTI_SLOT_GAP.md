# v2 to Full Multi-Slot Architecture: Gap Analysis

## Current v2 Reuse

| Component | Reusable? | Changes needed |
|-----------|-----------|----------------|
| `llm.py` | 100% | None |
| `bus.py` | 100% | None |
| `slot.py` | 95% | Mutator target scoping (actor/verifier only) |
| `actions.py` | 100% | None |
| `desktop.py` | 100% | None |
| `tui.py` | ~70% | Add multi-slot display + comms_operator bootstrap |

**Total reuse: ~95% of existing 1192 LOC is unchanged.**

## What Must Be Added

### 1. Comms Operator (~60 LOC)

A special "slot" that does not act on the desktop. It reads the user goal, decomposes it, and posts sub-goals to the bus for each worker slot.

```python
class CommsOperator:
    def __init__(self, llm: LLMClient, bus: Bus):
        self.llm = llm
        self.bus = bus

    def route(self, goal: str):
        # LLM decomposes goal into sub-goals per slot
        # Publishes "route" records to bus
        # Each slot reads bus for its assigned goal
        ...
```

**This is a stripped-down Slot that only has a planner (no actor/verifier).**

### 2. Per-Slot Prompt Directories (~0 LOC, just files)

```
prompts/
  architect/planner.txt
  architect/actor.txt
  architect/verifier.txt
  architect/mutator.txt
  implementor/...
  reviewer/...
  devops/...
  comms_operator/planner.txt
```

Each slot already takes `prompts_dir` as constructor arg. Just create the directories.

### 3. Global Mutator (~40 LOC)

Reads bus for denial patterns across all slots. Proposes planner prompt patches.

```python
class GlobalMutator:
    def __init__(self, llm: LLMClient, bus: Bus, slots: dict[str, Slot]):
        ...

    def step(self):
        # Read bus for cross-slot denial patterns
        # Propose prompt patches to underperforming planners
        ...
```

### 4. Multi-Slot Runner (~50 LOC)

Orchestrates multiple slots in a loop (round-robin or threaded).

```python
class Colony:
    def __init__(self, llm, bus, workspace, prompts_root):
        self.bus = bus
        self.comms = CommsOperator(llm, bus)
        self.slots = {
            "architect": Slot(llm, bus, prompts_root / "architect", workspace),
            "implementor": Slot(llm, bus, prompts_root / "implementor", workspace),
            "reviewer": Slot(llm, bus, prompts_root / "reviewer", workspace),
            "devops": Slot(llm, bus, prompts_root / "devops", workspace),
        }
        self.mutator = GlobalMutator(llm, bus, self.slots)

    def run(self, goal: str):
        self.comms.route(goal)
        while True:
            for slot in self.slots.values():
                slot.step()
            self.mutator.step()
```

### 5. Slot Goal Pickup from Bus (~15 LOC)

Add a method to `Slot` that checks the bus for routed goals:

```python
def check_bus_for_goal(self):
    routes = self.bus.query(record_type="route", limit=5)
    for r in routes:
        if r.data.get("to") == self.name and not self.state.goal:
            self.set_goal(r.data["goal"])
```

### 6. Mutator Scoping (~10 LOC)

Current `Mutator` in `slot.py` tunes generically. Scope it to actor/verifier prompts only (not planner, which is the global mutator's job).

## Total New Code

| Addition | LOC |
|----------|-----|
| CommsOperator | ~60 |
| GlobalMutator | ~40 |
| Colony runner | ~50 |
| Bus goal pickup | ~15 |
| Mutator scoping | ~10 |
| TUI multi-slot display | ~40 |
| **Total new** | **~215** |

## Final System Size

```
Current v2:     1192 LOC
New code:       ~215 LOC
Total:         ~1407 LOC
```

Still well under 2000 LOC.

## What Does NOT Change

- `llm.py` - zero changes
- `bus.py` - zero changes (already supports multi-publisher)
- `desktop.py` - zero changes (shared by actor slots)
- `actions.py` - zero changes
- `slot.py` - 10 lines added (bus goal pickup + mutator scope)
- Prompts format - zero changes (just more directories)

## Architecture Mapping (Diagram to Code)

```
Diagram Element              v2 Code
------------------------------------------------------
User goal                    CLI arg -> Colony.run(goal)
comms_operator planner       CommsOperator.route()
Shared bus / blackboard      Bus (bus.py) - already exists
architect slot               Slot(prompts_dir="prompts/architect")
implementor slot             Slot(prompts_dir="prompts/implementor")
reviewer slot                Slot(prompts_dir="prompts/reviewer")
devops slot                  Slot(prompts_dir="prompts/devops")
local mutator                Mutator class in slot.py - already exists
planner/actor/verifier       Planner/Actor/Verifier in slot.py - already exist
global mutator               GlobalMutator (new, ~40 LOC)
bus <-> slot planners         Slot.check_bus_for_goal() - 15 LOC
```

## Conclusion

The v2 architecture was designed exactly for this expansion. The single-slot implementation IS one cell of the diagram. Scaling to 4 slots + comms_operator + global mutator requires ~215 new lines and zero rewrites of existing code. The Bus is already the shared communication layer. Each Slot is already self-contained with its own prompts directory.

**Time estimate: 1-2 hours to implement and test the full diagram.**
