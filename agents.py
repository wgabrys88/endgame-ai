"""Agents â€” pipeline stages. Each: run(board) â†’ {phase, data, writes, next}."""
from __future__ import annotations
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
from llm import LLMResult, call_llm

_ASCII_MAP = str.maketrans({
    "\u2014": "-", "\u2013": "-", "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"', "\u00a0": " ",
})

def validate_python(text: str) -> tuple[bool, str, str]:
    """Syntax check only. Return (ok, cleaned_code, error_message)."""
    cleaned = text.translate(_ASCII_MAP).strip()
    if not cleaned:
        return False, "", "empty code"
    try:
        compile(cleaned, "<step>", "exec")
    except SyntaxError as exc:
        where = f"line {exc.lineno}" if exc.lineno else "step"
        return False, cleaned, f"SyntaxError: {exc.msg} ({where})"
    return True, cleaned, ""

_ELEMENT_ID_RE = re.compile(r"\[\d+\]")
_PLUGIN_NAME_RE = re.compile(r"^[a-z0-9_]+\.py$")
_PLACEHOLDER_USER_PATH_RE = re.compile(r"c:\\+users\\+user\\+", re.IGNORECASE)
_REASONING = (
    "Think in reasoning channel. Final content: one raw JSON object, no markdown fences.\n"
)
_CIRCUIT_HINTS: dict[str, str] = {
    "planner": '{"mode":"direct"|"done","sequence":[{"code":"python with print()"}],"done_when":"measurable outcome"}',
    "verifier": '{"verdict":"confirmed"|"denied","evidence":"what step results prove"}',
    "reflector": '{"diagnosis":"...","suggestion":"...","rule":"..."}',
    "mutator": '{"action":"patch_plugin"|"patch_prompt"|"none","filename":"plugins/existing_name.py","content":"full source or prompt text"}',
    "fission_judge": '{"verdict":"credit"|"deny","diagnosis":"...","suggestion":"...","rule":""}',
    "actor": '{"actions":[{"verb":"click|focus|write|press|hotkey|scroll","target":"[id]","value":""}],"conclusion":"EXECUTE"|"DONE"|"CANNOT"}',
}
def _personality(board: dict[str, Any] | None = None) -> str:
    if board:
        return str(board.get("personality", "")).strip()
    return os.environ.get("ENDGAME_PERSONALITY", "").strip()
def _llm_event_data(result: LLMResult, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "output_chars": len(result.text or ""),
        "reasoning_chars": len(result.reasoning or ""),
        "reasoning_tokens": getattr(result, "reasoning_tokens", 0) or 0,
    }
    if extra:
        data.update(extra)
    return data
def _persona_prompt(persona: str) -> str:
    path = config.PROMPTS_DIR / "personalities" / f"{persona}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""
def _personality_system(board: dict[str, Any] | None = None) -> str:
    name = _personality(board)
    text = _persona_prompt(name)
    if text:
        return text
    return f"You are {name or 'endgame-ai'}, a reactor rod in the colony organism."
def _load_prompt(role: str) -> str:
    path = config.PROMPTS_DIR / f"{role}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""
def _llm_user(circuit: str, body: str) -> str:
    parts: list[str] = [_REASONING]
    hint = _CIRCUIT_HINTS.get(circuit, "")
    if hint:
        parts.append(f"JSON shape (hint, not law): {hint}")
    circuit_text = _load_prompt(circuit)
    if circuit_text:
        parts.append(f"CIRCUIT ({circuit}):\n{circuit_text}")
    parts.append("---TASK_STATE---")
    parts.append(body.strip())
    return "\n".join(parts)
def _strip_code_fence(text: str) -> str:
    cleaned = str(text).strip()
    if not cleaned.startswith("```"):
        return cleaned
    lines = cleaned.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()
def _parse_json(text: str) -> dict[str, Any] | None:
    raw = _strip_code_fence(str(text or "").strip())
    if not raw:
        return None
    for candidate in (raw, raw[raw.find("{"): raw.rfind("}") + 1] if "{" in raw else ""):
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None
def _call_circuit(
    board: dict[str, Any],
    circuit: str,
    body: str,
    *,
    role: str = "",
    cache_key: str = "",
) -> LLMResult:
    return call_llm(
        _personality_system(board),
        _llm_user(circuit, body),
        role or circuit,
        cache_key=cache_key or circuit,
    )
