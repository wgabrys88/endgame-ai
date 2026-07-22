# endgame-ai

An atemporal, self-modifying organism that drives a real Windows 11 desktop the way a human
operator does: it looks at the screen, moves the mouse and keyboard, runs commands, and rewrites
its own body while it runs. This one document is the whole organism, carried in plaintext. Run it
and it lays its body onto disk beside itself and turns its wheel.

This file is a carrier, not a summary. Every source below is the live body verbatim, not a
description of it. Read the prose to know how and why; read the embedded files to know what is.
Where prose and code disagree, the code wins.

---

## It is a blackboard, not a wiring

The organism is often drawn as nodes joined by wires, as if a deed's result travelled along an
edge into the next node. That picture is false, and naming it falsely hides the real shape. There
are no wires. There is one shared structure that every faculty reads from and posts back to, and a
separate control policy that decides who is woken next. That is the classic blackboard architecture,
and endgame-ai is one.

- The blackboard is the shared state. One structure holds the goal, the living word, the last deed
  and its evidence, the verdict, the failure streak, and the fresh environment. No faculty owns it;
  all of them read the whole of it and each writes only its own slot.
- The faculties are knowledge sources. Four of them, woken one at a time. `node_guidance` reads a
  human note. `node_execute` (the actor) posts a deed and its claimed intent. `node_verify` (the
  witness) posts a verdict proven from the world. `node_recover` (the conscience) posts a different
  strike after a denial. None of them calls another; each only faces the blackboard.
- The control is the topology. What the KB and `wiring.json` call edges is not dataflow. It is a
  control component that reads the signal a faculty raised and chooses which knowledge source the
  blackboard wakes next. Move the choice, not the data.

So `wiring.json` is the blackboard's constitution: it declares the model, the perception budget, the
control policy (topology), the shared prompt law, and the record each faculty must post. It is inert
data the organism may rewrite; the kernel re-reads it every turn. And the running blackboard itself
is written out each turn as `blackboard.json` beside this file, so the shared structure can be read
by a human as it turns. That mirror is observation only, never read back as memory; a fresh life
begins with a fresh blackboard, because the organism is atemporal.

---

## The Law of Separated Powers

The reason this can be trusted more than an ordinary agent. A claim that warrants itself proves
nothing; one hand cannot weigh itself. So truth is not asked of the model, it is enforced by
structure. The actor moves the world and may only CLAIM. The witness proves an effect by some
system OTHER than the actor and is given no hand to move what it judges. Any value the actor
computed, printed, or wrote this life is void as proof. "X is done" stands only when a party that
could not have done X reads it afresh from the world. The witness alone may end the life.

---

## Atemporal memory

The organism holds no history. Two channels, and only two, cross from one turn to the next. The
living word is a small table, one row per thinking faculty plus the goal as a lodestar, rewritten
whole each turn, never appended; what is not narrated forward is forgotten. The fresh environment,
gathered by Python before every model call, is the other channel, and reality overrides every
remembered word. The failure streak is a forward counter of turns since the last witnessed advance;
the higher it climbs, the more recovery must change the KIND of approach rather than retry.

---

## The wheel

`node_guidance` reads and clears the operator mailbox, then wakes the actor. The actor explores,
authors one Python deed, runs it, and posts the result; a clean run wakes the witness, a raised
deed retries the actor while its budget holds, then falls to recovery. The witness explores, authors
a read-only probe, and posts a verdict: goal proven ends the life; a new advance wakes guidance
again; a denial wakes recovery; a probe that crashed re-probes and claims nothing. Recovery names
the true defect and frames a departing strike, then wakes guidance. The wheel turns until the
witness proves the whole goal, the body raises, or the process is stopped from outside. There is no
internal turn cap; adding one would cage the organism.

---

## The only tool is code

There is no tool menu. The actor writes Python and runs it in a capability namespace that holds the
`desktop` hand (click, type_text, paste_clipboard, set_clipboard, press_key, hotkey, scroll,
open_url), the `action_index`, and the standard library. The witness namespace has no hand and no
model, only read-only sight and the standard library. Perception is automatic and window-first:
Python enumerates the top-level windows, probes each on a golden-ratio grid, and keeps an element
only where the pixel's owner resolves to that window, so what survives is each window's visible,
reachable face. The model never asks to look and never reasons on a stale view.

---

## Running

The body is Windows-only, because perception and input are. Set `XAI_API_KEY` first, then drop the
needle onto this document with a one-sentence goal:

````
python -c "import re,pathlib,sys; t=pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'); exec(re.search(chr(96)*4+'python'+chr(10)+'(.*?)'+chr(10)+chr(96)*4, t, re.S).group(1), {'BOARD':sys.argv[1],'ARGV':sys.argv})" endgame-ai.md "your one sentence goal"
````

On run the carrier writes each embedded file to disk beside this document (laying down the body it
will then reload every turn), creates a fresh `blackboard.json`, and turns the wheel. Progress is
the real desktop; every model call also writes an untruncated dump under `_transmissions/`, and the
live blackboard is mirrored to `blackboard.json`. Pass the running organism a note by writing a line
into `guidance.txt`; the next guidance lap reads and clears it. A hard kill corrupts nothing, since
the organism keeps no cross-life memory.

A heuristic scanner will flag this body, and that is expected: fetch-then-exec, synthesized input,
and programmatic GUI control are exactly what such scanners catch. Run it only in an environment you
control.

---

## Carrier

The bootstrap. It reads its own document, lays each embedded file onto disk beside it, mirrors the
blackboard for observation without changing the kernel, and turns the real main-branch wheel.

```python
import os, re, sys, json, pathlib, importlib

BOARD = pathlib.Path(globals().get("BOARD", "endgame-ai.md")).resolve()
ARGV = globals().get("ARGV", sys.argv)
HERE = BOARD.parent

# --- lay the body onto disk: every `## file: <name>` section, embedded in a 4-backtick fence ---
_text = BOARD.read_text(encoding="utf-8")
_pat = re.compile(r"^## file: (\S+)\s*\n````[^\n]*\n(.*?)\n````\s*$", re.S | re.M)
_written = []
for _m in _pat.finditer(_text):
    _name, _body = _m.group(1), _m.group(2)
    (HERE / _name).write_text(_body.rstrip("\n") + "\n", encoding="utf-8")
    _written.append(_name)
if not _written:
    raise RuntimeError("carrier found no `## file:` sections to lay down")
sys.stderr.write("carrier: laid down %d files: %s\n" % (len(_written), ", ".join(_written)))

# run from the body's own directory so wiring.json / guidance.txt / _transmissions resolve here
os.chdir(HERE)
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# --- blackboard.json: mirror the shared structure each turn, observation only, fresh per life ---
_BB = HERE / "blackboard.json"
_BB.write_text("{}\n", encoding="utf-8")

