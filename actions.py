from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import time

from config import (DELAY_FOCUS, DELAY_CURSOR_SETTLE, DELAY_MOUSE_HOLD,
                    DELAY_CHAR_SEND, DELAY_KEY_INTER, MAX_WAIT_SECONDS, BASE_DIR, trace)
from win32 import user32, get_window_title, VK_MAP, EXTENDED_VKS, INPUT

__all__ = ["execute_verb", "ActionResult", "VERBS"]


@dataclass(slots=True)
class ActionResult:
    verb: str
    success: bool
    observation: str
    duration_ms: int = 0


VERBS: dict[str, Any] = {}


def execute_verb(verb: str, args: dict[str, Any], book: dict, state: Any) -> ActionResult:
    handler = VERBS.get(verb)
    if not handler:
        return ActionResult(verb=verb, success=False,
                            observation=f"unknown verb: {verb}. Valid: {', '.join(sorted(VERBS))}")
    t0 = time.perf_counter()
    try:
        result = handler(args, book, state)
        result.duration_ms = int((time.perf_counter() - t0) * 1000)
        trace("action.result", f"verb={verb} args={args} success={result.success} obs={result.observation}")
        return result
    except Exception as e:
        return ActionResult(verb=verb, success=False,
                            observation=f"ERROR: {type(e).__name__}: {e}",
                            duration_ms=int((time.perf_counter() - t0) * 1000))


def _register(name: str):
    def decorator(fn):
        VERBS[name] = fn
        return fn
    return decorator


@_register("click")
def _click(args: dict, book: dict, state) -> ActionResult:
    selector = str(args.get("selector", ""))
    if selector not in book:
        return ActionResult("click", False, f"selector {selector} not in book")
    entry = book[selector]
    px, py = entry.px + entry.pw // 2, entry.py + entry.ph // 2
    trace("action.click", f"selector={selector} role={entry.role} name={entry.name} pos=({px},{py}) hwnd={entry.hwnd}")
    user32.SetForegroundWindow(entry.hwnd)
    time.sleep(DELAY_FOCUS)
    user32.SetCursorPos(px, py)
    time.sleep(DELAY_CURSOR_SETTLE)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(DELAY_MOUSE_HOLD)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    return ActionResult("click", True, f"clicked {entry.role} '{entry.name}' at ({px},{py})")


@_register("write")
def _write(args: dict, book: dict, state) -> ActionResult:
    import ctypes
    selector = str(args.get("selector", ""))
    text = str(args.get("text", ""))
    if not text:
        return ActionResult("write", False, "text field is empty")
    if selector and selector in book:
        entry = book[selector]
        trace("action.write", f"selector={selector} role={entry.role} name={entry.name} hwnd={entry.hwnd} text_len={len(text)}")
        user32.SetForegroundWindow(entry.hwnd)
        time.sleep(DELAY_FOCUS)
    else:
        trace("action.write", f"no selector, typing into focused window, text_len={len(text)}")
    for char in text:
        code = ord(char)
        inputs = (INPUT * 2)()
        inputs[0].type = 1
        inputs[0].u.ki.wScan = code
        inputs[0].u.ki.dwFlags = 0x0004
        inputs[1].type = 1
        inputs[1].u.ki.wScan = code
        inputs[1].u.ki.dwFlags = 0x0006
        user32.SendInput(2, ctypes.byref(inputs), ctypes.sizeof(INPUT))
        time.sleep(DELAY_CHAR_SEND)
    return ActionResult("write", True, f"typed {len(text)} chars")


@_register("press")
def _press(args: dict, book: dict, state) -> ActionResult:
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
    flags = 0x0001 if vk in EXTENDED_VKS else 0
    user32.keybd_event(vk, 0, flags, None)
    time.sleep(DELAY_KEY_INTER)
    user32.keybd_event(vk, 0, 0x0002 | flags, None)
    return ActionResult("press", True, f"pressed {key}")


@_register("hotkey")
def _hotkey(args: dict, book: dict, state) -> ActionResult:
    selector = str(args.get("selector", ""))
    keys = args.get("keys", [])
    if not keys:
        return ActionResult("hotkey", False, "keys array is empty or missing")
    if selector and selector in book:
        entry = book[selector]
        user32.SetForegroundWindow(entry.hwnd)
        time.sleep(DELAY_FOCUS)
    vks = []
    for k in keys:
        k = k.lower()
        if k not in VK_MAP:
            return ActionResult("hotkey", False, f"unknown key: {k}")
        vks.append(VK_MAP[k])
    for vk in vks:
        user32.keybd_event(vk, 0, 0x0001 if vk in EXTENDED_VKS else 0, None)
        time.sleep(DELAY_KEY_INTER)
    for vk in reversed(vks):
        user32.keybd_event(vk, 0, 0x0002 | (0x0001 if vk in EXTENDED_VKS else 0), None)
        time.sleep(DELAY_KEY_INTER)
    return ActionResult("hotkey", True, f"pressed hotkey {'+'.join(str(k) for k in keys)}")


