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


def _token_set(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 3}


def _max_similarity_score(done_when: str, completed: list[str]) -> float:
    if not done_when or not completed:
        return 0.0
    dw = _token_set(done_when)
    if not dw:
        return 0.0
    best = 0.0
    for entry in completed:
        ct = _token_set(str(entry))
        if not ct:
            continue
        best = max(best, len(dw & ct) / max(len(dw), 1))
    return best


def _similarity_hint(done_when: str, completed: list[str]) -> str:
    score = _max_similarity_score(done_when, completed)
    flagged = score >= config.COMPLETED_SIMILARITY_THRESHOLD
    status = "possible repeat — use judgment" if flagged else "distinct enough — lean credit if valuable"
    return (
        f"SIMILARITY: {score:.2f} vs threshold {config.COMPLETED_SIMILARITY_THRESHOLD} ({status}). "
        "This is advisory only; you decide fission credit."
    )


_COMMS_ARTIFACTS: tuple[tuple[str, str], ...] = (
    ("runtime/comms/report.md", "runtime/comms/report.md written with agent status"),
    ("runtime/comms/quality.json", "runtime/comms/quality.json written with plugin audit results"),
    ("runtime/comms/messages.json", "runtime/comms/messages.json contains a new coordination message"),
)


def _milestone_hints(ctx: dict[str, Any]) -> str:
    goal = str(ctx.get("goal", "")).lower()
    if "runtime/comms" not in goal and "communicate" not in goal:
        return ""
    lines: list[str] = []
    comms = config.BASE_DIR / "runtime" / "comms"
    for rel, milestone in _COMMS_ARTIFACTS:
        path = config.BASE_DIR / rel
        if not path.exists() or path.stat().st_size == 0:
            lines.append(f"  - {milestone}")
    human = comms / "human.txt"
    if human.exists():
        try:
            body = human.read_text(encoding="utf-8").strip()
        except OSError:
            body = ""
        if len(body) < 80:
            lines.append("  - runtime/comms/human.txt appended with colony status line")
    if not lines:
        return ""
    return "SUGGESTED MILESTONES (missing artifacts — pick one):\n" + "\n".join(lines[:4])


DENIAL_DECAY_SECS = 120.0  # blocked plans decay after 2 minutes
DENIAL_MAX = 10

_RUNTIME_ERROR_MARKERS: tuple[str, ...] = (
    "NameError", "AttributeError", "ImportError", "SyntaxError", "TypeError",
    "KeyError", "FileNotFoundError", "ModuleNotFoundError", "IndentationError",
    "is not defined", "PLAN REJECTED", "not Python", "timeout after",
)


