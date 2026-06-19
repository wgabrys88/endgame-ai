"""Colony - single-path orchestrator driven by prompts/wiring.drawio."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from llm import LLMClient
from bus import Bus
from slot import Slot
from wiring import load_wiring


class Colony:
    """Wiring-driven. One startup path: startup.slot → startup.circuit loop."""

    def __init__(self, llm: LLMClient, bus: Bus, prompts_dir: Path, workspace: Path, wiring: dict[str, Any]):
        self.llm = llm
        self.bus = bus
        self._prompts_dir = prompts_dir
        self._workspace = workspace
        self._wiring = wiring
        self.all_slots: dict[str, Slot] = {}
        self.active_slots: dict[str, Slot] = {}
        self._actor_lock: str = ""
        self._apply_wiring(wiring)

    def _apply_wiring(self, wiring: dict[str, Any]) -> None:
        self._wiring = wiring
        slot_configs = wiring["slots"]
        enabled = {n: c for n, c in slot_configs.items() if c.get("enabled", True)}
        # Drop slots that are no longer enabled
        for name in list(self.active_slots):
            if name not in enabled:
                del self.active_slots[name]
        for name in list(self.all_slots):
            if name not in enabled:
                del self.all_slots[name]
        for name, cfg in enabled.items():
            if name not in self.all_slots:
                slot_prompts = self._prompts_dir / name if (self._prompts_dir / name).exists() else self._prompts_dir
                self.all_slots[name] = Slot(
                    name=name, llm=self.llm, bus=self.bus, prompts_dir=slot_prompts,
                    workspace=self._workspace, wiring=wiring, can_act_desktop=bool(cfg["can_desktop"]),
                )

    def reload_wiring(self) -> None:
        self._apply_wiring(load_wiring(self._prompts_dir))

    def set_goal(self, goal: str) -> None:
        """Single declarative path: wiring.startup.slot always receives the goal."""
        slot = str(self._wiring["startup"]["slot"])
        self.bus.publish("route", "startup", "", {"to": slot, "goal": goal, "status": "open", "seq": 1})

    def toggle_slot(self, name: str) -> bool:
        if name not in self.all_slots:
            return False
        if name in self.active_slots:
            del self.active_slots[name]
        else:
            self.active_slots[name] = self.all_slots[name]
        return True

    def is_active(self, name: str) -> bool:
        return name in self.active_slots

    def acquire_actor_lock(self, name: str) -> bool:
        if not self._actor_lock or self._actor_lock == name:
            self._actor_lock = name
            return True
        holder = self.all_slots.get(self._actor_lock)
        if not holder:
            self._actor_lock = name
            return True
        active = next((t for t in holder.state.tasks if t.status == "active"), None)
        if not active:
            self._actor_lock = name
            return True
        return False

    def release_actor_lock(self, name: str) -> None:
        if self._actor_lock == name:
            self._actor_lock = ""

    def step(self) -> list[tuple[str, dict[str, Any] | None]]:
        self.reload_wiring()
        for r in self.bus.records:
            if r.record_type == "route" and r.data.get("status") == "open":
                target = r.data.get("to", "")
                if target in self.all_slots and target not in self.active_slots:
                    self.active_slots[target] = self.all_slots[target]
        results: list[tuple[str, dict[str, Any] | None]] = []
        for name, slot in list(self.active_slots.items()):
            if slot.can_act_desktop and not self.acquire_actor_lock(name):
                continue
            result = slot.step()
            if result:
                results.append((name, result))
                if slot.can_act_desktop:
                    active = next((t for t in slot.state.tasks if t.status == "active"), None)
                    if not active:
                        self.release_actor_lock(name)
            elif slot.can_act_desktop:
                self.release_actor_lock(name)
        return results