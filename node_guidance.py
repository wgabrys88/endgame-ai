import core_bus as bus
import core_wiring as wiring


def run(ctx):
    state = ctx["state"]
    path = wiring.guidance_path(ctx["wiring"])
    counsel = path.read_text(encoding="utf-8").strip() if path.exists() else ""
    if not counsel:
        return bus.emit("attend")
    path.write_text("", encoding="utf-8")
    effective = state["effective_goal"] + f"\n\n[GUIDANCE] External counsel, to heed or refuse as the goal demands: {counsel}"
    return bus.emit("attend", {"effective_goal": effective})
