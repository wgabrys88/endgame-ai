"""Engine — runs the agent pipeline with priority interrupts, pressure math, plugin hot-swap."""
from __future__ import annotations
import importlib.util
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

from agents import SchedulerAgent, PlannerAgent, ActorAgent, VerifierAgent, ReflectorAgent, FissionJudgeAgent
import config
import comms
import log


AGENTS: dict[str, Any] = {
    "scheduler": SchedulerAgent(),
    "planner": PlannerAgent(),
    "actor": ActorAgent(),
    "verifier": VerifierAgent(),
    "reflector": ReflectorAgent(),
    "fission_judge": FissionJudgeAgent(),
}

_plugin_modules: dict[str, Any] = {}
_plugin_mtimes: dict[str, float] = {}


def run(board: dict[str, Any], interrupted: Callable[[], bool]) -> None:
    """Main loop: work on goal, check bus for priority interrupts each cycle."""
    board.setdefault("_pressure", {"stagnation": 0.0, "velocity": 0.0, "cycles": 0,
                                    "failures": 0, "last_fission": 0, "prev_stag": 0.0})
    board.setdefault("_moe", {"stuck_ticks": {}})

    while not log.exhausted() and not interrupted():
        # --- Priority interrupt check ---
        _check_interrupt(board)

        # --- Plugin hot-swap ---
        _run_plugins(board)

        # --- Pressure math (per cycle, not during LLM wait) ---
        _update_pressure(board)

        # --- MoE gate (comms_operator only, deterministic, no LLM) ---
        if _moe_route(board):
            time.sleep(config.DELAY_BETWEEN_CYCLES)
            continue

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
                board["_last_phase"] = phase
                # Apply writes to board
                for k, v in (result.get("writes") or {}).items():
                    board[k] = v
                # Track outcomes for pressure
                if phase == "fission":
                    board["_pressure"]["last_fission"] = time.time()
                    board["_pressure"]["failures"] = 0
                elif phase in ("planner.error", "actor.error", "verifier.error") or \
                     (phase == "verify" and (result.get("data") or {}).get("verdict") == "denied") or \
                     (phase == "actor" and not (result.get("data") or {}).get("ok", True)):
                    board["_pressure"]["failures"] += 1
                    if board.get("priority", config.PRI_MAINTENANCE) >= config.PRI_HUMAN:
                        board["_human_denials"] = board.get("_human_denials", 0) + 1
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
                if not isinstance(result, dict):
                    continue
                for k, v in (result.get("writes") or {}).items():
                    board[k] = v
                if result.get("phase"):
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
    velocity = round(p.get("prev_stag", stag) - stag, 4)  # positive = improving
    p["prev_stag"] = stag
    p["stagnation"] = stag
    p["velocity"] = velocity
    board["stagnation"] = stag
    board["velocity"] = velocity
    board["power"] = round(1.0 - stag, 3)

    if p["cycles"] % 10 == 0:
        log.emit("pressure", {"stagnation": round(stag, 3), "power": board["power"],
                               "velocity": velocity, "failures": failures, "cycles": p["cycles"]})


# --- MoE Gating (Bause 2026) — comms_operator softmax router ---

def _pick_alternate(persona: str) -> str:
    """Escalation target when a worker is stuck."""
    pool = [p for p in config.WORKER_PERSONAS if p != persona]
    if "quality_critic" in pool:
        return "quality_critic"
    return pool[0] if pool else "implementor"


def _moe_route(board: dict[str, Any]) -> bool:
    """Deterministic MoE routing cycle. Returns True if a route/escalation fired."""
    if os.environ.get("ENDGAME_PERSONALITY", "") != "comms_operator":
        return False
    if time.time() - float(board.get("_last_moe", 0)) < config.COMMS_ROUTE_INTERVAL:
        return False

    colony = comms.colony_state()
    workers = {k: v for k, v in colony.items()
               if k in config.WORKER_PERSONAS and k != "comms_operator"}
    if not workers:
        return False

    moe = board["_moe"]
    stuck_ticks: dict[str, int] = moe.setdefault("stuck_ticks", {})
    escalations: list[tuple[str, dict[str, Any]]] = []

    for who, st in workers.items():
        stag = float(st.get("stagnation", 0))
        vel = float(st.get("velocity", 0))
        if stag >= config.STAG_ESCALATE and abs(vel) <= config.VEL_STUCK:
            stuck_ticks[who] = stuck_ticks.get(who, 0) + 1
        else:
            stuck_ticks[who] = 0
        if stuck_ticks.get(who, 0) >= config.STUCK_TICKS_ESCALATE:
            escalations.append((who, st))

    powers = {who: float(st.get("power", 0)) for who, st in workers.items()}
    ranked = comms.softmax_route(powers)
    gate_weights = {w: round(p, 3) for w, p in ranked}
    board["_last_moe"] = time.time()

    if escalations:
        for who, st in escalations:
            alt = _pick_alternate(who)
            slot = int(st.get("slot", 0) or config.PERSONA_SLOTS.get(who, 0) or 0)
            ticks = stuck_ticks.get(who, 0)
            reason = (f"escalate @{who} stag={st.get('stagnation', 0):.2f} "
                      f"vel={st.get('velocity', 0):.2f} stuck={ticks}t")
            comms.route("comms_operator", alt, reason, priority=config.PRI_CRITICAL,
                        scores=gate_weights, goal=f"Unblock work stalled at @{who}",
                        escalate=True, slot=slot)
            if slot >= 2:
                comms.post_control("reassign", slot=slot, persona=alt,
                                   from_persona=who, reason=reason,
                                   priority=config.PRI_CRITICAL)
            stuck_ticks[who] = 0
            log.emit("moe.escalate", {"from": who, "to": alt, "slot": slot,
                                       "stagnation": st.get("stagnation"), "ticks": ticks})
        return True

    if comms.human_task_active():
        log.emit("moe.yield", {"reason": "human pri=3 task active"})
        return False

    if ranked and ranked[0][1] >= config.MOE_GATE_MIN:
        target, weight = ranked[0]
        reason = f"MoE gate={weight:.2f} — assign maintenance scan"
        comms.route("comms_operator", target, reason, priority=config.PRI_NORMAL,
                    scores=gate_weights, goal="Colony maintenance: audit and report on bus")
        log.emit("moe.route", {"to": target, "weight": round(weight, 3), "scores": gate_weights})
        return True

    return False


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

    inbox = sorted(inbox, key=lambda m: (-comms.msg_priority(m), -int(m.get("id", 0) or 0)))
    for msg in inbox:
        msg_id = int(msg.get("id", 0))
        if msg_id <= board.get("_last_msg_id", 0):
            continue
        msg_pri = comms.msg_priority(msg)
        is_human = str(msg.get("from", "")) == "human"
        if is_human or msg_pri >= config.PRI_HUMAN or msg_pri > current_pri:
            # INTERRUPT: switch goal
            board["_last_msg_id"] = msg_id
            payload = msg.get("payload") or msg.get("data") or {}
            goal_text = str(payload.get("goal", "")) if isinstance(payload, dict) else ""
            board["goal"] = goal_text or str(msg.get("text", ""))
            board["priority"] = msg_pri
            board["plan"] = []
            board["history"] = []
            board["_human_denials"] = 0
            board["_pressure"]["failures"] = 0  # reset on new goal
            log.emit("interrupt", {"from": msg.get("from"), "pri": msg_pri, "text": str(msg.get("text", ""))[:120]})
            return True
        board["_last_msg_id"] = msg_id
    return False
