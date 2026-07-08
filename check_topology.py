"""Topology coherence check — handles both linear (string) and fractal (list) edges.

Not part of the runtime; a dev/CI verifier. Run: python3 check_topology.py
Exit 0 = coherent, 1 = incoherent (prints reasons).
"""
from __future__ import annotations

import json
import sys


def _targets(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [t for t in value if isinstance(t, str)]
    return []


def check(path: str = "wiring.json") -> int:
    w = json.load(open(path, encoding="utf-8"))
    topo = w["topology"]
    edges = topo["edges"]
    nodes = set(topo["nodes"])
    problems: list[str] = []

    # dangling edge targets (halt is a terminal sentinel, not a node)
    for src, sigmap in edges.items():
        if src not in nodes:
            problems.append(f"edge source '{src}' not in topology.nodes")
        for sig, value in sigmap.items():
            targets = _targets(value)
            if not targets:
                problems.append(f"{src}.{sig} has no valid target(s): {value!r}")
            for t in targets:
                if t != "halt" and t not in nodes:
                    problems.append(f"{src}.{sig} -> '{t}' is not a known node")

    # reachability from cycle_start across both edge forms
    seen: set[str] = set()
    stack = [topo["cycle_start"]]
    while stack:
        cur = stack.pop()
        if cur in seen or cur == "halt":
            continue
        seen.add(cur)
        for value in edges.get(cur, {}).values():
            stack.extend(_targets(value))
    unreachable = nodes - seen
    if unreachable:
        problems.append(f"unreachable nodes from '{topo['cycle_start']}': {sorted(unreachable)}")

    if problems:
        print("TOPOLOGY INCOHERENT:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"topology coherent: {len(nodes)} nodes, all reachable from '{topo['cycle_start']}', no dangling targets")
    return 0


if __name__ == "__main__":
    sys.exit(check(sys.argv[1] if len(sys.argv) > 1 else "wiring.json"))
