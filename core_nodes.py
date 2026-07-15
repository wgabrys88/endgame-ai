import copy
import json
import os
import pathlib
import subprocess
import sys
import time
from typing import Any

import core_brain as brain
import core_bus as bus
import core_wiring as wiring

ROOT = pathlib.Path(__file__).parent.resolve()



def _action_index(state: dict[str, Any]) -> dict[str, Any]:
    index = state.get("action_index") or {}
    return index if isinstance(index, dict) else {}


def _node_center(node: dict[str, Any]) -> tuple[int, int]:
    if node.get("px") is not None and node.get("py") is not None:
        return int(node.get("px") or 0), int(node.get("py") or 0)
    rect = node.get("rect") if isinstance(node.get("rect"), dict) else {}
    left, top = int(rect.get("left", 0) or 0), int(rect.get("top", 0) or 0)
    right, bottom = int(rect.get("right", left) or left), int(rect.get("bottom", top) or top)
    return left + max(0, right - left) // 2, top + max(0, bottom - top) // 2


def capability_manifest(ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    w = (ctx or {}).get("wiring", {}) if isinstance(ctx, dict) else {}
    manifest = copy.deepcopy(w["capabilities"])
    transport, cfg = wiring.get_transport_config(w)
    manifest["configured_model"] = {"transport": transport, "model": cfg.get("model")}
    manifest["repo_root"] = str(ROOT)
    manifest["invocation"] = (
        "Every helper name is already a top-level global within the [runner]. Call it directly; "
        "import thou no [GUI] helper from [desktop]. The [modules] named are likewise prebound top-level objects. "
        "For all beyond the primitives, write plain [Python] and import from the standard library."
    )
    return manifest


def build_capability_runtime(ctx: dict[str, Any]) -> dict[str, Any]:
    """Namespace a runner script executes in. One flat set of primitives — no
    faculty split. The script imports/calls whatever else it needs (desktop,
    subprocess, stdlib) and sets `result` / prints / appends action_events."""
    import core_desktop as desktop
    d = desktop.get_desktop()
    state = ctx.get("state", {})
    w = ctx.get("wiring", {})
    action_index = _action_index(state)
    action_events: list[dict[str, Any]] = []

    def _record_action(result: Any) -> Any:
        event = dict(result) if isinstance(result, dict) else {"ok": True, "value": result}
        event.setdefault("ok", True)
        event["event_index"] = len(action_events)
        event["recorded_at"] = time.time()
        action_events.append(event)
        if event.get("ok") is not True:
            raise RuntimeError(f"body action failed: {event}")
        return result

    def _require_node(node_id: str) -> dict[str, Any]:
        node = action_index.get(str(node_id))
        if not isinstance(node, dict):
            raise RuntimeError(f"node id is not actionable in the latest observation: {node_id}")
        return dict(node)

    def _guarded(fn):
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return _record_action(fn(*args, **kwargs))
        return wrapper

    click = _guarded(lambda x, y, hwnd=0: d.click(int(x), int(y), int(hwnd or 0)))
    type_text = _guarded(lambda text: d.type_text(str(text)))
    press_key = _guarded(lambda key: d.press_key(str(key)))
    hotkey = _guarded(lambda *keys: d.hotkey(*keys))
    scroll = _guarded(lambda x, y, amount, hwnd=0: d.scroll(int(x), int(y), int(amount), int(hwnd or 0)))
    open_url = _guarded(lambda browser, url: d.open_url(str(browser), str(url)))

    def _target_label(node: dict[str, Any]) -> str:
        raw = str(node.get("name") or "").replace("\r", " ").replace("\n", " ")
        return " ".join(raw.split()) or str(node.get("role") or "element")

    def click_node(node_id: str) -> dict[str, Any]:
        node = _require_node(node_id)
        x, y = _node_center(node)
        res = d.click(x, y, int(node.get("hwnd") or 0))
        return _record_action({"ok": bool(res.get("ok", True)), "action": "click_node", "target": _target_label(node), "click": res})

    def read_node(node_id: str) -> dict[str, Any]:
        node = _require_node(node_id)
        return _record_action({"ok": True, "action": "read_node", "target": _target_label(node), "text": node.get("name") or node.get("text_full") or node.get("value") or ""})

    def observe() -> dict[str, Any]:
        obs = d.observe({"hover_cache": copy.deepcopy(w["observe_config"]["hover_cache"])})
        return _record_action(
            {
                "ok": True,
                "action": "observe",
                "observed_at": obs.get("observed_at"),
                "desktop_tree_text": obs.get("desktop_tree_text", ""),
            }
        )

    def consult_model(prompt: str, max_output_tokens: int = 800) -> dict[str, Any]:
        text = str(prompt).strip()
        if not text:
            raise RuntimeError("consult_model requires a non-empty prompt")
        result = brain.call([{"role": "user", "content": text}], w, request_config={"max_output_tokens": int(max_output_tokens), "plain_text": True})
        return _record_action({"ok": True, "action": "consult_model", "response": str(result["content"])})

    runtime = {
        "click": click, "click_node": click_node, "read_node": read_node,
        "type_text": type_text, "press_key": press_key, "hotkey": hotkey, "scroll": scroll,
        "open_url": open_url, "observe": observe, "consult_model": consult_model,
        "node_by_id": _require_node, "action_index": action_index,
        "desktop": desktop, "subprocess": subprocess,
        "os": os, "sys": sys, "json": json, "time": time, "pathlib": pathlib,
        "repo_root": str(ROOT), "python_executable": sys.executable,
        "state": state, "wiring": w, "goal": ctx.get("goal", ""),
        "desktop_tree_text": state.get("desktop_tree_text", ""),
        "observation": bus.observation_brief(state),
        "observed_at": state.get("observed_at"),
        "action_events": action_events, "_action_events": action_events,
    }
    missing = sorted(set(w["capabilities"]["helpers"]) - set(runtime))
    if missing:
        raise RuntimeError(f"wiring declares unavailable capability helpers: {missing}")
    return runtime
