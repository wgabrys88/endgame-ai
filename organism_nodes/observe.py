from __future__ import annotations

import desktop


def run(ctx):
    """Observe the desktop using hover_scan as primary method, return filtered elements."""
    config = ctx.get("wiring", {}).get("observe_config", {})
    obs = desktop.observe(config)
    return "screen_ready", {
        "screen": obs.get("screen"),
        "elements": obs.get("elements"),  # dict keyed by element_id
        "screen_text": obs.get("screen_text"),
        "windows": obs.get("windows"),
        "snapshot": obs.get("snapshot"),
        "focused_title": obs.get("focused_title"),
    }