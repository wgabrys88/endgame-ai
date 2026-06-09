from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable
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

__all__ = ["execute_verb", "ActionResult", "VERBS"]

type ElementBook = dict[str, Any]
type VerbFn = Callable[[dict[str, Any], ElementBook, Any], ActionResult]


@dataclass(slots=True)
class ActionResult:
    verb: str
    success: bool
    observation: str
    data: dict[str, Any] = field(default_factory=lambda: dict[str, Any]())


VERBS: dict[str, VerbFn] = {}


def execute_verb(verb: str, args: dict[str, Any], book: ElementBook, state: Any) -> ActionResult:
    handler = VERBS.get(verb)
    if not handler:
        return ActionResult(verb=verb, success=False,
                            observation=f"unknown verb: {verb}. Valid: {', '.join(sorted(VERBS))}")
    try:
        return handler(args, book, state)
    except Exception as e:
        return ActionResult(verb=verb, success=False, observation=f"ERROR: {type(e).__name__}: {e}")


def _register(name: str) -> Callable[[VerbFn], VerbFn]:
    def decorator(fn: VerbFn) -> VerbFn:
        VERBS[name] = fn
        return fn
    return decorator


@_register("click")
def _click(args: dict[str, Any], book: ElementBook, state: Any) -> ActionResult:
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
def _write(args: dict[str, Any], book: ElementBook, state: Any) -> ActionResult:
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
def _press(args: dict[str, Any], book: ElementBook, state: Any) -> ActionResult:
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
def _hotkey(args: dict[str, Any], book: ElementBook, state: Any) -> ActionResult:
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
def _scroll(args: dict[str, Any], book: ElementBook, state: Any) -> ActionResult:
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
def _wait(args: dict[str, Any], book: ElementBook, state: Any) -> ActionResult:
    seconds = min(float(args.get("seconds", 1.0)), MAX_WAIT_SECONDS)
    time.sleep(seconds)
    return ActionResult("wait", True, f"waited {seconds}s")


@_register("focus")
def _focus(args: dict[str, Any], book: ElementBook, state: Any) -> ActionResult:
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
def _read_file(args: dict[str, Any], book: ElementBook, state: Any) -> ActionResult:
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
def _write_file(args: dict[str, Any], book: ElementBook, state: Any) -> ActionResult:
    from pathlib import Path
    path = str(args.get("path", ""))
    content = str(args.get("content", ""))
    target = Path(path) if Path(path).is_absolute() else BASE_DIR / path
    resolved = target.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    return ActionResult("write_file", True, f"wrote {len(content)} bytes to {path}")


@_register("cmd")
def _cmd(args: dict[str, Any], book: ElementBook, state: Any) -> ActionResult:
    import subprocess
    command = str(args.get("command", ""))
    if not command:
        return ActionResult("cmd", False, "no command")
    command = command.replace("\u201c", "\"").replace("\u201d", "\"").replace("\u2018", "'").replace("\u2019", "'")
    try:
        cmd_parts = [COMMAND_EXECUTABLE, COMMAND_SHELL, command] if COMMAND_SHELL else [COMMAND_EXECUTABLE, command]
        proc = subprocess.run(
            cmd_parts,
            capture_output=True, text=True, timeout=COMMAND_TIMEOUT_SECONDS, cwd=str(BASE_DIR))
        output = (proc.stdout + proc.stderr).strip()
        return ActionResult("cmd", proc.returncode == 0, output or f"exit {proc.returncode}")
    except subprocess.TimeoutExpired:
        return ActionResult("cmd", False, f"timed out after {COMMAND_TIMEOUT_SECONDS}s")
