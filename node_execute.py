"""[node_execute] — the author. Thou writest [code] as a script artifact upon the disk,
then handest it to [node_run] by the "built" signal. The running is [node_run]'s office.

One [executor], one [runner], no division of faculty. The executor's sole office is to
fashion a [Python] script from the [LLM]. Whatsoever the
script hath need of — desktop, files, shell, web — it importeth and calleth of itself; there is
no wired split of browser, editor, nor terminal.
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

    def _write_artifact(self, code):
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(code.encode("utf-8", errors="replace")).hexdigest()[:16]
        path = ARTIFACT_DIR / f"{FACULTY}_{digest}.py"
        path.write_text(code, encoding="utf-8", newline="\n")
        return str(path)

    def run(self, ctx):
        state = ctx["state"]
        payload = self.build_payload(ctx)
        record = self.think(ctx)
        code = record.data["code"]
        label = "EXECUTE"
        artifact_path = self._write_artifact(code)
        artifact = {"path": artifact_path, "label": label}
        effective = bus.append_narrative(state["effective_goal"], f"\n\n[{label}] I have authored the script artifact {pathlib.Path(artifact_path).name}.", root_goal=state.get("goal", ""))
        return bus.emit("built", {"_execute_artifact": artifact, "effective_goal": effective}, record=record, evidence=payload)


def run(ctx):
    return ExecuteNode().run(ctx)
