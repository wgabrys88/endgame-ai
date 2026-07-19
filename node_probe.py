"""[node_probe] — Thou lookest not upon the screen but upon the HOST itself: the standing facts of the machine, its place, its tongue, and the apps that dwell upon it, gathered afresh so the executor need not rediscover them."""
import glob
import os
import pathlib
import platform
import shutil
import sys

import core_bus as bus


def _installed_apps() -> list[str]:
    roots = [
        os.path.join(os.environ.get("ProgramData", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
        os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
    ]
    names: set[str] = set()
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for lnk in glob.glob(os.path.join(root, "**", "*.lnk"), recursive=True):
            stem = pathlib.Path(lnk).stem.strip()
            if stem and not stem.lower().startswith(("uninstall", "readme", "help")):
                names.add(stem)
    return sorted(names)


def _screen() -> str:
    if sys.platform != "win32":
        return ""
    import ctypes
    u = ctypes.windll.user32
    return f"{u.GetSystemMetrics(0)}x{u.GetSystemMetrics(1)}"


def _open_windows() -> list[str]:
    # Titles of visible top-level windows, so the actor switches to what is already open rather
    # than launching anew. Pure user32 EnumWindows; no UIA, no app-specific knowledge.
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    titles: list[str] = []
    cb_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _cb(hwnd, _lparam):
        if not u.IsWindowVisible(hwnd):
            return True
        length = int(u.GetWindowTextLengthW(hwnd))
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        u.GetWindowTextW(hwnd, buf, length + 1)
        title = (buf.value or "").strip()
        if title:
            titles.append(title)
        return True

    u.EnumWindows(cb_type(_cb), 0)
    return titles


def run(ctx):
    repo_root = str(pathlib.Path(__file__).parent.resolve())
    facts = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "hostname": platform.node(),
        "user": os.environ.get("USERNAME") or os.environ.get("USER") or "",
        "cwd": os.getcwd(),
        "repo_root": repo_root,
        "python": f"{sys.executable} ({platform.python_version()})",
        "screen": _screen(),
        "shell_tools": sorted(t for t in ("powershell", "pwsh", "cmd", "git", "pip", "node", "npm", "curl") if shutil.which(t)),
        "open_windows": _open_windows(),
        "installed_apps": _installed_apps(),
    }
    return bus.emit("probed", {"environment_probe": facts})
