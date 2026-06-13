"""Engine — runs the agent pipeline with priority interrupts, pressure math, plugin hot-swap."""
from __future__ import annotations
import importlib.util
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

from agents import SchedulerAgent, PlannerAgent, ActorAgent, VerifierAgent, FissionJudgeAgent
import config
import comms
import log


AGENTS: dict[str, Any] = {
    "scheduler": SchedulerAgent(),
    "planner": PlannerAgent(),
    "actor": ActorAgent(),
    "verifier": VerifierAgent(),
    "fission_judge": FissionJudgeAgent(),
}

_plugin_modules: dict[str, Any] = {}
_plugin_mtimes: dict[str, float] = {}


def run(board: dict[str, Any], interrupted: Callable[[], bool]) -> None:
    """Main loop: work on goal, check bus for priority interrupts each cycle."""
    board.setdefault("_pressure", {"stagnation": 0.0, "cycles": 0, "failures": 0, "last_fission": 0})

    while not log.exhausted() and not interrupted():
        # --- Priority interrupt check ---
        _check_interrupt(board)

        # --- Plugin hot-swap ---
        _run_plugins(board)

        # --- Pressure math (per cycle, not during LLM wait) ---
        _update_pressure(board)

        # --- Pipeline ---
        scheduler = AGENTS["scheduler"]
        result = scheduler.run(board)
        nxt = (result or {}).get("next")
        if not nxt:
            time.sleep(config.DELAY_BETWEEN_CYCLES)
            continue

        log.emit("schedule", {"next": nxt, "reason": result.get("data", {}).get("reason", "")})

        # Walk the pipeline chain
        while nxt and nxt in AGENTS and not interrupted():
            agent = AGENTS[nxt]
            result = agent.run(board)
            if result:
                phase = result.get("phase", nxt)
                log.emit(phase, result.get("data"))
                # Apply writes to board
                for k, v in (result.get("writes") or {}).items():
                    board[k] = v
                # Track outcomes for pressure
                if phase == "fission":
                    board["_pressure"]["last_fission"] = time.time()
                    board["_pressure"]["failures"] = 0
                elif phase in ("planner.error", "actor.error", "verifier.error") or \
                     (phase == "verify" and (result.get("data") or {}).get("verdict") == "denied"):
                    board["_pressure"]["failures"] += 1
                nxt = result.get("next")
            else:
                nxt = None
            # Check interrupt between pipeline stages
            if _check_interrupt(board):
                break

        time.sleep(config.DELAY_BETWEEN_CYCLES)


# --- Plugin Hot-Swap ---
# Personas can write plugins/ that take effect next cycle without restart.

def _run_plugins(board: dict[str, Any]) -> None:
    """Load/reload plugins from plugins/ dir, run each."""
    if not config.PLUGINS_DIR.exists():
        return
    for path in sorted(config.PLUGINS_DIR.glob("*.py")):
        name = path.stem
        try:
            mt = path.stat().st_mtime
        except OSError:
            continue
        if name not in _plugin_modules or _plugin_mtimes.get(name) != mt:
            # Load or reload
            try:
                spec = importlib.util.spec_from_file_location(f"plugin_{name}", str(path))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                _plugin_modules[name] = mod
                _plugin_mtimes[name] = mt
            except Exception as e:
                log.emit("plugin.error", {"name": name, "error": str(e)[:120]})
                continue
        mod = _plugin_modules.get(name)
        if mod and hasattr(mod, "run"):
            try:
                result = mod.run(board)
                if isinstance(result, dict) and result.get("phase"):
                    log.emit(result["phase"], result.get("data"))
            except Exception as e:
                log.emit("plugin.error", {"name": name, "error": str(e)[:120]})


# --- Pressure Math ---
# Stagnation = how stuck this persona is (0.0 = productive, 1.0 = completely stuck)
# This feeds into comms_operator's routing decisions and TUI display.

def _update_pressure(board: dict[str, Any]) -> None:
    """Compute stagnation pressure. Runs once per cycle (NOT during LLM waits)."""
    p = board["_pressure"]
    p["cycles"] += 1

    # Stagnation: ramps up with failures and time since last fission
    failures = p["failures"]
    since_fission = time.time() - p["last_fission"] if p["last_fission"] else p["cycles"] * config.DELAY_BETWEEN_CYCLES

    # Failure pressure: each consecutive failure adds 0.15, capped
    fail_pressure = min(1.0, failures * 0.15)

    # Time pressure: after 60s without fission, starts ramping (maxes at 300s)
    time_pressure = min(1.0, max(0.0, since_fission - 60) / 240.0)

    # Combined: weighted average
    stag = min(1.0, fail_pressure * 0.6 + time_pressure * 0.4)
    p["stagnation"] = stag
    # MoE confidence signal: power = inverse stagnation (feeds comms_operator routing)
    board["stagnation"] = stag
    board["power"] = round(1.0 - stag, 3)

    # Emit periodically (every 10 cycles ~ 20s)
    if p["cycles"] % 10 == 0:
        log.emit("pressure", {"stagnation": round(stag, 3), "power": board["power"],
                               "failures": failures, "cycles": p["cycles"]})


# --- Priority Interrupt ---

def _check_interrupt(board: dict[str, Any]) -> bool:
    """Check bus for priority messages. Returns True if goal was switched."""
    try:
        comms.drain_inject()
    except Exception:
        pass
    me = comms.agent_id()
    inbox = comms.pending_for(me, 3)
    current_pri = board.get("priority", config.PRI_MAINTENANCE)

    for msg in inbox:
        msg_id = int(msg.get("id", 0))
        if msg_id <= board.get("_last_msg_id", 0):
            continue
        msg_pri = _msg_priority(msg)
        if msg_pri > current_pri:
            # INTERRUPT: switch goal
            board["_last_msg_id"] = msg_id
            board["goal"] = str(msg.get("text", ""))
            board["priority"] = msg_pri
            board["plan"] = []
            board["history"] = []
            board["_pressure"]["failures"] = 0  # reset on new goal
            log.emit("interrupt", {"from": msg.get("from"), "pri": msg_pri, "text": str(msg.get("text", ""))[:120]})
            return True
        board["_last_msg_id"] = msg_id
    return False


def _msg_priority(msg: dict) -> int:
    """Determine priority from message metadata."""
    data = msg.get("data") or {}
    if isinstance(data, dict) and "priority" in data:
        return int(data["priority"])
    if str(msg.get("from", "")) == "human":
        return config.PRI_HUMAN
    if str(msg.get("kind", "")) == "request":
        return config.PRI_NORMAL
    return config.PRI_MAINTENANCE
