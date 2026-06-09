from __future__ import annotations
from typing import Any

from agents import AgentResult
from config import (
    LORENZ_SIGMA, LORENZ_RHO, LORENZ_BETA, LORENZ_DT, LORENZ_MAG_CAP,
    LORENZ_RHO_SENSITIVITY, LORENZ_BETA_SENSITIVITY, LORENZ_BETA_MIN,
    LORENZ_EQUILIBRIUM_OFFSET,
)


class LorenzAgent:
    name: str = "lorenz"

    def should_run(self, board: Any) -> bool:
        return True

    def run(self, board: Any) -> AgentResult:
        prev_x = board.lorenz_x
        x, y, z = board.lorenz_x, board.lorenz_y, board.lorenz_z
        rho_eff = LORENZ_RHO + board.stagnation_score * LORENZ_RHO_SENSITIVITY * LORENZ_RHO
        beta_eff = max(LORENZ_BETA_MIN, LORENZ_BETA - board.repetition_score * LORENZ_BETA_SENSITIVITY)
        steps = 1 + int(board.stagnation_score * 4)
        for _ in range(steps):
            x = x + LORENZ_SIGMA * (y - x) * LORENZ_DT
            y = y + (x * (rho_eff - z) - y) * LORENZ_DT
            z = z + (x * y - beta_eff * z) * LORENZ_DT
        mag = (x * x + y * y + z * z) ** 0.5
        if mag > LORENZ_MAG_CAP:
            scale = LORENZ_MAG_CAP / mag
            x, y, z = x * scale, y * scale, z * scale
            mag = LORENZ_MAG_CAP
        wing_crossed = (prev_x > 0.0) != (x > 0.0) and board.stagnation_score > 0.4
        eq_xy_sq = LORENZ_BETA * (LORENZ_RHO - LORENZ_EQUILIBRIUM_OFFSET)
        eq_mag = (eq_xy_sq + eq_xy_sq + (LORENZ_RHO - LORENZ_EQUILIBRIUM_OFFSET) ** 2) ** 0.5
        energy = mag / max(eq_mag, LORENZ_EQUILIBRIUM_OFFSET)
        return AgentResult(
            writes={
                "lorenz_x": x, "lorenz_y": y, "lorenz_z": z,
                "attractor_energy": energy, "lorenz_wing_crossed": wing_crossed,
            },
            event_phase="heartbeat.lorenz",
            event_data={"x": round(x, 2), "energy": round(energy, 2), "wing": wing_crossed},
        )
