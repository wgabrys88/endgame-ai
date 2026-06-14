"""Agents — pipeline stages. Each: run(board) → {phase, data, writes, next}."""
from __future__ import annotations
import ast
import difflib
import json
import os
from pathlib import Path
import py_compile
import re
import sys
import tempfile
import time
import types
from typing import Any

import config
import log
from llm import LLMResult, call_llm
from python_code import goal_needs_gui, gui_mode_enabled, is_python_code, validate_python

_SIMPLE_FILE_DONE_PREFIX = "file_equals "
_CREATE_FILE_RE = re.compile(
    r"^(?:@[A-Za-z][A-Za-z0-9_]*\s+)?create\s+([^\s]+)\s+with\s+(.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)
_PLUGIN_NAME_RE = re.compile(r"^[a-z0-9_]+\.py$")
_MUTATOR_ALLOWED_IMPORTS = frozenset({"time", "json", "math", "statistics", "collections", "datetime"})
_MUTATOR_ALLOWED_FROM_IMPORTS = {
    "comms": frozenset({"agent_id", "post", "post_evolve", "post_telemetry"}),
}
_MUTATOR_BLOCKED_ROOTS = frozenset({
    "builtins", "ctypes", "os", "pathlib", "requests", "shutil", "socket", "subprocess",
    "sys", "urllib", "winreg",
})
_MUTATOR_BLOCKED_CALLS = frozenset({
    "__import__", "breakpoint", "compile", "eval", "exec", "getattr", "globals", "input",
    "locals", "open", "setattr", "vars",
})
_MUTATOR_BLOCKED_ATTRS = frozenset({
    "call", "connect", "mkdir", "open", "popen", "read", "read_text", "remove", "rename",
    "replace", "request", "rmdir", "run", "startfile", "system", "unlink", "urlopen",
    "write", "write_text", "writelines",
})
_MUTATOR_BLOCKED_BOARD_METHODS = frozenset({"clear", "pop", "popitem", "setdefault", "update"})
_MUTATOR_WRITE_PREFIX = "_plugin_"
_PROTECTED_PLUGINS = frozenset({"comms_beacon.py", "web_sentinel.py", "fission_log.py"})
_STABLE_SYSTEM: dict[str, str] = {}
_REASONING_CONTRACT = (
    "REASONING (separate channel — logged for debugging and persona adaptation):\n"
    "- Think step-by-step in your reasoning trace: inbox, pressure, risks, plan shape.\n"
    "- Do NOT put analysis or markdown in the final content field.\n"
    "OUTPUT (final content only):\n"
    "- ONE raw JSON object. No ``` fences. No prose before or after the JSON.\n"
)

_SCHEMA_USER_HEADERS: dict[str, str] = {
    "planner": (
        _REASONING_CONTRACT
        + "JSON_OUTPUT (schema contract — user message, not system):\n"
        '{"mode":"direct"|"done","sequence":[{"code":"..."}],"done_when":"..."}\n'
        "mode=direct for actionable plans. sequence=1-3 Python steps for one outcome.\n"
    ),
    "verifier": (
        _REASONING_CONTRACT
        + "JSON_OUTPUT (schema contract — user message, not system):\n"
        '{"verdict":"confirmed"|"denied","evidence":"..."}\n'
    ),
    "reflector": (
        _REASONING_CONTRACT
        + "JSON_OUTPUT (schema contract — user message, not system):\n"
        '{"diagnosis":"...","suggestion":"...","rule":"..."}\n'
    ),
    "mutator": (
        _REASONING_CONTRACT
        + "JSON_OUTPUT (schema contract — user message, not system):\n"
        '{"action":"patch_plugin"|"none","filename":"plugins/...","content":"..."}\n'
    ),
    "fission_judge": (
        _REASONING_CONTRACT
        + "JSON_OUTPUT (schema contract — user message, not system):\n"
        '{"verdict":"credit"|"deny","diagnosis":"...","suggestion":"...","rule":"..."}\n'
    ),
}


def _persona() -> str:
    return os.environ.get("ENDGAME_PERSONALITY", "").strip()


def _llm_event_data(result: LLMResult, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Attach captured reasoning trace to pipeline phase events."""
    data: dict[str, Any] = {
        "has_reasoning": bool(result.reasoning),
        "reasoning_chars": len(result.reasoning),
        "reasoning_tokens": result.reasoning_tokens,
    }
    if result.reasoning:
        limit = int(config.LLM_REASONING_LOG_MAX)
        data["reasoning"] = result.reasoning if limit <= 0 else result.reasoning[:limit]
    if extra:
        data.update(extra)
    return data


def _stable_system(role: str) -> str:
    """Immutable system prompt per role — never embed persona, bus, or schema here."""
    cached = _STABLE_SYSTEM.get(role)
    if cached is not None:
        return cached
    cached = _load_prompt(role)
    _STABLE_SYSTEM[role] = cached
    return cached


def _user_with_schema(role: str, body: str) -> str:
    """Prepend constant schema contract to user message for KV-friendly system prefix."""
    header = _SCHEMA_USER_HEADERS.get(role, "")
    if not header:
        return body
    return f"{header}\n---TASK_STATE---\n{body}"


def _persona_prompt(persona: str) -> str:
    if not persona:
        return ""
    path = config.PROMPTS_DIR / "personalities" / f"{persona}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


def _desktop_context() -> str:
    if not gui_mode_enabled():
        return ""
    try:
        from observer import observe
        obs = observe()
        parts = [f"DESKTOP_FOCUSED: {obs.focused_title}"]
        if obs.desktop_summary:
            parts.append(f"DESKTOP_SUMMARY: {obs.desktop_summary[:600]}")
        if obs.context_text:
            parts.append("DESKTOP_ELEMENTS:")
            parts.append(obs.context_text[:2000])
        return "\n".join(parts)
    except Exception as exc:
        return f"DESKTOP_OBSERVE_ERROR: {type(exc).__name__}: {exc}"


def _relative_manifest(paths: list[Path]) -> str:
    out: list[str] = []
    for path in sorted(paths, key=lambda item: str(item).lower()):
        try:
            out.append(path.relative_to(config.BASE_DIR).as_posix())
        except ValueError:
            continue
    return ", ".join(out) if out else "none"


def _repo_manifest_context() -> str:
    try:
        top_py = [p for p in config.BASE_DIR.glob("*.py") if p.is_file()]
        plugin_py = [p for p in config.PLUGINS_DIR.glob("*.py") if p.is_file()]
        docs = [
            config.BASE_DIR / "AGENTS.md",
            config.BASE_DIR / "KNOWLEDGE.md",
            config.BASE_DIR / "README.md",
            config.BASE_DIR / "sessions" / "20260614_132940" / "README.md",
            config.BASE_DIR / "ENDGAME_GOLDEN_RUN.html",
            config.BASE_DIR / "ENDGAME_VISION_ADVANCED.html",
        ]
        docs = [p for p in docs if p.is_file()]
    except OSError:
        return ""
    return "\n".join([
        "AVAILABLE_FILES (use exact paths; do not invent colony.py, endgame_ai.py, event.log, or other phantom files):",
        f"  TOP_LEVEL_PY: {_relative_manifest(top_py)}",
        f"  PLUGIN_PY: {_relative_manifest(plugin_py)}",
        f"  TRACKED_DOCS: {_relative_manifest(docs)}",
    ])


def _planner_messages(board: dict[str, Any]) -> tuple[str, str]:
    """Constant system prompt; persona/goal/schema/state in user message for KV reuse."""
    system = _stable_system("planner")
    persona = _persona()
    persona_text = _persona_prompt(persona)
    history_ctx = _format_history(board.get("history", []))
    bus_ctx = ""
    try:
        import comms
        bus_ctx = comms.format_bus_context(10 if persona == "comms_operator" else 6,
                                          for_agent=persona or None)
    except Exception:
        pass
    stag = board.get("stagnation", board.get("_pressure", {}).get("stagnation", 0))
    try:
        stag_f = float(stag)
    except (TypeError, ValueError):
        stag_f = 0.0
    pwr = board.get("power", 1.0 - stag_f)
    desktop_ctx = _desktop_context()
    manifest_ctx = _repo_manifest_context()
    parts = [f"PERSONA_NAME: {persona or 'default'}"]
    if persona_text:
        parts += ["PERSONA_MISSION:", persona_text, ""]
    parts += [
        f"GOAL: {str(board.get('goal', ''))[:800]}",
        "",
        f"PRESSURE: stagnation={stag_f:.3f} power={float(pwr):.3f}",
    ]
    if manifest_ctx:
        parts += ["", manifest_ctx]
    if desktop_ctx:
        parts += ["", desktop_ctx]
    if history_ctx:
        parts += ["", history_ctx]
    if bus_ctx:
        parts += ["", bus_ctx]
    parts += ["", "Plan JSON:"]
    return system, _user_with_schema("planner", "\n".join(parts))


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
        system, user = _planner_messages(board)
        schema = _load_schema("planner")
        llm_out = call_llm(system, user, "planner", schema=schema, cache_key="planner")
        try:
            parsed = json.loads(llm_out.text)
        except (json.JSONDecodeError, TypeError):
            return {"phase": "planner.error", "data": _llm_event_data(llm_out, {
                "error": "invalid JSON",
                "raw": str(llm_out.text)[:config.PLANNER_ERROR_RAW_MAX],
            })}
        mode = parsed.get("mode", "direct")
        if mode == "done":
            board["plan"] = []
            return {"phase": "plan", "data": _llm_event_data(llm_out, {
                "mode": "done", "done_when": parsed.get("done_when", ""),
            }), "writes": {"plan": []}}
        steps = parsed.get("sequence", [])
        if not steps:
            return {"phase": "planner.error", "data": _llm_event_data(llm_out, {"error": "empty sequence"})}
        contract_error = _validate_planner_contract(steps, parsed.get("done_when", ""))
        if contract_error:
            return {"phase": "planner.error", "data": _llm_event_data(llm_out, {
                "error": contract_error,
                "raw": str(llm_out.text)[:config.PLANNER_ERROR_RAW_MAX],
            })}
        for i, s in enumerate(steps):
            s["status"] = "active" if i == 0 else "pending"
        done_when = parsed.get("done_when", "")
        writes: dict[str, Any] = {"plan": steps, "done_when": done_when}
        if _persona() == "comms_operator":
            writes["_last_route"] = time.time()
        return {
            "phase": "plan", "next": "actor",
            "data": _llm_event_data(llm_out, {
                "mode": mode, "steps": len(steps), "done_when": done_when,
            }),
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
                board["_last_verified_goal"] = str(board.get("goal", ""))[:400]
                board["_last_verified_priority"] = board.get("priority", config.PRI_MAINTENANCE)
                board["_last_verifier_evidence"] = evidence[:400]
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
        system = _stable_system("verifier")
        user = _user_with_schema(
            "verifier",
            f"DONE_WHEN: {done_when}\n\nSTEP RESULTS:\n" + "\n".join(results),
        )
        schema = _load_schema("verifier")
        llm_out = call_llm(system, user, "verifier", schema=schema, cache_key="verifier")
        try:
            parsed = json.loads(llm_out.text)
        except (json.JSONDecodeError, TypeError):
            return {"phase": "verifier.error", "data": _llm_event_data(llm_out, {"error": "invalid JSON"})}
        verdict = parsed.get("verdict", "denied")
        if verdict == "confirmed":
            board["plan"] = []
            board.setdefault("completed", []).append(done_when)
            evidence = str(parsed.get("evidence", ""))
            board["_last_verified_goal"] = str(board.get("goal", ""))[:400]
            board["_last_verified_priority"] = board.get("priority", config.PRI_MAINTENANCE)
            board["_last_verifier_evidence"] = evidence[:400]
            if board.get("priority", config.PRI_MAINTENANCE) >= config.PRI_HUMAN:
                board["priority"] = config.PRI_MAINTENANCE
                board["goal"] = ""
                board["_human_denials"] = 0
            return {"phase": "verify", "data": _llm_event_data(llm_out, {
                "verdict": "confirmed", "evidence": evidence,
            }), "next": "fission_judge"}
        # Denied — clear plan, will replan
        board["plan"] = []
        evidence = str(parsed.get("evidence", ""))
        board.setdefault("history", []).append({"denied": done_when, "reason": evidence})
        _post_failure_candidate(board, done_when, evidence)
        return {"phase": "verify", "data": _llm_event_data(llm_out, {
            "verdict": "denied", "evidence": evidence,
        }), "next": "reflector"}


class FissionJudgeAgent:
    """Awards fission credit for confirmed, useful work."""

    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        completed = board.get("completed", [])
        if not completed:
            return None
        latest = str(completed[-1])
        review = _fission_review(board, latest)
        if review.get("verdict") != "credit":
            reason = str(review.get("diagnosis", "fission judge denied credit"))[:300]
            if not board.get("goal") and board.get("_last_verified_goal"):
                board["goal"] = str(board.get("_last_verified_goal", ""))
                board["priority"] = int(board.get("_last_verified_priority", config.PRI_NORMAL) or config.PRI_NORMAL)
            history = board.setdefault("history", [])
            history.append({"denied": latest, "reason": reason, "stage": "fission_judge"})
            _post_failure_candidate(board, latest, reason,
                                    behavior="fission_denial", reason="fission denied")
            llm_meta = review.pop("_llm", None) if isinstance(review.get("_llm"), dict) else None
            deny_data = {
                "completed": latest,
                "verdict": "deny",
                "diagnosis": reason,
                "suggestion": str(review.get("suggestion", "")),
                "rule": str(review.get("rule", "")),
            }
            if llm_meta:
                deny_data.update(llm_meta)
            return {
                "phase": "fission.deny",
                "data": deny_data,
                "writes": {"history": history},
                "next": "reflector",
            }
        fissions = board.get("fissions", 0) + 1
        board["fissions"] = fissions
        board.setdefault("fission_credited", []).append(latest)
        fitness = _evolution_fitness(board, fissions)
        _post_evolution_candidate(board, fissions, latest, fitness, review)
        llm_meta = review.pop("_llm", None) if isinstance(review.get("_llm"), dict) else None
        fission_data = {
            "fissions": fissions,
            "completed": latest,
            "fitness": fitness,
            "diagnosis": str(review.get("diagnosis", "")),
        }
        if llm_meta:
            fission_data.update(llm_meta)
        return {"phase": "fission", "data": fission_data}


class ReflectorAgent:
    """Diagnoses verifier denials and feeds a simpler rule back to planning."""

    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        history = board.get("history", [])
        last_denial = next((h for h in reversed(history)
                            if isinstance(h, dict) and h.get("denied")), {})
        pressure = board.get("_pressure", {})
        failures = int(pressure.get("failures", 0) or 0)
        stagnation = float(pressure.get("stagnation", board.get("stagnation", 0.0)) or 0.0)
        user = _user_with_schema(
            "reflector",
            (
                f"GOAL: {str(board.get('goal', ''))[:400]}\n"
                f"TRIGGER: stagnation={stagnation:.3f} failures={failures} "
                f"human_denials={int(board.get('_human_denials', 0) or 0)}\n"
                f"DENIED_DONE_WHEN: {str(last_denial.get('denied', ''))[:400]}\n"
                f"EVIDENCE: {str(last_denial.get('reason', ''))[:600]}\n"
                "Reflect JSON:"
            ),
        )
        llm_out = call_llm(_stable_system("reflector"), user, "reflector",
                           schema=_load_schema("reflector"), cache_key="reflector")
        try:
            parsed = json.loads(llm_out.text)
        except (json.JSONDecodeError, TypeError):
            writes = {"plan": [], "history": history[-config.MAX_HISTORY:]}
            return {
                "phase": "reflect.error",
                "data": _llm_event_data(llm_out, {
                    "error": "invalid JSON",
                    "failures": failures,
                    "stagnation": round(stagnation, 4),
                }),
                "writes": writes,
                "next": "planner",
            }
        if not isinstance(parsed, dict):
            writes = {"plan": [], "history": history[-config.MAX_HISTORY:]}
            return {
                "phase": "reflect.error",
                "data": _llm_event_data(llm_out, {
                    "error": "not object",
                    "failures": failures,
                    "stagnation": round(stagnation, 4),
                }),
                "writes": writes,
                "next": "planner",
            }
        reflection = {
            "diagnosis": str(parsed.get("diagnosis", "")),
            "suggestion": str(parsed.get("suggestion", "")),
            "rule": str(parsed.get("rule", "")),
        }
        if not reflection["diagnosis"] or not reflection["suggestion"]:
            writes = {"plan": [], "history": history[-config.MAX_HISTORY:]}
            return {
                "phase": "reflect.error",
                "data": _llm_event_data(llm_out, {
                    "error": "missing diagnosis or suggestion",
                    "failures": failures,
                    "stagnation": round(stagnation, 4),
                }),
                "writes": writes,
                "next": "planner",
            }
        writes = {
            "plan": [],
            "history": history[-config.MAX_HISTORY:] + [{"reflection": reflection}],
            "reflection": reflection,
        }
        return {"phase": "reflect", "data": _llm_event_data(llm_out, reflection),
                "writes": writes, "next": "mutator"}


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
        user = _user_with_schema(
            "mutator",
            (
                f"GOAL: {str(board.get('goal', ''))[:400]}\n"
                f"PRESSURE: failures={failures} human_denials={denials}\n"
                f"REFLECTION: {json.dumps(reflection, ensure_ascii=False)[:700]}\n"
                f"EXISTING_PLUGINS: {', '.join(plugin_names) or 'none'}\n"
                f"{_format_history(board.get('history', []))}\n"
                "Mutation JSON:"
            ),
        )
        llm_out = call_llm(_stable_system("mutator"), user, "mutator",
                           schema=_load_schema("mutator"), cache_key="mutator")
        try:
            parsed = json.loads(llm_out.text)
        except (json.JSONDecodeError, TypeError):
            return {
                "phase": "mutate",
                "data": _llm_event_data(llm_out, {"action": "none", "reason": "invalid mutator JSON"}),
                "next": "planner",
            }

        action = str(parsed.get("action", "none"))
        if action != "patch_plugin":
            return {
                "phase": "mutate",
                "data": _llm_event_data(llm_out, {
                    "action": "none",
                    "reason": str(parsed.get("content", "no mutation")),
                }),
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
        event_data = _llm_event_data(llm_out, data)
        if ok:
            _post_mutation_candidate(board, filename, diff, obs)
            return {"phase": "mutate", "data": event_data, "writes": {"mutation": data}, "next": "planner"}
        return {"phase": "mutate", "data": event_data, "next": "planner"}


# --- Helpers ---

def _validate_planner_contract(steps: Any, done_when: Any) -> str:
    if not isinstance(steps, list):
        return "sequence must be a JSON array"
    if len(steps) > 3:
        return "sequence must contain 1-3 Python steps for one measurable outcome"
    if not isinstance(done_when, str) or not done_when.strip():
        return "done_when must describe one measurable outcome"
    done_err = _done_when_contract_error(done_when)
    if done_err:
        return done_err
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            return f"sequence[{index}] must be an object"
        code = step.get("code")
        if not isinstance(code, str):
            return f"sequence[{index}].code must be a string"
        ok, cleaned, err = validate_python(code)
        if not ok:
            return f"sequence[{index}].code invalid Python: {err}"
        code_err = _plan_code_contract_error(cleaned)
        if code_err:
            return f"sequence[{index}].code {code_err}"
        step["code"] = cleaned
    return ""


def _done_when_contract_error(done_when: str) -> str:
    text = done_when.lower()
    bus = any(token in text for token in (
        "bus", "bus_post", "bus_route", "bus_request", "message", "posted", "routed", "assigned",
    ))
    artifact = any(token in text for token in (
        "file", "py_compile", "compile", "git", "commit", "hash", "plugin",
        "patch", "audit", "written", "modified", "created", "wrote",
    ))
    if bus and artifact:
        return "done_when bundles bus coordination with artifact work; use one measurable outcome"
    return ""


def _plan_code_contract_error(code: str) -> str:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        where = f"line {exc.lineno}" if exc.lineno else "step"
        return f"must be runnable Python ({exc.msg}, {where})"

    has_print = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "Path" or alias.name.split(".", 1)[0] == "Path":
                    return "must not import Path; Path is already pre-imported from pathlib"
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".", 1)[0] == "Path":
                return "must not import Path; Path is already pre-imported from pathlib"
            for alias in node.names:
                if alias.name == "Path":
                    return "must not import Path; Path is already pre-imported from pathlib"
        elif isinstance(node, ast.Call):
            root, name = _call_name(node.func)
            if root == "fission_judge" or name == "fission_judge":
                return "must not call fission_judge(); the pipeline runs fission judging after verification"
            if name == "print":
                has_print = True
    if not has_print:
        return "must call print() with verifier evidence"
    return ""


def _human_rephrase_suggestion(reason: str) -> str:
    lowered = reason.lower()
    if "gui" in lowered or "desktop" in lowered or "not supported" in lowered:
        return "Ask for a file-backed task, for example: create hello.txt with hello from colony"
    if "max retries" in lowered:
        return "Ask for one measurable file, audit, or bus task with verifier evidence"
    return "Ask for one measurable file, audit, git, or bus task that fits the planner schema"


def _decline_human_goal(board: dict[str, Any], reason: str) -> None:
    goal = str(board.get("goal", ""))[:120]
    suggestion = _human_rephrase_suggestion(reason)
    try:
        import comms
        comms.post(
            comms.agent_id(), "colony",
            f"@human cannot complete: {reason}. Goal: {goal}. Suggested rephrase: {suggestion}",
            priority=config.PRI_HUMAN,
            human_ack=True,
            blocked_by=reason,
            suggested_rephrase=suggestion,
        )
    except Exception:
        pass
    board["plan"] = []
    board["goal"] = ""
    board["priority"] = config.PRI_MAINTENANCE
    board["_human_denials"] = 0
    log.emit("human.decline", {
        "reason": reason,
        "goal": goal[:80],
        "suggested_rephrase": suggestion,
    })


def _gui_decline_plan(board: dict[str, Any], goal: str) -> dict[str, Any]:
    reason = "GUI/desktop tasks not supported"
    suggestion = _human_rephrase_suggestion(reason)
    log.emit("human.decline", {
        "reason": reason,
        "goal": str(goal)[:80],
        "suggested_rephrase": suggestion,
    })
    code = (
        "bus_post(bus_id(), 'colony', "
        "'@human GUI/desktop tasks not supported — colony has no GUI agent. "
        f"Suggested rephrase: {suggestion}', priority=3, human_ack=True, "
        f"blocked_by='{reason}', suggested_rephrase='{suggestion}')\n"
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


def _bus_config_snapshot() -> dict[str, Path]:
    return {
        "BUS_DIR": config.BUS_DIR,
        "BUS_CHAT_PATH": config.BUS_CHAT_PATH,
        "BUS_EVENTS_PATH": config.BUS_EVENTS_PATH,
        "BUS_INJECT_PATH": config.BUS_INJECT_PATH,
        "BUS_CONTROL_PATH": config.BUS_CONTROL_PATH,
    }


def _restore_bus_config(snapshot: dict[str, Path]) -> None:
    config.BUS_DIR = snapshot["BUS_DIR"]
    config.BUS_CHAT_PATH = snapshot["BUS_CHAT_PATH"]
    config.BUS_EVENTS_PATH = snapshot["BUS_EVENTS_PATH"]
    config.BUS_INJECT_PATH = snapshot["BUS_INJECT_PATH"]
    config.BUS_CONTROL_PATH = snapshot["BUS_CONTROL_PATH"]


def fission_credit_smoke() -> dict[str, Any]:
    """Exercise verifier -> fission -> breeder credit on a durable file milestone."""
    import comms

    runtime_dir = config.BASE_DIR / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    bus_snapshot = _bus_config_snapshot()
    old_call_llm = globals()["call_llm"]
    try:
        with tempfile.TemporaryDirectory(prefix="fission-credit-smoke-", dir=str(runtime_dir)) as tmp:
            smoke_dir = Path(tmp)
            config.BUS_DIR = smoke_dir / "comms"
            config.BUS_CHAT_PATH = config.BUS_DIR / "messages.json"
            config.BUS_EVENTS_PATH = config.BUS_DIR / "events_bus.jsonl"
            config.BUS_INJECT_PATH = config.BUS_DIR / "inject.jsonl"
            config.BUS_CONTROL_PATH = config.BUS_DIR / "control.jsonl"

            proof = smoke_dir / "proof.txt"
            proof.write_text("before\n", encoding="utf-8")
            rel_path = proof.relative_to(config.BASE_DIR).as_posix()
            content = "fission smoke durable milestone\n"

            def fake_call_llm(*_args: Any, **_kwargs: Any) -> LLMResult:
                return LLMResult(text=json.dumps({
                    "verdict": "credit",
                    "diagnosis": "Controlled smoke verified a durable file milestone with external file evidence.",
                    "suggestion": "Credit path is wired; continue with real long-run validation separately.",
                    "rule": "Credit durable file milestones with verifier evidence.",
                }))

            globals()["call_llm"] = fake_call_llm
            board: dict[str, Any] = {
                "goal": f"create {rel_path} with {json.dumps(content)}",
                "plan": [],
                "completed": [],
                "history": [],
                "fissions": 0,
                "priority": config.PRI_NORMAL,
                "power": 0.9,
                "stagnation": 0.1,
                "_pressure": {"stagnation": 0.1, "velocity": 0.0, "failures": 0},
            }

            plan_result = _simple_file_plan(str(board["goal"]))
            if not plan_result:
                return {"ok": False, "stage": "plan", "error": "simple file plan did not match"}
            for key, value in (plan_result.get("writes") or {}).items():
                board[key] = value

            actor_result = ActorAgent().run(board) or {}
            if not (actor_result.get("data") or {}).get("ok"):
                return {"ok": False, "stage": "actor", "actor": actor_result.get("data", {})}

            verify_result = VerifierAgent().run(board) or {}
            if (verify_result.get("data") or {}).get("verdict") != "confirmed":
                return {"ok": False, "stage": "verify", "verify": verify_result.get("data", {})}

            fission_result = FissionJudgeAgent().run(board) or {}
            candidates = comms.evolve_candidates(limit=5)
            ok = (
                fission_result.get("phase") == "fission"
                and int(board.get("fissions", 0) or 0) == 1
                and bool(candidates)
                and candidates[-1].get("payload", {}).get("action") == "retain"
            )
            return {
                "ok": ok,
                "actor": actor_result.get("data", {}),
                "verify": verify_result.get("data", {}),
                "fission": fission_result.get("data", {}),
                "evolve_action": candidates[-1].get("payload", {}).get("action") if candidates else "",
                "evolve_behavior": candidates[-1].get("payload", {}).get("behavior") if candidates else "",
                "proof_path": rel_path,
            }
    finally:
        globals()["call_llm"] = old_call_llm
        _restore_bus_config(bus_snapshot)


def _fission_review(board: dict[str, Any], completed: str) -> dict[str, str]:
    credited = [str(item) for item in board.get("fission_credited", [])]
    if str(completed) in credited:
        return {
            "verdict": "deny",
            "diagnosis": "This milestone repeats an already credited completion and should not receive new fission credit.",
            "suggestion": "Plan a new verifiable milestone or improve pressure before requesting more credit.",
            "rule": "Do not award fission credit for duplicate completed milestones.",
        }
    pressure = board.get("_pressure", {})
    user = _user_with_schema(
        "fission_judge",
        (
            f"GOAL: {str(board.get('_last_verified_goal') or board.get('goal', ''))[:500]}\n"
            f"COMPLETED: {str(completed)[:500]}\n"
            f"VERIFIER_EVIDENCE: {str(board.get('_last_verifier_evidence', ''))[:600]}\n"
            f"PRESSURE: stagnation={float(pressure.get('stagnation', board.get('stagnation', 0.0)) or 0.0):.3f} "
            f"power={float(board.get('power', 0.0) or 0.0):.3f} "
            f"failures={int(pressure.get('failures', 0) or 0)} "
            f"fissions={int(board.get('fissions', 0) or 0)}\n"
            f"{_format_history(board.get('history', []))}\n"
            "Fission judge JSON:"
        ),
    )
    llm_out = call_llm(_stable_system("fission_judge"), user, "fission_judge",
                       schema=_load_schema("fission_judge"), cache_key="fission_judge")
    try:
        parsed = json.loads(llm_out.text)
    except (json.JSONDecodeError, TypeError):
        return {
            "verdict": "deny",
            "diagnosis": "Fission judge did not return valid JSON, so the reactor must not award selection credit.",
            "suggestion": "Retry with a smaller verifiable milestone and require a valid fission judge verdict.",
            "rule": "No fission credit without a valid fission judge JSON verdict.",
            "_llm": _llm_event_data(llm_out, {"judge_error": "invalid_json"}),
        }
    if not isinstance(parsed, dict):
        return {
            "verdict": "deny",
            "diagnosis": "Fission judge output was not a JSON object, so credit is withheld.",
            "suggestion": "Return the required fission judge object before selection can retain this behavior.",
            "rule": "Fission judge output must be a JSON object.",
            "_llm": _llm_event_data(llm_out, {"judge_error": "not_object"}),
        }
    verdict = str(parsed.get("verdict", "deny"))
    if verdict not in {"credit", "deny"}:
        verdict = "deny"
    diagnosis = str(parsed.get("diagnosis", "")).strip()
    suggestion = str(parsed.get("suggestion", "")).strip()
    rule = str(parsed.get("rule", "")).strip()
    if not diagnosis:
        diagnosis = "Fission judge omitted a diagnosis, so the selection reactor cannot justify credit."
        verdict = "deny"
    if not suggestion:
        suggestion = "Return a complete fission judge verdict with evidence-grounded rationale."
        verdict = "deny"
    review = {
        "verdict": verdict,
        "diagnosis": diagnosis,
        "suggestion": suggestion,
        "rule": rule,
    }
    review["_llm"] = _llm_event_data(llm_out)
    return review


def _evolution_fitness(board: dict[str, Any], fissions: int) -> float:
    pressure = board.get("_pressure", {})
    stagnation = float(pressure.get("stagnation", board.get("stagnation", 0.0)) or 0.0)
    power = float(board.get("power", 1.0 - stagnation) or 0.0)
    failures = int(pressure.get("failures", 0) or 0)
    credit = min(0.2, fissions * 0.02)
    score = 0.55 + (power * 0.35) + credit - (stagnation * 0.25) - min(0.2, failures * 0.04)
    return round(max(0.0, min(1.0, score)), 4)


def _pressure_band(board: dict[str, Any]) -> str:
    pressure = board.get("_pressure", {})
    stagnation = float(pressure.get("stagnation", board.get("stagnation", 0.0)) or 0.0)
    if stagnation >= config.STAG_ESCALATE:
        return "high_pressure"
    if stagnation >= 0.3:
        return "mid_pressure"
    return "low_pressure"


def _completion_behavior(completed: str) -> str:
    done = str(completed)
    if done.startswith(_SIMPLE_FILE_DONE_PREFIX):
        return "file_task"
    if "decline" in done.lower():
        return "decline_task"
    if "plugin" in done.lower():
        return "plugin_task"
    return "general_task"


def _behavior_niche(board: dict[str, Any], behavior: str) -> str:
    safe_behavior = re.sub(r"[^a-z0-9_]+", "_", behavior.lower()).strip("_") or "general_task"
    return f"{safe_behavior}:{_pressure_band(board)}"


def _pressure_evolve_fields(board: dict[str, Any], behavior: str) -> dict[str, Any]:
    pressure = board.get("_pressure", {})
    return {
        "behavior": behavior,
        "pressure_band": _pressure_band(board),
        "niche": _behavior_niche(board, behavior),
        "stagnation": round(float(pressure.get("stagnation", board.get("stagnation", 0.0)) or 0.0), 4),
        "power": round(float(board.get("power", 0.0) or 0.0), 4),
        "velocity": round(float(pressure.get("velocity", board.get("velocity", 0.0)) or 0.0), 4),
        "failures": int(pressure.get("failures", 0) or 0),
    }


def _post_evolution_candidate(
    board: dict[str, Any],
    fissions: int,
    completed: str,
    fitness: float,
    review: dict[str, str] | None = None,
) -> None:
    try:
        import comms
        behavior = _completion_behavior(completed)
        data = _pressure_evolve_fields(board, behavior)
        data["fissions"] = fissions
        if review:
            data["judge"] = str(review.get("verdict", ""))[:20]
            data["diagnosis"] = str(review.get("diagnosis", ""))[:200]
            data["suggestion"] = str(review.get("suggestion", ""))[:160]
        comms.post_evolve(
            comms.agent_id(),
            comms.agent_id(),
            "retain",
            fitness=fitness,
            completed=completed,
            reason="fission credit",
            data=data,
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


def _post_failure_candidate(
    board: dict[str, Any],
    done_when: str,
    evidence: str,
    *,
    behavior: str = "verify_denial",
    reason: str = "verify denied",
) -> None:
    try:
        import comms
        data = _pressure_evolve_fields(board, behavior)
        data.update({
            "evidence": str(evidence)[:200],
            "human_denials": int(board.get("_human_denials", 0) or 0),
        })
        comms.post_evolve(
            comms.agent_id(),
            comms.agent_id(),
            "evict",
            fitness=_failure_fitness(board),
            completed=str(done_when),
            reason=reason,
            data=data,
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


def _node_root_name(node: ast.AST) -> str:
    current = node
    while isinstance(current, (ast.Attribute, ast.Subscript)):
        current = current.value
    if isinstance(current, ast.Call):
        return _node_root_name(current.func)
    if isinstance(current, ast.Name):
        return current.id
    return ""


def _call_name(node: ast.AST) -> tuple[str, str]:
    if isinstance(node, ast.Name):
        return node.id, node.id
    if isinstance(node, ast.Attribute):
        root = _node_root_name(node)
        return root, node.attr
    return "", ""


def _literal_str_key(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _plugin_return_is_safe(node: ast.AST | None) -> tuple[bool, str]:
    if node is None or (isinstance(node, ast.Constant) and node.value is None):
        return True, ""
    if not isinstance(node, ast.Dict):
        return False, "plugin returns must be literal None or dict values"
    for key_node, value_node in zip(node.keys, node.values):
        key = _literal_str_key(key_node)
        if not key:
            return False, "plugin return dict keys must be literal strings"
        if key != "writes":
            continue
        if not isinstance(value_node, ast.Dict):
            return False, "plugin writes must be a literal dict"
        for write_key_node in value_node.keys:
            write_key = _literal_str_key(write_key_node)
            if not write_key or not write_key.startswith(_MUTATOR_WRITE_PREFIX):
                return False, "plugin writes may only target _plugin_* state keys"
    return True, ""


def _plugin_mutation_is_safe(source: str) -> tuple[bool, str]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        where = f"line {exc.lineno}" if exc.lineno else "module"
        return False, f"SyntaxError: {exc.msg} ({where})"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root not in _MUTATOR_ALLOWED_IMPORTS:
                    return False, f"unsafe plugin import blocked: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                return False, "relative imports are blocked in plugin mutations"
            module = str(node.module or "").split(".", 1)[0]
            allowed = _MUTATOR_ALLOWED_FROM_IMPORTS.get(module)
            if not allowed:
                return False, f"unsafe plugin import blocked: {node.module or ''}"
            for alias in node.names:
                if alias.name not in allowed:
                    return False, f"unsafe import from {module} blocked: {alias.name}"
        elif isinstance(node, ast.Call):
            root, name = _call_name(node.func)
            if root in _MUTATOR_BLOCKED_ROOTS or name in _MUTATOR_BLOCKED_CALLS or name in _MUTATOR_BLOCKED_ATTRS:
                called = f"{root}.{name}" if root and root != name else name
                return False, f"unsafe plugin call blocked: {called}"
            if root == "board" and name in _MUTATOR_BLOCKED_BOARD_METHODS:
                return False, f"direct board mutation is blocked: board.{name}"
        elif isinstance(node, ast.Attribute):
            root = _node_root_name(node)
            if root in _MUTATOR_BLOCKED_ROOTS or node.attr.startswith("__"):
                return False, f"unsafe plugin attribute blocked: {root}.{node.attr}"
        elif isinstance(node, ast.Name):
            if node.id.startswith("__") or node.id in _MUTATOR_BLOCKED_ROOTS:
                return False, f"unsafe plugin name blocked: {node.id}"
        elif isinstance(node, ast.While):
            return False, "while loops are blocked in plugin mutations"
        elif isinstance(node, (ast.Global, ast.Nonlocal, ast.Delete)):
            return False, f"{type(node).__name__} is blocked in plugin mutations"
        elif isinstance(node, ast.Return):
            ok, err = _plugin_return_is_safe(node.value)
            if not ok:
                return False, err
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = list(getattr(node, "targets", []) or [])
            target = getattr(node, "target", None)
            if target is not None:
                targets.append(target)
            for assignment_target in targets:
                if isinstance(assignment_target, ast.Subscript) and _node_root_name(assignment_target) == "board":
                    return False, "direct board[...] assignment is blocked; return writes instead"
    return True, ""


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
    if path.name in _PROTECTED_PLUGINS:
        return False, f"plugins/{path.name} is protected from mutation", ""

    ok, cleaned, err = validate_python(_strip_code_fence(content))
    if not ok:
        return False, err, ""
    cleaned = cleaned.rstrip() + "\n"
    has_run, run_err = _plugin_defines_run(cleaned)
    if not has_run:
        return False, run_err, ""
    is_safe, safety_err = _plugin_mutation_is_safe(cleaned)
    if not is_safe:
        return False, safety_err, ""
    compiled, compile_err = _py_compile_plugin_source(path.name, cleaned)
    if not compiled:
        return False, compile_err, ""

    try:
        before = path.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"read failed: {exc}", ""
    if before == cleaned:
        return False, "plugin unchanged", ""

    before_ok, _, before_result = _probe_plugin_source(before)
    after_ok, after_obs, after_result = _probe_plugin_source(cleaned)
    if not after_ok:
        return False, f"plugin behavior probe failed before apply: {after_obs}", ""
    if before_ok and _plugin_result_has_telemetry(before_result) and not _plugin_result_has_telemetry(after_result):
        return False, "plugin telemetry regression: existing phase/data telemetry would be removed", ""

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


def _py_compile_plugin_source(filename: str, source: str) -> tuple[bool, str]:
    temp_path = ""
    cfile = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            prefix="endgame_plugin_",
            suffix=f"_{filename}",
            delete=False,
            encoding="utf-8",
        ) as handle:
            temp_path = handle.name
            handle.write(source)
        cfile = f"{temp_path}c"
        py_compile.compile(temp_path, cfile=cfile, doraise=True)
        return True, ""
    except Exception as exc:
        return False, f"py_compile failed before apply: {exc}"
    finally:
        for candidate in (cfile, temp_path):
            if candidate:
                try:
                    Path(candidate).unlink(missing_ok=True)
                except OSError:
                    pass


def _plugin_probe_board() -> dict[str, Any]:
    return {
        "goal": "plugin behavior probe",
        "plan": [],
        "history": [],
        "completed": [],
        "fissions": 1,
        "priority": config.PRI_MAINTENANCE,
        "stagnation": 0.25,
        "power": 0.75,
        "velocity": 0.1,
        "_last_phase": "probe",
        "_pressure": {"stagnation": 0.25, "failures": 0, "cycles": 1},
        "_plugin_fission_log": {"last_fissions": 0},
    }


def _fake_comms_module() -> types.ModuleType:
    module = types.ModuleType("comms")

    def _noop(*args: Any, **kwargs: Any) -> None:
        return None

    module.agent_id = lambda: "plugin_probe"  # type: ignore[attr-defined]
    module.post = _noop  # type: ignore[attr-defined]
    module.post_evolve = _noop  # type: ignore[attr-defined]
    module.post_telemetry = _noop  # type: ignore[attr-defined]
    return module


def _probe_plugin_source(source: str) -> tuple[bool, str, Any]:
    had_comms = "comms" in sys.modules
    previous_comms = sys.modules.get("comms")
    sys.modules["comms"] = _fake_comms_module()
    try:
        namespace: dict[str, Any] = {"__name__": "_endgame_plugin_probe"}
        exec(compile(source, "<plugin-probe>", "exec"), namespace)
        run = namespace.get("run")
        if not callable(run):
            return False, "plugin must define callable run(board)", None
        result = run(_plugin_probe_board())
        if result is not None and not isinstance(result, dict):
            return False, f"run(board) returned {type(result).__name__}, expected dict or None", result
        return True, "probe ok", result
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}", None
    finally:
        if had_comms and previous_comms is not None:
            sys.modules["comms"] = previous_comms
        else:
            sys.modules.pop("comms", None)


def _plugin_result_has_telemetry(result: Any) -> bool:
    return (
        isinstance(result, dict)
        and isinstance(result.get("phase"), str)
        and bool(result.get("phase"))
        and isinstance(result.get("data"), dict)
    )


def _mutation_fitness(board: dict[str, Any]) -> float:
    pressure = board.get("_pressure", {})
    stagnation = float(pressure.get("stagnation", board.get("stagnation", 0.0)) or 0.0)
    failures = int(pressure.get("failures", 0) or 0)
    score = 0.52 - min(0.12, failures * 0.02) - min(0.12, stagnation * 0.12)
    return round(max(0.0, min(0.59, score)), 4)


def _post_mutation_candidate(board: dict[str, Any], filename: str, diff: str, obs: str) -> None:
    try:
        import comms
        path = _resolve_existing_plugin(filename)
        display = f"plugins/{path.name}" if path else str(filename)[:80]
        data = _pressure_evolve_fields(board, "plugin_patch")
        data.update({
            "filename": display,
            "evidence": str(obs)[:200],
            "human_denials": int(board.get("_human_denials", 0) or 0),
        })
        comms.post_evolve(
            comms.agent_id(),
            comms.agent_id(),
            "patch_plugin",
            fitness=_mutation_fitness(board),
            completed=display,
            reason="mutator patch",
            diff=diff,
            data=data,
        )
    except Exception:
        pass


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
            lines.append(f"  {json.dumps(h, ensure_ascii=False)[:400]}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 2 and sys.argv[1] == "--fission-smoke":
        result = fission_credit_smoke()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        sys.exit(0 if result.get("ok") else 1)
    print("usage: python agents.py --fission-smoke")
