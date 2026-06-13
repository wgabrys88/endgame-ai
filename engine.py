"""Engine — runs the agent pipeline. Plugins hot-swap. Math thread. Snapshot."""
from __future__ import annotations

import importlib.util
import json
import threading
import time
from typing import Any, Callable

from agents import (StagnationAgent, LorenzAgent, PidAgent, SchedulerAgent,
                    PlannerAgent, ActorAgent, VerifierAgent,
                    FissionJudgeAgent, ReflectorAgent, MutatorAgent)
import config
import log
from python_code import is_python_code

_plugin_mtimes: dict[str, float] = {}
_plugin_modules: dict[str, Any] = {}
_last_snapshot_at: float = 0.0

MATH_AGENTS = [StagnationAgent(), LorenzAgent(), PidAgent()]
AGENTS: dict[str, Any] = {
    "scheduler": SchedulerAgent(),
    "planner": PlannerAgent(), "actor": ActorAgent(),
    "verifier": VerifierAgent(), "reflector": ReflectorAgent(),
    "fission_judge": FissionJudgeAgent(), "mutator": MutatorAgent(),
}
LLM_AGENTS: frozenset[str] = frozenset({"planner", "verifier", "reflector", "fission_judge", "mutator"})


def _run_plugins(board: dict[str, Any]) -> None:
    if not config.PLUGINS_DIR.exists():
        return
    for path in sorted(config.PLUGINS_DIR.glob("*.py")):
        key = str(path)
        try:
            mt = path.stat().st_mtime
        except OSError:
            continue
        if key in _plugin_mtimes and _plugin_mtimes[key] == mt:
            mod = _plugin_modules.get(key)
        else:
            try:
                spec = importlib.util.spec_from_file_location(path.stem, path)
                if spec is None or spec.loader is None:
                    continue
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                _plugin_modules[key] = mod
                _plugin_mtimes[key] = mt
            except Exception as e:
                log.emit("plugin.error", {"file": path.name, "error": str(e)[:200]})
                continue
        if mod and hasattr(mod, "run"):
            try:
                result = mod.run(board)
                if isinstance(result, dict):
                    board.update(result.get("writes", {}))
                    if result.get("phase"):
                        log.emit(result["phase"], result.get("data"))
            except Exception as e:
                log.emit("plugin.error", {"file": path.name, "error": str(e)[:200]})


def _math_loop(board: dict[str, Any], stop: threading.Event) -> None:
    while not stop.is_set():
        payload: dict[str, Any] = {}
        for agent in MATH_AGENTS:
            ctx = {k: board[k] for k in agent.reads if k in board}
            result = agent.run(ctx)
            board.update(result.get("writes", {}))
            payload[agent.name] = result.get("data", {})
        log.emit("math", payload)
        trace = list(board.get("math_trace", []))
        trace.append({"stag": round(float(board.get("stagnation", 0)), 3), "pid": round(float(board.get("pid_output", 0)), 3), "energy": round(float(board.get("energy", 1)), 3)})
        board["math_trace"] = trace[-config.MATH_TRACE_LEN:]
        _save(board)
        stop.wait(config.MATH_INTERVAL)


def run(board: dict[str, Any], interrupted: Callable[[], bool]) -> bool:
    log.emit("start", {"goal": str(board.get("goal", ""))[:200], "budget": log.budget()})
    stop = threading.Event()
    math_thread = threading.Thread(target=_math_loop, args=(board, stop), daemon=True)
    math_thread.start()
    try:
        return _main_loop(board, interrupted)
    finally:
        stop.set()
        math_thread.join(timeout=5)


def _run_agent(board: dict[str, Any], name: str) -> dict[str, Any]:
    agent = AGENTS[name]
    ctx = {k: board[k] for k in agent.reads if k in board}
    result = agent.run(ctx)
    board.update(result.get("writes", {}))
    log.emit(result.get("phase", name), result.get("data"))
    _save(board, force=True)
    return result


