from __future__ import annotations

import core_bus as bus
import core_desktop as desktop


def run(ctx):
    config = ctx["wiring"]["observe_config"]
    obs = desktop.get_desktop(config).observe(config)
    artifact = obs.get("observation_artifact", {}) or {}
    fresh = {"desktop_tree_text": obs.get("desktop_tree_text", ""), "observed_at": obs.get("observed_at"), "fresh_scan": obs.get("fresh_scan", True), "scan_config": artifact.get("scan_config", {}), "scan_stats": artifact.get("scan_stats", {}), "rendered_node_count": obs.get("rendered_node_count"), "max_llm_nodes": obs.get("max_llm_nodes"), "llm_node_limit_hit": obs.get("llm_node_limit_hit")}
    patch = {"observed_at": obs.get("observed_at"), "desktop_tree": obs.get("desktop_tree", {}), "desktop_tree_text": obs.get("desktop_tree_text", ""), "action_index": obs.get("action_index", {}), "fresh_scan": obs.get("fresh_scan"), "observation_artifact": obs.get("observation_artifact", {}), "rendered_node_count": obs.get("rendered_node_count"), "max_llm_nodes": obs.get("max_llm_nodes"), "llm_node_limit_hit": obs.get("llm_node_limit_hit"), "fresh_observation": fresh}
    return bus.emit("initial_screen" if not ctx.get("state", {}).get("plan") else "screen_ready", patch, evidence={"fresh_scan": obs.get("fresh_scan"), "scan_stats": fresh.get("scan_stats")})
