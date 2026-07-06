#!/usr/bin/env python3
"""
PowerShell Bridge - Deterministic PowerShell execution for endgame-ai.
Eliminates shell syntax issues (&&, ||, |) by using subprocess directly.
"""

import subprocess
import json
import sys
from pathlib import Path
from typing import Any, Optional


class PSBridge:
    """Deterministic PowerShell command executor."""

    def __init__(self, workdir: Optional[str] = None):
        self.workdir = Path(workdir) if workdir else Path.cwd()

    def run(self, command: str, timeout: int = 120000) -> dict[str, Any]:
        """Execute a PowerShell command and return structured result."""
        result = subprocess.run(
            ["powershell.exe", "-Command", command],
            cwd=self.workdir,
            capture_output=True,
            text=True,
            timeout=timeout / 1000,
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0,
        }

    def run_script(self, script_path: str, timeout: int = 120000) -> dict[str, Any]:
        """Execute a .ps1 script file."""
        return self.run(f"& '{script_path}'", timeout)

    def git_status(self) -> dict[str, Any]:
        return self.run("git status --porcelain")

    def git_diff(self, *args: str) -> dict[str, Any]:
        cmd = "git diff " + " ".join(args)
        return self.run(cmd)

    def git_add(self, *args: str) -> dict[str, Any]:
        cmd = "git add " + " ".join(args)
        return self.run(cmd)

    def git_commit(self, message: str) -> dict[str, Any]:
        return self.run(f'git commit -m "{message}"')

    def git_log(self, n: int = 10) -> dict[str, Any]:
        return self.run(f"git log --oneline -{n}")

    def pyright(self, target: str = ".", output_json: bool = True) -> dict[str, Any]:
        cmd = f"python -m pyright {'--outputjson' if output_json else ''} {target}"
        return self.run(cmd)

    def vulture(self, target: str = ".", min_confidence: int = 80) -> dict[str, Any]:
        cmd = f"python -m vulture {target} --min-confidence {min_confidence}"
        return self.run(cmd)

    def pyan3(self, target: str = ".", **kwargs) -> dict[str, Any]:
        """Generate call graph with pyan3 (static analysis, revived Feb 2026)."""
        flags = []
        if kwargs.get("uses"):
            flags.append("--uses")
        if kwargs.get("no_defines"):
            flags.append("--no-defines")
        if kwargs.get("colored"):
            flags.append("--colored")
        if kwargs.get("grouped"):
            flags.append("--grouped")
        if kwargs.get("annotated"):
            flags.append("--annotated")
        if kwargs.get("format"):
            flags.append(f"--{kwargs['format']}")
        if kwargs.get("depth"):
            flags.append(f"--depth {kwargs['depth']}")
        cmd = f"pyan3 {target} {' '.join(flags)}"
        return self.run(cmd)

    def pydeps(self, target: str = ".", **kwargs) -> dict[str, Any]:
        """Module dependency visualization with pydeps."""
        flags = []
        if kwargs.get("reverse"):
            flags.append("--reverse")
        if kwargs.get("noshow"):
            flags.append("--noshow")
        if kwargs.get("output"):
            flags.append(f"-o {kwargs['output']}")
        if kwargs.get("max_bacon"):
            flags.append(f"--max-bacon {kwargs['max_bacon']}")
        cmd = f"pydeps {target} {' '.join(flags)}"
        return self.run(cmd)

    def code2flow(self, target: str = ".", **kwargs) -> dict[str, Any]:
        """Dynamic call graph with code2flow."""
        flags = []
        if kwargs.get("output"):
            flags.append(f"-o {kwargs['output']}")
        if kwargs.get("format"):
            flags.append(f"--format {kwargs['format']}")
        cmd = f"code2flow {target} {' '.join(flags)}"
        return self.run(cmd)

    def pycallgraph(self, target: str = ".", **kwargs) -> dict[str, Any]:
        """Execution-based call graph with python-call-graph."""
        flags = []
        if kwargs.get("output"):
            flags.append(f"-o {kwargs['output']}")
        if kwargs.get("format"):
            flags.append(f"-f {kwargs['format']}")
        cmd = f"python -m pycallgraph {target} {' '.join(flags)}"
        return self.run(cmd)


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: ps_bridge.py <command> [args...]"}))
        sys.exit(1)

    bridge = PSBridge()
    cmd = sys.argv[1]

    if cmd == "run":
        if len(sys.argv) < 3:
            print(json.dumps({"error": "run requires a command"}))
            sys.exit(1)
        result = bridge.run(" ".join(sys.argv[2:]))
    elif cmd == "git_status":
        result = bridge.git_status()
    elif cmd == "git_diff":
        result = bridge.git_diff(*sys.argv[2:])
    elif cmd == "git_add":
        result = bridge.git_add(*sys.argv[2:])
    elif cmd == "git_commit":
        if len(sys.argv) < 3:
            print(json.dumps({"error": "git_commit requires message"}))
            sys.exit(1)
        result = bridge.git_commit(sys.argv[2])
    elif cmd == "git_log":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        result = bridge.git_log(n)
    elif cmd == "pyright":
        target = sys.argv[2] if len(sys.argv) > 2 else "."
        result = bridge.pyright(target)
    elif cmd == "vulture":
        target = sys.argv[2] if len(sys.argv) > 2 else "."
        min_conf = int(sys.argv[3]) if len(sys.argv) > 3 else 80
        result = bridge.vulture(target, min_conf)
    elif cmd == "pyan3":
        target = sys.argv[2] if len(sys.argv) > 2 else "."
        result = bridge.pyan3(target)
    elif cmd == "pydeps":
        target = sys.argv[2] if len(sys.argv) > 2 else "."
        result = bridge.pydeps(target)
    elif cmd == "code2flow":
        target = sys.argv[2] if len(sys.argv) > 2 else "."
        result = bridge.code2flow(target)
    elif cmd == "pycallgraph":
        target = sys.argv[2] if len(sys.argv) > 2 else "."
        result = bridge.pycallgraph(target)
    else:
        print(json.dumps({"error": f"Unknown command: {cmd}"}))
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()