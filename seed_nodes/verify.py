from __future__ import annotations

import brain


def run(ctx):
    wiring = ctx["wiring"]
    prompt = wiring.get("prompts", {}).get("verify", "Return JSON record_type verification")
    record = brain.think(prompt, {"goal": ctx.get("goal", ""), "state": ctx.get("state", {})}, wiring)
    if record.get("record_type") != "verification":
        raise RuntimeError(f"verify expected record_type verification, got {record.get('record_type')!r}")
    data = record.get("data", {})
    signal = str(data.get("next_signal") or "planner")
    return signal, {"verification": data}
