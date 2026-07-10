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
            "replan_contract": "Emit the complete remaining plan for the immutable root goal. A replan may change step count and granularity; preserve obligations by meaning, not by matching the old number of steps.",
        }

    def signal_from_data(self, data, ctx):
        return data["next_signal"]

    def patch_from_record(self, record, ctx):
        state, data = ctx["state"], record.data
        intent = data["intent"]
        if not isinstance(intent, list) or not intent:
            raise RuntimeError("planner step_ready requires non-empty data.intent list")
        for i, step in enumerate(intent):
            if not isinstance(step, dict) or not isinstance(step.get("description"), str) or not step["description"].strip() or not isinstance(step.get("done_when"), str) or not step["done_when"].strip():
                raise RuntimeError(f"planner intent[{i}] requires non-empty description and done_when strings")
        next_step = intent[0]["description"]
        effective = state["effective_goal"] + f"\n\n[PLANNER] Authored {len(intent)} remaining steps. Next: {next_step}."
        return {"plan": data, "step": 0, "plan_complete": False, "reasoning": record.reasoning, "effective_goal": effective}


def run(ctx):
    return PlannerNode().run(ctx)