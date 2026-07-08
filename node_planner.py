from __future__ import annotations

import core_bus as bus
from core_node_base import BaseNode


DATASHEET = bus.datasheet(
    "node_planner",
    kind="llm_intent_decomposer",
    inputs=["goal", "state_brief", "fresh_observation", "previous_plan", "completed_steps", "last_reflection"],
    signals=["step_ready", "reflect", "error"],
    writes=["plan", "root_plan_intent", "reasoning"],
    record_type="plan",
)


class PlannerNode(BaseNode):
    prompt_key = "node_planner"
    expected_record_type = "plan"

    def build_payload(self, ctx):
        state = ctx.get("state", {})
        prior_plan_obj = state.get("plan") if isinstance(state.get("plan"), dict) else {}
        prior_intent = prior_plan_obj.get("intent", []) if isinstance(prior_plan_obj, dict) else []
        root_intent = state.get("root_plan_intent") or prior_intent
        completed_steps = state.get("completed_steps") or []
        if not isinstance(completed_steps, list):
            completed_steps = []
        remaining_count = max(0, len(root_intent if isinstance(root_intent, list) else []) - len(completed_steps))
        return {
            "goal": ctx.get("goal", ""),
            "state": bus.state_brief(state),
            "fresh_observation": state.get("fresh_observation") or bus.observation_brief(state),
            "previous_plan": prior_plan_obj,
            "root_plan_intent": root_intent,
            "completed_steps": completed_steps,
            "remaining_root_obligation_count": remaining_count,
            "last_reflection": state.get("last_reflection", {}),
            "replan_contract": (
                "When replanning, emit a complete remaining plan for the whole original goal. "
                "Do not emit only the failed/current step unless all other root goal obligations are complete."
            ),
        }

    def signal_from_data(self, data, ctx):
        signal = data.get("next_signal")
        if signal not in {"step_ready", "reflect"}:
            raise RuntimeError(f"planner emitted invalid next_signal: {signal!r}")
        self._signal = signal
        return signal

    def patch_from_record(self, record, ctx):
        state = ctx.get("state", {})
        data = record.data
        if getattr(self, "_signal", None) == "reflect":
            return {
                "last_error": "planner requested reflect",
                "reasoning": record.reasoning,
            }
        intent = data.get("intent")
        if not isinstance(intent, list) or not intent:
            raise RuntimeError("planner step_ready requires non-empty data.intent list")
        for index, step in enumerate(intent):
            if not isinstance(step, dict):
                raise RuntimeError(f"planner intent[{index}] must be object")
            if not isinstance(step.get("description"), str) or not isinstance(step.get("done_when"), str):
                raise RuntimeError(f"planner intent[{index}] requires string description and done_when")

        root_intent = state.get("root_plan_intent")
        if not isinstance(root_intent, list) or not root_intent:
            root_intent = list(intent)
        completed_steps = state.get("completed_steps") or []
        if not isinstance(completed_steps, list):
            completed_steps = []
        is_replan = bool(state.get("plan")) and (state.get("last_reflection") or {}).get("signal") == "replan"
        remaining_root = max(0, len(root_intent) - len(completed_steps))
        if is_replan and len(intent) < remaining_root:
            raise RuntimeError(
                "planner replan amputated root goal obligations: "
                f"new_intent={len(intent)} remaining_root_obligations={remaining_root}"
            )
        
        # Rewrite goal for next nodes based on current plan
        effective_goal = ctx.get("goal", "")
        if intent:
            step_descs = [s.get("description", "") for s in intent if isinstance(s, dict)]
            effective_goal = f"{effective_goal}\n\n[PLANNER REWRITE] Current plan focuses on: {'; '.join(step_descs[:3])}. Next: {step_descs[0] if step_descs else 'no steps'}."
        
        return {
            "plan": data,
            "root_plan_intent": root_intent,
            "step": 0,
            "plan_complete": False,
            "reasoning": record.reasoning,
            "effective_goal": effective_goal,
        }


def run(ctx):
    return PlannerNode().run(ctx)
