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
        goal = state.get("effective_goal", ctx.get("goal", ""))
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
                "failure": state.get("last_failure", {}),
                "result": state.get("last_result", ""),
                "action": state.get("last_action", {}),
            },
            "state": bus.state_brief(state),
            "observation": bus.observation_brief(state),
            "capabilities": nodes.capability_manifest(ctx),
        }

    def _decision_failure(self, conclusion: str, reason: str) -> dict:
        return {
            "source": "execute",
            "kind": "task_route_decision",
            "conclusion": conclusion,
            "reason": reason,
            "contract_repair_allowed": False,
        }

    def _runtime_failure(self, exc: Exception) -> dict:
        return {
            "source": "execute",
            "kind": "task_route_exception",
            "exception_type": type(exc).__name__,
            "message": str(exc),
            "contract_repair_allowed": False,
        }

    def run(self, ctx):
        state = ctx.get("state", {})
        payload = self.build_payload(ctx)
        record = self.think(ctx)
        data = record.data
        code = str(data.get("code", "") or "")
        conclusion = str(data.get("conclusion") or "").upper()
        requested_signal = str(data.get("next_signal") or "").lower()

        if conclusion not in {"EXECUTE", "CANNOT", "FRAME"}:
            raise RuntimeError(f"execution emitted invalid conclusion: {conclusion!r}; execute cannot self-modify")
        if requested_signal not in {"verify", "frame", "reflect"}:
            raise RuntimeError(f"execution emitted invalid next_signal: {requested_signal!r}; execute cannot route to self_modify")
        if conclusion == "EXECUTE" and requested_signal != "verify":
            raise RuntimeError(f"execution conclusion EXECUTE requires next_signal verify, got {requested_signal!r}")
        if conclusion == "FRAME" and requested_signal != "frame":
            raise RuntimeError(f"execution conclusion FRAME requires next_signal frame, got {requested_signal!r}")
        if conclusion == "CANNOT" and requested_signal not in {"frame", "reflect"}:
            raise RuntimeError(f"execution conclusion CANNOT requires next_signal frame or reflect, got {requested_signal!r}")
        if conclusion != "EXECUTE" and code.strip():
            raise RuntimeError("execution emitted code when conclusion is not EXECUTE")

        if conclusion != "EXECUTE":
            signal = requested_signal
            if signal == "reflect" and self._should_frame(state, conclusion):
                signal = "frame"
            failure = self._decision_failure(conclusion, f"execute returned {conclusion}")
            return bus.emit(
                signal,
                {
                    "last_action": {"code": "", "conclusion": conclusion},
                    "last_error": failure["reason"],
                    "last_failure": failure,
                },
                record=record,
                evidence=payload,
            )
        if not code.strip():
            raise RuntimeError("execution conclusion EXECUTE requires non-empty code")
        deadline_at = state.get("deadline_at")
        if deadline_at is not None:
            try:
                deadline = float(deadline_at)
            except (TypeError, ValueError) as exc:
                raise RuntimeError(f"invalid deadline_at in state: {deadline_at!r}") from exc
            now = time.time()
            if now >= deadline:
                late_by = round(now - deadline, 3)
                failure = {
                    "source": "execute",
                    "kind": "duration_guard",
                    "late_by_s": late_by,
                    "contract_repair_allowed": False,
                }
                return bus.emit(
                    "reflect",
                    {
                        "last_action": {"code": code, "conclusion": conclusion, "not_executed": True},
                        "last_code": code,
                        "last_result": {
                            "result": None,
                            "stdout": "",
                            "stderr": "",
                            "action_events": [],
                            "duration_guard": {
                                "deadline_at": deadline,
                                "now": now,
                                "late_by_s": late_by,
                            },
                        },
                        "last_error": f"duration deadline expired before executing body action: late_by_s={late_by}",
                        "last_failure": failure,
                        "action_frame": state.get("action_frame"),
                    },
                    record=record,
                    evidence=payload,
                )

        ns = nodes.build_capability_runtime(ctx)
        ns["desktop"] = desktop
        stdout = io.StringIO()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exec(code, ns)
            explicit_result = ns.get("result")
            action_events = list(ns.get("_action_events") or [])
            result = {
                "result": explicit_result,
                "stdout": stdout.getvalue(),
                "stderr": stderr.getvalue(),
                "action_events": action_events,
            }
            if explicit_result is None and not action_events and not result["stdout"] and not result["stderr"]:
                error = "RuntimeError: EXECUTE produced no result, stdout, stderr, or recorded body action"
                failure = {
                    "source": "execute",
                    "kind": "empty_execute_result",
                    "contract_repair_allowed": False,
                }
            else:
                error = None
                failure = None
        except Exception as exc:
            result = {
                "stdout": stdout.getvalue(),
                "stderr": stderr.getvalue(),
                "action_events": list(ns.get("_action_events") or []) if "ns" in locals() else [],
            }
            error = f"{type(exc).__name__}: {exc}"
            failure = self._runtime_failure(exc)

        signal = "reflect" if error else "verify"
        # Rewrite goal for next nodes based on execution outcome
        effective_goal = state.get("effective_goal", ctx.get("goal", ""))
        if conclusion == "EXECUTE":
            effective_goal = f"{effective_goal}\n\n[EXECUTE] Action executed: {code[:120]}... Result: {'success' if not error else 'error: ' + str(error)[:80]}."
        elif conclusion == "FRAME":
            effective_goal = f"{effective_goal}\n\n[EXECUTE] Need sharper observation/frame. Current step: {step.get('description', '')[:100]}."
        elif conclusion == "CANNOT":
            effective_goal = f"{effective_goal}\n\n[EXECUTE] Cannot execute current approach. Need different strategy for: {step.get('description', '')[:100]}."
        return bus.emit(
            signal,
            {
                "last_action": {"code": code, "conclusion": conclusion},
                "last_code": code,
                "last_result": result,
                "last_error": error,
                "last_failure": failure,
                "action_frame": None if not error else state.get("action_frame"),
                "effective_goal": effective_goal,
            },
            record=record,
            evidence=payload,
        )


def run(ctx):
    return ExecuteNode().run(ctx)
