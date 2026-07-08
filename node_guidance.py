import core_bus as bus
import core_wiring as wiring


def run(ctx):
    """Fold any workspace guidance file into the narrative as a strong but ignorable signal.

    A human or another organism steers by writing text into the guidance file
    (paths.guidance). This node reads it and folds it into effective_goal as a
    clearly-tagged, high-signal event — guidance, not control. The node-group
    decides what to do with it; it may be embraced or ignored. Never truncated.
    Reading is one-shot per write: the file is consumed (unlinked) so the same
    guidance does not re-inject on every turn — only fresh writes bend the wheel.
    """
    state = ctx["state"]
    path = wiring.guidance_path(ctx["wiring"])
    effective = state["effective_goal"]
    if not path.exists():
        return bus.emit("attend", {"effective_goal": effective + "\n\n[GUIDANCE] No new counsel from without; the wheel turns on."})
    counsel = path.read_text(encoding="utf-8").strip()
    path.unlink()
    return bus.emit("attend", {
        "guidance_received": counsel,
        "effective_goal": effective + f"\n\n[GUIDANCE] A voice from without speaks (heed or not, as the goal demands): {counsel}",
    })
