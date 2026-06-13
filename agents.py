"""Agents — pipeline stages. Each: run(board) → {phase, data, writes, next}."""
from __future__ import annotations
import json
from typing import Any

import config
import log
from llm import call_llm
from python_code import is_python_code


class SchedulerAgent:
    """Decides what to do next: plan, continue, or idle."""

    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        plan = board.get("plan", [])
        if not plan:
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
        log.emit("planner.pending", {"goal": goal[:80]})
        system = _load_prompt("planner")
        history_ctx = _format_history(board.get("history", []))
        bus_ctx = ""
        try:
            import comms
            bus_ctx = comms.format_bus_context(6)
        except Exception:
            pass
        user = f"GOAL: {goal}\n\n{history_ctx}\n{bus_ctx}\n\nPlan JSON:"
        schema = _load_schema("planner")
        raw = call_llm(system, user, "planner", schema=schema)
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {"phase": "planner.error", "data": {"error": "invalid JSON", "raw": str(raw)[:200]}}
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
        return {
            "phase": "plan", "next": "actor",
            "data": {"mode": mode, "steps": len(steps), "done_when": done_when},
            "writes": {"plan": steps, "done_when": done_when},
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
        active["result"] = result.output[:config.EXEC_OUTPUT_LIMIT]
        ok = result.ok
        obs = result.output[:200]
        if not ok:
            board.setdefault("history", []).append({"step": code[:100], "ok": False, "obs": obs})
        return {"phase": "actor", "data": {"ok": ok, "obs": obs}, "next": "verifier" if ok else None}


class VerifierAgent:
    """Verifies plan completion."""

    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        done_when = board.get("done_when", "")
        if not done_when:
            return {"phase": "verify", "data": {"verdict": "confirmed", "evidence": "no done_when set"}}
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
            return {"phase": "verify", "data": {"verdict": "confirmed", "evidence": parsed.get("evidence", "")},
                    "next": "fission_judge"}
        # Denied — clear plan, will replan
        board["plan"] = []
        board.setdefault("history", []).append({"denied": done_when, "reason": parsed.get("evidence", "")})
        return {"phase": "verify", "data": {"verdict": "denied", "evidence": parsed.get("evidence", "")}}


class FissionJudgeAgent:
    """Awards fission credit for confirmed work."""

    def run(self, board: dict[str, Any]) -> dict[str, Any] | None:
        completed = board.get("completed", [])
        if not completed:
            return None
        fissions = board.get("fissions", 0) + 1
        board["fissions"] = fissions
        return {"phase": "fission", "data": {"fissions": fissions, "completed": completed[-1]}}


# --- Helpers ---

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
