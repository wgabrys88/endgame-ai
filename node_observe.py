"""[node_observe] — Thou expectest the present state after the foregoing faculty."""
import core_bus as bus


def run(ctx):
    import core_desktop as desktop
    config = ctx["wiring"]["observe_config"]
    obs = desktop.get_desktop(config).observe(config)
    patch = {"observed_at": obs.get("observed_at"), "desktop_tree_text": obs.get("desktop_tree_text", ""), "action_index": obs.get("action_index", {}), "screen_elements": obs.get("screen_elements", []), "observation_artifact": obs.get("observation_artifact", {})}
    return bus.emit("observed", patch)
