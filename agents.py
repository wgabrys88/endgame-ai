from __future__ import annotations
import re
import time
from typing import Any, Protocol

import config
import log
from actions import DEFAULT_SCROLL_AMOUNT


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


def _token_set(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 3}


def _similar_to_completed(done_when: str, completed: list[str]) -> bool:
    if not done_when or not completed:
        return False
    dw = _token_set(done_when)
    if not dw:
        return False
    for entry in completed:
        ct = _token_set(str(entry))
        if not ct:
            continue
        if len(dw & ct) / max(len(dw), 1) >= config.COMPLETED_SIMILARITY_THRESHOLD:
            return True
    return False


def _trivial_milestone(goal: str, done_when: str) -> bool:
    if not goal.strip():
        return False
    d = done_when.lower()
    # Trivial if done_when is purely observational (no creation/mutation)
    trivial_markers = ("listed", "shown", "visible", "printed", "displayed", "can be read",
                       "readable", "on screen", "loaded", "showing", "status shown",
                       "checked", "observed", "confirmed exists")
    production_markers = ("created", "written", "committed", "pushed", "modified",
                          "compiled", "sent", "saved", "fixed", "installed")
    is_trivial = any(k in d for k in trivial_markers)
    is_productive = any(k in d for k in production_markers)
    return is_trivial and not is_productive


