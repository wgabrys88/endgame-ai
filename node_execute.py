import contextlib
import hashlib
import io
import time

import core_bus as bus
import core_nodes as nodes
from core_node_base import BaseNode


class ExecuteNode(BaseNode):
    prompt_key = "node_execute"
    expected_record_type = "execution"

    def build_payload(self, ctx):
        state = ctx["state"]
        step = state.get("current_step") or {}
        return {
            "faculty": ctx["node_instance"],
            "goal": state["goal"],
            "step": {"description": step.get("description", state["goal"]), "done_when": step.get("done_when", "")},
            "action_frame": state.get("action_frame"),
            "focus": bus.state_brief(state),
            "observation": bus.observation_brief(state),
            "capabilities": nodes.capability_manifest(ctx),
        }

    def _failure(self, kind: str, **extra) -> dict:
        return {"source": "execute", "kind": kind, "contract_repair_allowed": False, **extra}

    @staticmethod
    def _turn_entry(code, result, error, failure):
        return {
            "code_sha256": hashlib.sha256(code.encode("utf-8", errors="replace")).hexdigest(),
            "code_chars": len(code),
            "result": result,
            "error": error,
            "failure": failure,
        }

    @staticmethod
    def _repair_probe(state, instance):
        repair = state.get("repair_validation") or {}
        if repair.get("status") != "probing":
            return None
        probe = repair["probe"]
        return probe if probe["faculty"] == instance else None

    def run(self, ctx):
        state = ctx["state"]
        instance = ctx["node_instance"]
        targets = state.get("_dispatch_targets") or []
        if f"node_execute:{instance}" not in targets:
            return bus.emit("done")

        payload = self.build_payload(ctx)
        probe = self._repair_probe(state, instance)
        if probe is None:
            record = self.think(ctx)
            code = record.data["code"]
            label = f"EXECUTE:{instance}"
        else:
            code = probe["code"]
            record = bus.Record.create(
                "execution",
                {"code": code},
                reasoning=(
                    f"Behavioral repair probe {state['repair_validation']['repair_id']} retries "
                    f"failure {probe['failure_signature']} through the original {instance} faculty."
                ),
            )
            payload["repair_probe"] = {
                "repair_id": state["repair_validation"]["repair_id"],
                "failure_signature": probe["failure_signature"],
                "comparison_basis": probe["comparison_basis"],
            }
            label = f"REPAIR_EXECUTE:{instance}"

        deadline_at = state.get("deadline_at")
        if deadline_at is not None and time.time() >= float(deadline_at):
            late_by = round(time.time() - float(deadline_at), 3)
            error = f"duration deadline expired before executing body action: late_by_s={late_by}"
            failure = self._failure("duration_guard", late_by_s=late_by)
            result = {
                "result": None,
                "stdout": "",
                "stderr": "",
                "action_events": [],
                "duration_guard": {"deadline_at": float(deadline_at), "late_by_s": late_by},
            }
            turn = dict(state.get("turn_executions") or {})
            turn[instance] = self._turn_entry(code, result, error, failure)
            effective = state["effective_goal"] + f"\n\n[{label}] No action: {error}."
            return bus.emit(
                "done",
                {
                    "turn_executions": turn,
                    "last_action": {"code": code, "faculty": instance, "not_executed": True},
                    "last_code": code,
                    "last_result": result,
                    "last_error": error,
                    "last_failure": failure,
                    "effective_goal": effective,
                },
                record=record,
                evidence=payload,
            )

        import core_desktop as desktop

        ns = nodes.build_capability_runtime(ctx)
        ns["desktop"] = desktop
        stdout, stderr = io.StringIO(), io.StringIO()
        error = failure = None
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exec(code, ns)
            result = {
                "result": ns.get("result"),
                "stdout": stdout.getvalue(),
                "stderr": stderr.getvalue(),
                "action_events": list(ns["_action_events"]),
            }
            policy = ctx["wiring"]["capabilities"]["faculties"][instance]
            if policy["requires_action_event"] and not result["action_events"]:
                error = f"RuntimeError: {instance} faculty produced no recorded capability action"
                failure = self._failure("faculty_evidence_missing", faculty=instance)
            elif result["result"] is None and not result["action_events"] and not result["stdout"] and not result["stderr"]:
                error = "RuntimeError: EXECUTE produced no result, stdout, stderr, or recorded body action"
                failure = self._failure("empty_execute_result")
        except Exception as exc:
            result = {
                "stdout": stdout.getvalue(),
                "stderr": stderr.getvalue(),
                "action_events": list(ns["_action_events"]),
            }
            error = f"{type(exc).__name__}: {exc}"
            failure = self._failure("task_route_exception", exception_type=type(exc).__name__, message=str(exc))

        turn = dict(state.get("turn_executions") or {})
        turn[instance] = self._turn_entry(code, result, error, failure)
        failed = {faculty: entry["error"] for faculty, entry in turn.items() if entry["error"] is not None}
        aggregate_error = None if not failed else "faculty failures: " + "; ".join(f"{faculty}={message}" for faculty, message in failed.items())
        aggregate_failure = None if not failed else self._failure("faculty_failures", faculties=failed)
        action_names = [str(event.get("action", "action")) for event in result["action_events"]]
        deed = ", ".join(action_names) if action_names else "local computation"
        outcome = "success" if error is None else error
        effective = state["effective_goal"] + f"\n\n[{label}] {deed}: {outcome}."
        return bus.emit(
            "done",
            {
                "turn_executions": turn,
                "last_action": {
                    "code": code,
                    "faculty": instance,
                    "repair_probe": probe is not None,
                },
                "last_code": code,
                "last_result": result,
                "last_error": aggregate_error,
                "last_failure": aggregate_failure,
                "action_frame": None if aggregate_error is None else state.get("action_frame"),
                "effective_goal": effective,
            },
            record=record,
            evidence=payload,
        )


def run(ctx):
    return ExecuteNode().run(ctx)
