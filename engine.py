from __future__ import annotations
import importlib.util
import json
import threading
import time
from pathlib import Path
from typing import Any, Callable

from actions import is_python_step
from agents import (
    StagnationAgent, LorenzAgent, PidAgent, SchedulerAgent,
    ObserverAgent, PlannerAgent, ActorAgent, VerifierAgent, ReflectorAgent,
    MutatorAgent,
    _similar_to_completed, _trivial_milestone,
)
import config
import log
from llm import consume_last_reply
from token_state import record_reply, snapshot as token_snapshot


# --- Plugin Loader -----------------------------------------------------------

_plugin_mtimes: dict[str, float] = {}
_plugin_modules: dict[str, Any] = {}


def _run_plugins(board: dict[str, Any]) -> None:
    """Scan plugins/*.py, hot-load new/changed, call run(board), isolate errors."""
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
                log.emit("plugin.load", {"file": path.name})
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


MATH_AGENTS: list[Any] = [StagnationAgent(), LorenzAgent(), PidAgent()]

AGENTS: dict[str, Any] = {
    "scheduler": SchedulerAgent(),
    "observer": ObserverAgent(),
    "planner": PlannerAgent(),
    "actor": ActorAgent(),
    "verifier": VerifierAgent(),
    "reflector": ReflectorAgent(),
    "mutator": MutatorAgent(),
}

LLM_AGENTS: frozenset[str] = frozenset({"planner", "actor", "verifier", "reflector", "mutator"})


def _math_loop(board: dict[str, Any], stop: threading.Event) -> None:
    while not stop.is_set():
        for agent in MATH_AGENTS:
            ctx = {k: board[k] for k in agent.reads if k in board}
            result: dict[str, Any] = agent.run(ctx)
            board.update(result.get("writes", {}))
            log.emit(result.get("phase", agent.name), result.get("data"))
        trace: list[dict[str, Any]] = list(board.get("math_trace", []))
        trace.append({
            "stag": round(float(board.get("stagnation", 0)), 3),
            "pid": round(float(board.get("pid_output", 0)), 3),
            "energy": round(float(board.get("energy", 1)), 3),
            "wing": bool(board.get("wing_crossed", False)),
            "x": round(float(board.get("lorenz_x", 0)), 2),
        })
        board["math_trace"] = trace[-config.MATH_TRACE_LEN:]
        _save(board)
        stop.wait(config.MATH_INTERVAL)


def run(board: dict[str, Any], interrupted: Callable[[], bool]) -> bool:
    log.emit("start", {"goal": board.get("goal", ""), "budget": log.budget()})

    stop = threading.Event()
    math_thread = threading.Thread(target=_math_loop, args=(board, stop), daemon=True)
    math_thread.start()

    try:
        return _main_loop(board, interrupted)
    finally:
        stop.set()
        math_thread.join(timeout=5)


def _needs_screen(board: dict[str, Any], target: str) -> bool:
    if target not in LLM_AGENTS or target == "planner":
        return False
    if target == "actor":
        active = next((s for s in board.get("plan", []) if s.get("status") == "active"), None)
        if active and is_python_step(str(active.get("text", ""))):
            return False
    return config.GUI_MODE_PATH.exists()


def _run_agent(board: dict[str, Any], name: str) -> dict[str, Any]:
    if _needs_screen(board, name):
        obs = AGENTS["observer"]
        obs_ctx = {k: board[k] for k in obs.reads if k in board}
        obs_result = obs.run(obs_ctx)
        board.update(obs_result.get("writes", {}))
        log.emit(obs_result.get("phase", "observe"), obs_result.get("data"))
    agent = AGENTS[name]
    ctx = {k: board[k] for k in agent.reads if k in board}
    result = agent.run(ctx)
    writes = dict(result.get("writes", {}))
    data = result.get("data")
    if name in LLM_AGENTS:
        reply = consume_last_reply()
        if reply is not None:
            writes["token_state"] = record_reply(board.get("token_state"), reply)
            if isinstance(data, dict):
                data = dict(data)
                data["tokens"] = {
                    "prompt_est": reply.prompt_tokens_est,
                    "completion_est": reply.completion_tokens_est,
                    "total_est": reply.total_tokens_est,
                    "actual_total": reply.total_tokens_actual,
                }
                result["data"] = data
    result["writes"] = writes
    board.update(writes)
    log.emit(result.get("phase", name), result.get("data"))
    _save(board)
    return result


def _stop_satisfied(board: dict[str, Any]) -> bool:
    _save(board)
    log.emit("stop", {
        "reason": "goal_satisfied",
        "events": log.count(),
        "work": log.work_count(),
        "power": board.get("power", 0.0),
        "completions": len(board.get("completed", [])),
    })
    return True