def _format_history(history: list) -> str:
    if not history:
        return ""
    lines = ["RECENT HISTORY:"]
    for h in history[-config.MAX_HISTORY:]:
        if isinstance(h, dict):
            lines.append(f"  {json.dumps(h, ensure_ascii=False)[:400]}")
    return "\n".join(lines)
def _desktop_dir() -> Path:
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    return home / "Desktop"
def _filesystem_context() -> str:
    return "\n".join([
        f"WORKSPACE_DIR: {config.BASE_DIR}",
        f"USER_HOME: {Path(os.environ.get('USERPROFILE') or Path.home())}",
        f"DESKTOP_DIR: {_desktop_dir()}",
        "PATH_RULE: Never use placeholder username paths; use the paths above or ENDGAME_* constants and print resolved path evidence.",
    ])
def _normalized_path_text(text: str) -> str:
    return text.lower().replace("\\\\", "\\")
def _has_placeholder_user_path(text: str) -> bool:
    return bool(_PLACEHOLDER_USER_PATH_RE.search(_normalized_path_text(text)))
def _goal_requires_file_artifact(goal: str) -> bool:
    low = goal.lower()
    return any(term in low for term in ("save file", "saved file", "desktop", "notepad", "write file", "file exists"))
def _has_actual_file_artifact_evidence(text: str) -> bool:
    normalized = _normalized_path_text(text)
    if any(marker in normalized for marker in ("filenotfounderror", "syntaxerror", "traceback", "does not exist")):
        return False
    desktop = _normalized_path_text(str(_desktop_dir()))
    if desktop not in normalized:
        return False
    return any(marker in normalized for marker in (
        "exists=true",
        "exists: true",
        "exists true",
        "readback",
        "content=",
        "contains",
        "length=",
        "size=",
        "bytes=",
    ))
def _fission_evidence_gate(board: dict[str, Any], completed: str) -> str:
    goal = str(board.get("_last_verified_goal") or board.get("goal", ""))
    evidence = str(board.get("_last_verifier_evidence", ""))
    combined = "\n".join([goal, completed, evidence, _format_history(board.get("history", [])[-3:])])
    if _has_placeholder_user_path(combined):
        return "placeholder username path is not valid evidence on this machine"
    if _goal_requires_file_artifact(goal) and not _has_actual_file_artifact_evidence(combined):
        return f"missing actual file evidence under {_desktop_dir()}; print resolved path, exists=True, and readback/content before fission credit"
    return ""
def _desktop_context() -> str:
    try:
        from desktop import observe
        obs = observe()
        parts = [f"DESKTOP_FOCUSED: {obs.focused_title}"]
        if obs.desktop_summary: parts.append(f"DESKTOP_SUMMARY: {obs.desktop_summary[:600]}")
        if obs.context_text: parts.append(obs.context_text[:2000])
        return "\n".join(parts)
    except Exception as exc:
        return f"DESKTOP_ERROR: {exc}"
def _active_claims() -> str:
    try:
        import comms
        claims: dict[str, str] = {}
        for e in comms.read_chat(30):
            kind, payload = str(e.get("kind", "")), e.get("payload") if isinstance(e.get("payload"), dict) else {}
            if kind == comms.KIND_ROUTE and str(e.get("from", "")) == "comms_operator":
                t = str(e.get("to", ""))
                if t: claims[t] = (str(payload.get("goal", "")) or str(e.get("text", "")))[:500]
            elif kind == comms.KIND_EVENT and payload.get("phase") == "plan":
                who = str(e.get("from", ""))
                if who: claims[who] = str(payload.get("done_when", ""))[:500] or claims.get(who, "")
        if not claims: return ""
        return "OTHERS WORKING ON (do not duplicate):\n" + "\n".join(f"  @{w}: {t}" for w, t in claims.items())
    except Exception:
        return ""

def _planner_state(board: dict[str, Any]) -> str:
    persona = _personality(board)
    stag = float(board.get("stagnation", board.get("_pressure", {}).get("stagnation", 0)) or 0)
    goal_text = str(board.get("goal", ""))
    parts = [f"ROD: {persona or 'default'}", f"ACTIVE_TASK: {goal_text[:config.PROMPT_GOAL_TEXT_MAX] or '(idle)'}"]
    try:
        lt = __import__("comms").colony_goal_text()[:config.PROMPT_GOAL_TEXT_MAX]
        if lt: parts.append(f"LONG_TERM_GOAL: {lt}")
    except Exception: pass
    parts.append(f"PRESSURE: stag={stag:.3f} pwr={float(board.get('power', 1.0 - stag) or 0):.3f}")
    parts.append(_filesystem_context())
    claims = _active_claims()
    if claims and persona != "comms_operator": parts.append(claims)
    desktop_ctx = _desktop_context()
    if desktop_ctx: parts.append(desktop_ctx)
    history_ctx = _format_history(board.get("history", []))
    if history_ctx: parts.append(history_ctx)
    try: parts.append(__import__("comms").format_bus_context(10 if persona == "comms_operator" else 6, for_agent=persona))
    except Exception: pass
    parts.append("Plan JSON:")
    return "\n".join(parts)
