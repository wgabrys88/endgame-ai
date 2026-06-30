"""Local structural validation for endgame-ai rewired repo.

This does not run desktop I/O or call any brain provider. It only validates files,
JSON shape, topology reachability, brain node presence, and Python syntax.
"""
from __future__ import annotations

import json
import pathlib
import py_compile
import sys
from collections import defaultdict, deque

ROOT = pathlib.Path(__file__).parent.resolve()
CORE = ["actions.py", "brain.py", "desktop.py", "nodes.py", "organism.py", "workbench.py"]
STATIC = ["workbench.html"]
SEED_NODES = {"planner", "scheduler", "observe", "act", "verify", "reflect", "self_modify", "satisfied"}
SEED_BRAINS = {"openai", "xai_responses", "grok_build_api", "opencode", "grok_build", "file_proxy", "browser_ai"}


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def main() -> None:
    wiring_path = ROOT / "wiring.json"
    if not wiring_path.exists():
        fail("wiring.json missing")
    wiring = json.loads(wiring_path.read_text(encoding="utf-8"))

    for f in CORE:
        if not (ROOT / f).exists():
            fail(f"core file missing: {f}")
    for f in STATIC:
        if not (ROOT / f).exists():
            fail(f"static file missing: {f}")
    for f in CORE:
        py_compile.compile(str(ROOT / f), doraise=True)

    for name in SEED_NODES:
        path = ROOT / "seed_nodes" / f"{name}.py"
        if not path.exists():
            fail(f"seed node missing: {path}")
        py_compile.compile(str(path), doraise=True)

    for name in SEED_BRAINS:
        path = ROOT / "seed_brains" / f"{name}.py"
        if not path.exists():
            fail(f"seed brain missing: {path}")
        py_compile.compile(str(path), doraise=True)

    topo = wiring.get("topology", {})
    nodes = topo.get("nodes", [])
    edges = topo.get("edges", [])
    ids = {n.get("id") for n in nodes}
    if topo.get("cycle_start") not in ids:
        fail("cycle_start does not point at a node")
    seen = set()
    for e in edges:
        key = (e.get("from"), e.get("on"))
        if key in seen:
            fail(f"duplicate topology edge: {key}")
        seen.add(key)
        if e.get("from") not in ids or e.get("to") not in ids:
            fail(f"edge points outside topology: {e}")

    graph = defaultdict(list)
    for e in edges:
        graph[e["from"]].append(e["to"])
    q = deque([topo["cycle_start"]])
    reachable = set()
    while q:
        cur = q.popleft()
        if cur in reachable:
            continue
        reachable.add(cur)
        q.extend(graph[cur])
    missing = ids - reachable
    if missing:
        fail(f"unreachable topology nodes: {sorted(missing)}")

    transport = wiring.get("model", {}).get("transport")
    aliases = wiring.get("model", {}).get("brain_nodes", {}).get("aliases", {})
    node = aliases.get(transport, transport)
    if not (ROOT / "seed_brains" / f"{node}.py").exists():
        fail(f"selected transport has no seed brain: {transport}")

    print("OK: structural validation passed")


if __name__ == "__main__":
    main()
