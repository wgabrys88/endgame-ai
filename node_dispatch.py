import core_bus as bus
import core_loader as loader
from core_node_base import BaseNode


class DispatchNode(BaseNode):
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
            "goal": state["goal"],
            "step": {"description": step.get("description", state["goal"]), "done_when": step.get("done_when", "")},
            "faculties": self._faculties(ctx["wiring"]),
            "focus": bus.state_brief(state),
            "observation": bus.observation_brief(state),
        }

    def run(self, ctx):
        wiring = ctx["wiring"]
        payload = self.build_payload(ctx)
        record = self.think(ctx)
        faculty_to_target = dict(zip(self._faculties(wiring), self._targets(wiring)))
        chosen = [faculty_to_target[faculty] for faculty in record.data["faculties"] if faculty in faculty_to_target]
        if not chosen:
            raise RuntimeError(f"dispatch selected no valid faculties from {record.data['faculties']!r}")
        return bus.emit("dispatch", {"_dispatch_targets": chosen, "turn_executions": {}}, record=record, evidence=payload)


def run(ctx):
    return DispatchNode().run(ctx)
