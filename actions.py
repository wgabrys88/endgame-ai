"""Mechanical body actions for Windows desktop operation.

The action layer is intentionally small and fail-hard. Unknown actions raise.
"""
from __future__ import annotations

import os
import platform
import subprocess
from typing import Any


def perform(action: dict[str, Any] | str | None) -> dict[str, Any]:
    if action is None:
        action = {"verb": "noop"}
    if isinstance(action, str):
        action = {"verb": action}
    if not isinstance(action, dict):
        raise RuntimeError(f"invalid action payload: {action!r}")
    verb = str(action.get("verb") or "noop")
    if verb == "noop":
        return {"ok": True, "verb": "noop", "detail": "no operation"}
    if verb == "open_notepad":
        if platform.system().lower() != "windows":
            raise RuntimeError("open_notepad requires Windows; this is a Windows 11 body action")
        subprocess.Popen(["notepad.exe"], close_fds=True)
        return {"ok": True, "verb": "open_notepad", "detail": "notepad.exe launched"}
    if verb == "shell":
        command = action.get("command")
        if not isinstance(command, str) or not command.strip():
            raise RuntimeError("shell action requires non-empty command")
        timeout = float(action.get("timeout", 30))
        cp = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
        if cp.returncode != 0:
            raise RuntimeError(f"shell action failed rc={cp.returncode}: {cp.stderr.strip()}")
        return {"ok": True, "verb": "shell", "stdout": cp.stdout, "stderr": cp.stderr}
    raise RuntimeError(f"unknown action verb '{verb}'; no fallback action was attempted")
