from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable
import os
import re
import time

from config import (
    BASE_DIR, DELAY_FOCUS, DELAY_CURSOR_SETTLE, DELAY_MOUSE_HOLD,
    DELAY_CHAR_SEND, DELAY_KEY_INTER, MAX_WAIT_SECONDS,
    COMMAND_TIMEOUT_SECONDS, COMMAND_EXECUTABLE, COMMAND_SHELL,
    MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, MOUSEEVENTF_WHEEL,
    WHEEL_DELTA, INPUT_KEYBOARD, KEYEVENTF_EXTENDEDKEY,
    KEYEVENTF_KEYUP, KEYEVENTF_UNICODE, KEYEVENTF_UNICODE_KEYUP,
    DEFAULT_SCROLL_AMOUNT,
)
from win32 import user32, get_window_title, VK_MAP, EXTENDED_VKS, INPUT

__all__ = ["execute_verb", "execute_step", "is_python_step", "ActionResult", "VERBS"]

FILE_ALIASES: dict[str, str] = {"reactor.py": "engine.py", "planner.py": "agents.py"}

type ElementBook = dict[str, Any]
type VerbFn = Callable[[dict[str, Any], ElementBook], ActionResult]


@dataclass(slots=True)
class ActionResult:
    verb: str
    success: bool
    observation: str
    data: dict[str, Any] = field(default_factory=lambda: dict[str, Any]())


VERBS: dict[str, VerbFn] = {}


def execute_verb(verb: str, args: dict[str, Any], book: ElementBook, _state: Any) -> ActionResult:
    handler = VERBS.get(verb)
    if not handler:
        return ActionResult(verb=verb, success=False,
                            observation=f"unknown verb: {verb}. Valid: {', '.join(sorted(VERBS))}")
    try:
        return handler(args, book)
    except Exception as e:
        return ActionResult(verb=verb, success=False, observation=f"ERROR: {type(e).__name__}: {e}")


def _register(name: str) -> Callable[[VerbFn], VerbFn]:
    def decorator(fn: VerbFn) -> VerbFn:
        VERBS[name] = fn
        return fn
    return decorator


@_register("click")
def _click(args: dict[str, Any], book: ElementBook) -> ActionResult:
    selector = str(args.get("selector", ""))
    if selector not in book:
        return ActionResult("click", False, f"selector {selector} not in book")
    entry = book[selector]
    px, py = entry.px + entry.pw // 2, entry.py + entry.ph // 2
    user32.SetForegroundWindow(entry.hwnd)
    time.sleep(DELAY_FOCUS)
    user32.SetCursorPos(px, py)
    time.sleep(DELAY_CURSOR_SETTLE)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(DELAY_MOUSE_HOLD)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    return ActionResult("click", True, f"clicked {entry.role} '{entry.name}' at ({px},{py})")


@_register("write")
def _write(args: dict[str, Any], book: ElementBook) -> ActionResult:
    import ctypes
    selector = str(args.get("selector", ""))
    text = str(args.get("text", ""))
    if not text:
        return ActionResult("write", False, "text is empty")
    if selector and selector in book:
        entry = book[selector]
        user32.SetForegroundWindow(entry.hwnd)
        time.sleep(DELAY_FOCUS)
    for char in text:
        code = ord(char)
        inputs = (INPUT * 2)()
        inputs[0].type = INPUT_KEYBOARD
        inputs[0].u.ki.wScan = code
        inputs[0].u.ki.dwFlags = KEYEVENTF_UNICODE
        inputs[1].type = INPUT_KEYBOARD
        inputs[1].u.ki.wScan = code
        inputs[1].u.ki.dwFlags = KEYEVENTF_UNICODE_KEYUP
        user32.SendInput(2, ctypes.byref(inputs), ctypes.sizeof(INPUT))
        time.sleep(DELAY_CHAR_SEND)
    return ActionResult("write", True, f"typed {len(text)} chars")


@_register("press")
def _press(args: dict[str, Any], book: ElementBook) -> ActionResult:
    key = str(args.get("key", "")).lower()
    if not key:
        return ActionResult("press", False, "key is empty")
    if key not in VK_MAP:
        return ActionResult("press", False, f"unknown key: {key}")
    vk = VK_MAP[key]
    flags = KEYEVENTF_EXTENDEDKEY if vk in EXTENDED_VKS else 0
    user32.keybd_event(vk, 0, flags, None)
    time.sleep(DELAY_KEY_INTER)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP | flags, None)
    return ActionResult("press", True, f"pressed {key}")


