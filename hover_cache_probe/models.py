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
    properties: dict[str, Any] = field(default_factory=dict)
    pattern_payloads: dict[str, Any] = field(default_factory=dict)
    text_sources: dict[str, str] = field(default_factory=dict)
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
        if self.text_sources:
            out["text_sources"] = self.text_sources
        if self.properties:
            out["properties"] = self.properties
        if self.pattern_payloads:
            out["pattern_payloads"] = self.pattern_payloads
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
        best = self.text_full or self.value or (self.text_sources.get("name") if self.text_sources else None)
        if best:
            n = len(best)
            out["text_hint"] = {
                "length": n,
                "prefix": best[:200] if n else "",
                "sources": list(self.text_sources.keys()) if self.text_sources else [],
            }
        return out