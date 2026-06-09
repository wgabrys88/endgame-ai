from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any

from config import (
    SNAPSHOT_PATH,
    LORENZ_SIGMA, LORENZ_RHO, LORENZ_BETA, LORENZ_DT, LORENZ_MAG_CAP,
    LORENZ_RHO_SENSITIVITY, LORENZ_BETA_SENSITIVITY, LORENZ_BETA_MIN,
    LORENZ_EQUILIBRIUM_OFFSET,
    PID_KP, PID_KI, PID_KD, PID_INTEGRAL_MAX, PID_DEAD_ZONE,
    STAGNATION_WEIGHT_FAILURES, STAGNATION_WEIGHT_REPETITION,
    STAGNATION_WEIGHT_SCREEN, STAGNATION_NORMALIZER,
    STAGNATION_HALT_THRESHOLD, STAGNATION_HALT_SUSTAINED,
    REPETITION_WINDOW, REPETITION_MIN_WINDOW,
    SCREEN_STAGNATION_LOOKBACK, SCREEN_HASH_HISTORY_LIMIT,
    MAX_HISTORY, CONTEXT_POLICY,
)
import log


@dataclass(slots=True)
class Board:
    goal: str = ""
    plan_steps: list[str] = field(default_factory=list[str])
    plan_index: int = 0
    history: list[dict[str, Any]] = field(default_factory=lambda: list[dict[str, Any]]())
    notes: list[str] = field(default_factory=list[str])
    screen: str = ""
    screen_hash: str = ""
    screen_elements: dict[str, Any] = field(default_factory=lambda: dict[str, Any]())
    focused_window: str = ""
    last_verb: str = ""
    last_success: bool = False
    last_observation: str = ""
    actor_observe: str = ""
    actor_conclusion: str = ""
    consecutive_failures: int = 0
    verify_denied_count: int = 0
    repetition_score: float = 0.0
    stagnation_score: float = 0.0
    screen_stagnation: int = 0
    recent_hashes: list[str] = field(default_factory=list[str])
    recent_sigs: list[str] = field(default_factory=list[str])
    jacobian: dict[str, float] = field(default_factory=lambda: dict[str, float]())
    jacobian_trials: dict[str, int] = field(default_factory=lambda: dict[str, int]())
    lorenz_x: float = 8.485
    lorenz_y: float = 8.485
    lorenz_z: float = 27.0
    attractor_energy: float = 1.0
    lorenz_wing_crossed: bool = False
    pid_output: float = 0.0
    pid_integral: float = 0.0
    pid_prev: float = 0.0
    last_instruction: str = ""
    requested_next: str = ""
    role_calls: dict[str, int] = field(default_factory=lambda: dict[str, int]())
    total_role_calls: int = 0
    halt_count: int = 0
    last_outputs: dict[str, str] = field(default_factory=lambda: dict[str, str]())

    def context(self, role: str, instruction: str = "") -> str:
        fields = CONTEXT_POLICY.get(role, [])
        parts: list[str] = []
        for f in fields:
            text = _render(self, f, instruction)
            if text:
                parts.append(text)
        return "\n\n".join(parts)

    def record_action(self, verb: str, success: bool, observation: str) -> None:
        self.last_verb = verb
        self.last_success = success
        self.last_observation = observation
        self.history.append({"verb": verb, "ok": success, "obs": observation[:200]})
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]
        self._update_signals(verb)

    def update_jacobian(self, verb: str, screen_changed: bool) -> None:
        trials = self.jacobian_trials.get(verb, 0) + 1
        self.jacobian_trials[verb] = trials
        old = self.jacobian.get(verb, 0.5)
        alpha = 1.0 / min(trials, 10)
        self.jacobian[verb] = old + alpha * ((1.0 if screen_changed else 0.0) - old)

    def record_screen(self, text: str, hash_val: str, elements: dict[str, Any], focused: str) -> None:
        self.screen = text
        self.screen_hash = hash_val
        self.screen_elements = elements
        self.focused_window = focused
        if hash_val in self.recent_hashes[-SCREEN_STAGNATION_LOOKBACK:]:
            self.screen_stagnation += 1
        else:
            self.screen_stagnation = 0
        self.recent_hashes.append(hash_val)
        if len(self.recent_hashes) > SCREEN_HASH_HISTORY_LIMIT:
            self.recent_hashes = self.recent_hashes[-SCREEN_HASH_HISTORY_LIMIT:]

    def on_success(self) -> None:
        self.consecutive_failures = 0

    def on_failure(self) -> None:
        self.consecutive_failures += 1
        self._update_signals("_fail")

    def on_verify_denied(self) -> None:
        self.verify_denied_count += 1
        if not (len(self.history) > 0 and self.history[-1].get("ok")):
            self.consecutive_failures += 1
        self._compute_stagnation()

    def on_last_step(self) -> bool:
        if not self.plan_steps:
            return False
        return self.plan_index >= len(self.plan_steps) - 1

    def advance_step(self) -> None:
        if self.plan_steps and self.plan_index < len(self.plan_steps) - 1:
            self.plan_index += 1
            self.pid_integral = 0.0

    def _update_signals(self, verb: str) -> None:
        self.recent_sigs.append(verb)
        if len(self.recent_sigs) > REPETITION_WINDOW:
            self.recent_sigs = self.recent_sigs[-REPETITION_WINDOW:]
        window = self.recent_sigs[-REPETITION_WINDOW:]
        if len(window) >= REPETITION_MIN_WINDOW:
            self.repetition_score = 1.0 - (len(set(window)) / len(window))
        else:
            self.repetition_score = 0.0
        self._compute_stagnation()

    def _compute_stagnation(self) -> None:
        raw = (self.consecutive_failures * STAGNATION_WEIGHT_FAILURES
               + self.repetition_score * STAGNATION_WEIGHT_REPETITION
               + self.screen_stagnation * STAGNATION_WEIGHT_SCREEN)
        self.stagnation_score = min(1.0, raw / STAGNATION_NORMALIZER)

    def _step_lorenz(self) -> None:
        prev_x = self.lorenz_x
        x, y, z = self.lorenz_x, self.lorenz_y, self.lorenz_z
        rho_eff = LORENZ_RHO + self.stagnation_score * LORENZ_RHO_SENSITIVITY * LORENZ_RHO
        beta_eff = max(LORENZ_BETA_MIN, LORENZ_BETA - self.repetition_score * LORENZ_BETA_SENSITIVITY)
        steps = 1 + int(self.stagnation_score * 4)
        for _ in range(steps):
            x = x + LORENZ_SIGMA * (y - x) * LORENZ_DT
            y = y + (x * (rho_eff - z) - y) * LORENZ_DT
            z = z + (x * y - beta_eff * z) * LORENZ_DT
        mag = (x * x + y * y + z * z) ** 0.5
        if mag > LORENZ_MAG_CAP:
            scale = LORENZ_MAG_CAP / mag
            x, y, z = x * scale, y * scale, z * scale
            mag = LORENZ_MAG_CAP
        self.lorenz_wing_crossed = (prev_x > 0.0) != (x > 0.0) and self.stagnation_score > 0.0
        self.lorenz_x, self.lorenz_y, self.lorenz_z = x, y, z
        eq_xy_sq = LORENZ_BETA * (LORENZ_RHO - LORENZ_EQUILIBRIUM_OFFSET)
        eq_mag = (eq_xy_sq + eq_xy_sq + (LORENZ_RHO - LORENZ_EQUILIBRIUM_OFFSET) ** 2) ** 0.5
        self.attractor_energy = mag / max(eq_mag, LORENZ_EQUILIBRIUM_OFFSET)

    def _step_pid(self) -> None:
        error = self.stagnation_score
        if self.consecutive_failures > 0:
            self.pid_integral = min(self.pid_integral + error, PID_INTEGRAL_MAX)
        slope = error - self.pid_prev
        d_term = PID_KD * slope if abs(slope) > PID_DEAD_ZONE else 0.0
        self.pid_output = max(0.0, PID_KP * error + PID_KI * self.pid_integral + d_term)
        self.pid_prev = error

    def save(self) -> None:
        data = {
            "goal": self.goal, "plan_steps": self.plan_steps, "plan_index": self.plan_index,
            "history": self.history[-20:], "consecutive_failures": self.consecutive_failures,
            "stagnation_score": self.stagnation_score, "lorenz_x": self.lorenz_x,
            "lorenz_y": self.lorenz_y, "lorenz_z": self.lorenz_z,
            "pid_output": self.pid_output, "pid_integral": self.pid_integral,
            "jacobian": self.jacobian,
            "events": log.count(), "budget": log.budget(),
        }
        SNAPSHOT_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def effective_temperature(self) -> float:
        from config import LLM_TEMPERATURE
        base = LLM_TEMPERATURE
        chaos_boost = min(0.4, self.attractor_energy * 0.1)
        stagnation_boost = min(0.3, self.stagnation_score * 0.3)
        return min(1.0, base + chaos_boost + stagnation_boost)

    def record_role_call(self, role: str) -> None:
        self.role_calls[role] = self.role_calls.get(role, 0) + 1
        self.total_role_calls += 1

    def decide_next_role(self) -> str:
        self._step_lorenz()
        self._step_pid()

        if self.stagnation_score >= STAGNATION_HALT_THRESHOLD:
            self.halt_count += 1
            if self.halt_count >= STAGNATION_HALT_SUSTAINED:
                return "halt"
        else:
            self.halt_count = 0

        if self.lorenz_wing_crossed:
            self.lorenz_wing_crossed = False
            self.plan_steps = []
            self.plan_index = 0
            self.notes = ["DIVERGE: previous approach failed. Try a completely different method."]
            log.emit("lorenz.fork", {"x": self.lorenz_x, "stagnation": self.stagnation_score})
            self.requested_next = ""
            return "planner"

        if self.requested_next:
            role = self.requested_next
            self.requested_next = ""
            return role

        if self.total_role_calls == 0:
            return "planner"

        if self.pid_output > 0.5 and self.role_calls.get("reflector", 0) < self.total_role_calls * 0.15:
            return "reflector"

        if not self.last_instruction:
            return "planner"

        return "actor"