def _sanitize_plan_step(step: str) -> str:
    if not _ELEMENT_ID_RE.search(step):
        return step
    cleaned = _ELEMENT_ID_RE.sub("", step)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or step
def _normalize_plan_sequence(sequence: Any) -> list[str]:
    if not isinstance(sequence, list):
        return []
    steps: list[str] = []
    for raw in sequence[: config.MAX_PLAN_STEPS]:
        if isinstance(raw, str):
            text = _sanitize_plan_step(raw.strip())
            if text:
                steps.append(text)
        elif isinstance(raw, dict):
            code = str(raw.get("code", "")).strip()
            text = str(raw.get("text", "")).strip()
            if code:
                steps.append(f"exec:\n{code}")
            elif text:
                steps.append(_sanitize_plan_step(text))
    return steps
def _advance_plan(plan: list[dict[str, Any]]) -> None:
    pending = next((s for s in plan if isinstance(s, dict) and s.get("status") == "pending"), None)
    if pending:
        pending["status"] = "active"


def _abort_plan_after_failure(plan: list[dict[str, Any]], reason: str) -> None:
    for step in plan:
        if isinstance(step, dict) and step.get("status") == "pending":
            step["status"] = "skipped_after_failure"
            step["result"] = f"SKIPPED after failed step: {reason[:config.EVIDENCE_TEXT_MAX]}"


def _build_args(verb: str, target: str, value: str) -> dict[str, Any]:
    from actions import DEFAULT_SCROLL_AMOUNT
    target = target.strip("[]")
    if verb == "click":
        return {"selector": target}
    if verb == "write":
        return {"selector": target, "text": value}
    if verb == "press":
        return {"key": target or value}
    if verb == "hotkey":
        raw = value or target
        keys = ["+"] if raw.strip() == "+" else [k.strip() for k in raw.replace("+", ",").split(",") if k.strip()]
        return {"keys": keys}
    if verb == "scroll":
        try:
            return {"selector": target, "amount": int(value) if value else DEFAULT_SCROLL_AMOUNT}
        except ValueError:
            return {"selector": target, "amount": DEFAULT_SCROLL_AMOUNT}
    if verb == "focus":
        return {"window_title": target or value}
    return {}
def _render_actor_context(board: dict[str, Any], instruction: str) -> str:
    parts: list[str] = [f"GOAL: {board.get('goal', '')}"]
    screen = str(board.get("screen", "")).strip()
    if screen:
        parts.append(f"SCREEN:\n{screen}")
    plan = board.get("plan", [])
    if plan:
        lines = ["PLAN:"]
        for step in plan:
            if isinstance(step, dict):
                lines.append(f"  - {step.get('status', '?')}: {step.get('text', '')}")
        parts.append("\n".join(lines))
    parts.append(f"INSTRUCTION: {instruction}")
    return "\n\n".join(parts)
def _plan_steps(sequence: list[str]) -> list[dict[str, Any]]:
    return [
        {"text": text, "status": "active" if i == 0 else "pending"}
        for i, text in enumerate(sequence)
    ]
def _restore_after_human_task(board: dict[str, Any]) -> None:
    board["priority"] = config.PRI_MAINTENANCE
    board["goal"] = ""
    board["plan"] = []
    board["_human_denials"] = 0
def _verify_outcome(
    board: dict[str, Any],
    done_when: str,
    ok: bool,
    evidence: str,
    *,
    llm_out: LLMResult | None = None,
) -> dict[str, Any]:
    if ok:
        board["plan"] = []
        board.setdefault("completed", []).append(done_when)
        board["_last_verified_goal"] = str(board.get("goal", ""))[:config.PROMPT_GOAL_TEXT_MAX]
        board["_last_verified_priority"] = board.get("priority", config.PRI_MAINTENANCE)
        board["_last_verifier_evidence"] = evidence[:config.EVIDENCE_TEXT_MAX]
        if board.get("priority", config.PRI_MAINTENANCE) >= config.PRI_HUMAN:
            _restore_after_human_task(board)
        data: dict[str, Any] = {"verdict": "confirmed", "evidence": evidence}
        if llm_out is not None:
            data = _llm_event_data(llm_out, data)
        return {"phase": "verify", "data": data, "next": "fission_judge"}
    board["plan"] = []
    board.setdefault("history", []).append({"denied": done_when, "reason": evidence})
    _post_failure_candidate(board, done_when, evidence)
    data = {"verdict": "denied", "evidence": evidence}
    if llm_out is not None:
        data = _llm_event_data(llm_out, data)
    return {"phase": "verify", "data": data, "next": "reflector"}
