from __future__ import annotations

import brain


def run(ctx):
    wiring = ctx["wiring"]
    prompt = wiring.get("prompts", {}).get("planner", "Return JSON record_type plan")
    record = brain.think(prompt, {"goal": ctx.get("goal", ""), "state": ctx.get("state", {})}, wiring)
    if record.get("record_type") != "plan":
        raise RuntimeError(f"planner expected record_type plan, got {record.get('record_type')!r}")
    data = record.get("data", {})
    signal = str(data.get("next_signal") or "observe")
    return signal, {"plan": data, "reasoning": record.get("reasoning", "")}
