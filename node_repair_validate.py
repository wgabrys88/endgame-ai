import hashlib
import time

import core_bus as bus
from core_node_base import BaseNode


class RepairValidateNode(BaseNode):
    prompt_key = "node_repair_validate"
    expected_record_type = "repair_validation"

    def _prepare(self, ctx):
        state = ctx["state"]
        repair = state["repair_validation"]
        if repair["status"] != "probing":
            raise RuntimeError(f"repair validation requires probing status, got {repair['status']!r}")
        probe = repair["probe"]
        after_observation = bus.observation_brief(state)
        observed_at = after_observation["observed_at"]
        probe_started_at = float(repair.get("probe_started_at", 0))
        probe_observed_at = float(repair.get("probe_observed_at", 0))
        # Validate: pre-probe observation should exist (probe_observed_at > 0)
        # and post-probe observation should be newer than pre-probe
        if probe_observed_at <= 0:
            raise RuntimeError("repair validation requires a pre-probe observation (probe_observed_at not set)")
        if observed_at is None or float(observed_at) <= probe_observed_at:
            raise RuntimeError("repair validation requires a fresh post-probe observation newer than pre-probe")
        # Also ensure probe actually ran after pre-probe observation
        if probe_started_at > 0 and probe_started_at < probe_observed_at:
            raise RuntimeError("probe started before pre-probe observation; timing invalid")
        executions = bus.execution_evidence(state)
        faculties = executions["faculties"]
        if probe["faculty"] not in faculties:
            raise RuntimeError(f"repair probe produced no execution evidence for faculty {probe['faculty']!r}")
        execution = faculties[probe["faculty"]]
        expected_hash = hashlib.sha256(probe["code"].encode("utf-8", errors="replace")).hexdigest()
        if execution["code_sha256"] != expected_hash:
            raise RuntimeError("repair validation execution does not match the authored probe code")
        self._repair = repair
        self._after = {
            "executions": executions,
            "observation": after_observation,
            "last_action": state["last_action"],
            "last_result": state["last_result"],
            "last_error": state["last_error"],
            "last_failure": state["last_failure"],
        }

    def build_payload(self, ctx):
        self._prepare(ctx)
        state = ctx["state"]
        return {
            "goal": state["goal"],
            "repair_id": self._repair["repair_id"],
            "repair_summary": self._repair["summary"],
            "expected_validation": self._repair["expected_validation"],
            "activation": self._repair["activation"],
            "candidate_commit": self._repair["commit"],
            "probe": self._repair["probe"],
            "before": self._repair["baseline"],
            "after": self._after,
            "focus": bus.state_brief(state),
            "observation": self._after["observation"],
        }

    def evidence(self, ctx):
        if not hasattr(self, "_after"):
            self._prepare(ctx)
        return {
            "repair_id": self._repair["repair_id"],
            "before": self._repair["baseline"],
            "after": self._after,
        }

    def signal_from_data(self, data, ctx):
        signal = data["next_signal"]
        resolved = data["resolved"]
        if signal not in {"repair_resolved", "repair_unresolved"}:
            raise RuntimeError(f"unknown repair validation signal: {signal!r}")
        if (signal == "repair_resolved") != resolved:
            raise RuntimeError(f"repair validation signal/resolved mismatch: {signal!r}/{resolved!r}")
        self._signal = signal
        self._resolved = resolved
        return signal

    def patch_from_record(self, record, ctx):
        state, data = ctx["state"], record.data
        validated_at = time.time()
        status = "resolved" if self._resolved else "unresolved"
        repair = {
            **self._repair,
            "status": status,
            "resolved": self._resolved,
            "comparison": data["comparison"],
            "conclusion": data["conclusion"],
            "after": self._after,
            "validated_at": validated_at,
        }
        summary = {
            "repair_id": repair["repair_id"],
            "status": status,
            "resolved": self._resolved,
            "failure_signature": repair["baseline"]["failure_signature"],
            "candidate_commit": repair["commit"]["commit"],
            "summary": repair["summary"],
            "expected_validation": repair["expected_validation"],
            "probe_faculty": repair["probe"]["faculty"],
            "probe_description": repair["probe"]["description"],
            "comparison": data["comparison"],
            "conclusion": data["conclusion"],
            "validated_at": validated_at,
        }
        history = list(state.get("repair_history") or [])
        history.append(summary)
        original_step = repair["baseline"]["step"]
        self_modify = dict(state["self_modify"])
        self_modify["status"] = "behaviorally_resolved_pending_acceptance" if self._resolved else "behaviorally_rejected"
        self_modify["behavioral_validation"] = summary
        effective = (
            state["effective_goal"]
            + f"\n\n[REPAIR VALIDATION] {status.upper()}: {data['comparison']} "
            + f"Conclusion: {data['conclusion']}."
        )
        patch = {
            "repair_validation": repair,
            "last_repair_validation": summary,
            "repair_history": history,
            "self_modify": self_modify,
            "current_step": original_step,
            "step_goal": original_step["description"],
            "action_frame": None,
            "turn_executions": {},
            "_dispatch_targets": [],
            "_barrier_release_signal": "join",
            "effective_goal": effective,
        }
        if self._resolved:
            patch.update(
                {
                    "last_error": None,
                    "last_failure": None,
                    "failure_streak": {"signature": None, "count": 0},
                }
            )
        else:
            failure = {
                "source": "repair_validation",
                "kind": "repair_not_resolved",
                "repair_id": repair["repair_id"],
                "failure_signature": repair["baseline"]["failure_signature"],
                "candidate_commit": repair["commit"]["commit"],
                "comparison": data["comparison"],
                "conclusion": data["conclusion"],
            }
            patch.update(
                {
                    "last_error": f"Behavioral repair validation failed: {data['conclusion']}",
                    "last_failure": failure,
                }
            )
        return patch


def run(ctx):
    return RepairValidateNode().run(ctx)
