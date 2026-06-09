from __future__ import annotations
from typing import Any

from config import (
    STAGNATION_HALT_THRESHOLD, STAGNATION_HALT_SUSTAINED,
    REFLECT_THRESHOLD, SCREEN_STAGNATION_LOOKBACK,
)


class SchedulerAgent:
    name: str = "scheduler"
    reads: list[str] = [
        "stagnation_score", "lorenz_wing_crossed", "pid_output",
        "halt_count", "requested_next", "total_role_calls", "role_calls",
        "last_instruction", "goal",
        "screen_hash", "recent_hashes", "last_verb",
    ]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        stag = float(ctx.get("stagnation_score", 0))
        wing = bool(ctx.get("lorenz_wing_crossed", False))
        pid = float(ctx.get("pid_output", 0))
        halt_count = int(ctx.get("halt_count", 0))
        total_calls = int(ctx.get("total_role_calls", 0))
        role_calls: dict[str, int] = ctx.get("role_calls", {})
        requested = str(ctx.get("requested_next", ""))
        instruction = str(ctx.get("last_instruction", ""))
        goal = str(ctx.get("goal", ""))
        last_verb = str(ctx.get("last_verb", ""))

        writes: dict[str, Any] = {}

        if stag >= STAGNATION_HALT_THRESHOLD:
            new_halt = halt_count + 1
            if new_halt >= STAGNATION_HALT_SUSTAINED:
                writes["halt_count"] = new_halt
                return {"writes": writes, "next": "halt", "phase": "schedule", "data": {"reason": "halt", "stag": stag}}
            writes["halt_count"] = new_halt
        else:
            writes["halt_count"] = 0

        if wing:
            writes["lorenz_wing_crossed"] = False
            writes["plan_steps"] = []
            writes["plan_index"] = 0
            writes["consecutive_failures"] = 0
            writes["halt_count"] = 0
            writes["recent_sigs"] = []
            writes["repetition_score"] = 0.0
            writes["stagnation_score"] = 0.0
            writes["pid_integral"] = 0.0
            writes["notes"] = ["DIVERGE: previous approach failed. Try a completely different method."]
            writes["requested_next"] = ""
            return {"writes": writes, "next": "planner", "phase": "schedule", "data": {"reason": "wing_cross"}}

        if not goal:
            return {"writes": writes, "next": "stagnation", "phase": "schedule", "data": {"reason": "idle"}}

        if requested:
            writes["requested_next"] = ""
            return {"writes": writes, "next": requested, "phase": "schedule", "data": {"reason": "requested", "target": requested}}

        if total_calls == 0:
            return {"writes": writes, "next": "planner", "phase": "schedule", "data": {"reason": "initial"}}

        if pid > REFLECT_THRESHOLD and role_calls.get("reflector", 0) < total_calls * 0.15:
            return {"writes": writes, "next": "reflector", "phase": "schedule", "data": {"reason": "pid_gate", "pid": pid}}

        if not instruction:
            return {"writes": writes, "next": "planner", "phase": "schedule", "data": {"reason": "need_plan"}}

        if last_verb:
            screen_hash = str(ctx.get("screen_hash", ""))
            recent: list[str] = ctx.get("recent_hashes", [])
            if screen_hash and screen_hash not in recent[-SCREEN_STAGNATION_LOOKBACK:]:
                writes["jacobian_update"] = last_verb
            return {"writes": writes, "next": "planner", "phase": "schedule", "data": {"reason": "post_action"}}

        return {"writes": writes, "next": "planner", "phase": "schedule", "data": {"reason": "default"}}
