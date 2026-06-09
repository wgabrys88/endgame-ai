from __future__ import annotations
from typing import Any

from config import (
    LORENZ_SIGMA, LORENZ_RHO, LORENZ_BETA, LORENZ_DT, LORENZ_MAG_CAP,
    LORENZ_RHO_SENSITIVITY, LORENZ_BETA_SENSITIVITY, LORENZ_BETA_MIN,
    LORENZ_EQUILIBRIUM_OFFSET,
)


class LorenzAgent:
    name: str = "lorenz"
    reads: list[str] = ["lorenz_x", "lorenz_y", "lorenz_z", "stagnation_score", "repetition_score"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        x = float(ctx.get("lorenz_x", 8.485))
        y = float(ctx.get("lorenz_y", 8.485))
        z = float(ctx.get("lorenz_z", 27.0))
        stag = float(ctx.get("stagnation_score", 0))
        rep = float(ctx.get("repetition_score", 0))
        prev_x = x

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

        return {
            "writes": {
                "lorenz_x": x, "lorenz_y": y, "lorenz_z": z,
                "attractor_energy": energy, "lorenz_wing_crossed": wing,
            },
            "next": "pid",
            "phase": "lorenz",
            "data": {"x": round(x, 2), "energy": round(energy, 2), "wing": wing},
        }
