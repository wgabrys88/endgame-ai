"""Hot-swappable node loader and one-node execution chokepoint."""
from __future__ import annotations

import importlib.util
import json
import pathlib
import shutil
import subprocess
import sys
import time
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


# =============================================================================
# Execute namespace builder
# =============================================================================


def _get_desktop_instance():
    """Get the singleton Desktop instance."""
    return desktop.get_desktop()


def execute_verb(verb: str, target: dict[str, Any] | None = None, value: str | None = None) -> str:
    """Convenience verbs for common actions."""
    d = _get_desktop_instance()
    target = target or {}
    
    if verb == "click":
        x = target.get("px") or target.get("x")
        y = target.get("py") or target.get("y")
        hwnd = target.get("hwnd", 0)
        if x is not None and y is not None:
            d.click(x, y, hwnd)
            return f"clicked at ({x},{y})"
        return "click: missing x/y"
    
    elif verb == "write":
        text = value or target.get("text", "")
        d.type_text(text)
        return f"typed: {text}"
    
    elif verb == "press":
        key = value or target.get("key", "")
        d.press_key(key)
        return f"pressed: {key}"
    
    elif verb == "hotkey":
        keys = value or target.get("keys", "")
        d.hotkey(keys)
        return f"hotkey: {keys}"
    
    elif verb == "focus":
        target_str = value or target.get("title", "")
        d.focus_window(target_str)
        return f"focused: {target_str}"
    
    elif verb == "scroll":
        amount = target.get("amount", 3)
        direction = target.get("direction", "down")
        x = target.get("px", 0)
        y = target.get("py", 0)
        hwnd = target.get("hwnd", 0)
        d.scroll(x, y, amount if direction == "down" else -amount, hwnd)
        return f"scrolled {direction} {amount}"
    
    elif verb == "wait":
        wait_time = target.get("seconds", 1)
        time.sleep(wait_time)
        return f"waited {wait_time}s"
    
    elif verb == "launch":
        cmd = value or target.get("command", "")
        subprocess.Popen(cmd, shell=True)
        return f"launched: {cmd}"
    
    elif verb == "open_url":
        browser = target.get("browser", "chrome")
        url = value or target.get("url", "")
        if browser == "chrome":
            subprocess.Popen(["chrome", url])
        else:
            import webbrowser
            webbrowser.open(url)
        return f"opened {url} in {browser}"
    
    elif verb == "remember":
        key = target.get("key", "")
        val = value or target.get("value", "")
        return f"remembered {key}={val}"
    
    return f"unknown verb: {verb}"


def _live_node_target(wiring: dict[str, Any], raw_path: str) -> pathlib.Path:
    live_dir = _path(wiring, "live_nodes", "live_nodes").resolve()
    requested = pathlib.Path(raw_path)
    path = (ROOT / requested).resolve() if not requested.is_absolute() else requested.resolve()
    try:
        path.relative_to(live_dir)
    except ValueError as exc:
        raise ValueError(f"self_modify path must stay under {live_dir}: {raw_path}") from exc
    if path.suffix != ".py":
        raise ValueError(f"self_modify node path must be a .py file: {raw_path}")
    return path


def apply_wiring_patch(wiring: dict[str, Any], parsed: dict[str, Any]) -> tuple[str, Any]:
    """Apply wiring patches and node file writes from self_modify output."""
    data = (parsed or {}).get("data") or {}
    
    # 1. Apply wiring patches
    for patch in data.get("wiring_patches", []):
        op = patch.get("op", "set")
        path = patch.get("path", "")
        value = patch.get("value")
        if not path:
            raise ValueError("wiring_patch missing path")
        parts = path.split(".")
        cur = wiring
        for part in parts[:-1]:
            if not isinstance(cur.get(part), dict):
                cur[part] = {}
            cur = cur[part]
        if op == "set":
            cur[parts[-1]] = value
        elif op == "delete":
            cur.pop(parts[-1], None)
        else:
            raise ValueError(f"unknown op: {op}")
    
    # 2. Write node files
    for write in data.get("node_writes", []):
        path = _live_node_target(wiring, write["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(write["content"], encoding="utf-8")
    
    # 3. Delete node files
    for delete_path in data.get("node_deletes", []):
        _live_node_target(wiring, delete_path).unlink(missing_ok=True)
    
    # 4. Atomic write wiring.json
    save_wiring(wiring)
    
    return "set", {
        "wiring_patches": len(data.get("wiring_patches", [])),
        "node_writes": len(data.get("node_writes", [])),
        "node_deletes": len(data.get("node_deletes", [])),
    }


def save_wiring(wiring: dict[str, Any]) -> None:
    """Atomic write of wiring.json."""
    brain.atomic_write_json(ROOT / "wiring.json", wiring)


def wiring_limit(name: str, default: int, wiring: dict[str, Any]) -> int:
    """Get a limit from wiring with default."""
    return wiring.get("limits", {}).get(name, default)


def build_execute_namespace(ctx: dict[str, Any]) -> dict[str, Any]:
    """Build the namespace for execute node's exec()."""
    d = _get_desktop_instance()
    state = ctx.get("state", {})
    wiring = ctx.get("wiring", {})
    goal = ctx.get("goal", "")
    
    return {
        # Observation
        "observe_screen": observe_screen,
        "last_observation_snapshot": last_observation_snapshot,
        "get_focused_title": get_focused_title,
        
        # Convenience verbs
        "execute_verb": execute_verb,
        
        # Raw desktop actions
        "click": d.click,
        "type_text": d.type_text,
        "press_key": d.press_key,
        "hotkey": d.hotkey,
        "scroll": d.scroll,
        "focus_window": d.focus_window,
        "open_url": d.open_url,
        
        # System modules
        "subprocess": subprocess,
        "ctypes": ctypes,
        "os": __import__("os"),
        "sys": sys,
        "json": json,
        "re": __import__("re"),
        "time": time,
        "pathlib": pathlib,
        "math": __import__("math"),
        "random": __import__("random"),
        
        # Self-modification
        "apply_wiring_patch": apply_wiring_patch,
        "save_wiring": save_wiring,
        "wiring_limit": wiring_limit,
        
        # Context
        "state": state,
        "wiring": wiring,
        "goal": goal,
        "screen": state.get("screen", {}),
        "elements": state.get("elements", {}),
        "windows": state.get("windows", []),
        "screen_text": state.get("screen_text", ""),
        "focused_title": state.get("focused_title", ""),
    }


# Need ctypes import for build_execute_namespace
import ctypes
