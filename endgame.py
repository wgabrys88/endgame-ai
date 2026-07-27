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
        raise NotImplementedError("chunk 2: load blackboard.json (seed if absent); map goal/counsel files")

    def get(self, section): raise NotImplementedError("chunk 2: machine section, or fresh read of a human file")
    def set(self, section, value): raise NotImplementedError("chunk 2")
    def save(self): raise NotImplementedError("chunk 2: atomic tmp+rename of blackboard.json")
    def seed(self): raise NotImplementedError("chunk 2: factory reset — rewrite blackboard.json to SEED; leave human files")


# ════════════════════════════════════════════════════════════════════════════════════
#  NODES & LOADER — the folder becomes the body  (distills: caps()/capabilities.build,
#  save_node/call_node, the stage-prompt/namespace wiring; config now a node too)
# ════════════════════════════════════════════════════════════════════════════════════
class Node:
    """A seated card. __doc__ is its packet meaning (prompt); public callables are its
    function (namespace). A plain data node (e.g. config.py) exposes constants instead."""

    def __init__(self, module):
        self.module = module
        self.name = module.__name__

    @property
    def doc(self) -> str:
        raise NotImplementedError("chunk 3: module __doc__, trimmed")

    def signatures(self) -> str:
        raise NotImplementedError("chunk 3: public callables' names+signatures for the prompt")

    def namespace(self, context) -> dict:
        raise NotImplementedError("chunk 3: module.namespace(ctx) if defined, else public callables")


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
    Classify each seated card as a tool Node or a Faculty. config.py is just a node whose
    constants the firmware reads for transport/budgets. Absent files contribute nothing."""

    def __init__(self, root=ROOT):
        raise NotImplementedError("chunk 3: scan+import top-level *.py; split tools vs faculties; find config node")

    def config(self) -> dict: raise NotImplementedError("chunk 3: settings from the config node")
    def tools(self) -> list: raise NotImplementedError("chunk 3")
    def faculties(self) -> dict: raise NotImplementedError("chunk 3: name -> Faculty instance")
    def changed(self) -> bool: raise NotImplementedError("chunk 7: mtimes moved — a card was hot-swapped")


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
