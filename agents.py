"""Unified agent system — every entity runs the same protocol.

Agent protocol: name, reads (board keys), run(ctx) -> {writes, next, phase, data}.
Math agents, LLM agents, observers — all identical interface.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

import config
import log

# --- Shared utilities ---

DENIAL_DECAY_SECS = 60.0

_RUNTIME_ERRORS = ("NameError", "AttributeError", "ImportError", "SyntaxError", "TypeError",
                   "KeyError", "FileNotFoundError", "ModuleNotFoundError", "IndentationError",
                   "is not defined", "PLAN REJECTED", "not Python", "timeout after")


def _has_error(text: str) -> bool:
    return any(m in text for m in _RUNTIME_ERRORS) if text.strip() else False


def _error_signal(ctx: dict[str, Any]) -> bool:
    if _has_error(str(ctx.get("last_observation", ""))):
        return True
    return any(_has_error(str(e.get("obs", ""))) for e in list(ctx.get("history", []))[-6:] if not e.get("ok"))


def _add_denial(denied: list[dict[str, Any]], done_when: str) -> list[dict[str, Any]]:
    now = time.time()
    active = [d for d in denied if now - d.get("ts", 0) < DENIAL_DECAY_SECS]
    active.append({"dw": done_when[:120], "ts": now})
    return active[-10:]


def _is_blocked(denied: list[dict[str, Any]], done_when: str) -> bool:
    now = time.time()
    dw = done_when.lower()[:120]
    return sum(1 for d in denied if now - d.get("ts", 0) < DENIAL_DECAY_SECS and d.get("dw", "").lower() == dw) >= 2


def _append_history(history: list[dict[str, Any]], entry: dict[str, Any]) -> list[dict[str, Any]]:
    history.append(entry)
    return history[-config.MAX_HISTORY:]


def _extract_json(raw: str, required: list[str]) -> dict[str, Any]:
    stripped = raw.strip()
    if stripped.startswith("{"):
        try:
            r = json.loads(stripped)
            if all(f in r for f in required):
                return r
        except json.JSONDecodeError:
            pass
    depth = start = 0
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
    for c in reversed(candidates):
        try:
            p = json.loads(c)
            if isinstance(p, dict) and all(f in p for f in required):
                return p
        except json.JSONDecodeError:
            continue
    for c in reversed(candidates):
        try:
            p = json.loads(c)
            if isinstance(p, dict):
                return p
        except json.JSONDecodeError:
            continue
    raise ValueError(f"no JSON: {raw[:200]}")


def _load_prompt(role: str) -> str:
    path = config.PROMPTS_DIR / f"{role}.txt"
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def _reject_plan(ctx: dict[str, Any], reason: str) -> dict[str, Any]:
    log.emit("plan.rejected", {"reason": reason[:120]})
    history = _append_history(list(ctx.get("history", [])), {"verb": "plan", "ok": False, "obs": f"REJECTED: {reason}"})
    return {
        "writes": {"consecutive_failures": int(ctx.get("consecutive_failures", 0)) + 1,
                   "last_observation": f"PLAN REJECTED: {reason}", "history": history, "plan": [], "done_when": "",
                   "last_plan_reject_at": time.time()},
        "next": "stagnation", "phase": "plan", "data": {"mode": "rejected", "reason": reason},
    }


# --- Math agents ---

class StagnationAgent:
    name = "stagnation"
    reads = ["plan", "progress_history", "consecutive_failures", "activity_events"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        plan = ctx.get("plan", [])
        done = sum(1 for s in plan if s.get("status") == "done")
        progress = done / len(plan) if plan else 0.0
        history = (ctx.get("progress_history", []) + [progress])[-config.STAGNATION_CYCLES_WINDOW:]
        if len(history) < config.STAGNATION_CYCLES_WINDOW // 2:
            stag = 0.0
        elif history[-1] - history[-2] > 0.01:
            stag = 0.0
        elif history[-1] - history[0] > 0.01:
            stag = 0.3
        else:
            # Ramp: proportion of window filled with no progress
            filled = len(history) / config.STAGNATION_CYCLES_WINDOW
            stag = min(1.0, filled * 0.8)
        failures = int(ctx.get("consecutive_failures", 0))
        stag = min(1.0, stag + min(failures * config.STAGNATION_FAILURE_WEIGHT, config.STAGNATION_FAILURE_CAP))
        if int(ctx.get("activity_events", 0)) > 0:
            stag = max(0.0, stag - 0.2)
        return {"writes": {"stagnation": stag, "progress_history": history, "activity_events": 0},
                "next": "lorenz", "phase": "stagnation", "data": {"stag": round(stag, 3)}}


class LorenzAgent:
    name = "lorenz"
    reads = ["lorenz_x", "lorenz_y", "lorenz_z", "stagnation"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        x, y, z = (float(ctx.get(k, 1.0)) for k in ("lorenz_x", "lorenz_y", "lorenz_z"))
        stag = float(ctx.get("stagnation", 0))
        prev_x = x
        for _ in range(max(3, 1 + int(stag * config.LORENZ_STAG_STEPS_SCALE))):
            x += config.LORENZ_SIGMA * (y - x) * config.LORENZ_DT
            y += (x * (config.LORENZ_RHO - z) - y) * config.LORENZ_DT
            z += (x * y - config.LORENZ_BETA * z) * config.LORENZ_DT
        mag = (x*x + y*y + z*z) ** 0.5
        if mag > config.LORENZ_MAG_CAP:
            s = config.LORENZ_MAG_CAP / mag
            x, y, z = x*s, y*s, z*s
            mag = config.LORENZ_MAG_CAP
        wing = (prev_x * x < 0) and stag >= config.LORENZ_WING_STAG_MIN
        eq = (config.LORENZ_BETA * (config.LORENZ_RHO - config.LORENZ_EQUILIBRIUM_OFFSET)) ** 0.5
        energy = mag / max(eq * 2, 1.0)
        return {"writes": {"lorenz_x": x, "lorenz_y": y, "lorenz_z": z, "energy": energy, "wing_crossed": wing},
                "next": "scheduler", "phase": "lorenz", "data": {"energy": round(energy, 2), "wing": wing}}


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
        return {"writes": {"pid_output": output, "pid_integral": integral, "pid_prev": stag},
                "next": "scheduler", "phase": "pid", "data": {"pid": round(output, 3)}}


# --- Scheduler ---

class SchedulerAgent:
    name = "scheduler"
    reads = ["stagnation", "wing_crossed", "energy", "pid_output", "consecutive_failures",
             "plan", "goal", "last_reflect_time", "done_when", "last_plan_reject_at",
             "last_observation", "history", "last_mutator_at", "completed"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        stag = float(ctx.get("stagnation", 0))
        pid = float(ctx.get("pid_output", 0))
        energy = float(ctx.get("energy", 1))
        failures = int(ctx.get("consecutive_failures", 0))
        plan = ctx.get("plan", [])
        now = time.time()
        last_reflect = float(ctx.get("last_reflect_time", 0))
        writes: dict[str, Any] = {}

        reflect_due = (now - last_reflect) >= config.REFLECT_MIN_INTERVAL_SEC
        reflect_wanted = reflect_due and (
            (pid >= config.REFLECT_THRESHOLD and stag >= config.REFLECT_STAG_THRESHOLD)
            or (stag >= config.REFLECT_STAG_THRESHOLD and failures >= config.REFLECT_FAILURE_MIN)
            or (energy >= config.CHAOS_ENERGY_THRESHOLD and stag >= config.REFLECT_STAG_THRESHOLD)
        )

        # No plan — reflect or replan
        if not plan:
            if reflect_wanted or (reflect_due and failures >= config.PLAN_REJECT_FAILURE_MIN and stag >= config.REFLECT_STAG_THRESHOLD):
                writes["last_reflect_time"] = now
                writes["reflect_trigger"] = {"stag": round(stag, 3), "pid": round(pid, 3), "energy": round(energy, 3), "failures": failures}
                return {"writes": writes, "next": "reflector", "phase": "schedule", "data": {"reason": "reflect"}}
            last_reject = float(ctx.get("last_plan_reject_at", 0))
            if last_reject and (now - last_reject) < config.PLAN_REJECT_COOLDOWN_SEC:
                return {"writes": writes, "next": "done", "phase": "schedule", "data": {"reason": "plan_cooldown", "wait": round(config.PLAN_REJECT_COOLDOWN_SEC - (now - last_reject), 1)}}
            return {"writes": writes, "next": "planner", "phase": "schedule", "data": {"reason": "need_plan"}}

        # All steps done — verify
        if all(s.get("status") == "done" for s in plan):
            return {"writes": writes, "next": "verifier", "phase": "schedule", "data": {"reason": "plan_complete"}}

        # Error escalation to mutator
        mutator_due = (now - float(ctx.get("last_mutator_at", 0))) >= config.MUTATOR_MIN_INTERVAL_SEC
        active = next((s for s in plan if s.get("status") == "active"), None)
        if _error_signal(ctx) and mutator_due and failures >= config.MUTATOR_ERROR_MIN_FAILURES and not active:
            if stag >= config.MUTATOR_MATH_STAG_MIN or pid >= config.MUTATOR_PID_MIN or energy >= config.MUTATOR_ENERGY_MIN:
                writes["last_mutator_at"] = now
                writes["mutator_trigger"] = {"stag": round(stag, 3), "pid": round(pid, 3), "failures": failures, "last_error": str(ctx.get("last_observation", ""))[:160]}
                return {"writes": writes, "next": "mutator", "phase": "schedule", "data": {"reason": "mutator"}}

        # Reflect if stuck with a plan
        if reflect_wanted:
            writes["last_reflect_time"] = now
            writes["reflect_trigger"] = {"stag": round(stag, 3), "pid": round(pid, 3), "energy": round(energy, 3), "failures": failures}
            return {"writes": writes, "next": "reflector", "phase": "schedule", "data": {"reason": "reflect"}}

        # Wing cross — replan
        if ctx.get("wing_crossed"):
            writes["wing_crossed"] = False
            writes["pid_integral"] = 0.0
            return {"writes": writes, "next": "planner", "phase": "schedule", "data": {"reason": "wing_cross"}}

        # Execute
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
        return {"writes": {"screen": obs.context_text, "screen_elements": obs.book, "focused_window": obs.focused_title, "desktop_summary": obs.desktop_summary},
                "next": "scheduler", "phase": "observe", "data": {"focused": obs.focused_title}}


# --- Planner ---

class PlannerAgent:
    name = "planner"
    reads = ["goal", "plan", "screen", "desktop_summary", "focused_window", "history",
             "consecutive_failures", "stagnation", "energy", "completed", "last_observation", "denied_goals"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        from llm import call_llm
        from python_code import validate_python
        context = _render_context(ctx, "planner")
        system = _load_planner_system()
        log.emit("planner.pending", {"goal": str(ctx.get("goal", ""))[:80]})
        try:
            raw = call_llm(system, context, "planner")
        except Exception as e:
            log.emit("planner.error", {"error": str(e)})
            return {"writes": {"consecutive_failures": int(ctx.get("consecutive_failures", 0)) + 1}, "next": "stagnation", "phase": "planner.error", "data": {"error": str(e)}}
        parsed = _extract_json(raw, ["mode", "sequence"])
        parsed.setdefault("done_when", "output produced")
        sequence = parsed.get("sequence", [])
        done_when = str(parsed.get("done_when", ""))
        denied = list(ctx.get("denied_goals", []))
        if done_when and _is_blocked(denied, done_when):
            return _reject_plan(ctx, "done_when denied too many times")
        if parsed.get("mode") == "done" or not sequence:
            if ctx.get("completed"):
                return {"writes": {}, "next": "halt", "phase": "plan", "data": {"mode": "done"}}
            return _reject_plan(ctx, "cannot declare done before progress")
        steps: list[dict[str, str]] = []
        for i, s in enumerate(sequence[:config.MAX_PLAN_STEPS]):
            raw_code = _step_code(s)
            ok, code, err = validate_python(raw_code)
            if ok:
                steps.append({"code": code, "status": "active" if i == 0 else "pending"})
        if not steps:
            return _reject_plan(ctx, "no valid Python steps")
        return {"writes": {"plan": steps, "done_when": done_when, "consecutive_failures": 0, "progress_history": []},
                "next": "actor", "phase": "plan", "data": {"mode": "direct", "steps": len(steps), "done_when": done_when}}


# --- Actor ---

class ActorAgent:
    name = "actor"
    reads = ["plan", "history", "consecutive_failures", "goal"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        from actions import run_python
        from python_code import validate_python
        plan = ctx.get("plan", [])
        active = next((s for s in plan if s.get("status") == "active"), None)
        if not active:
            return {"writes": {}, "next": "planner", "phase": "actor.error", "data": {"error": "no active step"}}
        # Combine all pending steps into one subprocess
        blocks = []
        for step in plan:
            if step.get("status") in ("active", "pending", "done"):
                raw = str(step.get("code", "")).strip()
                if raw:
                    ok, code, _ = validate_python(raw)
                    if ok:
                        blocks.append(code)
        code = "\n\n".join(blocks)
        if not code:
            return {"writes": {}, "next": "planner", "phase": "actor.error", "data": {"error": "empty code"}}
        result = run_python(code)
        history = _append_history(list(ctx.get("history", [])), {"verb": result.verb, "ok": result.success, "obs": result.observation})
        if result.success:
            for s in plan:
                if s.get("status") in ("active", "pending"):
                    s["status"] = "done"
            return {"writes": {"plan": plan, "history": history, "consecutive_failures": 0, "last_observation": result.observation},
                    "next": "stagnation", "phase": "actor", "data": {"ok": True, "obs": result.observation}}
        active["status"] = "failed"
        failures = int(ctx.get("consecutive_failures", 0)) + 1
        return {"writes": {"plan": plan, "history": history, "consecutive_failures": failures, "last_observation": result.observation},
                "next": "planner", "phase": "actor", "data": {"ok": False, "obs": result.observation}}


# --- Verifier ---

class VerifierAgent:
    name = "verifier"
    reads = ["goal", "history", "plan", "done_when", "completed", "last_observation", "denied_goals", "consecutive_failures"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        from llm import call_llm
        done_when = str(ctx.get("done_when", ""))
        denied = list(ctx.get("denied_goals", []))
        context = _render_context(ctx, "verifier")
        system = _load_prompt("verifier")
        try:
            raw = call_llm(system, context, "verifier")
        except Exception as e:
            return {"writes": {}, "next": "stagnation", "phase": "verifier.error", "data": {"error": str(e)}}
        parsed = _extract_json(raw, ["verdict"])
        verdict = str(parsed.get("verdict", "denied"))
        evidence = str(parsed.get("evidence", ""))
        if verdict == "confirmed":
            return {"writes": {"denied_goals": denied, "fission_approved": False}, "next": "fission_judge", "phase": "verify", "data": {"verdict": "confirmed", "evidence": evidence}}
        denied = _add_denial(denied, done_when)
        return {"writes": {"plan": [], "done_when": "", "consecutive_failures": 0, "denied_goals": denied}, "next": "planner", "phase": "verify", "data": {"verdict": "denied", "evidence": evidence}}


# --- Fission Judge ---

class FissionJudgeAgent:
    name = "fission_judge"
    reads = ["goal", "done_when", "last_observation", "history", "completed", "consecutive_failures", "denied_goals"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        from llm import call_llm
        done_when = str(ctx.get("done_when", ""))
        denied = list(ctx.get("denied_goals", []))
        context = "MODE: FISSION_REVIEW\n\n" + _render_context(ctx, "fission_judge")
        system = _load_prompt("reflector")
        try:
            raw = call_llm(system, context, "fission_judge")
        except Exception as e:
            return {"writes": {}, "next": "stagnation", "phase": "fission_judge.error", "data": {"error": str(e)}}
        parsed = _extract_json(raw, ["verdict", "diagnosis", "suggestion", "rule"])
        verdict = str(parsed.get("verdict", "deny")).lower()
        rule = str(parsed.get("rule", ""))
        if rule.strip():
            _apply_mutation("planner", rule)
        if verdict == "credit":
            return {"writes": {"fission_approved": True, "activity_events": 1}, "next": "done", "phase": "fission_judge",
                    "data": {"verdict": "credit", "diagnosis": str(parsed.get("diagnosis", ""))[:200]}}
        denied = _add_denial(denied, done_when)
        return {"writes": {"plan": [], "done_when": "", "fission_approved": False, "consecutive_failures": int(ctx.get("consecutive_failures", 0)) + 1, "denied_goals": denied},
                "next": "stagnation", "phase": "fission_judge", "data": {"verdict": "deny", "diagnosis": str(parsed.get("diagnosis", ""))[:200]}}


# --- Reflector ---

class ReflectorAgent:
    name = "reflector"
    reads = ["goal", "plan", "screen", "desktop_summary", "focused_window", "history",
             "stagnation", "pid_output", "energy", "reflect_trigger", "completed", "last_observation",
             "consecutive_failures"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        from llm import call_llm
        import os
        context = "MODE: STAGNATION_REFLECT\n\n" + _render_context(ctx, "reflector")
        system = _load_prompt("reflector")
        try:
            raw = call_llm(system, context, "reflector")
        except Exception as e:
            return {"writes": {}, "next": "stagnation", "phase": "reflector.error", "data": {"error": str(e)}}
        parsed = _extract_json(raw, ["diagnosis", "suggestion", "rule"])
        rule = str(parsed.get("rule", ""))
        if rule.strip():
            _apply_mutation("planner", rule)
            personality = os.environ.get("ENDGAME_PERSONALITY", "")
            if personality:
                _apply_personality_evolution(personality, rule)
        failures = int(ctx.get("consecutive_failures", 0))
        if failures >= config.MUTATOR_ESCALATION_FAILURES or (failures >= config.MUTATOR_ERROR_MIN_FAILURES and _error_signal(ctx)):
            return {"writes": {"pid_integral": 0.0, "activity_events": 1}, "next": "mutator", "phase": "reflect",
                    "data": {"diagnosis": str(parsed.get("diagnosis", "")), "escalate": "mutator"}}
        return {"writes": {"pid_integral": 0.0, "consecutive_failures": 0, "activity_events": 1}, "next": "stagnation", "phase": "reflect",
                "data": {"diagnosis": str(parsed.get("diagnosis", "")), "rule": rule}}


# --- Mutator ---

_PLUGIN_RE = re.compile(r"^[a-z0-9_]+\.py$")


class MutatorAgent:
    name = "mutator"
    reads = ["goal", "plan", "history", "stagnation", "energy", "consecutive_failures", "completed", "last_observation"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        from llm import call_llm
        import py_compile
        context = _render_context(ctx, "mutator")
        if _error_signal(ctx):
            context += "\n\nRUNTIME ERRORS: fix with a plugin."
        system = _load_prompt("mutator")
        if not system:
            return {"writes": {}, "next": "stagnation", "phase": "mutator.skip", "data": {"reason": "no prompt"}}
        try:
            raw = call_llm(system, context, "mutator")
        except Exception as e:
            return {"writes": {}, "next": "stagnation", "phase": "mutator.error", "data": {"error": str(e)}}
        parsed = _extract_json(raw, ["action", "filename", "content"])
        action = str(parsed.get("action", "none"))
        filename = str(parsed.get("filename", ""))
        content = str(parsed.get("content", ""))
        if action == "none" or not filename or not content or not _PLUGIN_RE.match(filename) or "def run(" not in content:
            return {"writes": {}, "next": "stagnation", "phase": "mutator", "data": {"action": "skip"}}
        target = config.PLUGINS_DIR / filename
        config.PLUGINS_DIR.mkdir(exist_ok=True)
        target.write_text(content, encoding="utf-8")
        try:
            py_compile.compile(str(target), doraise=True)
        except py_compile.PyCompileError:
            target.unlink(missing_ok=True)
            return {"writes": {}, "next": "stagnation", "phase": "mutator", "data": {"action": "rejected", "reason": "syntax"}}
        log.emit("mutator", {"action": action, "filename": filename})
        return {"writes": {"activity_events": 1}, "next": "stagnation", "phase": "mutator", "data": {"action": action, "filename": filename}}


# --- Context rendering (unified, no branching per field — match statement) ---

CONTEXT_POLICY: dict[str, list[str]] = {
    "planner": ["goal", "plan", "last_observation", "history", "completed", "bus", "denied_goals"],
    "verifier": ["goal", "done_when", "last_observation", "completed"],
    "reflector": ["goal", "last_observation", "history", "trigger", "completed"],
    "fission_judge": ["goal", "done_when", "last_observation", "history", "completed"],
    "mutator": ["goal", "last_observation", "history", "completed", "trigger"],
}


def _render_context(ctx: dict[str, Any], role: str) -> str:
    return "\n\n".join(t for f in CONTEXT_POLICY.get(role, []) if (t := _render_field(ctx, f)))


def _render_field(ctx: dict[str, Any], field: str) -> str:
    match field:
        case "goal":
            g = str(ctx.get("goal", ""))[:config.CONTEXT_GOAL_MAX]
            return f"GOAL: {g}" if g else ""
        case "plan":
            plan = ctx.get("plan", [])
            if not plan:
                return ""
            lines = ["PLAN:"]
            for i, s in enumerate(plan):
                marker = "✓ " if s.get("status") == "done" else ">>> " if s.get("status") == "active" else ""
                lines.append(f"  {marker}{str(s.get('code', ''))[:config.CONTEXT_PLAN_CODE_MAX]}")
            return "\n".join(lines)
        case "history":
            recent = list(ctx.get("history", []))[-config.CONTEXT_HISTORY_LINES:]
            if not recent:
                return ""
            lines = ["HISTORY:"]
            for h in recent:
                ok = "✓" if h.get("ok") else "✗"
                lines.append(f"  {ok} {h.get('verb', '')}: {str(h.get('obs', ''))[:config.CONTEXT_OBS_MAX]}")
            return "\n".join(lines)
        case "last_observation":
            obs = str(ctx.get("last_observation", ""))[:config.CONTEXT_OBS_MAX]
            return f"LAST_RESULT: {obs}" if obs else ""
        case "completed":
            c = ctx.get("completed", [])
            if not c:
                return ""
            lines = ["COMPLETED:"] + [f"  - {x}" for x in c[-config.CONTEXT_COMPLETED_MAX:]]
            return "\n".join(lines)
        case "done_when":
            dw = ctx.get("done_when", "")
            return f"DONE_WHEN: {dw}" if dw else ""
        case "denied_goals":
            now = time.time()
            active = [d for d in ctx.get("denied_goals", []) if now - d.get("ts", 0) < DENIAL_DECAY_SECS]
            blocked = list({d["dw"] for d in active if sum(1 for x in active if x.get("dw") == d.get("dw")) >= 2})
            if not blocked:
                return ""
            return "BLOCKED:\n" + "\n".join(f"  - {b}" for b in blocked[:5])
        case "trigger":
            trig = ctx.get("mutator_trigger") or ctx.get("reflect_trigger", {})
            if not trig:
                return ""
            parts = [f"TRIGGER: stag={trig.get('stag', 0)} pid={trig.get('pid', 0)} failures={trig.get('failures', 0)}"]
            err = str(trig.get("last_error", "")).strip()
            if err:
                parts.append(f"Error: {err}")
            return " ".join(parts)
        case "bus":
            from comms import format_bus_context, agent_id
            return format_bus_context(config.CONTEXT_BUS_MAX, for_agent=agent_id())
        case _:
            return ""


def _step_code(s: Any) -> str:
    if isinstance(s, dict):
        return str(s.get("code", s.get("text", ""))).strip()
    return str(s).strip()


def _load_planner_system() -> str:
    return _load_prompt("planner")


# --- Mutation system ---

_ELEMENT_ID_RE = re.compile(r"\[\d+\]")
_VAGUE = ("consistency", "foundation", "stable quality", "future success", "strong base")


def _apply_mutation(target: str, text: str) -> None:
    path = config.PROMPTS_DIR / f"{target}.txt"
    if not path.exists():
        return
    clean = text.strip()
    for prefix in ("RULE:", "EVOLVE:"):
        if clean.upper().startswith(prefix):
            clean = clean[len(prefix):].strip()
    if not clean or _ELEMENT_ID_RE.search(clean) or any(v in clean.lower() for v in _VAGUE):
        return
    current = path.read_text(encoding="utf-8")
    rules = [b.strip() for b in current.split("\n\n") if b.strip().startswith("RULE:")]
    if len(rules) >= config.PROMPT_MAX_RULES:
        header = current.split("RULE:", 1)[0].rstrip()
        current = header + "\n\n" + "\n\n".join(rules[-(config.PROMPT_MAX_RULES - 1):])
    path.write_text(current.rstrip() + f"\n\nRULE: {clean}\n", encoding="utf-8")
    log.emit("mutation", {"target": target, "appended": clean})


def _apply_personality_evolution(personality: str, text: str) -> None:
    path = config.PROMPTS_DIR / "personalities" / f"{personality}.txt"
    if not path.exists():
        return
    clean = text.strip()
    for prefix in ("RULE:", "EVOLVE:"):
        if clean.upper().startswith(prefix):
            clean = clean[len(prefix):].strip()
    if not clean or _ELEMENT_ID_RE.search(clean) or any(v in clean.lower() for v in _VAGUE):
        return
    current = path.read_text(encoding="utf-8")
    evolutions = [ln.strip() for ln in current.split("\n") if ln.strip().startswith("EVOLVE:")]
    if len(evolutions) >= config.PERSONALITY_MAX_EVOLUTIONS:
        header = current.split("EVOLVE:", 1)[0].strip()
        current = header + "\n" + "\n".join(evolutions[-(config.PERSONALITY_MAX_EVOLUTIONS - 1):])
    path.write_text(current.rstrip() + f"\nEVOLVE: {clean}\n", encoding="utf-8")
    log.emit("personality.evolve", {"personality": personality, "appended": clean})
