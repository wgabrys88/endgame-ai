import core_bus as bus
from core_node_base import BaseNode

FACULTIES = ("browser", "editor", "terminal")


class DispatchNode(BaseNode):
    """The faculty selector: chooses which hands to engage this turn and fans out.

    A group of specialists is not all woken for every task. The dispatcher reads
    the goal-narrative and the current step, selects a subset of faculties
    (browser / editor / terminal), records how many it sent so the barrier knows
    the assembly size, and fans out to those node_execute instances via a list
    edge. The barrier gathers them back as one.
    """

    prompt_key = "node_dispatch"
    expected_record_type = "dispatch"

    def build_payload(self, ctx):
        state = ctx["state"]
        step = state.get("current_step") or {}
        return {
            "goal": state["effective_goal"],
            "step": {"description": step.get("description", state["effective_goal"]), "done_when": step.get("done_when", "")},
            "faculties": list(FACULTIES),
            "state": bus.state_brief(state),
            "observation": bus.observation_brief(state),
        }

    def run(self, ctx):
        state = ctx["state"]
        payload = self.build_payload(ctx)
        record = self.think(ctx)
        chosen = [f for f in record.data["faculties"] if f in FACULTIES]
        if not chosen:
            raise RuntimeError(f"dispatch selected no valid faculties from {record.data.get('faculties')!r}; known: {FACULTIES}")
        targets = [f"node_execute:{f}" for f in chosen]
        effective = state["effective_goal"] + f"\n\n[DISPATCH] I wake the faculties {chosen} to labour; the rest pass through idle. All {len(FACULTIES)} branches return to the gate as one."
        return bus.emit("dispatch", {"_dispatch_targets": targets, "effective_goal": effective}, record=record, evidence=payload)


def run(ctx):
    return DispatchNode().run(ctx)
