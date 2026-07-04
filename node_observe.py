from __future__ import annotations

import core_bus as bus
import core_desktop as desktop


DATASHEET = bus.datasheet(
    "node_observe",
    kind="desktop_sensor",
    inputs=["wiring.observe_config"],
    signals=["screen_ready", "initial_screen", "error"],
    writes=[
        "observed_at",
        "desktop_tree",
        "desktop_tree_text",
        "action_index",
        "focused_title",
        "fresh_scan",
        "observation_artifact",
        "fresh_observation",
    ],
    record_type=None,
)


def run(ctx):
    """Gather desktop UIA data, filter once, emit the observation packet."""
    config = ctx.get("wiring", {}).get("observe_config", {})
    obs = desktop.observe(config)
    fresh_observation = {
        "focused_title": obs.get("focused_title", ""),
        "desktop_tree_text": obs.get("desktop_tree_text", ""),
        "observed_at": obs.get("observed_at"),
        "fresh_scan": obs.get("fresh_scan", True),
    }
    patch = {
        "observed_at": obs.get("observed_at"),
        "desktop_tree": obs.get("desktop_tree", {}),
        "desktop_tree_text": obs.get("desktop_tree_text", ""),
        "action_index": obs.get("action_index", {}),
        "focused_title": obs.get("focused_title"),
        "fresh_scan": obs.get("fresh_scan"),
        "observation_artifact": obs.get("observation_artifact", {}),
        "fresh_observation": fresh_observation,
    }
    signal = "initial_screen" if not ctx.get("state", {}).get("plan") else "screen_ready"
    return bus.emit(signal, patch, evidence={"focused_title": obs.get("focused_title"), "fresh_scan": obs.get("fresh_scan")})