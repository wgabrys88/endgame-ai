"""[node_guidance] — Thou foldest the counsel of the human into the wheel. THOU EXPECTEST: to read the [guidance] file. Thou emittest 'attend' to go on, setting any counsel as [latest_counsel] for the faculties to heed or refuse."""
import core_bus as bus
import core_wiring as wiring


def run(ctx):
    state = ctx["state"]
    path = wiring.guidance_path(ctx["wiring"])
    counsel = path.read_text(encoding="utf-8").strip() if path.exists() else ""
    if not counsel:
        return bus.emit("attend", {"latest_counsel": ""})
    path.write_text("", encoding="utf-8")
    return bus.emit("attend", {"latest_counsel": counsel})
