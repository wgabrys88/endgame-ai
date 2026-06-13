from __future__ import annotations
import re
import time
from pathlib import Path
from typing import Any, Protocol

import config
import log


class Agent(Protocol):
    name: str
    reads: list[str]
    def run(self, ctx: dict[str, Any]) -> dict[str, Any]: ...


def plan_progress(ctx: dict[str, Any]) -> float:
    steps: list[dict[str, Any]] = ctx.get("plan", [])
    if not steps:
        return 0.0
    done = sum(1 for s in steps if s.get("status") == "done")
    return done / len(steps)


_RUNTIME_ERROR_MARKERS: tuple[str, ...] = (
    "NameError", "AttributeError", "ImportError", "SyntaxError", "TypeError",
    "KeyError", "FileNotFoundError", "ModuleNotFoundError", "IndentationError",
    "is not defined", "PLAN REJECTED", "not Python", "timeout after",
)


def _text_has_runtime_error(text: str) -> bool:
    if not text:
        return False
    return any(marker in text for marker in _RUNTIME_ERROR_MARKERS)


def _runtime_error_signal(ctx: dict[str, Any]) -> bool:
    if _text_has_runtime_error(str(ctx.get("last_observation", ""))):
        return True
    for entry in list(ctx.get("history", []))[-6:]:
        if not entry.get("ok") and _text_has_runtime_error(str(entry.get("obs", ""))):
            return True
    return False


def _mutator_math_gate(ctx: dict[str, Any]) -> bool:
    return (
        float(ctx.get("stagnation", 0)) >= config.MUTATOR_MATH_STAG_MIN
        or float(ctx.get("pid_output", 0)) >= config.MUTATOR_PID_MIN
        or float(ctx.get("energy", 1)) >= config.MUTATOR_ENERGY_MIN
    )


# --- Denial tracking (simple) ---

DENIAL_DECAY_SECS = 60.0
DENIAL_MAX = 10


def _add_denial(denied: list[dict[str, Any]], done_when: str) -> list[dict[str, Any]]:
    now = time.time()
    active = [d for d in denied if now - d.get("ts", 0) < DENIAL_DECAY_SECS]
    active.append({"dw": done_when[:120], "ts": now})
    return active[-DENIAL_MAX:]


def _is_blocked(denied: list[dict[str, Any]], done_when: str) -> bool:
    now = time.time()
    dw_low = done_when.lower()[:120]
    count = sum(1 for d in denied if now - d.get("ts", 0) < DENIAL_DECAY_SECS and d.get("dw", "").lower() == dw_low)
    return count >= 2


# --- Math Agents ---

