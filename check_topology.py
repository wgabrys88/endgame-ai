"""Topology coherence check for the single-successor wheel.

`coherence_problems(w)` is the single source of truth for topology coherence,
callable from the runtime and from the CLI verifier below. Run: python3 check_topology.py
Exit 0 = coherent, 1 = incoherent (prints reasons).
"""
from __future__ import annotations

import json
import re
import sys

import core_wiring as wiring

SENTINELS = {"halt"}


def _contract_problems(w: dict) -> list[str]:
    problems: list[str] = []
    try:
        wiring.validate_record_contracts(w)
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
    return problems


def coherence_problems(w: dict) -> list[str]:
    """Return a list of topology/contract incoherence reasons for wiring `w`. Empty = coherent."""
    topo = w["topology"]
    edges = topo["edges"]
    nodes = set(topo["nodes"])
    problems: list[str] = []
    problems.extend(_contract_problems(w))

    if topo["cycle_start"] not in nodes:
        problems.append(f"cycle_start '{topo['cycle_start']}' not in topology.nodes")

    for src, sigmap in edges.items():
        if src not in nodes:
            problems.append(f"edge source '{src}' not in topology.nodes")
        for sig, target in sigmap.items():
            if not isinstance(target, str) or not target:
                problems.append(f"{src}.{sig} has no valid target: {target!r}")
                continue
            if target not in SENTINELS and target not in nodes:
                problems.append(f"{src}.{sig} -> '{target}' is not a known node")
            if target in SENTINELS and sig != target:
                problems.append(
                    f"{src}.{sig} targets terminal name '{target}' instead of emitting terminal signal '{target}'"
                )

    node_dir = wiring.root_path(w["paths"]["nodes"])
    for n in nodes:
        if n not in edges:
            problems.append(f"node '{n}' has no edges")
        base = n.split(":", 1)[0]
        if not (node_dir / f"{base}.py").is_file():
            problems.append(f"node '{n}' has no plugin file {(node_dir / f'{base}.py')}")

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
    unreachable = nodes - seen
    if unreachable:
        problems.append(f"unreachable nodes from '{topo['cycle_start']}': {sorted(unreachable)}")
    return problems


def check(path: str = "wiring.json") -> int:
    w = json.load(open(path, encoding="utf-8"))
    try:
        wiring.validate_wiring(w)
    except Exception as exc:
        print(f"WIRING INVALID: {type(exc).__name__}: {exc}")
        return 1
    problems = coherence_problems(w)
    if problems:
        print("TOPOLOGY INCOHERENT:")
        for p in problems:
            print(f"  - {p}")
        return 1
    topo = w["topology"]
    print(f"topology coherent: {len(topo['nodes'])} nodes, all reachable from '{topo['cycle_start']}', no dangling targets; contracts coherent: {len(w['record_contracts'])} record types")
    return 0


if __name__ == "__main__":
    sys.exit(check(sys.argv[1] if len(sys.argv) > 1 else "wiring.json"))
