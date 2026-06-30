"""organism — the living loop.

The topology graph is still the architecture: each node emits one signal and wiring.json
routes that signal to the next node. This file only makes runtime truth reliable:
  - state.json is written atomically before and after every node.
  - comms/runtime.ndjson receives compact lifecycle events used by the workbench.
  - brain swaps still reload live when wiring changes.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import time
from typing import Any

import brain as brain_mod
import nodes as nodes_mod

ROOT = pathlib.Path(__file__).parent.resolve()
WIRING_PATH = ROOT / "wiring.json"
STATE_PATH = ROOT / "state.json"
CONTROL_PATH = ROOT / "comms" / "control.json"


class Context:
    """Live organism context handed to every node."""

    def __init__(self, wiring: dict):
        self.wiring = wiring
        self.brain = brain_mod.Brain(wiring.get("model", {}))
        self.state: dict[str, Any] = {}
        self.narration: list[str] = []
        self.state_seq = 0

    @property
    def goal(self) -> str:
        return self.state.get("goal", "")

    @property
    def memory(self) -> dict:
        return self.state.setdefault("memory", {})

    def reload_brain(self):
        self.brain = brain_mod.Brain(self.wiring.get("model", {}))

    def narrate(self, msg: str):
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        self.narration.append(line)
        self.narration = self.narration[-300:]
        print(line, flush=True)
        brain_mod.log_runtime_event(self.wiring.get("model", {}), "narration", message=msg)


def load_wiring() -> dict:
    return json.loads(WIRING_PATH.read_text(encoding="utf-8"))


def _atomic_json(path: pathlib.Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}.{time.time_ns()}")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def save_state(ctx: Context, *, active_node: str | None = None, phase: str = "snapshot") -> None:
    ctx.state_seq += 1
    now = time.time()
    snap = dict(ctx.state)
    snap["_narration"] = ctx.narration[-80:]
    snap["_transport"] = ctx.wiring.get("model", {}).get("transport")
    snap["_saved_at"] = now
    snap["_saved_at_iso"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now))
    snap["_state_seq"] = ctx.state_seq
    snap["_pid"] = os.getpid()
    snap["_active_node"] = active_node or snap.get("_node", "")
    snap["_phase"] = phase
    _atomic_json(STATE_PATH, snap)


def _read_control() -> dict:
    if not CONTROL_PATH.exists():
        return {"mode": "run", "step_requested": False}
    try:
        data = json.loads(CONTROL_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"mode": "run", "step_requested": False}
    if not isinstance(data, dict):
        return {"mode": "run", "step_requested": False}
    mode = data.get("mode")
    if mode not in ("run", "pause", "step"):
        mode = "run"
    return {"mode": mode, "step_requested": bool(data.get("step_requested"))}


def _write_control(data: dict) -> None:
    cur = dict(data)
    cur.setdefault("mode", "run")
    cur.setdefault("step_requested", False)
    cur["updated_at"] = time.time()
    cur["updated_by"] = "organism"
    _atomic_json(CONTROL_PATH, cur)


def _step_gate(ctx: Context, current: str) -> None:
    """Single chokepoint for human step debugging: blocks before node execution."""
    announced = False
    while True:
        ctl = _read_control()
        mode = ctl.get("mode", "run")
        if mode == "run":
            return
        if mode == "step" and ctl.get("step_requested"):
            _write_control({"mode": "step", "step_requested": False})
            return
        if not announced:
            phase = "step_wait" if mode == "step" else "paused"
            ctx.state["_node"] = current
            save_state(ctx, active_node=current, phase=phase)
            brain_mod.log_runtime_event(ctx.wiring.get("model", {}), "organism_paused", node=current, mode=mode)
            ctx.narrate(f"paused before node '{current}' — workbench control is {mode}")
            announced = True
        time.sleep(0.25)


def build_routing(wiring: dict):
    topo = wiring.get("topology", {})
    nodes = {n["id"]: n for n in topo.get("nodes", [])}
    edges = {}
    for e in topo.get("edges", []):
        edges[(e["from"], e["on"])] = e["to"]
    return nodes, edges, topo.get("cycle_start", "planner")


def _load_prior_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        prior = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    # Keep organism memory/plan continuity, but never treat debug metadata as intent.
    return {k: v for k, v in prior.items() if not k.startswith("_")}


def _goal_from_file() -> str:
    gp = ROOT / "goal.json"
    if not gp.exists():
        return ""
    try:
        return (json.loads(gp.read_text(encoding="utf-8")) or {}).get("goal", "")
    except json.JSONDecodeError:
        return ""


def live(goal: str, max_ticks: int = 0, max_brain_calls: int = 0):
    wiring = load_wiring()
    if max_brain_calls > 0:
        wiring.setdefault("model", {})["max_brain_calls"] = max_brain_calls
    nodes_mod.ensure_nodes()
    nodes_mod._ensure_io(wiring)
    ctx = Context(wiring)
    ctx.state = _load_prior_state()

    if goal:
        ctx.state["goal"] = goal
    elif not ctx.state.get("goal"):
        dropped_goal = _goal_from_file()
        if dropped_goal:
            ctx.state["goal"] = dropped_goal
    ctx.state.setdefault("memory", {})

    goal = ctx.state.get("goal", "")
    node_map, edges, start = build_routing(wiring)
    transport = wiring.get("model", {}).get("transport", "openai")
    try:
        wiring_mtime = WIRING_PATH.stat().st_mtime
    except OSError:
        wiring_mtime = 0.0

    ctx.narrate(f"organism awake (unconstrained) — core brain: {transport}; goal: {goal or '(none)'}")
    current = ctx.state.get("_node") or start
    ctx.state["_node"] = current
    save_state(ctx, active_node=current, phase="awake")
    brain_mod.log_runtime_event(ctx.wiring.get("model", {}), "organism_awake", transport=transport, goal=goal or "")

    delay = int(wiring.get("observe", {}).get("post_action_delay_ms", 250)) / 1000.0
    tick = 0
    terminal_phase = ""
    try:
        while True:
            tick += 1

            try:
                latest_mtime = WIRING_PATH.stat().st_mtime
            except OSError:
                latest_mtime = wiring_mtime
            if latest_mtime != wiring_mtime:
                ctx.wiring = load_wiring()
                node_map, edges, start = build_routing(ctx.wiring)
                ctx.reload_brain()
                nodes_mod._io_ready = False
                nodes_mod._ensure_io(ctx.wiring)
                wiring_mtime = latest_mtime
                ctx.narrate(f"wiring file changed; core brain now: {ctx.wiring.get('model', {}).get('transport')}")

            _step_gate(ctx, current)

            node_cfg = node_map.get(current)
            if node_cfg is None:
                ctx.narrate(f"no node '{current}' in topology; resting")
                break

            ctx.state["_node"] = current
            ctx.state["_active_node"] = current
            ctx.state["_node_started_at"] = time.time()
            save_state(ctx, active_node=current, phase="before_node")
            brain_mod.log_runtime_event(ctx.wiring.get("model", {}), "node_start", node=current, tick=tick)

            try:
                signal, patch = nodes_mod.execute_node(node_cfg, ctx)
            except Exception as e:
                ctx.state["last_error"] = f"node '{current}' crashed: {type(e).__name__}: {e}"
                save_state(ctx, active_node=current, phase="node_crashed")
                brain_mod.log_runtime_event(ctx.wiring.get("model", {}), "node_error", node=current,
                                            error=ctx.state["last_error"])
                ctx.narrate(ctx.state["last_error"])
                raise

            ctx.state.update(patch)

            if patch.get("_wiring_changed"):
                ctx.wiring = load_wiring()
                node_map, edges, start = build_routing(ctx.wiring)
                ctx.reload_brain()
                nodes_mod._io_ready = False
                nodes_mod._ensure_io(ctx.wiring)
                try:
                    wiring_mtime = WIRING_PATH.stat().st_mtime
                except OSError:
                    pass
                ctx.narrate(f"wiring changed; core brain now: {ctx.wiring.get('model', {}).get('transport')}")

            nxt = patch.get("next") or edges.get((current, signal))
            ctx.narrate(f"[{current}] -> {signal} -> {nxt or 'satisfied'}")
            brain_mod.log_runtime_event(ctx.wiring.get("model", {}), "node_signal", node=current, signal=signal,
                                        next=nxt or "satisfied")
            current = nxt or "satisfied"
            ctx.state["_node"] = current
            save_state(ctx, active_node=current, phase="after_node")

            if current == "satisfied" and node_map.get("satisfied"):
                save_state(ctx, active_node="satisfied", phase="before_node")
                sig, p = nodes_mod.execute_node(node_map["satisfied"], ctx)
                ctx.state.update(p)
                save_state(ctx, active_node="satisfied", phase="rest")
                terminal_phase = "rest"
                brain_mod.log_runtime_event(ctx.wiring.get("model", {}), "organism_rest", signal=sig)
                ctx.narrate("organism at rest")
                break
            if max_ticks and tick >= max_ticks:
                ctx.narrate(f"reached max_ticks={max_ticks}; stopping")
                save_state(ctx, active_node=current, phase="max_ticks")
                terminal_phase = "max_ticks"
                break
            time.sleep(delay)
    except KeyboardInterrupt:
        ctx.narrate("interrupted by human — sleeping")
        save_state(ctx, active_node=current, phase="interrupted")
        terminal_phase = "interrupted"
        brain_mod.log_runtime_event(ctx.wiring.get("model", {}), "organism_interrupted", node=current)
    if not terminal_phase:
        save_state(ctx, active_node=current, phase="stopped")


def main():
    ap = argparse.ArgumentParser(description="endgame-ai — an unconstrained, self-evolving desktop organism.")
    ap.add_argument("goal", nargs="?", default="", help="the goal to pursue")
    ap.add_argument("--max-ticks", type=int, default=0,
                    help="stop after N topology ticks (0 = until rest/interrupt)")
    ap.add_argument("--max-brain-calls", type=int, default=0,
                    help="stop brain after N transport calls via model.max_brain_calls (0 = unlimited)")
    ap.add_argument("--reset", action="store_true", help="forget prior state before starting")
    args = ap.parse_args()
    if args.reset and STATE_PATH.exists():
        STATE_PATH.unlink()
    live(args.goal, args.max_ticks, args.max_brain_calls)


if __name__ == "__main__":
    main()
