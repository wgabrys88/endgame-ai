"""endgame — firmware for a self-evolving desktop organism. A BIOS, not an application.

THE BOOTLOADER DOCTRINE
  This file is the motherboard firmware. Like a BIOS it does four things and no more:
  it POSTs (discovers what hardware is plugged in), wires the buses, hands control to
  the installed parts, and routes signals between them. It carries NO domain knowledge —
  no desktop, no faculty prose, no goal. It is small, stable, and NOT self-mutable: the
  organism evolves by editing the parts plugged into it, never the firmware itself. A bad
  self-edit can brick a node; it can never brick the boot.

EVERYTHING IS A NODE EXCEPT THIS FILE
  Every other *.py in this folder is a hot-swappable card. Plug one in and it works; pull
  it out and the system simply lacks that faculty — no flag, no branch. Presence IS the
  switch. So there is no "gui mode": if gui.py is seated, a desktop hand appears in the
  namespace and its doc in the prompt; if not, it does not. config is a node. The faculties
  (executor, verifier, recover) are nodes. Only the firmware is fixed.

THE SWITCH / OSI VIEW  (skeleton contract every node fills)
  The kernel is a dumb layer-3 switch and each node is a packet:
      HEADER   name        — how the switch addresses it
               READS       — source sections it pulls off the blackboard   (src addr)
               WRITES      — sections it pushes back onto the blackboard    (dst addr)
               ROUTES      — signal -> next node                            (next hop)
      PAYLOAD  __doc__      — injected into the prompt   (what this packet MEANS)
               callables    — injected into the namespace (what this packet DOES)
  The firmware never interprets a payload; it only reads headers and forwards. This is why
  a new node can be skeletoned from nothing but its header — a shape every model knows.

ENTRY POINT / TEST BUS
  endgame.py is also the only way to reach a node: to exercise one in isolation you boot
  the firmware pointed at it. A test is a run; the switch is the probe.

SOURCE OF TRUTH FOR THE REWRITE
  Every behaviour here is distilled from the legacy single-file board endgame.md; each
  class names the legacy region it descends from so the chunk-by-chunk fill stays honest.
"""

import json, os, re, sys, io, subprocess, urllib.request, contextlib, pathlib, queue, threading, time, importlib, inspect, types

ROOT = pathlib.Path(__file__).resolve().parent
KERNEL = pathlib.Path(__file__).name


# ════════════════════════════════════════════════════════════════════════════════════
#  BLACKBOARD — persistent shared memory  (distills: legacy read_board/write_board, the
#  ## memory sections, ## reset defaults, cfg["state"])
#  SPLIT PERSISTENCE: machine state lives in blackboard.json; the two human-edited
#  surfaces live as plain files the human edits live between turns — goal.md and counsel.md.
# ════════════════════════════════════════════════════════════════════════════════════
class Blackboard:
    """Memory across turns. Machine sections persist to blackboard.json (atomic tmp+rename).
    goal.md and counsel.md are read FRESH each turn so a human may steer mid-run."""

    SEED = {
        "state": {"stage": None, "last_signal": None, "turn": 0, "failure_streak": 0},
        "living_word": {"execute": "", "verify": "", "recover": ""},
        "ledger": [], "action_frame": None, "perceived": "", "alternatives": "",
        "code": "", "evidence": "", "verdict": None,
        "nodes": {}, "node_edges": {},
    }
    HUMAN_FILES = {"goal": "goal.md", "counsel": "counsel.md"}

    def __init__(self, root=ROOT):
        self.root = pathlib.Path(root)
        self.path = self.root / "blackboard.json"
        if self.path.exists():
            self._m = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self._m = json.loads(json.dumps(self.SEED))  # deep copy of seed
            self.save()
        for section, fname in self.HUMAN_FILES.items():
            fp = self.root / fname
            if not fp.exists():
                fp.write_text("", encoding="utf-8")

    def get(self, section):
        if section in self.HUMAN_FILES:  # read FRESH so a human may steer mid-run
            return (self.root / self.HUMAN_FILES[section]).read_text(encoding="utf-8")
        return self._m.get(section)

    def set(self, section, value):
        if section in self.HUMAN_FILES:
            raise RuntimeError("%s is human-edited; the organism writes it not" % section)
        self._m[section] = value

    @property
    def state(self):
        return self._m["state"]

    def save(self):
        tmp = self.path.with_name(self.path.name + ".tmp.%s.%s" % (os.getpid(), time.time_ns()))
        tmp.write_text(json.dumps(self._m, ensure_ascii=False, indent=2), encoding="utf-8")
        os.rename(tmp, self.path)

    def seed(self):  # factory reset: machine memory only; human files (goal/counsel) untouched
        self._m = json.loads(json.dumps(self.SEED))
        self.save()


