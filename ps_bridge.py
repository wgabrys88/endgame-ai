from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent


def _json(result: dict[str, Any]) -> int:
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return int(result.get("exit_code", 1))


def _run(args: list[str], *, timeout: float | None = None) -> dict[str, Any]:
    if not args:
        return {
            "exit_code": 2,
            "stdout": "",
            "stderr": "missing command",
            "success": False,
            "command": args,
        }
    try:
        cp = subprocess.run(
            args,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "exit_code": cp.returncode,
            "stdout": cp.stdout,
            "stderr": cp.stderr,
            "success": cp.returncode == 0,
            "command": args,
        }
    except FileNotFoundError as exc:
        return {
            "exit_code": 127,
            "stdout": "",
            "stderr": str(exc),
            "success": False,
            "command": args,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "exit_code": 124,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or f"timeout after {exc.timeout}s",
            "success": False,
            "command": args,
        }


def _split_command(parts: list[str]) -> list[str]:
    if len(parts) == 1:
        return shlex.split(parts[0], posix=False)
    return parts


def _vulture_args(args: list[str]) -> list[str]:
    if args and args[-1].isdigit():
        return [sys.executable, "-m", "vulture", *args[:-1], "--min-confidence", args[-1]]
    return [sys.executable, "-m", "vulture", *(args or ["."])]


def dispatch(argv: list[str]) -> dict[str, Any]:
    if not argv:
        return {
            "exit_code": 2,
            "stdout": "",
            "stderr": "usage: python ps_bridge.py <run|git_status|git_diff|git_add|git_commit|git_log|pyright|vulture|pyan3|pydeps|code2flow|pycallgraph> [...]",
            "success": False,
        }

    cmd, rest = argv[0], argv[1:]
    if cmd == "run":
        return _run(_split_command(rest))
    if cmd == "git_status":
        return _run(["git", "status", "--short", "--branch"])
    if cmd == "git_diff":
        return _run(["git", "diff", *rest])
    if cmd == "git_add":
        return _run(["git", "add", "--", *rest])
    if cmd == "git_commit":
        message = " ".join(rest).strip()
        if not message:
            return {"exit_code": 2, "stdout": "", "stderr": "git_commit requires a message", "success": False}
        return _run(["git", "commit", "-m", message])
    if cmd == "git_log":
        count = rest[0] if rest else "20"
        return _run(["git", "log", f"-{count}", "--oneline", "--decorate"])
    if cmd == "pyright":
        return _run([sys.executable, "-m", "pyright", *(rest or ["."])])
    if cmd == "vulture":
        return _run(_vulture_args(rest))
    if cmd == "pyan3":
        return _run(["pyan3", *(rest or ["."])])
    if cmd == "pydeps":
        return _run([sys.executable, "-m", "pydeps", *(rest or ["."])])
    if cmd == "code2flow":
        return _run([sys.executable, "-m", "code2flow", *(rest or ["."])])
    if cmd == "pycallgraph":
        return _run([sys.executable, "-m", "pycallgraph", *rest])
    return {"exit_code": 2, "stdout": "", "stderr": f"unknown ps_bridge command: {cmd}", "success": False}


def main(argv: list[str] | None = None) -> int:
    return _json(dispatch(list(argv if argv is not None else sys.argv[1:])))


if __name__ == "__main__":
    raise SystemExit(main())
