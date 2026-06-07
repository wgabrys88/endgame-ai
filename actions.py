from __future__ import annotations
from config import ZERO_INT, ONE_INT, TWO_INT, FLOAT_ONE
from dataclasses import dataclass, field
from typing import Any, Callable
import time

from config import (DELAY_FOCUS, DELAY_CURSOR_SETTLE, DELAY_MOUSE_HOLD,
                    DELAY_CHAR_SEND, DELAY_KEY_INTER, MAX_WAIT_SECONDS, BASE_DIR,
                    COMMAND_TIMEOUT_SECONDS, COMMAND_EXECUTABLE, COMMAND_SHELL,
                    COMMAND_SHELL_FLAG, DURATION_MS_PER_SECOND,
                    MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP, MOUSEEVENTF_WHEEL,
                    WHEEL_DELTA, INPUT_KEYBOARD, KEYEVENTF_EXTENDEDKEY,
                    KEYEVENTF_KEYUP, KEYEVENTF_UNICODE, KEYEVENTF_UNICODE_KEYUP,
                    DEFAULT_SCROLL_AMOUNT)
from win32 import user32, get_window_title, VK_MAP, EXTENDED_VKS, INPUT

__all__ = ["execute_verb", "ActionResult", "VERBS"]

type ElementBook = dict[str, Any]
type VerbFn = Callable[[dict[str, Any], ElementBook, Any], ActionResult]


@dataclass(slots=True)
class ActionResult:
    verb: str
    success: bool
    observation: str
    duration_ms: int = ZERO_INT
    data: dict[str, Any] = field(default_factory=lambda: dict[str, Any]())


VERBS: dict[str, VerbFn] = {}


def execute_verb(verb: str, args: dict[str, Any], book: ElementBook, state: Any) -> ActionResult:
    handler = VERBS.get(verb)
    if not handler:
        return ActionResult(verb=verb, success=False,
                            observation=f"unknown verb: {verb}. Valid: {', '.join(sorted(VERBS))}")
    t0 = time.perf_counter()
    try:
        result = handler(args, book, state)
        result.duration_ms = int((time.perf_counter() - t0) * DURATION_MS_PER_SECOND)
        return result
    except Exception as e:
        return ActionResult(verb=verb, success=False,
                            observation=f"ERROR: {type(e).__name__}: {e}",
                            duration_ms=int((time.perf_counter() - t0) * DURATION_MS_PER_SECOND),
                            data={"exception_type": type(e).__name__, "exception": str(e)})


def _register(name: str) -> Callable[[VerbFn], VerbFn]:
    def decorator(fn: VerbFn) -> VerbFn:
        VERBS[name] = fn
        return fn
    return decorator


@_register("click")
def click_verb(args: dict[str, Any], book: ElementBook, state: Any) -> ActionResult:
    selector = str(args.get("selector", ""))
    if selector not in book:
        return ActionResult("click", False, f"selector {selector} not in book")
    entry = book[selector]
    px, py = entry.px + entry.pw // TWO_INT, entry.py + entry.ph // TWO_INT
    user32.SetForegroundWindow(entry.hwnd)
    time.sleep(DELAY_FOCUS)
    user32.SetCursorPos(px, py)
    time.sleep(DELAY_CURSOR_SETTLE)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, ZERO_INT, ZERO_INT, ZERO_INT, ZERO_INT)
    time.sleep(DELAY_MOUSE_HOLD)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, ZERO_INT, ZERO_INT, ZERO_INT, ZERO_INT)
    return ActionResult("click", True, f"clicked {entry.role} '{entry.name}' at ({px},{py})", data={"selector": selector, "role": entry.role, "name": entry.name, "x": px, "y": py, "hwnd": entry.hwnd, "window": entry.wnd})


@_register("write")
def write_verb(args: dict[str, Any], book: ElementBook, state: Any) -> ActionResult:
    import ctypes
    selector = str(args.get("selector", ""))
    text = str(args.get("text", ""))
    if not text:
        return ActionResult("write", False, "text field is empty")
    if selector and selector in book:
        entry = book[selector]
        user32.SetForegroundWindow(entry.hwnd)
        time.sleep(DELAY_FOCUS)
    for char in text:
        code = ord(char)
        inputs = (INPUT * TWO_INT)()
        inputs[ZERO_INT].type = INPUT_KEYBOARD
        inputs[ZERO_INT].u.ki.wScan = code
        inputs[ZERO_INT].u.ki.dwFlags = KEYEVENTF_UNICODE
        inputs[ONE_INT].type = INPUT_KEYBOARD
        inputs[ONE_INT].u.ki.wScan = code
        inputs[ONE_INT].u.ki.dwFlags = KEYEVENTF_UNICODE_KEYUP
        user32.SendInput(TWO_INT, ctypes.byref(inputs), ctypes.sizeof(INPUT))
        time.sleep(DELAY_CHAR_SEND)
    return ActionResult("write", True, f"typed {len(text)} chars", data={"selector": selector, "length": len(text), "text": text})


