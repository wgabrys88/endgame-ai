"""organism — the living loop. Drives the wiring topology graph: run a node, read the
signal it emits, follow the edge to the next node. ALL intelligence lives in the brain
(brain.py), the intent-based circuits (the node modules + wiring prompts), and the
organism's ability to rewrite its own wiring at runtime (self_modify), including which
brain it thinks with.

This is an UNCONSTRAINED organism. There is no safety gate and no constrained mode: it has
full control of the machine and decides for itself how to reach the goal — including
opening applications and, if it determines it should, routing its own cognition through a
different brain. The core always boots on the local LM Studio brain (model.transport=openai).

ROUTING is the wiring topology: each node emits a signal; the edge (from,on) -> to selects
the next node. If a node sets an explicit "next" in its patch, that wins. The graph starts
at topology.cycle_start.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import time

import brain as brain_mod
import nodes as nodes_mod

ROOT = pathlib.Path(__file__).parent.resolve()
WIRING_PATH = ROOT / "wiring.json"
STATE_PATH = ROOT / "state.json"


class Context:
    """Live organism context handed to every node."""

    def __init__(self, wiring: dict):
        self.wiring = wiring
        self.brain = brain_mod.Brain(wiring.get("model", {}))
        self.state: dict = {}
        self.narration: list[str] = []

    @property
    def goal(self) -> str:
        return self.state.get("goal", "")

    @property
    def memory(self) -> dict:
        return self.state.setdefault("memory", {})

    def reload_brain(self):
        """Re-bind the brain after a wiring change (e.g. self_modify swapped the transport)."""
        self.brain = brain_mod.Brain(self.wiring.get("model", {}))

    def narrate(self, msg: str):
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        self.narration.append(line)
        self.narration = self.narration[-300:]
        print(line, flush=True)


def load_wiring() -> dict:
    return json.loads(WIRING_PATH.read_text(encoding="utf-8"))


def save_state(ctx: Context):
    snap = dict(ctx.state)
    snap["_narration"] = ctx.narration[-60:]
    snap["_transport"] = ctx.wiring.get("model", {}).get("transport")
    STATE_PATH.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")


def build_routing(wiring: dict):
    topo = wiring.get("topology", {})
    nodes = {n["id"]: n for n in topo.get("nodes", [])}
    edges = {}
    for e in topo.get("edges", []):
        edges[(e["from"], e["on"])] = e["to"]
    return nodes, edges, topo.get("cycle_start", "planner")


def live(goal: str, max_ticks: int = 0):
    wiring = load_wiring()
    nodes_mod.ensure_nodes()
    nodes_mod._ensure_io(wiring)
    ctx = Context(wiring)
    if STATE_PATH.exists():
        try:
            prior = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            ctx.state = {k: v for k, v in prior.items() if not k.startswith("_")}
        except json.JSONDecodeError:
            ctx.state = {}
    if goal:
        ctx.state["goal"] = goal
    elif not ctx.state.get("goal"):
        # the workbench may have dropped a goal for us; otherwise we live without one
        gp = ROOT / "goal.json"
        if gp.exists():
            ctx.state["goal"] = (json.loads(gp.read_text(encoding="utf-8")) or {}).get("goal", "")
    ctx.state.setdefault("memory", {})

    goal = ctx.state.get("goal", "")

    node_map, edges, start = build_routing(wiring)
    transport = wiring.get("model", {}).get("transport", "openai")
    ctx.narrate(f"organism awake (unconstrained) — core brain: {transport}; goal: {goal or '(none)'}")

    current = ctx.state.get("_node") or start
    delay = int(wiring.get("observe", {}).get("post_action_delay_ms", 250)) / 1000.0
    tick = 0
    try:
        while True:
            tick += 1
            node_cfg = node_map.get(current)
            if node_cfg is None:
                ctx.narrate(f"no node '{current}' in topology; resting")
                break
            try:
                signal, patch = nodes_mod.execute_node(node_cfg, ctx)
            except Exception as e:
                ctx.narrate(f"node '{current}' crashed: {type(e).__name__}: {e}")
                raise
            ctx.state.update(patch)

            # if self_modify changed the wiring, rebuild routing + brain live
            if patch.get("_wiring_changed"):
                ctx.wiring = load_wiring()
                node_map, edges, start = build_routing(ctx.wiring)
                ctx.reload_brain()
                nodes_mod._io_ready = False
                nodes_mod._ensure_io(ctx.wiring)
                ctx.narrate(f"wiring changed; core brain now: {ctx.wiring.get('model', {}).get('transport')}")

            nxt = patch.get("next") or edges.get((current, signal))
            ctx.narrate(f"[{current}] -> {signal} -> {nxt or 'satisfied'}")
            current = nxt or "satisfied"
            ctx.state["_node"] = current
            save_state(ctx)

            if current == "satisfied" and node_map.get("satisfied"):
                # run satisfied once, then stop
                sig, p = nodes_mod.execute_node(node_map["satisfied"], ctx)
                ctx.state.update(p)
                save_state(ctx)
                ctx.narrate("organism at rest")
                break
            if max_ticks and tick >= max_ticks:
                ctx.narrate(f"reached max_ticks={max_ticks}; stopping")
                break
            time.sleep(delay)
    except KeyboardInterrupt:
        ctx.narrate("interrupted by human — sleeping")
    save_state(ctx)


def main():
    ap = argparse.ArgumentParser(description="endgame-ai — an unconstrained, self-evolving desktop organism.")
    ap.add_argument("goal", nargs="?", default="", help="the goal to pursue")
    ap.add_argument("--max-ticks", type=int, default=0, help="stop after N ticks (0 = until rest/interrupt)")
    ap.add_argument("--reset", action="store_true", help="forget prior state before starting")
    args = ap.parse_args()
    if args.reset and STATE_PATH.exists():
        STATE_PATH.unlink()
    live(args.goal, args.max_ticks)


if __name__ == "__main__":
    main()