class StagnationAgent:
    name = "stagnation"
    reads = ["plan", "progress_history", "consecutive_failures", "activity_events"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        progress = plan_progress(ctx)
        activity = int(ctx.get("activity_events", 0))
        history = (ctx.get("progress_history", []) + [progress])[-config.STAGNATION_CYCLES_WINDOW:]
        if len(history) < 3:
            stag = 0.0
        else:
            if history[-1] - history[-2] > 0.01:
                stag = 0.0
            elif history[-1] - history[0] > 0.01:
                stag = 0.3
            else:
                stag = 1.0
        failures = int(ctx.get("consecutive_failures", 0))
        stag = min(1.0, stag + min(failures * config.STAGNATION_FAILURE_WEIGHT, config.STAGNATION_FAILURE_CAP))
        if activity > 0:
            stag = max(0.0, stag - activity * 0.2)
        return {
            "writes": {"stagnation": stag, "progress_history": history, "activity_events": 0},
            "next": "lorenz", "phase": "stagnation",
            "data": {"stag": round(stag, 3), "progress": round(progress, 3)},
        }


class LorenzAgent:
    name = "lorenz"
    reads = ["lorenz_x", "lorenz_y", "lorenz_z", "stagnation"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        x = float(ctx.get("lorenz_x", 1.0))
        y = float(ctx.get("lorenz_y", 1.0))
        z = float(ctx.get("lorenz_z", 1.0))
        stag = float(ctx.get("stagnation", 0))
        prev_x, prev_y = x, y
        for _ in range(max(3, 1 + int(stag * config.LORENZ_STAG_STEPS_SCALE))):
            x += config.LORENZ_SIGMA * (y - x) * config.LORENZ_DT
            y += (x * (config.LORENZ_RHO - z) - y) * config.LORENZ_DT
            z += (x * y - config.LORENZ_BETA * z) * config.LORENZ_DT
        mag = (x*x + y*y + z*z) ** 0.5
        if mag > config.LORENZ_MAG_CAP:
            scale = config.LORENZ_MAG_CAP / mag
            x, y, z = x*scale, y*scale, z*scale
            mag = config.LORENZ_MAG_CAP
        wing = (prev_x * x < 0 or prev_y * y < 0) and stag >= config.LORENZ_WING_STAG_MIN
        eq = (config.LORENZ_BETA * (config.LORENZ_RHO - config.LORENZ_EQUILIBRIUM_OFFSET)) ** 0.5
        energy = mag / max(eq * 2, 1.0)
        return {
            "writes": {"lorenz_x": x, "lorenz_y": y, "lorenz_z": z, "energy": energy, "wing_crossed": wing},
            "next": "scheduler", "phase": "lorenz",
            "data": {"x": round(x, 2), "y": round(y, 2), "z": round(z, 2), "energy": round(energy, 2), "wing": wing},
        }


class PidAgent:
    name = "pid"
    reads = ["stagnation", "pid_integral", "pid_prev"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        stag = float(ctx.get("stagnation", 0))
        integral = float(ctx.get("pid_integral", 0))
        prev = float(ctx.get("pid_prev", 0))
        if stag <= config.PID_DEAD_ZONE:
            integral = max(0.0, integral - config.PID_INTEGRAL_DECAY)
        else:
            integral = min(integral + stag, config.PID_INTEGRAL_MAX)
        slope = stag - prev
        d_term = config.PID_KD * slope if abs(slope) > config.PID_DEAD_ZONE else 0.0
        output = max(0.0, config.PID_KP * stag + config.PID_KI * integral + d_term)
        return {
            "writes": {"pid_output": output, "pid_integral": integral, "pid_prev": stag},
            "next": "scheduler", "phase": "pid",
            "data": {"pid": round(output, 3)},
        }


# --- Scheduler ---

class SchedulerAgent:
    name = "scheduler"
    reads = [
        "stagnation", "wing_crossed", "energy", "pid_output", "consecutive_failures",
        "plan", "goal", "last_reflect_time", "done_when", "last_plan_reject_at",
        "last_observation", "history", "last_mutator_at",
    ]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        wing = bool(ctx.get("wing_crossed", False))
        energy = float(ctx.get("energy", 1))
        stag = float(ctx.get("stagnation", 0))
        pid = float(ctx.get("pid_output", 0))
        failures = int(ctx.get("consecutive_failures", 0))
        plan: list[dict[str, Any]] = ctx.get("plan", [])
        last_reflect = float(ctx.get("last_reflect_time", 0))
        writes: dict[str, Any] = {}
        now = time.time()

        reflect_due = (now - last_reflect) >= config.REFLECT_MIN_INTERVAL_SEC
        pid_gate = pid >= config.REFLECT_THRESHOLD and stag >= config.REFLECT_STAG_THRESHOLD
        stag_gate = stag >= config.REFLECT_STAG_THRESHOLD and failures >= config.REFLECT_FAILURE_MIN
        chaos_gate = energy >= config.CHAOS_ENERGY_THRESHOLD and stag >= config.REFLECT_STAG_THRESHOLD
        reflect_wanted = reflect_due and (pid_gate or stag_gate or chaos_gate)

        if not plan:
            replan_stuck = failures >= config.PLAN_REJECT_FAILURE_MIN and stag >= config.REFLECT_STAG_THRESHOLD
            if reflect_due and (reflect_wanted or replan_stuck):
                reason = "pid_gate" if pid_gate else ("stag_gate" if stag_gate or replan_stuck else "chaos_gate")
                writes["last_reflect_time"] = now
                if wing:
                    writes["wing_crossed"] = False
                writes["reflect_trigger"] = {"reason": reason, "stag": round(stag, 3), "pid": round(pid, 3), "energy": round(energy, 3), "failures": failures}
                return {"writes": writes, "next": "reflector", "phase": "schedule", "data": {"reason": reason}}
            last_reject = float(ctx.get("last_plan_reject_at", 0))
            if last_reject and (now - last_reject) < config.PLAN_REJECT_COOLDOWN_SEC:
                wait = round(config.PLAN_REJECT_COOLDOWN_SEC - (now - last_reject), 1)
                return {"writes": writes, "next": "done", "phase": "schedule", "data": {"reason": "plan_cooldown", "wait": wait}}
            return {"writes": writes, "next": "planner", "phase": "schedule", "data": {"reason": "need_plan"}}

        if all(s.get("status") == "done" for s in plan):
            return {"writes": writes, "next": "verifier", "phase": "schedule", "data": {"reason": "plan_complete"}}

        active = next((s for s in plan if s.get("status") == "active"), None)
        error_signal = _runtime_error_signal(ctx)
        mutator_due = (now - float(ctx.get("last_mutator_at", 0))) >= config.MUTATOR_MIN_INTERVAL_SEC
        if error_signal and mutator_due and failures >= config.MUTATOR_ERROR_MIN_FAILURES and _mutator_math_gate(ctx) and not active:
            writes["last_mutator_at"] = now
            writes["mutator_trigger"] = {"reason": "error_math", "stag": round(stag, 3), "failures": failures, "last_error": str(ctx.get("last_observation", ""))[:160]}
            return {"writes": writes, "next": "mutator", "phase": "schedule", "data": {"reason": "mutator_error_math"}}

        if reflect_wanted and plan and all(s.get("status") in ("done", "failed") for s in plan):
            writes["plan"] = []
            writes["last_reflect_time"] = now
            return {"writes": writes, "next": "planner", "phase": "schedule", "data": {"reason": "need_plan"}}

        if reflect_wanted:
            reason = "pid_gate" if pid_gate else ("stag_gate" if stag_gate else "chaos_gate")
            writes["last_reflect_time"] = now
            if wing:
                writes["wing_crossed"] = False
            writes["reflect_trigger"] = {"reason": reason, "stag": round(stag, 3), "pid": round(pid, 3), "energy": round(energy, 3), "failures": failures}
            return {"writes": writes, "next": "reflector", "phase": "schedule", "data": {"reason": reason}}

        if wing:
            writes["wing_crossed"] = False
            writes["pid_integral"] = 0.0
            return {"writes": writes, "next": "planner", "phase": "schedule", "data": {"reason": "wing_cross"}}

        if active:
            return {"writes": writes, "next": "actor", "phase": "schedule", "data": {"reason": "execute"}}

        pending = next((s for s in plan if s.get("status") == "pending"), None)
        if pending:
            pending["status"] = "active"
            return {"writes": {"plan": plan}, "next": "actor", "phase": "schedule", "data": {"reason": "advance"}}

        return {"writes": writes, "next": "planner", "phase": "schedule", "data": {"reason": "stuck"}}


# --- Observer ---

class ObserverAgent:
    name = "observer"
    reads = ["screen"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        from observer import observe
        try:
            obs = observe()
        except Exception as e:
            return {"writes": {}, "next": "scheduler", "phase": "observe", "data": {"error": str(e)}}
        return {
            "writes": {
                "screen": obs.context_text,
                "screen_elements": obs.book,
                "focused_window": obs.focused_title,
                "desktop_summary": obs.desktop_summary,
            },
            "next": "scheduler", "phase": "observe",
            "data": {"focused": obs.focused_title},
        }


# --- Planner ---

def _reject_plan(ctx: dict[str, Any], reason: str) -> dict[str, Any]:
    log.emit("plan.rejected", {"reason": reason})
    history = list(ctx.get("history", []))
    history.append({"verb": "plan", "ok": False, "obs": f"REJECTED: {reason}"})
    history = history[-config.MAX_HISTORY:]
    return {
        "writes": {
            "consecutive_failures": int(ctx.get("consecutive_failures", 0)) + 1,
            "last_observation": f"PLAN REJECTED: {reason}",
            "history": history, "plan": [], "done_when": "",
            "last_plan_reject_at": time.time(),
        },
        "next": "stagnation", "phase": "plan", "data": {"mode": "rejected", "reason": reason},
    }


class PlannerAgent:
    name = "planner"
    reads = [
        "goal", "plan", "screen", "desktop_summary", "focused_window", "history",
        "consecutive_failures", "stagnation", "energy", "completed", "last_observation", "denied_goals",
    ]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        from llm import call_llm
        context = _render_context(ctx, "planner")
        system = _load_planner_system()
        log.emit("planner.pending", {"goal": str(ctx.get("goal", ""))[:80]})
        try:
            raw = call_llm(system, context, "planner", max_tokens=config.BUDGET_PLANNER_OUT)
        except Exception as e:
            log.emit("planner.error", {"error": str(e)})
            return {"writes": {"consecutive_failures": int(ctx.get("consecutive_failures", 0)) + 1}, "next": "stagnation", "phase": "planner.error", "data": {"error": str(e)}}
        parsed = _extract_json(raw, ["mode", "sequence"])
        parsed.setdefault("done_when", "output produced")
        sequence: list[Any] = parsed.get("sequence", [])
        done_when = str(parsed.get("done_when", ""))
        denied_goals: list[dict[str, Any]] = list(ctx.get("denied_goals", []))
        if done_when and _is_blocked(denied_goals, done_when):
            return _reject_plan(ctx, "done_when denied too many times - try something different")
        mode = str(parsed.get("mode", "direct"))
        if mode == "done" or not sequence:
            if str(ctx.get("goal", "")).strip() and not list(ctx.get("completed", [])):
                return _reject_plan(ctx, "cannot declare done before any GOAL progress")
            if list(ctx.get("completed", [])):
                return {"writes": {}, "next": "halt", "phase": "plan", "data": {"mode": "done"}}
            return {"writes": {}, "next": "verifier", "phase": "plan", "data": {"mode": "done"}}
        from python_code import validate_python
        steps: list[dict[str, str]] = []
        code_errors: list[str] = []
        for i, s in enumerate(sequence[:config.MAX_PLAN_STEPS]):
            raw_code = _step_code(s)
            ok, code, err = validate_python(raw_code)
            if not ok:
                code_errors.append(err)
                continue
            steps.append({"code": code, "status": "active" if i == 0 else "pending"})
        if not steps:
            return _reject_plan(ctx, code_errors[0] if code_errors else "empty sequence")
        return {
            "writes": {"plan": steps, "done_when": done_when, "consecutive_failures": 0, "progress_history": []},
            "next": "actor", "phase": "plan",
            "data": {"mode": mode, "steps": len(steps), "done_when": done_when},
        }


# --- Actor ---

class ActorAgent:
    name = "actor"
    reads = ["plan", "history", "consecutive_failures", "goal"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        from actions import run_python
        plan: list[dict[str, Any]] = ctx.get("plan", [])
        active = next((s for s in plan if s.get("status") == "active"), None)
        if not active:
            return {"writes": {}, "next": "planner", "phase": "actor.error", "data": {"error": "no active step"}}
        code, active, code_errors = _combine_plan_code(plan)
        if not code:
            err = code_errors[0] if code_errors else "empty plan"
            history = list(ctx.get("history", []))
            history.append({"verb": "python", "ok": False, "obs": err})
            active["status"] = "failed"
            return {"writes": {"plan": plan, "history": history[-config.MAX_HISTORY:], "consecutive_failures": int(ctx.get("consecutive_failures", 0)) + 1, "last_observation": err}, "next": "planner", "phase": "actor", "data": {"ok": False, "obs": err}}
        result = run_python(code)
        history = list(ctx.get("history", []))
        history.append({"verb": result.verb, "ok": result.success, "obs": result.observation})
        history = history[-config.MAX_HISTORY:]
        if result.success:
            for step in plan:
                if step.get("status") in ("active", "pending"):
                    step["status"] = "done"
            return {"writes": {"plan": plan, "history": history, "consecutive_failures": 0, "last_observation": result.observation}, "next": "stagnation", "phase": "actor", "data": {"ok": True, "obs": result.observation}}
        active["status"] = "failed"
        failures = int(ctx.get("consecutive_failures", 0)) + 1
        return {"writes": {"plan": plan, "history": history, "consecutive_failures": failures, "last_observation": result.observation}, "next": "planner", "phase": "actor", "data": {"ok": False, "obs": result.observation}}


# --- Verifier ---

class VerifierAgent:
    name = "verifier"
    reads = ["goal", "screen", "history", "plan", "desktop_summary", "done_when", "completed", "last_observation", "denied_goals"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        from llm import call_llm
        done_when = str(ctx.get("done_when", ""))
        denied_goals: list[dict[str, Any]] = list(ctx.get("denied_goals", []))
        context = _render_context(ctx, "verifier")
        system = _load_prompt("verifier")
        try:
            raw = call_llm(system, context, "verifier", max_tokens=config.BUDGET_VERIFIER_OUT)
        except Exception as e:
            log.emit("verifier.error", {"error": str(e)})
            return {"writes": {}, "next": "stagnation", "phase": "verifier.error", "data": {"error": str(e)}}
        parsed = _extract_json(raw, ["verdict"])
        verdict = str(parsed.get("verdict", "denied"))
        evidence = str(parsed.get("evidence", ""))
        if verdict == "confirmed":
            return {"writes": {"denied_goals": denied_goals, "fission_approved": False}, "next": "fission_judge", "phase": "verify", "data": {"verdict": "confirmed", "evidence": evidence}}
        denied_goals = _add_denial(denied_goals, done_when)
        return {"writes": {"plan": [], "done_when": "", "consecutive_failures": 0, "denied_goals": denied_goals}, "next": "planner", "phase": "verify", "data": {"verdict": "denied", "evidence": evidence}}


# --- Fission Judge ---

class FissionJudgeAgent:
    name = "fission_judge"
    reads = ["goal", "done_when", "last_observation", "history", "completed", "consecutive_failures", "denied_goals"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        from llm import call_llm
        done_when = str(ctx.get("done_when", ""))
        denied_goals: list[dict[str, Any]] = list(ctx.get("denied_goals", []))
        failures = int(ctx.get("consecutive_failures", 0))
        context = "MODE: FISSION_REVIEW\n\n" + _render_context(ctx, "fission_judge")
        system = _load_prompt("reflector")
        try:
            raw = call_llm(system, context, "fission_judge", max_tokens=config.BUDGET_FISSION_JUDGE_OUT)
        except Exception as e:
            log.emit("fission_judge.error", {"error": str(e)})
            return {"writes": {}, "next": "stagnation", "phase": "fission_judge.error", "data": {"error": str(e)}}
        parsed = _extract_json(raw, ["verdict", "diagnosis", "suggestion", "rule"])
        verdict = str(parsed.get("verdict", "deny")).lower()
        diagnosis = str(parsed.get("diagnosis", ""))
        rule = str(parsed.get("rule", ""))
        if rule.strip():
            _apply_mutation("planner", rule)
            _write_lesson(rule)
        if verdict == "credit":
            return {"writes": {"fission_approved": True, "activity_events": 1}, "next": "done", "phase": "fission_judge", "data": {"verdict": verdict, "diagnosis": diagnosis}}
        denied_goals = _add_denial(denied_goals, done_when)
        log.emit("fission_blocked", {"reason": "llm_deny", "diagnosis": diagnosis[:160]})
        return {"writes": {"plan": [], "done_when": "", "fission_approved": False, "consecutive_failures": failures + 1, "denied_goals": denied_goals}, "next": "stagnation", "phase": "fission_judge", "data": {"verdict": verdict, "diagnosis": diagnosis}}


# --- Reflector ---

class ReflectorAgent:
    name = "reflector"
    reads = [
        "goal", "plan", "screen", "desktop_summary", "focused_window", "history",
        "stagnation", "pid_output", "energy", "reflect_trigger", "completed", "last_observation",
    ]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        from llm import call_llm
        context = "MODE: STAGNATION_REFLECT\n\n" + _render_context(ctx, "reflector")
        system = _load_prompt("reflector")
        failures = int(ctx.get("consecutive_failures", 0))
        try:
            raw = call_llm(system, context, "reflector", max_tokens=config.BUDGET_REFLECTOR_OUT)
        except Exception as e:
            log.emit("reflector.error", {"error": str(e)})
            return {"writes": {}, "next": "stagnation", "phase": "reflector.error", "data": {"error": str(e)}}
        parsed = _extract_json(raw, ["diagnosis", "suggestion", "rule"])
        diagnosis = str(parsed.get("diagnosis", ""))
        rule = str(parsed.get("rule", ""))
        if rule.strip():
            _apply_mutation("planner", rule)
            _write_lesson(rule)
            import os as _os3
            personality = _os3.environ.get("ENDGAME_PERSONALITY", "")
            if personality:
                _apply_personality_evolution(personality, rule)
        if failures >= config.MUTATOR_ESCALATION_FAILURES or (failures >= config.MUTATOR_ERROR_MIN_FAILURES and _runtime_error_signal(ctx)):
            return {"writes": {"pid_integral": 0.0, "activity_events": 1}, "next": "mutator", "phase": "reflect", "data": {"diagnosis": diagnosis, "escalate": "mutator"}}
        plan_steps = ctx.get("plan", [])
        retry = next((s for s in plan_steps if s.get("status") == "active"), None)
        return {"writes": {"pid_integral": 0.0, "consecutive_failures": 0, "activity_events": 1}, "next": "actor" if retry else "stagnation", "phase": "reflect", "data": {"diagnosis": diagnosis, "rule": rule}}


# --- Mutator ---

_PLUGIN_FILENAME_RE = re.compile(r"^[a-z0-9_]+\.py$")


class MutatorAgent:
    name = "mutator"
    reads = ["goal", "plan", "history", "stagnation", "energy", "consecutive_failures", "completed"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        from llm import call_llm
        import py_compile
        context = _render_context(ctx, "mutator")
        if _runtime_error_signal(ctx):
            context += "\n\nRUNTIME ERRORS: planner/actor Python failed — write a plugin that helps recover or auto-fix."
        system = _load_prompt("mutator")
        if not system:
            return {"writes": {}, "next": "stagnation", "phase": "mutator.skip", "data": {"reason": "no prompt"}}
        try:
            raw = call_llm(system, context, "mutator", max_tokens=config.BUDGET_MUTATOR_OUT)
        except Exception as e:
            log.emit("mutator.error", {"error": str(e)})
            return {"writes": {}, "next": "stagnation", "phase": "mutator.error", "data": {"error": str(e)}}
        parsed = _extract_json(raw, ["action", "filename", "content"])
        action = str(parsed.get("action", "none"))
        filename = str(parsed.get("filename", ""))
        content = str(parsed.get("content", ""))
        if action == "none" or not filename or not content:
            return {"writes": {}, "next": "stagnation", "phase": "mutator", "data": {"action": "none"}}
        if not _PLUGIN_FILENAME_RE.match(filename):
            return {"writes": {}, "next": "stagnation", "phase": "mutator", "data": {"action": "rejected", "reason": "invalid filename"}}
        if "def run(" not in content:
            return {"writes": {}, "next": "stagnation", "phase": "mutator", "data": {"action": "rejected", "reason": "no run()"}}
        target = config.PLUGINS_DIR / filename
        config.PLUGINS_DIR.mkdir(exist_ok=True)
        target.write_text(content, encoding="utf-8")
        try:
            py_compile.compile(str(target), doraise=True)
        except py_compile.PyCompileError as e:
            target.unlink(missing_ok=True)
            return {"writes": {}, "next": "stagnation", "phase": "mutator", "data": {"action": "rejected", "reason": "syntax error"}}
        log.emit("mutator", {"action": action, "filename": filename})
        return {"writes": {"activity_events": 1}, "next": "stagnation", "phase": "mutator", "data": {"action": action, "filename": filename}}


# --- Context rendering (no truncation) ---

def _render_context(ctx: dict[str, Any], role: str) -> str:
    fields = config.CONTEXT_POLICY.get(role, [])
    parts: list[str] = []
    for f in fields:
        text = _render_field(ctx, f)
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def _render_field(ctx: dict[str, Any], field: str) -> str:
    match field:
        case "goal":
            goal = str(ctx.get("goal", ""))
            return f"GOAL: {goal}" if goal else ""
        case "desktop":
            parts: list[str] = []
            fw = str(ctx.get("focused_window", "")).strip()
            if fw:
                parts.append(f"FOCUSED WINDOW: {fw}")
            ds = str(ctx.get("desktop_summary", "")).strip()
            if ds:
                parts.append(f"DESKTOP:\n{ds}")
            screen = str(ctx.get("screen", "")).strip()
            if screen:
                parts.append(f"SCREEN ELEMENTS:\n{screen}")
            return "\n\n".join(parts)
        case "instruction":
            return ""
        case "plan":
            plan: list[dict[str, Any]] = ctx.get("plan", [])
            if not plan:
                return ""
            lines = ["PLAN:"]
            for i, step in enumerate(plan):
                status = step.get("status", "pending")
                marker = "✓ " if status == "done" else ">>> " if status == "active" else ""
                snippet = str(step.get("code", "")).replace("\n", " ")
                lines.append(f"  {marker}{snippet}")
            return "\n".join(lines)
        case "history":
            recent = list(ctx.get("history", []))[-8:]
            if not recent:
                return ""
            lines = ["HISTORY:"]
            for h in recent:
                ok = "✓" if h.get("ok") else "✗"
                lines.append(f"  {ok} {h.get('verb', '')}: {h.get('obs', '')}")
            return "\n".join(lines)
        case "failures":
            f_count = int(ctx.get("consecutive_failures", 0))
            return f"FAILURES: {f_count} consecutive. Try different approach." if f_count else ""
        case "last_observation":
            obs = str(ctx.get("last_observation", ""))
            return f"LAST_RESULT: {obs}" if obs else ""
        case "denied_goals":
            now = time.time()
            active = [d for d in ctx.get("denied_goals", []) if now - d.get("ts", 0) < DENIAL_DECAY_SECS]
            blocked = list({d["dw"] for d in active if sum(1 for x in active if x.get("dw") == d.get("dw")) >= 2})
            if not blocked:
                return ""
            return "BLOCKED (denied 2x+):\n" + "\n".join(f"  - {b}" for b in blocked[:5])
        case "completed":
            completed = ctx.get("completed", [])
            if not completed:
                return ""
            lines = ["COMPLETED (no repeat credit):"]
            for c in completed[-6:]:
                lines.append(f"  - {c}")
            return "\n".join(lines)
        case "similarity":
            done_when = str(ctx.get("done_when", ""))
            completed = list(ctx.get("completed", []))
            if not done_when or not completed:
                return ""
            return f"DONE_WHEN: {done_when}\nCOMPLETED has {len(completed)} entries — judge if this is genuinely new value."
        case "hints":
            return ""
        case "bus":
            from comms import agent_id, format_bus_context
            return format_bus_context(config.CONTEXT_BUS_MAX, for_agent=agent_id())
        case "done_when":
            dw = ctx.get("done_when", "")
            return f"DONE_WHEN: {dw}" if dw else ""
        case "trigger":
            trig = ctx.get("mutator_trigger") or ctx.get("reflect_trigger", {})
            if not isinstance(trig, dict) or not trig:
                return ""
            parts_t = ["TRIGGER:"]
            reason = str(trig.get("reason", ""))
            if reason:
                parts_t.append(reason.replace("_", " "))
            failures = int(trig.get("failures", 0))
            if failures:
                parts_t.append(f"Failed {failures} time(s).")
            last_error = str(trig.get("last_error", "")).strip()
            if last_error:
                parts_t.append(f"Error: {last_error}")
            return " ".join(parts_t)
        case _:
            return ""


# --- Helpers ---

def _step_code(s: Any) -> str:
    if isinstance(s, dict):
        for key in ("code", "text", "exec"):
            if key in s and str(s[key]).strip():
                return str(s[key]).strip()
        return ""
    if isinstance(s, str):
        text = s.strip()
        if text.lower().startswith("exec:"):
            return text[5:].lstrip("\n")
        if text.lower().startswith("exec "):
            return text[5:].lstrip()
        return text
    return str(s).strip()


def _combine_plan_code(plan: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | None, list[str]]:
    blocks: list[str] = []
    active: dict[str, Any] | None = None
    errors: list[str] = []
    for step in plan:
        status = str(step.get("status", ""))
        if status == "failed":
            continue
        if status not in ("active", "pending", "done"):
            continue
        if status == "active" and active is None:
            active = step
        raw = str(step.get("code", "")).strip()
        if not raw:
            continue
        from python_code import validate_python
        ok, code, err = validate_python(raw)
        if not ok:
            errors.append(err)
            continue
        blocks.append(code)
    return "\n\n".join(blocks), active, errors


def _load_prompt(role: str) -> str:
    path = config.PROMPTS_DIR / f"{role}.txt"
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def _load_planner_system() -> str:
    import os
    personality = os.environ.get("ENDGAME_PERSONALITY", "").strip()
    if personality == "gui_operator":
        gui_path = config.PROMPTS_DIR / "planner_gui.txt"
        if gui_path.exists():
            return gui_path.read_text(encoding="utf-8").strip()
    return _load_prompt("planner")


def _extract_json(raw: str, required: list[str]) -> dict[str, Any]:
    import json
    stripped = raw.strip()
    if stripped.startswith("{"):
        try:
            result = json.loads(stripped)
            if isinstance(result, dict) and all(f in result for f in required):
                return result
        except json.JSONDecodeError:
            pass
    depth = 0
    start = -1
    candidates: list[str] = []
    for i, ch in enumerate(raw):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start != -1:
                candidates.append(raw[start:i + 1])
                start = -1
    for candidate in reversed(candidates):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict) and all(f in parsed for f in required):
                return parsed
        except json.JSONDecodeError:
            continue
    for candidate in reversed(candidates):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    raise ValueError(f"no JSON in response: {raw[:200]}")


def _write_lesson(lesson: str) -> None:
    import lessons
    lessons.record(lesson)


_ELEMENT_ID_RE = re.compile(r"\[\d+\]")


def _clean_mutation_text(text: str) -> str:
    clean = text.strip()
    for prefix in ("RULE:", "EVOLVE:"):
        if clean.upper().startswith(prefix):
            clean = clean[len(prefix):].strip()
    return clean


def _reject_mutation(clean_text: str) -> bool:
    if not clean_text:
        return True
    if _ELEMENT_ID_RE.search(clean_text):
        return True
    vague = ("consistency", "foundation", "stable quality", "future success", "strong base")
    return any(v in clean_text.lower() for v in vague)


def _apply_mutation(target: str, append_text: str) -> None:
    path = config.PROMPTS_DIR / f"{target}.txt"
    if not path.exists():
        return
    clean_text = _clean_mutation_text(append_text)
    if _reject_mutation(clean_text):
        return
    current = path.read_text(encoding="utf-8")
    rules = [block.strip() for block in current.split("\n\n") if block.strip().startswith("RULE:")]
    if len(rules) >= config.PROMPT_MAX_RULES:
        parts = current.split("RULE:", 1)
        header = parts[0] if parts else current
        kept = rules[-(config.PROMPT_MAX_RULES - 1):]
        current = header.rstrip() + "\n\n" + "\n\n".join(kept)
    new_content = current.rstrip() + "\n\nRULE: " + clean_text + "\n"
    path.write_text(new_content, encoding="utf-8")
    log.emit("mutation", {"target": target, "appended": clean_text})


def _apply_personality_evolution(personality: str, append_text: str) -> None:
    path = config.PROMPTS_DIR / "personalities" / f"{personality}.txt"
    if not path.exists():
        return
    clean_text = _clean_mutation_text(append_text)
    if _reject_mutation(clean_text):
        return
    current = path.read_text(encoding="utf-8")
    evolutions = [line.strip() for line in current.split("\n") if line.strip().startswith("EVOLVE:")]
    if len(evolutions) >= config.PERSONALITY_MAX_EVOLUTIONS:
        header = current.split("EVOLVE:", 1)[0].strip()
        kept = evolutions[-(config.PERSONALITY_MAX_EVOLUTIONS - 1):]
        current = header + "\n" + "\n".join(kept)
    new_content = current.rstrip() + f"\nEVOLVE: {clean_text}\n"
    path.write_text(new_content, encoding="utf-8")
    log.emit("personality.evolve", {"personality": personality, "appended": clean_text})