class ObserverAgent:
    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        from desktop import observe
        try:
            obs = observe()
        except Exception as exc:
            return {"phase": "observe", "data": {"error": str(exc)[:200]}}
        return {
            "phase": "observe",
            "data": {"focused": obs.focused_title, "chars": len(obs.context_text)},
            "writes": {
                "screen": obs.context_text,
                "screen_elements": obs.book,
                "focused_window": obs.focused_title,
                "desktop_summary": obs.desktop_summary,
            },
        }
class SchedulerAgent:
    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        # comms_operator only plans on human interrupt
        if _personality(board) == "comms_operator":
            if board.get("priority", config.PRI_MAINTENANCE) < config.PRI_HUMAN and not board.get("plan"):
                return None
        plan = board.get("plan", [])
        if not plan:
            # Workers always self-direct: use goal or personality mission
            if not board.get("goal"):
                persona = _personality(board) or "worker"
                board["goal"] = f"Self-directed {persona} maintenance: audit, improve, report"
            return {"next": "planner", "data": {"reason": "need_plan"}}
        active = [s for s in plan if isinstance(s, dict) and s.get("status") == "active"]
        if active:
            return {"next": "actor", "data": {"reason": "has_active_step"}}
        pending = [s for s in plan if isinstance(s, dict) and s.get("status") == "pending"]
        if pending:
            pending[0]["status"] = "active"
            return {"next": "actor", "data": {"reason": "next_step"}}
        return {"next": "verifier", "data": {"reason": "plan_complete"}}
class PlannerAgent:
    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        goal = board.get("goal", "")
        if not goal:
            return None
        log.emit("planner.pending", {"goal": goal[:config.GOAL_TEXT_MAX]})
        llm_out = _call_circuit(board, "planner", _planner_state(board), role="planner")
        parsed = _parse_json(llm_out.text)
        if not parsed:
            return {"phase": "planner.error", "data": _llm_event_data(llm_out, {
                "error": "invalid JSON",
                "raw": str(llm_out.text)[:config.PLANNER_ERROR_RAW_MAX],
            })}
        mode = str(parsed.get("mode", "direct"))
        if mode == "done":
            return {"phase": "plan", "data": _llm_event_data(llm_out, {
                "mode": "done", "done_when": parsed.get("done_when", ""),
            }), "writes": {"plan": []}}
        sequence = _normalize_plan_sequence(parsed.get("sequence", []))
        if not sequence:
            return {"phase": "planner.error", "data": _llm_event_data(llm_out, {"error": "empty sequence"})}
        done_when = str(parsed.get("done_when", "")).strip() or goal[:1000]
        steps = _plan_steps(sequence)
        writes: dict[str, Any] = {"plan": steps, "done_when": done_when}
        if _personality(board) == "comms_operator":
            writes["_last_route"] = time.time()
        return {
            "phase": "plan", "next": "actor",
            "data": _llm_event_data(llm_out, {"mode": mode, "steps": len(steps), "done_when": done_when}),
            "writes": writes,
        }
