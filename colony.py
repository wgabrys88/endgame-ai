"""Colony - multi-slot orchestrator with comms_operator and global mutator."""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any

from llm import LLMClient
from bus import Bus
from slot import Slot


class CommsOperator:
    """Decomposes user goals into sub-goals and routes them to slots via bus."""

    def __init__(self, llm: LLMClient, bus: Bus, slot_configs: dict[str, dict],
                 prompts_dir: Path, comms_cfg: dict[str, Any]):
        self._llm = llm
        self._bus = bus
        self._slot_names = list(slot_configs.keys())
        self._slot_configs = slot_configs
        self._last_goal: str = ""
        self._fallback_slot = str(comms_cfg["fallback_slot"])
        comms_path = prompts_dir / str(comms_cfg["prompt"])
        if not comms_path.exists():
            raise FileNotFoundError(f"comms prompt missing: {comms_path}")
        self._prompt = comms_path.read_text(encoding="utf-8").strip()

    def route(self, goal: str) -> dict[str, Any]:
        if goal == self._last_goal:
            return {"phase": "comms", "action": "skip"}
        self._last_goal = goal
        slot_desc = "\n".join(f"  {n} = {c.get('personality', '')}" for n, c in self._slot_configs.items())
        context = f"GOAL: {goal}\nAVAILABLE SLOTS:\n{slot_desc}"
        result = self._llm.call(self._prompt, context)
        try:
            parsed = json.loads(result.text)
        except (json.JSONDecodeError, TypeError):
            parsed = {}
        data = parsed.get("data", parsed) if isinstance(parsed, dict) else {}
        routes = data.get("routes", []) if isinstance(data, dict) else []
        if not isinstance(routes, list) or not routes:
            if self._fallback_slot not in self._slot_names:
                raise ValueError(f"comms.fallback_slot '{self._fallback_slot}' not in slots")
            self._bus.publish("route", "comms_operator", "",
                             {"to": self._fallback_slot, "goal": goal, "status": "open", "seq": 1})
            return {"phase": "comms", "routed": 1}
        count = 0
        for i, r in enumerate(routes):
            if not isinstance(r, dict):
                continue
            to = str(r.get("to", "")).strip()
            sub_goal = str(r.get("goal", "")).strip()
            if to in self._slot_names and sub_goal:
                seq = r.get("seq", i + 1)
                route_data: dict[str, Any] = {"to": to, "goal": sub_goal, "status": "open", "seq": seq}
                if "after" in r:
                    route_data["after"] = r["after"]
                self._bus.publish("route", "comms_operator", "", route_data)
                count += 1
        if count == 0:
            if self._fallback_slot not in self._slot_names:
                raise ValueError(f"comms.fallback_slot '{self._fallback_slot}' not in slots")
            self._bus.publish("route", "comms_operator", "",
                             {"to": self._fallback_slot, "goal": goal, "status": "open", "seq": 1})
            count = 1
        return {"phase": "comms", "routed": count}


class GlobalMutator:
    """Reads cross-slot denial patterns, proposes planner prompt patches."""

    def __init__(self, llm: LLMClient, bus: Bus, slots: dict[str, Slot], interval: float = 60.0):
        self._llm = llm
        self._bus = bus
        self._slots = slots
        self._last_run: float = 0
        self._interval = interval

    def step(self) -> dict[str, Any] | None:
        now = time.time()
        if now - self._last_run < self._interval:
            return None
        self._last_run = now
        denials: dict[str, int] = {}
        for name, slot in self._slots.items():
            count = sum(1 for h in slot.state.history[-10:] if isinstance(h, dict) and h.get("denied"))
            if count >= 3:
                denials[name] = count
        if not denials:
            return None
        context = (
            f"STRUGGLING SLOTS: {json.dumps(denials)}\n"
            f"BUS CONTEXT:\n{self._bus.format_context(limit=10)}\n"
            "Suggest planner prompt improvements.\n"
            'Return record_type "mutation" with data containing suggestion string.'
        )
        result = self._llm.call("You are a global mutator. Analyze failures and suggest improvements.",
                                context)
        try:
            data = json.loads(result.text).get("data", {})
        except (json.JSONDecodeError, TypeError):
            data = {}
        self._bus.publish("global_mutation", "global_mutator", "",
                          {"targets": list(denials.keys()), "suggestion": str(data.get("suggestion", ""))})
        return {"phase": "global_mutate", "targets": list(denials.keys())}


class Colony:
    """Multi-slot orchestrator. Wiring-driven."""

    def __init__(self, llm: LLMClient, bus: Bus, prompts_dir: Path, workspace: Path, wiring: dict[str, Any]):
        self.llm = llm
        self.bus = bus
        self._wiring = wiring
        slot_configs = wiring["slots"]
        self.all_slots: dict[str, Slot] = {}
        self.active_slots: dict[str, Slot] = {}
        for name, cfg in slot_configs.items():
            slot_prompts = prompts_dir / name if (prompts_dir / name).exists() else prompts_dir
            slot = Slot(name=name, llm=llm, bus=bus, prompts_dir=slot_prompts, workspace=workspace,
                        wiring=wiring, can_act_desktop=cfg.get("can_desktop", False))
            self.all_slots[name] = slot
            self.active_slots[name] = slot
        self.comms = CommsOperator(llm, bus, slot_configs, prompts_dir, wiring["comms"])
        self.global_mutator = GlobalMutator(llm, bus, self.all_slots,
                                            interval=wiring["limits"].get("global_mutator_interval_s", 60))
        self._actor_lock: str = ""

    def set_goal(self, goal: str):
        if not self.active_slots:
            slot = str(self._wiring["comms"]["fallback_slot"])
            self.bus.publish("route", "comms_operator", "",
                            {"to": slot, "goal": goal, "status": "open", "seq": 1})
        else:
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
        holder = self.all_slots.get(self._actor_lock)
        if not holder:
            self._actor_lock = name
            return True
        active = next((t for t in holder.state.tasks if t.status == "active"), None)
        if not active:
            self._actor_lock = name
            return True
        return False

    def release_actor_lock(self, name: str):
        if self._actor_lock == name:
            self._actor_lock = ""

    def step(self) -> list[tuple[str, dict[str, Any] | None]]:
        # Activate slots that have pending routes addressed to them
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
            else:
                if slot.can_act_desktop:
                    self.release_actor_lock(name)
        self.global_mutator.step()
        return results
