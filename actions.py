"""Actions â€” verb registry + Python subprocess runner."""
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
import log

_child_pids: list[int] = []

try:
    from desktop import user32, get_window_title, VK_MAP, EXTENDED_VKS, INPUT
    _HAS_WIN32 = True
except (ImportError, OSError):
    _HAS_WIN32 = False

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_WHEEL = 0x0800
WHEEL_DELTA = 120
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_UNICODE_KEYUP = 0x0006

DEFAULT_SCROLL_AMOUNT: int = 3
FILE_ALIASES: dict[str, str] = {"reactor.py": "engine.py", "planner.py": "agents.py"}

__all__ = [
    "execute_verb", "execute_step", "is_python_step", "run_python",
    "ActionResult", "VERBS", "DEFAULT_SCROLL_AMOUNT",
]

type ElementBook = dict[str, Any]
type VerbFn = Callable[[dict[str, Any], ElementBook], "ActionResult"]
@dataclass(slots=True)
class ActionResult:
    verb: str
    success: bool
    observation: str
    data: dict[str, Any] = field(default_factory=dict)
VERBS: dict[str, VerbFn] = {}
def execute_verb(verb: str, args: dict[str, Any], book: ElementBook, _state: Any) -> ActionResult:
    handler = VERBS.get(verb)
    if not handler:
        return ActionResult(verb, False, f"unknown verb: {verb}")
    try:
        return handler(args, book)
    except Exception as e:
        return ActionResult(verb, False, f"ERROR: {type(e).__name__}: {e}")
def _register(name: str):
    def dec(fn: VerbFn) -> VerbFn:
        VERBS[name] = fn
        return fn
    return dec
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
    return ActionResult("click", True, f"clicked '{entry.name}' at ({px},{py})")
@_register("write")
def _write(args: dict[str, Any], book: ElementBook) -> ActionResult:
    import ctypes
    selector = str(args.get("selector", ""))
    text = str(args.get("text", ""))
    if not text:
        return ActionResult("write", False, "text is empty")
    if selector and selector in book:
        user32.SetForegroundWindow(book[selector].hwnd)
        time.sleep(config.DELAY_FOCUS)
    for char in text:
        inputs = (INPUT * 2)()
        inputs[0].type = INPUT_KEYBOARD
        inputs[0].u.ki.wScan = ord(char)
        inputs[0].u.ki.dwFlags = KEYEVENTF_UNICODE
        inputs[1].type = INPUT_KEYBOARD
        inputs[1].u.ki.wScan = ord(char)
        inputs[1].u.ki.dwFlags = KEYEVENTF_UNICODE_KEYUP
        user32.SendInput(2, ctypes.byref(inputs), ctypes.sizeof(INPUT))
        time.sleep(config.DELAY_CHAR_SEND)
    return ActionResult("write", True, f"typed {len(text)} chars")
@_register("press")
def _press(args: dict[str, Any], book: ElementBook) -> ActionResult:
    key = str(args.get("key", "")).lower()
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
    keys = args.get("keys", [])
    if not keys:
        return ActionResult("hotkey", False, "keys empty")
    vks = []
    for k in keys:
        if k.lower() not in VK_MAP:
            return ActionResult("hotkey", False, f"unknown key: {k}")
        vks.append(VK_MAP[k.lower()])
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
    amount = int(args.get("amount", 3))
    if selector not in book:
        return ActionResult("scroll", False, f"selector {selector} not in book")
    entry = book[selector]
    px, py = entry.px + entry.pw // 2, entry.py + entry.ph // 2
    user32.SetForegroundWindow(entry.hwnd)
    time.sleep(config.DELAY_FOCUS)
    user32.SetCursorPos(px, py)
    time.sleep(config.DELAY_CURSOR_SETTLE)
    user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, amount * WHEEL_DELTA, 0)
    return ActionResult("scroll", True, f"scrolled {amount}")
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
        return ActionResult("read_file", True, "\n".join(f.name for f in sorted(resolved.iterdir())))
    return ActionResult("read_file", True, resolved.read_text(encoding="utf-8"))
@_register("write_file")
def _write_file(args: dict[str, Any], book: ElementBook) -> ActionResult:
    path = str(args.get("path", ""))
    content = str(args.get("content", ""))
    target = Path(path) if Path(path).is_absolute() else config.BASE_DIR / path
    resolved = target.resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    if resolved.suffix.lower() == ".py":
        try:
            py_compile.compile(str(resolved), doraise=True)
        except py_compile.PyCompileError as exc:
            return ActionResult("write_file", False, f"syntax error: {exc}")
    return ActionResult("write_file", True, f"wrote {len(content)} bytes to {path}")
# --- Headless plan steps (main-style exec / read_file / write_file / wait) ---

def _clip_obs(text: str) -> str:
    limit = config.EXEC_OUTPUT_LIMIT
    return text if len(text) <= limit else text[:limit] + "â€¦"
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
def execute_python(code: str) -> ActionResult:
    """Run Python code as subprocess (same as run_python)."""
    return run_python(code)
def execute_step(step: str) -> ActionResult:
    """Python executes headless plan steps â€” model only names them."""
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
# --- Python subprocess runner (colony bus sandbox) ---

