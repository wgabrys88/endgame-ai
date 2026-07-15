"""[node_observe] — Thou takest one fresh sight of the [UI], and layest its compact tree and its ephemeral [action_index] before the node that cometh after."""
import core_bus as bus


def run(ctx):
    import core_desktop as desktop
    config = ctx["wiring"]["observe_config"]
    obs = desktop.get_desktop(config).observe(config)
    patch = {"observed_at": obs.get("observed_at"), "desktop_tree_text": obs.get("desktop_tree_text", ""), "action_index": obs.get("action_index", {}), "observation_artifact": obs.get("observation_artifact", {})}
    return bus.emit("observed", patch)
