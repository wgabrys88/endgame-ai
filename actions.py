"""Actions - data-driven verb dispatch. Field mappings from wiring.json."""
from __future__ import annotations
import re
import threading
from dataclasses import dataclass
from typing import Any

from desktop import (
    Desktop,
    Element,
    Observation,
    assign_window_tokens,
    configure_observation,
    resolve_window_target,
)


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
        id_match = re.match(r"^\[?(\d+)\]?$", (target or "").strip())
        if id_match and id_match.group(1) in elements:
            return elements[id_match.group(1)]
        target_l = target.lower().strip()
        if not target_l:
            return None

        def name_score(el: Element) -> tuple[int, int]:
            name_l = (el.name or "").lower()
            if not name_l:
                return (99, 0)
            if target_l == name_l:
                return (0, -len(name_l))
            if target_l in name_l:
                return (1, -len(name_l))
            if name_l in target_l:
                return (2, -len(name_l))
            words = [w for w in re.split(r"[\s\-]+", target_l) if len(w) > 2]
            overlap = sum(1 for w in words if w in name_l)
            if overlap:
                return (3, -overlap * 10 - len(name_l))
            return (99, 0)

        def action_rank(el: Element) -> int:
            if el.action == "write" and el.role in ("Edit", "ComboBox", "Document"):
                return 0
            if el.action == "click":
                return 1
            if el.role != "Text":
                return 2
            return 3

        candidates = [
            (name_score(el), action_rank(el), el)
            for el in elements.values()
            if name_score(el)[0] < 99
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda x: (x[0][0], x[0][1], x[1]))
        return candidates[0][2]

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
                if not el:
                    return ActionResult(verb, False, f"element {target} not found")
                if el.action != "write" and el.role not in ("Edit", "ComboBox", "Document"):
                    return ActionResult(verb, False, f"element {target} is not writable ({el.role})")
                self._desktop.click(el.px + el.pw // 2, el.py + el.ph // 2, el.hwnd)
            self._desktop.hotkey(["ctrl", "a"])
            self._desktop.type_text(text)
            return ActionResult(verb, True, f"typed {len(text)} chars")

        if verb == "press":
            key = str(args.get(cfg["key_field"], ""))
            if not key:
                key = str(args.get("value", ""))
            if not key:
                return ActionResult(verb, False, "no key")
            self._desktop.press_key(key)
            return ActionResult(verb, True, f"pressed {key}")

        if verb == "hotkey":
            raw = str(args.get(cfg["key_field"], ""))
            if not raw:
                raw = str(args.get("value", ""))
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
            self._desktop.scroll(el.px + el.pw // 2, el.py + el.ph // 2, amount, el.hwnd)
            return ActionResult(verb, True, f"scrolled {amount}")

        if verb == "focus":
            title = str(args.get(cfg["title_field"], ""))
            if not title:
                return ActionResult(verb, False, "no title")
            windows = getattr(self, "_window_infos", None) or []
            if self._desktop.focus_window(title, windows):
                resolved = resolve_window_target(title, windows)
                label = f"[{resolved['token']}] {resolved['title']}" if resolved else title
                return ActionResult(verb, True, f"focused '{label}'")
            return ActionResult(verb, False, f"window '{title}' not found")

        if verb == "open_url":
            browser = str(args.get(cfg.get("browser_field", "target"), "")).strip()
            url = str(args.get(cfg.get("url_field", "value"), "")).strip()
            if not url:
                return ActionResult(verb, False, "no url")
            ok, message = self._desktop.open_url(browser, url)
            return ActionResult(verb, ok, message)

        if verb == "wait":
            import time
            raw = args.get(cfg.get("amount_field", "value"), args.get("value", args.get("target", "")))
            try:
                ms = int(raw or 1000)
            except (TypeError, ValueError):
                ms = 1000
            ms = max(100, min(ms, 30000))
            time.sleep(ms / 1000.0)
            return ActionResult(verb, True, f"waited {ms} ms")

        return ActionResult(verb, False, f"unhandled verb: {verb}")

_desktop: Desktop | None = None
_executor: ActionExecutor | None = None
_desktop_lock = threading.RLock()
_last_observation: Observation | None = None
_runtime_wiring: dict[str, Any] | None = None

_ELEMENT_VERBS = frozenset({"click", "scroll"})

def configure_runtime(wiring: dict[str, Any] | None) -> None:
    """Accept live wiring updates from server.py without recreating the desktop."""
    global _runtime_wiring, _executor
    with _desktop_lock:
        _runtime_wiring = dict(wiring or {})
        configure_observation(_runtime_wiring.get("observe", {}))
        if _desktop is not None:
            _executor = ActionExecutor(_desktop, _runtime_wiring)


def _init():
    global _desktop, _executor
    if _desktop is None:
        import json, pathlib
        wiring = _runtime_wiring or json.loads((pathlib.Path(__file__).parent / "prompts" / "wiring.json").read_text(encoding="utf-8"))
        configure_observation(wiring.get("observe", {}))
        _desktop = Desktop()
        _executor = ActionExecutor(_desktop, wiring)

def _remember_observation(obs: Observation) -> None:
    global _last_observation
    _last_observation = obs

def _needs_elements(verb: str, target: str) -> bool:
    return verb in _ELEMENT_VERBS or (verb == "write" and bool(target))

def _observation_windows(obs: Observation | None) -> list[dict[str, Any]]:
    if obs is None:
        return []
    snapshot = getattr(obs, "snapshot", None)
    if isinstance(snapshot, dict) and isinstance(snapshot.get("windows"), list):
        return snapshot["windows"]
    return []


def _focus_already_satisfied(target: str, obs: Observation | None) -> bool:
    focused = (getattr(obs, "focused_title", "") or "").lower().strip()
    target_l = (target or "").lower().strip()
    if not focused or not target_l:
        return False
    resolved = resolve_window_target(target, _observation_windows(obs))
    if resolved and bool(resolved.get("focused")):
        return True
    if target_l in focused or focused in target_l:
        return True
    words = [w for w in re.split(r"[\s\-]+", target_l) if len(w) > 2]
    return bool(words and any(w in focused for w in words))

def observe_screen() -> str:
    with _desktop_lock:
        _init()
        desktop = _desktop
        assert desktop is not None
        obs = desktop.observe()
        _remember_observation(obs)
        return obs.context_text

def last_observation_snapshot() -> dict[str, Any]:
    with _desktop_lock:
        if _last_observation is None:
            return {}
        snapshot = getattr(_last_observation, "snapshot", None)
        return snapshot if isinstance(snapshot, dict) else {}

def get_focused_title() -> str:
    """Lightweight post-action snapshot: just the focused window title."""
    with _desktop_lock:
        _init()
        desktop = _desktop
        assert desktop is not None
        hwnd = int(desktop.user32.GetForegroundWindow())
        import ctypes
        buf = ctypes.create_unicode_buffer(512)
        desktop.user32.GetWindowTextW(ctypes.c_void_p(hwnd), buf, 512)
        return buf.value or ""


def execute_verb(verb: str, target: str, value: str = "") -> str:
    with _desktop_lock:
        _init()
        obs = _last_observation
        if _needs_elements(verb, target) and obs is None:
            desktop = _desktop
            assert desktop is not None
            obs = desktop.observe()
            _remember_observation(obs)
        args = {"target": target, "value": value}
        elements = obs.elements if obs else {}
        if verb == "focus" and _focus_already_satisfied(target, obs):
            focused = getattr(obs, "focused_title", target)
            return f"focused '{focused}' (already focused)"
        executor = _executor
        assert executor is not None
        executor._window_infos = _observation_windows(obs)
        result = executor.execute(verb, args, elements)
        return result.observation if result.success else f"FAILED: {result.observation}"
