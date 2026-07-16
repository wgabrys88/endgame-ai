import json
import os
import pathlib
import subprocess
import sys
import time
import hashlib
from typing import Any

import core_brain as brain
import core_bus as bus

ROOT = pathlib.Path(__file__).parent.resolve()



def _action_index(state: dict[str, Any]) -> dict[str, Any]:
    index = state.get("action_index") or {}
    return index if isinstance(index, dict) else {}


def build_capability_runtime(ctx: dict[str, Any], *, read_only: bool = False) -> dict[str, Any]:
    """Build the capability namespace appointed to actor or witness."""
    import core_desktop as desktop
    d = desktop.get_desktop()
    state = ctx.get("state", {})
    w = ctx.get("wiring", {})
    action_index = _action_index(state)

    def consult_model(prompt: str) -> dict[str, Any]:
        text = str(prompt).strip()
        if not text:
            raise RuntimeError("consult_model requires a non-empty prompt")
        result = brain.call([{"role": "user", "content": text}], w)
        return {"ok": True, "action": "consult_model", "response": str(result["content"])}

    ns = {
        "action_index": action_index,
        "consult_model": consult_model,
        "subprocess": subprocess,
        "os": os, "sys": sys, "json": json, "time": time, "pathlib": pathlib, "hashlib": hashlib,
        "repo_root": str(ROOT), "python_executable": sys.executable,
        "state": state, "wiring": w, "goal": ctx.get("goal", ""),
        "desktop_tree_text": state.get("desktop_tree_text", ""),
        "screen_elements": state.get("screen_elements", []),
        "observation": bus.observation_brief(state),
        "observed_at": state.get("observed_at"),
    }
    if read_only:
        ns["observe"] = d.observe
        ns["expand"] = d.expand
    else:
        ns["desktop"] = d
    return ns
