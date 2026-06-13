"""Agents — pipeline stages. Each: run(board) → {phase, data, writes, next}."""
from __future__ import annotations
import json
import os
import time
from typing import Any

import config
import log
from llm import call_llm
from python_code import is_python_code


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