class ActorAgent:
    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        from actions import execute_step, execute_verb, is_python_step, VERBS

        plan = board.get("plan", [])
        active = next((s for s in plan if isinstance(s, dict) and s.get("status") == "active"), None)
        if not active:
            return None
        text = str(active.get("text", "")).strip()
        if not text:
            return {"phase": "actor.error", "data": {"error": "no active step text"}}
        history: list[dict[str, Any]] = list(board.get("history", []))

        if is_python_step(text):
            result = execute_step(text)
            history.append({"verb": result.verb, "ok": result.success, "obs": result.observation})
            active["result"] = result.observation[:config.EXEC_OUTPUT_LIMIT]
            if result.success:
                active["status"] = "done"
                _advance_plan(plan)
                plan_done = all(not isinstance(s, dict) or s.get("status") == "done" for s in plan)
                return {
                    "phase": "actor",
                    "data": {"ok": True, "verb": result.verb, "obs": result.observation[:200]},
                    "next": "verifier" if plan_done else "actor",
                    "writes": {"plan": plan, "history": history[-config.MAX_HISTORY:]},
                }
            active["status"] = "failed"
            _abort_plan_after_failure(plan, result.observation)
            return {
                "phase": "actor",
                "data": {"ok": False, "verb": result.verb, "obs": result.observation[:200]},
                "next": "verifier",
                "writes": {"plan": plan, "history": history[-config.MAX_HISTORY:]},
            }

        llm_out = _call_circuit(board, "actor", _render_actor_context(board, text), role="actor")
        parsed = _parse_json(llm_out.text)
        if not parsed:
            return {"phase": "actor.error", "data": _llm_event_data(llm_out, {"error": "invalid JSON"})}
        conclusion = str(parsed.get("conclusion", "EXECUTE"))
        actions: list[dict[str, Any]] = parsed.get("actions", []) if isinstance(parsed.get("actions"), list) else []
        actions = [a for a in actions if str(a.get("verb", "")) in VERBS]
        plan_done = lambda: all(not isinstance(s, dict) or s.get("status") == "done" for s in plan)

        if conclusion == "DONE":
            active["status"] = "done"
            _advance_plan(plan)
            return {
                "phase": "actor",
                "data": _llm_event_data(llm_out, {"conclusion": "DONE"}),
                "next": "verifier" if plan_done() else "actor",
                "writes": {"plan": plan},
            }
        if conclusion == "CANNOT" or (conclusion == "EXECUTE" and not actions):
            active["status"] = "failed"
            return {"phase": "actor", "data": _llm_event_data(llm_out, {"conclusion": conclusion, "ok": False})}

        elements: dict[str, Any] = board.get("screen_elements", {})
        had_failure = False
        for action in actions:
            verb = str(action.get("verb", ""))
            result = execute_verb(
                verb,
                _build_args(verb, str(action.get("target", "")), str(action.get("value", ""))),
                elements,
                None,
            )
            history.append({"verb": verb, "ok": result.success, "obs": result.observation})
            if not result.success:
                had_failure = True
                active["result"] = result.observation[:config.EXEC_OUTPUT_LIMIT]
                break
        if had_failure:
            active["status"] = "failed"
            _abort_plan_after_failure(plan, str(active.get("result", "")))
            return {
                "phase": "actor",
                "data": _llm_event_data(llm_out, {"conclusion": conclusion, "ok": False}),
                "next": "verifier",
                "writes": {"plan": plan, "history": history[-config.MAX_HISTORY:]},
            }
        active["status"] = "done"
        active["result"] = f"gui:{conclusion}"
        _advance_plan(plan)
        return {
            "phase": "actor",
            "data": _llm_event_data(llm_out, {"conclusion": conclusion, "ok": True}),
            "next": "verifier" if plan_done() else "actor",
            "writes": {"plan": plan, "history": history[-config.MAX_HISTORY:]},
        }
class VerifierAgent:
    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        done_when = board.get("done_when", "")
        if not done_when:
            return {"phase": "verify", "data": {"verdict": "confirmed", "evidence": "no done_when set"}}
        plan = board.get("plan", [])
        results = [str(s.get("result", ""))[:config.EVIDENCE_TEXT_MAX] for s in plan if isinstance(s, dict)]
        llm_out = _call_circuit(
            board,
            "verifier",
            f"DONE_WHEN: {done_when}\n\nSTEP RESULTS:\n" + "\n".join(results),
            role="verifier",
        )
        parsed = _parse_json(llm_out.text)
        if not parsed:
            return _verify_outcome(board, done_when, False, "verifier returned invalid JSON", llm_out=llm_out)
        verdict = str(parsed.get("verdict", "denied")).lower()
        evidence = str(parsed.get("evidence", ""))[:config.EVIDENCE_TEXT_MAX] or str(llm_out.text)[:config.EVIDENCE_TEXT_MAX]
        return _verify_outcome(board, done_when, verdict == "confirmed", evidence, llm_out=llm_out)
