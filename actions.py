from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
import json
import os
import py_compile
import subprocess
import sys
import time

import config
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
    time.sleep(config.DELAY_FOCUS)
    user32.SetCursorPos(px, py)
    time.sleep(config.DELAY_CURSOR_SETTLE)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(config.DELAY_MOUSE_HOLD)
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
        time.sleep(config.DELAY_FOCUS)
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
        time.sleep(config.DELAY_CHAR_SEND)
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
    time.sleep(config.DELAY_KEY_INTER)
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
        time.sleep(config.DELAY_KEY_INTER)
    for vk in reversed(vks):
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP | (KEYEVENTF_EXTENDEDKEY if vk in EXTENDED_VKS else 0), None)
        time.sleep(config.DELAY_KEY_INTER)
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
    time.sleep(config.DELAY_FOCUS)
    user32.SetCursorPos(px, py)
    time.sleep(config.DELAY_CURSOR_SETTLE)
    user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, amount * WHEEL_DELTA, 0)
    return ActionResult("scroll", True, f"scrolled {amount} at ({px},{py})")


@_register("wait")
def _wait(args: dict[str, Any], book: ElementBook) -> ActionResult:
    seconds = min(float(args.get("seconds", 1.0)), config.MAX_WAIT_SECONDS)
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
                time.sleep(config.DELAY_FOCUS)
                return ActionResult("focus", True, f"focused '{wt}'")
        hwnd = user32.GetWindow(hwnd, 2)
    return ActionResult("focus", False, f"no window matching '{title}'")


@_register("read_file")
def _read_file(args: dict[str, Any], book: ElementBook) -> ActionResult:
    path = str(args.get("path", ""))
    target = Path(path) if Path(path).is_absolute() else config.BASE_DIR / path
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
        cwd=str(config.BASE_DIR),
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout).strip()
        return False, f"import check failed: {err[:400]}"
    return True, "imports OK"


@_register("write_file")
def _write_file(args: dict[str, Any], book: ElementBook) -> ActionResult:
    path = str(args.get("path", ""))
    content = str(args.get("content", ""))
    target = Path(path) if Path(path).is_absolute() else config.BASE_DIR / path
    resolved = target.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    if resolved.suffix.lower() == ".py":
        ok, msg = _verify_python_edit(resolved)
        if not ok:
            return ActionResult("write_file", False, msg)
        return ActionResult("write_file", True, f"wrote {len(content)} bytes to {path}; {msg}")
    return ActionResult("write_file", True, f"wrote {len(content)} bytes to {path}")


def _clip_obs(text: str) -> str:
    limit = config.EXEC_OUTPUT_LIMIT
    return text if len(text) <= limit else text[:limit] + "…"


def _spawn_main(goal: str = "") -> int:
    try:
        ctx = json.loads(config.RESPAWN_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        ctx = {"goal": goal, "backend": "lmstudio", "budget": 200}
    g = goal or str(ctx.get("goal", ""))
    proc = subprocess.Popen(
        [sys.executable, "main.py", g, "--backend", str(ctx.get("backend", "lmstudio")),
         "--event-budget", str(int(ctx.get("budget", 200))),
         "--events-path", config.CHILD_EVENTS_PATH.name],
        cwd=str(config.BASE_DIR),
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return int(proc.pid)


def execute_python(code: str) -> ActionResult:
    import concurrent.futures
    import io
    import traceback

    code = code.strip()
    if not code:
        return ActionResult("exec", False, "no code")

    def enable_gui() -> None:
        config.GUI_MODE_PATH.write_text("1", encoding="utf-8")

    def pause_reactor() -> None:
        import log
        log.set_paused(True)

    namespace: dict[str, Any] = {
        "__builtins__": __builtins__,
        "__name__": "__exec__",
        "BASE_DIR": config.BASE_DIR,
        "Path": Path,
        "os": os,
        "sys": sys,
        "json": json,
        "time": time,
        "subprocess": subprocess,
        "spawn_main": _spawn_main,
        "enable_gui": enable_gui,
        "pause_reactor": pause_reactor,
    }

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    class _Capture(io.TextIOBase):
        def __init__(self, buf: io.StringIO) -> None:
            self._buf = buf

        def write(self, s: str) -> int:
            if s:
                self._buf.write(s)
            return len(s) if s else 0

        def flush(self) -> None:
            pass

    def _run() -> None:
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = _Capture(stdout_buf), _Capture(stderr_buf)
        try:
            exec(code, namespace, namespace)
        finally:
            sys.stdout, sys.stderr = old_out, old_err

    error_text = ""
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(_run).result(timeout=config.EXEC_TIMEOUT)
        ok = True
    except concurrent.futures.TimeoutError:
        ok, error_text = False, f"timeout after {config.EXEC_TIMEOUT}s"
    except Exception:
        ok, error_text = False, traceback.format_exc()

    parts = [stdout_buf.getvalue().rstrip(), stderr_buf.getvalue().rstrip()]
    if error_text:
        parts.append(error_text.rstrip())
    output = _clip_obs("\n".join(p for p in parts if p))
    return ActionResult("exec", ok, output or ("ok" if ok else "exec failed"))


def _parse_exec_code(step: str) -> str:
    s = step.strip()
    low = s.lower()
    if low.startswith("exec:"):
        return s[5:].lstrip("\n")
    if low.startswith("exec "):
        return s[5:]
    if low.startswith("exec"):
        return s[4:].lstrip(": \n")
    return s


def is_python_step(step: str) -> bool:
    low = step.strip().lower()
    if low.startswith("exec") and (len(low) == 4 or low[4] in ": \n"):
        return True
    if low.startswith(("read_file ", "write_file ")):
        return True
    if low.startswith("wait "):
        try:
            float(step.split(None, 1)[1])
            return True
        except (IndexError, ValueError):
            return False
    return False


def _resolve_write_path(path: str) -> str:
    raw = path.strip().strip("\"'")
    if raw in ("gui_mode", "enabled"):
        return str(config.GUI_MODE_PATH)
    p = Path(raw)
    return str(p) if p.is_absolute() else str((config.BASE_DIR / raw).resolve())


def execute_step(step: str) -> ActionResult:
    """Python executes headless plan steps — model only names them."""
    s = step.strip()
    low = s.lower()
    if low.startswith("exec") and (len(low) == 4 or low[4] in ": \n"):
        return execute_python(_parse_exec_code(s))
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