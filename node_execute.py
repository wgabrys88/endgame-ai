from __future__ import annotations

import contextlib
import io
import time

import core_bus as bus
import core_desktop as desktop
import core_nodes as nodes
from core_node_base import BaseNode


class ExecuteNode(BaseNode):
    prompt_key = "node_execute"
    expected_record_type = "execution"

    def _should_frame(self, state: dict, conclusion: str) -> bool:
        step = int(state.get("step", 0) or 0)
        return not (
            (state.get("action_frame") and (state.get("action_frame") or {}).get("step_index") == step)
            or state.get("framing_attempted_for_step") == step
        ) and (conclusion in {"CANNOT", "FRAME"} or bool(state.get("last_error")))

    def build_payload(self, ctx):
        state = ctx.get("state", {})
        goal = state.get("effective_goal", ctx.get("goal", ""))
        step = state.get("current_step") or {}
        return {
            "goal": goal,
            "step": {"description": step.get("description", goal), "done_when": step.get("done_when", "")},
            "action_frame": state.get("action_frame"),
            "last": {"error": state.get("last_error"), "failure": state.get("last_failure", {}), "result": state.get("last_result", ""), "action": state.get("last_action", {})},
            "state": bus.state_brief(state),
            "observation": bus.observation_brief(state),
            "capabilities": nodes.capability_manifest(ctx),
        }

    def _failure(self, kind: str, **extra) -> dict:
        return {"source": "execute", "kind": kind, "contract_repair_allowed": False, **extra}

    def run(self, ctx):
        state = ctx.get("state", {})
        payload = self.build_payload(ctx)
        record = self.think(ctx)
        data = record.data
        code = str(data.get("code", "") or "")
        conclusion = str(data.get("conclusion") or "").upper()
        requested = str(data.get("next_signal") or "").lower()
        valid = {"EXECUTE": {"verify"}, "FRAME": {"frame"}, "CANNOT": {"frame", "reflect"}}
        if conclusion not in valid or requested not in valid[conclusion]:
            raise RuntimeError(f"execution invalid conclusion/signal: {conclusion!r}/{requested!r}")
        if conclusion != "EXECUTE" and code.strip():
            raise RuntimeError("execution emitted code when conclusion is not EXECUTE")
        if conclusion != "EXECUTE":
            signal = "frame" if requested == "reflect" and self._should_frame(state, conclusion) else requested
            failure = self._failure("task_route_decision", conclusion=conclusion, reason=f"execute returned {conclusion}")
            return bus.emit(signal, {"last_action": {"code": "", "conclusion": conclusion}, "last_error": failure["reason"], "last_failure": failure}, record=record, evidence=payload)
        if not code.strip():
            raise RuntimeError("execution conclusion EXECUTE requires non-empty code")
        deadline_at = state.get("deadline_at")
        if deadline_at is not None and time.time() >= float(deadline_at):
            late_by = round(time.time() - float(deadline_at), 3)
            failure = self._failure("duration_guard", late_by_s=late_by)
            return bus.emit("reflect", {"last_action": {"code": code, "conclusion": conclusion, "not_executed": True}, "last_code": code, "last_result": {"result": None, "stdout": "", "stderr": "", "action_events": [], "duration_guard": {"deadline_at": float(deadline_at), "late_by_s": late_by}}, "last_error": f"duration deadline expired before executing body action: late_by_s={late_by}", "last_failure": failure, "action_frame": state.get("action_frame")}, record=record, evidence=payload)

        ns = nodes.build_capability_runtime(ctx)
        ns["desktop"] = desktop
        stdout, stderr = io.StringIO(), io.StringIO()
        error = failure = None
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exec(code, ns)
            result = {"result": ns.get("result"), "stdout": stdout.getvalue(), "stderr": stderr.getvalue(), "action_events": list(ns.get("_action_events") or [])}
            if result["result"] is None and not result["action_events"] and not result["stdout"] and not result["stderr"]:
                error = "RuntimeError: EXECUTE produced no result, stdout, stderr, or recorded body action"
                failure = self._failure("empty_execute_result")
        except Exception as exc:
            result = {"stdout": stdout.getvalue(), "stderr": stderr.getvalue(), "action_events": list(ns.get("_action_events") or [])}
            error = f"{type(exc).__name__}: {exc}"
            failure = self._failure("task_route_exception", exception_type=type(exc).__name__, message=str(exc))
        effective_goal = state.get("effective_goal", ctx.get("goal", ""))
        effective_goal += f"\n\n[EXECUTE] Action executed: {code[:120]}... Result: {'success' if not error else 'error: ' + str(error)[:80]}."
        return bus.emit("reflect" if error else "verify", {"last_action": {"code": code, "conclusion": conclusion}, "last_code": code, "last_result": result, "last_error": error, "last_failure": failure, "action_frame": None if not error else state.get("action_frame"), "effective_goal": effective_goal}, record=record, evidence=payload)


def run(ctx):
    return ExecuteNode().run(ctx)
