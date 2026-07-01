from __future__ import annotations

import desktop


def run(ctx):
    """Observe the desktop and return observation data."""
    config = ctx.get("wiring", {}).get("observe_config", {})
    obs = desktop.observe(config)
    return "screen_ready", {
        "observation": obs,
        "screen": obs.get("screen"),
        "elements": obs.get("elements"),
        "snapshot": obs.get("snapshot"),
        "focused_title": obs.get("focused_title"),
    }