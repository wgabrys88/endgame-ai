from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import CachedNode

CLICK = {
    "Button", "Calendar", "CheckBox", "Hyperlink", "ListItem", "MenuItem",
    "RadioButton", "Tab", "TabItem", "TreeItem", "DataItem", "SplitButton",
}
WRITE = {"Edit", "ComboBox", "Spinner", "Document"}
SCROLL = {"List", "ScrollBar", "Slider", "Tree", "DataGrid"}


def classify_role(role: str, class_name: str = "") -> str:
    if role in CLICK:
        return "click"
    if role in WRITE:
        return "write"
    if role == "Pane" and class_name == "Scintilla":
        return "write"
    if role in SCROLL:
        return "scroll"
    return ""


def display_name(node: CachedNode, text_max: int) -> str:
    base = (node.name or "").strip()
    text = (node.text_full or node.value or "").strip()
    if text and len(text) > len(base):
        return text[:text_max]
    return base


@dataclass
class FilteredObservation:
    action_elements: dict[str, dict[str, Any]] = field(default_factory=dict)
    llm_nodes: list[dict[str, Any]] = field(default_factory=list)
    gather_nodes: list[dict[str, Any]] = field(default_factory=list)


class ObservationFilter:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = dict(config or {})

    def apply(self, nodes: list[CachedNode]) -> FilteredObservation:
        filt = self.config.get("filter") or {}
        max_action = int(filt.get("max_action_nodes", 240))
        max_llm = int(filt.get("max_llm_nodes", 180))
        text_max = int(filt.get("text_hint_max", 120))
        require_interactive = bool(filt.get("require_interactive", True))
        action_elements: dict[str, dict[str, Any]] = {}
        llm_nodes: list[dict[str, Any]] = []
        gather_nodes = [n.to_gather_dict() for n in nodes]

        ranked = sorted(
            nodes,
            key=lambda n: (
                0 if n.keyboard_focus else 1,
                0 if n.name or n.text_full else 1,
                0 if not n.offscreen else 1,
            ),
        )

        for node in ranked:
            if node.offscreen or not node.enabled:
                continue
            rect = node.rect
            if rect.get("right", 0) <= rect.get("left", 0) or rect.get("bottom", 0) <= rect.get("top", 0):
                continue
            action = classify_role(node.role, node.class_name)
            label = display_name(node, text_max)
            if len(llm_nodes) < max_llm:
                if label or node.text_full or node.keyboard_focus:
                    if not require_interactive or action or node.keyboard_focus:
                        llm_nodes.append(node.to_llm_dict())
            if action and len(action_elements) < max_action:
                action_elements[node.id] = {
                    "id": node.id,
                    "name": label or node.name,
                    "role": node.role,
                    "action": action,
                    "px": node.px,
                    "py": node.py,
                    "hwnd": node.hwnd,
                    "rect": node.rect,
                    "enabled": node.enabled,
                    "focused": node.keyboard_focus,
                    "automation_id": node.automation_id,
                    "class_name": node.class_name,
                    "runtime_id": node.runtime_id,
                }

        return FilteredObservation(
            action_elements=action_elements,
            llm_nodes=llm_nodes,
            gather_nodes=gather_nodes,
        )