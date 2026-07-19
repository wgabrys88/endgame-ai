import copy
import glob
import json
import os
import pathlib
import platform
import shutil
import subprocess
import sys
import time
import hashlib
from typing import Any

import core_brain as brain
import core_bus as bus

ROOT = pathlib.Path(__file__).parent.resolve()


def _installed_apps() -> list[str]:
    roots = [
        os.path.join(os.environ.get("ProgramData", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
        os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
    ]
    names: set[str] = set()
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for lnk in glob.glob(os.path.join(root, "**", "*.lnk"), recursive=True):
            stem = pathlib.Path(lnk).stem.strip()
            if stem and not stem.lower().startswith(("uninstall", "readme", "help")):
                names.add(stem)
    return sorted(names)


def _host_facts() -> dict[str, Any]:
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "hostname": platform.node(),
        "user": os.environ.get("USERNAME") or os.environ.get("USER") or "",
        "cwd": os.getcwd(),
        "repo_root": str(ROOT),
        "python": f"{sys.executable} ({platform.python_version()})",
        "shell_tools": sorted(t for t in ("powershell", "pwsh", "cmd", "git", "pip", "node", "npm", "curl") if shutil.which(t)),
        "installed_apps": _installed_apps(),
    }


def explore(ctx: dict[str, Any]) -> None:
    import core_desktop as desktop
    config = ctx["wiring"]["exploration"]
    obs = desktop.get_desktop(config).observe(config)
    state = ctx["state"]
    state.update({
        "observed_at": obs.get("observed_at"),
        "desktop_tree_text": obs.get("desktop_tree_text", ""),
        "action_index": obs.get("action_index", {}),
        "screen_elements": obs.get("screen_elements", []),
        "observation_artifact": obs.get("observation_artifact", {}),
        "host_facts": _host_facts(),
    })


def _action_index(state: dict[str, Any]) -> dict[str, Any]:
    index = state.get("action_index") or {}
    return index if isinstance(index, dict) else {}


def build_capability_runtime(ctx: dict[str, Any], *, read_only: bool = False) -> dict[str, Any]:
    import core_desktop as desktop
    d = desktop.get_desktop()
    state = ctx.get("state", {})
    ns = {
        "subprocess": subprocess,
        "os": os, "sys": sys, "json": json, "time": time, "pathlib": pathlib, "hashlib": hashlib,
        "repo_root": str(ROOT), "python_executable": sys.executable,
        "desktop_tree_text": str(state.get("desktop_tree_text", "")),
        "screen_elements": copy.deepcopy(state.get("screen_elements", [])),
        "observation": copy.deepcopy(bus.environment_brief(state)),
        "observed_at": state.get("observed_at"),
    }
    if read_only:
        ns.update({"observe": d.observe})
        return ns

    w = ctx.get("wiring", {})

    def consult_model(prompt: str, profile: str | None = None) -> dict[str, Any]:
        text = str(prompt).strip()
        if not text:
            raise RuntimeError("consult_model requires a non-empty prompt")
        result = brain.call([{"role": "user", "content": text}], w, profile=profile)
        return {"ok": True, "action": "consult_model", "profile": profile, "response": str(result["content"])}

    ns.update({
        "desktop": d, "action_index": _action_index(state), "consult_model": consult_model,
        "state": state, "wiring": w, "goal": ctx.get("goal", ""),
    })
    return ns
