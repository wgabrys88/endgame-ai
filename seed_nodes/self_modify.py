from __future__ import annotations

import json
import pathlib


def run(ctx):
    # Minimal safe chokepoint: self-modification is wiring-defined, but this seed node
    # does not invent changes. A live hot-swapped node may perform deliberate edits.
    return "planner", {"self_modify": {"status": "no_change", "reason": "seed node does not modify wiring without an explicit live replacement"}}
