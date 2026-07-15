"""[node_guidance] — Thou foldest the counsel of the human into the wheel. THOU EXPECTEST: the [effective_goal] (and thou readest the [guidance] file). Thou emittest 'attend' to go on, joining any counsel unto the narrative."""
import core_bus as bus
import core_wiring as wiring


def run(ctx):
    state = ctx["state"]
    path = wiring.guidance_path(ctx["wiring"])
    counsel = path.read_text(encoding="utf-8").strip() if path.exists() else ""
    if not counsel:
        return bus.emit("attend")
    path.write_text("", encoding="utf-8")
    effective = bus.append_narrative(state["effective_goal"], f"\n\n[GUIDANCE] Counsel from the human, to heed or to refuse as the goal demandeth: {counsel}", root_goal=state.get("goal", ""))
    return bus.emit("attend", {"effective_goal": effective})
