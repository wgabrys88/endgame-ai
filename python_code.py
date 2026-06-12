"""Validate and sanitize agent-authored Python before execution."""
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

_PYTHON_MARKERS: tuple[str, ...] = (
    "print(", "import ", "from ", "def ", "class ",
    "COMMS_DIR", "BASE_DIR", "PLUGINS_DIR",
    "open(", "Path(", ".write_text", ".read_text", ".write(", ".mkdir",
    "subprocess.", "json.dump", "json.dumps", "py_compile",
    "for ", "while ", "with ", "try:", "except ",
)


def sanitize_python_text(text: str) -> str:
    return text.translate(_ASCII_MAP).strip()


def is_python_code(text: str) -> bool:
    t = sanitize_python_text(text)
    if len(t) < 6:
        return False
    if not any(marker in t for marker in _PYTHON_MARKERS):
        return False
    try:
        compile(t, "<step>", "exec")
    except SyntaxError:
        return False
    return True


def validate_python(text: str) -> tuple[bool, str, str]:
    """Return (ok, cleaned_code, error_message)."""
    cleaned = sanitize_python_text(text)
    if not cleaned:
        return False, "", "empty code"
    if not any(marker in cleaned for marker in _PYTHON_MARKERS):
        return False, cleaned, "not Python - sequence[].code must be runnable Python, not goal prose"
    try:
        compile(cleaned, "<step>", "exec")
    except SyntaxError as exc:
        where = f"line {exc.lineno}" if exc.lineno else "step"
        return False, cleaned, f"SyntaxError: {exc.msg} ({where})"
    return True, cleaned, ""