# ════════════════════════════════════════════════════════════════════════════════════
#  NODES & LOADER — the folder becomes the body  (distills: caps()/capabilities.build,
#  save_node/call_node, the stage-prompt/namespace wiring)
# ════════════════════════════════════════════════════════════════════════════════════
class Node:
    """A seated card. __doc__ is its packet meaning (prompt); public callables are its
    function (namespace). A node may define namespace(ctx) to inject a richer hand."""

    def __init__(self, module):
        self.module = module
        self.name = module.__name__

    @property
    def doc(self) -> str:
        return (getattr(self.module, "__doc__", "") or "").strip()

    def _public(self):
        names = getattr(self.module, "__all__", None)
        if names is None:
            names = [n for n in dir(self.module) if not n.startswith("_")]
        out = {}
        for n in names:
            obj = getattr(self.module, n, None)
            # only own definitions (skip re-exported stdlib modules pulled in by import)
            if isinstance(obj, types.ModuleType):
                continue
            if getattr(obj, "__module__", self.name) not in (self.name, None):
                if not (inspect.isclass(obj) or inspect.isfunction(obj)):
                    pass
            out[n] = obj
        return out

    def signatures(self) -> str:
        lines = []
        for n, obj in self._public().items():
            if callable(obj):
                try:
                    lines.append("%s%s" % (n, inspect.signature(obj)))
                except (ValueError, TypeError):
                    lines.append(n + "(...)")
        return "\n".join(lines)

    def namespace(self, context=None) -> dict:
        if hasattr(self.module, "namespace") and callable(self.module.namespace):
            return dict(self.module.namespace(context))
        return {n: o for n, o in self._public().items() if callable(o)}


class Faculty(Node):
    """A node that IS a stage of the wheel — a packet with routing headers. Subclasses (in
    executor.py / verifier.py / recover.py) set the header; __doc__ is the prompt payload.
        RECORD  — the strict output contract {required, types, non_empty, ...}
        READS   — blackboard sections pulled in as source
        WRITES  — record-field -> blackboard-section pushed back
        EXEC    — {field, namespace_kind, output_to} when the stage runs code, else None
        ROUTES  — signal -> next faculty name (next hop; 'halt' ends the run)
    """
    RECORD: dict = {}
    READS: tuple = ()
    WRITES: dict = {}
    EXEC: dict | None = None
    ROUTES: dict = {}