class FissionJudgeAgent:
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
            _post_failure_candidate(board, latest, reason, behavior="fission_denial", reason="fission denied")
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
            return {"phase": "fission.deny", "data": deny_data, "writes": {"history": history}, "next": "reflector"}
        fissions = board.get("fissions", 0) + 1
        board["fissions"] = fissions
        board.setdefault("fission_credited", []).append(latest)
        fitness = _fitness(board, fissions)
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
    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        history = board.get("history", [])
        last_denial = next((h for h in reversed(history) if isinstance(h, dict) and h.get("denied")), {})
        pressure = board.get("_pressure", {})
        llm_out = _call_circuit(
            board,
            "reflector",
            (
                f"GOAL: {str(board.get('goal', ''))[:config.PROMPT_GOAL_TEXT_MAX]}\n"
                f"PRESSURE: failures={int(pressure.get('failures', 0) or 0)} "
                f"stag={float(pressure.get('stagnation', 0) or 0):.3f}\n"
                f"DENIED: {str(last_denial.get('denied', ''))[:config.EVIDENCE_TEXT_MAX]}\n"
                f"EVIDENCE: {str(last_denial.get('reason', ''))[:config.EVIDENCE_TEXT_MAX]}\n"
                "Reflect JSON:"
            ),
            role="reflector",
        )
        parsed = _parse_json(llm_out.text) or {}
        reflection = {
            "diagnosis": str(parsed.get("diagnosis", last_denial.get("reason", "verify denied")))[:config.EVIDENCE_TEXT_MAX],
            "suggestion": str(parsed.get("suggestion", "simplify next plan"))[:config.EVIDENCE_TEXT_MAX],
            "rule": str(parsed.get("rule", ""))[:200],
        }
        writes = {"plan": [], "history": history[-config.MAX_HISTORY:] + [{"reflection": reflection}], "reflection": reflection}
        return {"phase": "reflect", "data": _llm_event_data(llm_out, reflection), "writes": writes, "next": "mutator"}
class MutatorAgent:
    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        pressure = board.get("_pressure", {})
        failures = int(pressure.get("failures", 0) or 0)
        denials = int(board.get("_human_denials", 0) or 0)
        reflection = board.get("reflection")
        if max(failures, denials) < config.MUTATE_AFTER_FAILURES or not isinstance(reflection, dict):
            return {
                "phase": "mutate",
                "data": {"action": "none", "reason": "waiting for failure pressure", "failures": failures},
                "next": "planner",
            }
        plugin_names = _existing_plugin_names()
        elite_dna = _get_elite_dna_context(_personality(board))
        llm_out = _call_circuit(
            board,
            "mutator",
            (
                f"GOAL: {str(board.get('goal', ''))[:config.PROMPT_GOAL_TEXT_MAX]}\n"
                f"REFLECTION: {json.dumps(reflection, ensure_ascii=False)[:config.EVIDENCE_TEXT_MAX]}\n"
                f"PLUGINS: {', '.join(plugin_names) or 'none'}\n"
                f"{elite_dna}"
                f"{_format_history(board.get('history', []))}\n"
                "Mutation JSON:"
            ),
            role="mutator",
        )
        parsed = _parse_json(llm_out.text) or {}
        action = str(parsed.get("action", "none"))
        if action == "patch_prompt":
            if not config.ALLOW_PERSONALITY_PATCH_PROMPT:
                return {
                    "phase": "mutate",
                    "data": _llm_event_data(llm_out, {
                        "action": "none",
                        "reason": "patch_prompt disabled during Phase 0 measurement",
                    }),
                    "next": "planner",
                }
            ok, obs = _apply_prompt_mutation(board, str(parsed.get("content", "")))
            data: dict[str, Any] = {"action": "patch_prompt", "ok": ok, "obs": obs}
            event_data = _llm_event_data(llm_out, data)
            if ok:
                _post_mutation_candidate(board, f"prompts/personalities/{_personality(board)}.txt", obs, obs)
            return {"phase": "mutate", "data": event_data, "next": "planner"}
        if action != "patch_plugin":
            return {
                "phase": "mutate",
                "data": _llm_event_data(llm_out, {"action": "none", "reason": str(parsed.get("content", "no mutation"))[:200]}),
                "next": "planner",
            }
        filename = str(parsed.get("filename", ""))
        ok, obs, diff = _apply_plugin_mutation(filename, str(parsed.get("content", "")))
        data = {"action": "patch_plugin", "filename": filename[:80], "ok": ok, "obs": obs}
        if diff:
            data["diff"] = diff[:500]
        event_data = _llm_event_data(llm_out, data)
        if ok:
            _post_mutation_candidate(board, filename, diff, obs)
            return {"phase": "mutate", "data": event_data, "writes": {"mutation": data}, "next": "planner"}
        return {"phase": "mutate", "data": event_data, "next": "planner"}
