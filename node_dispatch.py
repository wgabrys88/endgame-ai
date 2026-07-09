import core_bus as bus
import core_loader as loader
from core_node_base import BaseNode


class DispatchNode(BaseNode):
    """The faculty selector: topology decides which execute instances exist."""

    prompt_key = "node_dispatch"
    expected_record_type = "dispatch"

    def _targets(self, wiring):
        return list(wiring["topology"]["edges"]["node_dispatch"]["dispatch"])

    def _faculties(self, wiring):
        return [loader.split_instance(target)[1] for target in self._targets(wiring)]

    def build_payload(self, ctx):
        state = ctx["state"]
        step = state.get("current_step") or {}
        return {
            "goal": state["effective_goal"],
            "step": {"description": step.get("description", state["effective_goal"]), "done_when": step.get("done_when", "")},
            "faculties": self._faculties(ctx["wiring"]),
            "state": bus.state_brief(state),
            "observation": bus.observation_brief(state),
        }

    def run(self, ctx):
        state, wiring = ctx["state"], ctx["wiring"]
        payload = self.build_payload(ctx)
        record = self.think(ctx)
        faculty_to_target = dict(zip(self._faculties(wiring), self._targets(wiring)))
        chosen = [faculty_to_target[faculty] for faculty in record.data["faculties"] if faculty in faculty_to_target]
        if not chosen:
            raise RuntimeError(f"dispatch selected no valid faculties from {record.data['faculties']!r}")
        effective = state["effective_goal"] + f"\n\n[DISPATCH] I wake {record.data['faculties']} to labour; all {len(self._targets(wiring))} branches return to the gate."
        return bus.emit("dispatch", {"_dispatch_targets": chosen, "effective_goal": effective}, record=record, evidence=payload)


def run(ctx):
    return DispatchNode().run(ctx)
