"""Topology coherence check — handles both linear (string) and fractal (list) edges.

`coherence_problems(w)` is the single source of truth for topology coherence,
callable from the runtime (B5 gates mid-run topology_patch through it) and from
the CLI verifier below. Run: python3 check_topology.py
Exit 0 = coherent, 1 = incoherent (prints reasons).
"""
from __future__ import annotations

import json
import sys

SENTINELS = {"halt", "wait"}


def _targets(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [t for t in value if isinstance(t, str)]
    return []


def coherence_problems(w: dict) -> list[str]:
    """Return a list of topology-incoherence reasons for wiring `w`. Empty = coherent."""
    topo = w["topology"]
    edges = topo["edges"]
    nodes = set(topo["nodes"])
    barriers = topo["barriers"]
    problems: list[str] = []

    if topo["cycle_start"] not in nodes:
        problems.append(f"cycle_start '{topo['cycle_start']}' not in topology.nodes")

    # dangling edge targets (halt/wait are terminal sentinels, not nodes)
    for src, sigmap in edges.items():
        if src not in nodes:
            problems.append(f"edge source '{src}' not in topology.nodes")
        for sig, value in sigmap.items():
            targets = _targets(value)
            if not targets:
                problems.append(f"{src}.{sig} has no valid target(s): {value!r}")
            for t in targets:
                if t not in SENTINELS and t not in nodes:
                    problems.append(f"{src}.{sig} -> '{t}' is not a known node")

    # every wired node needs an edge map
    for n in nodes:
        if n not in edges:
            problems.append(f"node '{n}' has no edges")

    # each barrier must name a wired node with positive integer arity and a join edge
    for bnode, arity in barriers.items():
        if bnode not in nodes:
            problems.append(f"barrier '{bnode}' is not a topology node")
        if not isinstance(arity, int) or arity < 1:
            problems.append(f"barrier '{bnode}' arity must be a positive int, got {arity!r}")
        if bnode in edges and "join" not in edges[bnode]:
            problems.append(f"barrier '{bnode}' must declare a 'join' edge")

    # reachability from cycle_start across both edge forms
    seen: set[str] = set()
    stack = [topo["cycle_start"]]
    while stack:
        cur = stack.pop()
        if cur in seen or cur in SENTINELS:
            continue
        seen.add(cur)
        for value in edges.get(cur, {}).values():
            stack.extend(_targets(value))
    unreachable = nodes - seen
    if unreachable:
        problems.append(f"unreachable nodes from '{topo['cycle_start']}': {sorted(unreachable)}")
    return problems


def check(path: str = "wiring.json") -> int:
    w = json.load(open(path, encoding="utf-8"))
    problems = coherence_problems(w)
    if problems:
        print("TOPOLOGY INCOHERENT:")
        for p in problems:
            print(f"  - {p}")
        return 1
    topo = w["topology"]
    print(f"topology coherent: {len(topo['nodes'])} nodes, all reachable from '{topo['cycle_start']}', no dangling targets")
    return 0


if __name__ == "__main__":
    sys.exit(check(sys.argv[1] if len(sys.argv) > 1 else "wiring.json"))
