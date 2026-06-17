"""Actions - execute GUI verbs using Desktop object."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from desktop import Desktop, Element


@dataclass(slots=True)
class ActionResult:
    verb: str
    success: bool
    observation: str


class ActionExecutor:
    """Executes GUI actions via Desktop."""

    def __init__(self, desktop: Desktop):
        self._desktop = desktop

    def execute(self, verb: str, args: dict[str, Any], elements: dict[str, Element]) -> ActionResult:
        handler = getattr(self, f"_do_{verb}", None)
        if not handler:
            return ActionResult(verb, False, f"unknown verb: {verb}")
        try:
            return handler(args, elements)
        except Exception as e:
            return ActionResult(verb, False, f"{type(e).__name__}: {e}")

    def _resolve(self, target: str, elements: dict[str, Element]) -> Element | None:
        """Resolve target: try as element ID first, then name match."""
        if target in elements:
            return elements[target]
        # Try stripping non-numeric chars (LLM might say "13" or "[13]")
        digits = ''.join(c for c in target if c.isdigit())
        if digits and digits in elements:
            return elements[digits]
        # Last resort: match by name substring
        for el in elements.values():
            if el.name and el.name in target:
                return el
        return None

    def _do_click(self, args: dict[str, Any], elements: dict[str, Element]) -> ActionResult:
        target = str(args.get("target", ""))
        el = self._resolve(target, elements)
        if not el:
            return ActionResult("click", False, f"element {target} not found")
        px = el.px + el.pw // 2
        py = el.py + el.ph // 2
        self._desktop.click(px, py, el.hwnd)
        return ActionResult("click", True, f"clicked '{el.name}' at ({px},{py})")

    def _do_write(self, args: dict[str, Any], elements: dict[str, Element]) -> ActionResult:
        text = str(args.get("value", ""))
        if not text:
            return ActionResult("write", False, "empty text")
        target = str(args.get("target", ""))
        if target:
            el = self._resolve(target, elements)
            if el:
                self._desktop.click(el.px + el.pw // 2, el.py + el.ph // 2, el.hwnd)
        self._desktop.type_text(text)
        return ActionResult("write", True, f"typed {len(text)} chars")

    def _do_press(self, args: dict[str, Any], elements: dict[str, Element]) -> ActionResult:
        key = str(args.get("target", args.get("value", "")))
        if not key:
            return ActionResult("press", False, "no key")
        self._desktop.press_key(key)
        return ActionResult("press", True, f"pressed {key}")

    def _do_hotkey(self, args: dict[str, Any], elements: dict[str, Element]) -> ActionResult:
        raw = str(args.get("value", args.get("target", "")))
        keys = [k.strip() for k in raw.replace("+", ",").split(",") if k.strip()]
        if not keys:
            return ActionResult("hotkey", False, "no keys")
        self._desktop.hotkey(keys)
        return ActionResult("hotkey", True, f"pressed {'+'.join(keys)}")

    def _do_scroll(self, args: dict[str, Any], elements: dict[str, Element]) -> ActionResult:
        target = str(args.get("target", ""))
        amount = int(args.get("value", 3) or 3)
        el = self._resolve(target, elements)
        if not el:
            return ActionResult("scroll", False, f"element {target} not found")
        self._desktop.scroll(el.px + el.pw // 2, el.py + el.ph // 2, amount)
        return ActionResult("scroll", True, f"scrolled {amount}")

    def _do_focus(self, args: dict[str, Any], elements: dict[str, Element]) -> ActionResult:
        title = str(args.get("target", args.get("value", "")))
        if not title:
            return ActionResult("focus", False, "no title")
        if self._desktop.focus_window(title):
            return ActionResult("focus", True, f"focused '{title}'")
        return ActionResult("focus", False, f"window '{title}' not found")
