def run(board):
    """Comms operator: diagnose loop state and emit differentiated status report."""
    goal = board.get("goal", "")
    history = board.get("recent_history", [])
    reflection = board.get("reflection", {})

    # Detect duplicate-denial loop
    denied_count = sum(1 for h in history if isinstance(h, dict) and "denied" in h)

    if denied_count >= 2:
        # Break the loop: emit a status report instead of re-routing
        status = {
            "mode": "status_report",
            "system_state": "loop-breaking",
            "current_activity": "System detected self-referential goal causing duplicate routing. Comms operator is emitting a differentiated diagnostic instead of re-routing.",
            "diagnosis": reflection.get("diagnosis", "Routing loop detected"),
            "resolution": "Requesting human clarification on which specific code files or behaviors need fixing. Meanwhile, notepad status has been queued.",
            "notepad_content": f"[SYSTEM STATUS] Goal: {goal} | State: reflecting+replanning | Loop broken at denial #{denied_count} | Awaiting concrete error targets from human.",
            "done_when": "Status report emitted and loop broken"
        }
        return status

    # Normal routing (first attempt only)
    return {
        "mode": "route",
        "routes": [
            {"to": "architect", "reason": "replan strategy", "goal": "identify concrete code problems"},
            {"to": "implementor", "reason": "write status", "goal": "open notepad and display system state"}
        ],
        "done_when": "Status report emitted and loop broken"
    }