class StagnationAgent:
    name: str = "stagnation"
    reads: list[str] = ["plan", "progress_history", "consecutive_failures", "activity_events"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        progress = plan_progress(ctx)
        activity = int(ctx.get("activity_events", 0))
        history = ctx.get("progress_history", [])
        history = (history + [progress])[-config.STAGNATION_CYCLES_WINDOW:]
        if len(history) < 3:
            stag = 0.0
        else:
            recent_delta = history[-1] - history[-2]
            window_delta = history[-1] - history[0]
            if recent_delta > 0.01:
                stag = 0.0
            elif window_delta > 0.01:
                stag = 0.3
            else:
                stag = 1.0
        failures = int(ctx.get("consecutive_failures", 0))
        stag = min(1.0, stag + failures * 0.15)
        # Activity dampens stagnation — mutations, reflections, plugin writes count
        if activity > 0:
            stag = max(0.0, stag - activity * 0.2)
        return {
            "writes": {"stagnation": stag, "progress_history": history, "activity_events": 0},
            "next": "lorenz",
            "phase": "stagnation",
            "data": {"stag": round(stag, 3), "progress": round(progress, 3)},
        }


class LorenzAgent:
    name: str = "lorenz"
    reads: list[str] = ["lorenz_x", "lorenz_y", "lorenz_z", "stagnation"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        x = float(ctx.get("lorenz_x", 1.0))
        y = float(ctx.get("lorenz_y", 1.0))
        z = float(ctx.get("lorenz_z", 1.0))
        stag = float(ctx.get("stagnation", 0))
        prev_x, prev_y = x, y
        steps = max(3, 1 + int(stag * config.LORENZ_STAG_STEPS_SCALE))
        for _ in range(steps):
            x = x + config.LORENZ_SIGMA * (y - x) * config.LORENZ_DT
            y = y + (x * (config.LORENZ_RHO - z) - y) * config.LORENZ_DT
            z = z + (x * y - config.LORENZ_BETA * z) * config.LORENZ_DT
        mag = (x * x + y * y + z * z) ** 0.5
        if mag > config.LORENZ_MAG_CAP:
            scale = config.LORENZ_MAG_CAP / mag
            x, y, z = x * scale, y * scale, z * scale
            mag = config.LORENZ_MAG_CAP
        crossed = (prev_x * x < 0) or (prev_y * y < 0)
        wing = crossed and stag >= config.LORENZ_WING_STAG_MIN
        eq = (config.LORENZ_BETA * (config.LORENZ_RHO - config.LORENZ_EQUILIBRIUM_OFFSET)) ** 0.5
        energy = mag / max(eq * 2, 1.0)
        return {
            "writes": {"lorenz_x": x, "lorenz_y": y, "lorenz_z": z, "energy": energy, "wing_crossed": wing},
            "next": "scheduler",
            "phase": "lorenz",
            "data": {"x": round(x, 2), "y": round(y, 2), "z": round(z, 2), "energy": round(energy, 2), "wing": wing},
        }


class PidAgent:
    name: str = "pid"
    reads: list[str] = ["stagnation", "pid_integral", "pid_prev"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        stag = float(ctx.get("stagnation", 0))
        if config.PID_KP == 0 and config.PID_KI == 0 and config.PID_KD == 0:
            return {
                "writes": {"pid_output": 0.0, "pid_prev": stag},
                "next": "scheduler",
                "phase": "pid",
                "data": {"pid": 0.0},
            }
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
            "next": "scheduler",
            "phase": "pid",
            "data": {"pid": round(output, 3)},
        }


class SchedulerAgent:
    name: str = "scheduler"
    reads: list[str] = [
        "stagnation", "wing_crossed", "energy", "pid_output", "consecutive_failures",
        "plan", "goal", "last_reflect_time", "done_when",
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
        stag_gate = stag >= config.REFLECT_STAG_THRESHOLD and failures >= 1
        chaos_gate = energy >= config.CHAOS_ENERGY_THRESHOLD and stag >= config.REFLECT_STAG_THRESHOLD
        # Periodic reflect every 5 completions even without stagnation
        completions = len(ctx.get("completed", []))
        periodic_gate = completions > 0 and completions % 5 == 0
        reflect_wanted = reflect_due and (pid_gate or stag_gate or chaos_gate or periodic_gate)

        # Plan completion takes priority — verify before reflecting
        all_done = plan and all(s.get("status") == "done" for s in plan)
        if all_done:
            return {"writes": writes, "next": "verifier", "phase": "schedule", "data": {"reason": "plan_complete"}}

        # If stuck in reflect loop (3+ consecutive pid_gates), force replan instead
        if reflect_wanted and plan and all(s.get("status") == "done" or s.get("status") == "failed" for s in plan):
            writes["plan"] = []
            writes["last_reflect_time"] = now
            return {"writes": writes, "next": "planner", "phase": "schedule", "data": {"reason": "need_plan"}}

        # Reflection takes priority when system is stuck — even over replan/wing
        if reflect_wanted:
            if pid_gate:
                reason = "pid_gate"
            elif stag_gate:
                reason = "stag_gate"
            else:
                reason = "chaos_gate"
            writes["last_reflect_time"] = now
            if wing:
                writes["wing_crossed"] = False
            writes["reflect_trigger"] = {
                "reason": reason,
                "stag": round(stag, 3),
                "pid": round(pid, 3),
                "energy": round(energy, 3),
                "failures": failures,
                "step": "",
            }
            return {"writes": writes, "next": "reflector", "phase": "schedule", "data": {"reason": reason, "pid": round(pid, 3), "energy": round(energy, 3), "stag": round(stag, 3)}}

        if wing:
            writes["wing_crossed"] = False
            writes["pid_integral"] = 0.0
            return {"writes": writes, "next": "planner", "phase": "schedule", "data": {"reason": "wing_cross"}}

        if not plan:
            return {"writes": writes, "next": "planner", "phase": "schedule", "data": {"reason": "need_plan"}}

        active = next((s for s in plan if s.get("status") == "active"), None)

        if active:
            return {"writes": writes, "next": "actor", "phase": "schedule", "data": {"reason": "execute", "step": active.get("text", "")}}


        pending = next((s for s in plan if s.get("status") == "pending"), None)
        if pending:
            pending["status"] = "active"
            return {"writes": {"plan": plan}, "next": "actor", "phase": "schedule", "data": {"reason": "advance", "step": pending.get("text", "")}}

        return {"writes": writes, "next": "planner", "phase": "schedule", "data": {"reason": "stuck"}}

class ObserverAgent:
    name: str = "observer"
    reads: list[str] = ["screen"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        from observer import observe
        try:
            obs = observe()
        except Exception as e:
            return {
                "writes": {},
                "next": "scheduler",
                "phase": "observe",
                "data": {"error": str(e)},
            }
        return {
            "writes": {
                "screen": obs.context_text,
                "screen_elements": obs.book,
                "focused_window": obs.focused_title,
                "desktop_summary": obs.desktop_summary,
            },
            "next": "scheduler",
            "phase": "observe",
            "data": {"focused": obs.focused_title, "chars": len(obs.context_text)},
        }


class PlannerAgent:
    name: str = "planner"
    reads: list[str] = [
        "goal", "plan", "desktop_summary", "focused_window", "history",
        "consecutive_failures", "stagnation", "energy", "completed",
    ]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        from llm import call_llm
        context = _render_context(ctx, "planner")
        system = _load_prompt("planner")
        try:
            raw = call_llm(system, context, "planner", max_tokens=config.BUDGET_PLANNER_OUT)
        except Exception as e:
            log.emit("planner.error", {"error": str(e)})
            return {"writes": {"consecutive_failures": int(ctx.get("consecutive_failures", 0)) + 1}, "next": "stagnation", "phase": "planner.error", "data": {"error": str(e)}}
        parsed = _extract_json(raw, ["mode", "sequence"])
        parsed.setdefault("done_when", "output produced")
        mode = str(parsed.get("mode", "direct"))
        sequence: list[Any] = parsed.get("sequence", [])
        done_when = str(parsed.get("done_when", ""))
        if mode == "done" or not sequence:
            if str(ctx.get("goal", "")).strip() and not list(ctx.get("completed", [])):
                return {"writes": {"consecutive_failures": int(ctx.get("consecutive_failures", 0)) + 1}, "next": "stagnation", "phase": "plan", "data": {"mode": "rejected", "reason": "cannot declare done before any GOAL progress"}}
            if list(ctx.get("completed", [])):
                return {"writes": {}, "next": "halt", "phase": "plan", "data": {"mode": "done", "reason": "goal_satisfied"}}
            return {"writes": {}, "next": "verifier", "phase": "plan", "data": {"mode": "done"}}
        steps: list[dict[str, str]] = []
        for i, s in enumerate(sequence[:config.MAX_PLAN_STEPS]):
            text = _normalize_step(s)
            steps.append({"text": _sanitize_plan_step(text), "status": "active" if i == 0 else "pending"})
        return {
            "writes": {"plan": steps, "done_when": done_when, "consecutive_failures": 0, "progress_history": []},
            "next": "actor",
            "phase": "plan",
            "data": {"mode": mode, "steps": len(steps), "done_when": done_when},
        }

class ActorAgent:
    name: str = "actor"
    reads: list[str] = [
        "plan", "screen", "screen_elements", "history",
        "consecutive_failures", "goal", "focused_window", "desktop_summary",
    ]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        from actions import execute_step, execute_verb, is_python_step, VERBS
        from llm import call_llm
        plan: list[dict[str, Any]] = ctx.get("plan", [])
        active = next((s for s in plan if s.get("status") == "active"), None)
        if not active:
            return {"writes": {}, "next": "planner", "phase": "actor.error", "data": {"error": "no active step"}}
        instruction = str(active.get("text", ""))
        if is_python_step(instruction):
            history: list[dict[str, Any]] = list(ctx.get("history", []))
            result = execute_step(instruction)
            history.append({"verb": result.verb, "ok": result.success, "obs": result.observation})
            payload = {"conclusion": "python", "ok": result.success, "verb": result.verb, "obs": result.observation}
            if result.success:
                active["status"] = "done"
                _advance_plan(plan)
                return {"writes": {"plan": plan, "history": history, "consecutive_failures": 0}, "next": "stagnation", "phase": "actor", "data": payload}
            active["status"] = "failed"
            failures = int(ctx.get("consecutive_failures", 0)) + 1
            return {"writes": {"plan": plan, "history": history, "consecutive_failures": failures}, "next": "planner", "phase": "actor", "data": payload}
        context = _render_context(ctx, "actor", instruction)
        system = _load_prompt("actor")
        try:
            raw = call_llm(system, context, "actor", max_tokens=config.BUDGET_ACTOR_OUT)
        except Exception as e:
            log.emit("actor.error", {"error": str(e)})
            failures = int(ctx.get("consecutive_failures", 0)) + 1
            return {"writes": {"consecutive_failures": failures}, "next": "planner", "phase": "actor.error", "data": {"error": str(e)}}
        parsed = _extract_json(raw, ["actions", "conclusion"])
        conclusion = str(parsed.get("conclusion", "EXECUTE"))
        actions: list[dict[str, Any]] = parsed.get("actions", [])
        actions = [a for a in actions if str(a.get("verb", "")) in {"click", "write", "press", "hotkey", "scroll", "focus"}]
        if conclusion == "EXECUTE" and not actions:
            active["status"] = "failed"
            failures = int(ctx.get("consecutive_failures", 0)) + 1
            return {"writes": {"plan": plan, "consecutive_failures": failures}, "next": "planner", "phase": "actor", "data": {"conclusion": "CANNOT", "error": "need GUI verb"}}
        if conclusion == "DONE":
            active["status"] = "done"
            _advance_plan(plan)
            return {"writes": {"plan": plan, "consecutive_failures": 0}, "next": "stagnation", "phase": "actor", "data": {"conclusion": "DONE"}}
        if conclusion == "CANNOT":
            active["status"] = "failed"
            failures = int(ctx.get("consecutive_failures", 0)) + 1
            return {"writes": {"plan": plan, "consecutive_failures": failures}, "next": "planner", "phase": "actor", "data": {"conclusion": "CANNOT"}}
        elements: dict[str, Any] = ctx.get("screen_elements", {})
        history: list[dict[str, Any]] = list(ctx.get("history", []))
        had_failure = False
        for action in actions:
            verb = str(action.get("verb", ""))
            target = str(action.get("target", ""))
            value = str(action.get("value", ""))
            if verb not in VERBS:
                history.append({"verb": verb, "ok": False, "obs": f"unknown verb: {verb}"})
                had_failure = True
                break
            args = _build_args(verb, target, value)
            result = execute_verb(verb, args, elements, None)
            history.append({"verb": verb, "ok": result.success, "obs": result.observation})
            log.emit("action", {"verb": verb, "ok": result.success, "obs": result.observation})
            if not result.success:
                had_failure = True
                break
        if had_failure:
            active["status"] = "failed"
            failures = int(ctx.get("consecutive_failures", 0)) + 1
            return {"writes": {"plan": plan, "history": history, "consecutive_failures": failures}, "next": "planner", "phase": "actor", "data": {"conclusion": conclusion, "ok": False}}
        active["status"] = "done"
        _advance_plan(plan)
        return {"writes": {"plan": plan, "history": history, "consecutive_failures": 0}, "next": "stagnation", "phase": "actor", "data": {"conclusion": conclusion, "ok": True}}


class VerifierAgent:
    name: str = "verifier"
    reads: list[str] = ["goal", "screen", "history", "plan", "desktop_summary", "done_when", "completed"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        from llm import call_llm
        done_when = str(ctx.get("done_when", ""))
        completed: list[str] = list(ctx.get("completed", []))
        goal = str(ctx.get("goal", ""))
        if _similar_to_completed(done_when, completed):
            return {
                "writes": {"plan": [], "done_when": "", "consecutive_failures": int(ctx.get("consecutive_failures", 0)) + 1},
                "next": "stagnation",
                "phase": "verify",
                "data": {"verdict": "denied", "evidence": "done_when overlaps COMPLETED — no repeat fission credit"},
            }
        if _trivial_milestone(goal, done_when):
            return {
                "writes": {"plan": [], "done_when": "", "consecutive_failures": int(ctx.get("consecutive_failures", 0)) + 1},
                "next": "stagnation",
                "phase": "verify",
                "data": {"verdict": "denied", "evidence": "done_when is observational only — GOAL requires substantive action (post, create, execute)"},
            }
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
            return {"writes": {}, "next": "done", "phase": "verify", "data": {"verdict": "confirmed", "evidence": evidence}}
        return {"writes": {"plan": [], "done_when": "", "consecutive_failures": 0, "progress_history": []}, "next": "planner", "phase": "verify", "data": {"verdict": "denied", "evidence": evidence}}

class ReflectorAgent:
    name: str = "reflector"
    reads: list[str] = [
        "goal", "plan", "history", "stagnation", "pid_output", "energy",
        "reflect_trigger", "completed",
    ]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        from llm import call_llm
        context = _render_context(ctx, "reflector")
        system = _load_prompt("reflector")
        failures = int(ctx.get("consecutive_failures", 0))
        try:
            raw = call_llm(system, context, "reflector", max_tokens=config.BUDGET_REFLECTOR_OUT)
        except Exception as e:
            log.emit("reflector.error", {"error": str(e)})
            return {"writes": {}, "next": "stagnation", "phase": "reflector.error", "data": {"error": str(e)}}
        parsed = _extract_json(raw, ["diagnosis", "suggestion"])
        diagnosis = str(parsed.get("diagnosis", ""))
        rule = str(parsed.get("rule", ""))
        if rule.strip():
            _apply_mutation("planner", rule)
            _write_lesson(rule)
        plan_steps: list[dict[str, Any]] = ctx.get("plan", [])
        retry = next((s for s in plan_steps if s.get("status") == "active"), None)
        # Escalate to mutator if repeated reflections haven't helped
        if failures >= config.MUTATOR_ESCALATION_FAILURES:
            return {
                "writes": {"pid_integral": 0.0, "activity_events": 1},
                "next": "mutator",
                "phase": "reflect",
                "data": {"diagnosis": diagnosis, "rule": rule, "escalate": "mutator"},
            }
        return {
            "writes": {"pid_integral": 0.0, "consecutive_failures": 0, "activity_events": 1},
            "next": "actor" if retry else "stagnation",
            "phase": "reflect",
            "data": {"diagnosis": diagnosis, "rule": rule},
        }


def _advance_plan(plan: list[dict[str, Any]]) -> None:
    pending = next((s for s in plan if s.get("status") == "pending"), None)
    if pending:
        pending["status"] = "active"


def _build_args(verb: str, target: str, value: str) -> dict[str, Any]:
    target = target.strip("[]")
    if verb == "click":
        return {"selector": target}
    if verb == "write":
        return {"selector": target, "text": value}
    if verb == "press":
        return {"key": target or value}
    if verb == "hotkey":
        raw = value or target
        keys = [k.strip() for k in raw.replace("+", ",").split(",") if k.strip()]
        return {"keys": keys}
    if verb == "scroll":
        try:
            return {"selector": target, "amount": int(value) if value else DEFAULT_SCROLL_AMOUNT}
        except ValueError:
            return {"selector": target, "amount": DEFAULT_SCROLL_AMOUNT}
    if verb == "wait":
        try:
            return {"seconds": float(target or value or "1.0")}
        except ValueError:
            return {"seconds": 1.0}
    if verb == "focus":
        return {"window_title": target or value}
    if verb == "read_file":
        return {"path": target or value}
    if verb == "write_file":
        return {"path": target, "content": value}
    return {}


def _render_context(ctx: dict[str, Any], role: str, instruction: str = "") -> str:
    fields = config.CONTEXT_POLICY.get(role, [])
    parts: list[str] = []
    for f in fields:
        text = _render_field(ctx, f, instruction)
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def _render_field(ctx: dict[str, Any], field: str, instruction: str) -> str:
    match field:
        case "goal":
            goal = ctx.get("goal", "")
            hist = list(ctx.get("history", []))
            if hist:
                last = str(hist[-1].get("obs", ""))
                return "GOAL: " + goal + "\nLAST: " + last
            return "GOAL: " + goal
        case "screen":
            s = ctx.get("screen", "")
            return f"SCREEN:\n{s}" if s else ""
        case "desktop":
            parts: list[str] = []
            fw = str(ctx.get("focused_window", "")).strip()
            if fw:
                parts.append(f"FOCUSED WINDOW: {fw}")
            ds = str(ctx.get("desktop_summary", "")).strip()
            if ds:
                parts.append(f"DESKTOP:\n{ds}")
            return "\n\n".join(parts)
        case "instruction":
            if not instruction:
                return ""
            return f"INSTRUCTION: {instruction}"
        case "plan":
            plan: list[dict[str, Any]] = ctx.get("plan", [])
            if not plan:
                return ""
            lines = ["PLAN:"]
            for i, step in enumerate(plan):
                is_last = i == len(plan) - 1
                connector = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
                status = step.get("status", "pending")
                marker = "\u2713 " if status == "done" else ">>> " if status == "active" else ""
                lines.append(f"  {connector}{marker}{step.get('text', '')}")
            return "\n".join(lines)
        case "history":
            recent: list[dict[str, Any]] = list(ctx.get("history", []))
            if not recent:
                return ""
            lines = ["HISTORY:"]
            for h in recent:
                ok = "\u2713" if h.get("ok") else "\u2717"
                lines.append(f"  {ok} {h.get('verb', '')}: {h.get('obs', '')}")
            return "\n".join(lines)
        case "budget":
            remaining = log.budget() - log.work_count()
            if remaining > log.budget() // 2:
                return ""
            return f"BUDGET: {remaining} events remaining."
        case "failures":
            f_count = int(ctx.get("consecutive_failures", 0))
            if f_count == 0:
                return ""
            return f"FAILURES: {f_count} consecutive. Try different approach."
        case "lessons":
            import lessons
            step = ""
            plan = ctx.get("plan", [])
            if isinstance(plan, list):
                active = next((s for s in plan if isinstance(s, dict) and s.get("status") == "active"), None)
                if active:
                    step = str(active.get("text", ""))
            return lessons.format_for_context(keyword=step)
        case "math":
            stag = ctx.get('stagnation', 0)
            if stag >= 0.8:
                return 'STATUS: stuck, not making progress'
            elif stag >= 0.4:
                return 'STATUS: slow progress'
            return 'STATUS: making progress'

        case "trigger":
            trig = ctx.get("reflect_trigger", {})
            if not isinstance(trig, dict) or not trig:
                return ""
            failures = int(trig.get('failures', 0))
            stag = float(trig.get('stag', 0))
            step = trig.get('step', '')
            parts = ['TRIGGER:']
            if failures >= 3:
                parts.append(f'Failed {failures} times. Must change approach.')
            elif failures >= 1:
                parts.append(f'Failed {failures} time(s).')
            if stag >= 1.0:
                parts.append('Completely stuck.')
            if step:
                parts.append(f'Last step: {step}')
            return ' '.join(parts)
        case "completed":
            completed: list[str] = ctx.get("completed", [])
            if not completed:
                return ""
            lines = ["COMPLETED (no repeat credit):"]
            for c in completed:
                lines.append(f"  - {c}")
            return "\n".join(lines)
        case "done_when":
            dw = ctx.get("done_when", "")
            if not dw:
                return ""
            return f"DONE_WHEN: {dw}"
        case _:
            return ""


_ELEMENT_ID_RE = re.compile(r"\[\d+\]")


def _normalize_step(s: Any) -> str:
    if isinstance(s, str):
        return s
    if isinstance(s, dict):
        if "code" in s:
            return f"exec {s['code']}"
        if "exec" in s:
            return f"exec {s['exec']}"
        if "wait" in s:
            return f"wait {s['wait']}"
        if "read_file" in s:
            return f"read_file {s['read_file']}"
        if "write_file" in s:
            return f"write_file {s['write_file']} {s.get('content','')}"
        if "text" in s:
            return str(s["text"])
        if "step" in s:
            rest = s.get("args", s.get("code", s.get("value", "")))
            return f"{s['step']} {rest}".strip()
        k, v = next(iter(s.items()))
        return f"{k} {v}"
    return str(s)


def _sanitize_plan_step(step: str) -> str:
    if not _ELEMENT_ID_RE.search(step):
        return step
    cleaned = _ELEMENT_ID_RE.sub("", step)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    log.emit("plan.sanitize", {"original": step, "cleaned": cleaned})
    return cleaned or step


def _load_prompt(role: str) -> str:
    path = config.PROMPTS_DIR / f"{role}.txt"
    base = path.read_text(encoding="utf-8").strip() if path.exists() else ""
    if role == "planner":
        import os as _os2
        personality = _os2.environ.get("ENDGAME_PERSONALITY", "")
        if personality:
            ppath = config.PROMPTS_DIR / "personalities" / f"{personality}.txt"
            if ppath.exists():
                return base + "\n\n" + ppath.read_text(encoding="utf-8").strip()
    return base


def _extract_json(raw: str, required: list[str]) -> dict[str, Any]:
    import json
    from typing import cast
    stripped = raw.strip()
    if stripped.startswith("{"):
        try:
            result: dict[str, Any] = json.loads(stripped)
            if all(f in result for f in required):
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
            parsed: object = json.loads(candidate)
            if isinstance(parsed, dict):
                result = cast(dict[str, Any], parsed)
                if all(f in result for f in required):
                    return result
        except json.JSONDecodeError:
            continue
    for candidate in reversed(candidates):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return cast(dict[str, Any], parsed)
        except json.JSONDecodeError:
            continue
    raise ValueError(f"no JSON in response: {raw}")


def _write_lesson(lesson: str) -> None:
    import lessons
    lessons.record(lesson)


def _apply_mutation(target: str, append_text: str) -> None:
    path = config.PROMPTS_DIR / f"{target}.txt"
    if not path.exists():
        return
    current = path.read_text(encoding="utf-8")
    clean_text = append_text.strip()
    if clean_text.upper().startswith("RULE:"):
        clean_text = clean_text[5:].strip()
    if not clean_text:
        return
    if _ELEMENT_ID_RE.search(clean_text) or re.search(r"click\s*\[", clean_text, re.I):
        log.emit("mutation.rejected", {"target": target, "reason": "element_id_in_mutation"})
        return
    # Protect: header is everything before first RULE:
    parts = current.split("RULE:", 1)
    header = parts[0] if parts else ""
    if not header.strip():
        return  # refuse mutation if header already lost
    rules = [block.strip() for block in current.split("\n\n") if block.strip().startswith("RULE:")]
    if len(rules) >= config.PROMPT_MAX_RULES:
        kept = rules[-(config.PROMPT_MAX_RULES - 1):]
        current = header.rstrip() + "\n\n" + "\n\n".join(kept)
    new_content = current.rstrip() + "\n\nRULE: " + clean_text + "\n"
    path.write_text(new_content, encoding="utf-8")
    log.emit("mutation", {"target": target, "appended": clean_text})


# --- MutatorAgent (code evolution — writes to plugins/ only) ---

_PLUGIN_FILENAME_RE = re.compile(r"^[a-z0-9_]+\.py$")


class MutatorAgent:
    name: str = "mutator"
    reads: list[str] = [
        "goal", "plan", "history", "stagnation", "energy",
        "consecutive_failures", "completed",
    ]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        from llm import call_llm
        import py_compile
        context = _render_context(ctx, "reflector")  # reuse reflector context policy
        # Add plugin error context
        plugin_errors = self._recent_plugin_errors()
        if plugin_errors:
            context += "\n\nPLUGIN ERRORS:\n" + "\n".join(f"  - {e}" for e in plugin_errors)
        system = _load_prompt("mutator")
        if not system:
            return {"writes": {}, "next": "stagnation", "phase": "mutator.skip",
                    "data": {"reason": "no prompt"}}
        try:
            raw = call_llm(system, context, "mutator", max_tokens=getattr(config, "BUDGET_MUTATOR_OUT", config.BUDGET_REFLECTOR_OUT))
        except Exception as e:
            log.emit("mutator.error", {"error": str(e)})
            return {"writes": {}, "next": "stagnation", "phase": "mutator.error",
                    "data": {"error": str(e)}}
        parsed = _extract_json(raw, ["action", "filename", "content"])
        action = str(parsed.get("action", "none"))
        filename = str(parsed.get("filename", ""))
        content = str(parsed.get("content", ""))
        diagnosis = str(parsed.get("diagnosis", ""))
        if action == "none" or not filename or not content:
            return {"writes": {}, "next": "stagnation", "phase": "mutator",
                    "data": {"action": "none", "diagnosis": diagnosis}}
        if not _PLUGIN_FILENAME_RE.match(filename):
            log.emit("mutator.rejected", {"reason": "invalid filename", "filename": filename})
            return {"writes": {}, "next": "stagnation", "phase": "mutator",
                    "data": {"action": "rejected", "reason": "invalid filename"}}
        if "def run(" not in content:
            log.emit("mutator.rejected", {"reason": "missing run()", "filename": filename})
            return {"writes": {}, "next": "stagnation", "phase": "mutator",
                    "data": {"action": "rejected", "reason": "no run() def"}}
        target = config.PLUGINS_DIR / filename
        config.PLUGINS_DIR.mkdir(exist_ok=True)
        target.write_text(content, encoding="utf-8")
        try:
            py_compile.compile(str(target), doraise=True)
        except py_compile.PyCompileError as e:
            target.unlink(missing_ok=True)
            log.emit("mutator.rejected", {"reason": "syntax error", "error": str(e)[:200]})
            return {"writes": {}, "next": "stagnation", "phase": "mutator",
                    "data": {"action": "rejected", "reason": "syntax error"}}
        log.emit("mutator", {"action": action, "filename": filename, "diagnosis": diagnosis})
        return {"writes": {"activity_events": 1}, "next": "stagnation", "phase": "mutator",
                "data": {"action": action, "filename": filename}}

    @staticmethod
    def _recent_plugin_errors() -> list[str]:
        """Read last few plugin errors from events log."""
        path = config.EVENTS_PATH
        if not path.exists():
            return []
        errors: list[str] = []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()[-100:]
            for line in lines:
                if "plugin.error" in line:
                    errors.append(line.strip()[-200:])
        except OSError:
            pass
        return errors[-5:]
