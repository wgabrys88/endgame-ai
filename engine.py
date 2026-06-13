from __future__ import annotations
import importlib.util
import json
import threading
import time
from pathlib import Path
from typing import Any, Callable


from agents import (
    StagnationAgent, LorenzAgent, PidAgent, SchedulerAgent,
    ObserverAgent, PlannerAgent, ActorAgent, VerifierAgent, FissionJudgeAgent,
    ReflectorAgent, MutatorAgent,
)
import config
import log
from llm import consume_last_reply
from python_code import is_python_code
from token_state import record_reply, snapshot as token_snapshot


# --- Plugin Loader -----------------------------------------------------------

_plugin_mtimes: dict[str, float] = {}
_plugin_modules: dict[str, Any] = {}
_plugins_logged: set[str] = set()
_last_telemetry_stag: float | None = None
_last_snapshot_at: float = 0.0


def _run_plugins(board: dict[str, Any]) -> None:
    """Scan plugins/*.py, hot-load new/changed, call run(board), isolate errors."""
    global _last_telemetry_stag
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
                if path.name not in _plugins_logged:
                    _plugins_logged.add(path.name)
                    log.emit("plugin.load", {"file": path.name})
            except Exception as e:
                log.emit("plugin.error", {"file": path.name, "error": str(e)[:200]})
                continue
        if mod and hasattr(mod, "run"):
            try:
                result = mod.run(board)
                if isinstance(result, dict):
                    board.update(result.get("writes", {}))
                    phase = result.get("phase")
                    if phase:
                        data = result.get("data")
                        skip_log = False
                        if phase == "plugin.telemetry" and isinstance(data, dict):
                            stag = float(data.get("stagnation", -1))
                            if _last_telemetry_stag is not None and abs(stag - _last_telemetry_stag) < 0.05:
                                skip_log = True
                            else:
                                _last_telemetry_stag = stag
                        if not skip_log:
                            log.emit(phase, data)
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
    "fission_judge": FissionJudgeAgent(),
    "mutator": MutatorAgent(),
}

LLM_AGENTS: frozenset[str] = frozenset({"planner", "verifier", "reflector", "fission_judge", "mutator"})


def _math_loop(board: dict[str, Any], stop: threading.Event) -> None:
    while not stop.is_set():
        math_payload: dict[str, Any] = {}
        for agent in MATH_AGENTS:
            ctx = {k: board[k] for k in agent.reads if k in board}
            result: dict[str, Any] = agent.run(ctx)
            board.update(result.get("writes", {}))
            math_payload[agent.name] = result.get("data", {})
        log.emit("math", math_payload)
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
    goal = str(board.get("goal", ""))
    log.emit("start", {"goal": goal[:config.LOG_GOAL_MAX], "budget": log.budget()})

    stop = threading.Event()
    math_thread = threading.Thread(target=_math_loop, args=(board, stop), daemon=True)
    math_thread.start()

    try:
        return _main_loop(board, interrupted)
    finally:
        stop.set()
        math_thread.join(timeout=5)


def _needs_screen(board: dict[str, Any], target: str) -> bool:
    if target not in LLM_AGENTS or target in ("planner", "actor"):
        return False
    return config.GUI_MODE_PATH.exists()


def _ensure_gui_operator() -> None:
    import os
    if os.environ.get("ENDGAME_PERSONALITY", "").strip() == "gui_operator":
        try:
            config.GUI_MODE_PATH.write_text("1", encoding="utf-8")
        except OSError:
            pass


def _refresh_desktop(board: dict[str, Any]) -> None:
    if not config.GUI_MODE_PATH.exists():
        return
    if not config.is_gui_operator():
        return
    obs = AGENTS["observer"]
    obs_ctx = {k: board[k] for k in obs.reads if k in board}
    obs_result = obs.run(obs_ctx)
    board.update(obs_result.get("writes", {}))


def _run_agent(board: dict[str, Any], name: str) -> dict[str, Any]:
    if name == "planner" and config.GUI_MODE_PATH.exists():
        _refresh_desktop(board)
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
    result["writes"] = writes
    board.update(writes)
    log.emit(result.get("phase", name), result.get("data"))
    _save(board, force=True)
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
    import os as _os
    personality = _os.environ.get("ENDGAME_PERSONALITY", "")
    if personality:
        ppath = config.PROMPTS_DIR / "personalities" / f"{personality}.txt"
        if ppath.exists():
            try:
                new_goal = ppath.read_text(encoding="utf-8").strip()
            except OSError:
                return
            old_goal = str(board.get("goal", ""))
            if new_goal and new_goal != old_goal:
                board["goal"] = new_goal
                board["plan"] = []
                board["done_when"] = ""
                log.emit("goal_change", {"from": old_goal[:80], "to": new_goal[:80], "source": "personality"})
            return
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


def _plan_has_valid_active_step(plan: list[Any]) -> bool:
    """Return False only when an active step exists but is invalid/missing."""
    if not plan:
        return True
    active = next((s for s in plan if isinstance(s, dict) and s.get("status") == "active"), None)
    if active is None:
        return True  # no active step; scheduler will advance or verify
    snippet = str(active.get("code", active.get("text", ""))).strip()
    return bool(snippet) and is_python_code(snippet)


def _reset_invalid_plan(board: dict[str, Any], reason: str) -> None:
    board["plan"] = []
    board["done_when"] = ""
    log.emit("plan.reset", {"reason": reason})


def _main_loop(board: dict[str, Any], interrupted: Callable[[], bool]) -> bool:
    while not log.exhausted() and not interrupted():
        try:
            import comms
            comms.drain_inject()
        except Exception:
            pass
        _ensure_gui_operator()
        _poll_goal(board)
        if board.get("plan") and not _plan_has_valid_active_step(board.get("plan", [])):
            _reset_invalid_plan(board, "invalid active step - not Python or missing")
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
            data = result.get("data") if isinstance(result.get("data"), dict) else {}
            if data.get("reason") == "plan_cooldown":
                wait = float(data.get("wait", config.PLAN_REJECT_COOLDOWN_SEC))
                time.sleep(max(0.5, wait))
            else:
                time.sleep(config.DELAY_BETWEEN_CYCLES)
            continue
        if target not in AGENTS:
            time.sleep(config.DELAY_BETWEEN_CYCLES)
            continue

        nxt = target
        while nxt in AGENTS:
            if nxt == "actor" and board.get("plan") and not _plan_has_valid_active_step(board.get("plan", [])):
                _reset_invalid_plan(board, "actor saw invalid/missing active step")
                break
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
    if not board.pop("fission_approved", False):
        log.emit("fission_blocked", {"reason": "no_llm_credit", "done_when": done_when[:120]})
        board["plan"] = []
        board["done_when"] = ""
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


def _save(board: dict[str, Any], *, force: bool = False) -> None:
    global _last_snapshot_at
    now = time.time()
    if not force and now - _last_snapshot_at < config.SNAPSHOT_INTERVAL_SEC:
        return
    _last_snapshot_at = now
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