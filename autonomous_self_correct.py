from __future__ import annotations
import json
import pathlib

from prompt_sections import (
    section_goal, section_full_run_log,
    section_verified_state, section_current_prompts, section_current_schemas,
    section_lessons, section_run_outcome, assemble_prompt, load_prompt, call_llm,
)
from log import log, history

BASE_PATH = pathlib.Path(__file__).parent
PROMPTS_DIR = BASE_PATH / "prompts"


def reflect(goal: str, backend: str, lessons_depth: int) -> dict:
    user_prompt = assemble_prompt(
        section_goal(goal), section_full_run_log(),
        section_verified_state(), section_current_prompts(), section_current_schemas(),
        section_lessons(lessons_depth), section_run_outcome(),
    )
    analysis = call_llm(load_prompt("self_reflection_system_prompt.txt"), user_prompt, backend, "reflect")
    history("LESSON", json.dumps({
        "goal": goal,
        "outcome": analysis.get("outcome", "unknown"),
        "cycles_used": analysis.get("cycles_used", 0),
        "lessons": analysis.get("lessons", []),
        "patterns_that_worked": analysis.get("patterns_that_worked", []),
        "patterns_that_failed": analysis.get("patterns_that_failed", []),
    }, ensure_ascii=False))
    return analysis


def evolve(analysis: dict) -> list[str]:
    pending: list[tuple[pathlib.Path, str, str, str]] = []

    for key, filename in [("actor_prompt_rewrite", "actor_system_prompt.txt"),
                          ("planner_prompt_rewrite", "planner_system_prompt.txt")]:
        new_content = analysis.get(key, "").strip()
        if not new_content:
            continue
        target = PROMPTS_DIR / filename
        old_content = target.read_text(encoding="utf-8") if target.exists() else ""
        pending.append((target, filename, old_content, new_content))

    for key, filename in [("actor_schema_rewrite", "actor_schema.json"),
                          ("planner_schema_rewrite", "planner_schema.json")]:
        new_content = analysis.get(key, "").strip()
        if not new_content:
            continue
        json.loads(new_content)
        target = PROMPTS_DIR / filename
        old_content = target.read_text(encoding="utf-8") if target.exists() else ""
        pending.append((target, filename, old_content, new_content))

    if not pending:
        return []

    changed: list[str] = []
    for target, filename, old_content, new_content in pending:
        history("EVOLVED", json.dumps({
            "file": filename, "old_len": len(old_content), "new_len": len(new_content),
        }, ensure_ascii=False))
        target.write_text(new_content, encoding="utf-8")
        changed.append(filename)
        log(f"EVOLVED: {filename} ({len(old_content)} → {len(new_content)} chars)")
    return changed


def _rotate_history() -> None:
    history_path = BASE_PATH / "execution_history.txt"
    if not history_path.exists():
        return
    lines = history_path.read_text(encoding="utf-8").splitlines()
    keep = [l for l in lines if "[LESSON]" in l or "[RUN_START]" in l or "[RUN_END]" in l]
    history_path.write_text("\n".join(keep) + "\n" if keep else "", encoding="utf-8")
    log(f"ROTATED history: {len(lines)} lines → {len(keep)} lines")
