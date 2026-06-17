"""Colony - multi-slot orchestrator with comms_operator and global mutator."""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any

from llm import LLMClient
from bus import Bus
from slot import Slot

SLOT_CONFIGS: dict[str, dict[str, Any]] = {
    "architect": {"can_act_desktop": False},
    "implementor": {"can_act_desktop": True},
    "reviewer": {"can_act_desktop": False},
    "devops": {"can_act_desktop": False},
}


class CommsOperator:
    """Decomposes user goals into sub-goals and routes them to slots via bus."""

    def __init__(self, llm: LLMClient, bus: Bus, slot_names: list[str]):
        self._llm = llm
        self._bus = bus
        self._slot_names = slot_names
        self._last_goal: str = ""

    def route(self, goal: str) -> dict[str, Any]:
        if goal == self._last_goal:
            return {"phase": "comms", "action": "skip", "reason": "same goal"}
        self._last_goal = goal
        context = (
            f"GOAL: {goal}\n"
            f"AVAILABLE SLOTS: {', '.join(self._slot_names)}\n"
            "  architect = design, strategy, structure\n"
            "  implementor = execution, file ops, GUI actions, code\n"
            "  reviewer = verification, quality audits\n"
            "  devops = git, deployment, system health\n\n"
            "Decompose the goal into sub-goals. Assign each to ONE slot.\n"
            'Return record_type "route" with data containing routes array: [{"to":"slot_name","goal":"sub-goal"}]'
        )
        result = self._llm.call(
            "You are a comms_operator. Decompose goals and route to worker slots.",
            context,
        )
        try:
            parsed = json.loads(result.text)
        except (json.JSONDecodeError, TypeError):
            parsed = {}
        data = parsed.get("data", parsed)
        routes = data.get("routes", [])
        if not isinstance(routes, list) or not routes:
            self._bus.publish("route", "comms_operator", "",
                             {"to": "implementor", "goal": goal, "status": "open"})
            return {"phase": "comms", "routed": 1, "fallback": True}
        count = 0
        for r in routes:
            if not isinstance(r, dict):
                continue
            to = str(r.get("to", "")).strip()
            sub_goal = str(r.get("goal", "")).strip()
            if to in self._slot_names and sub_goal:
                self._bus.publish("route", "comms_operator", "", {"to": to, "goal": sub_goal, "status": "open"})
                count += 1
        if count == 0:
            self._bus.publish("route", "comms_operator", "",
                             {"to": "implementor", "goal": goal, "status": "open"})
            count = 1
        return {"phase": "comms", "routed": count}


class GlobalMutator:
    """Reads cross-slot denial patterns, proposes planner prompt patches."""

    def __init__(self, llm: LLMClient, bus: Bus, slots: dict[str, Slot]):
        self._llm = llm
        self._bus = bus
        self._slots = slots
        self._last_run: float = 0
        self._interval: float = 60.0

    def step(self) -> dict[str, Any] | None:
        now = time.time()
        if now - self._last_run < self._interval:
            return None
        self._last_run = now
        denials: dict[str, int] = {}
        for name, slot in self._slots.items():
            count = sum(1 for h in slot.state.history[-10:]
                        if isinstance(h, dict) and h.get("denied"))
            if count >= 3:
                denials[name] = count
        if not denials:
            return None
        context = (
            f"STRUGGLING SLOTS: {json.dumps(denials)}\n"
            f"BUS CONTEXT:\n{self._bus.format_context(limit=10)}\n"
            "Suggest planner prompt improvements for the struggling slots.\n"
            'Return record_type "mutation" with data containing targets array and suggestion string.'
        )
        result = self._llm.call(
            "You are a global mutator. Analyze cross-slot failures and suggest planner improvements.",
            context, max_tokens=512,
        )
        try:
            parsed = json.loads(result.text)
            data = parsed.get("data", parsed)
        except (json.JSONDecodeError, TypeError):
            data = {"suggestion": result.text[:500]}
        self._bus.publish("global_mutation", "global_mutator", "",
                          {"targets": list(denials.keys()), "suggestion": str(data.get("suggestion", ""))[:500]})
        return {"phase": "global_mutate", "targets": list(denials.keys()), "suggestion": result.text[:200]}


class Colony:
    """Multi-slot orchestrator. Reusable as a component in larger systems."""

    def __init__(self, llm: LLMClient, bus: Bus, prompts_dir: Path, workspace: Path):
        self.llm = llm
        self.bus = bus
        self.all_slots: dict[str, Slot] = {}
        self.active_slots: dict[str, Slot] = {}
        for name, cfg in SLOT_CONFIGS.items():
            slot_prompts = prompts_dir / name
            if not slot_prompts.exists():
                slot_prompts = prompts_dir
            slot = Slot(name=name, llm=llm, bus=bus, prompts_dir=slot_prompts,
                        workspace=workspace, can_act_desktop=cfg["can_act_desktop"])
            self.all_slots[name] = slot
            self.active_slots[name] = slot
        self.comms = CommsOperator(llm, bus, list(SLOT_CONFIGS.keys()))
        self.global_mutator = GlobalMutator(llm, bus, self.all_slots)
        self._actor_lock: str = ""

    def set_goal(self, goal: str):
        self.comms.route(goal)

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
        if not self.all_slots.get(self._actor_lock, None):
            self._actor_lock = name
            return True
        holder = self.all_slots[self._actor_lock]
        active_task = next((t for t in holder.state.tasks if t.status == "active"), None)
        if not active_task:
            self._actor_lock = name
            return True
        return False

    def release_actor_lock(self, name: str):
        if self._actor_lock == name:
            self._actor_lock = ""

    def step(self) -> list[tuple[str, dict[str, Any] | None]]:
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
            else:
                if slot.can_act_desktop:
                    self.release_actor_lock(name)
        self.global_mutator.step()
        return results
