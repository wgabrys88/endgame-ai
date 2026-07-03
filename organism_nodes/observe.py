from __future__ import annotations

import desktop


def run(ctx):
    """Observe the desktop using fresh hover-aware scan and return the screen-rooted tree."""
    config = ctx.get("wiring", {}).get("observe_config", {})
    obs = desktop.observe(config)
    return "screen_ready", {
        "observed_at": obs.get("observed_at"),
        "desktop_tree_text": obs.get("desktop_tree_text", ""),
        "focused_title": obs.get("focused_title"),
        "fresh_scan": obs.get("fresh_scan"),
    }
