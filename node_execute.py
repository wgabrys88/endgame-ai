from __future__ import annotations

import contextlib
import io

import core_bus as bus
import core_desktop as desktop
import core_nodes as nodes
from core_nodes import BaseNode


DATASHEET = bus.datasheet(
    "node_execute",
    kind="llm_code_actuator",
    inputs=["goal", "current_step", "fresh_observation", "action_frame", "capability_runtime"],
    signals=["verify", "frame", "reflect", "self_modify", "error"],
    writes=["last_action", "last_code", "last_result", "last_error", "action_frame"],
    record_type="execution",
)


class ExecuteNode(BaseNode):

    prompt_key = "node_execute"
    expected_record_type = "execution"

    def _should_frame(self, state: dict, conclusion: str) -> bool:
        step_index = int(state.get("step", 0) or 0)
        if state.get("action_frame") and (state.get("action_frame") or {}).get("step_index") == step_index:
            return False
        if state.get("framing_attempted_for_step") == step_index:
            return False
        if conclusion in {"CANNOT", "FRAME"}:
            return True
        last_error = str(state.get("last_error") or "")
        return bool(last_error) and state.get("framing_attempted_for_step") != step_index

    def build_payload(self, ctx):
        state = ctx.get("state", {})
        goal = ctx.get("goal", "")
        step = state.get("current_step") or {}
        return {
            "goal": goal,
            "step": {
                "description": step.get("description", goal),
                "done_when": step.get("done_when", ""),
            },
            "action_frame": state.get("action_frame"),
            "last": {
                "error": state.get("last_error"),
                "result": state.get("last_result", ""),
                "action": state.get("last_action", {}),
            },
            "state": bus.state_brief(state),
            "observation": bus.observation_brief(state),
        }

    def run(self, ctx):
        state = ctx.get("state", {})
        payload = self.build_payload(ctx)
        record = self.think(ctx)
        data = record.get("data", {})
        code = str(data.get("code", "") or "")
        conclusion = str(data.get("conclusion", "CANNOT") or "CANNOT").upper()

        if conclusion not in {"EXECUTE", "CANNOT", "FRAME", "SELF_MODIFY"}:
            conclusion = "CANNOT"

        if conclusion == "SELF_MODIFY":
            return bus.emit(
                "self_modify",
                {"last_action": {"code": "", "conclusion": conclusion}, "last_error": "execute requested self modification"},
                record=record,
                evidence=payload,
            )

        if conclusion != "EXECUTE" or not code.strip():
            signal = "frame" if self._should_frame(state, conclusion) else "reflect"
            return bus.emit(
                signal,
                {
                    "last_action": {"code": "", "conclusion": conclusion},
                    "last_error": f"execute returned {conclusion}",
                },
                record=record,
                evidence=payload,
            )

        d = desktop.get_desktop()
        focused_before = d.get_focused_title()
        ns = nodes.build_capability_runtime(ctx)
        ns["desktop"] = desktop
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exec(code, ns)
            explicit_result = ns.get("result")
            focused_after = d.get_focused_title()
            result = {
                "result": explicit_result,
                "stdout": stdout.getvalue(),
                "stderr": stderr.getvalue(),
                "body_delta": {
                    "focused_before": focused_before,
                    "focused_after": focused_after,
                    "focused_changed": focused_before != focused_after,
                },
            }
            error = None
        except Exception as exc:
            result = {"stdout": stdout.getvalue(), "stderr": stderr.getvalue()}
            error = f"{type(exc).__name__}: {exc}"

        signal = "reflect" if error else "verify"
        return bus.emit(
            signal,
            {
                "last_action": {"code": code, "conclusion": conclusion},
                "last_code": code,
                "last_result": result,
                "last_error": error,
                "action_frame": None if not error else state.get("action_frame"),
            },
            record=record,
            evidence=payload,
        )


def run(ctx):
    return ExecuteNode().run(ctx)
