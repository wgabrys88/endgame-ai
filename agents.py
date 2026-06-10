from __future__ import annotations
import time
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


class StagnationAgent:
    name: str = "stagnation"
    reads: list[str] = ["plan", "progress_history", "consecutive_failures"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        progress = plan_progress(ctx)
        history: list[float] = ctx.get("progress_history", [])
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
        return {
            "writes": {"stagnation": stag, "progress_history": history},
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
        prev_x = x
        steps = 1 + int(stag * 4)
        for _ in range(steps):
            x = x + config.LORENZ_SIGMA * (y - x) * config.LORENZ_DT
            y = y + (x * (config.LORENZ_RHO - z) - y) * config.LORENZ_DT
            z = z + (x * y - config.LORENZ_BETA * z) * config.LORENZ_DT
        mag = (x * x + y * y + z * z) ** 0.5
        if mag > config.LORENZ_MAG_CAP:
            scale = config.LORENZ_MAG_CAP / mag
            x, y, z = x * scale, y * scale, z * scale
            mag = config.LORENZ_MAG_CAP
        wing = (prev_x > 0.0) != (x > 0.0) and stag > 0.4
        eq = (config.LORENZ_BETA * (config.LORENZ_RHO - config.LORENZ_EQUILIBRIUM_OFFSET)) ** 0.5
        energy = mag / max(eq * 2, 1.0)
        return {
            "writes": {"lorenz_x": x, "lorenz_y": y, "lorenz_z": z, "energy": energy, "wing_crossed": wing},
            "next": "pid",
            "phase": "lorenz",
            "data": {"x": round(x, 2), "energy": round(energy, 2), "wing": wing},
        }


class PidAgent:
    name: str = "pid"
    reads: list[str] = ["stagnation", "pid_integral", "pid_prev"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        stag = float(ctx.get("stagnation", 0))
        integral = float(ctx.get("pid_integral", 0))
        prev = float(ctx.get("pid_prev", 0))
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
        "stagnation", "wing_crossed", "pid_output",
        "plan", "goal", "last_reflect_time", "done_when",
    ]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        wing = bool(ctx.get("wing_crossed", False))
        pid = float(ctx.get("pid_output", 0))
        plan: list[dict[str, Any]] = ctx.get("plan", [])
        last_reflect = float(ctx.get("last_reflect_time", 0))
        writes: dict[str, Any] = {}
        now = time.time()

        if wing:
            writes["wing_crossed"] = False
            writes["plan"] = []
            writes["done_when"] = ""
            writes["consecutive_failures"] = 0
            writes["pid_integral"] = 0.0
            writes["progress_history"] = []
            return {"writes": writes, "next": "planner", "phase": "schedule", "data": {"reason": "wing_cross"}}

        if not plan:
            return {"writes": writes, "next": "planner", "phase": "schedule", "data": {"reason": "need_plan"}}

        if pid > config.REFLECT_THRESHOLD and (now - last_reflect) >= config.REFLECT_MIN_INTERVAL_SEC:
            writes["last_reflect_time"] = now
            return {"writes": writes, "next": "reflector", "phase": "schedule", "data": {"reason": "pid_gate", "pid": round(pid, 3)}}

        active = next((s for s in plan if s.get("status") == "active"), None)
        if active:
            return {"writes": writes, "next": "actor", "phase": "schedule", "data": {"reason": "execute", "step": active.get("text", "")}}

        all_done = all(s.get("status") == "done" for s in plan)
        if all_done:
            return {"writes": writes, "next": "verifier", "phase": "schedule", "data": {"reason": "plan_complete"}}

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
        "goal", "plan", "screen", "desktop_summary", "history",
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
        parsed = _extract_json(raw, ["mode", "sequence", "done_when"])
        mode = str(parsed.get("mode", "direct"))
        sequence: list[Any] = parsed.get("sequence", [])
        done_when = str(parsed.get("done_when", ""))
        if mode == "done" or not sequence:
            return {"writes": {}, "next": "verifier", "phase": "plan", "data": {"mode": "done"}}
        steps: list[dict[str, str]] = []
        for i, s in enumerate(sequence[:config.MAX_PLAN_STEPS]):
            steps.append({"text": str(s), "status": "active" if i == 0 else "pending"})
        return {
            "writes": {"plan": steps, "done_when": done_when, "consecutive_failures": 0, "pid_integral": 0.0, "pid_output": 0.0, "progress_history": []},
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
        from actions import execute_verb, VERBS
        from llm import call_llm
        plan: list[dict[str, Any]] = ctx.get("plan", [])
        active = next((s for s in plan if s.get("status") == "active"), None)
        if not active:
            return {"writes": {}, "next": "stagnation", "phase": "actor.error", "data": {"error": "no active step"}}
        instruction = str(active.get("text", ""))
        direct_result = _try_direct(instruction, ctx)
        if direct_result is not None:
            return direct_result
        context = _render_context(ctx, "actor", instruction)
        system = _load_prompt("actor")
        try:
            raw = call_llm(system, context, "actor", max_tokens=config.BUDGET_ACTOR_OUT)
        except Exception as e:
            log.emit("actor.error", {"error": str(e)})
            return {"writes": {"consecutive_failures": int(ctx.get("consecutive_failures", 0)) + 1}, "next": "stagnation", "phase": "actor.error", "data": {"error": str(e)}}
        parsed = _extract_json(raw, ["actions", "conclusion"])
        conclusion = str(parsed.get("conclusion", "EXECUTE"))
        actions: list[dict[str, Any]] = parsed.get("actions", [])
        if conclusion == "DONE":
            active["status"] = "done"
            return {"writes": {"plan": plan, "consecutive_failures": 0}, "next": "stagnation", "phase": "actor", "data": {"conclusion": "DONE"}}
        if conclusion == "CANNOT":
            active["status"] = "failed"
            return {"writes": {"plan": plan, "consecutive_failures": int(ctx.get("consecutive_failures", 0)) + 1}, "next": "stagnation", "phase": "actor", "data": {"conclusion": "CANNOT"}}
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
            return {"writes": {"history": history[-config.MAX_HISTORY:], "consecutive_failures": int(ctx.get("consecutive_failures", 0)) + 1}, "next": "stagnation", "phase": "actor", "data": {"conclusion": conclusion, "ok": False}}
        active["status"] = "done"
        return {"writes": {"plan": plan, "history": history[-config.MAX_HISTORY:], "consecutive_failures": 0}, "next": "stagnation", "phase": "actor", "data": {"conclusion": conclusion, "ok": True}}


class VerifierAgent:
    name: str = "verifier"
    reads: list[str] = ["goal", "screen", "history", "plan", "desktop_summary", "done_when"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        from llm import call_llm
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
        return {"writes": {"plan": [], "done_when": "", "consecutive_failures": 0, "progress_history": []}, "next": "stagnation", "phase": "verify", "data": {"verdict": "denied", "evidence": evidence}}

class ReflectorAgent:
    name: str = "reflector"
    reads: list[str] = ["goal", "screen", "plan", "history", "stagnation", "pid_output", "energy"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        from llm import call_llm
        context = _render_context(ctx, "reflector")
        system = _load_prompt("reflector")
        try:
            raw = call_llm(system, context, "reflector", max_tokens=config.BUDGET_REFLECTOR_OUT)
        except Exception as e:
            log.emit("reflector.error", {"error": str(e)})
            return {"writes": {}, "next": "stagnation", "phase": "reflector.error", "data": {"error": str(e)}}
        parsed = _extract_json(raw, ["diagnosis", "lesson"])
        lesson = str(parsed.get("lesson", ""))
        if lesson.strip():
            _write_lesson(lesson)
        mutation = parsed.get("prompt_mutation")
        if isinstance(mutation, dict):
            target = str(mutation.get("target", ""))
            append_text = str(mutation.get("append", ""))
            if target and append_text:
                _apply_mutation(target, append_text)
        return {
            "writes": {"plan": [], "pid_integral": 0.0, "consecutive_failures": 0, "progress_history": []},
            "next": "stagnation",
            "phase": "reflect",
            "data": {"diagnosis": str(parsed.get("diagnosis", "")), "lesson": lesson},
        }


def _try_direct(instruction: str, ctx: dict[str, Any]) -> dict[str, Any] | None:
    from actions import execute_verb, VERBS
    parts = instruction.split(None, 2)
    if not parts:
        return None
    verb = parts[0].lower()
    if verb in ("click", "write", "scroll"):
        return None
    if verb not in VERBS:
        return None
    target, value = "", ""
    if verb in ("click", "write", "scroll") and len(parts) >= 2:
        target = parts[1].strip("[]")
        if not target.isdigit():
            return None
        value = parts[2] if len(parts) > 2 else ""
    elif verb in ("hotkey", "press"):
        value = parts[1] if len(parts) > 1 else ""
    elif verb == "wait":
        target = parts[1] if len(parts) > 1 else "1"
    elif verb == "focus":
        value = " ".join(parts[1:]) if len(parts) > 1 else ""
    elif verb == "cmd":
        value = " ".join(parts[1:]) if len(parts) > 1 else ""
    elif verb == "write_file" and len(parts) >= 3:
        target = parts[1]
        value = parts[2]
    elif verb == "read_file":
        target = parts[1] if len(parts) > 1 else ""
    else:
        return None
    args = _build_args(verb, target, value)
    elements: dict[str, Any] = ctx.get("screen_elements", {})
    result = execute_verb(verb, args, elements, None)
    plan: list[dict[str, Any]] = ctx.get("plan", [])
    active = next((s for s in plan if s.get("status") == "active"), None)
    history: list[dict[str, Any]] = list(ctx.get("history", []))
    history.append({"verb": verb, "ok": result.success, "obs": result.observation})
    log.emit("action", {"verb": verb, "ok": result.success, "obs": result.observation, "direct": True})
    if result.success:
        if active:
            active["status"] = "done"
        return {"writes": {"plan": plan, "history": history[-config.MAX_HISTORY:], "consecutive_failures": 0}, "next": "stagnation", "phase": "actor", "data": {"conclusion": "direct", "verb": verb, "ok": True}}
    return {"writes": {"history": history[-config.MAX_HISTORY:], "consecutive_failures": int(ctx.get("consecutive_failures", 0)) + 1}, "next": "stagnation", "phase": "actor", "data": {"conclusion": "direct", "verb": verb, "ok": False}}


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
            return {"selector": target, "amount": int(value) if value else config.DEFAULT_SCROLL_AMOUNT}
        except ValueError:
            return {"selector": target, "amount": config.DEFAULT_SCROLL_AMOUNT}
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
    if verb == "cmd":
        return {"command": value or target}
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
            return f"GOAL: {ctx.get('goal', '')}"
        case "screen":
            s = ctx.get("screen", "")
            return f"SCREEN:\n{s}" if s else ""
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
            recent: list[dict[str, Any]] = ctx.get("history", [])[-40:]
            if not recent:
                return ""
            lines = ["HISTORY:"]
            for h in recent:
                ok = "\u2713" if h.get("ok") else "\u2717"
                lines.append(f"  {ok} {h.get('verb', '')}: {h.get('obs', '')}")
            return "\n".join(lines)
        case "budget":
            remaining = log.budget() - log.count()
            if remaining > log.budget() // 2:
                return ""
            return f"BUDGET: {remaining} events remaining."
        case "failures":
            f_count = int(ctx.get("consecutive_failures", 0))
            if f_count == 0:
                return ""
            return f"FAILURES: {f_count} consecutive. Try different approach."
        case "lessons":
            if not config.LESSONS_PATH.exists():
                return ""
            text = config.LESSONS_PATH.read_text(encoding="utf-8").strip()
            if not text:
                return ""
            lines_l = text.splitlines()[-8:]
            return "LESSONS:\n" + "\n".join(f"  - {l}" for l in lines_l)
        case "math":
            return (f"MATH: stagnation={ctx.get('stagnation', 0):.2f} "
                    f"pid={ctx.get('pid_output', 0):.2f} energy={ctx.get('energy', 1):.2f}")
        case "completed":
            completed: list[str] = ctx.get("completed", [])
            if not completed:
                return ""
            lines = ["COMPLETED (no repeat credit):"]
            for c in completed[-10:]:
                lines.append(f"  - {c}")
            return "\n".join(lines)
        case "done_when":
            dw = ctx.get("done_when", "")
            if not dw:
                return ""
            return f"DONE_WHEN: {dw}"
        case _:
            return ""


def _load_prompt(role: str) -> str:
    path = config.PROMPTS_DIR / f"{role}.txt"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


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
    with config.LESSONS_PATH.open("a", encoding="utf-8") as f:
        f.write(lesson.strip() + "\n")


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
    rules = [block.strip() for block in current.split("\n\n") if block.strip().startswith("RULE:")]
    if len(rules) >= config.PROMPT_MAX_RULES:
        base = current.split("RULE:")[0].rstrip()
        kept = rules[-(config.PROMPT_MAX_RULES - 1):]
        current = base + "\n\n" + "\n\n".join(kept)
    new_content = current.rstrip() + "\n\nRULE: " + clean_text + "\n"
    path.write_text(new_content, encoding="utf-8")
    log.emit("mutation", {"target": target, "appended": clean_text})
