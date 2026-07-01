"""Hot-swappable node loader and one-node execution chokepoint."""
from __future__ import annotations

import importlib.util
import pathlib
import shutil
from abc import ABC, abstractmethod
from typing import Any

import brain
import desktop

ROOT = pathlib.Path(__file__).parent.resolve()


def _path(wiring: dict[str, Any], key: str, default: str) -> pathlib.Path:
    return brain.root_path(wiring.get("paths", {}).get(key), default)


def ensure_live_nodes(wiring: dict[str, Any]) -> None:
    seed_dir = _path(wiring, "seed_nodes", "seed_nodes")
    live_dir = _path(wiring, "live_nodes", "live_nodes")
    if not seed_dir.exists():
        raise RuntimeError(f"missing seed_nodes directory: {seed_dir}")
    live_dir.mkdir(parents=True, exist_ok=True)
    for src in seed_dir.glob("*.py"):
        dst = live_dir / src.name
        if not dst.exists() or src.read_bytes() != dst.read_bytes():
            shutil.copy2(src, dst)


def _load_node(node_name: str, wiring: dict[str, Any]):
    live_dir = _path(wiring, "live_nodes", "live_nodes")
    path = live_dir / f"{node_name}.py"
    if not path.exists():
        raise RuntimeError(f"topology node '{node_name}' has no live module at {path}")
    spec = importlib.util.spec_from_file_location(f"endgame_live_node_{node_name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load node module: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    if not hasattr(mod, "run"):
        raise RuntimeError(f"node '{node_name}' does not export run(ctx)")
    return mod


class BaseNode(ABC):
    """Base class for nodes that call brain.think() with a prompt from wiring.json.
    
    Subclasses only need to define:
    - prompt_key: key in wiring["prompts"] (e.g., "planner", "decide")
    - expected_record_type: expected record_type in brain response (e.g., "plan", "decision")
    - signal_from_data(): extracts next_signal from record["data"]
    - patch_from_record(): builds patch dict from record
    """
    
    prompt_key: str = ""
    expected_record_type: str = ""
    
    @abstractmethod
    def signal_from_data(self, data: dict[str, Any]) -> str:
        """Extract next_signal from record data."""
        ...
    
    @abstractmethod
    def patch_from_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """Build patch dict from full record."""
        ...
    
    def run(self, ctx: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        wiring = ctx["wiring"]
        prompt = wiring.get("prompts", {}).get(self.prompt_key, "")
        record = brain.think(prompt, {"goal": ctx.get("goal", ""), "state": ctx.get("state", {})}, wiring)
        if record.get("record_type") != self.expected_record_type:
            raise RuntimeError(f"{self.prompt_key} expected record_type {self.expected_record_type!r}, got {record.get('record_type')!r}")
        data = record.get("data", {})
        signal = self.signal_from_data(data)
        patch = self.patch_from_record(record)
        return signal, patch


def call_node(node_name: str, ctx: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    wiring = ctx["wiring"]
    ensure_live_nodes(wiring)
    mod = _load_node(node_name, wiring)
    result = mod.run(ctx)
    if not isinstance(result, tuple) or len(result) != 2:
        raise RuntimeError(f"node '{node_name}' contract violation: expected (signal, patch)")
    signal, patch = result
    if not isinstance(signal, str) or not signal:
        raise RuntimeError(f"node '{node_name}' contract violation: signal must be a non-empty string")
    if not isinstance(patch, dict):
        raise RuntimeError(f"node '{node_name}' contract violation: patch must be dict")
    return signal, patch


def topology_summary(wiring: dict[str, Any]) -> dict[str, Any]:
    topo = wiring.get("topology", {})
    return {
        "cycle_start": topo.get("cycle_start"),
        "nodes": list(topo.get("nodes", [])),
        "edges": topo.get("edges", {}),
    }


# =============================================================================
# Desktop observation helpers for nodes
# =============================================================================


def observe_screen(ctx: dict[str, Any] | None = None) -> dict[str, int]:
    """Get screen dimensions."""
    return desktop.observe_screen()


def last_observation_snapshot(ctx: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Get the last full observation snapshot."""
    return desktop.last_observation_snapshot()


def get_focused_title(ctx: dict[str, Any] | None = None) -> str:
    """Get the title of the currently focused window."""
    return desktop.get_focused_title()