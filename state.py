from __future__ import annotations
from config import ZERO_INT, ONE_INT, TWO_INT, FLOAT_ZERO, FLOAT_ONE
import json
import os
import time
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from config import (
    BASE_DIR, COMMS_DIR, SCREEN_LOCK_PATH, SCREEN_SNAPSHOT_PATH,
    SCREEN_SNAPSHOT_MAX_AGE, SCREEN_LOCK_STALE_SECONDS, LORENZ_INITIAL_X,
    LORENZ_INITIAL_Y, LORENZ_INITIAL_Z, REPETITION_WINDOW, REPETITION_MIN_WINDOW,
    STAGNATION_BLOCK_THRESHOLD, SIGNATURE_BLOCK_EXPIRY_ITERATIONS,
    LORENZ_EQUILIBRIUM_OFFSET, LORENZ_MAG_EXPONENT, JACOBIAN_FAILURE_GAIN,
    LORENZ_BETA_MIN, JACOBIAN_FUTURE_STEP_GAIN, SCREEN_STAGNATION_LOOKBACK,
    SCREEN_HASH_HISTORY_LIMIT, HISTORY_REPETITION_LOOKBACK,
    HISTORY_REPETITION_MIN_MATCHES, CONTEXT_OBSERVATION_EVIDENCE_LINES,
)

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
    iteration: int = ZERO_INT
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

    consecutive_failures: int = ZERO_INT
    recent_action_signatures: list[str] = field(default_factory=lambda: list[str]())
    blocked_signatures: dict[str, int] = field(default_factory=lambda: dict[str, int]())
    expectation_miss_streak: int = ZERO_INT

    repetition_score: float = FLOAT_ZERO
    stagnation_score: float = FLOAT_ZERO
    screen_stagnation: int = ZERO_INT
    recent_screen_hashes: list[str] = field(default_factory=lambda: list[str]())

    lorenz_x: float = LORENZ_INITIAL_X
    lorenz_y: float = LORENZ_INITIAL_Y
    lorenz_z: float = LORENZ_INITIAL_Z
    attractor_energy: float = FLOAT_ONE

    pid_output: float = FLOAT_ZERO
    pid_integral: float = FLOAT_ZERO
    pid_prev: float = FLOAT_ZERO
    pid_slope: float = FLOAT_ZERO

    jacobian_vector: list[float] = field(default_factory=lambda: list[float]())
    failed_step_index: int = ZERO_INT

    actor_observe: str = ""
    actor_conclusion: str = ""
    actor_reason: str = ""
    last_plan_because: str = ""
    last_instruction: str = ""
    plan_steps: list[str] = field(default_factory=lambda: list[str]())
    plan_step_index: int = ZERO_INT
    notes: list[str] = field(default_factory=lambda: list[str]())
    focused_window: str = ""

    children: dict[str, AgentHandle] = field(default_factory=lambda: dict[str, AgentHandle]())
    completed_subtasks: list[dict[str, Any]] = field(default_factory=lambda: list[dict[str, Any]]())
    pending_subtasks: list[dict[str, Any]] = field(default_factory=lambda: list[dict[str, Any]]())

    _screen_lock_held: bool = False

    def build_context(self, role: str, instruction: str = "") -> str:
        from config import CONTEXT_POLICY
        fields = CONTEXT_POLICY.get(role, [])
        parts: list[str] = []
        for f in fields:
            text = _render_field(self, f, instruction)
            if text:
                parts.append(text)
        return "\n\n".join(parts)

    def format_history(self, label: str = "RECENT", full: bool = False) -> str:
        from config import CONTEXT_HISTORY_LIMIT
        recent = self.history if full else self.history[-CONTEXT_HISTORY_LIMIT:]
        if not recent:
            return ""
        lines = [label + ":"]
        for h in recent:
            lines.append(f"  {h['verb']} -> {'ok' if h['success'] else 'FAIL'}: {h['obs']}")
        return "\n".join(lines)

    def acquire_screen(self) -> bool:
        lock_data = {"agent_id": self.agent_id, "ts": time.time(), "pid": os.getpid()}
        if SCREEN_LOCK_PATH.exists():
            try:
                existing = json.loads(SCREEN_LOCK_PATH.read_text(encoding="utf-8"))
                if existing.get("agent_id") != self.agent_id:
                    age = time.time() - existing.get("ts", ZERO_INT)
                    if age < SCREEN_LOCK_STALE_SECONDS:
                        return False
            except (json.JSONDecodeError, OSError):
                pass
        tmp = SCREEN_LOCK_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(lock_data), encoding="utf-8")
        os.replace(str(tmp), str(SCREEN_LOCK_PATH))
        self._screen_lock_held = True
        return True

    def publish_shared_screen(self) -> None:
        if not self.screen or not self.screen_valid:
            return
        payload = {
            "agent_id": self.agent_id,
            "ts": time.time(),
            "context_text": self.screen,
            "content_hash": self.screen_hash,
            "focused_window": self.focused_window,
        }
        tmp = SCREEN_SNAPSHOT_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(str(tmp), str(SCREEN_SNAPSHOT_PATH))

    def load_shared_screen(self) -> tuple[str, str, str] | None:
        if not SCREEN_SNAPSHOT_PATH.exists():
            return None
        try:
            data = json.loads(SCREEN_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        age = time.time() - float(data.get("ts", ZERO_INT))
        if age > SCREEN_SNAPSHOT_MAX_AGE:
            return None
        text = str(data.get("context_text", ""))
        if not text:
            return None
        return text, str(data.get("content_hash", "shared")), str(data.get("focused_window", ""))

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
        raw_events = poll_events(self.agent_id, {"goal_rewrite", "hint", "kill", "inject_lesson", "set_chaos"})
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
        child_events = poll_events(self.agent_id, {"child_done", "child_failed"})
        for evt in child_events:
            verb: str = evt.get("verb", "")
            source: str = evt.get("source", "")
            raw_payload = evt.get("payload")
            payload: dict[str, str] = {str(k): str(v) for k, v in cast(dict[Any, Any], raw_payload).items()} if isinstance(raw_payload, dict) else {}
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
        return sum(ONE_INT for h in self.children.values() if h.state == "running")

    def terminate_running_children(self) -> list[dict[str, Any]]:
        terminated: list[dict[str, Any]] = []
        for agent_id, handle in self.children.items():
            if handle.state != "running" or handle.pid <= ZERO_INT:
                continue
            from win32 import terminate_process
            if terminate_process(handle.pid):
                handle.state = "failed"
                handle.error = "terminated_with_parent"
                terminated.append({"agent_id": agent_id, "pid": handle.pid, "goal": handle.goal})
        return terminated

    def rewrite_goal(self, new_goal: str) -> None:
        if not new_goal:
            return
        from goal_wrapper import extract_human_goal, wrap_goal
        if not self.original_goal:
            self.original_goal = extract_human_goal(self.goal)
        self.goal = wrap_goal(new_goal)

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
        self.iteration = snap.get("iteration", ZERO_INT)
        self.mode = snap.get("mode", "direct")
        self.agent_id = snap.get("agent_id", "main")
        self.consecutive_failures = snap.get("consecutive_failures", ZERO_INT)
        self.last_verb = snap.get("last_verb", "")
        self.last_success = snap.get("last_success", False)
        self.problem = snap.get("problem", "")
        self.repetition_score = snap.get("repetition_score", FLOAT_ZERO)
        self.stagnation_score = snap.get("stagnation_score", FLOAT_ZERO)
        self.screen_stagnation = snap.get("screen_stagnation", ZERO_INT)
        self.lorenz_x = snap.get("lorenz_x", LORENZ_INITIAL_X)
        self.lorenz_y = snap.get("lorenz_y", LORENZ_INITIAL_Y)
        self.lorenz_z = snap.get("lorenz_z", LORENZ_INITIAL_Z)
        self.attractor_energy = snap.get("attractor_energy", FLOAT_ONE)
        self.pid_output = snap.get("pid_output", FLOAT_ZERO)
        self.pid_integral = snap.get("pid_integral", FLOAT_ZERO)
        self.pid_prev = snap.get("pid_prev", FLOAT_ZERO)
        self.pid_slope = snap.get("pid_slope", FLOAT_ZERO)
        self.expectation_miss_streak = snap.get("expectation_miss_streak", ZERO_INT)
        self.history = snap.get("history", [])
        self.errors = snap.get("errors", [])
        self.screen_valid = snap.get("screen_valid", False)
        self.verifier_denied_last = snap.get("verifier_denied_last", False)
        self.plan_steps = snap.get("plan_steps", [])
        self.plan_step_index = snap.get("plan_step_index", ZERO_INT)
        self.failed_step_index = snap.get("failed_step_index", ZERO_INT)
        self.notes = snap.get("notes", [])
        self.last_plan_because = snap.get("last_plan_because", "")
        self.jacobian_vector = snap.get("jacobian_vector", [])

    def update_signals(self, verb: str, target: str) -> None:
        from config import MAX_SIGNATURES
        signature = f"{verb}:{target}"
        self.recent_action_signatures.append(signature)
        if len(self.recent_action_signatures) > MAX_SIGNATURES:
            self.recent_action_signatures = self.recent_action_signatures[-MAX_SIGNATURES:]

        window = self.recent_action_signatures[-REPETITION_WINDOW:]
        if len(window) >= REPETITION_MIN_WINDOW:
            unique = len(set(window))
            self.repetition_score = FLOAT_ONE - (unique / len(window))
        else:
            self.repetition_score = FLOAT_ZERO

        self._compute_stagnation_score()
        self._step_lorenz()
        self._step_pid()
        self._step_jacobian()

        if self.stagnation_score > STAGNATION_BLOCK_THRESHOLD and not self.last_success:
            self.blocked_signatures[signature] = self.iteration
        expired = [s for s, it in self.blocked_signatures.items()
                   if self.iteration - it > SIGNATURE_BLOCK_EXPIRY_ITERATIONS]
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
        self.stagnation_score = min(FLOAT_ONE, raw / STAGNATION_NORMALIZER)

    def _step_lorenz(self) -> None:
        from config import (PIPELINE_LORENZ, LORENZ_SIGMA, LORENZ_RHO, LORENZ_BETA,
                            LORENZ_DT, LORENZ_MAG_CAP,
                            LORENZ_RHO_SENSITIVITY, LORENZ_BETA_SENSITIVITY)
        if not PIPELINE_LORENZ:
            self.attractor_energy = FLOAT_ONE
            return

        x, y, z = self.lorenz_x, self.lorenz_y, self.lorenz_z

        rho_eff = LORENZ_RHO + self.stagnation_score * LORENZ_RHO_SENSITIVITY * LORENZ_RHO
        beta_eff = max(LORENZ_BETA_MIN, LORENZ_BETA - self.repetition_score * LORENZ_BETA_SENSITIVITY)

        x = x + LORENZ_SIGMA * (y - x) * LORENZ_DT
        y = y + (x * (rho_eff - z) - y) * LORENZ_DT
        z = z + (x * y - beta_eff * z) * LORENZ_DT

        mag = (x * x + y * y + z * z) ** LORENZ_MAG_EXPONENT
        if mag > LORENZ_MAG_CAP:
            scale = LORENZ_MAG_CAP / mag
            x, y, z = x * scale, y * scale, z * scale
            mag = LORENZ_MAG_CAP

        self.lorenz_x, self.lorenz_y, self.lorenz_z = x, y, z

        eq_xy_sq = LORENZ_BETA * (LORENZ_RHO - LORENZ_EQUILIBRIUM_OFFSET)
        equilibrium_mag = (eq_xy_sq + eq_xy_sq + (LORENZ_RHO - LORENZ_EQUILIBRIUM_OFFSET) ** TWO_INT) ** LORENZ_MAG_EXPONENT
        self.attractor_energy = mag / max(equilibrium_mag, LORENZ_EQUILIBRIUM_OFFSET)

    def _step_pid(self) -> None:
        from config import (PIPELINE_PID, PID_KP, PID_KI, PID_KD,
                            PID_INTEGRAL_MAX, PID_DEAD_ZONE)
        if not PIPELINE_PID:
            self.pid_output = self.stagnation_score
            return

        error = self.stagnation_score
        self.pid_integral = min(self.pid_integral + error, PID_INTEGRAL_MAX)
        self.pid_slope = error - self.pid_prev
        d_term = PID_KD * self.pid_slope if abs(self.pid_slope) > PID_DEAD_ZONE else FLOAT_ZERO
        self.pid_output = max(FLOAT_ZERO, PID_KP * error + PID_KI * self.pid_integral + d_term)
        self.pid_prev = error

    def _step_jacobian(self) -> None:
        from config import PIPELINE_JACOBIAN
        if not PIPELINE_JACOBIAN or not self.plan_steps:
            self.jacobian_vector = []
            return
        n = len(self.plan_steps)
        self.jacobian_vector = [FLOAT_ZERO] * n
        for i in range(n):
            position_weight = (n - i) / n
            if i < self.plan_step_index:
                self.jacobian_vector[i] = FLOAT_ZERO
            elif i == self.plan_step_index:
                self.jacobian_vector[i] = (position_weight
                                           * self.stagnation_score
                                           * self.attractor_energy
                                           * (LORENZ_EQUILIBRIUM_OFFSET + self.consecutive_failures * JACOBIAN_FAILURE_GAIN))
            else:
                self.jacobian_vector[i] = position_weight * self.stagnation_score * self.attractor_energy * JACOBIAN_FUTURE_STEP_GAIN

    def update_screen_stagnation(self, screen_hash: str) -> None:
        if screen_hash in self.recent_screen_hashes[-SCREEN_STAGNATION_LOOKBACK:]:
            self.screen_stagnation += ONE_INT
        else:
            self.screen_stagnation = ZERO_INT
        self.recent_screen_hashes.append(screen_hash)
        self.recent_screen_hashes = self.recent_screen_hashes[-SCREEN_HASH_HISTORY_LIMIT:]

    def reset_pid_integral(self) -> None:
        self.pid_integral = FLOAT_ZERO

    def jacobian_impact(self, step_index: int) -> float:
        if not self.jacobian_vector:
            return self.stagnation_score
        if step_index < len(self.jacobian_vector):
            return self.jacobian_vector[step_index]
        return self.stagnation_score

    def should_replan(self, step_index: int) -> bool:
        impact = self.jacobian_impact(step_index)
        threshold = FLOAT_ONE / (FLOAT_ONE + self.pid_output)
        return impact > threshold

    def jacobian_dominant_step(self) -> int:
        if not self.jacobian_vector:
            return self.plan_step_index
        return max(range(len(self.jacobian_vector)), key=lambda i: self.jacobian_vector[i])

    def detect_repetition_in_history(self) -> bool:
        if len(self.history) < HISTORY_REPETITION_MIN_MATCHES:
            return False
        recent = self.history[-HISTORY_REPETITION_LOOKBACK:]
        sigs = [f"{h['verb']}:{h['obs']}" for h in recent if h['success']]
        return len(sigs) >= HISTORY_REPETITION_MIN_MATCHES and len(set(sigs)) == ONE_INT

    def stagnation_blocks_action(self, verb: str, target: str) -> bool:
        return f"{verb}:{target}" in self.blocked_signatures

    def record_action(self, verb: str, args: dict[str, Any], success: bool, observation: str) -> None:
        self.last_verb = verb
        self.last_success = success
        obs_record = _observation_record(observation)
        self.last_observation = str(obs_record["summary"])

        self.history.append({
            "verb": verb,
            "args": args,
            "success": success,
            "obs": self.last_observation,
            "observation": obs_record,
        })
        from config import MAX_HISTORY_ENTRIES
        if len(self.history) > MAX_HISTORY_ENTRIES:
            self.history = self.history[-MAX_HISTORY_ENTRIES:]

        target_str = str(args.get("target", "") or args.get("selector", "") or args.get("path", "") or args.get("command", "") or args.get("goal", "") or args.get("window_title", ""))
        self.update_signals(verb, target_str)

    def record_failure(self) -> None:
        self.consecutive_failures += ONE_INT

    def record_success(self) -> None:
        self.consecutive_failures = ZERO_INT

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


def _render_field(board: Blackboard, field_name: str, instruction: str) -> str:
    match field_name:
        case "goal":
            if board.original_goal and board.original_goal != board.goal:
                from goal_wrapper import is_wrapped_goal
                if is_wrapped_goal(board.goal):
                    return f"GOAL:\n{board.goal}"
                return f"GOAL: {board.goal}\nORIGINAL_GOAL: {board.original_goal}"
            return f"GOAL: {board.goal}"
        case "iteration":
            return f"ITERATION: {board.iteration}"
        case "instruction":
            if instruction:
                return f"INSTRUCTION: {instruction}"
            return ""
        case "checklist":
            if not board.plan_steps:
                return ""
            lines = ["CHECKLIST:"]
            for i, step in enumerate(board.plan_steps):
                if i < board.plan_step_index:
                    lines.append(f"  [{i}] done  {step}")
                elif i == board.plan_step_index:
                    lines.append(f"  [{i}] >>>   {step}")
                else:
                    lines.append(f"  [{i}]       {step}")
            return "\n".join(lines)
        case "checklist_current":
            if not board.plan_steps:
                return ""
            current = board.plan_steps[board.plan_step_index] if board.plan_step_index < len(board.plan_steps) else ""
            return f"CURRENT STEP: {current}" if current else ""
        case "notes":
            if not board.notes:
                return ""
            return "NOTES:\n" + "\n".join(f"  - {n}" for n in board.notes)
        case "screen_elements":
            if not board.screen:
                return ""
            return f"SCREEN_ELEMENTS:\n{board.screen}"
        case "focused_window":
            if not board.focused_window:
                return ""
            return f"FOCUSED_WINDOW: {board.focused_window}"
        case "actor_observe":
            if not board.actor_observe:
                return ""
            return f"ACTOR_OBSERVE: {board.actor_observe}"
        case "actor_conclusion":
            if not board.actor_conclusion:
                return ""
            return f"ACTOR_CONCLUSION: {board.actor_conclusion}"
        case "last_action":
            if not board.last_verb:
                return ""
            return f"LAST_ACTION: {board.last_verb} {'succeeded' if board.last_success else 'FAILED'}"
        case "last_result":
            if not board.last_observation:
                return ""
            return f"LAST_RESULT: {board.last_observation}"
        case "last_result_on_failure":
            if board.last_success or not board.last_observation:
                return ""
            return f"LAST_RESULT: {board.last_verb} FAILED: {board.last_observation}"
        case "last_expect":
            if not board.last_expect:
                return ""
            return f"LAST_EXPECT: {board.last_expect}"
        case "done_claimed":
            if not board.done_claimed:
                return ""
            return f"DONE_CLAIMED: {board.done_evidence}"
        case "planner_reasoning":
            if not board.last_plan_because:
                return ""
            return f"PLANNER_REASONING: {board.last_plan_because}"
        case "consecutive_failures":
            if board.consecutive_failures <= ZERO_INT:
                return ""
            return f"CONSECUTIVE_FAILURES: {board.consecutive_failures}"
        case "stagnation_score":
            return f"STAGNATION_SCORE: {board.stagnation_score:.3f}"
        case "pid":
            return f"PID: output={board.pid_output:.3f} integral={board.pid_integral:.3f} slope={board.pid_slope:.3f}"
        case "attractor_energy":
            return f"ATTRACTOR_ENERGY: {board.attractor_energy:.3f}"
        case "repetition_score":
            return f"REPETITION_SCORE: {board.repetition_score:.3f}"
        case "lorenz":
            return f"LORENZ: x={board.lorenz_x:.3f} y={board.lorenz_y:.3f} z={board.lorenz_z:.3f}"
        case "failed_step_index":
            if board.failed_step_index <= ZERO_INT:
                return ""
            return f"FAILED_STEP_INDEX: {board.failed_step_index}"
        case "recent_history":
            return board.format_history("RECENT_HISTORY", full=False)
        case "full_history":
            return board.format_history("FULL_HISTORY", full=True)
        case "learned_insights":
            try:
                from lessons import Lessons
                text = Lessons().get_context()
                return text if text else ""
            except Exception:
                return ""
        case "evolution_ledger":
            try:
                from persistence import get_evolution_ledger_context
                text = get_evolution_ledger_context()
                return text if text else ""
            except Exception:
                return ""
        case "current_prompts":
            prompts: dict[str, str] = {}
            for r in ("actor", "planner", "verifier"):
                p = BASE_DIR / "prompts" / f"{r}.txt"
                if p.exists():
                    prompts[r] = p.read_text(encoding="utf-8")
            if not prompts:
                return ""
            return "CURRENT_PROMPTS:\n" + "\n\n".join(f"[{r}.txt]\n{c}" for r, c in prompts.items())
        case "repetition_warning":
            if not board.detect_repetition_in_history():
                return ""
            return (
                "!!! WARNING: You have repeated the same action multiple times. "
                "If the goal's core action already succeeded, set mode=done NOW. "
                "If not done, you MUST try a DIFFERENT action."
            )
        case _:
            return ""


def _observation_record(observation: str) -> dict[str, Any]:
    if not observation:
        return {"chars": ZERO_INT, "lines": ZERO_INT, "sha256": "", "evidence_lines": [], "summary": ""}
    clean_lines = [line.strip() for line in observation.splitlines() if line.strip()]
    digest = hashlib.sha256(observation.encode("utf-8", errors="surrogatepass")).hexdigest()
    evidence = clean_lines[:CONTEXT_OBSERVATION_EVIDENCE_LINES]
    summary_parts = [
        f"chars={len(observation)}",
        f"lines={len(clean_lines)}",
        f"sha256={digest}",
    ]
    if evidence:
        summary_parts.append("evidence_lines=" + " | ".join(evidence))
    return {
        "chars": len(observation),
        "lines": len(clean_lines),
        "sha256": digest,
        "evidence_lines": evidence,
        "summary": "; ".join(summary_parts),
    }
