"""Deterministic desktop simulation for dev/test — zero deps, task-agnostic."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from desktop import Element, Observation


@dataclass(slots=True)
class _Scene:
    focused: str
    nodes: list[dict[str, Any]]


class SimDesktop:
    """Minimal UI state machine driven by verb execution."""

    def __init__(self):
        self._scene = _Scene(focused="Desktop", nodes=[])

    def observe(self) -> Observation:
        nodes = self._scene.nodes
        elements: dict[str, Element] = {}
        lines = [f"FOCUSED: {self._scene.focused}"]
        seq = 0
        for n in nodes:
            if n.get("action") == "read":
                lines.append(f"  {n['role']} \"{n.get('name', '')}\"")
                continue
            seq += 1
            eid = str(seq)
            role = n["role"]
            name = n.get("name", "")
            value = n.get("value", "")
            if value and n.get("action") == "write":
                desc = f'[{eid}] {role} "{name}" = "{value[:80]}"' if name else f'[{eid}] {role} "{value[:80]}"'
            elif name:
                desc = f'[{eid}] {role} "{name}"'
            else:
                desc = f'[{eid}] {role}'
            lines.append(f"  {desc}")
            elements[eid] = Element(
                id=eid,
                role=role,
                name=name,
                value=value,
                hwnd=1,
                px=n.get("x", 0),
                py=n.get("y", 0),
                pw=n.get("w", 100),
                ph=n.get("h", 24),
                action=n.get("action", "click"),
                wnd=self._scene.focused,
                enabled=True,
                readonly=False,
            )
        return Observation(self._scene.focused, elements, "\n".join(lines))

    def click(self, px: int, py: int, hwnd: int = 0):
        return None

    def type_text(self, text: str):
        for n in self._scene.nodes:
            if n.get("action") == "write":
                n["value"] = text
                return

    def press_key(self, key: str):
        self._apply_key(key)

    def hotkey(self, keys: list[str]):
        joined = "+".join(k.lower() for k in keys)
        if joined in ("win+r", "r+win"):
            self._open_run_dialog()
        elif "enter" in keys or keys == ["enter"]:
            self._apply_key("enter")
        else:
            for k in keys:
                self._apply_key(k)

    def scroll(self, px: int, py: int, amount: int = 3):
        return None

    def focus_window(self, title: str) -> bool:
        title_l = title.lower()
        if title_l in self._scene.focused.lower() or self._scene.focused.lower() in title_l:
            return True
        self._scene.focused = title
        return True

    def _open_run_dialog(self):
        self._scene.focused = "Run"
        self._scene.nodes = [
            {"role": "Edit", "name": "Open", "value": "", "action": "write", "x": 40, "y": 40, "w": 280, "h": 24},
            {"role": "Button", "name": "OK", "action": "click", "x": 200, "y": 80, "w": 80, "h": 24},
            {"role": "Button", "name": "Cancel", "action": "click", "x": 290, "y": 80, "w": 80, "h": 24},
        ]

    def _apply_key(self, key: str):
        key = key.lower()
        if key == "enter" and self._scene.focused == "Run":
            open_value = ""
            for n in self._scene.nodes:
                if n.get("name", "").lower() == "open":
                    open_value = (n.get("value") or "").lower()
            if open_value == "notepad":
                self._open_notepad()
        elif key == "enter":
            return

    def _open_notepad(self):
        self._scene.focused = "Notepad"
        self._scene.nodes = [
            {"role": "Document", "name": "Text Editor", "value": "", "action": "write", "x": 0, "y": 0, "w": 800, "h": 600},
        ]