"""Desktop automation helpers for agent Python scripts (mouse, keyboard, UIA)."""
from __future__ import annotations

from actions import ActionResult, execute_verb
from config import is_gui_operator
from observer import observe

__all__ = [
    "observe_screen",
    "desktop_focus",
    "desktop_click",
    "desktop_write",
    "desktop_press",
    "desktop_hotkey",
    "desktop_scroll",
    "desktop_wait",
]

_GUI_DENIED_MSG = (
    "ROLE VIOLATION: only gui_operator (n6 / @GUI) may use desktop_* helpers. "
    "Other personalities must delegate via bus_request(bus_id(), 'gui_operator', '...')."
)


def _require_gui_operator() -> None:
    if not is_gui_operator():
        raise RuntimeError(_GUI_DENIED_MSG)


def _safe_print(text: str) -> None:
    import sys
    out = text.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
        sys.stdout.encoding or "utf-8", errors="replace"
    )
    print(out)


def observe_screen(*, print_screen: bool = True) -> tuple[dict, str, str]:
    """Scan desktop UI. Returns (element_book, context_text, focused_window)."""
    obs = observe()
    if print_screen:
        if obs.context_text:
            _safe_print(obs.context_text[:4000])
        _safe_print(f"FOCUSED: {obs.focused_title}")
    return obs.book, obs.context_text, obs.focused_title


def _act(verb: str, args: dict, book: dict) -> ActionResult:
    result = execute_verb(verb, args, book, None)
    _safe_print(result.observation)
    if not result.success:
        raise RuntimeError(result.observation)
    return result


def desktop_focus(window_title: str, book: dict | None = None) -> dict:
    _require_gui_operator()
    if book is None:
        book, _, _ = observe_screen(print_screen=False)
    _act("focus", {"window_title": window_title}, book)
    return book


def desktop_click(selector: str, book: dict | None = None) -> dict:
    _require_gui_operator()
    if book is None:
        book, _, _ = observe_screen(print_screen=False)
    _act("click", {"selector": str(selector)}, book)
    return book


def desktop_write(text: str, selector: str = "", book: dict | None = None) -> dict:
    _require_gui_operator()
    if book is None:
        book, _, _ = observe_screen(print_screen=False)
    args: dict = {"text": text}
    if selector:
        args["selector"] = str(selector)
    _act("write", args, book)
    return book


def desktop_press(key: str, book: dict | None = None) -> dict:
    _require_gui_operator()
    if book is None:
        book, _, _ = observe_screen(print_screen=False)
    _act("press", {"key": key}, book)
    return book


def desktop_hotkey(keys: list[str], book: dict | None = None) -> dict:
    _require_gui_operator()
    if book is None:
        book, _, _ = observe_screen(print_screen=False)
    _act("hotkey", {"keys": keys}, book)
    return book


def desktop_scroll(selector: str, amount: int = 3, book: dict | None = None) -> dict:
    _require_gui_operator()
    if book is None:
        book, _, _ = observe_screen(print_screen=False)
    _act("scroll", {"selector": str(selector), "amount": int(amount)}, book)
    return book


def desktop_wait(seconds: float = 1.0, book: dict | None = None) -> dict:
    _require_gui_operator()
    if book is None:
        book, _, _ = observe_screen(print_screen=False)
    _act("wait", {"seconds": float(seconds)}, book)
    return book