@_register("press")
def press_verb(args: dict[str, Any], book: ElementBook, state: Any) -> ActionResult:
    selector = str(args.get("selector", ""))
    key = str(args.get("key", "")).lower()
    if not key:
        return ActionResult("press", False, "key field is empty or missing")
    if key.startswith("[") or key.endswith("]"):
        return ActionResult("press", False, f"'{key}' is an element ID, not a key name. Use: enter, escape, tab, etc.")
    if key not in VK_MAP:
        return ActionResult("press", False, f"unknown key: {key}")
    if selector and selector in book:
        entry = book[selector]
        user32.SetForegroundWindow(entry.hwnd)
        time.sleep(DELAY_FOCUS)
    vk = VK_MAP[key]
    flags = KEYEVENTF_EXTENDEDKEY if vk in EXTENDED_VKS else ZERO_INT
    user32.keybd_event(vk, ZERO_INT, flags, None)
    time.sleep(DELAY_KEY_INTER)
    user32.keybd_event(vk, ZERO_INT, KEYEVENTF_KEYUP | flags, None)
    return ActionResult("press", True, f"pressed {key}", data={"key": key, "vk": vk})


@_register("hotkey")
def hotkey_verb(args: dict[str, Any], book: ElementBook, state: Any) -> ActionResult:
    selector = str(args.get("selector", ""))
    keys: list[str] = args.get("keys", [])
    if not keys:
        return ActionResult("hotkey", False, "keys array is empty or missing")
    if selector and selector in book:
        entry = book[selector]
        user32.SetForegroundWindow(entry.hwnd)
        time.sleep(DELAY_FOCUS)
    vks: list[int] = []
    for k in keys:
        k = k.lower()
        if k not in VK_MAP:
            return ActionResult("hotkey", False, f"unknown key: {k}")
        vks.append(VK_MAP[k])
    for vk in vks:
        user32.keybd_event(vk, ZERO_INT, KEYEVENTF_EXTENDEDKEY if vk in EXTENDED_VKS else ZERO_INT, None)
        time.sleep(DELAY_KEY_INTER)
    for vk in reversed(vks):
        user32.keybd_event(vk, ZERO_INT, KEYEVENTF_KEYUP | (KEYEVENTF_EXTENDEDKEY if vk in EXTENDED_VKS else ZERO_INT), None)
        time.sleep(DELAY_KEY_INTER)
    return ActionResult("hotkey", True, f"pressed hotkey {'+'.join(str(k) for k in keys)}", data={"keys": keys, "vks": vks})


@_register("scroll")
def scroll_verb(args: dict[str, Any], book: ElementBook, state: Any) -> ActionResult:
    selector = str(args.get("selector", ""))
    amount = int(args.get("amount", DEFAULT_SCROLL_AMOUNT))
    if selector not in book:
        return ActionResult("scroll", False, f"selector {selector} not in book")
    entry = book[selector]
    px, py = entry.px + entry.pw // TWO_INT, entry.py + entry.ph // TWO_INT
    user32.SetForegroundWindow(entry.hwnd)
    time.sleep(DELAY_FOCUS)
    user32.SetCursorPos(px, py)
    time.sleep(DELAY_CURSOR_SETTLE)
    user32.mouse_event(MOUSEEVENTF_WHEEL, ZERO_INT, ZERO_INT, amount * WHEEL_DELTA, ZERO_INT)
    return ActionResult("scroll", True, f"scrolled {amount} notches at ({px},{py})", data={"selector": selector, "amount": amount, "x": px, "y": py, "hwnd": entry.hwnd, "window": entry.wnd})


@_register("wait")
def wait_verb(args: dict[str, Any], book: ElementBook, state: Any) -> ActionResult:
    seconds = min(float(args.get("seconds", FLOAT_ONE)), MAX_WAIT_SECONDS)
    time.sleep(seconds)
    return ActionResult("wait", True, f"waited {seconds}s", data={"seconds": seconds})


