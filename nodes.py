"""nodes — the self-evolution substrate.

A "node" is an independent Python module on disk. The organism can create, modify,
delete, and hot-swap nodes at RUNTIME, then execute them directly. This is the primary
mechanism by which the system expands its own capabilities.

A node file is plain Python executed in a namespace that contains:
    ctx     -> the live organism context (state, memory, last reasoning, brain, hands)
    emit    -> emit(signal, **patch): set the next signal and merge data into state
    log     -> log(msg): append to the narration stream
plus the stdlib modules already imported here (time, json, re, os, pathlib).

After execution a node is expected to have called emit() at least once. Whatever it
merged into ctx.state persists; whatever signal it emitted decides what happens next.

══════════════════════════════════════════════════════════════════════════════
 THE SINGLE SAFETY POINT
══════════════════════════════════════════════════════════════════════════════
Safety exists in exactly ONE place in the whole system: write_node(). That is the
moment the organism writes or modifies its own executable code. When autonomy is
disabled (the default), write_node() refuses and asks the human. When the launch
flag enables autonomy, write_node() proceeds with no questions asked. There are no
other gates anywhere — execution, desktop control, and deletion are all unguarded by
design, because this is an explicit human-replacement operator.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import time

ROOT = pathlib.Path(__file__).parent.resolve()
NODES_DIR = ROOT / "live_nodes"
SEED_DIR = ROOT / "seed"

_IDENT = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def ensure_nodes() -> None:
    """Populate the live node dir from seed on first run. Live nodes are mutable."""
    NODES_DIR.mkdir(parents=True, exist_ok=True)
    if SEED_DIR.exists():
        for src in SEED_DIR.glob("*.py"):
            dst = NODES_DIR / src.name
            if not dst.exists():
                dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def list_nodes() -> list[str]:
    NODES_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(p.stem for p in NODES_DIR.glob("*.py"))


def read_node(name: str) -> str:
    p = NODES_DIR / f"{name}.py"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def node_catalog() -> str:
    """A compact menu of available nodes + their one-line docstrings, for the brain."""
    out = []
    for name in list_nodes():
        src = read_node(name)
        doc = ""
        m = re.search(r'^\s*"""(.*?)("""|\n)', src, flags=re.S)
        if m:
            doc = m.group(1).strip().splitlines()[0][:90]
        out.append(f"- {name}: {doc}")
    return "\n".join(out) or "(no nodes yet)"


# ── THE SINGLE SAFETY POINT ──────────────────────────────────────────────────
def write_node(name: str, code: str, autonomous: bool) -> tuple[bool, str]:
    """Create or modify a node. This is the only safety gate in the system.

    autonomous=False -> refuse and surface the proposed code for a human decision.
    autonomous=True  -> write it. Full power, no further questions.
    """
    if not _IDENT.match(name or ""):
        return False, f"invalid node name: {name!r} (must be a Python identifier)"
    if not autonomous:
        return False, (
            f"SAFETY: node write blocked (autonomy disabled). The organism wanted to "
            f"write node '{name}'. Re-launch with --autonomous to allow self-modification.\n"
            f"--- proposed code ---\n{code}"
        )
    NODES_DIR.mkdir(parents=True, exist_ok=True)
    (NODES_DIR / f"{name}.py").write_text(code.rstrip() + "\n", encoding="utf-8")
    return True, f"wrote node '{name}' ({len(code)} chars)"


def delete_node(name: str) -> tuple[bool, str]:
    """Delete a node. Unguarded by design (not a code-authoring act)."""
    p = NODES_DIR / f"{name}.py"
    if not p.exists():
        return False, f"no such node: {name}"
    p.unlink()
    return True, f"deleted node '{name}'"


def execute_node(name: str, ctx) -> tuple[str, dict]:
    """Hot-load the node file fresh and run it. Returns (signal, state_patch).

    Reading the file every call is deliberate: a node modified mid-run is picked up
    on its next execution with no reload machinery.
    """
    p = NODES_DIR / f"{name}.py"
    if not p.exists():
        return "missing", {"error": f"node '{name}' not found"}
    code = p.read_text(encoding="utf-8")
    result = {"signal": None, "patch": {}}

    def emit(signal: str, **patch):
        result["signal"] = signal
        result["patch"].update(patch)

    def log(msg: str):
        ctx.narrate(f"[{name}] {msg}")

    ns = {
        "ctx": ctx, "emit": emit, "log": log,
        "time": time, "json": json, "re": re, "os": os, "pathlib": pathlib,
    }
    exec(compile(code, str(p), "exec"), ns, ns)
    return result["signal"] or "done", result["patch"]
