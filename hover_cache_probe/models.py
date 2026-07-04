"""Data shapes for hover cache probe reports."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CachedNode:
    id: str
    role: str
    name: str
    automation_id: str = ""
    class_name: str = ""
    hwnd: int = 0
    framework_id: str = ""
    px: int = 0
    py: int = 0
    rect: dict[str, int] = field(default_factory=dict)
    enabled: bool = True
    keyboard_focus: bool = False
    offscreen: bool = False
    runtime_id: list[int] = field(default_factory=list)
    text_full: str | None = None
    value: str | None = None
    patterns: list[str] = field(default_factory=list)
    source_probe: tuple[int, int] | None = None

    def to_gather_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "role": self.role,
            "name": self.name,
            "hwnd": self.hwnd,
            "px": self.px,
            "py": self.py,
            "rect": self.rect,
            "enabled": self.enabled,
            "keyboard_focus": self.keyboard_focus,
            "offscreen": self.offscreen,
            "patterns": self.patterns,
        }
        if self.automation_id:
            out["automation_id"] = self.automation_id
        if self.class_name:
            out["class_name"] = self.class_name
        if self.framework_id:
            out["framework_id"] = self.framework_id
        if self.text_full:
            out["text_full"] = self.text_full
        if self.value:
            out["value"] = self.value
        if self.source_probe:
            out["source_probe"] = list(self.source_probe)
        return out

    def to_llm_dict(self) -> dict[str, Any]:
        """Minimal LLM-facing projection (filter layer preview)."""
        out: dict[str, Any] = {
            "id": self.id,
            "role": self.role,
            "name": self.name,
        }
        if self.keyboard_focus:
            out["keyboard_focus"] = True
        if not self.name and self.automation_id:
            out["automation_id"] = self.automation_id
        if self.text_full:
            n = len(self.text_full)
            out["text_hint"] = {
                "length": n,
                "prefix": self.text_full[:200] if n else "",
            }
        return out