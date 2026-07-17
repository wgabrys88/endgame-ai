"""[node_verify] — You receive the last deed, its done_when and action time, and one fresh observation."""
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
        return {
            "goal": state["goal"],
            "deed": {"description": desc, "done_when": done_when, "acted_at": state.get("last_action_at")},
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
            verdict = ns.get("verdict")
            if not isinstance(verdict, dict) or not isinstance(verdict.get("goal_satisfied"), bool) or not isinstance(verdict.get("deed_confirmed"), bool) or not isinstance(verdict.get("reason"), str) or not verdict["reason"].strip():
                raise RuntimeError("verification probe must set verdict with boolean goal_satisfied/deed_confirmed and non-blank reason")
        except Exception:
            probe_fault = traceback.format_exc()
            verdict = {"goal_satisfied": False, "deed_confirmed": False, "reason": probe_fault}
        goal_satisfied = verdict["goal_satisfied"]
        deed_confirmed = verdict["deed_confirmed"]
        reason = verdict["reason"]
        if goal_satisfied:
            signal = "halt"
        elif deed_confirmed:
            signal = "deed_confirmed"
        else:
            signal = "deed_denied"
        desc, done_when = self._deed(ctx)
        confirmed = goal_satisfied or deed_confirmed
        patch = {
            "verification": {"goal_satisfied": goal_satisfied, "deed_confirmed": deed_confirmed, "reasoning": reason, "deed_goal": desc, "done_when": done_when},
            "last_verification": {"success": confirmed, "signal": signal, "reasoning": reason},
            "goal_interpretations": bus.with_interpretation(state.get("goal_interpretations"), "verify", f"The witness probe failed ere verdict:\n{probe_fault}" if probe_fault else str(record.data.get("goal_interpretation") or "")),
        }
        if confirmed:
            patch.update({"witnessed_deed_count": int(state.get("witnessed_deed_count") or 0) + 1, "failure_streak": {"count": 0}, "action_frame": None, "current_deed": None})
        return bus.emit(signal, patch, record=record, evidence=self.build_payload(ctx))


def run(ctx):
    return VerifyNode().run(ctx)