def _script_runner(code: str) -> str:
    desktop_import = (
        "from actions import observe_screen, desktop_focus, desktop_click, desktop_write, "
        "desktop_press, desktop_hotkey, desktop_scroll, desktop_wait\n"
    )
    workspace = str(config.BASE_DIR)
    return (
        "from comms import BASE_DIR, COMMS_DIR, PLUGINS_DIR, bus_post, bus_id, bus_request, bus_route\n"
        f"{desktop_import}"
        "from pathlib import Path\n"
        "import os, sys, json, time, subprocess, shutil, py_compile\n\n"
        f"ENDGAME_WORKSPACE = Path(r'{workspace}')\n"
        "ENDGAME_USER_HOME = Path(os.environ.get('USERPROFILE') or Path.home())\n"
        "ENDGAME_DESKTOP = ENDGAME_USER_HOME / 'Desktop'\n\n"
        "def endgame_open_app(command):\n"
        "    return subprocess.Popen(str(command), shell=True)\n\n"
        "def endgame_set_clipboard(text):\n"
        "    subprocess.run(['powershell', '-NoProfile', '-Command', 'Set-Clipboard -Value ([Console]::In.ReadToEnd())'], input=str(text), text=True, check=True)\n\n"
        "def endgame_get_clipboard():\n"
        "    return subprocess.run(['powershell', '-NoProfile', '-Command', 'Get-Clipboard'], capture_output=True, text=True, check=True).stdout.rstrip('\\n')\n\n"
        f"{code}\n"
    )
def run_python(code: str) -> ActionResult:
    import tempfile
    from agents import validate_python
    ok, code, err = validate_python(code)
    if not ok:
        return ActionResult("python", False, err)
    script = _script_runner(code)
    path = ""
    try:
        with tempfile.NamedTemporaryFile(mode="w", prefix="tmp", suffix=".py", delete=False, encoding="utf-8", dir=str(config.BASE_DIR)) as fh:
            fh.write(script)
            path = fh.name
        proc = subprocess.run(
            [sys.executable, path], cwd=str(config.BASE_DIR),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=config.EXEC_TIMEOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired as exc:
        pid = getattr(getattr(exc, "process", None), "pid", None)
        if pid:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return ActionResult("python", False, f"timeout after {config.EXEC_TIMEOUT}s")
    finally:
        if path:
            try:
                os.unlink(path)
            except OSError:
                pass
    out = (proc.stdout or "").rstrip()
    err_out = (proc.stderr or "").rstrip()
    if proc.returncode != 0:
        text = (err_out or out).strip()
        lines = [ln for ln in text.splitlines() if ln.strip()]
        msg = next((ln for ln in reversed(lines) if not ln.startswith(("Traceback", "  File ", "    "))), lines[-1] if lines else f"exit {proc.returncode}")
        return ActionResult("python", False, msg[:config.EXEC_OUTPUT_LIMIT])
    output = "\n".join(p for p in (out, err_out) if p)[:config.EXEC_OUTPUT_LIMIT]
    return ActionResult("python", True, output or "ok (no output)")
# --- Desktop helpers (injected into actor Python when GUI mode on) ---

def _desktop_safe_print(text: str) -> None:
    out = text.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
        sys.stdout.encoding or "utf-8", errors="replace"
    )
    print(out)
def observe_screen(*, print_screen: bool = True) -> tuple[dict, str, str]:
    from desktop import observe
    obs = observe()
    if print_screen:
        if obs.context_text:
            _desktop_safe_print(obs.context_text[:4000])
        _desktop_safe_print(f"FOCUSED: {obs.focused_title}")
    return obs.book, obs.context_text, obs.focused_title
def _desktop_act(verb: str, args: dict, book: dict) -> ActionResult:
    result = execute_verb(verb, args, book, None)
    _desktop_safe_print(result.observation)
    if not result.success:
        raise RuntimeError(result.observation)
    return result
def desktop_focus(window_title: str, book: dict | None = None) -> dict:
    if book is None:
        book, _, _ = observe_screen(print_screen=False)
    _desktop_act("focus", {"window_title": window_title}, book)
    return book
def desktop_click(selector: str, book: dict | None = None) -> dict:
    if book is None:
        book, _, _ = observe_screen(print_screen=False)
    _desktop_act("click", {"selector": str(selector)}, book)
    return book
def desktop_write(text: str, selector: str = "", book: dict | None = None) -> dict:
    if book is None:
        book, _, _ = observe_screen(print_screen=False)
    args: dict = {"text": text}
    if selector:
        args["selector"] = str(selector)
    _desktop_act("write", args, book)
    return book
def desktop_press(key: str, book: dict | None = None) -> dict:
    if book is None:
        book, _, _ = observe_screen(print_screen=False)
    _desktop_act("press", {"key": key}, book)
    return book
def desktop_hotkey(keys: list[str], book: dict | None = None) -> dict:
    if book is None:
        book, _, _ = observe_screen(print_screen=False)
    _desktop_act("hotkey", {"keys": keys}, book)
    return book
def desktop_scroll(selector: str, amount: int = 3, book: dict | None = None) -> dict:
    if book is None:
        book, _, _ = observe_screen(print_screen=False)
    _desktop_act("scroll", {"selector": str(selector), "amount": int(amount)}, book)
    return book
def desktop_wait(seconds: float = 1.0, book: dict | None = None) -> dict:
    if book is None:
        book, _, _ = observe_screen(print_screen=False)
    _desktop_act("wait", {"seconds": float(seconds)}, book)
    return book
