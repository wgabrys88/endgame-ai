"""[node_execute] — the author. Thou discernest the single next deed toward the goal
and writest [code] as a script artifact upon the disk, then handest it to [node_run]
by the "built" signal. The running is [node_run]'s office.

Decomposition liveth in the deed itself, for the
executor may author a long, multi-chained script. Whatsoever the script hath need of — desktop, files, shell, web,
or the rewriting of the body — it importeth and calleth of itself.
"""
import hashlib
import pathlib

import core_bus as bus
from core_node_base import BaseNode

ROOT = pathlib.Path(__file__).resolve().parent
ARTIFACT_DIR = ROOT / "runtime_artifacts"
FACULTY = "exec"


class ExecuteNode(BaseNode):
    prompt_key = "node_execute"
    expected_record_type = "execution"

    def build_payload(self, ctx):
        state = ctx["state"]
        return {
            "goal": state["goal"],
            "action_frame": state.get("action_frame"),
            "focus": bus.state_brief(state),
            "observation": bus.observation_brief(state),
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
        data = record.data
        code = data["code"]
        intent = str(data["intent"]).strip()
        done_when = str(data["done_when"]).strip()
        if not intent or not done_when:
            raise RuntimeError("execution requires non-empty intent and done_when")
        label = "EXECUTE"
        artifact_path = self._write_artifact(code)
        artifact = {"path": artifact_path, "label": label}
        interps = bus.with_interpretation(state.get("goal_interpretations"), "execute", str(data.get("goal_interpretation") or ""))
        return bus.emit("built", {"_execute_artifact": artifact, "current_deed": {"description": intent, "done_when": done_when}, "goal_interpretations": interps}, record=record, evidence=payload)


def run(ctx):
    return ExecuteNode().run(ctx)
