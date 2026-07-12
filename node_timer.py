"""node_timer — time awareness, not a kill switch.

The organism is never force-stopped by a timer anymore (that once interrupted a
self-modification mid-flight). Instead this node computes the current wall-clock
time and the target deadline and injects a plain-language budget line into the
narrative so the LLM can decide for itself when to converge, wrap up, or halt.

deadline_at is set by core_organism from --duration-seconds (informational). If
there is no deadline, the node still reports the current time and elapsed budget.
Emits "tick" to continue the wheel.
"""
import time

import core_bus as bus


def run(ctx):
    state = ctx["state"]
    now = time.time()
    started_at = state.get("started_at")
    deadline_at = state.get("deadline_at")
    elapsed = round(now - float(started_at), 1) if started_at is not None else None
    now_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))

    if deadline_at is not None:
        remaining = round(float(deadline_at) - now, 1)
        deadline_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(deadline_at)))
        line = (
            f"\n\n[TIMER] Now {now_str}. Target deadline {deadline_str} "
            f"(~{remaining}s remaining, {elapsed}s elapsed). Manage the budget yourself: "
            "converge, verify, and reach node_satisfied before the deadline. The system is not "
            "force-killed by this clock; only an explicit stop request halts you."
        )
    else:
        line = f"\n\n[TIMER] Now {now_str} ({elapsed}s elapsed). No deadline set; pace yourself."

    effective = bus.append_narrative(state["effective_goal"], line, root_goal=state.get("goal", ""))
    return bus.emit("tick", {"effective_goal": effective, "timer": {"now": now, "deadline_at": deadline_at, "remaining_seconds": (round(float(deadline_at) - now, 1) if deadline_at is not None else None), "elapsed_seconds": elapsed}})
