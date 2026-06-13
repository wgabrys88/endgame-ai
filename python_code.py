"""Validate agent-authored Python before execution (syntax only — full stdlib at runtime)."""
from __future__ import annotations
import re

import config

_ASCII_MAP = str.maketrans({
    "\u2014": "-",
    "\u2013": "-",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u00a0": " ",
})

_GUI_BLOCK_RE = re.compile(
    r"(?:"
    r"['\"]notepad(?:\.exe)?['\"]|"
    r"['\"]calc(?:\.exe)?['\"]|"
    r"['\"]mspaint(?:\.exe)?['\"]|"
    r"['\"]wordpad(?:\.exe)?['\"]|"
    r"os\.startfile\s*\(|"
    r"subprocess\.(?:run|Popen|call)\s*\([^)]*['\"]notepad|"
    r"subprocess\.(?:run|Popen|call)\s*\([^)]*['\"]calc|"
    r"pyautogui|pynput|mouse_event|keybd_event"
    r")",
    re.IGNORECASE,
)

_GUI_GOAL_WORDS = frozenset({
    "notepad", "calculator", "mspaint", "wordpad", "desktop app",
    "open app", "gui agent", "mouse hover", "mouse click", "keyboard macro",
})


def sanitize_python_text(text: str) -> str:
    return text.translate(_ASCII_MAP).strip()


def gui_mode_enabled() -> bool:
    return config.GUI_MODE_PATH.is_file()


def goal_needs_gui(text: str) -> bool:
    if gui_mode_enabled():
        return False
    g = sanitize_python_text(text).lower()
    return any(word in g for word in _GUI_GOAL_WORDS)


def is_python_code(text: str) -> bool:
    t = sanitize_python_text(text)
    if len(t) < 4:
        return False
    try:
        compile(t, "<step>", "exec")
    except SyntaxError:
        return False
    return True


def validate_python(text: str) -> tuple[bool, str, str]:
    """Return (ok, cleaned_code, error_message). Syntax check only — no sandbox."""
    cleaned = sanitize_python_text(text)
    if not cleaned:
        return False, "", "empty code"
    if not gui_mode_enabled() and _GUI_BLOCK_RE.search(cleaned):
        return False, cleaned, "blocked: GUI/desktop automation not supported (no GUI agent)"
    try:
        compile(cleaned, "<step>", "exec")
    except SyntaxError as exc:
        where = f"line {exc.lineno}" if exc.lineno else "step"
        return False, cleaned, f"SyntaxError: {exc.msg} ({where})"
    return True, cleaned, ""