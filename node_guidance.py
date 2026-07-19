"""[node_guidance] — Thou receivest the [guidance] file."""
import core_bus as bus
import core_wiring as wiring


def run(ctx):
    path = wiring.root_path(ctx["wiring"]["paths"]["guidance"])
    counsel = path.read_text(encoding="utf-8").strip() if path.exists() else ""
    if not counsel:
        return bus.emit("attend", {"latest_counsel": ""})
    path.write_text("", encoding="utf-8")
    return bus.emit("attend", {"latest_counsel": counsel})
