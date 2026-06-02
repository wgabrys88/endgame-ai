from __future__ import annotations
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from config import BASE_DIR, COMMS_DIR, SCREEN_LOCK_PATH, trace

COMMS_DIR.mkdir(parents=True, exist_ok=True)


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
    iteration: int = 0
    mode: str = "direct"
    agent_id: str = "main"

    screen: str = ""
    screen_hash: str = ""
    screen_elements: dict[str, Any] = field(default_factory=dict)
    screen_valid: bool = False

    history: list[dict[str, Any]] = field(default_factory=list)
    console_log: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    last_verb: str = ""
    last_success: bool = False
    last_observation: str = ""
    last_expect: str = ""

    done_claimed: bool = False
    done_evidence: str = ""
    problem: str = ""
    verifier_denied_last: bool = False

    consecutive_failures: int = 0

    recent_action_signatures: list[str] = field(default_factory=list)
    repetition_score: float = 0.0
    chaos_level: float = 0.0
    lorenz_x: float = 0.1
    lorenz_y: float = 1.0
    lorenz_z: float = 1.0
    blocked_signatures: dict[str, int] = field(default_factory=dict)
    expectation_miss_streak: int = 0

    actor_observe: str = ""

    children: dict[str, AgentHandle] = field(default_factory=dict)
    completed_subtasks: list[dict[str, Any]] = field(default_factory=list)
    pending_subtasks: list[dict[str, Any]] = field(default_factory=list)

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

    def poll_inbox(self) -> list[dict[str, Any]]:
        from persistence import poll_events
        raw_events = poll_events(self.agent_id)
        commands: list[dict[str, Any]] = []
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
        events: list[dict[str, Any]] = []
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

    def format_history(self, label: str = "RECENT", full: bool = False) -> str:
        from config import CONTEXT_HISTORY_LIMIT
        recent = self.history if full else self.history[-CONTEXT_HISTORY_LIMIT:]
        if not recent:
            return ""
        lines = [label + ":"]
        for h in recent:
            lines.append(f"  {h['verb']} -> {'ok' if h['success'] else 'FAIL'}: {h['obs']}")
        return "\n".join(lines)

    def rewrite_goal(self, new_goal: str) -> None:
        if not new_goal:
            return
        if not self.original_goal:
            self.original_goal = self.goal
        self.goal = new_goal.strip()

    def get_persistable_snapshot(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "original_goal": self.original_goal,
            "iteration": self.iteration,
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
            "history": self.history,
            "errors": self.errors,
            "screen_valid": self.screen_valid,
            "verifier_denied_last": self.verifier_denied_last,
        }

    def load_from_snapshot(self, snap: dict[str, Any]) -> None:
        self.goal = snap.get("goal", self.goal)
        self.original_goal = snap.get("original_goal", self.original_goal)
        self.iteration = snap.get("iteration", 0)
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
        self.errors = snap.get("errors", [])
        self.screen_valid = snap.get("screen_valid", False)
        self.verifier_denied_last = snap.get("verifier_denied_last", False)

    def update_chaos_and_repetition(self, verb: str, target: str) -> None:
        from config import MAX_SIGNATURES
        signature = f"{verb}:{target}"
        self.recent_action_signatures.append(signature)
        if len(self.recent_action_signatures) > MAX_SIGNATURES:
            self.recent_action_signatures = self.recent_action_signatures[-MAX_SIGNATURES:]

        window = self.recent_action_signatures[-12:]
        if len(window) >= 4:
            unique = len(set(window))
            self.repetition_score = 1.0 - (unique / len(window))
        else:
            self.repetition_score = 0.0

        x, y, z = self.lorenz_x, self.lorenz_y, self.lorenz_z
        sigma, rho, beta = 10.0, 28.0, 8.0 / 3.0
        dt = 0.02

        sigs = self.recent_action_signatures
        action_diversity = len(set(sigs[-6:])) / max(len(sigs[-6:]), 1)
        progress = 1.0 if (self.last_success and signature not in sigs[:-1]) else 0.0
        stagnation = (self.consecutive_failures
                      + (1.0 - action_diversity) * 3.0
                      + self.expectation_miss_streak * 2.5
                      + self.repetition_score * 8.0)

        x = x + sigma * (progress - x) * dt
        y = y + (x * (rho - stagnation) - y) * dt
        z = z + (x * y - beta * z) * dt

        mag = (x * x + y * y + z * z) ** 0.5
        if mag > 50.0:
            scale = 50.0 / mag
            x, y, z = x * scale, y * scale, z * scale

        self.lorenz_x, self.lorenz_y, self.lorenz_z = x, y, z
        self.chaos_level = min(1.0, (abs(z) + self.consecutive_failures * 5.0 + self.expectation_miss_streak * 4.0 + self.repetition_score * 12.0) / rho)

        if self.chaos_level > 0.5 and not self.last_success:
            self.blocked_signatures[signature] = self.iteration
        expired = [s for s, it in self.blocked_signatures.items()
                   if self.iteration - it > 5]
        for s in expired:
            del self.blocked_signatures[s]

    def chaos_rejects_done(self) -> bool:
        if self.repetition_score > 0.4:
            return False
        return self.chaos_level > 0.3 or self.iteration < 3 or self.expectation_miss_streak > 0

    def detect_repetition_in_history(self) -> bool:
        if len(self.history) < 3:
            return False
        recent = self.history[-4:]
        sigs = [f"{h['verb']}:{h['obs']}" for h in recent if h['success']]
        return len(sigs) >= 3 and len(set(sigs)) == 1

    def chaos_forces_parallel(self) -> bool:
        return self.chaos_level > 0.7

    def chaos_blocks_action(self, verb: str, target: str) -> bool:
        return f"{verb}:{target}" in self.blocked_signatures

    def record_action(self, verb: str, args: dict[str, Any], success: bool, observation: str) -> None:
        self.last_verb = verb
        self.last_success = success
        self.last_observation = observation

        self.history.append({
            "verb": verb,
            "args": args,
            "success": success,
            "obs": observation if observation else ""
        })
        from config import MAX_HISTORY_ENTRIES
        if len(self.history) > MAX_HISTORY_ENTRIES:
            self.history = self.history[-MAX_HISTORY_ENTRIES:]

        target = str(args.get("target", "") or args.get("selector", "") or args.get("path", "") or args.get("command", "") or args.get("goal", "") or args.get("window_title", ""))
        self.update_chaos_and_repetition(verb, target)

    def record_failure(self) -> None:
        self.consecutive_failures += 1

    def record_success(self) -> None:
        self.consecutive_failures = 0

    def record_screen(self, text: str, hash_val: str, elements: dict[str, Any]) -> None:
        self.screen = text
        self.screen_hash = hash_val
        self.screen_elements = elements

    def record_error(self, error_type: str, detail: str) -> None:
        entry = f"[{error_type}] {detail}"
        self.errors.append(entry)
        if not self.problem:
            self.problem = entry

    def clear_signals(self) -> None:
        self.done_claimed = False
        self.done_evidence = ""
        self.problem = ""

    def planner_context(self) -> str:
        parts = [f"ITERATION: {self.iteration}"]
        parts.append(f"MODE: {self.mode}")
        parts.append(f"HOME: {BASE_DIR}")
        parts.append(f"SCREEN_VALID: {self.screen_valid}")

        if self.errors:
            parts.append("ERRORS THIS RUN:\n" + "\n".join(f"  {e}" for e in self.errors[-5:]))

        if self.detect_repetition_in_history():
            parts.append(
                "!!! WARNING: You have repeated the same action multiple times. "
                "If the goal's core action already succeeded, set mode=done NOW. "
                "If not done, you MUST try a DIFFERENT action."
            )

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
            ledger = get_evolution_ledger_context()
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
        parts: list[str] = []
        if instruction:
            parts.append(f"INSTRUCTION: {instruction}")
        if self.problem:
            parts.append(f"PROBLEM: {self.problem}")
        if self.last_verb:
            parts.append(f"LAST: {self.last_verb} success={self.last_success}")
            if self.last_observation:
                parts.append(f"RESULT: {self.last_observation}")
        if self.last_expect and not self.last_success:
            parts.append(f"EXPECTED FROM LAST ITERATION: {self.last_expect}")
        hist = self.format_history()
        if hist:
            parts.append(hist)
        parts.append(f"AVAILABLE ELEMENTS (find the element matching the instruction by role/name, then use its numeric ID as target):\n{self.screen}")
        if self.original_goal and self.original_goal != self.goal:
            parts.append(f"ORIGINAL GOAL: {self.original_goal}")
            parts.append(f"CURRENT GOAL (adapted): {self.goal}")
        else:
            parts.append(f"GOAL: {self.goal}")

        try:
            from persistence import get_evolution_ledger_context
            ledger = get_evolution_ledger_context()
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
        hist = self.format_history("ACTIONS TAKEN", full=True)
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
            f"ITERATION: {self.iteration}",
            f"CONSECUTIVE_FAILURES: {self.consecutive_failures}",
            f"CHAOS_LEVEL: {self.chaos_level:.3f}",
            f"REPETITION_SCORE: {self.repetition_score:.3f}",
            f"SCREEN_VALID: {self.screen_valid}",
        ]

        if self.errors:
            parts.append("ERRORS:\n" + "\n".join(f"  {e}" for e in self.errors[-10:]))

        if self.console_log:
            parts.append("CONSOLE (last 20 lines):\n" + "\n".join(self.console_log[-20:]))

        try:
            from persistence import get_evolution_ledger_context
            ledger = get_evolution_ledger_context()
            if ledger:
                parts.append(ledger)
        except Exception:
            pass

        if self.problem:
            parts.append(f"PROBLEM: {self.problem}")

        damage = max(self.chaos_level, self.repetition_score * 0.8)
        hist = self.format_history("RECENT_HISTORY", full=True)
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

        prompts: dict[str, str] = {}
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
