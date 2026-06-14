"""Validate agent-authored Python before execution (syntax only — full stdlib at runtime)."""
from __future__ import annotations

_ASCII_MAP = str.maketrans({
    "\u2014": "-",
    "\u2013": "-",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u00a0": " ",
})


def sanitize_python_text(text: str) -> str:
    return text.translate(_ASCII_MAP).strip()


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
    """Return (ok, cleaned_code, error_message). Syntax check only."""
    cleaned = sanitize_python_text(text)
    if not cleaned:
        return False, "", "empty code"
    try:
        compile(cleaned, "<step>", "exec")
    except SyntaxError as exc:
        where = f"line {exc.lineno}" if exc.lineno else "step"
        return False, cleaned, f"SyntaxError: {exc.msg} ({where})"
    return True, cleaned, ""


def goal_prefers_gui(text: str) -> bool:
    """Route to GUI planner circuit when goal clearly needs desktop hands."""
    g = sanitize_python_text(text).lower()
    hints = (
        "notepad", "calculator", "mspaint", "wordpad", "chrome", "youtube",
        "opera", "linkedin", "desktop", "open app", "open the", "click",
        "type ", "window", "gui", "notepad.exe", "calc.exe",
    )
    return any(h in g for h in hints)