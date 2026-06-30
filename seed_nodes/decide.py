from __future__ import annotations

import brain


def run(ctx):
    wiring = ctx["wiring"]
    prompt = wiring.get("prompts", {}).get("decide", "Return JSON record_type decision")
    record = brain.think(prompt, {"goal": ctx.get("goal", ""), "state": ctx.get("state", {})}, wiring)
    if record.get("record_type") != "decision":
        raise RuntimeError(f"decide expected record_type decision, got {record.get('record_type')!r}")
    data = record.get("data", {})
    signal = str(data.get("next_signal") or "act")
    return signal, {"decision": data, "pending_action": data.get("action", {"verb": "noop"})}
