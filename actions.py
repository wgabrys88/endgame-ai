from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
import json
import os
import py_compile
import re
import subprocess
import sys
import time

from config import (
    BASE_DIR, DELAY_FOCUS, DELAY_CURSOR_SETTLE, DELAY_MOUSE_HOLD,
    DELAY_CHAR_SEND, DELAY_KEY_INTER, MAX_WAIT_SECONDS,
    COMMAND_TIMEOUT_SECONDS, RESPAWN_PATH,
)
from win32 import user32, get_window_title, VK_MAP, EXTENDED_VKS, INPUT

_CORE_MODULES: tuple[str, ...] = (
    "config", "engine", "agents", "actions", "main", "tui",
    "llm", "log", "observer", "win32", "acp_client",
)

MOUSEEVENTF_LEFTDOWN: int = 0x0002
MOUSEEVENTF_LEFTUP: int = 0x0004
MOUSEEVENTF_WHEEL: int = 0x0800
WHEEL_DELTA: int = 120
INPUT_KEYBOARD: int = 1
KEYEVENTF_EXTENDEDKEY: int = 0x0001
KEYEVENTF_KEYUP: int = 0x0002
KEYEVENTF_UNICODE: int = 0x0004
KEYEVENTF_UNICODE_KEYUP: int = 0x0006
DEFAULT_SCROLL_AMOUNT: int = 3

__all__ = [
    "execute_verb", "execute_step", "is_python_step", "ActionResult", "VERBS",
    "DEFAULT_SCROLL_AMOUNT",
]

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
    path = str(args.get("path", ""))
    target = Path(path) if Path(path).is_absolute() else BASE_DIR / path
    resolved = target.resolve()
    if not resolved.exists():
        return ActionResult("read_file", False, f"not found: {path}")
    if resolved.is_dir():
        files = [f.name for f in sorted(resolved.iterdir())]
        return ActionResult("read_file", True, "\n".join(files))
    return ActionResult("read_file", True, resolved.read_text(encoding="utf-8"))


def _verify_python_edit(resolved: Path) -> tuple[bool, str]:
    try:
        py_compile.compile(str(resolved), doraise=True)
    except py_compile.PyCompileError as exc:
        return False, f"syntax error in {resolved.name}: {exc}"
    script = "; ".join(f"import {name}" for name in _CORE_MODULES)
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(BASE_DIR),
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout).strip()
        return False, f"import check failed: {err[:400]}"
    return True, "imports OK"


@_register("write_file")
def _write_file(args: dict[str, Any], book: ElementBook) -> ActionResult:
    path = str(args.get("path", ""))
    content = str(args.get("content", ""))
    target = Path(path) if Path(path).is_absolute() else BASE_DIR / path
    resolved = target.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    if resolved.suffix.lower() == ".py":
        ok, msg = _verify_python_edit(resolved)
        if not ok:
            return ActionResult("write_file", False, msg)
        return ActionResult("write_file", True, f"wrote {len(content)} bytes to {path}; {msg}")
    return ActionResult("write_file", True, f"wrote {len(content)} bytes to {path}")


def _ensure_respawn_contract(command: str) -> str:
    low = command.lower()
    if "main.py" not in low or "--backend" in low:
        return command
    try:
        ctx = json.loads(RESPAWN_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return command
    backend = str(ctx.get("backend", "acp"))
    budget = int(ctx.get("budget", 200))
    goal = str(ctx.get("goal", "")).replace('"', '\\"')
    suffix = f' --backend {backend} --event-budget {budget}'
    if goal and goal not in command:
        suffix = f' "{goal}"{suffix}'
    return re.sub(
        r"((?:^|\s)(?:start(?:\s+/?b)?\s+)?(?:python(?:\.exe)?\s+)(?:\./)?main\.py)",
        rf"\1{suffix}",
        command,
        count=1,
        flags=re.IGNORECASE,
    )


def _normalize_cmd(command: str) -> str:
    return command.replace("\u201c", "\"").replace("\u201d", "\"").replace("\u2018", "'").replace("\u2019", "'")


@_register("cmd")
def _cmd(args: dict[str, Any], book: ElementBook) -> ActionResult:
    command = _ensure_respawn_contract(_normalize_cmd(str(args.get("command", "")))).strip()
    if not command:
        return ActionResult("cmd", False, "no command")
    if command.lower().startswith("start"):
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
    proc = subprocess.run(
        ["cmd.exe", "/c", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=COMMAND_TIMEOUT_SECONDS,
        cwd=str(BASE_DIR),
    )
    output = ((proc.stdout or "") + (proc.stderr or "")).strip()
    ok = proc.returncode == 0
    return ActionResult("cmd", ok, output or f"exit {proc.returncode}")


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