@_register("focus")
def focus_verb(args: dict[str, Any], book: ElementBook, state: Any) -> ActionResult:
    title = str(args.get("window_title", ""))
    if not title:
        return ActionResult("focus", False, "no window_title provided")
    found_hwnd: int | None = None
    hwnd = user32.GetTopWindow(None)
    while hwnd:
        if user32.IsWindowVisible(hwnd):
            wt = get_window_title(int(hwnd))
            if title.lower() in wt.lower() and "main.py" not in wt.lower() and "python" not in wt.lower():
                found_hwnd = int(hwnd)
                break
        hwnd = user32.GetWindow(hwnd, TWO_INT)
    if not found_hwnd:
        return ActionResult("focus", False, f"no window matching '{title}'")
    user32.SetForegroundWindow(found_hwnd)
    time.sleep(DELAY_FOCUS)
    actual_title = get_window_title(found_hwnd)
    return ActionResult("focus", True, f"focused window '{actual_title}'", data={"requested_title": title, "hwnd": found_hwnd, "actual_title": actual_title})


@_register("read_file")
def read_file_verb(args: dict[str, Any], book: ElementBook, state: Any) -> ActionResult:
    from pathlib import Path
    path = str(args.get("path", ""))
    target = Path(path)
    if not target.is_absolute():
        target = BASE_DIR / target
    resolved = target.resolve()
    if not resolved.exists():
        return ActionResult("read_file", False, f"file not found: {path}")
    if resolved.is_dir():
        files = [f.name for f in sorted(resolved.iterdir())]
        return ActionResult("read_file", True, "\n".join(files), data={"path": str(resolved), "is_dir": True, "files": files})
    content = resolved.read_text(encoding="utf-8")
    return ActionResult("read_file", True, content, data={"path": str(resolved), "is_dir": False, "content": content})


@_register("write_file")
def write_file_verb(args: dict[str, Any], book: ElementBook, state: Any) -> ActionResult:
    import hashlib
    from pathlib import Path
    path = str(args.get("path", ""))
    content = str(args.get("content", ""))
    target = Path(path)
    if not target.is_absolute():
        target = BASE_DIR / target
    resolved = target.resolve()
    if resolved.is_dir():
        return ActionResult("write_file", False, f"path is a directory, not a file: {path}")
    if resolved.exists():
        backup = resolved.with_suffix(resolved.suffix + ".bak")
        backup.write_text(resolved.read_text(encoding="utf-8"), encoding="utf-8")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    h = hashlib.sha256(content.encode()).hexdigest()
    return ActionResult("write_file", True, f"wrote {len(content)} bytes to {path} [sha256={h}]", data={"path": str(resolved), "content": content, "sha256": h})


@_register("spawn_agent")
def spawn_agent_verb(args: dict[str, Any], book: ElementBook, state: Any) -> ActionResult:
    import subprocess
    import sys
    goal = str(args.get("goal", ""))
    if not goal:
        return ActionResult("spawn_agent", False, "no goal provided")
    from llm import get_backend
    cmd = [sys.executable, str(BASE_DIR / "main.py"), goal, "--backend", get_backend()]
    proc = subprocess.Popen(cmd, cwd=str(BASE_DIR))
    return ActionResult("spawn_agent", True, f"spawned agent pid={proc.pid} for '{goal}'", data={"goal": goal, "pid": proc.pid, "cwd": str(BASE_DIR), "command": cmd})


@_register("cmd")
def cmd_verb(args: dict[str, Any], book: ElementBook, state: Any) -> ActionResult:
    import subprocess
    command = str(args.get("command", ""))
    if not command:
        return ActionResult("cmd", False, "no command provided")
    lower = command.lower()
    blocked = ("cmd.exe /c", "cmd /c", "cmd.exe /k", "cmd /k", "%username%", "%userprofile%")
    if any(item in lower for item in blocked):
        return ActionResult("cmd", False, "disallowed Windows cmd syntax inside WSL cmd verb", data={"command": command, "blocked": blocked})
    try:
        proc = subprocess.run(
            [COMMAND_EXECUTABLE, COMMAND_SHELL, COMMAND_SHELL_FLAG, command],
            capture_output=True, text=True, timeout=COMMAND_TIMEOUT_SECONDS, cwd=str(BASE_DIR))
        output = (proc.stdout + proc.stderr).strip()
        runner = [COMMAND_EXECUTABLE, COMMAND_SHELL, COMMAND_SHELL_FLAG]
        return ActionResult("cmd", proc.returncode == ZERO_INT, output or f"exit code {proc.returncode}", data={"command": command, "runner": runner, "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr, "cwd": str(BASE_DIR)})
    except subprocess.TimeoutExpired:
        return ActionResult("cmd", False, f"command timed out after {COMMAND_TIMEOUT_SECONDS}s", data={"command": command, "runner": [COMMAND_EXECUTABLE, COMMAND_SHELL, COMMAND_SHELL_FLAG], "timeout_seconds": COMMAND_TIMEOUT_SECONDS, "cwd": str(BASE_DIR)})


