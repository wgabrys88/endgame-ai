from __future__ import annotations
import json
import os
import random
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from config import BASE_DIR, COMMS_DIR, SCREEN_LOCK_PATH, trace

COMMS_DIR.mkdir(parents=True, exist_ok=True)


class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[Callable[[dict], None]]] = {}
        self._lock = threading.RLock()

    def subscribe(self, topic: str, callback: Callable[[dict], None]) -> None:
        with self._lock:
            self._subscribers.setdefault(topic, []).append(callback)

    def publish(self, topic: str, payload: dict) -> None:
        with self._lock:
            listeners = list(self._subscribers.get(topic, []))
        for cb in listeners:
            try:
                cb(payload)
            except Exception:
                pass


@dataclass(slots=True)
class AgentHandle:
    agent_id: str
    goal: str
    pid: int
    status_file: Path
    state: str = "running"
    result: str = ""
    error: str = ""
    started_at: float = field(default_factory=time.time)


@dataclass(slots=True)
class Blackboard:
    goal: str = ""
    original_goal: str = ""
    cycle: int = 0
    max_cycles: int = 0
    mode: str = "direct"
    agent_id: str = "main"

    screen: str = ""
    screen_hash: str = ""
    screen_elements: dict[str, Any] = field(default_factory=dict)

    history: list[dict[str, Any]] = field(default_factory=list)

    last_verb: str = ""
    last_success: bool = False
    last_observation: str = ""
    last_expect: str = ""

    done_claimed: bool = False
    done_evidence: str = ""
    problem: str = ""

    consecutive_failures: int = 0

    recent_action_signatures: list[str] = field(default_factory=list)
    repetition_score: float = 0.0
    chaos_level: float = 0.0
    lorenz_x: float = 0.1
    lorenz_y: float = 0.0
    lorenz_z: float = 0.0
    blocked_signatures: list[str] = field(default_factory=list)
    expectation_miss_streak: int = 0

    actor_observe: str = ""
    actor_reason: str = ""

    children: dict[str, AgentHandle] = field(default_factory=dict)
    completed_subtasks: list[dict[str, Any]] = field(default_factory=list)
    pending_subtasks: list[dict[str, Any]] = field(default_factory=list)

    events: EventBus = field(default_factory=EventBus)

    _screen_lock_held: bool = False

    def acquire_screen(self) -> bool:
        lock_data = {"agent_id": self.agent_id, "ts": time.time(), "pid": os.getpid()}
        if SCREEN_LOCK_PATH.exists():
            try:
                existing = json.loads(SCREEN_LOCK_PATH.read_text(encoding="utf-8"))
                if existing.get("agent_id") != self.agent_id:
                    age = time.time() - existing.get("ts", 0)
                    if age < 30:
                        trace("screen_lock.denied", f"held by {existing.get('agent_id')} for {age:.1f}s")
                        return False
            except (json.JSONDecodeError, OSError):
                pass
        tmp = SCREEN_LOCK_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(lock_data), encoding="utf-8")
        os.replace(str(tmp), str(SCREEN_LOCK_PATH))
        self._screen_lock_held = True
        trace("screen_lock.acquired", f"agent={self.agent_id}")
        return True

    def release_screen(self) -> None:
        if self._screen_lock_held and SCREEN_LOCK_PATH.exists():
            try:
                data = json.loads(SCREEN_LOCK_PATH.read_text(encoding="utf-8"))
                if data.get("agent_id") == self.agent_id:
                    SCREEN_LOCK_PATH.unlink(missing_ok=True)
            except (json.JSONDecodeError, OSError):
                pass
        self._screen_lock_held = False
        trace("screen_lock.released", f"agent={self.agent_id}")

    def poll_inbox(self) -> list[dict]:
        from persistence import poll_events
        raw_events = poll_events(self.agent_id)
        commands = []
        for evt in raw_events:
            verb = evt.get("verb", "")
            payload = evt.get("payload", "")
            if verb in ("goal_rewrite", "hint", "kill", "inject_lesson", "set_chaos"):
                commands.append({"type": verb, "payload": payload})
        if commands:
            trace("inbox.received", f"commands={len(commands)}")
        return commands

    def poll_children(self) -> list[dict[str, Any]]:
        from persistence import poll_events
        events = []
        child_events = poll_events(self.agent_id)
        for evt in child_events:
            verb = evt.get("verb", "")
            source = evt.get("source", "")
            payload = evt.get("payload") or {}
            if verb == "child_done" and source in self.children:
                handle = self.children[source]
                handle.state = "done"
                handle.result = payload.get("result", "")
                events.append({"agent_id": source, "state": "done", "result": handle.result, "error": ""})
                self.completed_subtasks.append({"agent_id": source, "goal": handle.goal, "result": handle.result})
            elif verb == "child_failed" and source in self.children:
                handle = self.children[source]
                handle.state = "failed"
                handle.error = payload.get("error", "")
                events.append({"agent_id": source, "state": "failed", "result": "", "error": handle.error})
                self.pending_subtasks.append({"sub_goal": handle.goal, "agent_id": f"{source}_retry", "reason": f"retry: {handle.error}"})
        return events

    def all_children_done(self) -> bool:
        if not self.children:
            return False
        return all(h.state in ("done", "failed") for h in self.children.values())

    def any_children_failed(self) -> list[str]:
        return [aid for aid, h in self.children.items() if h.state == "failed"]

    def active_children_count(self) -> int:
        return sum(1 for h in self.children.values() if h.state == "running")

    def children_summary(self) -> str:
        if not self.children:
            return ""
        lines = ["CHILD AGENTS:"]
        for aid, h in self.children.items():
            elapsed = int(time.time() - h.started_at)
            lines.append(f"  [{aid}] state={h.state} goal='{h.goal}' elapsed={elapsed}s")
            if h.result:
                lines.append(f"    result: {h.result}")
            if h.error:
                lines.append(f"    error: {h.error}")
        return "\n".join(lines)

    def completed_summary(self) -> str:
        if not self.completed_subtasks:
            return ""
        lines = ["COMPLETED SUBTASKS:"]
        for st in self.completed_subtasks:
            lines.append(f"  [{st['agent_id']}] {st['goal']} -> {st['result']}")
        return "\n".join(lines)

    def format_history(self, label: str = "RECENT", limit: int = 3) -> str:
        recent = self.history[-limit:]
        if not recent:
            return ""
        lines = [label + ":"]
        for h in recent:
            lines.append(f"  {h['verb']} -> {'ok' if h['success'] else 'FAIL'}: {h['obs']}")
        return "\n".join(lines)

    def rewrite_goal(self, new_goal: str) -> None:
        if not new_goal or not isinstance(new_goal, str):
            return
        if not self.original_goal:
            self.original_goal = self.goal
        old = self.goal
        self.goal = new_goal.strip()
        self.events.publish("goal.rewritten", {
            "old": old,
            "new": self.goal,
            "cycle": self.cycle,
        })

    def get_persistable_snapshot(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "original_goal": self.original_goal,
            "cycle": self.cycle,
            "max_cycles": self.max_cycles,
            "mode": self.mode,
            "agent_id": self.agent_id,
            "consecutive_failures": self.consecutive_failures,
            "last_verb": self.last_verb,
            "last_success": self.last_success,
            "problem": self.problem,
            "done_claimed": self.done_claimed,
            "repetition_score": self.repetition_score,
            "chaos_level": self.chaos_level,
            "lorenz_x": self.lorenz_x,
            "lorenz_y": self.lorenz_y,
            "lorenz_z": self.lorenz_z,
            "expectation_miss_streak": self.expectation_miss_streak,
            "history": self.history[-10:],
        }

    def load_from_snapshot(self, snap: dict) -> None:
        self.goal = snap.get("goal", self.goal)
        self.original_goal = snap.get("original_goal", self.original_goal)
        self.cycle = snap.get("cycle", 0)
        self.max_cycles = snap.get("max_cycles", 0)
        self.mode = snap.get("mode", "direct")
        self.agent_id = snap.get("agent_id", "main")
        self.consecutive_failures = snap.get("consecutive_failures", 0)
        self.last_verb = snap.get("last_verb", "")
        self.last_success = snap.get("last_success", False)
        self.problem = snap.get("problem", "")
        self.repetition_score = snap.get("repetition_score", 0.0)
        self.chaos_level = snap.get("chaos_level", 0.0)
        self.lorenz_x = snap.get("lorenz_x", 0.1)
        self.lorenz_y = snap.get("lorenz_y", 0.0)
        self.lorenz_z = snap.get("lorenz_z", 0.0)
        self.expectation_miss_streak = snap.get("expectation_miss_streak", 0)
        self.history = snap.get("history", [])

    def update_chaos_and_repetition(self, verb: str, target: str):
        signature = f"{verb}:{target}"
        self.recent_action_signatures.append(signature)
        self.recent_action_signatures = self.recent_action_signatures[-12:]

        sigs = self.recent_action_signatures
        n = len(sigs)
        if n >= 4:
            unique = len(set(sigs))
            self.repetition_score = 1.0 - (unique / n)
        else:
            self.repetition_score = 0.0

        x, y, z = self.lorenz_x, self.lorenz_y, self.lorenz_z
        sigma, rho, beta = 10.0, 28.0, 8.0 / 3.0
        dt = 0.02

        action_diversity = len(set(sigs[-6:])) / max(len(sigs[-6:]), 1)
        progress = 1.0 if (self.last_success and signature not in sigs[:-1]) else 0.0
        stagnation = (self.consecutive_failures
                      + (1.0 - action_diversity) * 3.0
                      + self.expectation_miss_streak * 2.5)

        x = x + sigma * (progress - x) * dt
        y = y + (x * (rho - stagnation) - y) * dt
        z = z + (x * y - beta * z) * dt

        mag = (x * x + y * y + z * z) ** 0.5
        if mag > 50.0:
            scale = 50.0 / mag
            x, y, z = x * scale, y * scale, z * scale

        self.lorenz_x, self.lorenz_y, self.lorenz_z = x, y, z
        self.chaos_level = min(1.0, abs(z) / rho)

        if self.chaos_level > 0.5:
            recent = sigs[-4:]
            self.blocked_signatures = list(set(recent))
        else:
            self.blocked_signatures = []

        self.events.publish("chaos.changed", {
            "x": round(x, 3), "y": round(y, 3), "z": round(z, 3),
            "chaos_level": round(self.chaos_level, 3),
            "blocked": self.blocked_signatures,
            "cycle": self.cycle,
        })

    def chaos_rejects_done(self) -> bool:
        return self.chaos_level > 0.3 or self.cycle < 3 or self.expectation_miss_streak > 0

    def chaos_forces_parallel(self) -> bool:
        return self.chaos_level > 0.7

    def chaos_blocks_action(self, verb: str, target: str) -> bool:
        return f"{verb}:{target}" in self.blocked_signatures

    def record_action(self, verb: str, args: dict, success: bool, observation: str) -> None:
        self.last_verb = verb
        self.last_success = success
        self.last_observation = observation

        self.history.append({
            "verb": verb,
            "args": args,
            "success": success,
            "obs": observation if observation else ""
        })
        if len(self.history) > 50:
            self.history = self.history[-50:]

        target = str(args.get("target", "") or args.get("selector", ""))
        self.update_chaos_and_repetition(verb, target)

        self.events.publish("action.recorded", {
            "verb": verb,
            "success": success,
            "obs": observation,
            "cycle": self.cycle
        })

    def _broadcast_action(self, verb: str, success: bool, observation: str) -> None:
        action_log = COMMS_DIR / f"{self.agent_id}_actions.jsonl"
        import json as _json
        line = _json.dumps({"verb": verb, "success": success, "obs": observation, "cycle": self.cycle, "ts": time.time()})
        with open(action_log, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        from config import CONSECUTIVE_FAILURES_FOR_REFLECT
        if self.consecutive_failures >= 3 and self.chaos_level > 0.5:
            self.events.publish("self_regulation.needs_goal_softening", {
                "failures": self.consecutive_failures,
                "chaos": self.chaos_level,
                "cycle": self.cycle,
            })
        if self.consecutive_failures >= CONSECUTIVE_FAILURES_FOR_REFLECT:
            self.events.publish("self_regulation.needs_reflection", {
                "failures": self.consecutive_failures,
                "cycle": self.cycle,
            })
            self.consecutive_failures = 0

    def record_success(self) -> None:
        self.consecutive_failures = 0
        if len(self.recent_action_signatures) > 3:
            self.recent_action_signatures = self.recent_action_signatures[-3:]

    def advance_cycle(self, cycle: int) -> None:
        self.cycle = cycle
        from config import REFLECT_EVERY_N_CYCLES, DISTILL_EVERY_N_CYCLES
        if cycle > 0 and cycle % REFLECT_EVERY_N_CYCLES == 0:
            self.events.publish("evolution.periodic_reflection_due", {"cycle": cycle})
        if cycle > 0 and cycle % DISTILL_EVERY_N_CYCLES == 0:
            self.events.publish("evolution.distillation_due", {"cycle": cycle})

    def record_screen(self, text: str, hash_val: str, elements: dict) -> None:
        self.screen = text
        self.screen_hash = hash_val
        self.screen_elements = elements

    def clear_signals(self) -> None:
        self.done_claimed = False
        self.done_evidence = ""
        self.problem = ""

    def planner_context(self) -> str:
        parts = [f"CYCLE: {self.cycle}"]
        if self.max_cycles > 0:
            parts.append(f"CYCLES_REMAINING: {self.max_cycles - self.cycle}")
        parts.append(f"MODE: {self.mode}")

        from config import BASE_DIR
        comms = BASE_DIR / "comms"
        if comms.exists():
            files = [f.name for f in comms.iterdir() if f.is_file()]
            if files:
                parts.append(f"COMMS FILES: {files}")

        if self.active_children_count() > 0:
            parts.append(f"ACTIVE CHILDREN: {self.active_children_count()}")
        children_sum = self.children_summary()
        if children_sum:
            parts.append(children_sum)
        completed_sum = self.completed_summary()
        if completed_sum:
            parts.append(completed_sum)
        if self.pending_subtasks:
            parts.append("PENDING SUBTASKS: " + json.dumps(self.pending_subtasks, ensure_ascii=False))

        if self.problem:
            parts.append(f"PROBLEM: {self.problem}")
        if self.consecutive_failures > 0:
            parts.append(f"CONSECUTIVE FAILURES: {self.consecutive_failures}")
        if self.last_verb:
            parts.append(f"LAST: {self.last_verb} success={self.last_success}")
            if self.last_observation:
                parts.append(f"RESULT: {self.last_observation}")
        hist = self.format_history()
        if hist:
            parts.append(hist)
        if self.actor_observe:
            parts.append(f"ACTOR OBSERVES: {self.actor_observe}")
        parts.append(f"SCREEN:\n{self.screen}")
        if self.last_expect:
            parts.append(f"EXPECTED: {self.last_expect}")
        if self.original_goal and self.original_goal != self.goal:
            parts.append(f"ORIGINAL GOAL: {self.original_goal}")
            parts.append(f"CURRENT GOAL (adapted): {self.goal}")
        else:
            parts.append(f"GOAL: {self.goal}")

        try:
            from persistence import get_evolution_ledger_context
            ledger = get_evolution_ledger_context(12)
            if ledger:
                parts.append(ledger)
        except Exception:
            pass

        if self.chaos_level > 0.25:
            parts.append(
                f"\n[CHAOS — Level {self.chaos_level:.2f} | Repetition {self.repetition_score:.2f}] "
                f"Prefer parallel decomposition or spawn_agent. Avoid repeating recent failing actions."
            )

        return "\n\n".join(parts)

    def actor_context(self, instruction: str) -> str:
        parts = []
        if instruction:
            parts.append(f"INSTRUCTION: {instruction}")
        if self.problem:
            parts.append(f"PROBLEM: {self.problem}")
        if self.last_verb:
            parts.append(f"LAST: {self.last_verb} success={self.last_success}")
            if self.last_observation:
                parts.append(f"RESULT: {self.last_observation}")
        if self.last_expect and not self.last_success:
            parts.append(f"EXPECTED FROM LAST CYCLE: {self.last_expect}")
        hist = self.format_history()
        if hist:
            parts.append(hist)
        needs_elements = bool(re.search(r"element\s+\d+|target.*\d+|\[\d+\]", instruction or ""))
        if needs_elements:
            parts.append(f"AVAILABLE ELEMENTS (use numeric IDs as selectors):\n{self.screen}")
        else:
            screen_lines = self.screen.split("\n")
            compact = [l for l in screen_lines if l.startswith("[") and ("W " in l or "Edt" in l or "Doc" in l)]
            if compact:
                parts.append(f"WRITABLE ELEMENTS:\n" + "\n".join(compact))
            parts.append(f"ELEMENT COUNT: {len(self.screen_elements)}")
        if self.original_goal and self.original_goal != self.goal:
            parts.append(f"ORIGINAL GOAL: {self.original_goal}")
            parts.append(f"CURRENT GOAL (adapted): {self.goal}")
        else:
            parts.append(f"GOAL: {self.goal}")

        try:
            from persistence import get_evolution_ledger_context
            ledger = get_evolution_ledger_context(6)
            if ledger:
                parts.append(ledger)
        except Exception:
            pass

        if self.chaos_level > 0.25:
            parts.append(
                f"\n[CHAOS — Level {self.chaos_level:.2f}] "
                f"If stuck, use spawn_agent or different approach instead of repeating."
            )

        return "\n\n".join(parts)

    def verifier_context(self, instruction: str = "") -> str:
        parts = [f"GOAL: {self.goal}"]
        if instruction:
            parts.append(f"INSTRUCTION GIVEN TO ACTOR: {instruction}")
        if self.done_claimed:
            parts.append(f"DONE CLAIMED: {self.done_evidence}")
        if self.problem:
            parts.append(f"PROBLEM REPORTED: {self.problem}")
        hist = self.format_history("ACTIONS TAKEN", limit=5)
        if hist:
            parts.append(hist)
        if self.actor_observe:
            parts.append(f"ACTOR OBSERVED: {self.actor_observe}")
        children_sum = self.children_summary()
        if children_sum:
            parts.append(children_sum)
        completed_sum = self.completed_summary()
        if completed_sum:
            parts.append(completed_sum)
        parts.append(f"SCREEN:\n{self.screen}")
        return "\n\n".join(parts)

    def build_reflector_context(self) -> str:
        parts = [
            f"GOAL: {self.goal}",
            f"ORIGINAL_GOAL: {self.original_goal}",
            f"MODE: {self.mode}",
            f"CYCLE: {self.cycle}",
            f"CONSECUTIVE_FAILURES: {self.consecutive_failures}",
            f"CHAOS_LEVEL: {self.chaos_level:.3f}",
            f"REPETITION_SCORE: {self.repetition_score:.3f}",
        ]

        try:
            from persistence import get_evolution_ledger_context
            ledger = get_evolution_ledger_context(5)
            if ledger:
                parts.append(ledger)
        except Exception:
            pass

        if self.problem:
            parts.append(f"PROBLEM: {self.problem}")

        damage = max(self.chaos_level, self.repetition_score * 0.8)
        if damage > 0.30:
            hist_limit = max(3, int(8 * (1.0 - min(damage, 0.9))))
            if random.random() < damage:
                hist_limit = max(2, hist_limit - random.randint(0, 2))
            hist = self.format_history("RECENT_HISTORY", limit=hist_limit)
        else:
            hist = self.format_history("RECENT_HISTORY", limit=5)
        if hist:
            parts.append(hist)

        if damage > 0.45:
            parts.append(
                "HIGH DAMAGE STATE: Generate meaningfully divergent rewrite families. "
                "Avoid repeating previous failed patterns."
            )
        if damage > 0.65:
            parts.append(
                "GOAL_REWRITE ENCOURAGED: If the current goal phrasing causes repeated problems, "
                "propose a version that preserves intent using different surface language."
            )

        children_sum = self.children_summary()
        if children_sum:
            parts.append(children_sum)
        completed_sum = self.completed_summary()
        if completed_sum:
            parts.append(completed_sum)

        prompts = {}
        for role in ("actor", "planner", "verifier"):
            p = BASE_DIR / "prompts" / f"{role}.txt"
            if p.exists():
                prompts[role] = p.read_text(encoding="utf-8")

        if prompts:
            parts.append("CURRENT_PROMPTS:\n" +
                         "\n\n".join(f"[{r}.txt]\n{c}" for r, c in prompts.items()))

        try:
            from lessons import Lessons
            existing = Lessons().get_context()
            if existing:
                parts.append(f"EXISTING_LESSONS:\n{existing}")
        except Exception:
            pass

        if self.chaos_level > 0.55 or self.repetition_score > 0.6:
            parts.append(
                "\n!!! HIGH DAMAGE / REPETITION: Focus on finding different approaches "
                "and rewrites that break the current pattern."
            )

        return "\n\n".join(parts)