def _render(b: Board, field: str, instruction: str) -> str:
    match field:
        case "goal":
            return f"GOAL: {b.goal}"
        case "instruction":
            return f"INSTRUCTION: {instruction}" if instruction else ""
        case "screen":
            return f"SCREEN:\n{b.screen}" if b.screen else ""
        case "plan":
            if not b.plan_steps:
                return ""
            lines = ["PLAN:"]
            for i, step in enumerate(b.plan_steps):
                marker = ">>>" if i == b.plan_index else ("done" if i < b.plan_index else "   ")
                lines.append(f"  [{i}] {marker} {step}")
            return "\n".join(lines)
        case "history":
            recent = b.history[-8:]
            if not recent:
                return ""
            lines = ["HISTORY:"]
            for h in recent:
                lines.append(f"  {h['verb']} {'ok' if h['ok'] else 'FAIL'}: {h['obs']}")
            return "\n".join(lines)
        case "budget":
            remaining = log.budget() - log.count()
            if remaining > log.budget() // 2:
                return ""
            return f"BUDGET: {remaining} events remaining. Be decisive."
        case "diverge":
            if not b.notes:
                return ""
            return "\n".join(b.notes)
        case "math":
            jac = ""
            if b.jacobian:
                top = sorted(b.jacobian.items(), key=lambda x: x[1], reverse=True)[:5]
                jac = " jacobian=[" + ",".join(f"{k}:{v:.2f}" for k, v in top) + "]"
            return (f"MATH: stagnation={b.stagnation_score:.2f} pid={b.pid_output:.2f} "
                    f"energy={b.attractor_energy:.2f} lorenz_x={b.lorenz_x:.2f}{jac}")
        case "failures":
            if b.consecutive_failures == 0 and b.verify_denied_count == 0:
                return ""
            parts_f: list[str] = []
            if b.verify_denied_count > 0:
                parts_f.append(f"Verifier DENIED {b.verify_denied_count} times. You MUST choose mode=direct and take actions.")
            if b.consecutive_failures > 0:
                parts_f.append(f"Consecutive failures: {b.consecutive_failures}. Try a different approach.")
            return "\n".join(parts_f)
        case "roles":
            if not b.last_outputs:
                return ""
            lines_r = ["OTHER AGENTS:"]
            for role_name, output in b.last_outputs.items():
                lines_r.append(f"  {role_name}: {output[:120]}")
            return "\n".join(lines_r)
        case _:
            return ""
