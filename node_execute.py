"""node_execute — the author. Writes code as a script artifact on disk, then hands
off to node_run via the "built" signal. Running is node_run's job.

Two-phase execution: this node authors code (from the LLM, or replays a repair
probe) and persists it as a volatile script node under runtime/. The wheel then
routes to node_run which loads and executes the artifact. Authoring and running
are separate wired steps so the topology controls the boundary.
"""
import hashlib
import pathlib

import core_bus as bus
import core_nodes as nodes
from core_node_base import BaseNode

ROOT = pathlib.Path(__file__).resolve().parent
ARTIFACT_DIR = ROOT / "runtime_artifacts"


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

    @staticmethod
    def _repair_probe(state, instance):
        repair = state.get("repair_validation") or {}
        if repair.get("status") != "probing":
            return None
        probe = repair["probe"]
        return probe if probe["faculty"] == instance else None

    def _write_artifact(self, instance, code):
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(code.encode("utf-8", errors="replace")).hexdigest()[:16]
        path = ARTIFACT_DIR / f"{instance}_{digest}.py"
        path.write_text(code, encoding="utf-8", newline="\n")
        return str(path)

    def run(self, ctx):
        state = ctx["state"]
        instance = ctx["node_instance"]
        targets = state.get("_dispatch_targets") or []
        if f"node_execute:{instance}" not in targets:
            return bus.emit("built")

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

        artifact_path = self._write_artifact(instance, code)
        artifacts = dict(state.get("_execute_artifacts") or {})
        artifacts[instance] = {"code": code, "path": artifact_path, "label": label, "repair_probe": probe is not None}
        effective = bus.append_narrative(state["effective_goal"], f"\n\n[{label}] Authored script artifact {pathlib.Path(artifact_path).name}.", root_goal=state.get("goal", ""))
        return bus.emit(
            "built",
            {"_execute_artifacts": artifacts, "effective_goal": effective},
            record=record,
            evidence=payload,
        )


def run(ctx):
    return ExecuteNode().run(ctx)