def _parse_fission_judge_payload(llm_out: LLMResult) -> dict[str, str] | None:
    parsed = _parse_json(llm_out.text)
    if not parsed:
        return None
    verdict = str(parsed.get("verdict", "deny"))
    if verdict not in {"credit", "deny"}:
        verdict = "deny"
    diagnosis = str(parsed.get("diagnosis", "")).strip() or str(llm_out.text)[:300]
    suggestion = str(parsed.get("suggestion", "")).strip() or "continue toward goal"
    return {
        "verdict": verdict,
        "diagnosis": diagnosis,
        "suggestion": suggestion,
        "rule": str(parsed.get("rule", "")).strip(),
    }
def _fission_review(board: dict[str, Any], completed: str) -> dict[str, str]:
    credited = [str(item) for item in board.get("fission_credited", [])]
    if str(completed) in credited:
        return {
            "verdict": "deny",
            "diagnosis": "duplicate credited milestone",
            "suggestion": "plan a new verifiable step",
            "rule": "",
        }
    gate = _fission_evidence_gate(board, completed)
    if gate:
        return {
            "verdict": "deny",
            "diagnosis": gate,
            "suggestion": "produce external evidence from the actual Desktop path, then verify again",
            "rule": "fission requires real path/readback evidence for file/Desktop tasks",
        }
    pressure = board.get("_pressure", {})
    llm_out = _call_circuit(
        board,
        "fission_judge",
        (
            f"GOAL: {str(board.get('_last_verified_goal') or board.get('goal', ''))[:config.PROMPT_GOAL_TEXT_MAX]}\n"
            f"COMPLETED: {completed[:config.EVIDENCE_TEXT_MAX]}\n"
            f"EVIDENCE: {str(board.get('_last_verifier_evidence', ''))[:config.EVIDENCE_TEXT_MAX]}\n"
            f"PRESSURE: stag={float(pressure.get('stagnation', 0) or 0):.3f} "
            f"fissions={int(board.get('fissions', 0) or 0)}\n"
            f"{_format_history(board.get('history', [])[-3:])}\n"
            "Fission judge JSON:"
        ),
        role="fission_judge",
        cache_key="fission_judge",
    )
    review = _parse_fission_judge_payload(llm_out)
    if review:
        review["_llm"] = _llm_event_data(llm_out)
        return review
    return {
        "verdict": "deny",
        "diagnosis": str(llm_out.text)[:300] or "invalid judge JSON",
        "suggestion": "retry with clearer milestone",
        "rule": "",
        "_llm": _llm_event_data(llm_out, {"judge_error": "invalid_json"}),
    }

def _fitness(board: dict[str, Any], fissions: int) -> float:
    """MAP-Elites fitness: power + fission bonus - stagnation penalty."""
    stag = float(board.get("_pressure", {}).get("stagnation", 0) or 0)
    power = float(board.get("power", 1.0 - stag) or 0)
    return round(max(0.0, min(1.0, 0.55 + power * 0.35 + min(0.2, fissions * 0.02) - stag * 0.25)), 4)
def _niche(board: dict[str, Any], behavior: str) -> str:
    stag = float(board.get("_pressure", {}).get("stagnation", 0) or 0)
    band = "high" if stag >= config.STAG_ESCALATE else "mid" if stag >= 0.3 else "low"
    safe = re.sub(r"[^a-z0-9_]+", "_", behavior.lower()).strip("_") or "general"
    return f"{safe}:{band}"
def _post_evolution_candidate(board: dict[str, Any], fissions: int, completed: str, fitness: float, review: dict[str, str] | None = None) -> None:
    try:
        import comms
        comms.post_evolve(comms.agent_id(), comms.agent_id(), "retain", fitness=fitness,
                          completed=completed, reason="fission credit",
                          data={"niche": _niche(board, "general_task"), "fissions": fissions})
    except Exception:
        pass
def _post_failure_candidate(board: dict[str, Any], done_when: str, evidence: str, **_kw: Any) -> None:
    try:
        import comms
        stag = float(board.get("_pressure", {}).get("stagnation", 0) or 0)
        fit = round(max(0.0, 0.35 - stag * 0.25), 4)
        comms.post_evolve(comms.agent_id(), comms.agent_id(), "evict", fitness=fit,
                          completed=str(done_when), reason="verify denied",
                          data={"niche": _niche(board, "denial"), "evidence": str(evidence)[:200]})
    except Exception:
        pass