class Loader:
    """POST: import every top-level *.py in ROOT except the firmware and _private files.
    A module that defines a Faculty subclass is a faculty (its instance is that subclass);
    every other seated module is a tool node. config is NOT a node — it is constants on the
    bootloader (module-level CONFIG). Absent files contribute nothing; presence is the switch."""

    def __init__(self, root=ROOT):
        self.root = pathlib.Path(root)
        self._tools = []
        self._faculties = {}
        self._mtimes = {}
        self.reload()

    def _node_files(self):
        return sorted(p for p in self.root.glob("*.py")
                      if p.name != KERNEL and not p.name.startswith("_"))

    def reload(self):
        self._tools, self._faculties, self._mtimes = [], {}, {}
        for path in self._node_files():
            self._mtimes[path.name] = path.stat().st_mtime
            spec = importlib.util.spec_from_file_location(path.stem, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            fac_cls = self._faculty_class(module)
            if fac_cls is not None:
                self._faculties[path.stem] = fac_cls(module)
            else:
                self._tools.append(Node(module))

    @staticmethod
    def _faculty_class(module):
        for obj in vars(module).values():
            if (inspect.isclass(obj) and issubclass(obj, Faculty)
                    and obj is not Faculty and obj.__module__ == module.__name__):
                return obj
        return None

    def tools(self) -> list:
        return list(self._tools)

    def faculties(self) -> dict:
        return dict(self._faculties)

    def changed(self) -> bool:
        current = {p.name: p.stat().st_mtime for p in self._node_files()}
        return current != self._mtimes


# ════════════════════════════════════════════════════════════════════════════════════
#  TRANSPORT — the one mind, many mouths  (distills: call_llm, _build_transport_request,
#  ask_model, web_search, _call_acp, file_proxy, _record_response_format, _dump_transmission)
# ════════════════════════════════════════════════════════════════════════════════════
class Transport:
    """Speaks to the model over responses(x.ai)/chat_completions/acp/file_proxy; builds a
    strict json_schema response_format from a Faculty.RECORD; tees every exchange to
    .transmissions AND to the screen in full (no truncation — the record is the proof)."""

    def __init__(self, config):
        raise NotImplementedError("chunk 4: hold model config + run stamp")

    def response_format(self, record: dict) -> dict:
        raise NotImplementedError("chunk 4: legacy _record_response_format incl. developer_feedback inject")

    def call(self, faculty, prompt_text) -> str:
        raise NotImplementedError("chunk 4: legacy call_llm across apis (reuse the phase-4 shared builder)")

    def ask_model(self, prompt, schema=None): raise NotImplementedError("chunk 4")
    def web_search(self, query, allowed_domains=None): raise NotImplementedError("chunk 4")
    def _dump(self, *a): raise NotImplementedError("chunk 4: redacted tee to disk AND stdout")


# ════════════════════════════════════════════════════════════════════════════════════
#  STIGMERGY — routing memory, backprop, pruning  (distills: _stigmergy_confirm/_decay_only,
#  _prune_graph, node credit via pending_node_credit/pending_edges, edge reinforcement)
# ════════════════════════════════════════════════════════════════════════════════════
class Stigmergy:
    """Node-to-node edges reinforce on a proven advance and evaporate each turn; nodes below
    threshold are pruned. Credit (backprop) flows to the nodes a confirmed deed invoked."""

    def __init__(self, blackboard, config):
        raise NotImplementedError("chunk 6")

    def confirm(self, invoked_nodes, edges): raise NotImplementedError("chunk 6: reinforce + decay + credit")
    def decay_only(self): raise NotImplementedError("chunk 6")
    def prune(self): raise NotImplementedError("chunk 6: drop weak edges, budget nodes")


# ════════════════════════════════════════════════════════════════════════════════════
#  PROMPT — the board rebuilt from what is seated  (distills: render_request,
#  shared_prompt_prefix, _budget_environment, per-stage reads)
# ════════════════════════════════════════════════════════════════════════════════════
class Prompt:
    """Assembles a request: shared prefix + faculty.__doc__ + docs/signatures of the seated
    tool nodes + the blackboard sections the faculty READS (environment budgeted)."""

    PREFIX = ""  # chunk 5: the shared law (fail-hard, honest guard, no-truncation, living word)

    def __init__(self, blackboard, loader):
        raise NotImplementedError("chunk 5")

    def render(self, faculty) -> str:
        raise NotImplementedError("chunk 5: prefix + role doc + seated tool docs + read sections")


# ════════════════════════════════════════════════════════════════════════════════════
#  WHEEL — the turn loop / the switch fabric  (distills: turn(), run_exec/_run_in_process/
#  _run_as_child, spawn_actor parallel recursion, heal_if_body_changed, main())
# ════════════════════════════════════════════════════════════════════════════════════
class Wheel:
    """One turn: address the current faculty, render its packet, ask the model, apply WRITES,
    run any EXEC in a namespace built from the seated nodes, judge the signal, forward to the
    next hop. Hot-reloads a NODE when its file changes (never the firmware). Spawns budgeted
    parallel sub-actors on demand."""

    def __init__(self, root=ROOT):
        raise NotImplementedError("chunk 7: POST via Loader; wire Blackboard, Transport, Stigmergy, Prompt")

    def build_namespace(self, kind) -> dict:
        raise NotImplementedError("chunk 7: stdlib + every seated tool node's namespace + transport tools")

    def run_exec(self, code, kind) -> tuple:
        raise NotImplementedError("chunk 7: subprocess deed or in-process; signal default per kind")

    def spawn(self, subgoal, hint=""):
        raise NotImplementedError("chunk 7: parallel recursion, budgeted")

    def turn(self) -> tuple:
        raise NotImplementedError("chunk 7: the whole turn; returns (next_stage, stop)")

    def run(self, once=False):
        raise NotImplementedError("chunk 7: loop until halt")


def main():
    # chunk 8: the firmware entry — parse argv (--once/--reset/--dry/--inject/--mode/<node>),
    # boot the Wheel, or exercise a single named node as a test bus.
    raise NotImplementedError("chunk 8")


if __name__ == "__main__":
    main()