def _text_has_runtime_error(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    return any(marker in t for marker in _RUNTIME_ERROR_MARKERS)


def _runtime_error_signal(ctx: dict[str, Any]) -> bool:
    if _text_has_runtime_error(str(ctx.get("last_observation", ""))):
        return True
    for entry in list(ctx.get("history", []))[-6:]:
        if entry.get("ok"):
            continue
        if _text_has_runtime_error(str(entry.get("obs", ""))):
            return True
    return False


def _mutator_math_gate(ctx: dict[str, Any]) -> bool:
    stag = float(ctx.get("stagnation", 0))
    pid = float(ctx.get("pid_output", 0))
    energy = float(ctx.get("energy", 1))
    return (
        stag >= config.MUTATOR_MATH_STAG_MIN
        or pid >= config.MUTATOR_PID_MIN
        or energy >= config.MUTATOR_ENERGY_MIN
    )

_ARTIFACT_PATTERNS: tuple[re.Pattern[str], int] = (
    (re.compile(r"named\s+([\w./\\_-]+\.\w+)\s+is\s+(?:created|written)", re.I), 1),
    (re.compile(r"(plugins/[\w._-]+\.py)\s+is\s+(?:created|written)", re.I), 1),
    (re.compile(r"(runtime/comms/[\w._-]+)\s+(?:written|created|contains)", re.I), 1),
    (re.compile(r"file\s+[`\"']?([\w./\\_-]+\.\w+)[`\"']?\s+is\s+(?:created|written|overwritten)", re.I), 1),
)


def _artifact_paths(done_when: str) -> list[Path]:
    paths: list[Path] = []
    seen: set[str] = set()
    for pattern, group in _ARTIFACT_PATTERNS:
        for match in pattern.finditer(done_when):
            rel = match.group(group).replace("\\", "/")
            if rel in seen:
                continue
            seen.add(rel)
            paths.append(config.BASE_DIR / rel)
    return paths


def _missing_artifacts(done_when: str) -> list[str]:
    missing: list[str] = []
    for path in _artifact_paths(done_when):
        try:
            if not path.exists() or path.stat().st_size == 0:
                missing.append(str(path.relative_to(config.BASE_DIR)))
        except OSError:
            missing.append(str(path.relative_to(config.BASE_DIR)))
    return missing


def _add_denial(denied_goals: list[dict[str, Any]], done_when: str) -> list[dict[str, Any]]:
    """Track denied done_when strings with timestamp for decay."""
    import time as _t
    now = _t.time()
    # Decay old entries
    active = [d for d in denied_goals if now - d.get("ts", 0) < DENIAL_DECAY_SECS]
    active.append({"dw": done_when[:120], "ts": now})
    return active[-DENIAL_MAX:]


def _is_blocked(denied_goals: list[dict[str, Any]], done_when: str) -> bool:
    """Return True if this done_when was denied >=2 times and hasn't decayed."""
    import time as _t
    now = _t.time()
    dw_low = done_when.lower()[:120]
    count = sum(1 for d in denied_goals
                if now - d.get("ts", 0) < DENIAL_DECAY_SECS
                and d.get("dw", "").lower() == dw_low)
    return count >= 2


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
        stag = min(1.0, stag + min(failures * config.STAGNATION_FAILURE_WEIGHT, config.STAGNATION_FAILURE_CAP))
        # Activity dampens stagnation - mutations, reflections, plugin writes count
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


def _reject_plan(ctx: dict[str, Any], reason: str, *, event: str = "plan.rejected") -> dict[str, Any]:
    log.emit(event, {"reason": reason[:120]})
    history = _append_history(list(ctx.get("history", [])), {"verb": "plan", "ok": False, "obs": f"REJECTED: {reason}"})
    return {
        "writes": {
            "consecutive_failures": int(ctx.get("consecutive_failures", 0)) + 1,
            "last_observation": f"PLAN REJECTED: {reason}",
            "history": history,
            "plan": [],
            "done_when": "",
            "last_plan_reject_at": time.time(),
        },
        "next": "stagnation",
        "phase": "plan",
        "data": {"mode": "rejected", "reason": reason},
    }


class SchedulerAgent:
    name: str = "scheduler"
    reads: list[str] = [
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
        # Periodic reflect every 5 completions even without stagnation
        completions = len(ctx.get("completed", []))
        periodic_gate = completions > 0 and completions % 5 == 0
        reflect_wanted = reflect_due and (pid_gate or stag_gate or chaos_gate or periodic_gate)

        if not plan:
            replan_stuck = failures >= config.PLAN_REJECT_FAILURE_MIN and stag >= config.REFLECT_STAG_THRESHOLD
            if reflect_due and (reflect_wanted or replan_stuck):
                if pid_gate:
                    reason = "pid_gate"
                elif stag_gate or replan_stuck:
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
                return {
                    "writes": writes,
                    "next": "reflector",
                    "phase": "schedule",
                    "data": {"reason": reason, "pid": round(pid, 3), "energy": round(energy, 3), "stag": round(stag, 3)},
                }
            last_reject = float(ctx.get("last_plan_reject_at", 0))
            if last_reject and (now - last_reject) < config.PLAN_REJECT_COOLDOWN_SEC:
                wait = round(config.PLAN_REJECT_COOLDOWN_SEC - (now - last_reject), 1)
                return {"writes": writes, "next": "done", "phase": "schedule", "data": {"reason": "plan_cooldown", "wait": wait}}
            return {"writes": writes, "next": "planner", "phase": "schedule", "data": {"reason": "need_plan"}}

        # Plan completion takes priority — verify before reflecting
        all_done = plan and all(s.get("status") == "done" for s in plan)
        if all_done:
            return {"writes": writes, "next": "verifier", "phase": "schedule", "data": {"reason": "plan_complete"}}

        active = next((s for s in plan if s.get("status") == "active"), None)
        error_signal = _runtime_error_signal(ctx)
        mutator_due = (now - float(ctx.get("last_mutator_at", 0))) >= config.MUTATOR_MIN_INTERVAL_SEC
        if (
            error_signal
            and mutator_due
            and failures >= config.MUTATOR_ERROR_MIN_FAILURES
            and _mutator_math_gate(ctx)
            and not active
        ):
            writes["last_mutator_at"] = now
            writes["mutator_trigger"] = {
                "reason": "error_math",
                "stag": round(stag, 3),
                "pid": round(pid, 3),
                "energy": round(energy, 3),
                "failures": failures,
                "last_error": str(ctx.get("last_observation", ""))[:160],
            }
            return {
                "writes": writes,
                "next": "mutator",
                "phase": "schedule",
                "data": {"reason": "mutator_error_math", "stag": round(stag, 3), "pid": round(pid, 3), "failures": failures},
            }

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

        if active:
            return {"writes": writes, "next": "actor", "phase": "schedule", "data": {"reason": "execute", "step": active.get("code", "")[:120]}}


        pending = next((s for s in plan if s.get("status") == "pending"), None)
        if pending:
            pending["status"] = "active"
            return {"writes": {"plan": plan}, "next": "actor", "phase": "schedule", "data": {"reason": "advance", "step": pending.get("code", "")[:120]}}

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
        "goal", "plan", "screen", "desktop_summary", "focused_window", "history",
        "consecutive_failures", "stagnation", "energy", "completed", "last_observation", "denied_goals",
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
        denied_goals: list[dict[str, Any]] = list(ctx.get("denied_goals", []))
        completed: list[str] = list(ctx.get("completed", []))
        goal = str(ctx.get("goal", ""))
        if done_when and _is_blocked(denied_goals, done_when):
            log.emit("plan.blocked", {"done_when": done_when[:80]})
            return _reject_plan(ctx, "done_when denied too many times - try something different", event="plan.blocked")
        if mode == "done" or not sequence:
            if str(ctx.get("goal", "")).strip() and not list(ctx.get("completed", [])):
                return _reject_plan(ctx, "cannot declare done before any GOAL progress - use mode direct with Python steps")
            if list(ctx.get("completed", [])):
                return {"writes": {}, "next": "halt", "phase": "plan", "data": {"mode": "done", "reason": "goal_satisfied"}}
            return {"writes": {}, "next": "verifier", "phase": "plan", "data": {"mode": "done"}}
        from python_code import validate_python
        steps: list[dict[str, str]] = []
        code_errors: list[str] = []
        for i, s in enumerate(sequence[:config.MAX_PLAN_STEPS]):
            raw = _sanitize_plan_step(_step_code(s))
            ok, code, err = validate_python(raw)
            if not ok:
                code_errors.append(err)
                continue
            steps.append({"code": code, "status": "active" if i == 0 else "pending"})
        if not steps:
            reason = code_errors[0] if code_errors else "empty sequence - each step needs valid Python in code field"
            return _reject_plan(ctx, reason)
        return {
            "writes": {"plan": steps, "done_when": done_when, "consecutive_failures": 0, "progress_history": []},
            "next": "actor",
            "phase": "plan",
            "data": {"mode": mode, "steps": len(steps), "done_when": done_when},
        }

class ActorAgent:
    name: str = "actor"
    reads: list[str] = ["plan", "history", "consecutive_failures", "goal"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        from actions import run_python
        plan: list[dict[str, Any]] = ctx.get("plan", [])
        active = next((s for s in plan if s.get("status") == "active"), None)
        if not active:
            return {"writes": {}, "next": "planner", "phase": "actor.error", "data": {"error": "no active step"}}
        code, active, code_errors = _combine_plan_code(plan)
        if not code:
            err = code_errors[0] if code_errors else "empty plan sequence"
            history = _append_history(list(ctx.get("history", [])), {"verb": "python", "ok": False, "obs": err})
            active["status"] = "failed"
            failures = int(ctx.get("consecutive_failures", 0)) + 1
            return {"writes": {"plan": plan, "history": history, "consecutive_failures": failures, "last_observation": err}, "next": "planner", "phase": "actor", "data": {"ok": False, "verb": "python", "obs": err}}
        history: list[dict[str, Any]] = list(ctx.get("history", []))
        result = run_python(code)
        history = _append_history(history, {"verb": result.verb, "ok": result.success, "obs": result.observation})
        payload = {"ok": result.success, "verb": result.verb, "obs": result.observation}
        if result.success:
            for step in plan:
                if step.get("status") in ("active", "pending"):
                    step["status"] = "done"
            return {"writes": {"plan": plan, "history": history, "consecutive_failures": 0, "last_observation": result.observation}, "next": "stagnation", "phase": "actor", "data": payload}
        active["status"] = "failed"
        failures = int(ctx.get("consecutive_failures", 0)) + 1
        return {"writes": {"plan": plan, "history": history, "consecutive_failures": failures, "last_observation": result.observation}, "next": "planner", "phase": "actor", "data": payload}


class VerifierAgent:
    name: str = "verifier"
    reads: list[str] = ["goal", "screen", "history", "plan", "desktop_summary", "done_when", "completed", "last_observation", "denied_goals"]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        from llm import call_llm
        done_when = str(ctx.get("done_when", ""))
        completed: list[str] = list(ctx.get("completed", []))
        goal = str(ctx.get("goal", ""))
        denied_goals: list[dict[str, Any]] = list(ctx.get("denied_goals", []))
        missing = _missing_artifacts(done_when)
        if missing:
            denied_goals = _add_denial(denied_goals, done_when)
            return {
                "writes": {"plan": [], "done_when": "", "consecutive_failures": int(ctx.get("consecutive_failures", 0)) + 1, "denied_goals": denied_goals},
                "next": "stagnation",
                "phase": "verify",
                "data": {"verdict": "denied", "evidence": f"artifact(s) missing on disk: {', '.join(missing)}"},
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
            missing = _missing_artifacts(done_when)
            if missing:
                denied_goals = _add_denial(denied_goals, done_when)
                return {
                    "writes": {"plan": [], "done_when": "", "consecutive_failures": int(ctx.get("consecutive_failures", 0)) + 1, "denied_goals": denied_goals},
                    "next": "stagnation",
                    "phase": "verify",
                    "data": {"verdict": "denied", "evidence": f"LLM confirmed but artifact(s) missing: {', '.join(missing)}"},
                }
            return {"writes": {"denied_goals": denied_goals, "fission_approved": False}, "next": "fission_judge", "phase": "verify", "data": {"verdict": "confirmed", "evidence": evidence}}
        denied_goals = _add_denial(denied_goals, done_when)
        return {"writes": {"plan": [], "done_when": "", "consecutive_failures": 0, "progress_history": [], "denied_goals": denied_goals}, "next": "planner", "phase": "verify", "data": {"verdict": "denied", "evidence": evidence}}

class FissionJudgeAgent:
    name: str = "fission_judge"
    reads: list[str] = [
        "goal", "done_when", "last_observation", "history", "completed",
        "consecutive_failures", "denied_goals",
    ]

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        from llm import call_llm
        done_when = str(ctx.get("done_when", ""))
        completed: list[str] = list(ctx.get("completed", []))
        denied_goals: list[dict[str, Any]] = list(ctx.get("denied_goals", []))
        failures = int(ctx.get("consecutive_failures", 0))
        context = "MODE: FISSION_REVIEW\n\n" + _render_context(ctx, "fission_judge")
        context += "\n\n" + _similarity_hint(done_when, completed)
        system = _load_prompt("reflector")
        try:
            raw = call_llm(
                system, context, "fission_judge",
                max_tokens=getattr(config, "BUDGET_FISSION_JUDGE_OUT", config.BUDGET_VERIFIER_OUT),
            )
        except Exception as e:
            log.emit("fission_judge.error", {"error": str(e)})
            return {"writes": {}, "next": "stagnation", "phase": "fission_judge.error", "data": {"error": str(e)}}
        parsed = _extract_json(raw, ["verdict", "diagnosis", "suggestion", "rule"])
        verdict = str(parsed.get("verdict", "deny")).lower()
        diagnosis = str(parsed.get("diagnosis", ""))
        suggestion = str(parsed.get("suggestion", ""))
        rule = str(parsed.get("rule", ""))
        payload = {
            "verdict": verdict,
            "diagnosis": diagnosis[:200],
            "suggestion": suggestion[:200],
            "rule": rule[:120],
        }
        if rule.strip():
            _apply_mutation("planner", rule)
            _write_lesson(rule)
        if verdict == "credit":
            return {
                "writes": {"fission_approved": True, "activity_events": 1},
                "next": "done",
                "phase": "fission_judge",
                "data": payload,
            }
        denied_goals = _add_denial(denied_goals, done_when)
        log.emit("fission_blocked", {"reason": "llm_deny", "diagnosis": diagnosis[:160]})
        return {
            "writes": {
                "plan": [],
                "done_when": "",
                "fission_approved": False,
                "consecutive_failures": failures + 1,
                "denied_goals": denied_goals,
            },
            "next": "stagnation",
            "phase": "fission_judge",
            "data": payload,
        }


class ReflectorAgent:
    name: str = "reflector"
    reads: list[str] = [
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
        plan_steps: list[dict[str, Any]] = ctx.get("plan", [])
        retry = next((s for s in plan_steps if s.get("status") == "active"), None)
        # Escalate to mutator when math+errors persist after reflection
        if failures >= config.MUTATOR_ESCALATION_FAILURES or (
            failures >= config.MUTATOR_ERROR_MIN_FAILURES and _runtime_error_signal(ctx)
        ):
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


def _clip_context(text: str, limit: int) -> str:
    if limit <= 0 or len(text) <= limit:
        return text
    return text[:limit] + "..."


def _append_history(history: list[dict[str, Any]], entry: dict[str, Any]) -> list[dict[str, Any]]:
    obs = str(entry.get("obs", ""))
    if obs:
        entry = dict(entry)
        entry["obs"] = _clip_context(obs, config.CONTEXT_OBS_MAX)
    history.append(entry)
    return history[-config.MAX_HISTORY:]


def _advance_plan(plan: list[dict[str, Any]]) -> None:
    pending = next((s for s in plan if s.get("status") == "pending"), None)
    if pending:
        pending["status"] = "active"


def _combine_plan_code(plan: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | None, list[str]]:
    """Run sequence steps in one Python process so variables persist across steps."""
    partial = any(s.get("status") == "done" for s in plan)
    blocks: list[str] = []
    active: dict[str, Any] | None = None
    errors: list[str] = []
    for step in plan:
        status = str(step.get("status", ""))
        if status == "failed":
            continue
        if partial:
            if status not in ("done", "active", "pending"):
                continue
        elif status not in ("active", "pending"):
            continue
        if status == "active" and active is None:
            active = step
        raw = str(step.get("code", step.get("text", ""))).strip()
        if not raw:
            continue
        from python_code import validate_python
        ok, code, err = validate_python(raw)
        if not ok:
            errors.append(err)
            continue
        blocks.append(code)
    return "\n\n".join(blocks), active, errors





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
            goal = _clip_context(str(ctx.get("goal", "")), config.CONTEXT_GOAL_MAX)
            return "GOAL: " + goal if goal else ""
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
            screen = str(ctx.get("screen", "")).strip()
            if screen:
                parts.append(f"SCREEN ELEMENTS:\n{_clip_context(screen, config.CONTEXT_OBS_MAX)}")
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
                snippet = _clip_context(str(step.get("code", step.get("text", ""))).replace("\n", " "), config.CONTEXT_PLAN_CODE_MAX)
                lines.append(f"  {connector}{marker}{snippet}")
            return "\n".join(lines)
        case "history":
            recent: list[dict[str, Any]] = list(ctx.get("history", []))[-config.CONTEXT_HISTORY_LINES:]
            if not recent:
                return ""
            lines = ["HISTORY:"]
            for h in recent:
                ok = "\u2713" if h.get("ok") else "\u2717"
                obs = _clip_context(str(h.get("obs", "")), config.CONTEXT_OBS_MAX)
                lines.append(f"  {ok} {h.get('verb', '')}: {obs}")
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
        case "last_observation":
            obs = _clip_context(str(ctx.get("last_observation", "")), config.CONTEXT_OBS_MAX)
            if not obs:
                return ""
            return f"LAST_RESULT: {obs}"
        case "denied_goals":
            import time as _t2
            now = _t2.time()
            active = [d for d in ctx.get("denied_goals", []) if now - d.get("ts", 0) < DENIAL_DECAY_SECS]
            if not active:
                return ""
            blocked = list({d["dw"] for d in active if active.count(d) >= 2 or sum(1 for x in active if x.get("dw") == d.get("dw")) >= 2})
            if not blocked:
                return ""
            return "BLOCKED (denied 2x+):\n" + "\n".join(f"  - {b}" for b in blocked[:5])
        case "lessons":
            import lessons
            return lessons.format_for_context(n=config.CONTEXT_LESSONS_MAX)
        case "similarity":
            done_when = str(ctx.get("done_when", ""))
            completed = list(ctx.get("completed", []))
            if not done_when:
                return ""
            return _similarity_hint(done_when, completed)
        case "math":
            stag = ctx.get('stagnation', 0)
            if stag >= 0.8:
                return 'STATUS: stuck, not making progress'
            elif stag >= 0.4:
                return 'STATUS: slow progress'
            return 'STATUS: making progress'

        case "trigger":
            trig = ctx.get("mutator_trigger") or ctx.get("reflect_trigger", {})
            if not isinstance(trig, dict) or not trig:
                return ""
            reason = str(trig.get("reason", ""))
            failures = int(trig.get("failures", 0))
            stag = float(trig.get("stag", 0))
            step = trig.get("step", "")
            last_error = str(trig.get("last_error", "")).strip()
            parts = ["TRIGGER:"]
            if reason:
                parts.append(reason.replace("_", " "))
            if failures >= 3:
                parts.append(f"Failed {failures} times. Must change approach.")
            elif failures >= 1:
                parts.append(f"Failed {failures} time(s).")
            if stag >= 1.0:
                parts.append("Completely stuck.")
            if last_error:
                parts.append(f"Error: {last_error}")
            if step:
                parts.append(f"Last step: {step}")
            return " ".join(parts)
        case "completed":
            completed: list[str] = ctx.get("completed", [])
            if not completed:
                return ""
            lines = ["COMPLETED (no repeat credit):"]
            for c in completed[-config.CONTEXT_COMPLETED_MAX:]:
                lines.append(f"  - {c}")
            return "\n".join(lines)
        case "hints":
            return _milestone_hints(ctx)
        case "done_when":
            dw = ctx.get("done_when", "")
            if not dw:
                return ""
            return f"DONE_WHEN: {dw}"
        case _:
            return ""


_ELEMENT_ID_RE = re.compile(r"\[\d+\]")


def _step_code(s: Any) -> str:
    if isinstance(s, dict):
        for key in ("code", "text", "exec"):
            if key in s and str(s[key]).strip():
                return str(s[key]).strip()
        return ""
    if isinstance(s, str):
        text = s.strip()
        low = text.lower()
        if low.startswith("exec:"):
            return text[5:].lstrip("\n")
        if low.startswith("exec "):
            return text[5:].lstrip()
        return text
    return str(s).strip()


def _sanitize_plan_step(step: str) -> str:
    if not _ELEMENT_ID_RE.search(step):
        return step
    cleaned = _ELEMENT_ID_RE.sub("", step)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    log.emit("plan.sanitize", {"original": step, "cleaned": cleaned})
    return cleaned or step


def _load_prompt(role: str) -> str:
    path = config.PROMPTS_DIR / f"{role}.txt"
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


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


def _clean_mutation_text(append_text: str) -> str:
    clean_text = append_text.strip()
    for prefix in ("RULE:", "EVOLVE:"):
        if clean_text.upper().startswith(prefix):
            clean_text = clean_text[len(prefix):].strip()
    return clean_text


def _reject_mutation(clean_text: str, target: str) -> bool:
    if not clean_text:
        return True
    if _ELEMENT_ID_RE.search(clean_text) or re.search(r"click\s*\[", clean_text, re.I):
        log.emit("mutation.rejected", {"target": target, "reason": "element_id_in_mutation"})
        return True
    vague = ("consistency", "foundation", "stable quality", "future success", "strong base",
             "confirms current", "leads to stable", "baseline for")
    if any(v in clean_text.lower() for v in vague):
        log.emit("mutation.rejected", {"target": target, "reason": "vague_rule"})
        return True
    return False


def _apply_mutation(target: str, append_text: str) -> None:
    path = config.PROMPTS_DIR / f"{target}.txt"
    if not path.exists():
        return
    current = path.read_text(encoding="utf-8")
    clean_text = _clean_mutation_text(append_text)
    if _reject_mutation(clean_text, target):
        return
    parts = current.split("RULE:", 1)
    header = parts[0] if parts else ""
    if not header.strip():
        return
    rules = [block.strip() for block in current.split("\n\n") if block.strip().startswith("RULE:")]
    if len(rules) >= config.PROMPT_MAX_RULES:
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
    if _reject_mutation(clean_text, f"personality:{personality}"):
        return
    current = path.read_text(encoding="utf-8")
    header = current.split("EVOLVE:", 1)[0].strip()
    if not header:
        return
    evolutions = [block.strip() for block in current.split("\n") if block.strip().startswith("EVOLVE:")]
    if len(evolutions) >= config.PERSONALITY_MAX_EVOLUTIONS:
        kept = evolutions[-(config.PERSONALITY_MAX_EVOLUTIONS - 1):]
        current = header + "\n" + "\n".join(kept)
    new_content = current.rstrip() + f"\nEVOLVE: {clean_text}\n"
    path.write_text(new_content, encoding="utf-8")
    log.emit("personality.evolve", {"personality": personality, "appended": clean_text})


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
        context = _render_context(ctx, "mutator")
        plugin_errors = self._recent_plugin_errors()
        if plugin_errors:
            context += "\n\nPLUGIN ERRORS:\n" + "\n".join(f"  - {e}" for e in plugin_errors)
        if _runtime_error_signal(ctx):
            context += "\n\nRUNTIME ERRORS: planner/actor Python failed — write a plugin that helps recover or auto-fix."
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