def _poll_goal(board: dict[str, Any]) -> None:
    if not getattr(config, "_GOAL_MUTABLE", True) or not config.GOAL_PATH.exists():
        return
    try:
        new_goal = config.GOAL_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return
    old_goal = str(board.get("goal", ""))
    if new_goal == old_goal:
        return
    board["goal"] = new_goal
    board["plan"] = []
    board["done_when"] = ""
    log.emit("goal_change", {"from": old_goal, "to": new_goal})


def _main_loop(board: dict[str, Any], interrupted: Callable[[], bool]) -> bool:
    while not log.exhausted() and not interrupted():
        _poll_goal(board)
        if log.paused():
            time.sleep(config.DELAY_BETWEEN_CYCLES)
            continue
        _run_plugins(board)
        scheduler = AGENTS["scheduler"]
        ctx = {k: board[k] for k in scheduler.reads if k in board}
        result: dict[str, Any] = scheduler.run(ctx)
        board.update(result.get("writes", {}))
        log.emit(result.get("phase", "schedule"), result.get("data"))
        _save(board)

        target = str(result.get("next", ""))
        if target == "halt":
            return _stop_satisfied(board)
        if target == "done":
            time.sleep(config.DELAY_BETWEEN_CYCLES)
            continue
        if target not in AGENTS:
            time.sleep(config.DELAY_BETWEEN_CYCLES)
            continue

        nxt = target
        while nxt in AGENTS:
            result = _run_agent(board, nxt)
            nxt = str(result.get("next", ""))
            if nxt == "halt":
                return _stop_satisfied(board)
            if nxt == "done":
                _fission(board)
                log.emit("fission_sustain", {
                    "power": board.get("power", 0.0),
                    "completions": len(board.get("completed", [])),
                })
                break
            if nxt not in AGENTS:
                break

        _save(board)
        time.sleep(config.DELAY_BETWEEN_CYCLES)

    reason = "budget" if log.exhausted() else "interrupted"
    log.emit("stop", {"reason": reason, "events": log.count(), "work": log.work_count(), "power": board.get("power", 0.0)})
    return False


def _fission(board: dict[str, Any]) -> None:
    completed: list[str] = board.get("completed", [])
    done_when = str(board.get("done_when", ""))
    goal = str(board.get("goal", ""))
    if _similar_to_completed(done_when, completed):
        log.emit("fission_blocked", {"reason": "repeat", "done_when": done_when})
        board["plan"] = []
        board["done_when"] = ""
        return
    if _trivial_milestone(goal, done_when):
        log.emit("fission_blocked", {"reason": "trivial", "done_when": done_when})
        board["plan"] = []
        board["done_when"] = ""
        board["consecutive_failures"] = int(board.get("consecutive_failures", 0)) + 1
        return
    if done_when:
        completed.append(done_when)
    board["completed"] = completed
    start_time = float(board.get("start_time", time.time()))
    elapsed = max(1.0, time.time() - start_time)
    board["power"] = len(completed) / elapsed
    board["plan"] = []
    board["done_when"] = ""
    board["consecutive_failures"] = 0
    board["progress_history"] = []
    board["pid_integral"] = 0.0
    log.emit("fission", {"power": board["power"], "completions": len(completed)})


def _save(board: dict[str, Any]) -> None:
    data = {
        "goal": board.get("goal", ""),
        "plan": board.get("plan", []),
        "done_when": board.get("done_when", ""),
        "completed": board.get("completed", []),
        "power": board.get("power", 0.0),
        "consecutive_failures": board.get("consecutive_failures", 0),
        "stagnation": board.get("stagnation", 0),
        "lorenz_x": board.get("lorenz_x", 0),
        "lorenz_y": board.get("lorenz_y", 0),
        "lorenz_z": board.get("lorenz_z", 0),
        "energy": board.get("energy", 1),
        "pid_output": board.get("pid_output", 0),
        "pid_integral": board.get("pid_integral", 0),
        "wing_crossed": board.get("wing_crossed", False),
        "reflect_trigger": board.get("reflect_trigger", {}),
        "focused_window": board.get("focused_window", ""),
        "math_trace": board.get("math_trace", [])[-12:],
        "events": log.count(),
        "work_events": log.work_count(),
        "budget": log.budget(),
    }
    tokens = token_snapshot(board.get("token_state"))
    data["token_state"] = tokens
    data["token_trace"] = tokens.get("trace", [])[-config.TOKEN_TRACE_LEN:]
    data["token_warnings"] = tokens.get("warnings", [])[-config.TOKEN_WARNING_TRACE_LEN:]
    config.SNAPSHOT_PATH.write_text(json.dumps(data), encoding="utf-8")