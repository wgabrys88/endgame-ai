from __future__ import annotations

import json
import pathlib
import py_compile
import sys

ROOT = pathlib.Path(__file__).parent.resolve()
REQUIRED = [
    ".gitignore", ".gitattributes", "LICENSE", "README.md", "wiring.json",
    "brain.py", "nodes.py", "organism.py", "actions.py", "desktop.py",
    "workbench.py", "workbench.html", "validate_repo.py",
]
FORBIDDEN_DIRS = {".git", "__pycache__", ".pytest_cache", "live_nodes", "live_brains", "comms"}
FORBIDDEN_FILES = {"state.json", "goal.json"}
CORE_PY = ["brain.py", "nodes.py", "organism.py", "workbench.py", "actions.py", "desktop.py", "validate_repo.py"]


def fail(msg: str) -> None:
    raise SystemExit(f"validate_repo failed: {msg}")


def main() -> int:
    for rel in REQUIRED:
        if not (ROOT / rel).exists():
            fail(f"missing required file {rel}")
    for p in ROOT.iterdir():
        if p.is_dir() and p.name in FORBIDDEN_DIRS:
            fail(f"runtime/cache directory must not be packaged: {p.name}")
        if p.is_file() and (p.name in FORBIDDEN_FILES or p.suffix == ".txt"):
            fail(f"runtime/raw file must not be packaged: {p.name}")
    try:
        wiring = json.loads((ROOT / "wiring.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"wiring.json malformed: {exc}")
    transport = wiring.get("model", {}).get("transport")
    if not isinstance(transport, str) or not transport:
        fail("wiring model.transport must be a non-empty string")
    if not (ROOT / "seed_brains" / f"{transport}.py").exists():
        fail(f"selected transport {transport!r} has no seed_brains module")
    topo = wiring.get("topology", {})
    nodes = topo.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        fail("topology.nodes must be a non-empty list")
    for node in nodes:
        if not (ROOT / "seed_nodes" / f"{node}.py").exists():
            fail(f"topology node {node!r} has no seed_nodes module")
    if topo.get("cycle_start") not in nodes:
        fail("topology.cycle_start must be present in topology.nodes")
    for rel in CORE_PY:
        py_compile.compile(str(ROOT / rel), doraise=True)
    for d in ["seed_nodes", "seed_brains"]:
        files = sorted((ROOT / d).glob("*.py"))
        if not files:
            fail(f"{d} has no python files")
        for p in files:
            py_compile.compile(str(p), doraise=True)
    print("validate_repo: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
