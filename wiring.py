"""Load endgame-ai topology from prompts/wiring.json — sole control-plane config."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CACHE: dict[str, Any] | None = None
_MTIME: float = 0.0


def load_wiring(prompts_dir: Path, *, force: bool = False) -> dict[str, Any]:
    """Load wiring.json. Reloads automatically when file mtime changes."""
    global _CACHE, _MTIME
    path = prompts_dir / "wiring.json"
    if not path.exists():
        raise FileNotFoundError(f"Required config missing: {path}")
    mtime = path.stat().st_mtime
    if not force and _CACHE is not None and mtime == _MTIME:
        return _CACHE
    data = json.loads(path.read_text(encoding="utf-8"))
    _validate(data)
    _CACHE = data
    _MTIME = mtime
    return data


def _validate(data: dict[str, Any]) -> None:
    for key in ("instance", "startup", "limits", "slots", "circuits", "transitions", "verbs", "guards"):
        if key not in data:
            raise ValueError(f"wiring.json missing section: {key}")
    if "role" not in data["instance"]:
        raise ValueError("wiring.json instance.role is required")
    if data["instance"]["role"] not in ("manager", "student"):
        raise ValueError("instance.role must be manager or student")
    startup = data["startup"]
    if startup.get("on_goal") != "route_to_slot":
        raise ValueError("startup.on_goal must be route_to_slot")
    slot = str(startup.get("slot", ""))
    if not slot:
        raise ValueError("startup.slot is required")
    enabled = {n for n, c in data["slots"].items() if c.get("enabled", True)}
    if slot not in enabled:
        raise ValueError(f"startup.slot '{slot}' is not an enabled slot")
    circuit = str(startup.get("circuit", ""))
    if circuit not in data["circuits"]:
        raise ValueError(f"startup.circuit '{circuit}' not in circuits")
    if "default" not in data["transitions"]:
        raise ValueError("transitions.default is required")
    valid_phases = set(data["circuits"]) | {"idle"}
    for event, target in data["transitions"].items():
        if event == "default":
            continue
        if target not in valid_phases:
            raise ValueError(f"transition {event} -> {target} invalid")
    if data["transitions"]["default"] not in data["circuits"]:
        raise ValueError("transitions.default must name a circuit")
    if "unified" not in data["guards"]:
        raise ValueError("guards.unified is required")
    for name, cfg in data["slots"].items():
        if not cfg.get("enabled", True):
            continue
        for req in ("can_desktop", "mode"):
            if req not in cfg:
                raise ValueError(f"slot '{name}' missing {req}")
    for name, cfg in data["circuits"].items():
        if "prompt" not in cfg or "inject" not in cfg:
            raise ValueError(f"circuit '{name}' needs prompt and inject")