def _get_elite_dna_context(persona: str) -> str:
    """Pull best prompt DNA from breed archive for crossover context."""
    try:
        import json as _json
        archive_path = config.PROMPTS_DIR.parent / "runtime" / "breed_archive.json"
        if not archive_path.exists():
            return ""
        data = _json.loads(archive_path.read_text(encoding="utf-8"))
        archive = data.get("archive", {}) if isinstance(data, dict) else {}
        best_dna, best_fit = "", 0.0
        for elite in archive.values():
            if not isinstance(elite, dict):
                continue
            fit = float(elite.get("fitness", 0) or 0)
            dna = str(elite.get("prompt_dna", "")).strip()
            if dna and fit > best_fit and elite.get("target") != persona:
                best_dna, best_fit = dna, fit
        if best_dna:
            return f"ELITE_DNA (fitness={best_fit:.2f}, use for crossover):\n{best_dna[:800]}\n"
    except Exception:
        pass
    return ""


def _apply_prompt_mutation(board: dict[str, Any], new_prompt: str) -> tuple[bool, str]:
    """Mutate the current persona's prompt file with new DNA."""
    persona = _personality(board)
    if not persona:
        return False, "no persona"
    cleaned = new_prompt.strip()
    if len(cleaned) < 20:
        return False, "prompt too short"
    if len(cleaned) > 2000:
        cleaned = cleaned[:2000]
    pfile = config.PROMPTS_DIR / "personalities" / f"{persona}.txt"
    try:
        before = pfile.read_text(encoding="utf-8").strip() if pfile.exists() else ""
    except OSError:
        return False, "read failed"
    if before == cleaned:
        return False, "unchanged"
    pfile.write_text(cleaned, encoding="utf-8")
    return True, f"patched {persona}.txt ({len(cleaned)} chars)"


def _existing_plugin_names() -> list[str]:
    try:
        deny = set(config.PHASE0_PLUGIN_MUTATION_DENYLIST)
        return [p.name for p in sorted(config.PLUGINS_DIR.glob("*.py")) if p.is_file() and p.name not in deny]
    except OSError:
        return []


def _resolve_existing_plugin(filename: str) -> Path | None:
    raw = str(filename).strip().replace("\\", "/")
    if raw.startswith("plugins/"):
        raw = raw[len("plugins/"):]
    if "/" in raw or not _PLUGIN_NAME_RE.fullmatch(raw):
        return None
    if raw in config.PHASE0_PLUGIN_MUTATION_DENYLIST:
        return None
    path = (config.PLUGINS_DIR / raw).resolve()
    try:
        path.relative_to(config.PLUGINS_DIR.resolve())
    except ValueError:
        return None
    return path if path.is_file() else None
def _apply_plugin_mutation(filename: str, content: str) -> tuple[bool, str, str]:
    path = _resolve_existing_plugin(filename)
    if path is None:
        return False, "mutable existing plugins/[name].py required", ""
    ok, cleaned, err = validate_python(_strip_code_fence(content))
    if not ok:
        return False, err, ""
    cleaned = cleaned.rstrip() + "\n"
    if "def run(" not in cleaned:
        return False, "plugin must define def run(board)", ""
    try:
        before = path.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"read failed: {exc}", ""
    if before == cleaned:
        return False, "plugin unchanged", ""
    diff = "\n".join(list(difflib.unified_diff(
        before.splitlines(), cleaned.splitlines(),
        fromfile=f"a/{path.name}", tofile=f"b/{path.name}", lineterm="", n=2))[:40])
    try:
        path.write_text(cleaned, encoding="utf-8")
        py_compile.compile(str(path), doraise=True)
        # Trial exec in isolated namespace to catch import/name errors
        exec(compile(cleaned, str(path), "exec"), {"__builtins__": __builtins__})
    except Exception as exc:
        try:
            path.write_text(before, encoding="utf-8")
        except OSError:
            pass
        return False, f"apply failed: {exc}", ""
    return True, f"patched plugins/{path.name}", diff
def _post_mutation_candidate(board: dict[str, Any], filename: str, diff: str, obs: str) -> None:
    try:
        import comms
        fit = round(max(0.0, min(0.6, 0.52 - float(board.get("_pressure", {}).get("stagnation", 0) or 0) * 0.12)), 4)
        comms.post_evolve(comms.agent_id(), comms.agent_id(), "patch_plugin",
                          fitness=fit, completed=str(filename)[:80], reason="mutator patch",
                          diff=diff, data={"niche": _niche(board, "plugin_patch")})
    except Exception:
        pass
