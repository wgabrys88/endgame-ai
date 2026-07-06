#!/usr/bin/env python3
"""
PowerShell Bridge - Deterministic PowerShell execution for endgame-ai.
Eliminates shell syntax issues (&&, ||, |) by using subprocess directly.
Usage: python ps_bridge.py run "command"
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


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: ps_bridge.py run \"command\" | git_status | git_diff | git_add | git_commit | git_log | pyright | vulture | pyan3 | pydeps | code2flow | pycallgraph"}))
        sys.exit(1)

    bridge = PSBridge()
    cmd = sys.argv[1]

    if cmd == "run":
        if len(sys.argv) < 3:
            print(json.dumps({"error": "run requires a command"}))
            sys.exit(1)
        result = bridge.run(" ".join(sys.argv[2:]))
    elif cmd == "git_status":
        result = bridge.run("git status --porcelain")
    elif cmd == "git_diff":
        result = bridge.run("git diff " + " ".join(sys.argv[2:]))
    elif cmd == "git_add":
        result = bridge.run("git add " + " ".join(sys.argv[2:]))
    elif cmd == "git_commit":
        if len(sys.argv) < 3:
            print(json.dumps({"error": "git_commit requires message"}))
            sys.exit(1)
        result = bridge.run(f'git commit -m "{sys.argv[2]}"')
    elif cmd == "git_log":
        n = sys.argv[2] if len(sys.argv) > 2 else "10"
        result = bridge.run(f"git log --oneline -{n}")
    elif cmd == "pyright":
        target = sys.argv[2] if len(sys.argv) > 2 else "."
        result = bridge.run(f"python -m pyright --outputjson {target}")
    elif cmd == "vulture":
        target = sys.argv[2] if len(sys.argv) > 2 else "."
        min_conf = sys.argv[3] if len(sys.argv) > 3 else "80"
        result = bridge.run(f"python -m vulture {target} --min-confidence {min_conf}")
    elif cmd == "pyan3":
        target = sys.argv[2] if len(sys.argv) > 2 else "."
        result = bridge.run(f"python -m pyan3 {target} --uses --no-defines --colored --grouped --annotated --format dot")
    elif cmd == "pydeps":
        target = sys.argv[2] if len(sys.argv) > 2 else "."
        result = bridge.run(f"pydeps {target} --noshow")
    elif cmd == "code2flow":
        target = sys.argv[2] if len(sys.argv) > 2 else "."
        result = bridge.run(f"code2flow {target} --format dot")
    elif cmd == "pycallgraph":
        target = sys.argv[2] if len(sys.argv) > 2 else "."
        result = bridge.run(f"python -m pycallgraph {target}")
    else:
        print(json.dumps({"error": f"Unknown command: {cmd}"}))
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()