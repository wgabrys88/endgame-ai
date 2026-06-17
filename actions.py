"""Actions - data-driven verb dispatch. Field mappings from wiring.json."""
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
    def __init__(self, desktop: Desktop, wiring: dict[str, Any]):
        self._desktop = desktop
        self._verbs = wiring.get("verbs", {})

    def _resolve(self, target: str, elements: dict[str, Element]) -> Element | None:
        if target in elements:
            return elements[target]
        digits = ''.join(c for c in target if c.isdigit())
        if digits and digits in elements:
            return elements[digits]
        for el in elements.values():
            if el.name and el.name in target:
                return el
        return None

    def execute(self, verb: str, args: dict[str, Any], elements: dict[str, Element]) -> ActionResult:
        cfg = self._verbs.get(verb)
        if not cfg:
            return ActionResult(verb, False, f"unknown verb: {verb}")
        try:
            return self._dispatch(verb, cfg, args, elements)
        except Exception as e:
            return ActionResult(verb, False, f"{type(e).__name__}: {e}")

    def _dispatch(self, verb: str, cfg: dict, args: dict[str, Any], elements: dict[str, Element]) -> ActionResult:
        if verb == "click":
            target = str(args.get(cfg["target_field"], ""))
            el = self._resolve(target, elements)
            if not el:
                return ActionResult(verb, False, f"element {target} not found")
            px, py = el.px + el.pw // 2, el.py + el.ph // 2
            self._desktop.click(px, py, el.hwnd)
            return ActionResult(verb, True, f"clicked '{el.name}' at ({px},{py})")

        if verb == "write":
            text = str(args.get(cfg.get("value_field", "value"), ""))
            if not text:
                return ActionResult(verb, False, "empty text")
            target = str(args.get(cfg.get("target_field", "target"), ""))
            if target:
                el = self._resolve(target, elements)
                if el:
                    self._desktop.click(el.px + el.pw // 2, el.py + el.ph // 2, el.hwnd)
            self._desktop.type_text(text)
            return ActionResult(verb, True, f"typed {len(text)} chars")

        if verb == "press":
            key = str(args.get(cfg["key_field"], ""))
            if not key:
                return ActionResult(verb, False, "no key")
            self._desktop.press_key(key)
            return ActionResult(verb, True, f"pressed {key}")

        if verb == "hotkey":
            raw = str(args.get(cfg["key_field"], ""))
            keys = [k.strip() for k in raw.replace("+", ",").split(",") if k.strip()]
            if not keys:
                return ActionResult(verb, False, f"no keys (field '{cfg['key_field']}' was empty)")
            self._desktop.hotkey(keys)
            return ActionResult(verb, True, f"pressed {'+'.join(keys)}")

        if verb == "scroll":
            target = str(args.get(cfg["target_field"], ""))
            amount = int(args.get(cfg.get("amount_field", "value"), 3) or 3)
            el = self._resolve(target, elements)
            if not el:
                return ActionResult(verb, False, f"element {target} not found")
            self._desktop.scroll(el.px + el.pw // 2, el.py + el.ph // 2, amount)
            return ActionResult(verb, True, f"scrolled {amount}")

        if verb == "focus":
            title = str(args.get(cfg["title_field"], ""))
            if not title:
                return ActionResult(verb, False, "no title")
            if self._desktop.focus_window(title):
                return ActionResult(verb, True, f"focused '{title}'")
            return ActionResult(verb, False, f"window '{title}' not found")

        return ActionResult(verb, False, f"unhandled verb: {verb}")
