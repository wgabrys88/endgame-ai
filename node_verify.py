"""[node_verify] — Thou expectest the last deed, its [done_when], and the fresh observation."""
import traceback

import core_bus as bus
import core_nodes as nodes
from core_node_base import BaseNode


class VerifyNode(BaseNode):
    prompt_key = "node_verify"
    expected_record_type = "verification"

    def _deed(self, ctx):
        state = ctx["state"]
        deed = state.get("current_deed") or {}
        return deed.get("description", state["goal"]), deed.get("done_when", "")

    def build_payload(self, ctx):
        state = ctx["state"]
        desc, done_when = self._deed(ctx)
        observation = bus.observation_brief(state)
        observed_at = state.get("observed_at")
        last_action_at = state.get("last_action_at")
        observation["observation_fresh"] = bool(
            observed_at is not None and (last_action_at is None or float(observed_at) > float(last_action_at))
        )
        return {
            "goal": state["goal"],
            "deed": {"description": desc, "done_when": done_when},
            "focus": bus.state_brief(state),
            "observation": observation,
        }

    def run(self, ctx):
        state = ctx["state"]
        record = self.think(ctx)
        code = record.data["code"]
        ns = nodes.build_capability_runtime(ctx, read_only=True)
        probe_fault = None
        try:
            exec(code, ns)
        except Exception:
            probe_fault = traceback.format_exc()
        verdict = ns.get("verdict")
        if probe_fault:
            goal_satisfied = deed_confirmed = False
            reason = probe_fault
        else:
            if not isinstance(verdict, dict) or "goal_satisfied" not in verdict or "deed_confirmed" not in verdict or "reason" not in verdict:
                raise RuntimeError("verification probe must set verdict = {goal_satisfied, deed_confirmed, reason}")
            goal_satisfied = bool(verdict["goal_satisfied"])
            deed_confirmed = bool(verdict["deed_confirmed"])
            reason = str(verdict["reason"])
        if goal_satisfied:
            signal = "goal_satisfied"
        elif deed_confirmed:
            signal = "deed_confirmed"
        else:
            signal = "deed_denied"
        desc, done_when = self._deed(ctx)
        confirmed = goal_satisfied or deed_confirmed
        patch = {
            "verification": {"goal_satisfied": goal_satisfied, "deed_confirmed": deed_confirmed, "reasoning": reason, "deed_goal": desc, "done_when": done_when},
            "last_verification": {"success": confirmed, "signal": signal, "reasoning": reason},
            "goal_interpretations": bus.with_interpretation(state.get("goal_interpretations"), "verify", str(record.data.get("goal_interpretation") or "")),
        }
        if confirmed:
            patch.update({"witnessed_deed_count": int(state.get("witnessed_deed_count") or 0) + 1, "failure_streak": {"signature": None, "count": 0}, "action_frame": None, "current_deed": None})
        return bus.emit(signal, patch, record=record, evidence=self.build_payload(ctx))


def run(ctx):
    return VerifyNode().run(ctx)
