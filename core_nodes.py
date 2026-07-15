import json
import os
import pathlib
import subprocess
import sys
import time
from typing import Any

import core_brain as brain
import core_bus as bus

ROOT = pathlib.Path(__file__).parent.resolve()



def _action_index(state: dict[str, Any]) -> dict[str, Any]:
    index = state.get("action_index") or {}
    return index if isinstance(index, dict) else {}


def build_capability_runtime(ctx: dict[str, Any]) -> dict[str, Any]:
    """Namespace a runner script executes in. There is no menu of tools: the [Python]
    language is the tool. The script hath the live [desktop] instance (its methods
    click/type_text/press_key/hotkey/scroll/open_url/observe drive the real machine),
    the [action_index] mapping each observed [id] to what it IS (its role, name,
    action, rect, hwnd), and the whole standard library. To strike an element the
    script readeth its geometry from [action_index] and calleth the [desktop] method
    itself. A script that raiseth faileth hard; a script that worketh no effect is
    judged by the witness upon fresh observation, not here."""
    import core_desktop as desktop
    d = desktop.get_desktop()
    state = ctx.get("state", {})
    w = ctx.get("wiring", {})
    action_index = _action_index(state)

    def consult_model(prompt: str, max_output_tokens: int = 800) -> dict[str, Any]:
        text = str(prompt).strip()
        if not text:
            raise RuntimeError("consult_model requires a non-empty prompt")
        result = brain.call([{"role": "user", "content": text}], w, request_config={"max_output_tokens": int(max_output_tokens), "plain_text": True})
        return {"ok": True, "action": "consult_model", "response": str(result["content"])}

    return {
        "desktop": d,
        "action_index": action_index,
        "consult_model": consult_model,
        "subprocess": subprocess,
        "os": os, "sys": sys, "json": json, "time": time, "pathlib": pathlib,
        "repo_root": str(ROOT), "python_executable": sys.executable,
        "state": state, "wiring": w, "goal": ctx.get("goal", ""),
        "desktop_tree_text": state.get("desktop_tree_text", ""),
        "observation": bus.observation_brief(state),
        "observed_at": state.get("observed_at"),
    }
