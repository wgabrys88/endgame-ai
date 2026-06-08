from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import MUTABLE_PROMPT_END, MUTABLE_PROMPT_START
from lessons import Lessons
from self_evolution import (
    maybe_apply_prompt_mutation,
    maybe_switch_to_code_evolution_goal,
    mutate_prompt_text,
    process_reflection_result,
)


class BoardStub:
    def __init__(self) -> None:
        self.agent_id = "main"
        self.iteration = 7
        self.goal = "original user goal"
        self.original_goal = "original user goal"
        self.mode = "direct"
        self.plan_steps: list[str] = []
        self.plan_step_index = 0
        self.notes: list[str] = []
        self.pid_integral = 1.0

    def rewrite_goal(self, new_goal: str) -> None:
        self.goal = new_goal

    def reset_pid_integral(self) -> None:
        self.pid_integral = 0.0


def prompt_text(slot_line: str = "- Old mutable lesson.") -> str:
    return "\n".join([
        "You are an execution module in a desktop automation system.",
        "",
        "Immutable setup line.",
        MUTABLE_PROMPT_START,
        slot_line,
        MUTABLE_PROMPT_END,
        "Immutable footer line.",
    ])


def workspace_tempdir() -> tempfile.TemporaryDirectory[str]:
    scratch_root = Path("C:/tmp")
    scratch_root.mkdir(exist_ok=True)
    return tempfile.TemporaryDirectory(dir=scratch_root)


class SelfEvolutionTests(unittest.TestCase):
    def test_mutate_prompt_text_changes_one_mutable_line_only(self) -> None:
        original = prompt_text()
        updated, result = mutate_prompt_text("actor", original, "- Learned: Prefer focus before relaunching visible windows.")

        self.assertTrue(result.applied)
        self.assertIn("- Learned: Prefer focus before relaunching visible windows.", updated)
        self.assertTrue(updated.startswith("You are an execution module in a desktop automation system."))
        self.assertIn("Immutable setup line.", updated)
        self.assertIn("Immutable footer line.", updated)
        self.assertNotIn("- Old mutable lesson.", updated)

    def test_mutate_prompt_text_rejects_missing_markers(self) -> None:
        updated, result = mutate_prompt_text("actor", "You are stable.\nNo mutable region.", "- Learned: Something.")

        self.assertFalse(result.applied)
        self.assertEqual("mutable_markers_missing", result.reason)
        self.assertEqual("You are stable.\nNo mutable region.", updated)

    def test_prompt_mutations_disabled_still_stores_lesson(self) -> None:
        with workspace_tempdir() as tmp:
            lessons_path = Path(tmp) / "lessons.json"
            with patch("lessons._PATH", lessons_path):
                board = BoardStub()
                result = {
                    "outcome": "failure",
                    "diagnosis": "The actor repeated a failed click without using visible evidence.",
                    "lesson": "When a click repeats without progress, choose a different visible action.",
                    "checklist_rewrite": [],
                    "used_fields": ["recent_history", "last_action"],
                }

                process_reflection_result(board, result, prompt_mutations_enabled=False)

                data = json.loads(lessons_path.read_text(encoding="utf-8"))
                self.assertEqual(["When a click repeats without progress, choose a different visible action."], data["insights"])
                self.assertEqual("original user goal", board.goal)

    def test_prompt_mutation_requires_threshold_and_marks_batch(self) -> None:
        with workspace_tempdir() as tmp:
            root = Path(tmp)
            lessons_path = root / "lessons.json"
            prompts_dir = root / "prompts"
            prompts_dir.mkdir()
            (prompts_dir / "actor.txt").write_text(prompt_text(), encoding="utf-8")
            with patch("lessons._PATH", lessons_path), patch("self_evolution.PROMPTS_DIR", prompts_dir):
                store = Lessons()
                for index in range(3):
                    store.add_lesson(
                        f"When actor action repeats {index}, choose fresh visible evidence",
                        role="actor",
                        issue_key="actor:repeat-action",
                        diagnosis="repeated action",
                        source_iteration=index,
                    )
                store.save()

                result = maybe_apply_prompt_mutation(store, "actor", 10)
                store.save()

                prompt = (prompts_dir / "actor.txt").read_text(encoding="utf-8")
                data = json.loads(lessons_path.read_text(encoding="utf-8"))
                self.assertTrue(result.applied)
                self.assertIn("- Learned: When actor action repeats 2, choose fresh visible evidence.", prompt)
                self.assertTrue(all(entry["prompt_applied"] for entry in data["entries"]))
                self.assertEqual(1, len(data["prompt_mutations"]))

    def test_tier3_switches_after_repeated_issue_and_prompt_mutations(self) -> None:
        with workspace_tempdir() as tmp:
            lessons_path = Path(tmp) / "lessons.json"
            with patch("lessons._PATH", lessons_path):
                store = Lessons()
                for index in range(6):
                    entry = store.add_lesson(
                        f"Planner should stop repeating the stale step number {index}",
                        role="planner",
                        issue_key="planner:stale-step",
                        diagnosis="stale step",
                        source_iteration=index,
                    )
                    self.assertIsNotNone(entry)
                store.data["prompt_mutations"] = [
                    {"issue_key": "planner:stale-step"},
                    {"issue_key": "planner:stale-step"},
                ]
                board = BoardStub()

                switched = maybe_switch_to_code_evolution_goal(board, store)

                self.assertTrue(switched)
                self.assertIn("TIER3 CODE EVOLUTION", board.goal)
                self.assertEqual(0.0, board.pid_integral)
                self.assertTrue(board.plan_steps[0].startswith("Use read_file path=lessons.json"))


if __name__ == "__main__":
    unittest.main()
