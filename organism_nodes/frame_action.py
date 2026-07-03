from __future__ import annotations

import brain
import bus


DATASHEET = bus.datasheet(
    "frame_action",
    kind="llm_rod_framing_pass",
    inputs=["goal", "current_step", "last_action", "last_result", "last_error", "fresh_observation"],
    signals=["framed", "reflect", "error"],
    writes=["action_frame", "framing_attempted_for_step"],
    record_type="action_frame",
)


def run(ctx):
    """ROD/framing pass: turn raw screen chaos into a compact action strategy."""
    state = ctx.get("state", {})
    wiring = ctx.get("wiring", {})
    goal = ctx.get("goal", "")
    step = state.get("current_step") or {}
    step_index = int(state.get("step", 0) or 0)
    evidence = {
        "state": bus.state_brief(state),
        "last_action": state.get("last_action", {}),
        "last_result": state.get("last_result", ""),
        "last_error": state.get("last_error", ""),
    }

    record = brain.think(
        system_prompt=wiring.get("prompts", {}).get("frame_action", ""),
        payload={
            "goal": goal,
            "observation": bus.observation_brief(state),
            "step": {
                "description": step.get("description", goal),
                "done_when": step.get("done_when", ""),
            },
            "evidence": evidence,
        },
        wiring=wiring,
        expected_record_type="action_frame",
        request_config={"reasoning_effort": "low"},
    )
    if record.get("record_type") != "action_frame":
        raise RuntimeError(f"frame_action expected record_type=action_frame, got {record.get('record_type')}")

    data = record.get("data", {})
    signal = str(data.get("next_signal") or "framed")
    if signal not in {"framed", "reflect"}:
        signal = "framed"

    frame = {
        "screen_summary": data.get("screen_summary", ""),
        "target": data.get("target", ""),
        "strategy": data.get("strategy", ""),
        "risk": data.get("risk", "low"),
        "notes": data.get("notes", ""),
        "step_index": step_index,
    }
    return bus.emit(
        signal,
        {"action_frame": frame, "framing_attempted_for_step": step_index},
        record=record,
        evidence=evidence,
    )
