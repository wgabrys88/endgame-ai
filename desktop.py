"""Desktop observation helpers.

The real target is Windows 11. Non-Windows environments return platform evidence only;
mechanical Windows-only actions fail hard in actions.py.
"""
from __future__ import annotations

import platform
import shutil
import subprocess
from typing import Any


def observe() -> dict[str, Any]:
    system = platform.system()
    obs: dict[str, Any] = {
        "platform": system,
        "release": platform.release(),
        "machine": platform.machine(),
    }
    if system.lower() == "windows":
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        obs["powershell"] = bool(powershell)
        if powershell:
            cp = subprocess.run(
                [powershell, "-NoProfile", "-Command", "Get-Process | Select-Object -First 5 -ExpandProperty ProcessName"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            obs["process_sample"] = cp.stdout.splitlines()
            obs["process_probe_rc"] = cp.returncode
    else:
        obs["windows_body"] = "experiment pending: not running on Windows 11"
    return obs
