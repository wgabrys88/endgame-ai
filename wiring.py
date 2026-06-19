"""Load endgame topology from prompts/wiring.drawio — single unified format, hot-reload."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from topology import read_drawio, write_drawio

_CACHE: dict[str, Any] | None = None
_MTIME: float = 0.0
WIRING_FILE = "wiring.drawio"


def wiring_path(prompts_dir: Path) -> Path:
    return prompts_dir / WIRING_FILE


def load_wiring(prompts_dir: Path, *, force: bool = False) -> dict[str, Any]:
    """Load from wiring.drawio only. Reloads when file mtime changes."""
    global _CACHE, _MTIME
    path = wiring_path(prompts_dir)
    legacy = prompts_dir / "wiring.json"
    if not path.exists() and legacy.exists():
        data = json.loads(legacy.read_text(encoding="utf-8"))
        _validate(data)
        _resolve_context_templates(data)
        write_drawio(data, path)
    if not path.exists():
        raise FileNotFoundError(f"Required config missing: {path}")
    mtime = path.stat().st_mtime
    if not force and _CACHE is not None and mtime == _MTIME:
        return _CACHE
    data = read_drawio(path)
    _validate(data)
    _resolve_context_templates(data)
    _CACHE = data
    _MTIME = mtime
    return data


def save_wiring(prompts_dir: Path, data: dict[str, Any]) -> Path:
    """Write unified wiring.drawio (topology + embedded config)."""
    _validate(data)
    path = wiring_path(prompts_dir)
    write_drawio(data, path)
    global _CACHE, _MTIME
    _CACHE = data
    _MTIME = path.stat().st_mtime
    return path


def _resolve_context_templates(data: dict[str, Any]) -> None:
    ctx = data.get("context", {})
    blocks = data.get("request", {}).get("unified", {}).get("user", {}).get("blocks", [])
    for block in blocks:
        if block.get("id") == "screen" and block.get("empty_template") == "{screen_empty}":
            block["empty_template"] = ctx.get("screen_empty", "")


def _validate(data: dict[str, Any]) -> None:
    if data.get("schema") != "endgame-topology/v1":
        raise ValueError("wiring schema must be endgame-topology/v1")
    for key in ("instance", "startup", "limits", "slots", "circuits", "transitions",
                "verbs", "topology", "request", "response", "feedback", "runtime"):
        if key not in data:
            raise ValueError(f"wiring missing section: {key}")
    if data["instance"]["role"] not in ("manager", "student"):
        raise ValueError("instance.role must be manager or student")
    slot = str(data["startup"].get("slot", ""))
    enabled = {n for n, c in data["slots"].items() if c.get("enabled", True)}
    if slot not in enabled:
        raise ValueError(f"startup.slot '{slot}' not enabled")
    if "default" not in data["transitions"]:
        raise ValueError("transitions.default required")
    valid = set(data["circuits"]) | {"idle"}
    for event, target in data["transitions"].items():
        if event != "default" and target not in valid:
            raise ValueError(f"invalid transition {event} -> {target}")
    if "unified" not in data["response"]:
        raise ValueError("response.unified required")
    if "unified" not in data["request"]:
        raise ValueError("request.unified required")
    topo = data["topology"]
    if not topo.get("nodes") or not topo.get("edges"):
        raise ValueError("topology.nodes and topology.edges required")


def main() -> int:
    """CLI: python wiring.py save | python wiring.py json (dump config to stdout)."""
    prompts = Path(__file__).parent / "prompts"
    if len(sys.argv) < 2:
        print("Usage: python wiring.py json | save", file=sys.stderr)
        return 1
    cmd = sys.argv[1]
    if cmd == "json":
        data = load_wiring(prompts, force=True)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    if cmd == "save":
        data = load_wiring(prompts, force=True)
        path = save_wiring(prompts, data)
        print(f"Wrote {path}")
        return 0
    print(f"Unknown command: {cmd}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())