"""Colony - graph executor orchestrator driven by prompts/wiring.json."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from llm import LLMClient
from bus import Bus
from slot import Slot
from topology import GraphExecutor, GraphRuntime
from wiring import load_wiring


class Colony:
    """Wiring-driven. colony.step() = one topology graph cycle per active slot."""

    def __init__(self, llm: LLMClient, bus: Bus, prompts_dir: Path, workspace: Path,
                 wiring: dict[str, Any], *, desktop_enabled: bool = True,
                 desktop: Any = None, actions: Any = None,
                 llm_hook: Any = None):
        self.llm = llm
        self.bus = bus
        self._prompts_dir = prompts_dir
        self._workspace = workspace
        self._wiring = wiring
        self._desktop_enabled = desktop_enabled
        self._desktop = desktop
        self._actions = actions
        self._llm_hook = llm_hook
        self.all_slots: dict[str, Slot] = {}
        self.active_slots: dict[str, Slot] = {}
        self._executor: GraphExecutor | None = None
        self._apply_wiring(wiring)

    def _apply_wiring(self, wiring: dict[str, Any]) -> None:
        self._wiring = wiring
        slot_configs = wiring["slots"]
        enabled = {n: c for n, c in slot_configs.items() if c.get("enabled", True)}
        for name in list(self.active_slots):
            if name not in enabled:
                del self.active_slots[name]
        for name in list(self.all_slots):
            if name not in enabled:
                del self.all_slots[name]
        for name, cfg in enabled.items():
            if name not in self.all_slots:
                self.all_slots[name] = Slot(
                    name=name, wiring=wiring, can_act_desktop=bool(cfg["can_desktop"]),
                )
        runtime = GraphRuntime(
            wiring=wiring,
            llm=self.llm,
            bus=self.bus,
            workspace=self._workspace,
            prompts_dir=self._prompts_dir,
            desktop_enabled=self._desktop_enabled,
            desktop=self._desktop,
            actions=self._actions,
            llm_hook=self._llm_hook,
        )
        if self._executor is None:
            self._executor = GraphExecutor(runtime)
        else:
            self._executor._rt.desktop = self._desktop
            self._executor._rt.actions = self._actions
            self._executor._rt.desktop_enabled = self._desktop_enabled
            self._executor._rt.llm_hook = self._llm_hook
            self._executor.update_wiring(wiring)

    def reload_wiring(self) -> None:
        self._apply_wiring(load_wiring(self._prompts_dir))

    def set_desktop(self, desktop: Any, actions: Any, enabled: bool) -> None:
        self._desktop = desktop
        self._actions = actions
        self._desktop_enabled = enabled
        if self._executor:
            self._executor._rt.desktop = desktop
            self._executor._rt.actions = actions
            self._executor._rt.desktop_enabled = enabled

    def set_llm_hook(self, hook: Any) -> None:
        self._llm_hook = hook
        if self._executor:
            self._executor._rt.llm_hook = hook

    def set_goal(self, goal: str) -> None:
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

    def step(self) -> list[tuple[str, dict[str, Any] | None]]:
        self.reload_wiring()
        for r in self.bus.records:
            if r.record_type == "route" and r.data.get("status") == "open":
                target = r.data.get("to", "")
                if target in self.all_slots and target not in self.active_slots:
                    self.active_slots[target] = self.all_slots[target]
        results: list[tuple[str, dict[str, Any] | None]] = []
        assert self._executor is not None
        for name, slot in list(self.active_slots.items()):
            result = self._executor.run_cycle(name, slot)
            if result:
                result["phase"] = self._wiring["startup"]["circuit"]
                results.append((name, result))
        return results