@_register("hotkey")
def _hotkey(args: dict[str, Any], book: ElementBook) -> ActionResult:
    keys: list[str] = args.get("keys", [])
    if not keys:
        return ActionResult("hotkey", False, "keys is empty")
    vks: list[int] = []
    for k in keys:
        k = k.lower()
        if k not in VK_MAP:
            return ActionResult("hotkey", False, f"unknown key: {k}")
        vks.append(VK_MAP[k])
    for vk in vks:
        user32.keybd_event(vk, 0, KEYEVENTF_EXTENDEDKEY if vk in EXTENDED_VKS else 0, None)
        time.sleep(DELAY_KEY_INTER)
    for vk in reversed(vks):
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP | (KEYEVENTF_EXTENDEDKEY if vk in EXTENDED_VKS else 0), None)
        time.sleep(DELAY_KEY_INTER)
    return ActionResult("hotkey", True, f"pressed {'+'.join(keys)}")


@_register("scroll")
def _scroll(args: dict[str, Any], book: ElementBook) -> ActionResult:
    selector = str(args.get("selector", ""))
    amount = int(args.get("amount", DEFAULT_SCROLL_AMOUNT))
    if selector not in book:
        return ActionResult("scroll", False, f"selector {selector} not in book")
    entry = book[selector]
    px, py = entry.px + entry.pw // 2, entry.py + entry.ph // 2
    user32.SetForegroundWindow(entry.hwnd)
    time.sleep(DELAY_FOCUS)
    user32.SetCursorPos(px, py)
    time.sleep(DELAY_CURSOR_SETTLE)
    user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, amount * WHEEL_DELTA, 0)
    return ActionResult("scroll", True, f"scrolled {amount} at ({px},{py})")


@_register("wait")
def _wait(args: dict[str, Any], book: ElementBook) -> ActionResult:
    seconds = min(float(args.get("seconds", 1.0)), MAX_WAIT_SECONDS)
    time.sleep(seconds)
    return ActionResult("wait", True, f"waited {seconds}s")


@_register("focus")
def _focus(args: dict[str, Any], book: ElementBook) -> ActionResult:
    title = str(args.get("window_title", ""))
    if not title:
        return ActionResult("focus", False, "no window_title")
    hwnd = user32.GetTopWindow(None)
    while hwnd:
        if user32.IsWindowVisible(hwnd):
            wt = get_window_title(int(hwnd))
            if title.lower() in wt.lower():
                user32.SetForegroundWindow(hwnd)
                time.sleep(DELAY_FOCUS)
                return ActionResult("focus", True, f"focused '{wt}'")
        hwnd = user32.GetWindow(hwnd, 2)
    return ActionResult("focus", False, f"no window matching '{title}'")


@_register("read_file")
def _read_file(args: dict[str, Any], book: ElementBook) -> ActionResult:
    from pathlib import Path
    path = str(args.get("path", ""))
    target = Path(path) if Path(path).is_absolute() else BASE_DIR / path
    resolved = target.resolve()
    if not resolved.exists():
        return ActionResult("read_file", False, f"not found: {path}")
    if resolved.is_dir():
        files = [f.name for f in sorted(resolved.iterdir())]
        return ActionResult("read_file", True, "\n".join(files))
    return ActionResult("read_file", True, resolved.read_text(encoding="utf-8"))


@_register("write_file")
def _write_file(args: dict[str, Any], book: ElementBook) -> ActionResult:
    from pathlib import Path
    path = str(args.get("path", ""))
    content = str(args.get("content", ""))
    target = Path(path) if Path(path).is_absolute() else BASE_DIR / path
    resolved = target.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    return ActionResult("write_file", True, f"wrote {len(content)} bytes to {path}")


