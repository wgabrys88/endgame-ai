from __future__ import annotations

import brain
import json


def run(ctx):
    """Reflect node: LLM diagnoses failure and chooses recovery route."""
    state = ctx.get("state", {})
    wiring = ctx.get("wiring", {})
    goal = ctx.get("goal", "")
    
    # Current step info
    step = state.get("current_step") or {}
    step_goal = step.get("description", goal)
    done_when = step.get("done_when", "")
    
    # Evidence
    screen_text = state.get("screen_text", "")
    elements = state.get("elements", {})
    focused_title = state.get("focused_title", "")
    last_action = state.get("last_action", {})
    last_result = state.get("last_result", "")
    last_error = state.get("last_error", "")
    last_verification = state.get("last_verification", {})
    
    # Build prompt for LLM
    prompt = f"""You are the REFLECT node of endgame-ai. The previous step failed. Diagnose the failure and choose recovery.

GOAL: {goal}
STEP: {step_goal}
DONE WHEN: {done_when or "not specified"}

EVIDENCE:
- FOCUSED WINDOW: {focused_title}
- SCREEN: {screen_text[:5000] if screen_text else "empty"}

LAST ACTION:
{json.dumps(last_action, indent=2)[:2000] if last_action else "none"}

LAST RESULT: {str(last_result)[:1000] if last_result else "none"}
LAST ERROR: {last_error or "none"}
VERIFICATION: {json.dumps(last_verification)}

RECOVERY OPTIONS:
- "retry": Same step, same approach (if transient error)
- "replan": Go back to planner for new plan (if wrong approach)
- "escalate": Go to self_modify to evolve code/wiring (if systemic issue)
- "give_up": Mark satisfied, end organism (if goal impossible)

Return JSON with:
- next_signal: "retry" | "replan" | "escalate" | "give_up"
- lesson: Concrete diagnosis + specific suggestion (what to change, what to try)
- diagnosis: Brief root cause
"""

    record = brain.think(
        system_prompt=wiring.get("prompts", {}).get("reflect", ""),
        payload={"prompt": prompt, "goal": goal, "state": state},
        wiring=wiring
    )
    
    if record.get("record_type") != "reflection":
        raise RuntimeError(f"reflect expected record_type=reflection, got {record.get('record_type')}")
    
    data = record.get("data", {})
    signal = data.get("next_signal", "replan")
    lesson = data.get("lesson", "No lesson provided")
    diagnosis = data.get("diagnosis", "No diagnosis")
    
    # Validate signal
    valid_signals = {"retry", "replan", "escalate", "give_up"}
    if signal not in valid_signals:
        signal = "replan"
    
    return signal, {
        "reflection": {
            "lesson": lesson,
            "diagnosis": diagnosis,
            "step_goal": step_goal,
            "recovery_signal": signal,
        },
        "last_reflection": {"signal": signal, "lesson": lesson},
    }