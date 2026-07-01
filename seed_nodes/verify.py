from __future__ import annotations

import brain
import json


def run(ctx):
    """Verify node: LLM judges if step intent was satisfied based on evidence."""
    state = ctx.get("state", {})
    wiring = ctx.get("wiring", {})
    goal = ctx.get("goal", "")
    
    # Get current step
    step = state.get("current_step") or {}
    step_goal = step.get("description", goal)
    done_when = step.get("done_when", "")
    
    # Evidence from state
    screen_text = state.get("screen_text", "")
    elements = state.get("elements", {})
    windows = state.get("windows", [])
    focused_title = state.get("focused_title", "")
    last_action = state.get("last_action", {})
    last_result = state.get("last_result", "")
    last_error = state.get("last_error", "")
    
    # Build prompt for LLM
    prompt = f"""You are the VERIFY node of endgame-ai. Judge if the step intent was satisfied based on evidence.

GOAL: {goal}
STEP: {step_goal}
DONE WHEN: {done_when or "not specified"}

EVIDENCE:
- FOCUSED WINDOW: {focused_title}
- SCREEN: {screen_text[:4000] if screen_text else "empty"}

LAST ACTION:
{json.dumps(last_action, indent=2)[:2000] if last_action else "none"}

LAST RESULT: {str(last_result)[:1000] if last_result else "none"}
LAST ERROR: {last_error or "none"}

Return JSON with:
- next_signal: "step_confirmed" (success) or "step_denied" (failure)
- success: true/false
- reasoning: brief evidence-based justification
"""

    record = brain.think(
        system_prompt=wiring.get("prompts", {}).get("verify", ""),
        payload={"prompt": prompt, "goal": goal, "state": state},
        wiring=wiring
    )
    
    if record.get("record_type") != "verification":
        raise RuntimeError(f"verify expected record_type=verification, got {record.get('record_type')}")
    
    data = record.get("data", {})
    signal = data.get("next_signal", "step_denied")
    success = data.get("success", False)
    
    # Ensure valid signal
    if signal not in ("step_confirmed", "step_denied"):
        signal = "step_denied"
        success = False
    
    return signal, {
        "verification": {
            "success": success,
            "reasoning": data.get("reasoning", ""),
            "step_goal": step_goal,
            "done_when": done_when,
        },
        "last_verification": {"success": success, "signal": signal},
    }