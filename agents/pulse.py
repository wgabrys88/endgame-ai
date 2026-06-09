from __future__ import annotations
from typing import Any

from agents import AgentResult
from config import (
    STAGNATION_WEIGHT_FAILURES, STAGNATION_WEIGHT_REPETITION,
    STAGNATION_WEIGHT_SCREEN, STAGNATION_NORMALIZER,
    REPETITION_WINDOW, REPETITION_MIN_WINDOW,
    LORENZ_SIGMA, LORENZ_RHO, LORENZ_BETA, LORENZ_DT, LORENZ_MAG_CAP,
    LORENZ_RHO_SENSITIVITY, LORENZ_BETA_SENSITIVITY, LORENZ_BETA_MIN,
    LORENZ_EQUILIBRIUM_OFFSET,
    PID_KP, PID_KI, PID_KD, PID_INTEGRAL_MAX, PID_DEAD_ZONE,
    SCREEN_STAGNATION_LOOKBACK,
    STAGNATION_HALT_THRESHOLD, STAGNATION_HALT_SUSTAINED,
    REFLECT_THRESHOLD,
)


class PulseAgent:
    name: str = "pulse"

    def should_run(self, board: Any) -> bool:
        return True

    def run(self, board: Any) -> AgentResult:
        writes: dict[str, Any] = {}

        stag, rep = _stagnation(board)
        writes["stagnation_score"] = stag
        writes["repetition_score"] = rep

        lx, ly, lz, energy, wing = _lorenz(board, stag, rep)
        writes["lorenz_x"] = lx
        writes["lorenz_y"] = ly
        writes["lorenz_z"] = lz
        writes["attractor_energy"] = energy
        writes["lorenz_wing_crossed"] = wing

        pid_out, pid_int = _pid(board, stag)
        writes["pid_output"] = pid_out
        writes["pid_integral"] = pid_int
        writes["pid_prev"] = stag

        if board.last_verb:
            jac, jac_t = _jacobian(board)
            writes["jacobian"] = jac
            writes["jacobian_trials"] = jac_t

        next_agent, sched_writes, reason = _schedule(board, stag, wing, pid_out)
        writes.update(sched_writes)

        return AgentResult(
            writes=writes,
            next_agent=next_agent,
            event_phase="pulse",
            event_data={
                "stag": round(stag, 3),
                "lorenz_x": round(lx, 2),
                "pid": round(pid_out, 3),
                "energy": round(energy, 2),
                "wing": wing,
                "next": next_agent,
                "reason": reason,
            },
        )


def _stagnation(board: Any) -> tuple[float, float]:
    window = board.recent_sigs[-REPETITION_WINDOW:]
    if len(window) >= REPETITION_MIN_WINDOW:
        rep = 1.0 - (len(set(window)) / len(window))
    else:
        rep = 0.0
    raw = (board.consecutive_failures * STAGNATION_WEIGHT_FAILURES
           + rep * STAGNATION_WEIGHT_REPETITION
           + board.screen_stagnation * STAGNATION_WEIGHT_SCREEN)
    return min(1.0, raw / STAGNATION_NORMALIZER), rep


def _lorenz(board: Any, stag: float, rep: float) -> tuple[float, float, float, float, bool]:
    prev_x = board.lorenz_x
    x, y, z = board.lorenz_x, board.lorenz_y, board.lorenz_z
    rho_eff = LORENZ_RHO + stag * LORENZ_RHO_SENSITIVITY * LORENZ_RHO
    beta_eff = max(LORENZ_BETA_MIN, LORENZ_BETA - rep * LORENZ_BETA_SENSITIVITY)
    steps = 1 + int(stag * 4)
    for _ in range(steps):
        x = x + LORENZ_SIGMA * (y - x) * LORENZ_DT
        y = y + (x * (rho_eff - z) - y) * LORENZ_DT
        z = z + (x * y - beta_eff * z) * LORENZ_DT
    mag = (x * x + y * y + z * z) ** 0.5
    if mag > LORENZ_MAG_CAP:
        scale = LORENZ_MAG_CAP / mag
        x, y, z = x * scale, y * scale, z * scale
        mag = LORENZ_MAG_CAP
    wing = (prev_x > 0.0) != (x > 0.0) and stag > 0.4
    eq_xy_sq = LORENZ_BETA * (LORENZ_RHO - LORENZ_EQUILIBRIUM_OFFSET)
    eq_mag = (eq_xy_sq + eq_xy_sq + (LORENZ_RHO - LORENZ_EQUILIBRIUM_OFFSET) ** 2) ** 0.5
    energy = mag / max(eq_mag, LORENZ_EQUILIBRIUM_OFFSET)
    return x, y, z, energy, wing


def _pid(board: Any, stag: float) -> tuple[float, float]:
    integral = board.pid_integral
    if board.consecutive_failures > 0:
        integral = min(integral + stag, PID_INTEGRAL_MAX)
    slope = stag - board.pid_prev
    d_term = PID_KD * slope if abs(slope) > PID_DEAD_ZONE else 0.0
    output = max(0.0, PID_KP * stag + PID_KI * integral + d_term)
    return output, integral


def _jacobian(board: Any) -> tuple[dict[str, float], dict[str, int]]:
    verb = board.last_verb
    screen_changed = board.screen_hash not in board.recent_hashes[-SCREEN_STAGNATION_LOOKBACK:]
    trials = board.jacobian_trials.get(verb, 0) + 1
    new_trials = dict(board.jacobian_trials)
    new_trials[verb] = trials
    old = board.jacobian.get(verb, 0.5)
    alpha = 1.0 / min(trials, 10)
    new_score = old + alpha * ((1.0 if screen_changed else 0.0) - old)
    new_jac = dict(board.jacobian)
    new_jac[verb] = new_score
    return new_jac, new_trials


def _schedule(board: Any, stag: float, wing: bool, pid_out: float) -> tuple[str, dict[str, Any], str]:
    writes: dict[str, Any] = {}

    if stag >= STAGNATION_HALT_THRESHOLD:
        new_halt = board.halt_count + 1
        if new_halt >= STAGNATION_HALT_SUSTAINED:
            writes["halt_count"] = new_halt
            return "halt", writes, "halt"
        writes["halt_count"] = new_halt
    else:
        writes["halt_count"] = 0

    if wing:
        writes["lorenz_wing_crossed"] = False
        writes["plan_steps"] = []
        writes["plan_index"] = 0
        writes["consecutive_failures"] = 0
        writes["halt_count"] = 0
        writes["recent_sigs"] = []
        writes["repetition_score"] = 0.0
        writes["stagnation_score"] = 0.0
        writes["pid_integral"] = 0.0
        writes["notes"] = ["DIVERGE: previous approach failed. Try a completely different method."]
        writes["requested_next"] = ""
        return "planner", writes, "wing_cross"

    if board.requested_next:
        chosen = board.requested_next
        writes["requested_next"] = ""
        return chosen, writes, "requested"

    if board.total_role_calls == 0:
        return "planner", writes, "initial"

    if pid_out > REFLECT_THRESHOLD and board.role_calls.get("reflector", 0) < board.total_role_calls * 0.15:
        return "reflector", writes, "pid_gate"

    if not board.last_instruction:
        return "planner", writes, "no_instruction"

    return "actor", writes, "default"