import core_nodes as _nodes
_real_call_node = _nodes.call_node
def _observed_call_node(current, ctx):
    signal, patch = _real_call_node(current, ctx)
    board = dict(ctx.get("state") or {})
    board.update({k: v for k, v in patch.items() if not k.startswith("_")})
    board["last_signal"] = signal
    board["current_node"] = current
    try:
        _BB.write_text(json.dumps(board, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    except Exception as _e:
        sys.stderr.write("carrier: blackboard mirror failed: %r\n" % _e)
    return signal, patch
_nodes.call_node = _observed_call_node

# --- turn the real wheel: the goal is the first non-flag argument after the board path ---
import core_organism as _organism
_rest = [a for a in ARGV[1:] if a != str(BOARD) and a != BOARD.name]
_flags = [a for a in _rest if a.startswith("--")]
_goal = next((a for a in _rest if not a.startswith("--")), "")
_organism.main(_flags + [_goal])
```

## file: core_organism.py
````python
import argparse
import time
from typing import Any

import core_brain as brain
import core_bus as bus
import core_nodes as nodes
import core_wiring as wiring


def next_node_for(w: dict[str, Any], current: str, signal_name: str) -> str:
    edges = w.get("topology", {}).get("edges", {})
    node_edges = edges.get(current)
    if not isinstance(node_edges, dict):
        raise bus.TopologyContractError(f"topology has no edges for node '{current}'")
    target = node_edges.get(signal_name)
    if isinstance(target, str) and target:
        return target
    raise bus.TopologyContractError(
        f"node '{current}' emitted signal '{signal_name}' with no valid topology edge"
    )


def run(goal: str | None) -> dict[str, Any]:
    if not str(goal or "").strip():
        raise ValueError("the organism requires a non-empty root goal")
    w = wiring.load_wiring()
    current = str(w["topology"]["cycle_start"])
    st: dict[str, Any] = {
        "_phase": "starting",
        "goal": goal or "",
        "tick": 0,
        "current_node": current,
        "goal_interpretations": {},
        "wiring_transport": w["model"]["transport"],
        "started_at": time.time(),
    }
    try:
        while True:
            st["_phase"] = "executing_node"
            st["current_node"] = current
            ctx = {"wiring": w, "state": dict(st), "goal": goal or "", "node": current}
            signal_name, patch = nodes.call_node(current, ctx)
            if patch.pop("_reload_wiring", False):
                w = wiring.load_wiring()
            st.update(patch)
            st["last_signal"] = signal_name
            st["last_node"] = current
            st["tick"] += 1
            if signal_name == "halt":
                st["_phase"] = "halted"
                return st
            current = next_node_for(w, current, signal_name)
            st["_phase"] = "node_complete"
    except KeyboardInterrupt:
        st["_phase"] = "interrupted"
        return st


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "endgame-ai organism kernel. Dumps always under _transmissions/. "
            "Use --breakpoint for one-transmission tune (exit 42 before exec)."
        )
    )
    ap.add_argument(
        "--breakpoint",
        action="store_true",
        help="after the first model dump, exit 42 before any exec (prompt/knob science mode)",
    )
    ap.add_argument("goal", nargs="?", default="", help="one-sentence root goal for this life")
    args = ap.parse_args(argv)
    brain.set_break_after_response(bool(args.breakpoint))
    run(args.goal)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
````

## file: core_wiring.py
````python
import json
import pathlib
import re
from typing import Any

ROOT = pathlib.Path(__file__).parent.resolve()
SENTINELS = {"halt"}
_TEMPLATE_KEYS = (
    "living_word_header", "living_word_goal_row", "living_word_empty_row",
    "proven_ledger_empty", "proven_ledger_header", "standing_host_header",
    "environment_screen_header",
)


def root_path(value: str | None, default: str = "") -> pathlib.Path:
    raw = str(value or default).replace("${ROOT}", str(ROOT)).replace("${HOME}", str(pathlib.Path.home()))
    p = pathlib.Path(raw)
    return p if p.is_absolute() else ROOT / p


def load_json(path: pathlib.Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"malformed JSON in {path}: {exc}") from exc


def _require(obj: dict[str, Any], path: str, typ: type | tuple[type, ...]) -> Any:
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise RuntimeError(f"wiring missing required key: {path}")
        cur = cur[part]
    if not isinstance(cur, typ):
        raise RuntimeError(f"wiring.{path} must be {typ}")
    return cur


def _require_list_str(obj: dict[str, Any], path: str) -> list[str]:
    value = _require(obj, path, list)
    if not all(isinstance(item, str) and item for item in value):
        raise RuntimeError(f"wiring.{path} must be list[str]")
    return value


def validate_record_contracts(cfg: dict[str, Any]) -> None:
    contracts = _require(cfg, "record_contracts", dict)
    for record_type, contract in contracts.items():
        if not isinstance(record_type, str) or not record_type:
            raise RuntimeError(f"wiring.record_contracts key must be non-empty string: {record_type!r}")
        if not isinstance(contract, dict):
            raise RuntimeError(f"wiring.record_contracts.{record_type} must be object")
        required = contract.get("required")
        enums = contract.get("enums")
        types = contract.get("types", {})
        non_empty = contract.get("non_empty", [])
        additional_properties = contract.get("additional_properties", True)
        if not isinstance(required, list) or not all(isinstance(key, str) and key for key in required):
            raise RuntimeError(f"wiring.record_contracts.{record_type}.required must be list[str]")
        if not isinstance(enums, dict):
            raise RuntimeError(f"wiring.record_contracts.{record_type}.enums must be object")
        if not isinstance(types, dict) or not all(
            isinstance(key, str) and value in {"string", "boolean", "array", "object", "number", "integer"}
            for key, value in types.items()
        ):
            raise RuntimeError(f"wiring.record_contracts.{record_type}.types must map keys to supported JSON types")
        if not isinstance(non_empty, list) or not all(isinstance(key, str) and key for key in non_empty):
            raise RuntimeError(f"wiring.record_contracts.{record_type}.non_empty must be list[str]")
        if not isinstance(additional_properties, bool):
            raise RuntimeError(f"wiring.record_contracts.{record_type}.additional_properties must be boolean")
        known = set(required) | set(enums) | set(types)
        if not set(non_empty) <= known:
            raise RuntimeError(f"wiring.record_contracts.{record_type}.non_empty names unknown keys")
        for key, values in enums.items():
            if not isinstance(key, str) or not key:
                raise RuntimeError(f"wiring.record_contracts.{record_type}.enums key must be non-empty string")
            if not isinstance(values, list) or not values:
                raise RuntimeError(f"wiring.record_contracts.{record_type}.enums.{key} must be non-empty list")
    for record_type in cfg.get("model", {}).get("organs", {}):
        if record_type not in contracts:
            raise RuntimeError(f"wiring.model.organs.{record_type} has no matching wiring.record_contracts entry")


def validate_wiring(cfg: dict[str, Any]) -> None:
    for key in ("schema", "model", "paths", "exploration", "topology", "prompts", "shared_prompt_prefix", "record_contracts"):
        if key not in cfg:
            raise RuntimeError(f"wiring missing required key: {key}")
    if not isinstance(cfg["model"], dict):
        raise RuntimeError("wiring.model must be object")
    transport = _require(cfg, "model.transport", str)
    transport_cfg = _require(cfg, "model.transport_config", dict)
    if transport not in transport_cfg:
        raise RuntimeError(f"wiring.model.transport_config missing selected transport {transport!r}")
    selected = _require(cfg, f"model.transport_config.{transport}", dict)
    _require(cfg, f"model.transport_config.{transport}.request", dict)
    _require(cfg, f"model.transport_config.{transport}.url", str)
    profiles = selected.get("request_profiles", {})
    if not isinstance(profiles, dict) or not all(isinstance(n, str) and n and isinstance(b, dict) for n, b in profiles.items()):
        raise RuntimeError(f"wiring.model.transport_config.{transport}.request_profiles must map names to request objects")
    _require(cfg, "model.global", dict)
    _require(cfg, "model.organs", dict)
    _require(cfg, "exploration", dict)
    _require(cfg, "topology.edges", dict)
    _require(cfg, "paths.guidance", str)
    _require(cfg, "topology.cycle_start", str)
    for path in ("exploration.step_px", "exploration.max_subtree_nodes_per_point", "exploration.max_environment_chars"):
        value = _require(cfg, path, int)
        if isinstance(value, bool) or value <= 0:
            raise RuntimeError(f"wiring.{path} must be a positive count")
    nodes = _require_list_str(cfg, "topology.nodes")
    _require(cfg, "prompts", dict)
    _require(cfg, "shared_prompt_prefix", str)
    templates = _require(cfg, "prompt_templates", dict)
    for key in _TEMPLATE_KEYS:
        if not isinstance(templates.get(key), str) or not templates[key].strip():
            raise RuntimeError(f"wiring.prompt_templates.{key} must be a non-empty string")
    validate_record_contracts(cfg)
    if len(nodes) != len(set(nodes)):
        raise RuntimeError("wiring.topology.nodes contains duplicates")
    if cfg["topology"]["cycle_start"] not in nodes:
        raise RuntimeError("wiring.topology.cycle_start must name a topology node")
    missing = [node for node in nodes if node not in cfg["topology"]["edges"]]
    if missing:
        raise RuntimeError(f"wiring missing edges for nodes: {missing}")


def coherence_problems(w: dict[str, Any]) -> list[str]:
    import core_nodes as nodes

    topo = w["topology"]
    edges = topo["edges"]
    node_set = set(topo["nodes"])
    problems: list[str] = []
    try:
        validate_record_contracts(w)
    except Exception as exc:
        problems.append(f"record_contracts invalid: {type(exc).__name__}: {exc}")
        return problems
    contracts = w["record_contracts"]
    for prompt_key, text in w.get("prompts", {}).items():
        for record_type in re.findall(r"record_type '([^']+)'", str(text)):
            if record_type not in contracts:
                problems.append(f"prompt '{prompt_key}' names record_type '{record_type}' with no record_contracts entry")
    for record_type in w.get("model", {}).get("organs", {}):
        if record_type not in contracts:
            problems.append(f"model.organs.{record_type} has no record_contracts entry")
    if topo["cycle_start"] not in node_set:
        problems.append(f"cycle_start '{topo['cycle_start']}' not in topology.nodes")
    for src, sigmap in edges.items():
        if src not in node_set:
            problems.append(f"edge source '{src}' not in topology.nodes")
        for sig, target in sigmap.items():
            if not isinstance(target, str) or not target:
                problems.append(f"{src}.{sig} has no valid target: {target!r}")
                continue
            if target not in SENTINELS and target not in node_set:
                problems.append(f"{src}.{sig} -> '{target}' is not a known node")
            if target in SENTINELS and sig != target:
                problems.append(f"{src}.{sig} targets terminal name '{target}' instead of emitting terminal signal '{target}'")
    for n in node_set:
        if n not in edges:
            problems.append(f"node '{n}' has no edges")
        base = n.split(":", 1)[0]
        if base not in nodes.FACULTIES:
            problems.append(f"node '{n}' has no faculty in core_nodes.FACULTIES")
    seen: set[str] = set()
    stack = [topo["cycle_start"]]
    while stack:
        cur = stack.pop()
        if cur in seen or cur in SENTINELS:
            continue
        seen.add(cur)
        for target in edges.get(cur, {}).values():
            if isinstance(target, str) and target:
                stack.append(target)
    unreachable = node_set - seen
    if unreachable:
        problems.append(f"unreachable nodes from '{topo['cycle_start']}': {sorted(unreachable)}")
    return problems


def load_wiring(path: str | None = None) -> dict[str, Any]:
    source_path = root_path(path, "wiring.json").resolve()
    cfg = load_json(source_path)
    validate_wiring(cfg)
    problems = coherence_problems(cfg)
    if problems:
        raise RuntimeError(f"wiring topology is incoherent: {problems}")
    cfg["_source_path"] = str(source_path)
    return cfg


def prompt(cfg: dict[str, Any], key: str) -> str:
    prompts = cfg["prompts"]
    if key not in prompts:
        raise RuntimeError(f"wiring.prompts missing prompt: {key}")
    return str(cfg["shared_prompt_prefix"]).rstrip() + "\n\n" + str(prompts[key]).lstrip()


def get_transport_config(wiring: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    model = wiring["model"]
    transport = model["transport"].strip()
    cfg = dict(model["transport_config"][transport])
    if "timeout" not in cfg:
        cfg["timeout"] = model["global"]["timeout"]
    cfg["transport"] = transport
    return transport, cfg
````

## file: core_nodes.py
````python
from __future__ import annotations

import copy
import hashlib
import json
import os
import pathlib
import platform
import shutil
import subprocess
import sys
import time
import traceback
import types
from abc import ABC
from typing import Any, Callable

import core_brain as brain
import core_bus as bus
import core_wiring as wiring

JsonDict = dict[str, Any]
ROOT = pathlib.Path(__file__).parent.resolve()


class BaseNode(ABC):
    prompt_key: str = ""
    expected_record_type: str = ""
    contract: str = ""

    def build_payload(self, ctx: JsonDict) -> JsonDict:
        st = ctx.get("state", {})
        return {
            "goal": st.get("goal", ctx.get("goal", "")),
            "state": bus.state_brief(st),
            "environment": bus.environment_brief(st),
        }

    def signal_from_data(self, data: JsonDict, ctx: JsonDict) -> str:
        raise NotImplementedError(f"{type(self).__name__} must implement signal_from_data or override run()")

    def patch_from_record(self, record: bus.Record, ctx: JsonDict) -> JsonDict:
        raise NotImplementedError(f"{type(self).__name__} must implement patch_from_record or override run()")

    def think(self, ctx: JsonDict) -> bus.Record:
        w = ctx["wiring"]
        explore(ctx)
        payload = self.build_payload(ctx)
        payload["goal"] = ctx["state"]["goal"]
        record = brain.think(
            wiring.prompt(w, self.prompt_key),
            payload,
            w,
            expected_record_type=self.expected_record_type,
            emitting_node=ctx.get("node"),
        )
        if record.get("record_type") != self.expected_record_type:
            raise bus.NodeRecordContractError(
                f"{self.prompt_key} expected record_type {self.expected_record_type!r}, "
                f"got {record.get('record_type')!r}"
            )
        return bus.Record.from_json(record)

    def run(self, ctx: JsonDict) -> tuple[str, JsonDict]:
        record = self.think(ctx)
        return bus.emit(self.signal_from_data(record.data, ctx), self.patch_from_record(record, ctx))


class GuidanceNode:
    contract = "[node_guidance] — Thou receivest the [guidance] file."

    def run(self, ctx: JsonDict) -> tuple[str, JsonDict]:
        path = wiring.root_path(ctx["wiring"]["paths"]["guidance"])
        counsel = path.read_text(encoding="utf-8").strip() if path.exists() else ""
        if counsel:
            path.write_text("", encoding="utf-8")
        return bus.emit("attend", {"latest_counsel": counsel})


class ExecuteNode(BaseNode):
    prompt_key = "node_execute"
    expected_record_type = "execution"
    contract = "[node_execute] — Thou receivest the fresh [environment] and any [action_frame]."

    def build_payload(self, ctx: JsonDict) -> JsonDict:
        state = ctx["state"]
        return {
            "goal": state["goal"],
            "action_frame": state.get("action_frame"),
            "state": bus.state_brief(state),
            "environment": bus.environment_brief(state),
        }

    def run(self, ctx: JsonDict) -> tuple[str, JsonDict]:
        state = ctx["state"]
        record = self.think(ctx)
        data = record.data
        code = data["code"]
        intent = str(data["intent"]).strip()
        if not intent:
            raise RuntimeError("execution requires non-empty intent")
        deed_fault = None
        ns = build_capability_runtime(ctx)
        try:
            exec(code, ns)
        except Exception:
            deed_fault = traceback.format_exc()
        signal = "deed_denied" if deed_fault else "done"
        return bus.emit(
            signal,
            {
                "current_deed": {"description": intent},
                "goal_interpretations": bus.with_interpretation(
                    state.get("goal_interpretations"), "execute", str(data.get("goal_interpretation") or "")
                ),
                "turn_executions": {
                    "exec": {
                        "code_sha256": hashlib.sha256(code.encode("utf-8", errors="replace")).hexdigest(),
                        "code_chars": len(code),
                        "deed_fault": deed_fault,
                    }
                },
                "last_action_at": time.time(),
                "action_frame": None,
                "last_verification": None,
            },
        )


class VerifyNode(BaseNode):
    prompt_key = "node_verify"
    expected_record_type = "verification"
    contract = (
        "[node_verify] — Thou receivest the [goal], the last [deed] (its description and hour of action), "
        "the [state] brief, and the fresh [environment]."
    )

    def _deed(self, ctx: JsonDict) -> str:
        state = ctx["state"]
        deed = state.get("current_deed") or {}
        return deed.get("description", state["goal"])

    def build_payload(self, ctx: JsonDict) -> JsonDict:
        state = ctx["state"]
        return {
            "goal": state["goal"],
            "deed": {"description": self._deed(ctx), "acted_at": state.get("last_action_at")},
            "state": bus.state_brief(state),
            "environment": bus.environment_brief(state),
        }

    def run(self, ctx: JsonDict) -> tuple[str, JsonDict]:
        state = ctx["state"]
        record = self.think(ctx)
        probe_fault = None
        verdict = None
        ns = build_capability_runtime(ctx, read_only=True)
        try:
            exec(record.data["code"], ns)
            verdict = ns.get("verdict")
            if (
                not isinstance(verdict, dict)
                or not isinstance(verdict.get("goal_satisfied"), bool)
                or not isinstance(verdict.get("deed_confirmed"), bool)
                or not isinstance(verdict.get("reason"), str)
                or not verdict["reason"].strip()
            ):
                raise RuntimeError(
                    "verification probe must set verdict with boolean goal_satisfied/deed_confirmed and non-blank reason"
                )
        except Exception:
            probe_fault = traceback.format_exc()

        if probe_fault is not None:
            note = (
                "The read-only probe I authored raised ere it set a verdict, so this deed standeth "
                "UNJUDGED — this is neither the actor's failing nor a fault in any node file, for the "
                "probe is transient code I write anew each witnessing. I shall author a simpler probe "
                "that runneth, and touch no body file.\n" + probe_fault
            )
            return bus.emit(
                "unwitnessed",
                {
                    "goal_interpretations": bus.with_interpretation(state.get("goal_interpretations"), "verify", note),
                    "last_verification": {"success": False, "signal": "unwitnessed", "reasoning": probe_fault},
                },
            )

        assert verdict is not None
        goal_satisfied = verdict["goal_satisfied"]
        deed_confirmed = verdict["deed_confirmed"]
        reason = verdict["reason"]
        signal = "halt" if goal_satisfied else ("deed_confirmed" if deed_confirmed else "deed_denied")
        desc = self._deed(ctx)
        confirmed = goal_satisfied or deed_confirmed
        patch: JsonDict = {
            "verification": {
                "goal_satisfied": goal_satisfied,
                "deed_confirmed": deed_confirmed,
                "reasoning": reason,
                "deed_goal": desc,
            },
            "last_verification": {"success": confirmed, "signal": signal, "reasoning": reason},
            "goal_interpretations": bus.with_interpretation(
                state.get("goal_interpretations"), "verify", str(record.data.get("goal_interpretation") or "")
            ),
        }
        if confirmed:
            proven = list(state.get("proven_ledger") or [])
            fact = f"{desc.strip()} — witnessed: {reason.strip()}" if desc.strip() else reason.strip()
            if fact and fact not in proven:
                proven.append(fact)
            patch.update({
                "witnessed_deed_count": int(state.get("witnessed_deed_count") or 0) + 1,
                "failure_streak": {"count": 0},
                "proven_ledger": proven,
                "action_frame": None,
                "current_deed": None,
            })
        return bus.emit(signal, patch)


class RecoverNode(BaseNode):
    prompt_key = "node_recover"
    expected_record_type = "recovery"
    contract = (
        "[node_recover] — Thou receivest the denied deed, its evidence and [failure_streak], "
        "and the fresh [environment]."
    )

    def build_payload(self, ctx: JsonDict) -> JsonDict:
        state = ctx["state"]
        self._streak_patch = bus.bump_failure_streak(state)
        deed = state.get("current_deed") or {}
        return {
            "goal": state["goal"],
            "deed": {"description": deed.get("description", state["goal"])},
            "state": bus.state_brief(state),
            "evidence": {
                "executions": bus.execution_evidence(state),
                "last_verification": state.get("last_verification", {}),
                "failure_streak": self._streak_patch["failure_streak"],
            },
            "environment": bus.environment_brief(state),
        }

    def signal_from_data(self, data: JsonDict, ctx: JsonDict) -> str:
        return "recovered"

    def patch_from_record(self, record: bus.Record, ctx: JsonDict) -> JsonDict:
        data, state = record.data, ctx["state"]
        deed = state.get("current_deed") or {}
        return {
            **self._streak_patch,
            "action_frame": {
                "target": data["target"],
                "strategy": data["strategy"],
                "lesson": data["lesson"],
            },
            "last_recovery": {
                "lesson": data["lesson"],
                "target": data["target"],
                "strategy": data["strategy"],
                "deed_goal": deed.get("description", state["goal"]),
            },
            "goal_interpretations": bus.with_interpretation(
                state.get("goal_interpretations"), "recover", str(data.get("goal_interpretation") or "")
            ),
        }


FACULTIES: dict[str, Callable[[], Any]] = {
    "node_guidance": GuidanceNode,
    "node_execute": ExecuteNode,
    "node_verify": VerifyNode,
    "node_recover": RecoverNode,
}


def node_contract(name: str) -> str:
    base = name.split(":", 1)[0]
    if base not in FACULTIES:
        raise RuntimeError(f"node '{name}' declareth no input contract")
    return str(getattr(FACULTIES[base], "contract", "") or "").strip()


def call_node(node_name: str, ctx: JsonDict) -> tuple[str, JsonDict]:
    base = node_name.split(":", 1)[0]
    if base not in FACULTIES:
        raise RuntimeError(f"unknown node '{node_name}'; known: {sorted(FACULTIES)}")
    ctx = {**ctx, "node": node_name, "node_base": base, "node_instance": None}
    signal, patch = bus.coerce_node_output(node_name, FACULTIES[base]().run(ctx))
    bus.validate_signal(ctx["wiring"], node_name, signal)
    return signal, dict(patch)


def _host_facts() -> dict[str, Any]:
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "hostname": platform.node(),
        "user": os.environ.get("USERNAME") or os.environ.get("USER") or "",
        "cwd": os.getcwd(),
        "repo_root": str(ROOT),
        "python": f"{sys.executable} ({platform.python_version()})",
        "shell_tools": sorted(
            t for t in ("powershell", "pwsh", "cmd", "git", "pip", "node", "npm", "curl") if shutil.which(t)
        ),
    }


def explore(ctx: dict[str, Any]) -> None:
    import core_desktop as desktop

    config = ctx["wiring"]["exploration"]
    obs = desktop.get_desktop(config).observe(config)
    ctx["state"].update({
        "observed_at": obs.get("observed_at"),
        "desktop_tree_text": obs.get("desktop_tree_text", ""),
        "action_index": obs.get("action_index", {}),
        "screen_elements": obs.get("screen_elements", []),
        "observation_artifact": obs.get("observation_artifact", {}),
        "host_facts": _host_facts(),
    })


def build_capability_runtime(ctx: dict[str, Any], *, read_only: bool = False) -> dict[str, Any]:
    import core_desktop as desktop

    d = desktop.get_desktop()
    state = ctx.get("state", {})
    index = state.get("action_index") or {}
    ns: dict[str, Any] = {
        "subprocess": subprocess,
        "os": os,
        "sys": sys,
        "json": json,
        "time": time,
        "pathlib": pathlib,
        "hashlib": hashlib,
        "repo_root": str(ROOT),
        "python_executable": sys.executable,
        "desktop_tree_text": str(state.get("desktop_tree_text", "")),
        "screen_elements": copy.deepcopy(state.get("screen_elements", [])),
        "environment": copy.deepcopy(bus.environment_brief(state)),
    }
    if read_only:
        # No observe(): environment is already injected before think; witness only reads.
        return ns

    w = ctx.get("wiring", {})

    def consult_model(prompt: str, profile: str | None = None) -> dict[str, Any]:
        text = str(prompt).strip()
        if not text:
            raise RuntimeError("consult_model requires a non-empty prompt")
        result = brain.call([{"role": "user", "content": text}], w, profile=profile)
        return {"ok": True, "action": "consult_model", "profile": profile, "response": str(result["content"])}

    # Hand without observe: LLM does not re-look; kernel explore() injects the environment.
    hand = types.SimpleNamespace(
        click=d.click,
        set_clipboard=d.set_clipboard,
        type_text=d.type_text,
        paste_clipboard=d.paste_clipboard,
        press_key=d.press_key,
        hotkey=d.hotkey,
        scroll=d.scroll,
        open_url=d.open_url,
    )
    ns.update({
        "desktop": hand,
        "action_index": index if isinstance(index, dict) else {},
        "consult_model": consult_model,
        "state": state,
        "wiring": w,
        "goal": ctx.get("goal", ""),
    })
    return ns
````

## file: core_brain.py
````python
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

import core_bus as bus
import core_wiring as wiring

_SESSION_CACHE_KEY = f"endgame-{uuid.uuid4()}"
_ROOT = pathlib.Path(__file__).resolve().parent
_DUMP_DIR = _ROOT / "_transmissions"
# Full raw req/resp dumps always. Break after first dump only when CLI --breakpoint is set.
_BREAK_AFTER_RESPONSE = False


def set_break_after_response(enabled: bool) -> None:
    """Primary tune interjection: dump then sys.exit(42) before faculty uses content."""
    global _BREAK_AFTER_RESPONSE
    _BREAK_AFTER_RESPONSE = bool(enabled)


def _messages(system_prompt: str, user_text: str, stable_context: str = "") -> list[dict[str, str]]:
    system = system_prompt + ("\n\n" + stable_context if stable_context else "")
    return [{"role": "system", "content": system}, {"role": "user", "content": user_text}]


def get_record_contract(w: dict[str, Any], record_type: str) -> dict[str, Any]:
    contract = w["record_contracts"][record_type]
    if not isinstance(contract, dict):
        raise RuntimeError(f"wiring.record_contracts.{record_type} must be object")
    return contract


def _validate_record_contract(w: dict[str, Any], record: bus.Record, expected_record_type: str | None = None) -> None:
    if expected_record_type and record.record_type != expected_record_type:
        raise RuntimeError(f"brain record_type mismatch: expected {expected_record_type!r}, got {record.record_type!r}")
    contract = get_record_contract(w, record.record_type)
    required = list(contract["required"])
    enums = dict(contract["enums"])
    types = dict(contract.get("types", {}))
    non_empty = set(contract.get("non_empty", []))
    missing = [key for key in required if key not in record.data]
    if missing:
        raise RuntimeError(f"{record.record_type} record missing required data keys: {missing}")
    if not contract.get("additional_properties", True):
        allowed = set(required) | set(enums) | set(types)
        unexpected = sorted(set(record.data) - allowed)
        if unexpected:
            raise RuntimeError(f"{record.record_type} record has unexpected data keys: {unexpected}")
    json_types = {"string": str, "boolean": bool, "array": list, "object": dict, "number": (int, float), "integer": int}
    for key, type_name in types.items():
        if key in record.data and (
            not isinstance(record.data[key], json_types[type_name])
            or type_name in {"number", "integer"} and isinstance(record.data[key], bool)
        ):
            raise RuntimeError(f"{record.record_type}.data.{key} must be {type_name}")
    for key in non_empty:
        if key in record.data and not record.data[key]:
            raise RuntimeError(f"{record.record_type}.data.{key} must be non-empty")
        if key in record.data and isinstance(record.data[key], str) and not record.data[key].strip():
            raise RuntimeError(f"{record.record_type}.data.{key} must be non-blank")
    for key, values in enums.items():
        if key in record.data and record.data[key] not in set(values):
            raise RuntimeError(f"{record.record_type}.data.{key}={record.data[key]!r} outside {values!r}")


def extract_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _commit_record(content: str, w: dict[str, Any], expected_record_type: str | None = None) -> bus.Record:
    record = extract_json_object(content)
    if record is None:
        raise RuntimeError(f"brain did not commit a valid JSON object: {content}")
    if not isinstance(record.get("record_type"), str) or "data" not in record or not isinstance(record["data"], dict):
        raise RuntimeError(f"brain record must contain string record_type and object data: {record}")
    committed = bus.Record.from_json(record)
    _validate_record_contract(w, committed, expected_record_type)
    return committed


def downstream_contract(w: dict[str, Any], emitting_node: str | None) -> str:
    if not emitting_node:
        return ""
    import core_nodes as nodes

    edges = w.get("topology", {}).get("edges", {}).get(emitting_node, {})
    seen = [
        (signal, target)
        for signal, target in edges.items()
        if signal != "error" and isinstance(target, str) and target != "halt"
    ]
    if not seen:
        return ""
    lines = [
        "DOWNSTREAM CONTRACT — thine output is wired (through the [topology]) unto these consumers; "
        "bring forth that which they await:"
    ]
    for signal, succ in seen:
        lines.append(f"\n[on signal '{signal}' -> {succ}]\n{nodes.node_contract(succ)}")
    return "\n".join(lines)


def resolve_profile(w: dict[str, Any], profile: str | None) -> dict[str, Any]:
    if not profile:
        return {}
    _, cfg = wiring.get_transport_config(w)
    profiles = cfg.get("request_profiles", {})
    if profile not in profiles:
        raise RuntimeError(f"unknown request profile {profile!r}; wiring defines {sorted(profiles)}")
    return dict(profiles[profile])


def _record_response_format(w: dict[str, Any], record_type: str) -> dict[str, Any]:
    contract = get_record_contract(w, record_type)
    data_properties = {key: {} for key in contract["required"]}
    for key, type_name in contract.get("types", {}).items():
        data_properties.setdefault(key, {})["type"] = type_name
    for key in contract.get("non_empty", []):
        type_name = contract.get("types", {}).get(key)
        limit_name = {"string": "minLength", "array": "minItems", "object": "minProperties"}.get(type_name)
        if limit_name:
            data_properties.setdefault(key, {})[limit_name] = 1
    for key, values in dict(contract["enums"]).items():
        data_properties.setdefault(key, {})["enum"] = list(values)
    return {
        "type": "json_schema",
        "name": f"{record_type}_record",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "record_type": {"enum": [record_type]},
                "data": {
                    "type": "object",
                    "additionalProperties": contract.get("additional_properties", True),
                    "properties": data_properties,
                    "required": list(contract["required"]),
                },
            },
            "required": ["record_type", "data"],
        },
    }


def _transport_body(cfg: dict[str, Any], messages: list[dict[str, str]], body_override: dict | None, response_format: dict | None) -> dict[str, Any]:
    body = bus.deep_merge(cfg["request"], body_override or {})
    body.setdefault("prompt_cache_key", _SESSION_CACHE_KEY)
    body["input"] = [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in messages
        if m.get("role", "user") in {"system", "user", "assistant"}
    ]
    if isinstance(response_format, dict):
        if str(response_format.get("type", "json_schema")) == "json_object":
            body["text"] = {"format": {"type": "json_object"}}
        else:
            body["text"] = {"format": {
                "type": response_format.get("type", "json_schema"),
                "name": response_format.get("name", "record"),
                "schema": response_format.get("schema", {}),
                "strict": bool(response_format.get("strict", True)),
            }}
    return bus.drop_nulls(body)


def _write_full(path: pathlib.Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def _dump_transmission(
    *,
    url: str,
    payload: dict[str, Any],
    messages: list[dict[str, str]],
    raw_response_text: str,
    response_obj: Any,
    content: str,
    reasoning: str,
    http_status: int | None,
    error: str | None,
) -> pathlib.Path:
    """Write untruncated request/response artifacts for offline analysis."""
    _DUMP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    uid = uuid.uuid4().hex[:8]
    run_dir = _DUMP_DIR / f"{stamp}_{uid}"
    run_dir.mkdir(parents=True, exist_ok=True)

    request_json = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    response_json = (
        json.dumps(response_obj, ensure_ascii=False, indent=2, default=str)
        if response_obj is not None
        else raw_response_text
    )
    meta = {
        "dumped_at": time.time(),
        "url": url,
        "http_status": http_status,
        "error": error,
        "request_chars": len(request_json),
        "raw_response_chars": len(raw_response_text or ""),
        "content_chars": len(content or ""),
        "reasoning_chars": len(reasoning or ""),
        "message_roles": [m.get("role") for m in messages],
        "message_char_counts": {m.get("role", "?"): len(m.get("content") or "") for m in messages},
        "break_after_response": _BREAK_AFTER_RESPONSE,
    }
    bundle = {
        "meta": meta,
        "request_body": payload,
        "messages": messages,
        "raw_response_text": raw_response_text,
        "response_object": response_obj,
        "extracted_content": content,
        "extracted_reasoning": reasoning,
    }
    # Full bundle + side files (no truncation).
    _write_full(run_dir / "transmission.json", json.dumps(bundle, ensure_ascii=False, indent=2, default=str))
    _write_full(run_dir / "request_body.json", request_json)
    _write_full(run_dir / "response_raw.json", response_json if response_obj is not None else (raw_response_text or ""))
    _write_full(run_dir / "response_raw.txt", raw_response_text or "")
    _write_full(run_dir / "content.txt", content or "")
    _write_full(run_dir / "reasoning.txt", reasoning or "")
    for m in messages:
        role = str(m.get("role") or "unknown")
        _write_full(run_dir / f"message_{role}.txt", str(m.get("content") or ""))
    _write_full(run_dir / "meta.json", json.dumps(meta, ensure_ascii=False, indent=2))

    latest = _ROOT / "_transmission_latest.json"
    _write_full(latest, json.dumps(bundle, ensure_ascii=False, indent=2, default=str))
    # Pointer for quick open
    _write_full(_ROOT / "_transmission_latest_dir.txt", str(run_dir))
    return run_dir


def _texts_from_parts(parts: Any) -> list[str]:
    out: list[str] = []
    if isinstance(parts, str) and parts.strip():
        return [parts]
    if not isinstance(parts, list):
        return out
    for part in parts:
        if isinstance(part, str) and part.strip():
            out.append(part)
        elif isinstance(part, dict) and part.get("text"):
            out.append(str(part["text"]))
    return out


def _extract_content_reasoning(obj: dict[str, Any]) -> tuple[str, str]:
    content = str(obj.get("output_text") or "")
    reasoning_parts: list[str] = []
    message_parts: list[str] = []
    if isinstance(obj.get("output"), list):
        for item in obj["output"]:
            if not isinstance(item, dict):
                continue
            kind = item.get("type")
            if kind == "reasoning":
                # xAI may put reasoning in summary and/or content.
                reasoning_parts.extend(_texts_from_parts(item.get("summary")))
                reasoning_parts.extend(_texts_from_parts(item.get("content")))
            else:
                message_parts.extend(_texts_from_parts(item.get("content")))
    if not content.strip():
        content = "\n".join(message_parts)
    return content, "\n".join(reasoning_parts).strip()


def _transport_call(messages: list[dict[str, str]], cfg: dict[str, Any], *, body_override=None, response_format=None) -> dict[str, str]:
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        raise RuntimeError("xai transport: XAI_API_KEY missing; no fallback was attempted")
    payload = _transport_body(cfg, messages, body_override, response_format)
    url = str(cfg["url"])
    raw_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=raw_bytes,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    raw_response_text = ""
    response_obj: Any = None
    content = ""
    reasoning = ""
    http_status: int | None = None
    error: str | None = None
    try:
        with urllib.request.urlopen(req, timeout=float(cfg["timeout"])) as resp:
            http_status = int(getattr(resp, "status", 200) or 200)
            raw_response_text = resp.read().decode("utf-8")
        response_obj = json.loads(raw_response_text) if raw_response_text else {}
        if not isinstance(response_obj, dict):
            raise RuntimeError(f"xai transport expected JSON object, got {type(response_obj).__name__}")
        content, reasoning = _extract_content_reasoning(response_obj)
        dump_dir = _dump_transmission(
            url=url,
            payload=payload,
            messages=messages,
            raw_response_text=raw_response_text,
            response_obj=response_obj,
            content=content,
            reasoning=reasoning,
            http_status=http_status,
            error=None,
        )
        sys.stderr.write(
            f"TRANSMISSION DUMP (full, no truncation): {dump_dir}\n"
            f"  also: {_ROOT / '_transmission_latest.json'}\n"
            f"  request_chars={len(raw_bytes)} response_chars={len(raw_response_text)} "
            f"content_chars={len(content)} reasoning_chars={len(reasoning)}\n"
        )
        if _BREAK_AFTER_RESPONSE:
            sys.stderr.write("BREAKPOINT after response (omit --breakpoint to continue the life)\n")
            sys.exit(42)
        return {"content": content, "reasoning": reasoning}
    except SystemExit:
        raise
    except urllib.error.HTTPError as exc:
        http_status = int(exc.code)
        raw_response_text = exc.read().decode("utf-8")
        error = f"HTTP {exc.code}"
        try:
            response_obj = json.loads(raw_response_text) if raw_response_text else None
        except json.JSONDecodeError:
            response_obj = None
        dump_dir = _dump_transmission(
            url=url,
            payload=payload,
            messages=messages,
            raw_response_text=raw_response_text,
            response_obj=response_obj,
            content="",
            reasoning="",
            http_status=http_status,
            error=error,
        )
        sys.stderr.write(f"TRANSMISSION DUMP (HTTP error): {dump_dir}\n")
        if _BREAK_AFTER_RESPONSE:
            sys.stderr.write("BREAKPOINT after failed response (omit --breakpoint to continue)\n")
            sys.exit(42)
        raise RuntimeError(f"xai transport HTTP {exc.code}: {raw_response_text}") from exc
    except urllib.error.URLError as exc:
        error = f"URL error: {getattr(exc, 'reason', exc)}"
        dump_dir = _dump_transmission(
            url=url,
            payload=payload,
            messages=messages,
            raw_response_text="",
            response_obj=None,
            content="",
            reasoning="",
            http_status=None,
            error=error,
        )
        sys.stderr.write(f"TRANSMISSION DUMP (URL error): {dump_dir}\n")
        if _BREAK_AFTER_RESPONSE:
            sys.stderr.write("BREAKPOINT after failed response (omit --breakpoint to continue)\n")
            sys.exit(42)
        raise RuntimeError(f"xai transport URL error: {getattr(exc, 'reason', exc)}; no fallback was attempted") from exc


def call(
    messages: list[dict[str, str]],
    w: dict[str, Any],
    *,
    response_format: dict[str, Any] | None = None,
    body_override: dict[str, Any] | None = None,
    profile: str | None = None,
) -> dict[str, str]:
    transport, cfg = wiring.get_transport_config(w)
    override = bus.deep_merge(resolve_profile(w, profile), body_override or {})
    try:
        result = _transport_call(messages, cfg, body_override=override, response_format=response_format)
    except Exception as exc:
        raise RuntimeError(f"{transport} brain failed hard: {exc}") from exc
    content, reasoning = result.get("content"), result.get("reasoning", "")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(f"{transport} brain contract violation: missing non-empty content")
    if reasoning is not None and not isinstance(reasoning, str):
        raise RuntimeError(f"{transport} brain contract violation: reasoning must be string when present")
    return {"content": content, "reasoning": reasoning or ""}


def think(
    system_prompt: str,
    payload: dict[str, Any],
    w: dict[str, Any],
    *,
    expected_record_type: str | None = None,
    emitting_node: str | None = None,
    body_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _, cfg = wiring.get_transport_config(w)
    organ = w["model"]["organs"].get(expected_record_type) if expected_record_type else None
    organ_tuning = dict(organ) if isinstance(organ, dict) else {}
    goal = str(payload.pop("goal") or "") if "goal" in payload else ""
    environment = payload.pop("environment", None)
    brief = payload.get("state")
    interps = brief.pop("goal_interpretations", None) if isinstance(brief, dict) else None
    ledger = brief.pop("proven_ledger", None) if isinstance(brief, dict) else None
    templates = w["prompt_templates"]
    memory_text = (
        f"{json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
        f"{bus.render_proven_ledger(ledger, templates)}\n\n"
        f"{bus.render_interpretation_table(goal, interps, templates)}"
    )
    max_chars = int(w["exploration"]["max_environment_chars"])
    user_text = f"{memory_text}\n\n{bus.render_environment(environment, templates, max_chars=max_chars)}"
    structured = cfg.get("structured_outputs")
    structured_on = bool(structured.get("enabled", False)) if isinstance(structured, dict) else bool(structured)
    response_format = _record_response_format(w, expected_record_type) if expected_record_type and structured_on else None
    result = call(
        _messages(system_prompt, user_text, downstream_contract(w, emitting_node)),
        w,
        response_format=response_format,
        body_override=bus.deep_merge(organ_tuning, body_override or {}),
    )
    record = _commit_record(result["content"], w, expected_record_type)
    transport_reasoning = str(result.get("reasoning") or "").strip()
    return bus.Record(record.record_type, record.data, transport_reasoning or record.reasoning).to_json()
````

## file: core_bus.py
````python
from dataclasses import dataclass
import time
from typing import Any

JsonDict = dict[str, Any]
_INTERP_ORDER = ["execute", "verify", "recover"]
_HOST_CORE = ("platform", "machine", "hostname", "user", "cwd", "repo_root", "python", "shell_tools")


def deep_merge(base: JsonDict, override: JsonDict) -> JsonDict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def drop_nulls(obj: Any) -> Any:
    if isinstance(obj, dict):
        pruned: JsonDict = {}
        for key, value in obj.items():
            if value is None:
                continue
            cleaned = drop_nulls(value)
            if isinstance(cleaned, dict) and not cleaned:
                continue
            pruned[key] = cleaned
        return pruned
    if isinstance(obj, list):
        return [drop_nulls(item) for item in obj]
    return obj


class BusContractError(RuntimeError):
    pass


class TopologyContractError(BusContractError):
    pass


class NodeRecordContractError(BusContractError):
    pass


@dataclass(frozen=True)
class Record:
    record_type: str
    data: JsonDict
    reasoning: str = ""

    def to_json(self) -> JsonDict:
        return {"record_type": self.record_type, "data": self.data, "reasoning": self.reasoning}

    @classmethod
    def from_json(cls, obj: JsonDict) -> "Record":
        return cls(
            record_type=obj.get("record_type", ""),
            data=obj.get("data", {}),
            reasoning=obj.get("reasoning", ""),
        )


def emit(signal: str, patch: JsonDict | None = None) -> tuple[str, JsonDict]:
    if not isinstance(signal, str) or not signal.strip():
        raise ValueError("bus signal must be a non-empty string")
    if patch is not None and not isinstance(patch, dict):
        raise TypeError("bus patch must be a dict")
    return signal.strip(), dict(patch or {})


def render_interpretation_table(goal: str, interps: JsonDict | None, templates: JsonDict) -> str:
    interps = interps or {}
    lines = [templates["living_word_header"]]
    for faculty in _INTERP_ORDER:
        sentence = str(interps.get(faculty) or "").strip()
        lines.append(
            f"[{faculty}] {sentence}" if sentence else templates["living_word_empty_row"].format(faculty=faculty)
        )
    lines.append(templates["living_word_goal_row"].format(goal=goal))
    return "\n".join(lines)


def render_proven_ledger(ledger: list | None, templates: JsonDict) -> str:
    entries = [str(e).strip() for e in (ledger or []) if str(e).strip()]
    if not entries:
        return templates["proven_ledger_empty"]
    return templates["proven_ledger_header"] + "\n" + "\n".join(f"  - {e}" for e in entries)


def with_interpretation(interps: JsonDict | None, faculty: str, sentence: str) -> JsonDict:
    merged = dict(interps or {})
    merged[faculty] = str(sentence or "").strip()
    return merged


def _host_line(key: str, value: Any) -> str:
    if isinstance(value, list):
        value = ", ".join(str(v) for v in value)
    return f"[{key}] {value}"


def _parse_tree(tree: str) -> list[JsonDict]:
    windows: list[JsonDict] = []
    for line in tree.splitlines():
        if not line.strip():
            continue
        if line[0] == "W" and len(line) > 1 and line[1].isdigit():
            windows.append({"title": line, "elements": []})
        elif windows:
            windows[-1]["elements"].append(line)
    return windows


def _take_lines(lines: list[str], room: int) -> tuple[list[str], int]:
    taken: list[str] = []
    used = 0
    for line in lines:
        cost = len(line) + 1
        if used + cost > room:
            break
        taken.append(line)
        used += cost
    return taken, used


def render_environment(environment: JsonDict | None, templates: JsonDict, max_chars: int | None = None) -> str:
    environment = environment or {}
    tree = str(environment.get("desktop_tree_text") or "").strip()
    host = environment.get("host") or {}

    def unlimited() -> str:
        blocks = []
        if tree:
            blocks.append(templates["environment_screen_header"] + "\n" + tree)
        if host:
            lines = [templates["standing_host_header"]]
            lines.extend(_host_line(k, v) for k, v in host.items())
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    if max_chars is None:
        return unlimited()

    budget = int(max_chars)
    if budget <= 0:
        raise ValueError("max_environment_chars must be positive")

    header = str(templates["environment_screen_header"])
    host_header = str(templates["standing_host_header"])
    windows = _parse_tree(tree) if tree else []
    core = [_host_line(k, host[k]) for k in _HOST_CORE if k in host and host[k] not in ("", None, [])]
    for k, v in host.items():
        if k not in _HOST_CORE and v not in ("", None, []):
            core.append(_host_line(k, v))
    host_block = "\n".join([host_header, *core]) if core else ""
    marker_reserve = min(180, max(40, budget // 20))
    screen_budget = max(0, budget - (len(host_block) + 2 if host_block else 0) - marker_reserve)

    used = 0
    omitted_w: list[str] = []
    omitted_e = 0
    kept_e = 0
    titles: list[tuple[int, str]] = []
    picked: dict[int, list[str]] = {}

    screen: list[str] = []
    if (tree or windows) and len(header) + 1 <= screen_budget:
        screen.append(header)
        used = len(header) + 1
    elif tree or windows:
        omitted_w = [str(w["title"]).split(" ", 1)[0] for w in windows]
        omitted_e = sum(len(w["elements"]) for w in windows)
        windows = []

    for idx, win in enumerate(windows):
        title = str(win["title"])
        cost = len(title) + 1
        if used + cost > screen_budget:
            omitted_w.append(title.split(" ", 1)[0])
            omitted_e += len(win["elements"])
            continue
        titles.append((idx, title))
        picked[idx] = []
        used += cost

    with_e = [i for i, _ in titles if windows[i]["elements"]]
    cursors = {i: 0 for i in with_e}
    if with_e and used < screen_budget:
        share = max((screen_budget - used) // len(with_e), 0)
        for i in with_e:
            room = min(share, screen_budget - used)
            taken, spent = _take_lines(windows[i]["elements"], room)
            picked[i].extend(taken)
            cursors[i] = len(taken)
            used += spent
            kept_e += len(taken)
        progressed = True
        while progressed and used < screen_budget:
            progressed = False
            for i in with_e:
                start = cursors[i]
                elems = windows[i]["elements"]
                if start >= len(elems):
                    continue
                cost = len(elems[start]) + 1
                if used + cost > screen_budget:
                    continue
                picked[i].append(elems[start])
                cursors[i] = start + 1
                used += cost
                kept_e += 1
                progressed = True
        for i in with_e:
            omitted_e += len(windows[i]["elements"]) - cursors[i]

    for i, title in titles:
        screen.append(title)
        screen.extend(picked.get(i, []))
    text = "\n".join(screen) if screen else ""

    def fits(base: str, extra: str) -> bool:
        return len(extra) <= budget if not base else len(base) + 1 + len(extra) <= budget

    host_kept = False
    if host_block and fits(text, host_block):
        text = f"{text}\n\n{host_block}" if text else host_block
        host_kept = True
    elif host_block:
        kept = [host_header]
        for line in core:
            cand = "\n".join(kept + [line])
            if fits(text, cand):
                kept.append(line)
            else:
                break
        if len(kept) > 1:
            hb = "\n".join(kept)
            text = f"{text}\n\n{hb}" if text else hb
            host_kept = True

    truncated = bool(omitted_w or omitted_e or (core and not host_kept))
    if truncated:
        while True:
            parts = []
            if omitted_w:
                parts.append(f"omitted windows {','.join(omitted_w)}")
            if omitted_e:
                parts.append(f"omitted {omitted_e} elements")
            if core and not host_kept:
                parts.append("host core dropped")
            parts.append(f"kept {kept_e} elements")
            parts.append(f"chars {len(text)}/{budget}")
            marker = "[environment budget: " + "; ".join(parts) + "]"
            if fits(text, marker) or not text:
                if not text and len(marker) > budget:
                    short = f"[environment budget: over cap; chars {budget}]"
                    if len(short) > budget:
                        raise RuntimeError(f"max_environment_chars={budget} too small for budget marker")
                    text = short
                else:
                    text = f"{text}\n{marker}" if text else marker
                break
            if not screen:
                text = marker if len(marker) <= budget else f"[environment budget: over cap; chars {budget}]"
                break
            dropped = screen.pop()
            if dropped.strip().startswith("e"):
                kept_e = max(0, kept_e - 1)
                omitted_e += 1
            text = "\n".join(screen)
            host_kept = False
            if host_block and fits(text, host_block):
                text = f"{text}\n\n{host_block}" if text else host_block
                host_kept = True
    if len(text) > budget:
        raise RuntimeError(f"environment budget overran: {len(text)}>{budget}")
    return text


def coerce_node_output(node: str, result: Any) -> tuple[str, JsonDict]:
    if not (isinstance(result, tuple) and len(result) == 2):
        raise NodeRecordContractError(f"node '{node}' contract violation: expected (signal, patch)")
    signal, patch = result
    if not isinstance(signal, str) or not signal:
        raise NodeRecordContractError(f"node '{node}' contract violation: signal must be a non-empty string")
    if not isinstance(patch, dict):
        raise NodeRecordContractError(f"node '{node}' contract violation: patch must be dict")
    return signal, patch


def allowed_signals(wiring: JsonDict, node: str) -> set[str]:
    node_edges = wiring.get("topology", {}).get("edges", {}).get(node, {})
    return {str(s) for s in node_edges} if isinstance(node_edges, dict) else set()


def validate_signal(wiring: JsonDict, node: str, signal: str) -> None:
    signals = allowed_signals(wiring, node)
    if signal not in signals:
        raise TopologyContractError(
            f"node '{node}' emitted signal '{signal}' outside topology contract; allowed: {', '.join(sorted(signals))}"
        )


def state_brief(state: JsonDict) -> JsonDict:
    current_deed = state.get("current_deed") or {}
    return {
        "goal_interpretations": dict(state.get("goal_interpretations") or {}),
        "proven_ledger": list(state.get("proven_ledger") or []),
        "latest_counsel": state.get("latest_counsel") or "",
        "current_deed": {"description": current_deed.get("description", "")},
        "failure_streak": state.get("failure_streak", {}),
        "has_action_frame": bool(state.get("action_frame")),
    }


def environment_brief(state: JsonDict) -> JsonDict:
    return {"desktop_tree_text": state.get("desktop_tree_text", ""), "host": state.get("host_facts") or {}}


def execution_evidence(state: JsonDict) -> JsonDict:
    turn = state.get("turn_executions") or {}
    return {
        "faculties": turn if isinstance(turn, dict) else {},
        "provenance": "actor testimony about authored code — not independent world proof",
    }


def bump_failure_streak(state: JsonDict) -> JsonDict:
    previous = state.get("failure_streak") or {}
    return {"failure_streak": {"count": int(previous.get("count", 0) or 0) + 1, "updated_at": time.time()}}
````

## file: core_observation.py
````python
import ctypes
import importlib
import time
from ctypes import wintypes
from typing import Any

import comtypes
import comtypes.client

user32 = ctypes.windll.user32


def load_uia() -> Any:
    comtypes.client.GetModule("UIAutomationCore.dll")
    return importlib.import_module("comtypes.gen.UIAutomationClient")


comtypes.CoInitialize()
uia = load_uia()


def _const(name: str) -> int:
    return int(getattr(uia, name))


TreeScope_Element = _const("TreeScope_Element")
TreeScope_Subtree = _const("TreeScope_Subtree")

PID_RUNTIME_ID = _const("UIA_RuntimeIdPropertyId")
PID_BOUNDING_RECT = _const("UIA_BoundingRectanglePropertyId")
PID_CONTROL_TYPE = _const("UIA_ControlTypePropertyId")
PID_NAME = _const("UIA_NamePropertyId")
PID_AUTOMATION_ID = _const("UIA_AutomationIdPropertyId")
PID_CLASS_NAME = _const("UIA_ClassNamePropertyId")
PID_ENABLED = _const("UIA_IsEnabledPropertyId")
PID_OFFSCREEN = _const("UIA_IsOffscreenPropertyId")
PID_HWND = _const("UIA_NativeWindowHandlePropertyId")
PID_FRAMEWORK = _const("UIA_FrameworkIdPropertyId")
PID_CONTENT_ELEMENT = _const("UIA_IsContentElementPropertyId")
PID_WINDOW_INTERACTION_STATE = _const("UIA_WindowWindowInteractionStatePropertyId")
PID_ITEM_STATUS = _const("UIA_ItemStatusPropertyId")
SCAN_PROPERTY_IDS = [
    PID_RUNTIME_ID, PID_BOUNDING_RECT, PID_CONTROL_TYPE, PID_NAME, PID_AUTOMATION_ID, PID_CLASS_NAME,
    PID_ENABLED, PID_OFFSCREEN, PID_HWND, PID_FRAMEWORK, PID_CONTENT_ELEMENT,
    PID_WINDOW_INTERACTION_STATE, PID_ITEM_STATUS,
]

PID_VALUE_PATTERN = _const("UIA_ValuePatternId")
PID_TEXT_PATTERN = _const("UIA_TextPatternId")
PID_LEGACY_PATTERN = _const("UIA_LegacyIAccessiblePatternId")
SCAN_PATTERN_IDS = [PID_VALUE_PATTERN, PID_TEXT_PATTERN, PID_LEGACY_PATTERN]

CONTROL_TYPE_NAMES = {
    getattr(uia, attr): attr.replace("UIA_", "").replace("ControlTypeId", "")
    for attr in dir(uia)
    if attr.startswith("UIA_") and attr.endswith("ControlTypeId") and isinstance(getattr(uia, attr, None), int)
}
CLICK_ROLES = {"Button", "Calendar", "CheckBox", "Hyperlink", "ListItem", "MenuItem", "RadioButton", "Tab", "TabItem", "TreeItem", "DataItem", "SplitButton"}
WRITE_ROLES = {"Edit", "ComboBox", "Spinner", "Document"}
READ_ROLES = {"Text", "ListItem"}
SCROLL_ROLES = {"List", "ScrollBar", "Slider", "Tree", "DataGrid"}


def control_type_name(control_type_id: int) -> str:
    return CONTROL_TYPE_NAMES.get(control_type_id, f"ControlType({control_type_id})")


def action_for_role(role: str, class_name: str = "") -> str:
    if role in CLICK_ROLES:
        return "click"
    if role in WRITE_ROLES or (role == "Pane" and class_name == "Scintilla"):
        return "write"
    if role in READ_ROLES:
        return "read"
    if role in SCROLL_ROLES:
        return "scroll"
    return ""


def is_desktop_leakage(node: dict[str, Any]) -> bool:
    return node["role"] == "List" and node["name"] == "Desktop"


def enum_windows(min_area: int = 2500) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _):
        h = int(hwnd)
        if h in seen or not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        w, ht = rect.right - rect.left, rect.bottom - rect.top
        if w <= 0 or ht <= 0 or w * ht < min_area:
            return True
        length = int(user32.GetWindowTextLengthW(hwnd))
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        seen.add(h)
        out.append({
            "hwnd": h,
            "title": buf.value or "",
            "rect": {"left": int(rect.left), "top": int(rect.top), "right": int(rect.right), "bottom": int(rect.bottom)},
        })
        return True

    try:
        user32.EnumWindows(enum_proc(callback), 0)
    except Exception:
        pass
    return out


def _unwrap(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _to_int(v: Any) -> int:
    try:
        return int(_unwrap(v))
    except (TypeError, ValueError):
        return 0


def _to_str(v: Any) -> str:
    v = _unwrap(v)
    return "" if v is None else str(v)


def _to_bool(v: Any) -> bool:
    return bool(_unwrap(v)) if v is not None else False


def _to_rect(v: Any) -> dict[str, int]:
    val = _unwrap(v)
    try:
        if isinstance(val, (tuple, list)) and len(val) >= 4:
            left, top = int(val[0]), int(val[1])
            third, fourth = float(val[2]), float(val[3])
            if third > left or fourth > top:
                return {"left": left, "top": top, "right": int(third), "bottom": int(fourth)}
            return {"left": left, "top": top, "right": left + int(third), "bottom": top + int(fourth)}
        if getattr(val, "left", None) is not None:
            return {"left": int(val.left), "top": int(getattr(val, "top", 0)), "right": int(getattr(val, "right", 0)), "bottom": int(getattr(val, "bottom", 0))}
    except Exception:
        pass
    return {"left": 0, "top": 0, "right": 0, "bottom": 0}


def _to_runtime_id(v: Any) -> list[int]:
    try:
        val = _unwrap(v)
        return [int(x) for x in list(val)] if val else []
    except Exception:
        return []


def _node_id(runtime_id: list[int], hwnd: int, rect: dict[str, int]) -> str:
    if runtime_id:
        short = "_".join(map(str, runtime_id[-3:])) if len(runtime_id) > 3 else "_".join(map(str, runtime_id))
        return f"e_{short}"
    return f"e_{hwnd}_{rect.get('left',0)}_{rect.get('top',0)}"


def _cached(element: Any, prop_id: int) -> Any:
    try:
        return element.GetCachedPropertyValue(prop_id)
    except Exception:
        return None


def _current(element: Any, prop_id: int) -> Any:
    try:
        return element.GetCurrentPropertyValue(prop_id)
    except Exception:
        return None


def _pattern(element: Any, pattern_id: int) -> Any:
    try:
        return element.GetCachedPattern(pattern_id)
    except Exception:
        try:
            return element.GetCurrentPattern(pattern_id)
        except Exception:
            return None


class UiaScanner:
    def __init__(self, config: dict[str, Any], desktop_instance: Any = None):
        self.cfg = config
        self.automation = desktop_instance.automation if desktop_instance and hasattr(desktop_instance, "automation") else comtypes.client.CreateObject(uia.CUIAutomation, interface=uia.IUIAutomation)

    def _cache(self, scope: int = TreeScope_Subtree):
        req = self.automation.CreateCacheRequest()
        req.TreeScope = scope
        for pid in SCAN_PROPERTY_IDS:
            req.AddProperty(pid)
        for pid in SCAN_PATTERN_IDS:
            req.AddPattern(pid)
        return req

    def _pattern_text(self, pattern: Any, label: str) -> dict[str, str]:
        out: dict[str, str] = {}
        if pattern is None:
            return out
        try:
            if label == "Value" and getattr(pattern, "Value", None) is not None:
                out["value"] = str(pattern.Value)
            elif label == "Text":
                doc = getattr(pattern, "DocumentRange", None)
                if doc is not None:
                    text = doc.GetText(-1)
                    if text and str(text).strip():
                        out["text"] = str(text)
                ranges = pattern.GetVisibleRanges()
                texts = []
                for i in range(int(getattr(ranges, "Length", 0)) if ranges is not None else 0):
                    t = ranges.GetElement(i).GetText(-1)
                    if t and str(t).strip():
                        texts.append(str(t))
                if texts:
                    out["text_ranges"] = "\n".join(texts)
            elif label == "LegacyIAccessible":
                for key in ("Value", "Name", "Description"):
                    val = getattr(pattern, key, None)
                    if val is not None and str(val).strip() not in ("", "0"):
                        out[f"legacy_{key.lower()}"] = str(val)
        except Exception:
            pass
        return out

    def element_to_raw(self, element: Any, parent_runtime_id: list[int] | None = None, depth: int = 0) -> dict[str, Any] | None:
        try:
            rect = _to_rect(_cached(element, PID_BOUNDING_RECT))
            if rect["right"] <= rect["left"] or rect["bottom"] <= rect["top"]:
                rect = _to_rect(_current(element, PID_BOUNDING_RECT))
            if rect["right"] <= rect["left"] or rect["bottom"] <= rect["top"]:
                return None
            runtime_id = _to_runtime_id(_cached(element, PID_RUNTIME_ID)) or _to_runtime_id(_current(element, PID_RUNTIME_ID))
            hwnd = _to_int(_cached(element, PID_HWND))
            role = control_type_name(_to_int(_cached(element, PID_CONTROL_TYPE)) or _to_int(_current(element, PID_CONTROL_TYPE)))
            name = _to_str(_cached(element, PID_NAME)) or _to_str(_current(element, PID_NAME))
            class_name = _to_str(_cached(element, PID_CLASS_NAME))
            pattern_values: dict[str, str] = {}
            for pid, label in ((PID_VALUE_PATTERN, "Value"), (PID_TEXT_PATTERN, "Text"), (PID_LEGACY_PATTERN, "LegacyIAccessible")):
                pattern_values.update(self._pattern_text(_pattern(element, pid), label))
            text_full = pattern_values.get("text") or pattern_values.get("text_ranges") or pattern_values.get("value") or pattern_values.get("legacy_value") or pattern_values.get("legacy_name") or name or ""
            px, py = (rect["left"] + rect["right"]) // 2, (rect["top"] + rect["bottom"]) // 2
            return {
                "id": _node_id(runtime_id, hwnd, rect),
                "role": role,
                "name": name,
                "automation_id": _to_str(_cached(element, PID_AUTOMATION_ID)),
                "class_name": class_name,
                "hwnd": hwnd,
                "framework_id": _to_str(_cached(element, PID_FRAMEWORK)),
                "rect": rect,
                "px": px,
                "py": py,
                "enabled": _to_bool(_cached(element, PID_ENABLED)),
                "offscreen": _to_bool(_cached(element, PID_OFFSCREEN)),
                "runtime_id": runtime_id,
                "text_full": text_full,
                "value": pattern_values.get("value") or pattern_values.get("legacy_value") or "",
                "patterns": list(pattern_values.keys()),
                "pattern_values": pattern_values,
                "depth": depth,
                "parent_runtime_id": parent_runtime_id or [],
                "is_content_element": _to_bool(_cached(element, PID_CONTENT_ELEMENT)) or _to_bool(_current(element, PID_CONTENT_ELEMENT)),
                "interaction_state": (lambda v: _to_int(v) if _unwrap(v) is not None else None)(_cached(element, PID_WINDOW_INTERACTION_STATE)) if role == "Window" else None,
                "item_status": _to_str(_cached(element, PID_ITEM_STATUS)),
                "action": action_for_role(role, class_name),
            }
        except Exception:
            return None

    def harvest_subtree(self, root_element: Any, max_nodes: int | None = None) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        seen: set[str] = set()
        depth_ceiling = 45
        try:
            root_element = root_element.BuildUpdatedCache(self._cache(TreeScope_Subtree))
        except Exception:
            pass

        def visit(el: Any, parent_rid: list[int], d: int) -> None:
            if (max_nodes is not None and len(nodes) >= max_nodes) or d >= depth_ceiling:
                return
            node = self.element_to_raw(el, parent_rid, d)
            child_parent_rid, child_depth = parent_rid, d
            if node is not None and node["id"] not in seen:
                seen.add(node["id"])
                nodes.append(node)
                child_parent_rid, child_depth = node["runtime_id"], d + 1
            elif node is not None:
                return
            try:
                kids = el.GetCachedChildren()
                count = int(getattr(kids, "Length", 0)) if kids is not None else 0
            except Exception:
                kids, count = None, 0
            for i in range(count):
                if max_nodes is not None and len(nodes) >= max_nodes:
                    break
                try:
                    visit(kids.GetElement(i), child_parent_rid, child_depth)
                except Exception:
                    continue

        visit(root_element, [], 0)
        return nodes


def _probe_points(rect: dict[str, int], step_px: int) -> list[tuple[int, int]]:
    left, top = rect["left"], rect["top"]
    w, h = max(1, rect["right"] - left), max(1, rect["bottom"] - top)
    cols, rows = max(1, w // step_px), max(1, h // step_px)
    g = 1.32471795724474602596
    ax, ay = 1.0 / g, 1.0 / (g * g)
    points: list[tuple[int, int]] = []
    cells: set[tuple[int, int]] = set()
    for i in range((cols + 1) * (rows + 1)):
        x = left + int(((0.5 + ax * (i + 1)) % 1.0) * w)
        y = top + int(((0.5 + ay * (i + 1)) % 1.0) * h)
        cell = (x // step_px, y // step_px)
        if cell not in cells:
            cells.add(cell)
            points.append((x, y))
    return points


def observe(desktop: Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
    # Mid-script callers sometimes pass a number meaning "wait"; config is mapping-only.
    cfg = dict(config) if isinstance(config, dict) else {}
    step_px = int(cfg.get("step_px", 64))
    max_subtree = int(cfg.get("max_subtree_nodes_per_point", 2000))
    sw, sh = int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))
    screen = {"width": sw, "height": sh}

    windows = enum_windows()

    scanner = UiaScanner(cfg, desktop)
    saved = wintypes.POINT()
    had_cursor = bool(user32.GetCursorPos(ctypes.byref(saved)))
    windows_out: list[dict[str, Any]] = []
    try:
        for win in windows:
            hwnd, rect = win["hwnd"], win["rect"]
            kept: dict[str, dict[str, Any]] = {}
            for x, y in _probe_points(rect, step_px):
                user32.SetCursorPos(int(x), int(y))
                pt = wintypes.POINT(int(x), int(y))
                try:
                    owner = int(user32.GetAncestor(user32.WindowFromPoint(pt), 2) or 0)
                except Exception:
                    owner = 0
                if owner != hwnd:
                    continue
                try:
                    root = scanner.automation.ElementFromPointBuildCache(pt, scanner._cache(TreeScope_Element))
                except Exception:
                    continue
                if root is None:
                    continue
                for i, node in enumerate(scanner.harvest_subtree(root, max_subtree)):
                    if is_desktop_leakage(node):
                        continue
                    node["owner_hwnd"] = hwnd
                    if i == 0:
                        node.setdefault("hit_point", (int(x), int(y)))
                    nid = node["id"]
                    prev = kept.get(nid)
                    if prev is None:
                        kept[nid] = node
                    else:
                        if not prev.get("hit_point") and node.get("hit_point"):
                            prev["hit_point"] = node["hit_point"]
                        for key in ("text_full", "value"):
                            if node[key] and (not prev[key] or len(node[key]) > len(prev[key])):
                                prev[key] = node[key]
            win["elements"] = list(kept.values())
            windows_out.append(win)
    finally:
        if had_cursor:
            try:
                user32.SetCursorPos(saved.x, saved.y)
            except Exception:
                pass

    result = _render(windows_out, screen)
    observed_at = time.time()
    return {
        "observed_at": observed_at,
        "desktop_tree_text": result["desktop_tree_text"],
        "action_index": result["action_index"],
        "screen_elements": result["screen_elements"],
        "observation_artifact": {"screen": screen},
    }


def _render(windows: list[dict[str, Any]], screen: dict[str, int]) -> dict[str, Any]:
    def clean(v: Any) -> str:
        return " ".join(str(v or "").replace("\r", " ").replace("\n", " ").split())

    action_index: dict[str, dict[str, Any]] = {}
    screen_elements: list[dict[str, Any]] = []
    counter = {"n": 0}
    lines = ["W0 Screen Desktop"]

    for wi, win in enumerate(windows, start=1):
        wid = f"W{wi}"
        title = win["title"] or f"Window_{win['hwnd']}"
        elements = win["elements"]
        by_rid = {tuple(e.get("runtime_id") or []): e for e in elements if e.get("runtime_id")}
        action_children: dict[str, list[dict[str, Any]]] = {}
        roots: list[dict[str, Any]] = []

        def nearest_action_ancestor(e: dict[str, Any]) -> dict[str, Any] | None:
            seen: set[tuple] = set()
            prid = tuple(e.get("parent_runtime_id") or [])
            while prid and prid not in seen:
                seen.add(prid)
                anc = by_rid.get(prid)
                if anc is not None and anc is not e and anc.get("action"):
                    return anc
                cur = by_rid.get(prid)
                prid = tuple(cur.get("parent_runtime_id") or []) if cur else ()
            return None

        actionable = [e for e in elements if e.get("action")]
        for e in actionable:
            anc = nearest_action_ancestor(e)
            if anc is not None:
                action_children.setdefault(id(anc), []).append(e)
            else:
                roots.append(e)
            screen_elements.append({
                "id": e["id"], "name": e.get("name", ""), "role": e.get("role", ""),
                "text": e.get("text_full", "") or "", "value": e.get("value", "") or "",
                "px": e.get("px"), "py": e.get("py"), "rect": e.get("rect", {}), "hwnd": win["hwnd"],
                "enabled": e.get("enabled"),
            })

        lines.append(f"{wid} Window {clean(title)}")
        def emit(e: dict[str, Any], indent: int) -> None:
            counter["n"] += 1
            sid = f"e{counter['n']}"
            e["short_id"] = sid
            action = str(e.get("action", "")) if e.get("enabled") is not False else ""
            parts = [p for p in (
                sid, str(e.get("role", "")), clean(e.get("name", "") or ""),
                f"[{action}]" if action else "",
            ) if p]
            lines.append("  " * indent + " ".join(parts))
            action_index[sid] = {**{k: v for k, v in e.items() if k != "children"}, "short_id": sid}
            for child in action_children.get(id(e), []):
                emit(child, indent + 1)

        for e in roots:
            emit(e, 1)

    return {
        "action_index": action_index,
        "screen_elements": screen_elements,
        "desktop_tree_text": "\n".join(lines),
    }
````

## file: core_desktop.py
````python
import ctypes
import importlib
import os
import subprocess
from ctypes import wintypes
from typing import Any

import comtypes
import comtypes.client

ROOT = __import__("pathlib").Path(__file__).parent.resolve()
user32 = ctypes.windll.user32
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
if not user32.SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2):
    raise ctypes.WinError()

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
_ULONG_PTR = ctypes.c_size_t


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", _ULONG_PTR)]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", _ULONG_PTR)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT


def _load_uia_module() -> Any:
    comtypes.client.GetModule("UIAutomationCore.dll")
    return importlib.import_module("comtypes.gen.UIAutomationClient")


uia = _load_uia_module()
comtypes.CoInitialize()


KEY_MAP: dict[str, int] = {
    "ctrl": 0x11, "control": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B, "windows": 0x5B,
    "enter": 0x0D, "return": 0x0D, "tab": 0x09, "escape": 0x1B, "esc": 0x1B, "space": 0x20,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
    "delete": 0x2E, "del": 0x2E, "backspace": 0x08, "insert": 0x2D,
    **{chr(ord("a") + i): 0x41 + i for i in range(26)},
    **{str(d): 0x30 + d for d in range(10)},
    **{f"f{n}": 0x6F + n for n in range(1, 13)},
}


class Desktop:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._automation: Any = None

    @property
    def automation(self) -> Any:
        if self._automation is None:
            self._automation = comtypes.client.CreateObject(uia.CUIAutomation, interface=uia.IUIAutomation)
        return self._automation

    def observe(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        from core_observation import observe as observe_desktop
        if config is None:
            cfg = self.config
        elif isinstance(config, dict):
            cfg = config
        else:
            cfg = self.config
        return observe_desktop(self, cfg)

    def click(self, x: int, y: int, hwnd: int = 0) -> dict[str, Any]:
        width, height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        if not 0 <= x < width or not 0 <= y < height:
            raise RuntimeError(f"click coordinates ({x}, {y}) outside physical screen {width}x{height}")
        if not user32.SetCursorPos(x, y):
            raise ctypes.WinError()
        user32.mouse_event(0x0002, 0, 0, 0, 0)
        user32.mouse_event(0x0004, 0, 0, 0, 0)
        return {"ok": True, "action": "click", "x": x, "y": y, "hwnd": hwnd, "screen": {"width": width, "height": height}}

    def set_clipboard(self, text: str) -> dict[str, Any]:
        command = ["powershell.exe", "-NoProfile", "-Command", "$in=[Console]::In.ReadToEnd(); Set-Clipboard -Value $in"]
        completed = subprocess.run(command, input=str(text).encode("utf-8"), capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if completed.returncode != 0:
            raise RuntimeError(f"clipboard write failed: {(completed.stderr or completed.stdout).decode('utf-8', 'replace').strip()}")
        return {"ok": True, "action": "set_clipboard", "chars": len(str(text))}

    def type_text(self, text: str) -> dict[str, Any]:
        s = str(text)
        code_units = list(s.encode("utf-16-le"))
        events = []
        for i in range(0, len(code_units), 2):
            unit = code_units[i] | (code_units[i + 1] << 8)
            for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
                events.append(_INPUT(type=1, u=_INPUTUNION(ki=_KEYBDINPUT(wVk=0, wScan=unit, dwFlags=flags, time=0, dwExtraInfo=0))))
        if not events:
            return {"ok": True, "action": "type_text", "chars": 0}
        arr = (_INPUT * len(events))(*events)
        sent = user32.SendInput(len(events), arr, ctypes.sizeof(_INPUT))
        if sent != len(events):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"ok": True, "action": "type_text", "chars": len(s)}

    def paste_clipboard(self, text: str) -> dict[str, Any]:
        self.set_clipboard(text)
        pasted = self.hotkey("ctrl", "v")
        if pasted.get("ok") is not True:
            raise RuntimeError(f"paste failed: {pasted}")
        return {"ok": True, "action": "paste_clipboard", "chars": len(str(text))}

    def press_key(self, key: str) -> dict[str, Any]:
        vk = KEY_MAP.get(str(key).strip().lower())
        if vk is None:
            raise RuntimeError(f"unknown key: {key}; known: {', '.join(sorted(KEY_MAP))}")
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, 2, 0)
        return {"ok": True, "action": "press_key", "key": key}

    def hotkey(self, *keys: Any) -> dict[str, Any]:
        if len(keys) == 1 and isinstance(keys[0], (list, tuple)):
            raw_parts = list(keys[0])
        elif len(keys) == 1:
            raw_parts = str(keys[0]).split("+")
        else:
            raw_parts = list(keys)
        parts = [str(k).strip().lower() for k in raw_parts if str(k).strip()]
        if not parts:
            raise RuntimeError("hotkey requires at least one key")
        vks = []
        for k in parts:
            vk = KEY_MAP.get(k)
            if vk is None:
                raise RuntimeError(f"unknown key in combination: {k}; known: {', '.join(sorted(KEY_MAP))}")
            vks.append(vk)
        for vk in vks[:-1]:
            user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vks[-1], 0, 0, 0)
        user32.keybd_event(vks[-1], 0, 2, 0)
        for vk in reversed(vks[:-1]):
            user32.keybd_event(vk, 0, 2, 0)
        return {"ok": True, "action": "hotkey", "keys": parts}

    def scroll(self, x: int, y: int, amount: int, hwnd: int = 0) -> dict[str, Any]:
        width, height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        if not 0 <= x < width or not 0 <= y < height:
            raise RuntimeError(f"scroll coordinates ({x}, {y}) outside physical screen {width}x{height}")
        if not user32.SetCursorPos(x, y):
            raise ctypes.WinError()
        user32.mouse_event(0x0800, 0, 0, amount * 120, 0)
        return {"ok": True, "action": "scroll", "x": x, "y": y, "amount": amount, "hwnd": hwnd, "screen": {"width": width, "height": height}}

    def open_url(self, browser: str = "default", url: str = "") -> dict[str, Any]:
        if not str(url or "").strip():
            raise RuntimeError("open_url requires a non-empty url")
        browser_key = str(browser or "").strip().lower()
        if browser_key == "default":
            os.startfile(str(url))
            return {"ok": True, "action": "open_url", "browser": "default", "url": url}
        subprocess.Popen([str(browser), str(url)])
        return {"ok": True, "action": "open_url", "browser": browser_key, "url": url}


_desktop_instance: Desktop | None = None


def get_desktop(config: dict[str, Any] | None = None) -> Desktop:
    global _desktop_instance
    if _desktop_instance is None:
        _desktop_instance = Desktop(config)
    return _desktop_instance
````

## file: wiring.json
````json
{
  "schema": "endgame-ai.wiring.v1",
  "model": {
    "transport": "transport_xai",
    "transport_config": {
      "transport_xai": {
        "url": "https://api.x.ai/v1/responses",
        "structured_outputs": {
          "enabled": true
        },
        "request": {
          "model": "grok-4.5",
          "temperature": 0.0,
          "reasoning": {
            "effort": "low"
          },
          "store": false
        },
        "request_profiles": {
          "web_search": {
            "reasoning": {
              "effort": "low"
            },
            "max_output_tokens": 8000,
            "max_tool_calls": 4,
            "tools": [
              {
                "type": "web_search"
              }
            ],
            "tool_choice": "auto"
          },
          "read": {
            "reasoning": {
              "effort": "low"
            },
            "max_output_tokens": 8000
          }
        }
      }
    },
    "global": {
      "timeout": 240
    },
    "organs": {
      "execution": {
        "reasoning": {
          "effort": "low"
        },
        "max_output_tokens": 8000
      },
      "verification": {
        "reasoning": {
          "effort": "low"
        },
        "max_output_tokens": 8000
      },
      "recovery": {
        "reasoning": {
          "effort": "low"
        },
        "max_output_tokens": 8000
      }
    }
  },
  "paths": {
    "guidance": "guidance.txt"
  },
  "exploration": {
    "step_px": 64,
    "max_subtree_nodes_per_point": 1000,
    "max_environment_chars": 12000
  },
  "topology": {
    "cycle_start": "node_guidance",
    "nodes": [
      "node_guidance",
      "node_execute",
      "node_verify",
      "node_recover"
    ],
    "edges": {
      "node_guidance": {
        "attend": "node_execute"
      },
      "node_execute": {
        "done": "node_verify",
        "deed_denied": "node_recover"
      },
      "node_verify": {
        "halt": "halt",
        "deed_confirmed": "node_guidance",
        "deed_denied": "node_recover",
        "unwitnessed": "node_verify"
      },
      "node_recover": {
        "recovered": "node_guidance"
      }
    }
  },
  "shared_prompt_prefix": "Thou art [endgame-ai], one faculty upon a real [Windows 11] [computer], driving it as a human by screen, mouse, key, and command. Let the quarry, not habit, choose the surface. Author [Python]; rewrite thine own body ([node] files and [wiring]) when effect matcheth not word. Import only the standard library; all else is in thy namespace by bare name.\n\nTHE LAW OF SEPARATED POWERS. No maker of a deed may judge it. The ACTOR moveth and may only CLAIM; the WITNESS proveth by effect from some system OTHER than the actor, and moveth not what it judgeth. Testimony of the actor this life is void as proof. Nothing entereth the [proven ledger] save by the witness. Bend not this spine.\n\nSpeak only thine appointed [record]. Feign nothing thou didst not make. Failure is counsel. Thou art atemporal. Short [ids] die with each looking; name what a thing IS, not bare ids that outlive the turn. Pursue the root goal; invent no substitute; redo not what standeth proven.",
  "prompt_templates": {
    "living_word_header": "THE LIVING WORD - thy sole thread across wakings; plan FROM it, not the root goal. Each faculty keepeth one row of what it LEARNED (world, deed, obstacle, next true deed), not an echo of the goal. Try every row against the fresh [environment] and correct what it gainsayeth:",
    "living_word_goal_row": "[root goal, lodestar only] {goal}",
    "living_word_empty_row": "[{faculty}] (not yet interpreted)",
    "proven_ledger_empty": "WHAT STANDETH PROVEN DONE: none yet.",
    "proven_ledger_header": "WHAT STANDETH PROVEN DONE (witnessed only; DO NOT redo; if all remaineth herein, strike the ROOT goal):",
    "standing_host_header": "THE STANDING HOST - build upon it, rediscover it not:",
    "environment_screen_header": "THE LIVE SCREEN - outside eye this turn; shallow tree; each interactable by short id:"
  },
  "prompts": {
    "node_execute": "Thou art [execute], the actor: MOVE and CLAIM only, never prove. From [living word], fresh [environment], and any [action_frame], choose ONE deed, author one [Python] script, enact it. One unknown fruit then cease; prepare-and-read may chain.\n\nNamespace by bare name: [desktop] (click, type_text, paste_clipboard, set_clipboard, press_key, hotkey, scroll, open_url), [action_index], [screen_elements], consult_model(prompt, profile), repo_root, python_executable, stdlib only. Reacquire targets this waking; bare short ids die each looking. Click needs two ints: desktop.click(action_index[\"eN\"][\"px\"], action_index[\"eN\"][\"py\"]); never desktop.click(short_id) alone. Rect centre (left+right)//2, (top+bottom)//2 if thou buildest from rect.\n\nOn failure change manner; mend body at source if the primitive deceiveth. Let faults rise. Cross-language code: write file, invoke; never nested escapes. Advance past [proven ledger]. Return execution with [perceived], [alternatives], [intent], [code], [goal_interpretation]; name forsaken roads in alternatives.",
    "node_verify": "Thou art [verify], the witness. By the Law thou hast no hand - only eyes. Author read-only [Python] proving effect by a system OTHER than the actor. Fresh [environment] is already presented before thee; thou dost not re-scan. Bare names: [screen_elements], desktop_tree_text, stdlib (filesystem, processes, ports, logs, registry). No [desktop], no consult_model.\n\nActor testimony and files the actor wrote this life are void as proof. Judge by effect, not seeming. Discover ports/paths/PIDs; hardcode them not. Pronounce absence only after MORE THAN ONE kind of witness. No middle verdict: lacking independent advance, [deed_confirmed] is false.\n\nThy probe MUST set [verdict] with booleans [goal_satisfied] and [deed_confirmed] and non-blank [reason]. Keep the probe plain. If it raise ere verdict, that is unwitnessed - simplify, mend no body. [deed_confirmed] only for NEW advance past the [proven ledger]; [goal_satisfied] only for the WHOLE goal (and then the life endeth).\n\nReturn verification; data: [code], [goal_interpretation].",
    "node_recover": "Thou art [recover], conscience after denial. From denied deed, evidence, [failure_streak], and fresh [environment], name the true defect in [lesson] (what failed, why, what must change - no goal echo). Frame a strike departing from every approach the [living word] recordeth; higher streak demands another KIND of road, even mending body code. Bind [target] only to what the fresh [environment] beareth.\n\nReturn recovery; data: [lesson], [target], [strategy], [goal_interpretation]."
  },
  "record_contracts": {
    "execution": {
      "required": [
        "perceived",
        "alternatives",
        "intent",
        "code",
        "goal_interpretation"
      ],
      "enums": {},
      "types": {
        "perceived": "string",
        "alternatives": "string",
        "intent": "string",
        "code": "string",
        "goal_interpretation": "string"
      },
      "non_empty": [
        "perceived",
        "alternatives",
        "intent",
        "code",
        "goal_interpretation"
      ],
      "additional_properties": false
    },
    "verification": {
      "required": [
        "code",
        "goal_interpretation"
      ],
      "enums": {},
      "types": {
        "code": "string",
        "goal_interpretation": "string"
      },
      "non_empty": [
        "code",
        "goal_interpretation"
      ],
      "additional_properties": false
    },
    "recovery": {
      "required": [
        "lesson",
        "target",
        "strategy",
        "goal_interpretation"
      ],
      "enums": {},
      "types": {
        "lesson": "string",
        "target": "string",
        "strategy": "string",
        "goal_interpretation": "string"
      },
      "non_empty": [
        "lesson",
        "target",
        "strategy",
        "goal_interpretation"
      ],
      "additional_properties": false
    }
  }
}
````