def _main_loop(board: dict[str, Any], interrupted: Callable[[], bool]) -> bool:
    import os
    import comms
    personality = os.environ.get("ENDGAME_PERSONALITY", "")
    always_active = personality == "comms_operator"
    _last_wake_id: int = 0
    _booted = False  # allow first cycle before sleeping

    while not log.exhausted() and not interrupted():
        try:
            comms.drain_inject()
        except Exception:
            pass
        _poll_goal(board)

        # Sleep/wake gate: non-comms agents sleep unless they have work or are @mentioned
        if not always_active and not board.get("plan") and _booted:
            me = comms.agent_id()
            inbox = comms.pending_for(me, 3)
            new_msgs = [m for m in inbox if int(m.get("id", 0)) > _last_wake_id]
            if not new_msgs:
                if not board.get("_sleeping"):
                    log.emit("sleep", {})
                    board["_sleeping"] = True
                time.sleep(config.SLEEP_POLL_INTERVAL)
                continue
            board["_sleeping"] = False
            _last_wake_id = int(new_msgs[-1].get("id", 0))
            wake_msg = str(new_msgs[-1].get("text", ""))
            board["wake_request"] = wake_msg
            log.emit("wake", {"from": new_msgs[-1].get("from", "?"), "text": wake_msg[:120]})
        _booted = True

        # Validate active plan step is Python
        plan = board.get("plan", [])
        if plan and any(isinstance(s, dict) and s.get("status") == "active" and not is_python_code(str(s.get("code", ""))) for s in plan):
            board["plan"] = []
            board["done_when"] = ""
            log.emit("plan.reset", {"reason": "invalid step"})
        if log.paused():
            time.sleep(config.DELAY_BETWEEN_CYCLES)
            continue
        _run_plugins(board)
        # Schedule
        scheduler = AGENTS["scheduler"]
        ctx = {k: board[k] for k in scheduler.reads if k in board}
        result = scheduler.run(ctx)
        board.update(result.get("writes", {}))
        log.emit(result.get("phase", "schedule"), result.get("data"))
        _save(board)
        target = str(result.get("next", ""))
        if target == "halt":
            return _stop(board)
        if target == "done":
            data = result.get("data") if isinstance(result.get("data"), dict) else {}
            if data.get("reason") == "plan_cooldown":
                time.sleep(max(0.5, float(data.get("wait", config.PLAN_REJECT_COOLDOWN_SEC))))
            else:
                _fission(board)
                log.emit("fission_sustain", {"power": board.get("power", 0.0), "completions": len(board.get("completed", []))})
            time.sleep(config.DELAY_BETWEEN_CYCLES)
            continue
        # Chain agents
        nxt = target
        while nxt in AGENTS:
            result = _run_agent(board, nxt)
            nxt = str(result.get("next", ""))
            if nxt == "halt":
                return _stop(board)
            if nxt == "done":
                _fission(board)
                log.emit("fission_sustain", {"power": board.get("power", 0.0), "completions": len(board.get("completed", []))})
                break
        _save(board)
        time.sleep(config.DELAY_BETWEEN_CYCLES)
    log.emit("stop", {"reason": "budget" if log.exhausted() else "interrupted", "events": log.count(), "power": board.get("power", 0.0)})
    return False


def _fission(board: dict[str, Any]) -> None:
    if not board.pop("fission_approved", False):
        board["plan"] = []
        board["done_when"] = ""
        return
    completed = board.get("completed", [])
    dw = str(board.get("done_when", ""))
    if dw:
        completed.append(dw)
    board["completed"] = completed
    board["power"] = len(completed) / max(1.0, time.time() - float(board.get("start_time", time.time())))
    board["plan"] = []
    board["done_when"] = ""
    board["consecutive_failures"] = 0
    board["progress_history"] = []
    board["pid_integral"] = 0.0
    log.emit("fission", {"power": board["power"], "completions": len(completed)})


def _stop(board: dict[str, Any]) -> bool:
    _save(board)
    log.emit("stop", {"reason": "goal_satisfied", "events": log.count(), "power": board.get("power", 0.0), "completions": len(board.get("completed", []))})
    return True


def _poll_goal(board: dict[str, Any]) -> None:
    import os
    personality = os.environ.get("ENDGAME_PERSONALITY", "")
    if personality:
        ppath = config.PROMPTS_DIR / "personalities" / f"{personality}.txt"
        if ppath.exists():
            try:
                new = ppath.read_text(encoding="utf-8").strip()
            except OSError:
                return
            if new and new != board.get("goal"):
                board["goal"] = new
                board["plan"] = []
                board["done_when"] = ""
                log.emit("goal_change", {"source": "personality"})
            return
    if config.GOAL_PATH.exists():
        try:
            new = config.GOAL_PATH.read_text(encoding="utf-8").strip()
        except OSError:
            return
        if new and new != board.get("goal"):
            board["goal"] = new
            board["plan"] = []
            board["done_when"] = ""
            log.emit("goal_change", {"source": "goal.txt"})


def _save(board: dict[str, Any], *, force: bool = False) -> None:
    global _last_snapshot_at
    now = time.time()
    if not force and now - _last_snapshot_at < config.SNAPSHOT_INTERVAL_SEC:
        return
    _last_snapshot_at = now
    data = {k: board.get(k) for k in ("goal", "plan", "done_when", "completed", "power", "consecutive_failures",
                                       "stagnation", "energy", "pid_output", "pid_integral", "wing_crossed",
                                       "lorenz_x", "lorenz_y", "lorenz_z", "focused_window", "math_trace")}
    data["events"] = log.count()
    data["work_events"] = log.work_count()
    data["budget"] = log.budget()
    try:
        config.SNAPSHOT_PATH.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass
