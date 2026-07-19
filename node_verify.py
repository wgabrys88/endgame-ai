"""[node_verify] — Thou receivest the [goal], the last [deed] (its description and hour of action), the [state] brief, and one fresh observation."""
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
        return deed.get("description", state["goal"])

    def build_payload(self, ctx):
        state = ctx["state"]
        desc = self._deed(ctx)
        observation = bus.observation_brief(state)
        return {
            "goal": state["goal"],
            "deed": {"description": desc, "acted_at": state.get("last_action_at")},
            "state": bus.state_brief(state),
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

        if probe_fault is not None:
            note = (
                "The read-only probe I authored raised ere it set a verdict, so this deed standeth "
                "UNJUDGED — this is neither the actor's failing nor a fault in any node file, for the "
                "probe is transient code I write anew each witnessing. I shall author a simpler probe "
                "that runneth, and touch no body file.\n" + probe_fault
            )
            patch = {
                "goal_interpretations": bus.with_interpretation(state.get("goal_interpretations"), "verify", note),
                "last_verification": {"success": False, "signal": "unwitnessed", "reasoning": probe_fault},
            }
            return bus.emit("unwitnessed", patch)

        goal_satisfied = verdict["goal_satisfied"]
        deed_confirmed = verdict["deed_confirmed"]
        reason = verdict["reason"]
        if goal_satisfied:
            signal = "halt"
        elif deed_confirmed:
            signal = "deed_confirmed"
        else:
            signal = "deed_denied"
        desc = self._deed(ctx)
        confirmed = goal_satisfied or deed_confirmed
        patch = {
            "verification": {"goal_satisfied": goal_satisfied, "deed_confirmed": deed_confirmed, "reasoning": reason, "deed_goal": desc},
            "last_verification": {"success": confirmed, "signal": signal, "reasoning": reason},
            "goal_interpretations": bus.with_interpretation(state.get("goal_interpretations"), "verify", str(record.data.get("goal_interpretation") or "")),
        }
        if confirmed:
            proven = list(state.get("proven_ledger") or [])
            fact = f"{desc.strip()} — witnessed: {reason.strip()}" if desc.strip() else reason.strip()
            if fact and fact not in proven:
                proven.append(fact)
            patch.update({
                "witnessed_deed_count": int(state.get("witnessed_deed_count") or 0) + 1,
                "failure_streak": {"count": 0},
                "proven_ledger": proven,
                "action_frame": None,
                "current_deed": None,
            })
        return bus.emit(signal, patch)


def run(ctx):
    return VerifyNode().run(ctx)
