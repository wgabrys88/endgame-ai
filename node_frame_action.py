import core_bus as bus
from core_node_base import BaseNode


class FrameActionNode(BaseNode):
    prompt_key = "node_frame_action"
    expected_record_type = "action_frame"

    def evidence(self, ctx):
        return bus.execution_evidence(ctx["state"])

    def build_payload(self, ctx):
        state = ctx["state"]
        step = state.get("current_step") or {}
        return {
            "goal": state["goal"],
            "step": {"description": step.get("description", state["goal"]), "done_when": step.get("done_when", "")},
            "focus": bus.state_brief(state),
            "evidence": self.evidence(ctx),
            "observation": bus.observation_brief(state),
        }

    def signal_from_data(self, data, ctx):
        signal = data["next_signal"]
        if signal not in {"framed", "reflect"}:
            raise RuntimeError(f"frame_action emitted invalid next_signal: {signal!r}")
        return signal

    def patch_from_record(self, record, ctx):
        data, state = record.data, ctx["state"]
        frame = {key: data[key] for key in ("screen_summary", "target", "strategy", "risk", "notes")}
        frame["step_index"] = int(state.get("step", 0) or 0)
        effective = bus.append_narrative(state["effective_goal"], f"\n\n[FRAME_ACTION] Target {frame['target']} via {frame['strategy']}: {frame['notes']}", root_goal=state.get("goal", ""))
        return {"action_frame": frame, "framing_attempted_for_step": frame["step_index"], "effective_goal": effective}


def run(ctx):
    return FrameActionNode().run(ctx)
