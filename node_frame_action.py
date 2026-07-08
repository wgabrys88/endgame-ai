import core_bus as bus
from core_node_base import BaseNode


class FrameActionNode(BaseNode):
    prompt_key = "node_frame_action"
    expected_record_type = "action_frame"

    def evidence(self, ctx):
        state = ctx.get("state", {})
        return {"state": bus.state_brief(state), "last_action": state.get("last_action", {}), "last_result": state.get("last_result", ""), "last_error": state.get("last_error", "")}

    def build_payload(self, ctx):
        state = ctx.get("state", {})
        step = state.get("current_step") or {}
        goal = bus.current_goal(state, ctx)
        return {"goal": goal, "step": {"description": step.get("description", goal), "done_when": step.get("done_when", "")}, "evidence": self.evidence(ctx), "observation": bus.observation_brief(state)}

    def signal_from_data(self, data, ctx):
        signal = data.get("next_signal")
        if signal not in {"framed", "reflect"}:
            raise RuntimeError(f"frame_action emitted invalid next_signal: {signal!r}")
        return signal

    def patch_from_record(self, record, ctx):
        data, state = record.data, ctx.get("state", {})
        step_index = int(state.get("step", 0) or 0)
        frame = {key: data.get(key, "") for key in ("screen_summary", "target", "strategy", "risk", "notes")}
        frame["step_index"] = step_index
        effective = bus.append_goal(state, ctx, f"[FRAME_ACTION] Focusing on {frame.get('target', 'unknown')} via {frame.get('strategy', 'unknown')}: {frame.get('notes', '')[:200]}")
        return {"action_frame": frame, "framing_attempted_for_step": step_index, "effective_goal": effective}


def run(ctx):
    return FrameActionNode().run(ctx)
