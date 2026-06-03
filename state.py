from __future__ import annotations
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from config import BASE_DIR, COMMS_DIR, SCREEN_LOCK_PATH

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
    screen_elements: dict[str, Any] = field(default_factory=lambda: dict[str, Any]())
    screen_valid: bool = False

    history: list[dict[str, Any]] = field(default_factory=lambda: list[dict[str, Any]]())
    console_log: list[str] = field(default_factory=lambda: list[str]())
    errors: list[str] = field(default_factory=lambda: list[str]())

    last_verb: str = ""
    last_success: bool = False
    last_observation: str = ""
    last_expect: str = ""

    done_claimed: bool = False
    done_evidence: str = ""
    problem: str = ""
    verifier_denied_last: bool = False

    consecutive_failures: int = 0
    recent_action_signatures: list[str] = field(default_factory=lambda: list[str]())
    blocked_signatures: dict[str, int] = field(default_factory=lambda: dict[str, int]())
    expectation_miss_streak: int = 0

    repetition_score: float = 0.0
    stagnation_score: float = 0.0
    screen_stagnation: int = 0
    recent_screen_hashes: list[str] = field(default_factory=lambda: list[str]())

    lorenz_x: float = 8.485
    lorenz_y: float = 8.485
    lorenz_z: float = 27.0
    attractor_energy: float = 1.0

    pid_output: float = 0.0
    pid_integral: float = 0.0
    pid_prev: float = 0.0
    pid_slope: float = 0.0

    jacobian_vector: list[float] = field(default_factory=lambda: list[float]())
    failed_step_index: int = 0

    actor_observe: str = ""
    actor_conclusion: str = ""
    actor_reason: str = ""
    last_plan_because: str = ""
    last_instruction: str = ""
    plan_steps: list[str] = field(default_factory=lambda: list[str]())
    plan_step_index: int = 0
    notes: list[str] = field(default_factory=lambda: list[str]())
    focused_window: str = ""

    children: dict[str, AgentHandle] = field(default_factory=lambda: dict[str, AgentHandle]())
    completed_subtasks: list[dict[str, Any]] = field(default_factory=lambda: list[dict[str, Any]]())
    pending_subtasks: list[dict[str, Any]] = field(default_factory=lambda: list[dict[str, Any]]())

    _screen_lock_held: bool = False

    def acquire_screen(self) -> bool:
        lock_data = {"agent_id": self.agent_id, "ts": time.time(), "pid": os.getpid()}
        if SCREEN_LOCK_PATH.exists():
            try:
                existing = json.loads(SCREEN_LOCK_PATH.read_text(encoding="utf-8"))
                if existing.get("agent_id") != self.agent_id:
                    age = time.time() - existing.get("ts", 0)
                    if age < 30:
                        return False
            except (json.JSONDecodeError, OSError):
                pass
        tmp = SCREEN_LOCK_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(lock_data), encoding="utf-8")
        os.replace(str(tmp), str(SCREEN_LOCK_PATH))
        self._screen_lock_held = True
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

    def poll_inbox(self) -> list[dict[str, Any]]:
        from persistence import poll_events
        raw_events = poll_events(self.agent_id)
        commands: list[dict[str, Any]] = []
        for evt in raw_events:
            verb = evt.get("verb", "")
            payload = evt.get("payload", "")
            if verb in ("goal_rewrite", "hint", "kill", "inject_lesson", "set_chaos"):
                commands.append({"type": verb, "payload": payload})
        return commands

    def poll_children(self) -> list[dict[str, str]]:
        from persistence import poll_events
        events: list[dict[str, str]] = []
        child_events = poll_events(self.agent_id)
        for evt in child_events:
            verb: str = evt.get("verb", "")
            source: str = evt.get("source", "")
            payload: dict[str, str] = evt.get("payload") or {}
            if verb == "child_done" and source in self.children:
                handle = self.children[source]
                handle.state = "done"
                handle.result = str(payload.get("result", ""))
                events.append({"agent_id": source, "state": "done", "result": handle.result, "error": ""})
                self.completed_subtasks.append({"agent_id": source, "goal": handle.goal, "result": handle.result})
            elif verb == "child_failed" and source in self.children:
                handle = self.children[source]
                handle.state = "failed"
                handle.error = str(payload.get("error", ""))
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
            "stagnation_score": self.stagnation_score,
            "screen_stagnation": self.screen_stagnation,
            "lorenz_x": self.lorenz_x,
            "lorenz_y": self.lorenz_y,
            "lorenz_z": self.lorenz_z,
            "attractor_energy": self.attractor_energy,
            "pid_output": self.pid_output,
            "pid_integral": self.pid_integral,
            "pid_prev": self.pid_prev,
            "pid_slope": self.pid_slope,
            "expectation_miss_streak": self.expectation_miss_streak,
            "history": self.history,
            "errors": self.errors,
            "screen_valid": self.screen_valid,
            "verifier_denied_last": self.verifier_denied_last,
            "plan_steps": self.plan_steps,
            "plan_step_index": self.plan_step_index,
            "failed_step_index": self.failed_step_index,
            "notes": self.notes,
            "last_plan_because": self.last_plan_because,
            "jacobian_vector": self.jacobian_vector,
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
        self.stagnation_score = snap.get("stagnation_score", 0.0)
        self.screen_stagnation = snap.get("screen_stagnation", 0)
        self.lorenz_x = snap.get("lorenz_x", 8.485)
        self.lorenz_y = snap.get("lorenz_y", 8.485)
        self.lorenz_z = snap.get("lorenz_z", 27.0)
        self.attractor_energy = snap.get("attractor_energy", 1.0)
        self.pid_output = snap.get("pid_output", 0.0)
        self.pid_integral = snap.get("pid_integral", 0.0)
        self.pid_prev = snap.get("pid_prev", 0.0)
        self.pid_slope = snap.get("pid_slope", 0.0)
        self.expectation_miss_streak = snap.get("expectation_miss_streak", 0)
        self.history = snap.get("history", [])
        self.errors = snap.get("errors", [])
        self.screen_valid = snap.get("screen_valid", False)
        self.verifier_denied_last = snap.get("verifier_denied_last", False)
        self.plan_steps = snap.get("plan_steps", [])
        self.plan_step_index = snap.get("plan_step_index", 0)
        self.failed_step_index = snap.get("failed_step_index", 0)
        self.notes = snap.get("notes", [])
        self.last_plan_because = snap.get("last_plan_because", "")
        self.jacobian_vector = snap.get("jacobian_vector", [])

    def update_signals(self, verb: str, target: str) -> None:
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

        self._compute_stagnation_score()
        self._step_lorenz()
        self._step_pid()
        self._step_jacobian()

        if self.stagnation_score > 0.5 and not self.last_success:
            self.blocked_signatures[signature] = self.iteration
        expired = [s for s, it in self.blocked_signatures.items()
                   if self.iteration - it > 5]
        for s in expired:
            del self.blocked_signatures[s]

    def _compute_stagnation_score(self) -> None:
        from config import (STAGNATION_WEIGHT_FAILURES, STAGNATION_WEIGHT_MISS,
                            STAGNATION_WEIGHT_REPETITION, STAGNATION_WEIGHT_SCREEN,
                            STAGNATION_NORMALIZER)
        raw = (self.consecutive_failures * STAGNATION_WEIGHT_FAILURES
               + self.expectation_miss_streak * STAGNATION_WEIGHT_MISS
               + self.repetition_score * STAGNATION_WEIGHT_REPETITION
               + self.screen_stagnation * STAGNATION_WEIGHT_SCREEN)
        self.stagnation_score = min(1.0, raw / STAGNATION_NORMALIZER)

    def _step_lorenz(self) -> None:
        from config import (PIPELINE_LORENZ, LORENZ_SIGMA, LORENZ_RHO, LORENZ_BETA,
                            LORENZ_DT, LORENZ_MAG_CAP,
                            LORENZ_RHO_SENSITIVITY, LORENZ_BETA_SENSITIVITY)
        if not PIPELINE_LORENZ:
            self.attractor_energy = 1.0
            return

        x, y, z = self.lorenz_x, self.lorenz_y, self.lorenz_z

        rho_eff = LORENZ_RHO + self.stagnation_score * LORENZ_RHO_SENSITIVITY * LORENZ_RHO
        beta_eff = max(0.5, LORENZ_BETA - self.repetition_score * LORENZ_BETA_SENSITIVITY)

        x = x + LORENZ_SIGMA * (y - x) * LORENZ_DT
        y = y + (x * (rho_eff - z) - y) * LORENZ_DT
        z = z + (x * y - beta_eff * z) * LORENZ_DT

        mag = (x * x + y * y + z * z) ** 0.5
        if mag > LORENZ_MAG_CAP:
            scale = LORENZ_MAG_CAP / mag
            x, y, z = x * scale, y * scale, z * scale
            mag = LORENZ_MAG_CAP

        self.lorenz_x, self.lorenz_y, self.lorenz_z = x, y, z

        eq_xy_sq = LORENZ_BETA * (LORENZ_RHO - 1.0)
        equilibrium_mag = (eq_xy_sq + eq_xy_sq + (LORENZ_RHO - 1.0) ** 2) ** 0.5
        self.attractor_energy = mag / max(equilibrium_mag, 1.0)

    def _step_pid(self) -> None:
        from config import (PIPELINE_PID, PID_KP, PID_KI, PID_KD,
                            PID_INTEGRAL_MAX, PID_DEAD_ZONE)
        if not PIPELINE_PID:
            self.pid_output = self.stagnation_score
            return

        error = self.stagnation_score
        self.pid_integral = min(self.pid_integral + error, PID_INTEGRAL_MAX)
        self.pid_slope = error - self.pid_prev
        d_term = PID_KD * self.pid_slope if abs(self.pid_slope) > PID_DEAD_ZONE else 0.0
        self.pid_output = max(0.0, PID_KP * error + PID_KI * self.pid_integral + d_term)
        self.pid_prev = error

    def _step_jacobian(self) -> None:
        from config import PIPELINE_JACOBIAN
        if not PIPELINE_JACOBIAN or not self.plan_steps:
            self.jacobian_vector = []
            return
        n = len(self.plan_steps)
        self.jacobian_vector = [0.0] * n
        for i in range(n):
            position_weight = (n - i) / n
            if i < self.plan_step_index:
                self.jacobian_vector[i] = 0.0
            elif i == self.plan_step_index:
                self.jacobian_vector[i] = (position_weight
                                           * self.stagnation_score
                                           * self.attractor_energy
                                           * (1.0 + self.consecutive_failures * 0.5))
            else:
                self.jacobian_vector[i] = position_weight * self.stagnation_score * self.attractor_energy * 0.3

    def update_screen_stagnation(self, screen_hash: str) -> None:
        if screen_hash in self.recent_screen_hashes[-4:]:
            self.screen_stagnation += 1
        else:
            self.screen_stagnation = 0
        self.recent_screen_hashes.append(screen_hash)
        self.recent_screen_hashes = self.recent_screen_hashes[-8:]

    def reset_pid_integral(self) -> None:
        self.pid_integral = 0.0

    def jacobian_impact(self, step_index: int) -> float:
        if not self.jacobian_vector:
            return self.stagnation_score
        if step_index < len(self.jacobian_vector):
            return self.jacobian_vector[step_index]
        return self.stagnation_score

    def should_replan(self, step_index: int) -> bool:
        impact = self.jacobian_impact(step_index)
        threshold = 1.0 / (1.0 + self.pid_output)
        return impact > threshold

    def jacobian_dominant_step(self) -> int:
        if not self.jacobian_vector:
            return self.plan_step_index
        return max(range(len(self.jacobian_vector)), key=lambda i: self.jacobian_vector[i])

    def detect_repetition_in_history(self) -> bool:
        if len(self.history) < 3:
            return False
        recent = self.history[-4:]
        sigs = [f"{h['verb']}:{h['obs']}" for h in recent if h['success']]
        return len(sigs) >= 3 and len(set(sigs)) == 1

    def stagnation_blocks_action(self, verb: str, target: str) -> bool:
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

        target_str = str(args.get("target", "") or args.get("selector", "") or args.get("path", "") or args.get("command", "") or args.get("goal", "") or args.get("window_title", ""))
        self.update_signals(verb, target_str)

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

    def full_context(self, role: str, instruction: str = "") -> str:
        parts: list[str] = []
        parts.append(f"ROLE: {role}")
        parts.append(f"GOAL: {self.goal}")
        if self.original_goal and self.original_goal != self.goal:
            parts.append(f"ORIGINAL_GOAL: {self.original_goal}")
        parts.append(f"ITERATION: {self.iteration}")
        parts.append(f"MODE: {self.mode}")
        parts.append(f"AGENT_ID: {self.agent_id}")
        parts.append(f"HOME: {BASE_DIR}")
        if instruction:
            parts.append(f"INSTRUCTION_TO_ACTOR: {instruction}")
        if self.last_instruction:
            parts.append(f"LAST_INSTRUCTION_ISSUED: {self.last_instruction}")
        if self.focused_window:
            parts.append(f"FOCUSED_WINDOW: {self.focused_window}")
        if self.plan_steps:
            lines = ["CHECKLIST:"]
            for i, step in enumerate(self.plan_steps):
                if i < self.plan_step_index:
                    lines.append(f"  [{i}] done  {step}")
                elif i == self.plan_step_index:
                    lines.append(f"  [{i}] >>>   {step}")
                else:
                    lines.append(f"  [{i}]       {step}")
            parts.append("\n".join(lines))
        if self.notes:
            parts.append("NOTES:\n" + "\n".join(f"  - {n}" for n in self.notes))
        if self.last_plan_because:
            parts.append(f"PLANNER_REASONING: {self.last_plan_because}")
        if self.actor_observe:
            parts.append(f"ACTOR_OBSERVE: {self.actor_observe}")
        if self.actor_conclusion:
            parts.append(f"ACTOR_CONCLUSION: {self.actor_conclusion}")
        if self.actor_reason:
            parts.append(f"ACTOR_REASON: {self.actor_reason}")
        if self.last_verb:
            parts.append(f"LAST_ACTION: {self.last_verb} {'succeeded' if self.last_success else 'FAILED'}")
            if self.last_observation:
                parts.append(f"LAST_RESULT: {self.last_observation}")
        if self.last_expect:
            parts.append(f"LAST_EXPECT: {self.last_expect}")
        if self.done_claimed:
            parts.append(f"DONE_CLAIMED: {self.done_evidence}")
        if self.problem:
            parts.append(f"PROBLEM: {self.problem}")
        if self.verifier_denied_last:
            parts.append("VERIFIER_DENIED_LAST: true")
        parts.append(f"CONSECUTIVE_FAILURES: {self.consecutive_failures}")
        parts.append(f"STAGNATION_SCORE: {self.stagnation_score:.3f}")
        parts.append(f"ATTRACTOR_ENERGY: {self.attractor_energy:.3f}")
        parts.append(f"PID: output={self.pid_output:.3f} integral={self.pid_integral:.3f} slope={self.pid_slope:.3f}")
        parts.append(f"REPETITION_SCORE: {self.repetition_score:.3f}")
        parts.append(f"SCREEN_STAGNATION: {self.screen_stagnation}")
        parts.append(f"EXPECTATION_MISS_STREAK: {self.expectation_miss_streak}")
        parts.append(f"LORENZ: x={self.lorenz_x:.3f} y={self.lorenz_y:.3f} z={self.lorenz_z:.3f}")
        if self.jacobian_vector:
            parts.append(f"JACOBIAN_VECTOR: {[round(v, 3) for v in self.jacobian_vector]}")
        parts.append(f"FAILED_STEP_INDEX: {self.failed_step_index}")
        hist = self.format_history("FULL_HISTORY", full=True)
        if hist:
            parts.append(hist)
        if self.errors:
            parts.append("ERRORS:\n" + "\n".join(f"  {e}" for e in self.errors))
        if self.screen:
            parts.append(f"SCREEN_ELEMENTS:\n{self.screen}")
        children_sum = self.children_summary()
        if children_sum:
            parts.append(children_sum)
        completed_sum = self.completed_summary()
        if completed_sum:
            parts.append(completed_sum)
        if self.pending_subtasks:
            parts.append("PENDING_SUBTASKS: " + json.dumps(self.pending_subtasks, ensure_ascii=False))
        try:
            from lessons import Lessons
            lesson_text = Lessons().get_context()
            if lesson_text:
                parts.append(lesson_text)
        except Exception:
            pass
        try:
            from persistence import get_evolution_ledger_context
            ledger = get_evolution_ledger_context()
            if ledger:
                parts.append(ledger)
        except Exception:
            pass
        if role == "reflector":
            prompts: dict[str, str] = {}
            for r in ("actor", "planner", "verifier"):
                p = BASE_DIR / "prompts" / f"{r}.txt"
                if p.exists():
                    prompts[r] = p.read_text(encoding="utf-8")
            if prompts:
                parts.append("CURRENT_PROMPTS:\n" + "\n\n".join(f"[{r}.txt]\n{c}" for r, c in prompts.items()))
        return "\n\n".join(parts)

    def planner_context(self) -> str:
        parts = [f"ITERATION: {self.iteration}"]
        parts.append(f"MODE: {self.mode}")
        parts.append(f"HOME: {BASE_DIR}")
        if self.focused_window:
            parts.append(f"FOCUSED WINDOW: {self.focused_window}")

        if self.plan_steps:
            lines = ["CHECKLIST:"]
            for i, step in enumerate(self.plan_steps):
                if i < self.plan_step_index:
                    lines.append(f"  [{i}] done  {step}")
                elif i == self.plan_step_index:
                    lines.append(f"  [{i}] >>>   {step}")
                else:
                    lines.append(f"  [{i}]       {step}")
            parts.append("\n".join(lines))

        if self.last_plan_because:
            parts.append(f"PREVIOUS PLAN REASONING: {self.last_plan_because}")

        if self.notes:
            parts.append("NOTES:\n" + "\n".join(f"  - {n}" for n in self.notes))

        sitrep: list[str] = []
        if self.actor_observe:
            sitrep.append(f"ACTOR SEES: {self.actor_observe}")
        if self.actor_conclusion:
            sitrep.append(f"ACTOR CONCLUSION: {self.actor_conclusion}")
        if self.last_verb:
            sitrep.append(f"LAST ACTION: {self.last_verb} {'succeeded' if self.last_success else 'FAILED'}")
            if self.last_observation:
                sitrep.append(f"RESULT: {self.last_observation}")
        if self.last_expect and not self.last_success:
            sitrep.append(f"EXPECTED (unmet): {self.last_expect}")
        if sitrep:
            parts.append("\n".join(sitrep))

        try:
            from lessons import Lessons
            lesson_text = Lessons().get_context()
            if lesson_text:
                parts.append(lesson_text)
        except Exception:
            pass

        if self.errors:
            parts.append("ERRORS THIS RUN:\n" + "\n".join(f"  {e}" for e in self.errors[-5:]))

        if self.detect_repetition_in_history():
            parts.append(
                "!!! WARNING: You have repeated the same action multiple times. "
                "If the goal's core action already succeeded, set mode=done NOW. "
                "If not done, you MUST try a DIFFERENT action."
            )

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

        hist = self.format_history()
        if hist:
            parts.append(hist)

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

        if self.stagnation_score > 0.25:
            parts.append(
                f"\n[STAGNATION {self.stagnation_score:.2f} | Repetition {self.repetition_score:.2f}] "
                f"Prefer parallel decomposition or spawn_agent. Avoid repeating recent failing actions."
            )

        return "\n\n".join(parts)

    def actor_context(self, instruction: str) -> str:
        parts: list[str] = []
        if instruction:
            parts.append(f"INSTRUCTION: {instruction}")

        if self.plan_steps:
            current = self.plan_steps[self.plan_step_index] if self.plan_step_index < len(self.plan_steps) else ""
            parts.append(f"CURRENT STEP: {current}")

        if self.problem:
            parts.append(f"PROBLEM: {self.problem}")
        if self.last_verb:
            parts.append(f"LAST: {self.last_verb} {'succeeded' if self.last_success else 'FAILED'}")
            if self.last_observation:
                parts.append(f"RESULT: {self.last_observation}")
        if self.last_expect and not self.last_success:
            parts.append(f"EXPECTED FROM LAST ITERATION: {self.last_expect}")
        hist = self.format_history()
        if hist:
            parts.append(hist)

        try:
            from lessons import Lessons
            lesson_text = Lessons().get_context()
            if lesson_text:
                parts.append(lesson_text)
        except Exception:
            pass

        parts.append(f"AVAILABLE ELEMENTS (match instruction by role/name, use numeric ID as target):\n{self.screen}")

        if self.original_goal and self.original_goal != self.goal:
            parts.append(f"ORIGINAL GOAL: {self.original_goal}")
            parts.append(f"CURRENT GOAL (adapted): {self.goal}")
        else:
            parts.append(f"GOAL: {self.goal}")

        if self.stagnation_score > 0.25:
            parts.append(
                f"\n[STAGNATION {self.stagnation_score:.2f}] "
                f"If stuck, use spawn_agent or different approach instead of repeating."
            )

        return "\n\n".join(parts)

    def verifier_context(self, instruction: str = "") -> str:
        parts = [f"GOAL: {self.goal}"]
        if self.plan_steps:
            done_count = self.plan_step_index
            total_count = len(self.plan_steps)
            parts.append(f"COMPLETION STATUS: {done_count}/{total_count} steps done. {'ALL COMPLETE.' if done_count >= total_count else 'INCOMPLETE — cannot confirm done until all steps are marked done.'}")
            lines = ["CHECKLIST:"]
            for i, step in enumerate(self.plan_steps):
                if i < self.plan_step_index:
                    lines.append(f"  [{i}] done  {step}")
                elif i == self.plan_step_index:
                    lines.append(f"  [{i}] >>>   {step}")
                else:
                    lines.append(f"  [{i}]       {step}")
            parts.append("\n".join(lines))
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
            f"STAGNATION_SCORE: {self.stagnation_score:.3f}",
            f"ATTRACTOR_ENERGY: {self.attractor_energy:.3f}",
            f"PID: output={self.pid_output:.3f} slope={self.pid_slope:.3f} integral={self.pid_integral:.3f} screen_stag={self.screen_stagnation}",
            f"REPETITION_SCORE: {self.repetition_score:.3f}",
        ]

        if self.plan_steps:
            lines = ["CHECKLIST:"]
            for i, step in enumerate(self.plan_steps):
                if i < self.plan_step_index:
                    lines.append(f"  [{i}] done  {step}")
                elif i == self.plan_step_index:
                    lines.append(f"  [{i}] >>>   {step}")
                else:
                    lines.append(f"  [{i}]       {step}")
            parts.append("\n".join(lines))

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

        hist = self.format_history("RECENT_HISTORY", full=True)
        if hist:
            parts.append(hist)

        damage = max(self.stagnation_score, self.repetition_score * 0.8)
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

        if self.stagnation_score > 0.55 or self.repetition_score > 0.6:
            parts.append(
                "\n!!! HIGH STAGNATION / REPETITION: Focus on finding different approaches "
                "and rewrites that break the current pattern."
            )

        return "\n\n".join(parts)
