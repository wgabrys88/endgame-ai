"""node_observe — take one fresh UI observation and expose its compact tree and ephemeral action index to the next node."""
import core_bus as bus


def run(ctx):
    import core_desktop as desktop
    config = ctx["wiring"]["observe_config"]
    obs = desktop.get_desktop(config).observe(config)
    artifact = obs.get("observation_artifact", {}) or {}
    observation = {"desktop_tree_text": obs.get("desktop_tree_text", ""), "observed_at": obs.get("observed_at"), "scan_config": artifact.get("scan_config", {}), "screen": artifact.get("screen", {}), "scan_stats": artifact.get("scan_stats", {}), "rendered_node_count": obs.get("rendered_node_count"), "max_llm_nodes": obs.get("max_llm_nodes"), "llm_node_limit_hit": obs.get("llm_node_limit_hit")}
    patch = {"observed_at": obs.get("observed_at"), "desktop_tree_text": obs.get("desktop_tree_text", ""), "action_index": obs.get("action_index", {}), "observation_artifact": obs.get("observation_artifact", {}), "rendered_node_count": obs.get("rendered_node_count"), "max_llm_nodes": obs.get("max_llm_nodes"), "llm_node_limit_hit": obs.get("llm_node_limit_hit")}
    return bus.emit("observed", patch, evidence={"screen": observation.get("screen"), "scan_stats": observation.get("scan_stats")})
