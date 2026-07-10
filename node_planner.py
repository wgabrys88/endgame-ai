import core_bus as bus
from core_node_base import BaseNode


class PlannerNode(BaseNode):
    prompt_key = "node_planner"
    expected_record_type = "plan"

    def build_payload(self, ctx):
        state = ctx.get("state", {})
        prior = state.get("plan") if isinstance(state.get("plan"), dict) else {}
        prior_intent = prior.get("intent", []) if isinstance(prior, dict) else []
        root_intent = state.get("root_plan_intent") or prior_intent
        completed = state.get("completed_steps") if isinstance(state.get("completed_steps"), list) else []
        return {"goal": ctx.get("goal", ""), "state": bus.state_brief(state), "observation": bus.observation_brief(state), "previous_plan": prior, "root_plan_intent": root_intent, "completed_steps": completed, "remaining_root_obligation_count": max(0, len(root_intent if isinstance(root_intent, list) else []) - len(completed)), "last_reflection": state.get("last_reflection", {}), "replan_contract": "Emit the complete remaining plan for the original goal; uncertainty becomes an executable evidence-gathering step."}

    def signal_from_data(self, data, ctx):
        return data["next_signal"]

    def patch_from_record(self, record, ctx):
        state, data = ctx.get("state", {}), record.data
        intent = data.get("intent")
        if not isinstance(intent, list) or not intent:
            raise RuntimeError("planner step_ready requires non-empty data.intent list")
        for i, step in enumerate(intent):
            if not isinstance(step, dict) or not isinstance(step.get("description"), str) or not step["description"].strip() or not isinstance(step.get("done_when"), str) or not step["done_when"].strip():
                raise RuntimeError(f"planner intent[{i}] requires non-empty description and done_when strings")
        root_intent = state.get("root_plan_intent") if isinstance(state.get("root_plan_intent"), list) and state.get("root_plan_intent") else list(intent)
        completed = state.get("completed_steps") if isinstance(state.get("completed_steps"), list) else []
        if bool(state.get("plan")) and (state.get("last_reflection") or {}).get("signal") == "replan" and len(intent) < max(0, len(root_intent) - len(completed)):
            raise RuntimeError("planner replan amputated root goal obligations")
        descs = [step["description"] for step in intent]
        effective = state["effective_goal"] + f"\n\n[PLANNER] Remaining plan: {'; '.join(descs)}. Next: {descs[0]}."
        return {"plan": data, "root_plan_intent": root_intent, "step": 0, "plan_complete": False, "reasoning": record.reasoning, "effective_goal": effective}


def run(ctx):
    return PlannerNode().run(ctx)
