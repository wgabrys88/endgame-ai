"""organism — a small, dumb loop that hosts a living, self-directed agent.

DESIGN
The wiring is intentionally simple. The loop does almost nothing: it executes the
current node, reads the signal it emits, and routes to the next node. ALL intelligence,
adaptability and long-term evolution live in:
  1. swappable LLM brains (brain.py),
  2. the organism's ability to create/modify/delete its own executable nodes at runtime
     (nodes.py), and
  3. the stateless reasoning-feedback loop (the brain re-injects its own prior thinking).

The organism is alive: given no goal it still ticks, narrates, and may decide on its own
to act or to grow a new capability (idle initiative), like a person with nothing urgent
to do. Given a goal it pursues it, replans, and uses whatever brains/nodes it has.

ROUTING
A node emits a signal string. The loop maps signal -> next node via these rules, in
order: (a) the node put an explicit "next" in the patch; (b) a signal that names an
existing node routes there; (c) otherwise fall back to the "mind" node, which is the
organism's decision-maker. There is no fixed graph file — the mind node decides flow,
and new nodes extend behavior. Simple and dumb on purpose.

SAFETY
Exactly one gate: writing/modifying node code (nodes.write_node). Controlled by the
--autonomous launch flag. Nothing else is gated. This is a human-replacement operator
with full power on the user's own machine when autonomy is on.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import time

import brain as brain_mod
import hands as hands_mod
import nodes as nodes_mod

ROOT = pathlib.Path(__file__).parent.resolve()
CONFIG_PATH = ROOT / "config.json"
STATE_PATH = ROOT / "state.json"


class Context:
    """The live organism context handed to every node. Nodes read/write through it."""

    def __init__(self, brain, hands, cfg, autonomous: bool):
        self.brain = brain
        self.hands = hands
        self.cfg = cfg
        self.autonomous = autonomous
        self.state: dict = {}
        self.narration: list[str] = []

    # convenience accessors used by nodes
    @property
    def goal(self) -> str:
        return self.state.get("goal", "")

    @property
    def memory(self) -> dict:
        return self.state.setdefault("memory", {})

    def last_reasoning(self) -> str:
        return self.state.get("reasoning", "")

    def remember_reasoning(self, reasoning: str):
        self.state["reasoning"] = reasoning
        chain = self.state.setdefault("reasoning_chain", [])
        chain.append(reasoning[:2000])
        depth = int(self.cfg.get("loop", {}).get("reasoning_chain_depth", 24))
        self.state["reasoning_chain"] = chain[-depth:]

    def narrate(self, msg: str):
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        self.narration.append(line)
        self.narration = self.narration[-200:]
        print(line, flush=True)

    # the organism's own capabilities, exposed to nodes
    def think(self, system: str, user: str) -> tuple[str, dict | None]:
        content, parsed, reasoning = self.brain.think(system, user, self.last_reasoning())
        self.remember_reasoning(reasoning)
        return content, parsed

    def write_node(self, name: str, code: str) -> tuple[bool, str]:
        ok, msg = nodes_mod.write_node(name, code, self.autonomous)
        self.narrate(("grew" if ok else "BLOCKED growing") + f" node '{name}': {msg.splitlines()[0]}")
        return ok, msg

    def delete_node(self, name: str) -> tuple[bool, str]:
        return nodes_mod.delete_node(name)

    def catalog(self) -> str:
        return nodes_mod.node_catalog()


def load_cfg() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_state(ctx: Context):
    STATE_PATH.write_text(json.dumps(ctx.state, ensure_ascii=False, indent=2), encoding="utf-8")


def route(signal: str, patch: dict, available: list[str]) -> str:
    """The dumb router. Explicit next > signal-names-a-node > fall back to mind."""
    nxt = patch.get("next")
    if nxt:
        return str(nxt)
    if signal in available:
        return signal
    return "mind"


def live(goal: str, autonomous: bool, max_ticks: int = 0):
    cfg = load_cfg()
    nodes_mod.ensure_nodes()
    ctx = Context(brain_mod.Brain(cfg.get("brain", {})), hands_mod.Hands(), cfg, autonomous)
    if STATE_PATH.exists():
        try:
            ctx.state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            ctx.state = {}
    if goal:
        ctx.state["goal"] = goal
    ctx.state.setdefault("memory", {})

    mode = "AUTONOMOUS (self-modification enabled)" if autonomous else "guarded (self-modification asks first)"
    ctx.narrate(f"organism awake — {mode}; hands {'live' if ctx.hands.live else 'offline'}; goal: {goal or '(none — free initiative)'}")

    current = ctx.state.get("_node") or "mind"
    delay = int(cfg.get("loop", {}).get("tick_delay_ms", 600)) / 1000.0
    tick = 0
    try:
        while True:
            tick += 1
            available = nodes_mod.list_nodes()
            if current not in available:
                current = "mind"
            try:
                signal, patch = nodes_mod.execute_node(current, ctx)
            except Exception as e:
                ctx.narrate(f"node '{current}' crashed: {type(e).__name__}: {e}")
                signal, patch = "error", {"error": f"{type(e).__name__}: {e}", "failed_node": current}
            ctx.state.update(patch)
            nxt = route(signal, patch, available)
            ctx.state["_node"] = nxt
            save_state(ctx)
            if signal == "rest":
                ctx.narrate("organism at rest (goal satisfied / nothing to do)")
                if not cfg.get("loop", {}).get("idle_initiative", True) or goal:
                    break
            if max_ticks and tick >= max_ticks:
                ctx.narrate(f"reached max_ticks={max_ticks}, stopping")
                break
            current = nxt
            time.sleep(delay)
    except KeyboardInterrupt:
        ctx.narrate("organism interrupted by human — sleeping")
    save_state(ctx)


def main():
    ap = argparse.ArgumentParser(description="endgame-ai — a living, self-evolving desktop organism.")
    ap.add_argument("goal", nargs="?", default="", help="optional goal; omit to let the organism act on its own initiative")
    ap.add_argument("--autonomous", action="store_true",
                    help="DISABLE the single safety point: allow the organism to write/modify its own node code freely. Full power, full danger.")
    ap.add_argument("--max-ticks", type=int, default=0, help="stop after N ticks (0 = run until rest/interrupt)")
    ap.add_argument("--reset", action="store_true", help="forget prior state before starting")
    args = ap.parse_args()
    if args.reset and STATE_PATH.exists():
        STATE_PATH.unlink()
    live(args.goal, args.autonomous, args.max_ticks)


if __name__ == "__main__":
    main()
