from __future__ import annotations

import brain


def run(ctx):
    wiring = ctx["wiring"]
    prompt = wiring.get("prompts", {}).get("reflect", "Return JSON record_type reflection")
    record = brain.think(prompt, {"goal": ctx.get("goal", ""), "state": ctx.get("state", {})}, wiring)
    if record.get("record_type") != "reflection":
        raise RuntimeError(f"reflect expected record_type reflection, got {record.get('record_type')!r}")
    data = record.get("data", {})
    signal = str(data.get("next_signal") or "planner")
    return signal, {"reflection": data}
