"""[node_repair_probe] — Thou shalt consume a candidate awaiting and its captured baseline; and thou shalt author one behavioral [probe] with code and criteria of comparison that may be beheld, then emit 'probe_ready'."""
import time

import core_bus as bus
import core_nodes as nodes
from core_node_base import BaseNode


class RepairProbeNode(BaseNode):
    prompt_key = "node_repair_probe"
    expected_record_type = "repair_probe"

    def build_payload(self, ctx):
        state = ctx["state"]
        repair = state["repair_validation"]
        if repair["status"] != "awaiting_probe":
            raise RuntimeError(f"repair probe requires awaiting_probe status, got {repair['status']!r}")
        self._repair = repair
        self._baseline = repair["baseline"]
        return {
            "goal": state["goal"],
            "repair_id": repair["repair_id"],
            "repair_summary": repair["summary"],
            "expected_validation": repair["expected_validation"],
            "activation": repair["activation"],
            "candidate_commit": repair["commit"],
            "original_failure": self._baseline,
            "focus": bus.state_brief(state),
            "observation": bus.observation_brief(state),
            "capabilities": nodes.capability_manifest(ctx),
        }

    def signal_from_data(self, data, ctx):
        if data["failure_signature"] != self._baseline["failure_signature"]:
            raise RuntimeError(
                "repair probe changed the failure identity: "
                f"expected {self._baseline['failure_signature']!r}, got {data['failure_signature']!r}"
            )
        return "probe_ready"

    def patch_from_record(self, record, ctx):
        state, data = ctx["state"], record.data
        probe_started_at = time.time()
        original_step = self._baseline["step"]
        probe = {
            "failure_signature": data["failure_signature"],
            "description": data["description"],
            "done_when": data["done_when"],
            "comparison_basis": data["comparison_basis"],
            "code": data["code"],
            "authored_at": probe_started_at,
        }
        repair = {
            **self._repair,
            "status": "probing",
            "probe": probe,
            "probe_started_at": probe_started_at,
        }
        current_step = {
            "description": (
                f"Behavioral repair probe for original step: {original_step['description']}. "
                f"Probe: {data['description']}"
            ),
            "done_when": data["done_when"],
        }
        effective = bus.append_narrative(
            state["effective_goal"],
            f"\n\n[REPAIR PROBE] I retry the failure {data['failure_signature']}. The proof required: {data['done_when']}.",
            root_goal=state.get("goal", ""),
        )
        return {
            "repair_validation": repair,
            "current_step": current_step,
            "step_goal": current_step["description"],
            "action_frame": None,
            "turn_executions": {},
            "last_error": None,
            "last_failure": None,
            "effective_goal": effective,
        }


def run(ctx):
    return RepairProbeNode().run(ctx)
