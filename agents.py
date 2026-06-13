"""Agents — pipeline stages. Each: run(board) → {phase, data, writes, next}."""
from __future__ import annotations
import ast
import difflib
import json
import os
from pathlib import Path
import py_compile
import re
import time
from typing import Any

import config
import log
from llm import call_llm
from python_code import goal_needs_gui, is_python_code, validate_python

_SIMPLE_FILE_DONE_PREFIX = "file_equals "
_CREATE_FILE_RE = re.compile(
    r"^(?:@[A-Za-z][A-Za-z0-9_]*\s+)?create\s+([^\s]+)\s+with\s+(.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)
_PLUGIN_NAME_RE = re.compile(r"^[a-z0-9_]+\.py$")


def _persona() -> str:
    return os.environ.get("ENDGAME_PERSONALITY", "").strip()


def _apply_human_goal(board: dict[str, Any]) -> bool:
    """Preempt maintenance with human @mention before planner runs."""
    try:
        import comms
        me = comms.agent_id()
        for msg in sorted(comms.pending_for(me, 6),
                          key=lambda m: (-comms.msg_priority(m), -int(m.get("id", 0) or 0))):
            msg_id = int(msg.get("id", 0))
            if msg_id <= board.get("_last_msg_id", 0):
                continue
            if str(msg.get("from", "")) != "human" and comms.msg_priority(msg) < config.PRI_HUMAN:
                continue
            board["_last_msg_id"] = msg_id
            payload = msg.get("payload") or msg.get("data") or {}
            goal_text = str(payload.get("goal", "")) if isinstance(payload, dict) else ""
            board["goal"] = goal_text or str(msg.get("text", ""))
            board["priority"] = config.PRI_HUMAN
            board["plan"] = []
            board["history"] = []
            board["_human_denials"] = 0
            board.get("_pressure", {}).update(failures=0)
            log.emit("interrupt", {"from": "human", "pri": config.PRI_HUMAN,
                                  "text": str(msg.get("text", ""))[:120]})
            return True
    except Exception:
        pass
    return False


class SchedulerAgent:
    """Decides what to do next: plan, continue, or idle."""

    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        if _apply_human_goal(board):
            return {"next": "planner", "data": {"reason": "human_goal"}}

        # Orchestrator: workers idle until comms_operator assigns work via bus
        if _persona() != "comms_operator":
            pri = board.get("priority", config.PRI_MAINTENANCE)
            if pri <= config.PRI_MAINTENANCE and not board.get("plan"):
                try:
                    import comms
                    if not comms.pending_for(comms.agent_id(), 1):
                        return None
                except Exception:
                    return None

        plan = board.get("plan", [])
        if not plan:
            if board.get("priority", config.PRI_MAINTENANCE) >= config.PRI_HUMAN:
                if board.get("_human_denials", 0) >= config.HUMAN_GOAL_MAX_DENIALS:
                    _decline_human_goal(board, "max retries exceeded")
                    return None
            if _persona() == "comms_operator":
                # Deterministic MoE in engine._moe_route handles normal cycles.
                # LLM planner only when human (pri=3) interrupted this persona.
                if board.get("priority", config.PRI_MAINTENANCE) < config.PRI_HUMAN:
                    return None
            return {"next": "planner", "data": {"reason": "need_plan"}}
        active = [s for s in plan if isinstance(s, dict) and s.get("status") == "active"]
        if active:
            return {"next": "actor", "data": {"reason": "has_active_step"}}
        pending = [s for s in plan if isinstance(s, dict) and s.get("status") == "pending"]
        if pending:
            pending[0]["status"] = "active"
            return {"next": "actor", "data": {"reason": "next_step"}}
        # All steps done
        return {"next": "verifier", "data": {"reason": "plan_complete"}}


class PlannerAgent:
    """Generates a plan from the goal."""

    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        goal = board.get("goal", "")
        if not goal:
            return None
        if goal_needs_gui(goal):
            return _gui_decline_plan(board, goal)
        simple_file_plan = _simple_file_plan(goal)
        if simple_file_plan:
            return simple_file_plan
        log.emit("planner.pending", {"goal": goal[:80]})
        system = _load_prompt("planner")
        persona = _persona()
        if persona:
            pfile = config.PROMPTS_DIR / "personalities" / f"{persona}.txt"
            if pfile.exists():
                system += f"\n\nPERSONA ({persona}):\n{pfile.read_text(encoding='utf-8').strip()}"
        history_ctx = _format_history(board.get("history", []))
        bus_ctx = ""
        try:
            import comms
            bus_ctx = comms.format_bus_context(10 if persona == "comms_operator" else 6,
                                                for_agent=persona or None)
        except Exception:
            pass
        stag = board.get("stagnation", board.get("_pressure", {}).get("stagnation", 0))
        pwr = board.get("power", 1.0 - float(stag))
        user = (f"GOAL: {goal}\n\nPRESSURE: stagnation={stag:.3f} power={pwr:.3f}\n"
                f"{history_ctx}\n{bus_ctx}\n\nPlan JSON:")
        schema = _load_schema("planner")
        raw = call_llm(system, user, "planner", schema=schema)
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {"phase": "planner.error", "data": {"error": "invalid JSON",
                    "raw": str(raw)[:config.PLANNER_ERROR_RAW_MAX]}}
        mode = parsed.get("mode", "direct")
        if mode == "done":
            board["plan"] = []
            return {"phase": "plan", "data": {"mode": "done", "done_when": parsed.get("done_when", "")},
                    "writes": {"plan": []}}
        steps = parsed.get("sequence", [])
        if not steps:
            return {"phase": "planner.error", "data": {"error": "empty sequence"}}
        for i, s in enumerate(steps):
            s["status"] = "active" if i == 0 else "pending"
        done_when = parsed.get("done_when", "")
        writes: dict[str, Any] = {"plan": steps, "done_when": done_when}
        if _persona() == "comms_operator":
            writes["_last_route"] = time.time()
        return {
            "phase": "plan", "next": "actor",
            "data": {"mode": mode, "steps": len(steps), "done_when": done_when},
            "writes": writes,
        }


class ActorAgent:
    """Executes the active plan step (Python code)."""

    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        plan = board.get("plan", [])
        active = next((s for s in plan if isinstance(s, dict) and s.get("status") == "active"), None)
        if not active:
            return None
        code = str(active.get("code", ""))
        if not is_python_code(code):
            active["status"] = "done"
            active["result"] = "skipped: not python"
            return {"phase": "actor", "data": {"ok": False, "obs": "not python code"}}
        from actions import run_python
        result = run_python(code)
        active["status"] = "done"
        active["result"] = result.observation[:config.EXEC_OUTPUT_LIMIT]
        ok = result.success
        obs = result.observation[:200]
        if not ok:
            board.setdefault("history", []).append({"step": code[:100], "ok": False, "obs": obs})
        return {"phase": "actor", "data": {"ok": ok, "obs": obs}, "next": "verifier" if ok else None}


class VerifierAgent:
    """Verifies plan completion."""

    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        done_when = board.get("done_when", "")
        if not done_when:
            return {"phase": "verify", "data": {"verdict": "confirmed", "evidence": "no done_when set"}}
        simple_file_result = _verify_simple_file_done(done_when)
        if simple_file_result:
            ok, evidence = simple_file_result
            if ok:
                board["plan"] = []
                board.setdefault("completed", []).append(done_when)
                if board.get("priority", config.PRI_MAINTENANCE) >= config.PRI_HUMAN:
                    board["priority"] = config.PRI_MAINTENANCE
                    board["goal"] = ""
                    board["_human_denials"] = 0
                return {"phase": "verify", "data": {"verdict": "confirmed", "evidence": evidence},
                        "next": "fission_judge"}
            board["plan"] = []
            board.setdefault("history", []).append({"denied": done_when, "reason": evidence})
            _post_failure_candidate(board, done_when, evidence)
            return {"phase": "verify", "data": {"verdict": "denied", "evidence": evidence},
                    "next": "reflector"}
        plan = board.get("plan", [])
        results = [str(s.get("result", ""))[:200] for s in plan if isinstance(s, dict)]
        system = _load_prompt("verifier")
        user = f"DONE_WHEN: {done_when}\n\nSTEP RESULTS:\n" + "\n".join(results)
        schema = _load_schema("verifier")
        raw = call_llm(system, user, "verifier", schema=schema)
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {"phase": "verifier.error", "data": {"error": "invalid JSON"}}
        verdict = parsed.get("verdict", "denied")
        if verdict == "confirmed":
            board["plan"] = []
            board.setdefault("completed", []).append(done_when)
            if board.get("priority", config.PRI_MAINTENANCE) >= config.PRI_HUMAN:
                board["priority"] = config.PRI_MAINTENANCE
                board["goal"] = ""
                board["_human_denials"] = 0
            return {"phase": "verify", "data": {"verdict": "confirmed", "evidence": parsed.get("evidence", "")},
                    "next": "fission_judge"}
        # Denied — clear plan, will replan
        board["plan"] = []
        evidence = str(parsed.get("evidence", ""))
        board.setdefault("history", []).append({"denied": done_when, "reason": evidence})
        _post_failure_candidate(board, done_when, evidence)
        return {"phase": "verify", "data": {"verdict": "denied", "evidence": evidence},
                "next": "reflector"}


class FissionJudgeAgent:
    """Awards fission credit for confirmed work."""

    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        completed = board.get("completed", [])
        if not completed:
            return None
        fissions = board.get("fissions", 0) + 1
        board["fissions"] = fissions
        latest = str(completed[-1])
        fitness = _evolution_fitness(board, fissions)
        _post_evolution_candidate(board, fissions, latest, fitness)
        return {"phase": "fission", "data": {
            "fissions": fissions,
            "completed": latest,
            "fitness": fitness,
        }}


class ReflectorAgent:
    """Diagnoses verifier denials and feeds a simpler rule back to planning."""

    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        history = board.get("history", [])
        last_denial = next((h for h in reversed(history)
                            if isinstance(h, dict) and h.get("denied")), {})
        pressure = board.get("_pressure", {})
        failures = int(pressure.get("failures", 0) or 0)
        stagnation = float(pressure.get("stagnation", board.get("stagnation", 0.0)) or 0.0)
        user = (
            f"GOAL: {str(board.get('goal', ''))[:400]}\n"
            f"TRIGGER: stagnation={stagnation:.3f} failures={failures} "
            f"human_denials={int(board.get('_human_denials', 0) or 0)}\n"
            f"DENIED_DONE_WHEN: {str(last_denial.get('denied', ''))[:400]}\n"
            f"EVIDENCE: {str(last_denial.get('reason', ''))[:600]}\n"
            "Reflect JSON:"
        )
        raw = call_llm(_load_prompt("reflector"), user, "reflector", schema=_load_schema("reflector"))
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            parsed = _fallback_reflection(last_denial, failures, stagnation)
        reflection = {
            "diagnosis": str(parsed.get("diagnosis", ""))[:300],
            "suggestion": str(parsed.get("suggestion", ""))[:300],
            "rule": str(parsed.get("rule", ""))[:180],
        }
        if not reflection["diagnosis"] or not reflection["suggestion"]:
            reflection = _fallback_reflection(last_denial, failures, stagnation)
        writes = {
            "plan": [],
            "history": history[-config.MAX_HISTORY:] + [{"reflection": reflection}],
            "reflection": reflection,
        }
        return {"phase": "reflect", "data": reflection, "writes": writes, "next": "mutator"}


class MutatorAgent:
    """Applies bounded plugin patches after recurring verifier pressure."""

    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        pressure = board.get("_pressure", {})
        failures = int(pressure.get("failures", 0) or 0)
        denials = int(board.get("_human_denials", 0) or 0)
        failure_events = max(failures, denials)
        reflection = board.get("reflection")
        if failure_events < config.MUTATE_AFTER_FAILURES or not isinstance(reflection, dict):
            return {
                "phase": "mutate",
                "data": {
                    "action": "none",
                    "reason": "waiting for recurring failure pressure",
                    "failures": failures,
                    "human_denials": denials,
                    "failure_events": failure_events,
                },
                "next": "planner",
            }

        plugin_names = _existing_plugin_names()
        user = (
            f"GOAL: {str(board.get('goal', ''))[:400]}\n"
            f"PRESSURE: failures={failures} human_denials={denials}\n"
            f"REFLECTION: {json.dumps(reflection, ensure_ascii=False)[:700]}\n"
            f"EXISTING_PLUGINS: {', '.join(plugin_names) or 'none'}\n"
            f"{_format_history(board.get('history', []))}\n"
            "Mutation JSON:"
        )
        raw = call_llm(_load_prompt("mutator"), user, "mutator", schema=_load_schema("mutator"))
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {
                "phase": "mutate",
                "data": {"action": "none", "reason": "invalid mutator JSON"},
                "next": "planner",
            }

        action = str(parsed.get("action", "none"))
        if action == "write":
            action = "patch_plugin"
        if action not in {"write_plugin", "patch_plugin"}:
            return {
                "phase": "mutate",
                "data": {"action": "none", "reason": str(parsed.get("content", "no mutation"))[:160]},
                "next": "planner",
            }

        filename = str(parsed.get("filename", ""))
        ok, obs, diff = _apply_plugin_mutation(filename, str(parsed.get("content", "")))
        data: dict[str, Any] = {
            "action": "patch_plugin",
            "filename": filename[:80],
            "ok": ok,
            "obs": obs,
        }
        if diff:
            data["diff"] = diff[:500]
        if ok:
            _post_mutation_candidate(board, filename, diff, obs)
            return {"phase": "mutate", "data": data, "writes": {"mutation": data}, "next": "planner"}
        return {"phase": "mutate", "data": data, "next": "planner"}


# --- Helpers ---

def _decline_human_goal(board: dict[str, Any], reason: str) -> None:
    goal = str(board.get("goal", ""))[:120]
    try:
        import comms
        comms.post(
            comms.agent_id(), "colony",
            f"@human cannot complete: {reason}. Goal: {goal}",
            priority=config.PRI_HUMAN,
        )
    except Exception:
        pass
    board["plan"] = []
    board["goal"] = ""
    board["priority"] = config.PRI_MAINTENANCE
    board["_human_denials"] = 0
    log.emit("human.decline", {"reason": reason, "goal": goal[:80]})


def _gui_decline_plan(board: dict[str, Any], goal: str) -> dict[str, Any]:
    code = (
        "bus_post(bus_id(), 'colony', "
        "'@human GUI/desktop tasks not supported — colony has no GUI agent. "
        "Try: write hello.txt with Path.write_text', priority=3)\n"
        "print('declined: GUI task not supported')"
    )
    done_when = "decline posted to bus"
    return {
        "phase": "plan", "next": "actor",
        "data": {"mode": "direct", "steps": 1, "done_when": done_when},
        "writes": {"plan": [{"status": "active", "code": code}], "done_when": done_when},
    }


def _simple_file_plan(goal: str) -> dict[str, Any] | None:
    parsed = _parse_simple_file_goal(goal)
    if not parsed:
        return None
    rel_path, content = parsed
    done_when = _SIMPLE_FILE_DONE_PREFIX + json.dumps(
        {"path": rel_path, "content": content},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    code = (
        f"target = Path({json.dumps(rel_path)})\n"
        "target.parent.mkdir(parents=True, exist_ok=True)\n"
        f"target.write_text({json.dumps(content)}, encoding='utf-8')\n"
        "actual = target.read_text(encoding='utf-8')\n"
        "print(f'verified {target.as_posix()} == {actual!r}')"
    )
    return {
        "phase": "plan", "next": "actor",
        "data": {"mode": "direct", "steps": 1, "done_when": done_when},
        "writes": {"plan": [{"status": "active", "code": code}], "done_when": done_when},
    }


def _parse_simple_file_goal(goal: str) -> tuple[str, str] | None:
    match = _CREATE_FILE_RE.match(str(goal).strip())
    if not match:
        return None
    rel_path = match.group(1).strip("'\"")
    content = _strip_matching_quotes(match.group(2).strip())
    path = Path(rel_path)
    if path.is_absolute() or path.suffix.lower() == ".py" or any(part in ("", "..") for part in path.parts):
        return None
    return rel_path, content


def _strip_matching_quotes(text: str) -> str:
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        return text[1:-1]
    return text


def _verify_simple_file_done(done_when: str) -> tuple[bool, str] | None:
    if not str(done_when).startswith(_SIMPLE_FILE_DONE_PREFIX):
        return None
    try:
        spec = json.loads(str(done_when)[len(_SIMPLE_FILE_DONE_PREFIX):])
        rel_path = str(spec["path"])
        expected = str(spec["content"])
    except (KeyError, TypeError, json.JSONDecodeError):
        return False, "invalid file verification target"
    target = (config.BASE_DIR / rel_path).resolve()
    try:
        target.relative_to(config.BASE_DIR.resolve())
    except ValueError:
        return False, f"{rel_path} resolves outside workspace"
    if not target.exists():
        return False, f"{rel_path} not found"
    if target.is_dir():
        return False, f"{rel_path} is a directory"
    actual = target.read_text(encoding="utf-8")
    if actual != expected:
        return False, f"{rel_path} content mismatch: {actual!r}"
    return True, f"{rel_path} contains expected content"


def _evolution_fitness(board: dict[str, Any], fissions: int) -> float:
    pressure = board.get("_pressure", {})
    stagnation = float(pressure.get("stagnation", board.get("stagnation", 0.0)) or 0.0)
    power = float(board.get("power", 1.0 - stagnation) or 0.0)
    failures = int(pressure.get("failures", 0) or 0)
    credit = min(0.2, fissions * 0.02)
    score = 0.55 + (power * 0.35) + credit - (stagnation * 0.25) - min(0.2, failures * 0.04)
    return round(max(0.0, min(1.0, score)), 4)


def _post_evolution_candidate(board: dict[str, Any], fissions: int, completed: str, fitness: float) -> None:
    try:
        import comms
        pressure = board.get("_pressure", {})
        comms.post_evolve(
            comms.agent_id(),
            comms.agent_id(),
            "retain",
            fitness=fitness,
            completed=completed,
            reason="fission credit",
            data={
                "fissions": fissions,
                "stagnation": round(float(pressure.get("stagnation", board.get("stagnation", 0.0)) or 0.0), 4),
                "power": round(float(board.get("power", 0.0) or 0.0), 4),
                "velocity": round(float(pressure.get("velocity", board.get("velocity", 0.0)) or 0.0), 4),
            },
        )
    except Exception:
        pass


def _failure_fitness(board: dict[str, Any]) -> float:
    pressure = board.get("_pressure", {})
    stagnation = float(pressure.get("stagnation", board.get("stagnation", 0.0)) or 0.0)
    failures = int(pressure.get("failures", 0) or 0)
    denials = int(board.get("_human_denials", 0) or 0)
    score = 0.35 - (stagnation * 0.25) - min(0.2, failures * 0.04) - min(0.2, denials * 0.06)
    return round(max(0.0, min(0.49, score)), 4)


def _post_failure_candidate(board: dict[str, Any], done_when: str, evidence: str) -> None:
    try:
        import comms
        pressure = board.get("_pressure", {})
        comms.post_evolve(
            comms.agent_id(),
            comms.agent_id(),
            "evict",
            fitness=_failure_fitness(board),
            completed=str(done_when),
            reason="verify denied",
            data={
                "evidence": str(evidence)[:200],
                "stagnation": round(float(pressure.get("stagnation", board.get("stagnation", 0.0)) or 0.0), 4),
                "failures": int(pressure.get("failures", 0) or 0),
                "human_denials": int(board.get("_human_denials", 0) or 0),
            },
        )
    except Exception:
        pass


def _existing_plugin_names() -> list[str]:
    try:
        return [p.name for p in sorted(config.PLUGINS_DIR.glob("*.py")) if p.is_file()]
    except OSError:
        return []


def _resolve_existing_plugin(filename: str) -> Path | None:
    raw = str(filename).strip().replace("\\", "/")
    if raw.startswith("plugins/"):
        raw = raw[len("plugins/"):]
    if "/" in raw or not _PLUGIN_NAME_RE.fullmatch(raw):
        return None
    path = (config.PLUGINS_DIR / raw).resolve()
    try:
        path.relative_to(config.PLUGINS_DIR.resolve())
    except ValueError:
        return None
    if not path.is_file():
        return None
    return path


def _strip_code_fence(text: str) -> str:
    cleaned = str(text).strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def _plugin_defines_run(source: str) -> tuple[bool, str]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        where = f"line {exc.lineno}" if exc.lineno else "module"
        return False, f"SyntaxError: {exc.msg} ({where})"
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "run":
            args = node.args.args
            if args and args[0].arg == "board":
                return True, ""
            return False, "plugin run function must accept board as its first argument"
    return False, "plugin must define def run(board)"


def _mutation_diff(filename: str, before: str, after: str) -> str:
    diff = difflib.unified_diff(
        before.splitlines(),
        after.splitlines(),
        fromfile=f"a/plugins/{filename}",
        tofile=f"b/plugins/{filename}",
        lineterm="",
        n=2,
    )
    return "\n".join(list(diff)[:80])


def _apply_plugin_mutation(filename: str, content: str) -> tuple[bool, str, str]:
    path = _resolve_existing_plugin(filename)
    if path is None:
        return False, "filename must be an existing plugins/[a-z0-9_]+.py file", ""

    ok, cleaned, err = validate_python(_strip_code_fence(content))
    if not ok:
        return False, err, ""
    cleaned = cleaned.rstrip() + "\n"
    has_run, run_err = _plugin_defines_run(cleaned)
    if not has_run:
        return False, run_err, ""

    try:
        before = path.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"read failed: {exc}", ""
    if before == cleaned:
        return False, "plugin unchanged", ""

    diff = _mutation_diff(path.name, before, cleaned)
    try:
        path.write_text(cleaned, encoding="utf-8")
        py_compile.compile(str(path), doraise=True)
    except Exception as exc:
        try:
            path.write_text(before, encoding="utf-8")
            py_compile.compile(str(path), doraise=True)
        except Exception:
            pass
        return False, f"compile failed and original plugin was restored: {exc}", ""
    return True, f"patched plugins/{path.name}", diff


def _mutation_fitness(board: dict[str, Any]) -> float:
    pressure = board.get("_pressure", {})
    stagnation = float(pressure.get("stagnation", board.get("stagnation", 0.0)) or 0.0)
    failures = int(pressure.get("failures", 0) or 0)
    score = 0.52 - min(0.12, failures * 0.02) - min(0.12, stagnation * 0.12)
    return round(max(0.0, min(0.59, score)), 4)


def _post_mutation_candidate(board: dict[str, Any], filename: str, diff: str, obs: str) -> None:
    try:
        import comms
        pressure = board.get("_pressure", {})
        path = _resolve_existing_plugin(filename)
        display = f"plugins/{path.name}" if path else str(filename)[:80]
        comms.post_evolve(
            comms.agent_id(),
            comms.agent_id(),
            "patch_plugin",
            fitness=_mutation_fitness(board),
            completed=display,
            reason="mutator patch",
            diff=diff,
            data={
                "filename": display,
                "evidence": str(obs)[:200],
                "stagnation": round(float(pressure.get("stagnation", board.get("stagnation", 0.0)) or 0.0), 4),
                "failures": int(pressure.get("failures", 0) or 0),
                "human_denials": int(board.get("_human_denials", 0) or 0),
            },
        )
    except Exception:
        pass


def _fallback_reflection(last_denial: dict[str, Any], failures: int, stagnation: float) -> dict[str, str]:
    denied = str(last_denial.get("denied", "the milestone"))[:120]
    reason = str(last_denial.get("reason", "evidence did not satisfy verifier"))[:160]
    return {
        "diagnosis": (
            f"Verifier denied {denied}; evidence gap was: {reason}. "
            f"Pressure shows failures={failures}, stagnation={stagnation:.2f}."
        ),
        "suggestion": (
            "Plan one smaller Python step that prints concrete evidence, then verify only "
            "that evidence before attempting broader coordination."
        ),
        "rule": "Print exact evidence for the smallest done_when before verification.",
    }


def _load_prompt(role: str) -> str:
    path = config.PROMPTS_DIR / f"{role}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return f"You are a {role}."


def _load_schema(role: str) -> dict | None:
    path = config.SCHEMAS_DIR / f"{role}.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _format_history(history: list) -> str:
    if not history:
        return ""
    lines = ["RECENT HISTORY:"]
    for h in history[-config.MAX_HISTORY:]:
        if isinstance(h, dict):
            lines.append(f"  {json.dumps(h, ensure_ascii=False)[:120]}")
    return "\n".join(lines)