def _sanitize_cmd(command: str) -> str:
    command = command.replace("\u201c", "\"").replace("\u201d", "\"").replace("\u2018", "'").replace("\u2019", "'")
    low = command.lower().strip()
    if "tasklist" in low and "/fi" in low:
        if "opera" in low:
            return r'tasklist /FI "IMAGENAME eq opera.exe"'
        m = re.search(r"eq\s+(\S+\.exe)", low)
        if m:
            return f'tasklist /FI "IMAGENAME eq {m.group(1)}"'
    local = os.environ.get("LOCALAPPDATA", "")
    opera_glob = f"dir /s /b {local}\\Programs\\Opera\\opera.exe" if local else ""
    if opera_glob and low.startswith("dir /s /b") and "opera" in low:
        return opera_glob
    if opera_glob and (low.startswith("where opera") or low == "where opera.exe"):
        return opera_glob
    return command


def _cmd_success(command: str, output: str, returncode: int) -> bool:
    if returncode == 0:
        return True
    low_cmd = command.lower()
    low_out = output.lower()
    if "where" in low_cmd and (".exe" in low_out or ":\\" in output):
        return True
    if "dir /s /b" in low_cmd and "opera.exe" in low_out:
        return True
    if "tasklist" in low_cmd and ("no tasks are running" in low_out or "opera.exe" in low_out):
        return True
    if "findstr" in low_cmd and "opera" in low_out:
        return True
    if "wmic" in low_cmd and ("processid" in low_out or "no instance" in low_out):
        return True
    return False


@_register("cmd")
def _cmd(args: dict[str, Any], book: ElementBook) -> ActionResult:
    import subprocess
    command = _sanitize_cmd(str(args.get("command", "")))
    if not command:
        return ActionResult("cmd", False, "no command")
    low = command.lower()
    if low.startswith("start"):
        try:
            subprocess.Popen(
                command,
                shell=True,
                cwd=str(BASE_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return ActionResult("cmd", True, "launched in background")
        except Exception as e:
            return ActionResult("cmd", False, f"launch failed: {e}")
    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
            cwd=str(BASE_DIR),
        )
        output = (proc.stdout + proc.stderr).strip()
        ok = _cmd_success(command, output, proc.returncode)
        return ActionResult("cmd", ok, output or f"exit {proc.returncode}")
    except subprocess.TimeoutExpired:
        if "start" in low:
            return ActionResult("cmd", True, "launched in background")
        return ActionResult("cmd", False, f"timed out after {COMMAND_TIMEOUT_SECONDS}s")


def is_python_step(step: str) -> bool:
    low = step.strip().lower()
    if low.startswith(("cmd ", "read_file ", "write_file ")):
        return True
    if low.startswith("wait "):
        try:
            float(step.split(None, 1)[1])
            return True
        except (IndexError, ValueError):
            return False
    return False


def _resolve_write_path(path: str) -> str:
    from pathlib import Path
    from config import GUI_MODE_PATH
    raw = path.strip().strip("\"'")
    if raw in ("gui_mode", "enabled"):
        return str(GUI_MODE_PATH)
    p = Path(raw)
    return str(p) if p.is_absolute() else str((BASE_DIR / raw).resolve())


def execute_step(step: str) -> ActionResult:
    """Python executes headless plan steps — model only names them."""
    s = step.strip()
    low = s.lower()
    if low.startswith("cmd "):
        return execute_verb("cmd", {"command": s[4:].strip()}, {}, None)
    if low.startswith("wait "):
        try:
            sec = float(s.split(None, 1)[1])
        except (IndexError, ValueError):
            sec = 1.0
        return execute_verb("wait", {"seconds": sec}, {}, None)
    if low.startswith("read_file "):
        from pathlib import Path
        path = s.split(None, 1)[1].strip().strip("\"'")
        base = Path(path).name.lower()
        if base in FILE_ALIASES:
            path = FILE_ALIASES[base]
        return execute_verb("read_file", {"path": path}, {}, None)
    if low.startswith("write_file "):
        parts = s.split(None, 2)
        if len(parts) < 2:
            return ActionResult("write_file", False, "need path and content")
        path = _resolve_write_path(parts[1])
        content = parts[2] if len(parts) > 2 else "1"
        if content in ("enabled", "enable"):
            content = "1"
        return execute_verb("write_file", {"path": path, "content": content}, {}, None)
    return ActionResult("step", False, f"not a python step: {step}")