@_register("scroll")
def _scroll(args: dict, book: dict, state) -> ActionResult:
    selector = str(args.get("selector", ""))
    amount = int(args.get("amount", 3))
    if selector not in book:
        return ActionResult("scroll", False, f"selector {selector} not in book")
    entry = book[selector]
    px, py = entry.px + entry.pw // 2, entry.py + entry.ph // 2
    user32.SetForegroundWindow(entry.hwnd)
    time.sleep(DELAY_FOCUS)
    user32.SetCursorPos(px, py)
    time.sleep(DELAY_CURSOR_SETTLE)
    user32.mouse_event(0x0800, 0, 0, amount * 120, 0)
    return ActionResult("scroll", True, f"scrolled {amount} notches at ({px},{py})")


@_register("wait")
def _wait(args: dict, book: dict, state) -> ActionResult:
    seconds = min(float(args.get("seconds", 1.0)), MAX_WAIT_SECONDS)
    time.sleep(seconds)
    return ActionResult("wait", True, f"waited {seconds}s")


@_register("focus")
def _focus(args: dict, book: dict, state) -> ActionResult:
    title = str(args.get("window_title", ""))
    if not title:
        return ActionResult("focus", False, "no window_title provided")
    found_hwnd = None
    hwnd = user32.GetTopWindow(None)
    while hwnd:
        if user32.IsWindowVisible(hwnd):
            wt = get_window_title(int(hwnd))
            if title.lower() in wt.lower() and "main.py" not in wt.lower() and "python" not in wt.lower():
                found_hwnd = int(hwnd)
                break
        hwnd = user32.GetWindow(hwnd, 2)
    if not found_hwnd:
        return ActionResult("focus", False, f"no window matching '{title}'")
    user32.SetForegroundWindow(found_hwnd)
    time.sleep(DELAY_FOCUS)
    actual_title = get_window_title(found_hwnd)
    return ActionResult("focus", True, f"focused window '{actual_title}'")


@_register("read_file")
def _read_file(args: dict, book: dict, state) -> ActionResult:
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
        return ActionResult("read_file", True, "\n".join(files))
    content = resolved.read_text(encoding="utf-8", errors="replace")
    return ActionResult("read_file", True, content)


@_register("write_file")
def _write_file(args: dict, book: dict, state) -> ActionResult:
    import hashlib
    from pathlib import Path
    path = str(args.get("path", ""))
    content = str(args.get("content", ""))
    target = Path(path)
    if not target.is_absolute():
        target = BASE_DIR / target
    resolved = target.resolve()
    if not resolved.is_relative_to(BASE_DIR):
        return ActionResult("write_file", False, f"path escapes project root: {path}")
    if resolved.exists():
        backup = resolved.with_suffix(resolved.suffix + ".bak")
        backup.write_text(resolved.read_text(encoding="utf-8"), encoding="utf-8")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    h = hashlib.sha256(content.encode()).hexdigest()
    return ActionResult("write_file", True, f"wrote {len(content)} bytes to {path} [sha256={h}]")


@_register("spawn_agent")
def _spawn_agent(args: dict, book: dict, state) -> ActionResult:
    import subprocess
    goal = str(args.get("goal", ""))
    if not goal:
        return ActionResult("spawn_agent", False, "no goal provided")
    from llm import get_backend
    cmd = ["python", str(BASE_DIR / "main.py"), goal, "--backend", get_backend()]
    proc = subprocess.Popen(cmd, cwd=str(BASE_DIR))
    return ActionResult("spawn_agent", True, f"spawned agent pid={proc.pid} for '{goal}'")


@_register("cmd")
def _cmd(args: dict, book: dict, state) -> ActionResult:
    import subprocess
    command = str(args.get("command", ""))
    if not command:
        return ActionResult("cmd", False, "no command provided")
    try:
        proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30, cwd=str(BASE_DIR))
        output = (proc.stdout + proc.stderr).strip()
        return ActionResult("cmd", proc.returncode == 0, output or f"exit code {proc.returncode}")
    except subprocess.TimeoutExpired:
        return ActionResult("cmd", False, "command timed out after 30s")


@_register("done")
def _done(args: dict, book: dict, state) -> ActionResult:
    evidence = str(args.get("evidence", ""))
    return ActionResult("done", True, f"completion claimed: {evidence}")
