"""node_planner — authors the remaining plan for the root goal. EXPECTS: the goal, the current effective_goal narrative, any previous plan and completed_steps, last_reflection, last_repair_validation, and self_modify status. PRODUCES a plan (intent: list of steps, each with description + done_when) and next_signal 'step_ready'."""
import core_bus as bus
from core_node_base import BaseNode


class PlannerNode(BaseNode):
    prompt_key = "node_planner"
    expected_record_type = "plan"

    def build_payload(self, ctx):
        state = ctx["state"]
        prior = state.get("plan") if isinstance(state.get("plan"), dict) else {}
        completed = state.get("completed_steps") if isinstance(state.get("completed_steps"), list) else []
        return {
            "goal": state["goal"],
            "focus": bus.state_brief(state),
            "observation": bus.observation_brief(state),
            "previous_plan": prior,
            "completed_steps": completed,
            "last_reflection": state.get("last_reflection", {}),
            "last_evolution": state.get("self_modify", {}),
            "last_repair_validation": state.get("last_repair_validation", {}),
            "replan_contract": (
                "Emit the complete remaining plan for the immutable root goal. A replan may change step count and "
                "granularity; preserve obligations by meaning, not by matching the old number of steps. A resolved "
                "repair validation proves only that the failed mechanism now works; it does not automatically verify "
                "the original task step. An unresolved repair validation forbids treating that candidate repair as available."
            ),
        }

    def signal_from_data(self, data, ctx):
        return data["next_signal"]

    def patch_from_record(self, record, ctx):
        state, data = ctx["state"], record.data
        intent = data["intent"]
        if not isinstance(intent, list) or not intent:
            raise RuntimeError("planner step_ready requires non-empty data.intent list")
        for i, step in enumerate(intent):
            if (
                not isinstance(step, dict)
                or not isinstance(step.get("description"), str)
                or not step["description"].strip()
                or not isinstance(step.get("done_when"), str)
                or not step["done_when"].strip()
            ):
                raise RuntimeError(f"planner intent[{i}] requires non-empty description and done_when strings")
        next_step = intent[0]["description"]
        effective = bus.append_narrative(state["effective_goal"], f"\n\n[PLANNER] Authored {len(intent)} remaining steps. Next: {next_step}.", root_goal=state.get("goal", ""))
        return {
            "plan": data,
            "step": 0,
            "plan_complete": False,
            "reasoning": record.reasoning,
            "effective_goal": effective,
        }


def run(ctx):
    return PlannerNode().run(ctx)
