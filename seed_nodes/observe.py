from __future__ import annotations

import desktop


def run(ctx):
    obs = desktop.observe()
    return "decide", {"observation": obs}
