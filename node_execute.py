"""node_execute — the author. Writes code as a script artifact on disk, then hands
off to node_run via the "built" signal. Running is node_run's job.

One executor, one runner, no faculty distinction. The executor's only job is to
create a Python script (from the LLM, or replay a repair probe). Whatever the
script needs — desktop, files, shell, web — it imports and calls itself; there is
no wired browser/editor/terminal split.
"""
import hashlib
import pathlib

import core_bus as bus
import core_nodes as nodes
from core_node_base import BaseNode

ROOT = pathlib.Path(__file__).resolve().parent
ARTIFACT_DIR = ROOT / "runtime_artifacts"
FACULTY = "exec"


class ExecuteNode(BaseNode):
    prompt_key = "node_execute"
    expected_record_type = "execution"

    def build_payload(self, ctx):
        state = ctx["state"]
        step = state.get("current_step") or {}
        return {
            "goal": state["goal"],
            "step": {"description": step.get("description", state["goal"]), "done_when": step.get("done_when", "")},
            "action_frame": state.get("action_frame"),
            "focus": bus.state_brief(state),
            "observation": bus.observation_brief(state),
            "capabilities": nodes.capability_manifest(ctx),
        }

    @staticmethod
    def _repair_probe(state):
        repair = state.get("repair_validation") or {}
        return repair["probe"] if repair.get("status") == "probing" else None

    def _write_artifact(self, code):
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(code.encode("utf-8", errors="replace")).hexdigest()[:16]
        path = ARTIFACT_DIR / f"{FACULTY}_{digest}.py"
        path.write_text(code, encoding="utf-8", newline="\n")
        return str(path)

    def run(self, ctx):
        state = ctx["state"]
        payload = self.build_payload(ctx)
        probe = self._repair_probe(state)
        if probe is None:
            record = self.think(ctx)
            code = record.data["code"]
            label = "EXECUTE"
        else:
            code = probe["code"]
            record = bus.Record.create(
                "execution",
                {"code": code},
                reasoning=f"Behavioral repair probe {state['repair_validation']['repair_id']} retries failure {probe['failure_signature']}.",
            )
            payload["repair_probe"] = {
                "repair_id": state["repair_validation"]["repair_id"],
                "failure_signature": probe["failure_signature"],
                "comparison_basis": probe["comparison_basis"],
            }
            label = "REPAIR_EXECUTE"

        artifact_path = self._write_artifact(code)
        artifact = {"path": artifact_path, "label": label, "repair_probe": probe is not None}
        effective = bus.append_narrative(state["effective_goal"], f"\n\n[{label}] Authored script artifact {pathlib.Path(artifact_path).name}.", root_goal=state.get("goal", ""))
        return bus.emit("built", {"_execute_artifact": artifact, "effective_goal": effective}, record=record, evidence=payload)


def run(ctx):
    return ExecuteNode().run(ctx)
